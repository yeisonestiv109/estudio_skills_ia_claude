"""
TheirStackAdapter — implementación de PuertoFuenteTriggers y PuertoDescubridorEmpresas.
...
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import requests

from src.core.domain.models import (
    Empresa,
    EstadoEmpresa,
    ManifiestoICP,
    NivelConfianza,
    OrigenTrigger,
    TamanoEmpresa,
    Trigger,
)
from src.core.ports.interfaces import PuertoDescubridorEmpresas, PuertoFuenteTriggers

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.theirstack.com/v1"
_JOBS_ENDPOINT = f"{_BASE_URL}/jobs/search"
_REQUEST_TIMEOUT_SECS = 15


def _calcular_nivel_confianza(n_vacantes: int) -> NivelConfianza | None:
    if n_vacantes >= 3:
        return NivelConfianza.ALTA
    if n_vacantes >= 1:
        return NivelConfianza.MEDIA
    return None


def _parsear_fecha(fecha_str: str | None) -> datetime | None:
    if not fecha_str:
        return None
    try:
        if "T" in fecha_str:
            return datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        return datetime.strptime(fecha_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _inferir_tamano(employee_count: int | None) -> TamanoEmpresa:
    """
    Mapea el número entero de empleados (campo employee_count de TheirStack)
    al Enum TamanoEmpresa. Reemplaza el mapeo por string employee_count_range,
    que fallaba dejando empresas grandes clasificadas como SME.

    Lógica real:
        < 50        → STARTUP
        50 – 200    → SME
        201 – 1000  → MID_MARKET
        > 1000      → ENTERPRISE
    """
    if not employee_count or employee_count <= 0:
        return TamanoEmpresa.SME  # Valor seguro por defecto ante dato ausente
    if employee_count < 50:
        return TamanoEmpresa.STARTUP
    if employee_count <= 200:
        return TamanoEmpresa.SME
    if employee_count <= 1000:
        return TamanoEmpresa.MID_MARKET
    return TamanoEmpresa.ENTERPRISE


class TheirStackAdapter(PuertoFuenteTriggers, PuertoDescubridorEmpresas):
    """
    Adaptador Motor 2 dual — TheirStack.

    Implementa PuertoFuenteTriggers (Caso A: Scoring) y
    PuertoDescubridorEmpresas (Caso B: Discovery).

    Args:
        api_key: Clave de API de TheirStack. Si None, lee de THEIRSTACK_API_KEY.
        tecnologias_objetivo: Lista de tecnologías del ManifiestoICP.
                              Usadas tanto en scoring como en discovery.
        max_resultados_scoring: Límite de vacantes al evaluar una empresa conocida.
        max_empresas_discovery: Límite de empresas a descubrir por llamada de discovery.
    """

    def __init__(
        self,
        api_key: str | None = None,
        tecnologias_objetivo: list[str] | None = None,
        max_resultados_scoring: int = 3,
        max_empresas_discovery: int = 5,
    ) -> None:
        self._api_key = api_key or os.getenv("THEIRSTACK_API_KEY")
        self._tecnologias = tecnologias_objetivo or []
        self._max_scoring = max_resultados_scoring
        self._max_discovery = max_empresas_discovery

        if not self._api_key:
            logger.warning(
                "THEIRSTACK_API_KEY no configurada. "
                "TheirStackAdapter retornará listas vacías hasta que se configure."
            )

    # ──────────────────────────────────────────────────────────────────────
    # Caso A: SCORING — PuertoFuenteTriggers
    # ──────────────────────────────────────────────────────────────────────
    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Busca vacantes técnicas abiertas para una empresa conocida y retorna Triggers.
        Implementa PuertoFuenteTriggers.obtener_triggers().
        """
        if not self._api_key:
            return []

        payload = {
            "limit": self._max_scoring,
            "order_by": [{"desc": True, "field": "date_posted"}],
            "company_domain_or": [empresa.dominio],
        }
        if self._tecnologias:
            # Convertir nombre oficial completo → slug kebab-case de TheirStack
            # "Amazon Web Services" → "amazon-web-services"
            payload["company_technology_slug_or"] = [
                t.lower().replace(" ", "-") for t in self._tecnologias
            ]

        data = self._llamar_api(payload, contexto=f"scoring de '{empresa.nombre}'")
        if data is None:
            return []

        return self._parsear_triggers(data, empresa)

    def _parsear_triggers(self, data: dict, empresa: Empresa) -> list[Trigger]:
        vacantes = data.get("data", [])
        nivel = _calcular_nivel_confianza(len(vacantes))
        if nivel is None:
            return []

        techs = set()
        fecha_evento: datetime | None = None
        for v in vacantes:
            for t in v.get("technologies", []):
                techs.add(t.get("name", str(t)) if isinstance(t, dict) else str(t))
            if fecha_evento is None:
                fecha_evento = _parsear_fecha(v.get("date_posted"))

        titulo_sample = (
            vacantes[0].get("title", "Vacante técnica")
            if vacantes
            else "Vacante técnica"
        )
        techs_str = ", ".join(sorted(techs)) if techs else "no especificadas"

        # Si alcanzamos el techo de paginación, hay más señales ocultas: mostrar "+N".
        n_vacantes = len(vacantes)
        conteo_str = (
            f"+{n_vacantes}" if n_vacantes >= self._max_scoring else str(n_vacantes)
        )

        descripcion = (
            f"{conteo_str} vacante(s) técnica(s) abiertas en '{empresa.nombre}'. "
            f"Ejemplo: '{titulo_sample}'. Tecnologías: {techs_str}."
        )

        logger.info(
            "TheirStack SCORING: '%s' — %d vacantes → confianza %s",
            empresa.nombre,
            len(vacantes),
            nivel.value,
        )
        return [
            Trigger(
                empresa_id=empresa.id,
                origen=OrigenTrigger.THEIRSTACK,
                nivel_confianza=nivel,
                descripcion=descripcion,
                fecha_evento=fecha_evento,
            )
        ]

    # ──────────────────────────────────────────────────────────────────────
    # Caso B: DISCOVERY — PuertoDescubridorEmpresas
    # ──────────────────────────────────────────────────────────────────────
    def descubrir_empresas(self, manifesto: ManifiestoICP) -> list[Empresa]:
        """
        Busca empresas que publican vacantes para las tecnologías del ICP.
        Retorna Empresa(estado=DESCUBIERTA) para cada candidata encontrada.
        Implementa PuertoDescubridorEmpresas.descubrir_empresas().
        """
        if not self._api_key:
            return []

        # Para discovery, usamos las tecnologías del manifesto (no del constructor)
        tecnologias = manifesto.anclaje_tecnologico or self._tecnologias
        if not tecnologias:
            logger.warning(
                "TheirStack DISCOVERY: sin tecnologías en ICP. Retornando []."
            )
            return []

        payload: dict = {
            "limit": self._max_discovery,
            "order_by": [{"desc": True, "field": "date_posted"}],
            "company_technology_slug_or": [
                t.lower().replace(" ", "-") for t in tecnologias
            ],
            # Filtro obligatorio de TheirStack (E-024): debe proveerse al menos uno de
            # posted_at_max_age_days, posted_at_gte o company_domain_or.
            # Usamos 30 días: ventana alineada con TriggerAggregationPolicy (45 días).
            # Señales de >30 días ya serían candidatas a descartar por data decay.
            "posted_at_max_age_days": 30,
        }

        # Filtros adicionales derivados del ManifiestoICP
        if manifesto.geografia and manifesto.geografia.upper() != "LATAM":
            payload["company_country_code_or"] = [manifesto.geografia[:2].upper()]

        data = self._llamar_api(
            payload,
            contexto=f"discovery ICP={manifesto.categoria_empresa.value}",
        )
        if data is None:
            return []

        return self._parsear_empresas_descubiertas(data, manifesto)

    def _parsear_empresas_descubiertas(
        self, data: dict, manifesto: ManifiestoICP
    ) -> list[Empresa]:
        """
        Convierte la respuesta de TheirStack en objetos Empresa con estado=DESCUBIERTA.

        Deduplicamos por dominio para evitar crear el mismo objeto varias veces
        cuando TheirStack retorna múltiples vacantes de la misma empresa.
        """
        vacantes = data.get("data", [])
        empresas_vistas: set[str] = set()
        empresas: list[Empresa] = []

        for vacante in vacantes:
            empresa_data = vacante.get("company_object", {}) or {}
            dominio = (empresa_data.get("domain") or "").strip().lower()
            nombre = (empresa_data.get("name") or vacante.get("company") or "").strip()

            if not dominio or not nombre:
                logger.debug(
                    "TheirStack DISCOVERY: vacante sin dominio/nombre, omitida."
                )
                continue

            if dominio in empresas_vistas:
                continue
            empresas_vistas.add(dominio)

            tamano = _inferir_tamano(empresa_data.get("employee_count"))
            pais = empresa_data.get("country_code", "CO") or "CO"

            empresa = Empresa(
                nombre=nombre,
                dominio=dominio,
                tamano=tamano,
                vertical=manifesto.vertical,
                pais=pais.upper()[:2],
                estado=EstadoEmpresa.DESCUBIERTA,
            )
            empresas.append(empresa)

        logger.info(
            "TheirStack DISCOVERY: %d empresa(s) únicas descubiertas para ICP '%s'.",
            len(empresas),
            manifesto.categoria_empresa.value,
        )
        return empresas

    # ──────────────────────────────────────────────────────────────────────
    # Método HTTP compartido — lógica de red centralizada
    # ──────────────────────────────────────────────────────────────────────
    def _llamar_api(self, payload: dict, contexto: str) -> dict | None:
        """
        Ejecuta la llamada POST a TheirStack con reintentos ante 429/5xx.
        Retorna None ante cualquier error definitivo (contrato: nunca propagar al Core).
        """
        _REINTENTABLES = {429, 500, 502, 503, 504}
        for intento in range(3):  # 0 = primera llamada, 1 y 2 = reintentos
            try:
                logger.info(
                    "TheirStack: consultando API [%s] (intento %d)",
                    contexto,
                    intento + 1,
                )
                response = requests.post(
                    _JOBS_ENDPOINT,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=_REQUEST_TIMEOUT_SECS,
                )
                if response.status_code in _REINTENTABLES and intento < 2:
                    logger.warning(
                        "TheirStack: HTTP %d [%s]. Reintento en 2s...",
                        response.status_code,
                        contexto,
                    )
                    time.sleep(2)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                logger.warning("TheirStack: timeout [%s]. Retornando None.", contexto)
                return None
            except requests.exceptions.HTTPError as exc:
                logger.warning(
                    "TheirStack: HTTP %s [%s]. Retornando None.",
                    exc.response.status_code if exc.response else "?",
                    contexto,
                )
                return None
            except requests.exceptions.RequestException as exc:
                logger.error("TheirStack: error de red [%s]: %s", contexto, exc)
                return None
            except Exception as exc:
                logger.error("TheirStack: error inesperado [%s]: %s", contexto, exc)
                return None
        return None
