"""
ApolloHunterCascadaAdapter — implementación de PuertoEnriquecedorContactos.

Diseño completo: `02_Lineas_de_Producto/Outbound_Prospector/docs/tecnico/prospector-m3-m4-design.md` §3.1-§3.2.

Orquesta la cascada barato→caro:
    1. Apollo descubre perfiles por cargo dentro del dominio de la Empresa.
    2. Por cada perfil con email candidato, Hunter verifica entregabilidad.
    3. Por cada perfil SIN email, Hunter intenta inferir el patrón del dominio.
    4. PoliticaMapeoEstadoCorreo traduce el resultado crudo a EstadoCorreo/confianza_dato.

REGLA DE CORTE DE COSTO (crítica, exigida por el Principal Architect):
    Si Apollo devuelve 0 perfiles, el método retorna inmediatamente. NINGÚN
    request de red se hace a Hunter. El gasto de Hunter (0.5 créd/verify) solo
    ocurre sobre perfiles que Apollo efectivamente encontró.

Firma stateless (enriquecer(empresa, cargos)): este adaptador no guarda
contexto de job entre llamadas. Es seguro invocarlo en paralelo sobre
múltiples empresas.

Contrato de error: nunca propaga excepciones al Core. Los clientes HTTP
subyacentes (ApolloClient, HunterClient) ya contienen sus propios errores de
red y retornan [] / None; este adaptador únicamente compone esos resultados.
"""

from __future__ import annotations

import logging

from src.adapters.enrichment.apollo_client import ApolloClient
from src.adapters.enrichment.hunter_client import HunterClient
from src.adapters.enrichment.mapeo_estado_correo import PoliticaMapeoEstadoCorreo
from src.core.domain.models import AutoridadDecision, Decisor, Empresa, Seniority
from src.core.ports.interfaces import PuertoEnriquecedorContactos

logger = logging.getLogger(__name__)

# Mapeo heurístico de fragmentos de cargo → Seniority. Determinista, sin LLM.
# Se evalúa en orden: el primer fragmento que matchea (case-insensitive) gana.
_FRAGMENTOS_SENIORITY: tuple[tuple[str, Seniority], ...] = (
    ("chief", Seniority.C_LEVEL),
    ("ceo", Seniority.C_LEVEL),
    ("cto", Seniority.C_LEVEL),
    ("cfo", Seniority.C_LEVEL),
    ("coo", Seniority.C_LEVEL),
    ("vp", Seniority.VP),
    ("vice president", Seniority.VP),
    ("director", Seniority.DIRECTOR),
    ("head of", Seniority.DIRECTOR),
    ("manager", Seniority.MANAGER),
    ("gerente", Seniority.MANAGER),
    ("lead", Seniority.LEAD),
)

_CARGOS_DECISION_MAKER: frozenset[str] = frozenset(
    {"chief", "ceo", "cto", "cfo", "coo", "vp", "vice president", "director"}
)


def _inferir_seniority(cargo: str) -> Seniority:
    cargo_lower = cargo.lower()
    for fragmento, nivel in _FRAGMENTOS_SENIORITY:
        if fragmento in cargo_lower:
            return nivel
    return Seniority.IC


def _inferir_autoridad(cargo: str) -> AutoridadDecision:
    cargo_lower = cargo.lower()
    if any(frag in cargo_lower for frag in _CARGOS_DECISION_MAKER):
        return AutoridadDecision.DECISION_MAKER
    if "manager" in cargo_lower or "gerente" in cargo_lower or "lead" in cargo_lower:
        return AutoridadDecision.INFLUENCER
    return AutoridadDecision.UNKNOWN


