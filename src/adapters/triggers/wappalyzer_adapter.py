"""
WappalyzerHeadlessAdapter — implementación ligera del PuertoFuenteTriggers.

Detecta tecnologías visibles públicamente en el dominio de una empresa
inspeccionando headers HTTP y meta tags del HTML, usando solo `requests`
y `BeautifulSoup`. No requiere Playwright ni APIs de pago.

Limitación documentada (modelos_dominio_core.md):
    Solo lee la "corteza" web (frontend, headers públicos).
    No detecta deuda técnica de backend (BD, microservicios internos).

Política de NivelConfianza:
    ALTA  → Stack EOL confirmado (versión mayor > 2 años en producción)
    MEDIA → Stack detectado hace match con anclaje_tecnologico del ICP
    BAJA  → Stack detectado pero sin match con el ICP

Contrato de error: NUNCA propaga excepciones al Core.
    Errores de red, SSL o timeout → retorna [].
"""

from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    Trigger,
)
from src.core.ports.interfaces import PuertoFuenteTriggers

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECS = 8
_MAX_RESPONSE_BYTES = 150_000  # Leer solo los primeros 150 KB del HTML

# Headers de navegador real para evadir WAF / Cloudflare
_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ---------------------------------------------------------------------------
# Tecnologías conocidas que se buscan en headers y meta tags
# Formato: nombre_normalizado → [patrones_a_buscar]
# ---------------------------------------------------------------------------
_TECH_PATTERNS: dict[str, list[str]] = {
    "php": ["php", "x-powered-by: php"],
    "wordpress": ["wordpress", "wp-content", "wp-includes"],
    "drupal": ["drupal", "x-generator: drupal"],
    "joomla": ["joomla"],
    "django": ["django", "csrfmiddlewaretoken"],
    "laravel": ["laravel", "x-powered-by: php"],
    "rails": ["ruby on rails", "x-powered-by: phusion passenger"],
    "express": ["express", "x-powered-by: express"],
    "next.js": ["next.js", "__next", "_next/"],
    "react": ["react", "__reactfiber", "reactdom"],
    "vue": ["vue.js", "__vue__", "vuejs"],
    "angular": ["angular", "ng-version"],
    "jquery": ["jquery"],
    "bootstrap": ["bootstrap"],
    "nginx": ["nginx"],
    "apache": ["apache"],
    "iis": ["iis", "microsoft-iis"],
    "cloudflare": ["cloudflare", "cf-ray"],
    "aws": ["amazon", "aws", "x-amz-"],
    "azure": ["azure", "x-ms-"],
    "shopify": ["shopify", "x-shopify"],
    "wix": ["wix.com", "wixsite"],
    "squarespace": ["squarespace"],
}

# Tecnologías con versiones conocidas EOL o próximas a EOL (2026)
_EOL_MARKERS: frozenset[str] = frozenset(
    {
        "php 5",
        "php 7.0",
        "php 7.1",
        "php 7.2",
        "php 7.3",
        "wordpress 5",
        "wordpress 4",
        "wordpress 3",
        "jquery 1.",
        "jquery 2.",
        "angular 1.",
        "mysql 5.5",
        "mysql 5.6",
    }
)


def _construir_url(dominio: str) -> str:
    """Asegura que el dominio tenga protocolo HTTPS."""
    dominio = dominio.strip().lower()
    if not dominio.startswith("http"):
        return f"https://{dominio}"
    return dominio


def _detectar_tecnologias_headers(headers: dict) -> set[str]:
    """Extrae tecnologías visibles en los headers HTTP de la respuesta."""
    techs: set[str] = set()
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()}

    server = headers_lower.get("server", "")
    powered = headers_lower.get("x-powered-by", "")
    generator = headers_lower.get("x-generator", "")
    via = headers_lower.get("via", "")
    combined = f"{server} {powered} {generator} {via}"

    for tech, patterns in _TECH_PATTERNS.items():
        for p in patterns:
            if p in combined:
                techs.add(tech)
                break

    return techs


def _detectar_tecnologias_html(html: str) -> set[str]:
    """Extrae tecnologías visibles en meta tags, scripts y links del HTML."""
    techs: set[str] = set()
    try:
        soup = BeautifulSoup(html[:_MAX_RESPONSE_BYTES], "html.parser")
    except Exception:
        return techs

    # Meta tags (generator, application-name)
    for meta in soup.find_all("meta"):
        content = (meta.get("content") or "").lower()
        name = (meta.get("name") or "").lower()
        if name in ("generator", "application-name"):
            for tech, patterns in _TECH_PATTERNS.items():
                if any(p in content for p in patterns):
                    techs.add(tech)

    # Scripts y links src/href
    text_a_buscar = " ".join(
        [(tag.get("src") or "") for tag in soup.find_all("script")]
        + [(tag.get("href") or "") for tag in soup.find_all("link")]
    ).lower()

    for tech, patterns in _TECH_PATTERNS.items():
        if any(p in text_a_buscar for p in patterns):
            techs.add(tech)

    return techs


