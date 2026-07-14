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
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    Trigger,
)
from src.core.ports.interfaces import PuertoFuenteTriggers

logger = logging.getLogger(__name__)

_SOCRATA_URL = "https://www.datos.gov.co/resource/jbjy-vk9h.json"
_REQUEST_TIMEOUT_SECS = 15
_LIMITE_RESULTADOS = 5

# Ventanas de tiempo para clasificar la urgencia del contrato
_DIAS_ALTA = 180
_DIAS_MEDIA = 365


def _parsear_fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(valor[:19], fmt[:len(fmt)])
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


class SecopSocrataAdapter(PuertoFuenteTriggers):
    """
    Adaptador Motor 2 — Inteligencia Gubernamental (SECOP II / Socrata).

    Detecta contratos públicos adjudicados a la empresa objetivo.
    Relevante para Caso A (scoring) cuando la empresa ya está en el pipeline.

    Args:
        max_resultados: Máximo de contratos a traer por consulta.
        incluir_baja_confianza: Si True, genera Triggers para contratos > 1 año.
    """

    def __init__(
        self,
        max_resultados: int = _LIMITE_RESULTADOS,
        incluir_baja_confianza: bool = False,
    ) -> None:
        self._max_resultados = max_resultados
        self._incluir_baja = incluir_baja_confianza

    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Busca contratos SECOP II adjudicados al nombre de la empresa.
        Implementa PuertoFuenteTriggers.obtener_triggers().
        """
        nombre = empresa.nombre.strip()
        if not nombre:
            return []

        # SoQL: buscar por nombre del proveedor (case-insensitive con UPPER)
        # %25 es % en URL → LIKE '%NOMBRE%'
        nombre_upper = nombre.upper()
        where_clause = f"upper(proveedor_adjudicado) like '%{nombre_upper}%'"
        params = {
            "$where": where_clause,
            "$limit": str(self._max_resultados),
            "$order": "fecha_adjudicacion DESC",
        }

        try:
            logger.info("SECOP: consultando contratos para '%s'", nombre)
            response = requests.get(
                _SOCRATA_URL,
                params=params,
                headers={"Accept": "application/json"},
                timeout=_REQUEST_TIMEOUT_SECS,
            )
            response.raise_for_status()
            contratos = response.json()
        except requests.exceptions.Timeout:
            logger.warning("SECOP: timeout para '%s'. Retornando [].", nombre)
            return []
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "SECOP: HTTP %s para '%s'. Retornando [].",
                exc.response.status_code if exc.response else "?",
                nombre,
            )
            return []
        except Exception as exc:
            logger.error("SECOP: error inesperado para '%s': %s", nombre, exc)
            return []

        if not contratos or not isinstance(contratos, list):
            logger.debug("SECOP: 0 contratos encontrados para '%s'.", nombre)
            return []

        return self._construir_triggers(contratos, empresa)

    def _construir_triggers(self, contratos: list[dict], empresa: Empresa) -> list[Trigger]:
        triggers: list[Trigger] = []

        for contrato in contratos:
            fecha_raw = contrato.get("fecha_adjudicacion") or contrato.get("fecha_firma")
            fecha_contrato = _parsear_fecha(fecha_raw)
            nivel = _nivel_por_fecha(fecha_contrato)

            if nivel == NivelConfianza.BAJA and not self._incluir_baja:
                continue

            # Campos del contrato para la descripción
            objeto = contrato.get("objeto_contrato", "Contrato público")
            entidad = contrato.get("entidad_nombre", "Entidad no especificada")
            valor_raw = contrato.get("valor_contrato", "")
            numero = contrato.get("numero_contrato", contrato.get("id_proceso", "N/A"))

            try:
                valor_str = f"COP {float(valor_raw):,.0f}" if valor_raw else "valor no disponible"
            except (ValueError, TypeError):
                valor_str = str(valor_raw)

            objeto_corto = objeto[:80] + "..." if len(objeto) > 80 else objeto
            descripcion = (
                f"Contrato SECOP #{numero} adjudicado a '{empresa.nombre}'. "
                f"Entidad: {entidad}. Valor: {valor_str}. "
                f"Objeto: {objeto_corto}"
            )

            trigger = Trigger(
                empresa_id=empresa.id,
                origen=OrigenTrigger.SECOP_SOCRATA,
                nivel_confianza=nivel,
                descripcion=descripcion,
                fecha_evento=fecha_contrato,
            )
            triggers.append(trigger)

        logger.info(
            "SECOP: %d trigger(s) generados para '%s'.",
            len(triggers),
            empresa.nombre,
        )
        return triggers
