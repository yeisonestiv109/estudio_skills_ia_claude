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

# Límite de vacantes a traer en la consulta de SCORING. Se sube de 3 a 25
# porque el TIER de la señal depende del AGING (antigüedad de la vacante
# abierta más vieja) y TheirStack cobra por CONSULTA, no por resultado: traer
# más vacantes en la MISMA llamada no agrega costo y mejora la estimación de
# aging (la cota inferior del aging real es más ajustada con más muestras).
# El "conteo" que muestra la descripción sigue gobernado por
# max_resultados_scoring (parámetro del constructor), no por este límite.
_LIMITE_VACANTES_AGING = 25

# Umbral de aging (en días) a partir del cual una vacante abierta se considera
# fill-rate failure (sangrado activo) — mismo valor que la ventana de decay de
# EFECTO en ScoreTriggerPolicy: >= 45d abierta = TIER_0, < 45d = TIER_2.
_AGING_TIER0_DIAS = 45


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
            # Traemos más vacantes (25) que las que se reportan (max_scoring)
            # para estimar el aging de la vacante más antigua sin costo extra
            # (TheirStack cobra por consulta, no por resultado). Mantenemos el
            # orden por date_posted desc.
            "limit": _LIMITE_VACANTES_AGING,
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
        """
        Construye el Trigger de scoring con los DOS EJES DE TIEMPO de la spec
        canónica (Signal-Based Selling v5.0):

        - Una vacante abierta es un EFECTO (síntoma observable del dolor).
        - El TIER lo determina el AGING (antigüedad de la vacante abierta más
          ANTIGUA): aging >= 45 días → TIER_0 (fill-rate failure, sangrado
          activo); aging < 45 días → TIER_2 (demanda fresca, contexto).
        - El DECAY lo determina la frescura de OBSERVACIÓN: una vacante aún
          listada es un estado CONTINUO (fresco en cada re-observación), así
          que fecha_evento = now (NO date_posted), para que el decay de EFECTO
          (45d) de ScoreTriggerPolicy no elimine precisamente al TIER_0 de
          aging alto.

        LIMITACIÓN documentada: el aging se estima SOLO sobre las vacantes que
        devolvió esta consulta (hasta _LIMITE_VACANTES_AGING), no sobre TODAS
        las históricas. Es una cota INFERIOR honesta del aging real (la vacante
        más antigua realmente abierta podría ser aún más vieja).
        """
        vacantes = data.get("data", [])
        nivel = _calcular_nivel_confianza(len(vacantes))
        if nivel is None:
            return []

        ahora = datetime.now(timezone.utc)
        techs = set()
        fechas_posted: list[datetime] = []
        for v in vacantes:
            for t in v.get("technologies", []):
                techs.add(t.get("name", str(t)) if isinstance(t, dict) else str(t))
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

        tier_urgencia = (
            TierUrgencia.TIER_0
            if aging_dias >= _AGING_TIER0_DIAS
            else TierUrgencia.TIER_2
        )

        titulo_sample = (
            vacantes[0].get("title", "Vacante técnica")
            if vacantes
            else "Vacante técnica"
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