def _detectar_eol(techs_raw: set[str], response_text: str) -> bool:
    """
    Detecta si hay tecnologías EOL en los headers o el cuerpo de la respuesta.
    Normaliza las versiones con barra (PHP/5.6.40 → 'php 5.6') para matching.
    """
    # Normalizar formato "Technology/version" → "technology version_major"
    # para que "PHP/5.6.40" quede como "php 5" y haga match con _EOL_MARKERS
    text_lower = response_text.lower()
    # También normalizar el texto directamente con reemplazo de "/" por " "
    text_normalizado = text_lower.replace("/", " ").replace(".", " ")

    for marker in _EOL_MARKERS:
        marker_normalizado = marker.replace(".", " ")
        if marker_normalizado in text_normalizado or marker in text_lower:
            return True
    return False


def _calcular_nivel(
    techs_detectadas: set[str],
    tecnologias_objetivo: list[str],
    es_eol: bool,
) -> NivelConfianza | None:
    """
    Determina el NivelConfianza según el match con el ICP.
    Retorna None si no se detectó nada relevante.
    """
    if not techs_detectadas:
        return None

    if es_eol:
        return NivelConfianza.ALTA

    objetivo_lower = {t.lower() for t in tecnologias_objetivo}
    match = techs_detectadas & objetivo_lower
    if match:
        return NivelConfianza.MEDIA

    return NivelConfianza.BAJA


class WappalyzerHeadlessAdapter(PuertoFuenteTriggers):
    """
    Adaptador Motor 2 — detección de stack tecnológico público (ligero).

    Usa solo HTTP GET + BeautifulSoup. No requiere Playwright ni APIs de pago.
    Detecta tecnologías en headers HTTP y meta tags del HTML del dominio.

    Args:
        tecnologias_objetivo: Tecnologías del ManifiestoICP (anclaje_tecnologico).
                              Usadas para calcular el NivelConfianza por match.
        timeout: Segundos máximos de espera por solicitud HTTP.
        incluir_baja_confianza: Si True, genera Triggers de NivelConfianza.BAJA
                                 cuando se detecta stack sin match con el ICP.
                                 Por defecto False para reducir ruido.
    """

    def __init__(
        self,
        tecnologias_objetivo: list[str] | None = None,
        timeout: int = _REQUEST_TIMEOUT_SECS,
        incluir_baja_confianza: bool = False,
    ) -> None:
        self._tecnologias = tecnologias_objetivo or []
        self._timeout = timeout
        self._incluir_baja = incluir_baja_confianza

    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Inspecciona el dominio de la empresa y retorna Triggers si detecta
        tecnologías relevantes.

        Implementa PuertoFuenteTriggers.obtener_triggers().
        Contrato: nunca propaga excepciones al Core. Errores → [].
        """
        if not empresa.dominio:
            return []

        url = _construir_url(empresa.dominio)

        try:
            logger.info("Wappalyzer: inspeccionando '%s'", url)
            response = requests.get(
                url,
                timeout=self._timeout,
                headers=_BROWSER_HEADERS,
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.warning(
                "Wappalyzer: timeout en '%s'. Retornando [].", empresa.dominio
            )
            return []
        except requests.exceptions.SSLError:
            logger.warning(
                "Wappalyzer: SSL error en '%s'. Retornando [].", empresa.dominio
            )
            return []
        except requests.exceptions.ConnectionError:
            logger.warning(
                "Wappalyzer: no se pudo conectar a '%s'. Retornando [].",
                empresa.dominio,
            )
            return []
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Wappalyzer: HTTP %s en '%s'. Retornando [].",
                exc.response.status_code if exc.response else "?",
                empresa.dominio,
            )
            return []
        except Exception as exc:
            logger.error(
                "Wappalyzer: error inesperado en '%s': %s", empresa.dominio, exc
            )
            return []

        # Detección de tecnologías
        techs_headers = _detectar_tecnologias_headers(dict(response.headers))
        techs_html = _detectar_tecnologias_html(response.text)
        techs_detectadas = techs_headers | techs_html

        # Construir texto combinado de headers + body para detección EOL
        headers_text = " ".join(f"{k} {v}" for k, v in response.headers.items())
        texto_completo = f"{headers_text} {response.text}"
        es_eol = _detectar_eol(techs_detectadas, texto_completo)

        nivel = _calcular_nivel(techs_detectadas, self._tecnologias, es_eol)

        if nivel is None:
            logger.debug(
                "Wappalyzer: 0 tecnologías detectadas en '%s'.", empresa.dominio
            )
            return []

        if nivel == NivelConfianza.BAJA and not self._incluir_baja:
            logger.debug(
                "Wappalyzer: stack BAJA relevancia en '%s'. Omitido.", empresa.dominio
            )
            return []

        techs_str = (
            ", ".join(sorted(techs_detectadas))
            if techs_detectadas
            else "no identificadas"
        )
        eol_nota = " [Stack potencialmente EOL detectado]" if es_eol else ""
        descripcion = (
            f"Stack público detectado en '{empresa.dominio}': {techs_str}.{eol_nota}"
        )

        logger.info(
            "Wappalyzer: Trigger generado para '%s' — confianza %s | techs: %s",
            empresa.dominio,
            nivel.value,
            techs_str,
        )

        return [
            Trigger(
                empresa_id=empresa.id,
                origen=OrigenTrigger.WAPPALYZER,
                nivel_confianza=nivel,
                descripcion=descripcion,
            )
        ]
