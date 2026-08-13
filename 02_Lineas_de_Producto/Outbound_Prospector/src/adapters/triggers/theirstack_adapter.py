"""
TheirStackAdapter — implementación de PuertoFuenteTriggers y PuertoDescubridorEmpresas.
...
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests

from src.core.domain.models import (
    PAIS_DESCONOCIDO,
    Empresa,
    EstadoEmpresa,
    EstimacionTamano,
    ManifiestoICP,
    NivelConfianza,
    OrigenTrigger,
    TamanoEmpresa,
    TierUrgencia,
    TipoTrigger,
    Trigger,
)
from src.core.ports.interfaces import (
    PuertoDescubridorEmpresas,
    PuertoEstimadorTamano,
    PuertoFuenteTriggers,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.theirstack.com/v1"
_JOBS_ENDPOINT = f"{_BASE_URL}/jobs/search"
_REQUEST_TIMEOUT_SECS = 15

# Rango de empleados por TamanoEmpresa, para el filtro NATIVO de TheirStack en el
# discovery (min_employee_count / max_employee_count — confirmado en el OpenAPI de
# la API, JobSearchFilters-Input). Mismos cortes que _inferir_tamano.
# FIX 25-jul-2026 (corrida signal-first): sin este filtro, el discovery se sesgaba
# a GRANDES empresas (Experian, Havas, AXA, Postobón…) porque son las que más
# vacantes tech publican en Colombia — no el SME 50-200 del ICP de TBBC. Ahora le
# pedimos a TheirStack directamente el rango del ICP, en vez de traer enterprises
# y filtrarlas después (y gastar créditos en ellas).
_RANGO_EMPLEADOS_POR_TAMANO: dict[TamanoEmpresa, tuple[int | None, int | None]] = {
    TamanoEmpresa.STARTUP: (None, 49),
    TamanoEmpresa.SME: (50, 200),
    TamanoEmpresa.MID_MARKET: (201, 1000),
    TamanoEmpresa.ENTERPRISE: (1001, None),
}

# Bandas de AGING de una vacante tech ABIERTA (recalibración 26-jul-2026, tras
# corrida #5 que salió 12/12 TIER_0 con umbral único de 45d). Una vacante que
# lleva 45-60 días publicada es ciclo de contratación NORMAL, no dolor — por eso
# 45d como TIER_0 automático hacía que casi todo calificara (falso positivo
# masivo). Ahora hay gradación:
#   aging >= _AGING_TIER0_DIAS (75d) → TIER_0: 2.5+ meses sin llenar un rol
#       técnico = sangrado activo real; califica SOLO (200 >= 150).
#   _AGING_TIER1_DIAS (45d) <= aging < 75d → TIER_1: dificultad NOTABLE pero no
#       aguda; NO califica sola (100 < 150), necesita cruce con otro origen.
#   aging < 45d → TIER_2: demanda fresca / contexto (50).
# Así el TIER_0 se reserva para aging FUERTE o para el cruce multi-origen
# (ScoreTriggerPolicy), restaurando la capacidad de discriminar.
_AGING_TIER0_DIAS = 75
_AGING_TIER1_DIAS = 45

# Ventana de descubrimiento/scoring (días). Corte duro coherente con el decay de
# CAUSA de ScoreTriggerPolicy y con SHiFT!.
_VENTANA_DISCOVERY_DIAS = 90

# Patrones (regex, OR) de TÍTULO de vacante que denotan un ROL TÉCNICO de
# construcción de software. Se usan en la query de aging (job_title_pattern_or,
# filtro a nivel de VACANTE — no de empresa) para exigir que la vacante
# envejecida sea REALMENTE de tech (fix corrida #5: company_technology_slug_or
# es a nivel EMPRESA, así que la vacante vieja podía ser de un rol NO técnico —
# ej. contador — en una empresa que alguna vez publicó una vacante Python).
# TheirStack soporta regex case-insensitive en job_title_pattern_or (OpenAPI).
_PATRONES_ROL_TECNICO: list[str] = [
    r"(?i)(desarrollador|developer|programador)",
    r"(?i)(ingenier).*(software|sistemas|datos|backend|frontend|devops|cloud|qa|desarrollo)",
    r"(?i)(software|data|cloud|backend|frontend)\s+engineer",
    r"(?i)(devops|sre|site reliability)",
    r"(?i)(backend|frontend|full[ -]?stack)",
    r"(?i)(arquitect).*(software|soluciones|datos|cloud|nube|ti|it)",
    r"(?i)(tech(nical)? lead|l[ií]der t[eé]cnic)",
    r"(?i)(data scien|machine learning)",
    r"(?i)(analista).*(desarrollo|programaci)",
]

# Patrones (regex, OR) de EXCLUSIÓN por rol NO técnico (fix corrida #6): en
# Colombia "Desarrollador Comercial" / "Desarrollador de Negocio" = VENDEDOR,
# no ingeniero de software. La corrida dio un falso positivo TIER_0 en Aló
# Credit con "Vendedor / Desarrollador Comercial con Moto". Estos términos se
# pasan a job_title_pattern_not (TheirStack excluye el job si el título matchea
# cualquiera), de modo que la exclusión gana sobre el match de rol técnico.
_PATRONES_ROL_NO_TECNICO: list[str] = [
    r"(?i)(comercial|ventas|vendedor|negocio|fidelizaci|marketing|mercadeo)",
]


def _calcular_nivel_confianza(n_vacantes: int) -> NivelConfianza | None:
    if n_vacantes >= 3:
        return NivelConfianza.ALTA
    if n_vacantes >= 1:
        return NivelConfianza.MEDIA
    return None


def _extraer_titulo(vacante: dict) -> str:
    """
    Título de la vacante tolerando ambos esquemas: `job_title` (API real de
    TheirStack) y `title` (mocks de tests / esquemas legados). Fallback a
    'Vacante técnica' si ninguno viene.
    """
    titulo = (vacante.get("job_title") or vacante.get("title") or "").strip()
    return titulo or "Vacante técnica"


def _extraer_tecnologias(vacante: dict) -> set[str]:
    """
    Tecnologías de la vacante tolerando ambos esquemas: `technology_slugs`
    (API real: lista de strings) y `technologies` (mocks: lista de dicts con
    'name' o lista de strings). Retorna un set de nombres/slugs no vacíos.
    """
    techs: set[str] = set()
    for t in vacante.get("technology_slugs") or []:
        if isinstance(t, str) and t.strip():
            techs.add(t.strip())
    for t in vacante.get("technologies") or []:
        if isinstance(t, dict):
            nombre = (t.get("name") or "").strip()
            if nombre:
                techs.add(nombre)
        elif isinstance(t, str) and t.strip():
            techs.add(t.strip())
    return techs


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


class TheirStackAdapter(
    PuertoFuenteTriggers, PuertoDescubridorEmpresas, PuertoEstimadorTamano
):
    """
    Adaptador Motor 2 triple — TheirStack.

    Implementa PuertoFuenteTriggers (Caso A: Scoring), PuertoDescubridorEmpresas
    (Caso B: Discovery) y PuertoEstimadorTamano (waterfall de tamaño — alimenta
    PoliticaCorroboracionTamano junto con otros orígenes independientes).

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

        # Cache de vacantes por dominio, poblada en descubrir_empresas().
        # FIX de raíz (25-jul-2026): antes el discovery hacía 1 llamada y DESCARTABA
        # las vacantes; luego obtener_triggers() y estimar_tamano() RE-CONSULTABAN
        # TheirStack por cada empresa (2 llamadas extra/empresa → ~36 llamadas para
        # 18 empresas) agotando créditos (HTTP 402) y disparando rate limits (429).
        # La respuesta del discovery YA contiene las vacantes (fecha, conteo) y el
        # employee_count de cada empresa: reutilizarla da el trigger EFECTO y el
        # tamaño con CERO llamadas adicionales. Solo se re-consulta para empresas
        # que NO vinieron del discovery de esta instancia (fallback).
        self._discovery_jobs: dict[str, list[dict]] = {}

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
        Retorna Triggers de vacantes técnicas para la empresa.
        Implementa PuertoFuenteTriggers.obtener_triggers().

        VACANTE TÉCNICA VIEJA-Y-ABIERTA, POR BANDAS (recalibración 26-jul-2026,
        tras corrida #5 = 12/12 falsos TIER_0). Para cada finalista se busca una
        vacante de ROL TÉCNICO (job_title_pattern_or), aún abierta (is_closed=
        False), posteada dentro de una ventana de FECHAS absolutas — robusto al
        bug del `order_by` deprecado. Se consultan DOS bandas en orden:

            1. Banda TIER_0 [75-90 días]: si hay una vacante técnica abierta
               posteada hace >=75d → TIER_0 (sangrado activo real, califica sola).
            2. Banda TIER_1 [45-75 días]: si NO hubo TIER_0 → si hay una posteada
               hace 45-75d → TIER_1 (dificultad notable, NO califica sola).

        Por qué 2 queries y no 1: `order_by` está DEPRECADO en la API (se ignora),
        así que no puedo pedir "la más antigua". Las ventanas de fecha absolutas
        garantizan la banda sin depender del orden. Y como TheirStack NO cobra si
        devuelve 0 registros, cada banda cuesta 0 salvo cuando encuentra señal:
        el costo total es 1 crédito solo cuando hay TIER_0 o TIER_1, 0 si no.

        Precisión (fix corrida #5): se filtra por job_title_pattern_or (rol
        técnico a nivel de VACANTE) en vez de company_technology_slug_or (a nivel
        de EMPRESA) — así la vacante envejecida es realmente de desarrollo/eng, no
        un rol administrativo en una empresa que alguna vez publicó algo tech.

        FALLBACK: sin banda TIER_0/TIER_1 (o sin API key / query falló) → cache
        del discovery (vacante más fresca → TIER_2, 0 créditos), preservando la
        señal de "demanda fresca" como contexto.
        """
        if self._api_key:
            # Banda 1 (TIER_0): vacante técnica abierta posteada hace 75-90 días.
            data = self._query_vacante_abierta(
                empresa, dias_min=_AGING_TIER0_DIAS, dias_max=_VENTANA_DISCOVERY_DIAS
            )
            # Banda 2 (TIER_1): si no hubo TIER_0, buscar 45-75 días.
            if not (data is not None and data.get("data")):
                data = self._query_vacante_abierta(
                    empresa, dias_min=_AGING_TIER1_DIAS, dias_max=_AGING_TIER0_DIAS
                )
            if data is not None and data.get("data"):
                return self._parsear_triggers(data, empresa)

        # FALLBACK: cache del discovery (vacante fresca → TIER_2) con 0 créditos.
        jobs_cache = self._discovery_jobs.get(empresa.dominio)
        if jobs_cache:
            return self._parsear_triggers({"data": jobs_cache}, empresa)

        return []

    def _query_vacante_abierta(
        self, empresa: Empresa, dias_min: int, dias_max: int
    ) -> dict | None:
        """
        Consulta 1 vacante de ROL TÉCNICO, ABIERTA (is_closed=False), posteada
        entre `dias_min` y `dias_max` días atrás (ventana de fechas absolutas,
        robusta al `order_by` deprecado). Retorna el dict de la API o None.
        """
        hoy = datetime.now(timezone.utc).date()
        payload: dict = {
            "limit": 1,
            "company_domain_or": [empresa.dominio],
            # posted_at_gte = borde MÁS ANTIGUO (hace dias_max);
            # posted_at_lte = borde MÁS RECIENTE (hace dias_min).
            "posted_at_gte": (hoy - timedelta(days=dias_max)).isoformat(),
            "posted_at_lte": (hoy - timedelta(days=dias_min)).isoformat(),
            "is_closed": False,
            # Rol técnico a nivel de VACANTE (no de empresa)...
            "job_title_pattern_or": _PATRONES_ROL_TECNICO,
            # ...pero EXCLUYENDO roles comerciales ("Desarrollador Comercial" =
            # vendedor). La exclusión gana sobre el match de rol técnico.
            "job_title_pattern_not": _PATRONES_ROL_NO_TECNICO,
        }
        return self._llamar_api(
            payload,
            contexto=f"aging [{dias_min}-{dias_max}d] de '{empresa.nombre}'",
        )

    def _parsear_triggers(self, data: dict, empresa: Empresa) -> list[Trigger]:
        """
        Construye el Trigger de scoring con los DOS EJES DE TIEMPO de la spec
        canónica (Signal-Based Selling v5.0):

        - Una vacante abierta es un EFECTO (síntoma observable del dolor).
        - El TIER lo determina el AGING (antigüedad de la vacante abierta más
          ANTIGUA devuelta), por BANDAS (recalibración 26-jul-2026):
            aging >= 75d → TIER_0 (sangrado activo, califica sola);
            45d <= aging < 75d → TIER_1 (dificultad notable, no califica sola);
            aging < 45d → TIER_2 (demanda fresca / contexto).
        - El DECAY lo determina la frescura de OBSERVACIÓN: una vacante aún
          listada es un estado CONTINUO (fresco en cada re-observación), así
          que fecha_evento = now (NO date_posted), para que el decay de EFECTO
          (45d) de ScoreTriggerPolicy no elimine al TIER_0/TIER_1 de aging alto.

        PARSEO (fix corrida #5): los campos reales de la API de TheirStack son
        `job_title` y `technology_slugs` (no `title`/`technologies`); antes se
        leían mal y el título caía siempre al fallback y las techs a "no
        especificadas". Se leen ambos esquemas (real + el de los mocks) por
        robustez.
        """
        vacantes = data.get("data", [])
        nivel = _calcular_nivel_confianza(len(vacantes))
        if nivel is None:
            return []

        ahora = datetime.now(timezone.utc)
        techs = set()
        fechas_posted: list[datetime] = []
        for v in vacantes:
            techs |= _extraer_tecnologias(v)
            fecha_v = _parsear_fecha(v.get("date_posted"))
            if fecha_v is not None:
                fechas_posted.append(fecha_v)

        # Aging = antigüedad de la vacante abierta MÁS ANTIGUA devuelta. Sin
        # fecha parseable → aging 0 (TIER_2 conservador, fail-closed).
        if fechas_posted:
            aging_dias = (ahora - min(fechas_posted)).days
            if aging_dias < 0:
                aging_dias = 0
        else:
            aging_dias = 0

        # SHiFT! Phase 3 Pivot: TheirStack degrada a TIER_2 permanentemente 
        # (50 pts) por nula cobertura en PYMEs.
        tier_urgencia = TierUrgencia.TIER_2

        titulo_sample = (
            _extraer_titulo(vacantes[0]) if vacantes else "Vacante técnica"
        )
        techs_str = ", ".join(sorted(techs)) if techs else "no especificadas"

        # Si alcanzamos el techo de reporte (max_scoring), hay más señales
        # ocultas: mostrar "+N".
        n_vacantes = len(vacantes)
        conteo_str = (
            f"+{n_vacantes}" if n_vacantes >= self._max_scoring else str(n_vacantes)
        )

        aging_str = (
            f"vacante más antigua: {aging_dias} días abierta"
            if fechas_posted
            else "aging no estimable (sin fecha)"
        )

        descripcion = (
            f"{conteo_str} vacante(s) técnica(s) abiertas en '{empresa.nombre}'. "
            f"Ejemplo: '{titulo_sample}'. Tecnologías: {techs_str}. "
            f"Aging ({aging_str})."
        )

        logger.info(
            "TheirStack SCORING: '%s' — %d vacantes → confianza %s, "
            "aging=%dd → %s (EFECTO, fecha_evento=now)",
            empresa.nombre,
            len(vacantes),
            nivel.value,
            aging_dias,
            tier_urgencia.value,
        )
        return [
            Trigger(
                empresa_id=empresa.id,
                origen=OrigenTrigger.THEIRSTACK,
                nivel_confianza=nivel,
                descripcion=descripcion,
                fecha_evento=ahora,
                tipo_trigger=TipoTrigger.EFECTO,
                tier_urgencia=tier_urgencia,
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
            # NOTA (fix 26-jul-2026): `order_by` está DEPRECADO en la API de
            # TheirStack (verificado en el OpenAPI) y se ignora, así que NO se
            # puede confiar en "ASC = más antiguas primero" para capturar
            # vacantes envejecidas (ese fue el bug de la corrida #4: el discovery
            # traía las más RECIENTES y todo salía TIER_2). El discovery se queda
            # como descubridor AMPLIO (universo de empresas con vacante tech
            # ABIERTA en 90d); la determinación de aging/TIER_0 (vacante vieja-y-
            # abierta) se hace en obtener_triggers vía ventana de FECHAS absolutas
            # (posted_at_gte/lte), que NO depende del orden.
            "company_technology_slug_or": [
                t.lower().replace(" ", "-") for t in tecnologias
            ],
            # Filtro de ROL TÉCNICO a nivel de VACANTE desde el discovery (fix
            # corrida #6): el universo inicial debe estar limpio de vacantes NO
            # técnicas. company_technology_slug_or es a nivel EMPRESA ("mencionó
            # la tech en algún job"), así que sin esto el discovery traía
            # vacantes de ventas/psicología en empresas que alguna vez tocaron
            # tech. job_title_pattern_or exige rol dev/eng; job_title_pattern_not
            # excluye "Desarrollador Comercial"/ventas/marketing.
            "job_title_pattern_or": _PATRONES_ROL_TECNICO,
            "job_title_pattern_not": _PATRONES_ROL_NO_TECNICO,
            # Solo vacantes ABIERTAS: una ya cerrada (llenada) no es señal de
            # necesidad activa. Robusto y no deprecado.
            "is_closed": False,
            # Filtro obligatorio de TheirStack (E-024): debe proveerse al menos uno de
            # posted_at_max_age_days, posted_at_gte o company_domain_or.
            #
            # VENTANA = 90 días (Signal-First Discovery, 25-jul-2026). Antes eran
            # 30 días, lo que era un ERROR para el paradigma de descubrimiento por
            # señal: el trigger FUERTE de TheirStack es la vacante ENVEJECIDA
            # (aging >= 45d abierta = fallo de reclutamiento = TIER_0, el dolor
            # exacto de una consultora de staff-aug). Con ventana de 30d, JAMÁS
            # descubríamos esas vacantes aged (por definición tienen >30d). Ahora
            # descubrimos vacantes posteadas en los últimos 90d (el corte duro de
            # SHiFT!): trae tanto frescas (<45d → TIER_2, nurturing) como
            # envejecidas (45-90d → TIER_0, califican). El scoring (obtener_triggers)
            # las tiera por aging. 90d también es la ventana de decay de CAUSA.
            "posted_at_max_age_days": 90,
        }

        # Filtros adicionales derivados del ManifiestoICP
        if manifesto.geografia and manifesto.geografia.upper() != "LATAM":
            payload["company_country_code_or"] = [manifesto.geografia[:2].upper()]

        # Filtro de TAMAÑO nativo (min/max_employee_count) derivado del ICP: apunta
        # el discovery al tier del ICP (ej. SME 50-200) en vez de traer grandes
        # empresas y descartarlas después. Corrige el sesgo enterprise observado en
        # la corrida signal-first del 25-jul.
        rango = _RANGO_EMPLEADOS_POR_TAMANO.get(manifesto.tamano_empresa)
        if rango:
            min_e, max_e = rango
            if min_e is not None:
                payload["min_employee_count"] = min_e
            if max_e is not None:
                payload["max_employee_count"] = max_e

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

            # Cachear TODAS las vacantes por dominio (aunque la empresa ya se haya
            # creado): obtener_triggers()/estimar_tamano() las reutilizan sin
            # re-consultar la API. Ver nota en __init__ (self._discovery_jobs).
            self._discovery_jobs.setdefault(dominio, []).append(vacante)

            if dominio in empresas_vistas:
                continue
            empresas_vistas.add(dominio)

            tamano = _inferir_tamano(empresa_data.get("employee_count"))
            # BUG CORREGIDO (caso Parcero/UK): antes se asumía "CO" cuando
            # TheirStack no reportaba country_code, disfrazando de local a
            # empresas extranjeras. Un dato ausente NUNCA debe traducirse en
            # "es Colombia" — se usa el centinela PAIS_DESCONOCIDO explícito,
            # que PoliticaValidacionGeografica trata como no verificable
            # (no lo aprueba automáticamente, no lo descarta automáticamente).
            pais_raw = empresa_data.get("country_code")
            pais = pais_raw.upper()[:2] if pais_raw else PAIS_DESCONOCIDO

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
    # (Eliminado 26-jul-2026) DISCOVERY POR FUNDING: TheirStack /v1/companies/
    # search devolvió 0 para PYMEs colombianas → cobertura nula. Se borró el
    # discoverer por funding y el origen THEIRSTACK_FUNDING para no mantener
    # código muerto. El funding queda 100% delegado a Google Alerts (Motor 2).
    # ──────────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────
    # Caso C: WATERFALL DE TAMAÑO — PuertoEstimadorTamano
    # ──────────────────────────────────────────────────────────────────────
    def estimar_tamano(self, empresa: Empresa) -> EstimacionTamano | None:
        """
        Estima el tamaño de la Empresa a partir del campo employee_count que
        TheirStack asocia a la vacante más reciente encontrada para su dominio.
        Implementa PuertoEstimadorTamano.estimar_tamano().

        Esta es UNA sola opinión (un origen). No se usa de forma aislada: la
        PoliticaCorroboracionTamano exige que al menos 2 orígenes distintos
        coincidan antes de aceptar el TamanoEmpresa como válido.

        Retorna None si no hay API key, no hay vacantes, o el campo
        employee_count no viene en la respuesta (silencio válido — no forzar
        una opinión sin dato real).
        """
        # REUTILIZACIÓN DE CACHE (fix 25-jul-2026): el employee_count YA vino en el
        # discovery. Si la empresa fue descubierta por esta instancia, se lee de la
        # cache — CERO llamadas/créditos extra. Fallback a query para empresas ajenas.
        jobs_cache = self._discovery_jobs.get(empresa.dominio)
        if jobs_cache is not None:
            if not jobs_cache:
                return None
            empresa_data = jobs_cache[0].get("company_object", {}) or {}
            employee_count = empresa_data.get("employee_count")
            if not employee_count:
                return None
            return EstimacionTamano(
                origen=OrigenTrigger.THEIRSTACK,
                tamano_estimado=_inferir_tamano(employee_count),
            )

        if not self._api_key:
            return None

        payload = {
            "limit": 1,
            "order_by": [{"desc": True, "field": "date_posted"}],
            "company_domain_or": [empresa.dominio],
        }
        data = self._llamar_api(
            payload, contexto=f"estimacion_tamano de '{empresa.nombre}'"
        )
        if data is None:
            return None

        vacantes = data.get("data", [])
        if not vacantes:
            return None

        empresa_data = vacantes[0].get("company_object", {}) or {}
        employee_count = empresa_data.get("employee_count")
        if not employee_count:
            # Sin dato real de headcount: no forzar SME por defecto aquí.
            # _inferir_tamano() sí usa SME por defecto para Discovery (donde
            # una Empresa DEBE nacer con algún tamaño), pero el waterfall de
            # corroboración necesita silencio real, no un relleno.
            return None

        tamano = _inferir_tamano(employee_count)
        logger.info(
            "TheirStack ESTIMACION_TAMANO: '%s' → %s (employee_count=%s)",
            empresa.nombre,
            tamano.value,
            employee_count,
        )
        return EstimacionTamano(origen=OrigenTrigger.THEIRSTACK, tamano_estimado=tamano)

    # ──────────────────────────────────────────────────────────────────────
    # Método HTTP compartido — lógica de red centralizada
    # ──────────────────────────────────────────────────────────────────────
    def _llamar_api(self, payload: dict, contexto: str) -> dict | None:
        """
        Ejecuta la llamada POST a TheirStack (jobs/search) con reintentos ante 429/5xx.
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
                # OJO: un requests.Response con status 4xx/5xx es FALSY
                # (Response.__bool__ == self.ok), así que `if exc.response`
                # enmascaraba el código real como "?". Usar `is not None` y,
                # además, incluir el cuerpo del error (TheirStack devuelve un
                # JSON con code/description muy útil, ej. E-020 del plan free).
                if exc.response is not None:
                    cuerpo = (exc.response.text or "")[:300]
                    logger.warning(
                        "TheirStack: HTTP %d [%s]. Cuerpo: %s. Retornando None.",
                        exc.response.status_code,
                        contexto,
                        cuerpo,
                    )
                else:
                    logger.warning(
                        "TheirStack: HTTPError sin response [%s]: %s. Retornando None.",
                        contexto,
                        exc,
                    )
                return None
            except requests.exceptions.RequestException as exc:
                logger.error("TheirStack: error de red [%s]: %s", contexto, exc)
                return None
            except Exception as exc:
                logger.error("TheirStack: error inesperado [%s]: %s", contexto, exc)
                return None
        return None
