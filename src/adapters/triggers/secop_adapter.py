"""
SecopSocrataAdapter — implementación del PuertoFuenteTriggers.

Consulta la API abierta SECOP II (Colombia Compra Eficiente) vía Socrata
para detectar contratos gubernamentales adjudicados a la empresa objetivo.

API gratuita, sin autenticación, sin límite de uso:
    Endpoint: https://www.datos.gov.co/resource/jbjy-vk9h.json
    Protocolo: Socrata Open Data API (SODA) — SoQL queries via GET params

Política de NivelConfianza (modelos_dominio_core.md):
    ALTA  → Contrato adjudicado en los últimos 180 días (liquidez inmediata)
    MEDIA → Contrato adjudicado entre 180 y 365 días
    BAJA  → Contrato encontrado pero fuera de ventana de relevancia (>1 año)

Contrato de error: NUNCA propaga excepciones al Core. Errores → [].
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone

import requests

from src.core.domain.models import (
    Empresa,
    EstimacionTamano,
    NivelConfianza,
    OrigenTrigger,
    TamanoEmpresa,
    TierUrgencia,
    TipoTrigger,
    Trigger,
)
from src.core.domain.text_matching import contiene_palabra_completa
from src.core.ports.interfaces import PuertoEstimadorTamano, PuertoFuenteTriggers

logger = logging.getLogger(__name__)

_SOCRATA_URL = "https://www.datos.gov.co/resource/jbjy-vk9h.json"

# CAUSA RAÍZ (histórica) de los "SECOP: timeout" observados en corridas
# reales (2026-07): el filtro `upper(proveedor_adjudicado) like '%NOMBRE%'`
# usaba un wildcard INICIAL ('%...'), lo que Postgres/Socrata no puede
# resolver con un índice — cada consulta hacía un full scan sobre TODO el
# dataset nacional de contratos SECOP II (millones de filas). Medido en vivo
# contra el endpoint real: 7-16s por consulta con `$where LIKE`, contra
# 0.5-1s con `$q` (búsqueda de texto completo indexada de Socrata — ver
# dev.socrata.com/docs/queries/search.html). Confirmado en vivo, 2026-07:
# misma consulta, ~10.5s con $where LIKE vs ~0.5-1s con $q.
#
# Fix de raíz: la consulta primaria ahora usa `$q` (rápido, indexado) en vez
# de `$where LIKE` (full scan). Contrapartida: `$q` es full-text FUZZY —
# puede traer falsos positivos (ej. "$q=ACME" trae también "PAVIMENTOS ACM
# SAS", que NO es un match real de "ACME"). Por eso `_construir_triggers`
# aplica un filtro de verificación en Python (substring exacto, case
# insensitive) sobre los candidatos que trae `$q` antes de convertirlos en
# Trigger — el mismo criterio de match que antes exigía el `$where LIKE`,
# pero aplicado en memoria (barato) en vez de en el motor de BD (caro).
#
# Se mantiene timeout holgado + reintentos con backoff (mismo patrón que
# TheirStackAdapter._llamar_api) como defensa en profundidad — `$q` es
# rápido en la inmensa mayoría de los casos, pero la red sigue siendo red.
_REQUEST_TIMEOUT_SECS = 25
_MAX_INTENTOS = 3
_ESPERA_ENTRE_REINTENTOS_SECS = 2
_LIMITE_RESULTADOS = 5

# Tamaño del pool de candidatos que trae `$q` ANTES del filtro de
# verificación en Python. Debe ser mayor que _LIMITE_RESULTADOS porque `$q`
# puede traer falsos positivos que el filtro descarta después — un pool más
# grande evita quedarnos con menos de _LIMITE_RESULTADOS contratos reales
# solo porque varios candidatos del pool eran ruido fuzzy.
_LIMITE_CANDIDATOS_Q = 40

# es_pyme (PYME = Micro/Pequeña/Mediana Empresa, Ley 590 de 2000) es un dato
# VERIFICADO por la entidad contratante al momento de adjudicar — no una
# inferencia de lenguaje como PropuestaValorAdapter. Aun así, "PYME" en la
# ley colombiana abarca un rango más amplio (incluye micro <10 empleados)
# que TamanoEmpresa.SME (50-200 empleados) del Core, así que el mapeo es
# aproximado, no exacto. Confianza moderada (ni tan alta como un dato 1:1,
# ni tan baja como una inferencia semántica de LLM) para que el waterfall de
# PoliticaCorroboracionTamano lo trate como una opinión seria pero no
# definitiva por sí sola.
_CONFIANZA_ESTIMACION_ES_PYME = 0.55

# Ventanas de tiempo para clasificar la urgencia del contrato
_DIAS_ALTA = 180
_DIAS_MEDIA = 365


def _parsear_fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(valor[:19], fmt[: len(fmt)])
            return dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _nivel_por_fecha(fecha_contrato: datetime | None) -> NivelConfianza:
    if fecha_contrato is None:
        return NivelConfianza.MEDIA  # Sin fecha → confianza media por defecto
    hoy = datetime.now(timezone.utc)
    dias = (hoy - fecha_contrato).days
    if dias <= _DIAS_ALTA:
        return NivelConfianza.ALTA
    if dias <= _DIAS_MEDIA:
        return NivelConfianza.MEDIA
    return NivelConfianza.BAJA


def _tier_por_nivel(nivel: NivelConfianza) -> TierUrgencia:
    """
    Mapea el NivelConfianza (basado en recencia del contrato) al TierUrgencia
    de Signal-Based Selling. Un contrato SECOP ganado es SIEMPRE una CAUSA
    (genera el "capacity shock": tienen presupuesto pero no equipo).

    ALTA (≤180d) → TIER_0 (sangrado activo). Nota: ScoreTriggerPolicy aplica
                   un decay de 90d para CAUSA, más estricto que la ventana de
                   180d de este adaptador; la política es la autoridad final
                   sobre caducidad — los contratos entre 90-180d se filtran
                   allí, no aquí.
    MEDIA/BAJA   → TIER_2 (dolor latente). No califican solos; y de hecho
                   serán filtrados por el decay de 90d de la política.
    """
    if nivel == NivelConfianza.ALTA:
        return TierUrgencia.TIER_0
    return TierUrgencia.TIER_2


class SecopSocrataAdapter(PuertoFuenteTriggers, PuertoEstimadorTamano):
    """
    Adaptador Motor 2 — Inteligencia Gubernamental (SECOP II / Socrata).

    Detecta contratos públicos adjudicados a la empresa objetivo.
    Relevante para Caso A (scoring) cuando la empresa ya está en el pipeline.

    Implementa también PuertoEstimadorTamano: el campo `es_pyme` que SECOP
    reporta sobre el proveedor adjudicado es un dato verificado por la
    entidad contratante, y aporta una tercera señal (independiente de
    TheirStack y PropuestaValorAdapter) al waterfall de
    PoliticaCorroboracionTamano — ver nota junto a
    _CONFIANZA_ESTIMACION_ES_PYME.

    Args:
        max_resultados: Máximo de contratos a retornar como Trigger tras el
                        filtro de verificación (ver nota de _q_ en el
                        encabezado del módulo).
        incluir_baja_confianza: Si True, genera Triggers para contratos > 1 año.
    """

    def __init__(
        self,
        max_resultados: int = _LIMITE_RESULTADOS,
        incluir_baja_confianza: bool = False,
        app_token: str | None = None,
    ) -> None:
        self._max_resultados = max_resultados
        self._incluir_baja = incluir_baja_confianza
        # Socrata funciona sin token, pero aplica throttling agresivo a
        # tráfico anónimo. Un App Token (gratuito, ver dev.socrata.com) eleva
        # el límite de tasa por cliente. Lee SECOP_APP_TOKEN del entorno si
        # no se pasa explícitamente — mismo patrón que el resto de adaptadores.
        self._app_token = app_token or os.getenv("SECOP_APP_TOKEN")
        # Cache por instancia: evita 2 llamadas HTTP idénticas cuando el
        # orquestador invoca obtener_triggers() y estimar_tamano() sobre la
        # MISMA empresa en el mismo pase (patrón ya usado en PropuestaValorAdapter).
        self._cache_contratos: dict[uuid.UUID, list[dict]] = {}

    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Busca contratos SECOP II adjudicados al nombre de la empresa.
        Implementa PuertoFuenteTriggers.obtener_triggers().
        """
        contratos = self._buscar_contratos(empresa)
        if not contratos:
            return []
        return self._construir_triggers(contratos, empresa)

    def estimar_tamano(self, empresa: Empresa) -> EstimacionTamano | None:
        """
        Implementa PuertoEstimadorTamano.estimar_tamano().

        Usa el campo `es_pyme` del contrato más reciente encontrado para la
        empresa (dato verificado por la entidad contratante al adjudicar, no
        una inferencia semántica). Retorna None si no hay contratos, o si el
        único contrato encontrado no reporta `es_pyme` (silencio válido —
        mismo contrato que TheirStackAdapter.estimar_tamano()).

        Mapeo aproximado (ver nota junto a _CONFIANZA_ESTIMACION_ES_PYME):
        es_pyme="Sí" → SME; es_pyme="No" → MID_MARKET (asumimos que una
        entidad que NO clasifica a su proveedor como PYME lo trata como
        empresa grande, ya que SECOP no distingue MID_MARKET de ENTERPRISE).
        """
        contratos = self._buscar_contratos(empresa)
        if not contratos:
            return None

        es_pyme_raw = contratos[0].get("es_pyme")
        if not es_pyme_raw:
            return None

        es_pyme = es_pyme_raw.strip().lower() in ("sí", "si", "yes", "true")
        tamano = TamanoEmpresa.SME if es_pyme else TamanoEmpresa.MID_MARKET

        logger.info(
            "SECOP ESTIMACION_TAMANO: '%s' → %s (es_pyme=%s)",
            empresa.nombre,
            tamano.value,
            es_pyme_raw,
        )
        return EstimacionTamano(
            origen=OrigenTrigger.SECOP_SOCRATA,
            tamano_estimado=tamano,
            confianza=_CONFIANZA_ESTIMACION_ES_PYME,
        )

    def _buscar_contratos(self, empresa: Empresa) -> list[dict]:
        """
        Consulta Socrata usando `$q` (búsqueda de texto completo indexada,
        rápida) y luego verifica en Python que el nombre del proveedor
        adjudicado realmente contiene el nombre de la empresa buscada como
        palabra completa — `$q` es fuzzy y puede traer falsos positivos
        (ver nota de causa raíz junto a _REQUEST_TIMEOUT_SECS).

        Retorna como máximo _max_resultados contratos YA verificados,
        ordenados por fecha de firma descendente.
        """
        if empresa.id in self._cache_contratos:
            return self._cache_contratos[empresa.id]

        nombre = empresa.nombre.strip()
        if not nombre:
            return []

        params = {
            "$q": nombre,
            "$limit": str(_LIMITE_CANDIDATOS_Q),
            # fecha_de_firma es la columna real del dataset jbjy-vk9h — el
            # nombre anterior (fecha_adjudicacion) no existe en el esquema y
            # causaba un HTTP 400 Bad Request en TODA consulta (causa raíz
            # confirmada por ingeniería inversa del endpoint, 2026-07).
            "$order": "fecha_de_firma DESC",
        }

        candidatos = self._llamar_api(params, contexto=nombre)
        if not candidatos or not isinstance(candidatos, list):
            logger.debug("SECOP: 0 contratos encontrados para '%s'.", nombre)
            self._cache_contratos[empresa.id] = []
            return []

        verificados = [
            c
            for c in candidatos
            if contiene_palabra_completa(
                c.get("proveedor_adjudicado", ""), nombre
            )
        ]
        if not verificados:
            logger.debug(
                "SECOP: %d candidato(s) de '$q' para '%s', 0 verificados "
                "tras filtro de nombre exacto.",
                len(candidatos),
                nombre,
            )
            self._cache_contratos[empresa.id] = []
            return []

        resultado = verificados[: self._max_resultados]
        self._cache_contratos[empresa.id] = resultado
        return resultado

    def _llamar_api(self, params: dict, contexto: str) -> list | None:
        """
        GET a Socrata con reintentos ante Timeout/429/5xx (mismo patrón que
        TheirStackAdapter._llamar_api). Contrato: nunca propaga al Core;
        retorna None ante cualquier fallo definitivo tras agotar reintentos.
        """
        headers = {"Accept": "application/json"}
        if self._app_token:
            headers["X-App-Token"] = self._app_token

        _REINTENTABLES = {429, 500, 502, 503, 504}
        for intento in range(_MAX_INTENTOS):
            try:
                logger.info(
                    "SECOP: consultando contratos para '%s' (intento %d)",
                    contexto,
                    intento + 1,
                )
                response = requests.get(
                    _SOCRATA_URL,
                    params=params,
                    headers=headers,
                    timeout=_REQUEST_TIMEOUT_SECS,
                )
                if (
                    response.status_code in _REINTENTABLES
                    and intento < _MAX_INTENTOS - 1
                ):
                    logger.warning(
                        "SECOP: HTTP %d para '%s'. Reintento en %ds...",
                        response.status_code,
                        contexto,
                        _ESPERA_ENTRE_REINTENTOS_SECS,
                    )
                    time.sleep(_ESPERA_ENTRE_REINTENTOS_SECS)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                if intento < _MAX_INTENTOS - 1:
                    logger.warning(
                        "SECOP: timeout para '%s' (intento %d/%d, full-scan de "
                        "'%%LIKE%%' puede tardar >15s). Reintento en %ds...",
                        contexto,
                        intento + 1,
                        _MAX_INTENTOS,
                        _ESPERA_ENTRE_REINTENTOS_SECS,
                    )
                    time.sleep(_ESPERA_ENTRE_REINTENTOS_SECS)
                    continue
                logger.warning(
                    "SECOP: timeout para '%s' tras %d intentos. Retornando [].",
                    contexto,
                    _MAX_INTENTOS,
                )
                return None
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response else None
                if status == 403 and self._app_token:
                    # Causa raíz común: el valor de SECOP_APP_TOKEN viene de
                    # la sección "Claves API" (escritura) de datos.gov.co en
                    # vez de "Tokens de la aplicación" (lectura, el que
                    # espera X-App-Token). Socrata rechaza el primero con
                    # 403 Invalid app_token.
                    logger.warning(
                        "SECOP: Token 403 — verifica que usaste 'Token de la "
                        "aplicación', no 'Clave API' en datos.gov.co."
                    )
                else:
                    logger.warning(
                        "SECOP: HTTP %s para '%s'. Retornando [].",
                        status if status is not None else "?",
                        contexto,
                    )
                return None
            except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
                logger.error("SECOP: error inesperado para '%s': %s", contexto, exc)
                return None
        return None

    def _construir_triggers(
        self, contratos: list[dict], empresa: Empresa
    ) -> list[Trigger]:
        """
        Extrae los campos del contrato con el esquema REAL del dataset
        jbjy-vk9h (confirmado por ingeniería inversa del endpoint, 2026-07).
        Los nombres de columna anteriores (fecha_adjudicacion, entidad_nombre,
        objeto_contrato, valor_contrato, numero_contrato/id_proceso) no
        existen en este dataset — la extracción fallaba silenciosamente
        (siempre caía a los defaults) porque .get() nunca lanza excepción
        sobre una clave ausente.
        """
        triggers: list[Trigger] = []

        for contrato in contratos:
            # Fecha base: fecha_de_firma primero; si el contrato no la trae
            # (ej. en trámite de legalización), se usa fecha_de_inicio_del_contrato
            # como fallback antes de caer en None.
            fecha_raw = contrato.get("fecha_de_firma") or contrato.get(
                "fecha_de_inicio_del_contrato"
            )
            fecha_contrato = _parsear_fecha(fecha_raw)
            nivel = _nivel_por_fecha(fecha_contrato)

            if nivel == NivelConfianza.BAJA and not self._incluir_baja:
                continue

            # Campos del contrato para la descripción
            objeto = contrato.get("objeto_del_contrato") or contrato.get(
                "descripcion_del_proceso", "Contrato público"
            )
            entidad = contrato.get("nombre_entidad", "Entidad no especificada")
            valor_raw = contrato.get("valor_del_contrato", "")
            numero = contrato.get("id_contrato", "N/A")
            # Campos nuevos (esquema completo jbjy-vk9h, confirmado 2026-07):
            # urlproceso permite verificación humana de un clic (revisión
            # manual accionable); codigo_de_categoria_principal (UNSPSC) y
            # direccion_de_ejecucion aportan señal adicional de relevancia
            # TI y geografía respectivamente.
            url_proceso = (contrato.get("urlproceso") or {}).get("url")
            categoria_unspsc = contrato.get("codigo_de_categoria_principal")
            direccion_ejecucion = contrato.get("direcci_n_de_ejecuci_n_del_contrato")

            try:
                valor_str = (
                    f"COP {float(valor_raw):,.0f}"
                    if valor_raw
                    else "valor no disponible"
                )
            except (ValueError, TypeError):
                valor_str = str(valor_raw)

            objeto_corto = objeto[:80] + "..." if len(objeto) > 80 else objeto
            descripcion = (
                f"Contrato SECOP #{numero} adjudicado a '{empresa.nombre}'. "
                f"Entidad: {entidad}. Valor: {valor_str}. "
                f"Objeto: {objeto_corto}"
            )
            if categoria_unspsc:
                descripcion += f" Categoría UNSPSC: {categoria_unspsc}."
            if direccion_ejecucion:
                direccion_corta = direccion_ejecucion.replace("\n", ", ")
                descripcion += f" Ejecución: {direccion_corta}."
            if url_proceso:
                descripcion += f" URL: {url_proceso}"

            trigger = Trigger(
                empresa_id=empresa.id,
                origen=OrigenTrigger.SECOP_SOCRATA,
                nivel_confianza=nivel,
                descripcion=descripcion,
                fecha_evento=fecha_contrato,
                tipo_trigger=TipoTrigger.CAUSA,
                tier_urgencia=_tier_por_nivel(nivel),
            )
            triggers.append(trigger)

        logger.info(
            "SECOP: %d trigger(s) generados para '%s'.",
            len(triggers),
            empresa.nombre,
        )
        return triggers
