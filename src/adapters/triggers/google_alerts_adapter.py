"""
GoogleAlertsRSSAdapter — implementación del PuertoFuenteTriggers.

Parsea feeds RSS de Google Alerts para detectar eventos de negocio y liderazgo
en la empresa objetivo: M&A, rondas de inversión, llegada de nuevos C-Levels.

Configuración previa: el usuario debe crear las alertas en Google Alerts
(https://www.google.com/alerts) con salida en formato RSS y proporcionar
las URLs al construir este adaptador.

Política de NivelConfianza (definida en modelos_dominio_core.md):
    ALTA  → Nuevo CTO/CIO/CDO confirmado en medios < 6 meses
    MEDIA → Ronda de inversión anunciada
    BAJA  → Mención en medios sin evento concreto identificable

Contrato de error: NUNCA propaga excepciones al Core.
    Cualquier error de red o parseo se captura, se registra y retorna [].
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import NamedTuple

import requests

import feedparser

from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    Trigger,
)
from src.core.ports.interfaces import PuertoFuenteTriggers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Palabras clave que determinan el NivelConfianza del trigger de noticias
# ---------------------------------------------------------------------------
_KEYWORDS_C_LEVEL = frozenset(
    {
        "cto",
        "cio",
        "cdo",
        "chief technology",
        "chief information",
        "chief digital",
        "nuevo director",
        "new cto",
        "nombrado",
        "appointed",
        "joins as",
        "se une como",
        "director tecnología",
        "director tecnologia",
    }
)

_KEYWORDS_INVERSION = frozenset(
    {
        "ronda",
        "round",
        "series a",
        "series b",
        "series c",
        "inversión",
        "inversion",
        "funding",
        "raised",
        "levantó",
        "levanto",
        "millones",
        "million",
        "capital",
        "financiamiento",
        "vc",
        "venture",
    }
)

_KEYWORDS_MA = frozenset(
    {
        "adquisición",
        "adquisicion",
        "acquisition",
        "merger",
        "fusión",
        "fusion",
        "compra",
        "acquired",
        "acquired by",
        "adquirida",
        "se une a",
        "joins",
    }
)


class _EntradaRSS(NamedTuple):
    titulo: str
    resumen: str
    enlace: str
    fecha: datetime | None


def _convertir_fecha_rss(entry) -> datetime | None:
    """Extrae la fecha de una entrada RSS (feedparser) y la convierte a UTC."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            ts = time.mktime(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    return None


def _clasificar_nivel(titulo: str, resumen: str) -> NivelConfianza:
    """
    Determina el NivelConfianza basándose en las palabras clave del contenido.
    Orden de prioridad: C-Level > Inversión/M&A > Mención genérica.
    """
    texto = (titulo + " " + resumen).lower()

    if any(kw in texto for kw in _KEYWORDS_C_LEVEL):
        return NivelConfianza.ALTA

    if any(kw in texto for kw in _KEYWORDS_INVERSION | _KEYWORDS_MA):
        return NivelConfianza.MEDIA

    return NivelConfianza.BAJA


def _empresa_mencionada(empresa: Empresa, texto: str) -> bool:
    """
    Verifica si la empresa es mencionada en el texto de la entrada RSS.
    Usa el nombre y el dominio (sin extensión) como patrones de búsqueda.
    """
    nombre_normalizado = empresa.nombre.lower()
    dominio_raiz = empresa.dominio.split(".")[0].lower()  # "acme" de "acme.com"
    texto_lower = texto.lower()

    return nombre_normalizado in texto_lower or dominio_raiz in texto_lower