class ApolloHunterCascadaAdapter(PuertoEnriquecedorContactos):
    """
    Adaptador Motor 3 — Cascada Apollo (descubridor) → Hunter (validador duro).

    Args:
        apollo_client: Cliente de Apollo. Si None, se instancia uno por defecto
            (lee APOLLO_API_KEY del entorno).
        hunter_client: Cliente de Hunter. Si None, se instancia uno por defecto
            (lee HUNTER_API_KEY del entorno).
        politica_mapeo: Política de traducción resultado→EstadoCorreo. Si None,
            se instancia PoliticaMapeoEstadoCorreo() con la calibración aprobada.
        max_perfiles_por_empresa: Límite de perfiles que Apollo puede retornar
            por llamada (control de costo adicional).
    """

    def __init__(
        self,
        apollo_client: ApolloClient | None = None,
        hunter_client: HunterClient | None = None,
        politica_mapeo: PoliticaMapeoEstadoCorreo | None = None,
        max_perfiles_por_empresa: int = 5,
    ) -> None:
        self._apollo = apollo_client or ApolloClient()
        self._hunter = hunter_client or HunterClient()
        self._politica = politica_mapeo or PoliticaMapeoEstadoCorreo()
        self._max_perfiles = max_perfiles_por_empresa

    def enriquecer(self, empresa: Empresa, cargos: list[str]) -> list[Decisor]:
        """
        Implementa PuertoEnriquecedorContactos.enriquecer().

        Contrato: nunca lanza excepción. Ante cualquier fallo no controlado
        se registra el error y se retorna lo acumulado hasta ese punto (o []).
        """
        if not cargos:
            logger.debug(
                "Cascada M3: sin cargos objetivo para '%s'. Retornando [].",
                empresa.nombre,
            )
            return []

        try:
            perfiles = self._apollo.buscar_perfiles(
                dominio=empresa.dominio,
                cargos=cargos,
                max_resultados=self._max_perfiles,
            )
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error(
                "Cascada M3: error inesperado llamando a Apollo para '%s': %s",
                empresa.nombre,
                exc,
            )
            return []

        # ⛔ FRONTERA DE COSTO: Apollo no encontró nada → cero llamadas a Hunter.
        if not perfiles:
            logger.info(
                "Cascada M3: Apollo 0 perfiles para '%s'. Hunter NO se invoca.",
                empresa.nombre,
            )
            return []

        decisores: list[Decisor] = []
        for perfil in perfiles:
            try:
                decisor = self._procesar_perfil(perfil, empresa)
            except Exception as exc:  # noqa: BLE001 — aislar fallos por perfil
                logger.error(
                    "Cascada M3: error procesando perfil de '%s': %s",
                    empresa.nombre,
                    exc,
                )
                continue
            if decisor is not None:
                decisores.append(decisor)

        logger.info(
            "Cascada M3: %d decisor(es) construidos para '%s'.",
            len(decisores),
            empresa.nombre,
        )
        return decisores

    def _procesar_perfil(self, perfil: dict, empresa: Empresa) -> Decisor | None:
        nombre = (perfil.get("name") or "").strip()
        cargo_original = (perfil.get("title") or "").strip()
        email_candidato = perfil.get("email")

        if not nombre or not cargo_original:
            logger.debug(
                "Cascada M3: perfil incompleto (sin nombre/cargo) en '%s'. Omitido.",
                empresa.nombre,
            )
            return None

        if email_candidato:
            hunter_status, hunter_score = self._verificar_con_hunter(email_candidato)
            estado_correo, confianza = self._politica.mapear(
                email_encontrado=True,
                hunter_status=hunter_status,
                hunter_score=hunter_score,
            )
        else:
            patron_inferido = self._inferir_patron_con_hunter(empresa.dominio)
            estado_correo, confianza = self._politica.mapear(
                email_encontrado=False,
                patron_inferido=patron_inferido,
            )

        return Decisor(
            empresa_id=empresa.id,
            nombre=nombre,
            cargo_original=cargo_original,
            cargo_normalizado=cargo_original.upper(),
            seniority=_inferir_seniority(cargo_original),
            autoridad_decision=_inferir_autoridad(cargo_original),
            correo=email_candidato if email_candidato else None,
            estado_correo=estado_correo,
            confianza_dato=confianza,
        )

    def _verificar_con_hunter(self, email: str) -> tuple[str | None, int | None]:
        """
        Invoca Hunter SOLO porque ya hay un email candidato de Apollo (regla de
        corte de costo respetada por construcción: este método nunca se llama
        si `email_candidato` es falsy — ver `_procesar_perfil`).
        """
        try:
            resultado = self._hunter.verificar_email(email)
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error("Cascada M3: error inesperado en Hunter verify: %s", exc)
            return None, None

        if resultado is None:
            return None, None
        return resultado.get("status"), resultado.get("score")

    def _inferir_patron_con_hunter(self, dominio: str) -> bool:
        try:
            return self._hunter.inferir_patron_dominio(dominio)
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error(
                "Cascada M3: error inesperado en Hunter domain-search: %s", exc
            )
            return False