class GoogleAlertsRSSAdapter(PuertoFuenteTriggers):
    """
    Adaptador Motor 2 — señales de noticias y eventos de liderazgo (Google Alerts RSS).

    Las URLs de los feeds RSS se configuran externamente (por el usuario o el
    orquestador) al construir el adaptador. Cada URL corresponde a una alerta
    de Google configurada para la empresa o el sector objetivo.

    Args:
        rss_urls: Lista de URLs de feeds RSS de Google Alerts.
        palabras_clave_extra: Keywords adicionales para filtrar entradas relevantes
                              (ej. términos del dolor_operativo del ManifiestoICP).
        max_triggers_por_empresa: Límite de Triggers a generar por empresa
                                  para evitar spam de señales del mismo origen.
    """

    def __init__(
        self,
        rss_urls: list[str],
        palabras_clave_extra: list[str] | None = None,
        max_triggers_por_empresa: int = 3,
    ) -> None:
        self._rss_urls = rss_urls
        self._keywords_extra: frozenset[str] = frozenset(
            kw.lower() for kw in (palabras_clave_extra or [])
        )
        self._max_triggers = max_triggers_por_empresa

    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Implementa PuertoFuenteTriggers.obtener_triggers().

        Parsea todos los feeds RSS configurados y filtra entradas que mencionen
        a la empresa objetivo. Retorna Triggers ordenados por NivelConfianza
        (ALTA primero).

        Returns:
            list[Trigger] — triggers detectados; [] si no hay entradas relevantes
            o si ocurre cualquier error de parseo/red.
        """
        if not self._rss_urls:
            logger.debug("GoogleAlerts: sin URLs RSS configuradas. Retornando [].")
            return []

        entradas_relevantes: list[_EntradaRSS] = []

        for url in self._rss_urls:
            try:
                entradas = self._parsear_feed(url, empresa)
                entradas_relevantes.extend(entradas)
            except Exception as exc:
                # Contrato: nunca propagar al Core
                logger.error(
                    "GoogleAlerts: error procesando feed '%s' para '%s': %s",
                    url,
                    empresa.nombre,
                    exc,
                )

        if not entradas_relevantes:
            logger.debug(
                "GoogleAlerts: 0 entradas relevantes para '%s'.", empresa.nombre
            )
            return []

        # Construir Triggers ordenando por relevancia (ALTA primero)
        triggers: list[Trigger] = []
        for entrada in entradas_relevantes[: self._max_triggers]:
            nivel = _clasificar_nivel(entrada.titulo, entrada.resumen)
            descripcion = self._formatear_descripcion(entrada, nivel)

            trigger = Trigger(
                empresa_id=empresa.id,
                origen=OrigenTrigger.GOOGLE_ALERTS,
                nivel_confianza=nivel,
                descripcion=descripcion,
                fecha_evento=entrada.fecha,
            )
            triggers.append(trigger)

        # Ordenar ALTA > MEDIA > BAJA para que el orquestador reciba los mejores primero
        _orden = {
            NivelConfianza.ALTA: 0,
            NivelConfianza.MEDIA: 1,
            NivelConfianza.BAJA: 2,
        }
        triggers.sort(key=lambda t: _orden[t.nivel_confianza])

        logger.info(
            "GoogleAlerts: %d trigger(s) generados para '%s'.",
            len(triggers),
            empresa.nombre,
        )

        return triggers

    def _parsear_feed(self, url: str, empresa: Empresa) -> list[_EntradaRSS]:
        """
        Descarga y parsea un feed RSS usando headers de navegador para evadir WAF.
        Filtra entradas que mencionan a la empresa.
        """
        _BROWSER_HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        }
        try:
            http_response = requests.get(url, headers=_BROWSER_HEADERS, timeout=10)
            http_response.raise_for_status()
            feed = feedparser.parse(http_response.text)
        except Exception:
            # Fallback: dejar que feedparser lo intente con su propio user-agent
            feed = feedparser.parse(url)

        if feed.get("bozo") and not feed.get("entries"):
            logger.warning(
                "GoogleAlerts: feed '%s' tiene errores de parseo (bozo=True).", url
            )
            return []

        relevantes: list[_EntradaRSS] = []

        for entry in feed.get("entries", []):
            titulo = getattr(entry, "title", "") or ""
            resumen = getattr(entry, "summary", "") or ""
            enlace = getattr(entry, "link", "") or ""
            texto_completo = titulo + " " + resumen

            # Filtrar por empresa y/o por keywords del ICP
            menciona_empresa = _empresa_mencionada(empresa, texto_completo)
            menciona_keyword = any(
                kw in texto_completo.lower() for kw in self._keywords_extra
            )

            if not (menciona_empresa or menciona_keyword):
                continue

            relevantes.append(
                _EntradaRSS(
                    titulo=titulo,
                    resumen=resumen,
                    enlace=enlace,
                    fecha=_convertir_fecha_rss(entry),
                )
            )

        return relevantes

    @staticmethod
    def _formatear_descripcion(entrada: _EntradaRSS, nivel: NivelConfianza) -> str:
        """Genera la descripción legible del Trigger según el nivel detectado."""
        titulo_truncado = (
            (entrada.titulo[:120] + "...")
            if len(entrada.titulo) > 120
            else entrada.titulo
        )
        nivel_label = {
            NivelConfianza.ALTA: "Cambio de liderazgo C-Level",
            NivelConfianza.MEDIA: "Evento de inversión o M&A",
            NivelConfianza.BAJA: "Mención en medios",
        }[nivel]

        return f"{nivel_label}: '{titulo_truncado}' — Fuente: {entrada.enlace or 'RSS'}"
