"""
PropuestaValorAdapter — implementación de PuertoClasificadorPropuestaValor
y PuertoEstimadorTamano.

Diseño: investigación "Negative ICP" / "Waterfall Enrichment"
(02_Lineas_de_Producto/Outbound_Prospector/docs/tecnico/prospector-m3-m4-design.md, sesión de
afinamiento del Motor 2 post-piloto TBBC). Implementa la Capa 2 (análisis
semántico profundo) del framework de exclusión de competidores en 3 cubetas:

    Capa 1 (PoliticaExclusionCompetidores, pura, sin costo):
        compara CategoriaEmpresa del cliente vs. la candidata.
        - Idénticas           → EXCLUIDO_DURO (nunca llega aquí)
        - Ambiguas (vecinas)  → REQUIERE_ANALISIS_SEMANTICO (llega aquí)
        - Distintas           → PERMITIDO (nunca llega aquí)

    Capa 2 (este adaptador, con costo — lectura web + LLM):
        solo se invoca sobre el subconjunto ambiguo de la Capa 1. Lee el
        texto público de la homepage de la empresa candidata y usa el mismo
        LLM barato de M1 (Groq) para inferir dos señales en una sola llamada:
            1. es_vendor_it: ¿esta empresa construye/vende tecnología a
               terceros (como el propio cliente), o usa tecnología para
               resolver su propio negocio?
            2. tamano_estimado: tamaño aproximado inferido del lenguaje
               corporativo ("líder regional", "equipo de 15 personas", etc.).

Doble rol arquitectónico (dos puertos, una sola lectura web + una sola
llamada de LLM, cacheada por empresa dentro de la instancia):
    - PuertoClasificadorPropuestaValor.clasificar() → resuelve la Capa 2
      del Negative ICP.
    - PuertoEstimadorTamano.estimar_tamano() → aporta una SEGUNDA señal
      independiente y gratuita (ya se pagó el LLM para lo anterior) al
      waterfall de PoliticaCorroboracionTamano.

Contrato de error (idéntico al resto de adaptadores del proyecto): NUNCA
propaga excepción al Core. Cualquier fallo (sin texto público, error de red,
LLM no disponible, respuesta sin el formato esperado) retorna None en ambos
métodos — el orquestador decide qué hacer con la ambigüedad no resuelta
(ej. cola manual, nunca "asumir que es seguro").

MEJORAS DE ROBUSTEZ v2.0 (Prioridad 1):
- Domain Discovery: variaciones automáticas de dominio
- User-Agent Rotation: pool de headers rotativos anti-bot
- Exponential Backoff: retry inteligente con delays crecientes
- Protocol Fallbacks: HTTPS/HTTP + www/sin-www automático
- Timeout progresivo: aumenta timeout por reintento
"""

from __future__ import annotations

import logging
import random
import re
import time
import uuid
from dataclasses import dataclass

import groq as groq_sdk
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError

from src.adapters.llm.groq_key_pool import GroqKeyPool
from src.core.domain.models import (
    CategoriaEmpresa,
    Empresa,
    EstimacionTamano,
    OrigenTrigger,
    TamanoEmpresa,
    TipoOrganizacion,
)
from src.core.ports.interfaces import (
    PuertoClasificadorPropuestaValor,
    PuertoEstimadorTamano,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECS = 10
_MAX_CARACTERES_TEXTO_HOMEPAGE = 2000

# Umbral bajo el cual el texto visible se considera "insuficiente" (caso
# típico: SPA en JavaScript sin server-side rendering, donde BeautifulSoup
# solo ve el shell vacío del <div id="root">). Bug corregido (caso Parcero):
# antes, texto_limpio vacío o casi vacío devolvía None sin intentar ningún
# fallback, lo que el orquestador terminaba interpretando como "sin
# evidencia de competencia" → PERMITIDO automático (fail-open). Ahora se
# intenta un fallback de <title>/<meta name="description"> antes de rendirse.
_MIN_CARACTERES_TEXTO_SUFICIENTE = 100

_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Confianza reducida frente a un origen de dato firmográfico real (TheirStack
# usa 1.0 por defecto): esta estimación se infiere de LENGUAJE, no de un
# employee_count real. PoliticaCorroboracionTamano la usa como desempate,
# no como fuente primaria.
_CONFIANZA_ESTIMACION_SEMANTICA = 0.6

# Mismos headers de navegador real que WappalyzerHeadlessAdapter, para
# reducir la tasa de bloqueo por WAF/Cloudflare al leer la homepage pública.
_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
}

# Pool de User-Agents rotativos para evitar detección (Prioridad 1 - Anti-blocking)
_USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
]

# Configuración de retry con exponential backoff (Prioridad 1)
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1

# Estrategia de reintentos técnicos (respuesta a hallazgo de corrida real:
# muchos casos que caen en PENDIENTE_REVISION_MANUAL no son ambigüedad
# semántica real, sino fallas técnicas de lectura — la raíz del dominio
# viene vacía pero la empresa SÍ tiene texto público en otra ruta). Se
# intentan, EN ORDEN, solo cuando la raíz del dominio no dio NINGÚN texto
# utilizable (ni body visible ni meta-fallback) — nunca cuando la raíz sí
# dio algo, por corto que sea (preserva el comportamiento histórico: un
# texto corto pero real sigue siendo mejor señal que gastar más llamadas).
_RUTAS_ALTERNAS: tuple[str, ...] = (
    "/nosotros",
    "/about",
    "/quienes-somos",
    "/about-us",
)

# Timeout del fallback pesado (renderizado con navegador real). Más holgado
# que _REQUEST_TIMEOUT_SECS porque un render completo con JS es
# intrínsecamente más lento que un GET simple.
_PLAYWRIGHT_TIMEOUT_MS = 15_000


def _renderizar_con_playwright(url: str) -> str | None:
    """
    Fallback pesado: renderiza `url` con un navegador real (Chromium
    headless vía Playwright) y retorna el texto visible del DOM YA
    ejecutado JS. Se invoca SOLO cuando ni la raíz del dominio ni ninguna
    ruta alterna (ambas vía `requests` + BeautifulSoup, sin ejecutar JS)
    dieron texto utilizable — es decir, es el ÚLTIMO recurso ante el caso
    SPA sin server-side rendering, no el camino feliz.

    Contrato de error: nunca lanza excepción hacia el llamador. Si
    Playwright no está instalado, si el navegador no está descargado
    (`playwright install chromium` pendiente en el entorno), o si la
    página falla al cargar/renderizar, retorna None con log — mismo
    contrato de "silencio válido, nunca asumir éxito" que el resto del
    adaptador.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug(
            "PropuestaValorAdapter: playwright no instalado. Sin fallback JS "
            "disponible para '%s'.",
            url,
        )
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(
                    url, timeout=_PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded"
                )
                texto = page.inner_text("body")
            finally:
                browser.close()
        return texto
    except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar, fallback opcional
        logger.warning(
            "PropuestaValorAdapter: fallback Playwright falló para '%s': %s",
            url,
            exc,
        )
        return None


_SYSTEM_PROMPT = """Eres un analista de clasificación de empresas B2B para un sistema de prospección.

Recibirás el texto público de la homepage de una empresa. Tu única tarea es responder
CUATRO preguntas sobre esa empresa, en base ÚNICAMENTE al texto proporcionado.

FORMATO DE RESPUESTA OBLIGATORIO (responde ÚNICAMENTE con este JSON, sin markdown, sin explicaciones):
{
  "es_vendor_it": <true si la empresa CONSTRUYE, DESARROLLA o VENDE software/tecnología/servicios de TI a
                    terceros como su modelo de negocio principal (ej. fábrica de software, consultora IT,
                    agencia de desarrollo, plataforma SaaS); false si la empresa USA tecnología como
                    herramienta para resolver su propio negocio en otro sector (ej. banco, retail,
                    logística, salud) y no vende tecnología a otros>,
  "tamano_estimado": "<uno de: STARTUP | SME | MID_MARKET | ENTERPRISE, inferido del lenguaje corporativo
                       (ej. 'equipo pequeño' o pocos empleados mencionados = STARTUP; 'PYME' o 50-200
                       personas = SME; 'empresa mediana' o cientos de empleados = MID_MARKET; 'líder
                       regional/global', presencia multinacional, miles de empleados = ENTERPRISE).
                       Usa null si el texto no da ninguna pista de tamaño.>",
  "pais_hq": "<código ISO Alpha-2 (2 letras, MAYÚSCULAS) del país donde está la sede principal (HQ) de
              la empresa, inferido de direcciones físicas, menciones de ciudad/país, dominio, o cualquier
              otra pista textual (ej. 'London' o 'UK' -> 'GB'; 'Bogotá' o 'Colombia' -> 'CO'; 'Ciudad de
              México' -> 'MX'). Usa null si el texto no da NINGUNA pista verificable del país de HQ. No
              adivines a partir del idioma del texto solamente: el idioma español no implica LATAM.>",
  "tipo_organizacion": "<uno de: EMPRESA_PRIVADA | GOBIERNO | ONG_FUNDACION | MEDIOS | EDUCACION |
                        GREMIO_ASOCIACION | OTRO. Clasifica la NATURALEZA de la organización:
                        EMPRESA_PRIVADA = empresa privada con ánimo de lucro (el caso típico);
                        GOBIERNO = entidad pública, ministerio, alcaldía, ente regulador o estatal;
                        ONG_FUNDACION = organización sin ánimo de lucro, fundación, cooperación
                        internacional; MEDIOS = medio de comunicación, revista, periódico, portal de
                        noticias; EDUCACION = universidad, colegio, instituto educativo; GREMIO_ASOCIACION
                        = gremio, cámara de comercio, asociación sectorial; OTRO = si no encaja en ninguna
                        de las anteriores. Usa null solo si el texto no da NINGUNA pista del tipo.>"
}

REGLAS CRÍTICAS:
1. Responde SOLO con el JSON. Sin explicaciones. Sin bloques de código markdown.
2. Si el texto es insuficiente para juzgar es_vendor_it con razonable confianza, aun así responde tu
   mejor estimación — el llamador ya sabe que esto es una inferencia, no un hecho verificado.
3. tamano_estimado, pais_hq y tipo_organizacion pueden ser null; es_vendor_it NUNCA puede ser null
   (siempre true o false)."""


def _construir_url(dominio: str) -> str:
    dominio = dominio.strip().lower()
    if not dominio.startswith("http"):
        return f"https://{dominio}"
    return dominio


def _generar_variaciones_dominio(
    empresa_nombre: str, dominio_original: str
) -> list[str]:
    """
    Genera variaciones comunes de dominio basadas en el nombre de empresa.
    Técnica: Domain Discovery (Prioridad 1 - Resolución dominios alternativos)
    """
    if not empresa_nombre or not dominio_original:
        return []

    base_name = re.sub(r"[^a-zA-Z0-9]", "", empresa_nombre.lower())
    dominio_sin_tld = (
        dominio_original.split(".")[0] if "." in dominio_original else dominio_original
    )

    variaciones = [
        # Variaciones de TLD colombiano
        f"{dominio_sin_tld}.co",
        f"{dominio_sin_tld}.com.co",
        # Basado en nombre de empresa
        f"{base_name}.com",
        f"{base_name}.co",
        f"{base_name}.com.co",
        # Variaciones con keywords colombianas
        f"{base_name}colombia.com",
        f"{base_name}group.com",
        f"grupo{base_name}.com",
        # Con guiones comunes
        f"{base_name.replace('logistics', '-logistics')}.com",
        f"{base_name.replace('group', '-group')}.com",
        f"{base_name.replace('company', '-company')}.com",
    ]

    # Remover duplicados y el dominio original
    variaciones_unicas = list(dict.fromkeys(variaciones))
    return [v for v in variaciones_unicas if v != dominio_original]


def _get_headers_rotativos() -> dict[str, str]:
    """
    Retorna headers con User-Agent rotativo.
    Técnica: User-Agent Rotation (Prioridad 1 - Anti-blocking)
    """
    return {
        "User-Agent": random.choice(_USER_AGENT_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _intentar_variaciones_protocolo(base_domain: str) -> list[str]:
    """
    Genera variaciones de protocolo y www.
    Técnica: Protocol Fallbacks (Prioridad 1 - DNS y conectividad)
    """
    variaciones = [
        f"https://{base_domain}",
        f"http://{base_domain}",
        f"https://www.{base_domain}",
        f"http://www.{base_domain}",
    ]
    return list(dict.fromkeys(variaciones))  # Remover duplicados


def _normalizar_pais_hq(valor: str | None) -> str | None:
    """
    Normaliza el campo pais_hq crudo del LLM a un código ISO Alpha-2 en
    mayúsculas de exactamente 2 letras, o None si no es utilizable.

    Contrato defensivo: el LLM puede alucinar nombres completos de país
    ("United Kingdom"), minúsculas, o strings vacíos. Solo se acepta un
    resultado que YA tenga forma de código Alpha-2 (2 letras alfabéticas);
    cualquier otra cosa se descarta como None en vez de propagar basura
    hacia PoliticaValidacionGeografica.
    """
    if not valor:
        return None
    candidato = valor.strip().upper()
    if len(candidato) == 2 and candidato.isalpha():
        return candidato
    return None


def _normalizar_tipo_organizacion(valor: str | None) -> TipoOrganizacion | None:
    """
    Normaliza el campo tipo_organizacion crudo del LLM a un miembro válido de
    TipoOrganizacion, o None si no es utilizable.

    Contrato defensivo (mismo patrón que _normalizar_pais_hq): el LLM puede
    responder null, un valor fuera del vocabulario, o con espacios/minúsculas.
    Cualquier valor no reconocido se descarta como None en vez de tumbar toda
    la respuesta (que también contiene es_vendor_it, tamano y país). Un
    tipo_organizacion=None NO excluye la empresa: PoliticaTipoOrganizacion es
    fail-open en este eje (ver su docstring).
    """
    if not valor:
        return None
    candidato = valor.strip().upper()
    try:
        return TipoOrganizacion(candidato)
    except ValueError:
        return None


class _RespuestaClasificacion(BaseModel):
    """Esquema de validación de la respuesta cruda del LLM."""

    es_vendor_it: bool
    tamano_estimado: TamanoEmpresa | None = None
    pais_hq: str | None = None
    # Crudo (str) en vez de TipoOrganizacion directo: un valor fuera del
    # vocabulario NO debe invalidar toda la respuesta — se normaliza aparte
    # (ver _normalizar_tipo_organizacion) para caer a None sin perder las
    # otras tres señales de la misma llamada.
    tipo_organizacion: str | None = None


@dataclass(frozen=True)
class _AnalisisPropuestaValor:
    """Resultado interno combinado: las cuatro señales de una sola llamada al LLM."""

    es_vendor_it: bool
    tamano_estimado: TamanoEmpresa | None
    pais_hq: str | None
    tipo_organizacion: TipoOrganizacion | None


class PropuestaValorAdapter(PuertoClasificadorPropuestaValor, PuertoEstimadorTamano):
    """
    Args:
        api_key: Clave de API de Groq única. Si se provee, tiene prioridad
            sobre `key_pool` y sobre el descubrimiento automático — construye
            un pool de una sola clave (comportamiento previo, preservado
            para no romper integraciones existentes).
        key_pool: GroqKeyPool ya construido, inyectable para tests o para
            compartir el mismo pool entre varios adaptadores del Motor 2 en
            un mismo proceso. Si None y no se pasa `api_key`, se construye
            un GroqKeyPool() que descubre GROQ_API_KEY_1..N del entorno (o
            GROQ_API_KEY como fallback de una sola clave).

    Rotación reactiva con cooldown (failover): este adaptador es el mayor
    consumidor de tokens del Motor 2 (una lectura de homepage + una llamada
    LLM por cada empresa candidata ambigua del Negative ICP), y el primero
    en agotar el límite de Tokens Por Día del tier gratuito de Groq en
    corridas de batch grande (confirmado en corrida real, 2026-07: falla a
    partir de la empresa #15 de un lote de 50). Ver
    `src/adapters/llm/groq_key_pool.py` para el diseño de la rotación.
    """

    def __init__(
        self,
        api_key: str | None = None,
        key_pool: GroqKeyPool | None = None,
    ) -> None:
        if api_key is not None:
            self._pool = GroqKeyPool(api_keys=[api_key])
        elif key_pool is not None:
            self._pool = key_pool
        else:
            self._pool = GroqKeyPool()

        if not self._pool.tiene_claves:
            logger.warning(
                "GROQ_API_KEY (o GROQ_API_KEY_1..N) no configurada(s). "
                "PropuestaValorAdapter retornará None hasta que se configure."
            )
        # Cache por instancia: evita pagar 2 lecturas web + 2 llamadas LLM
        # cuando el orquestador invoca clasificar() y estimar_tamano() sobre
        # la MISMA empresa en el mismo pase (caso normal en el sandbox).
        self._cache: dict[uuid.UUID, _AnalisisPropuestaValor | None] = {}
        # Cache separado del texto leído (independiente de si el análisis
        # LLM tuvo éxito o no) — usado por snippet_homepage() para exponer
        # evidencia al Paquete de Revisión Manual sin duplicar lecturas de red.
        self._cache_texto: dict[uuid.UUID, str | None] = {}

    # ──────────────────────────────────────────────────────────────────────
    # PuertoClasificadorPropuestaValor — Capa 2 del Negative ICP
    # ──────────────────────────────────────────────────────────────────────
    def clasificar(self, empresa: Empresa) -> CategoriaEmpresa | None:
        """
        Implementa PuertoClasificadorPropuestaValor.clasificar().

        Mapeo de la señal binaria es_vendor_it al vocabulario CategoriaEmpresa
        del Core: si el LLM concluye que la empresa candidata SÍ es un vendor
        de TI, se retorna CategoriaEmpresa.AGENCIA_IT (el ancla genérica de
        "vendor de tecnología a terceros" que ya usa PoliticaExclusionCompetidores
        en CATEGORIAS_AMBIGUAS). Si concluye que NO lo es, o si el análisis
        falla, se retorna None — el llamador (composition root) decide cómo
        tratar ambos casos; para el detalle fino (competidor confirmado NO)
        el adaptador expone también es_vendor_it() como método concreto.
        """
        analisis = self._analizar(empresa)
        if analisis is None:
            return None
        if analisis.es_vendor_it:
            return CategoriaEmpresa.AGENCIA_IT
        return None

    # ──────────────────────────────────────────────────────────────────────
    # PuertoEstimadorTamano — segunda señal gratis para el waterfall
    # ──────────────────────────────────────────────────────────────────────
    def estimar_tamano(self, empresa: Empresa) -> EstimacionTamano | None:
        """
        Implementa PuertoEstimadorTamano.estimar_tamano().

        Retorna None si el análisis falló o si el LLM no pudo inferir ningún
        tamaño del lenguaje del texto (tamano_estimado=null es una respuesta
        válida del LLM, no un error).
        """
        analisis = self._analizar(empresa)
        if analisis is None or analisis.tamano_estimado is None:
            return None
        return EstimacionTamano(
            origen=OrigenTrigger.PROPUESTA_VALOR,
            tamano_estimado=analisis.tamano_estimado,
            confianza=_CONFIANZA_ESTIMACION_SEMANTICA,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Detalle de implementación expuesto al composition root (NO forma parte
    # de ningún puerto del Core — es una conveniencia de la capa de
    # adaptador para el orquestador, que ya conoce clases concretas).
    # ──────────────────────────────────────────────────────────────────────
    def es_vendor_it(self, empresa: Empresa) -> bool | None:
        """
        Expone la señal binaria cruda (sin pasar por el mapeo a CategoriaEmpresa)
        para que el composition root pueda desempatar con precisión entre
        "confirmado competidor", "confirmado NO competidor" y "no se pudo
        determinar" — distinción que clasificar() por sí solo no preserva.

        Retorna None si el análisis no pudo completarse (no hay señal).
        """
        analisis = self._analizar(empresa)
        return analisis.es_vendor_it if analisis is not None else None

    def snippet_homepage(self, empresa: Empresa) -> str | None:
        """
        Expone el texto público que se leyó (y se envió al LLM) para esta
        empresa. Pensado para el Paquete de Revisión Manual (ver
        src/adapters/revision_manual/paquete_revision_adapter.py): el humano
        ve exactamente el mismo texto que vio el LLM al no poder decidir,
        en vez de tener que re-investigar desde cero.

        Reutiliza el cache de texto poblado por _analizar() — nunca dispara
        una segunda lectura de red para la misma empresa. Si la empresa
        nunca pasó por _analizar() (ej. se llama snippet_homepage() antes de
        cualquier otro método), fuerza esa primera lectura una sola vez.
        Retorna None si no hay texto disponible (mismo contrato del resto).
        """
        if empresa.id not in self._cache_texto:
            self._analizar(empresa)
        return self._cache_texto.get(empresa.id)

    def pais_hq(self, empresa: Empresa) -> str | None:
        """
        Expone el país de HQ inferido semánticamente (código ISO Alpha-2),
        para que el composition root lo cruce con manifiesto.geografia vía
        PoliticaValidacionGeografica.

        Retorna None si el análisis no pudo completarse o si el LLM no
        encontró ninguna pista textual verificable del país de HQ — ambos
        casos son "sin señal", no "empresa sin país" (fail-closed: el
        llamador debe tratar None como INDETERMINADO, nunca como aprobación
        automática).
        """
        analisis = self._analizar(empresa)
        return analisis.pais_hq if analisis is not None else None

    def tipo_organizacion(self, empresa: Empresa) -> TipoOrganizacion | None:
        """
        Expone el TIPO de organización inferido semánticamente (empresa
        privada, gobierno, ONG, medios, educación, gremio, otro), para que el
        composition root aplique PoliticaTipoOrganizacion (Motor 2 — gate de
        tipo de organización, afinamiento post-piloto TBBC).

        Reutiliza la MISMA llamada cacheada que clasificar()/estimar_tamano()/
        pais_hq(): no gasta una segunda lectura web ni una segunda llamada al
        LLM para la misma empresa.

        Retorna None si el análisis no pudo completarse (scraping/LLM sin
        señal) o si el LLM no pudo determinar el tipo. None es "sin señal", no
        "empresa sospechosa": PoliticaTipoOrganizacion trata None como apta
        (fail-open en este eje; los demás gates siguen aplicando).
        """
        analisis = self._analizar(empresa)
        return analisis.tipo_organizacion if analisis is not None else None

    # ──────────────────────────────────────────────────────────────────────
    # Lógica interna compartida — una lectura web + una llamada LLM
    # ──────────────────────────────────────────────────────────────────────
    def _analizar(self, empresa: Empresa) -> _AnalisisPropuestaValor | None:
        if empresa.id in self._cache:
            return self._cache[empresa.id]

        resultado = self._analizar_sin_cache(empresa)
        self._cache[empresa.id] = resultado
        return resultado

    def _analizar_sin_cache(self, empresa: Empresa) -> _AnalisisPropuestaValor | None:
        cliente = self._pool.cliente_activo()
        if cliente is None:
            logger.warning(
                "PropuestaValorAdapter: sin clientes Groq disponibles "
                "(sin claves configuradas o todas en enfriamiento) para '%s'.",
                empresa.nombre,
            )
            return None

        # Preservar nombre de empresa para Domain Discovery
        self._empresa_nombre_actual = empresa.nombre
        texto = self._leer_texto_homepage(empresa.dominio, empresa.nombre)
        self._cache_texto[empresa.id] = texto
        if not texto:
            return None

        contenido = self._llamar_llm_con_failover(cliente, texto, empresa)
        if not contenido:
            return None

        try:
            respuesta = _RespuestaClasificacion.model_validate_json(contenido)
        except ValidationError as exc:
            logger.warning(
                "PropuestaValorAdapter: respuesta del LLM con formato inválido "
                "para '%s': %s",
                empresa.nombre,
                exc,
            )
            return None

        pais_hq_normalizado = _normalizar_pais_hq(respuesta.pais_hq)
        tipo_org_normalizado = _normalizar_tipo_organizacion(
            respuesta.tipo_organizacion
        )
        logger.info(
            "PropuestaValorAdapter: '%s' → es_vendor_it=%s, tamano_estimado=%s, "
            "pais_hq=%s, tipo_organizacion=%s",
            empresa.nombre,
            respuesta.es_vendor_it,
            respuesta.tamano_estimado,
            pais_hq_normalizado,
            tipo_org_normalizado,
        )
        return _AnalisisPropuestaValor(
            es_vendor_it=respuesta.es_vendor_it,
            tamano_estimado=respuesta.tamano_estimado,
            pais_hq=pais_hq_normalizado,
            tipo_organizacion=tipo_org_normalizado,
        )

    def _llamar_llm_con_failover(
        self, cliente: groq_sdk.Groq, texto: str, empresa: Empresa
    ) -> str | None:
        """
        Invoca al LLM con el cliente activo del pool. Ante un RateLimitError
        (429), registra la clave agotada en el pool (que la marca en
        enfriamiento por el tiempo parseado del propio mensaje de error) y
        reintenta UNA vez con la siguiente clave disponible — afinidad
        preservada: no rota en cada llamada, solo cuando la activa se agota.

        Si el failover también agota el pool completo (todas en
        enfriamiento) o si el segundo intento también recibe 429, retorna
        None — mismo contrato de "nunca propagar al Core" que el resto del
        adaptador.
        """
        try:
            return self._invocar_llm(cliente, texto)
        except groq_sdk.RateLimitError as exc:
            logger.warning(
                "PropuestaValorAdapter: rate limit para '%s': %s", empresa.nombre, exc
            )
            cliente_failover = self._pool.registrar_rate_limit(exc)
            if cliente_failover is None:
                logger.error(
                    "PropuestaValorAdapter: pool de claves Groq agotado "
                    "(todas en enfriamiento). Sin reintento para '%s'.",
                    empresa.nombre,
                )
                return None
            try:
                return self._invocar_llm(cliente_failover, texto)
            except groq_sdk.RateLimitError as exc2:
                logger.warning(
                    "PropuestaValorAdapter: rate limit también en la clave de "
                    "failover para '%s': %s. Sin más reintentos.",
                    empresa.nombre,
                    exc2,
                )
                self._pool.registrar_rate_limit(exc2)
                return None
            except groq_sdk.APIError as exc2:
                logger.error(
                    "PropuestaValorAdapter: error de API (failover) para '%s': %s",
                    empresa.nombre,
                    exc2,
                )
                return None
            except Exception as exc2:  # noqa: BLE001 — contrato: nunca propagar al Core
                logger.error(
                    "PropuestaValorAdapter: error inesperado con LLM (failover) "
                    "para '%s': %s",
                    empresa.nombre,
                    exc2,
                )
                return None
        except groq_sdk.APIError as exc:
            logger.error(
                "PropuestaValorAdapter: error de API para '%s': %s",
                empresa.nombre,
                exc,
            )
            return None
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error(
                "PropuestaValorAdapter: error inesperado con LLM para '%s': %s",
                empresa.nombre,
                exc,
            )
            return None

    def _invocar_llm(self, cliente: groq_sdk.Groq, texto: str) -> str | None:
        """Llamada directa al SDK. Sin manejo de errores — eso lo hace el llamador."""
        completion = cliente.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": texto},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200,
        )
        return completion.choices[0].message.content

    def _leer_texto_homepage(self, dominio: str) -> str | None:
        """
        Estrategia de scraping robusto con cascada completa.
        Implementa todas las técnicas de Prioridad 1:
        1. Domain Discovery - variaciones de dominio
        2. Anti-blocking - User-Agent rotation + exponential backoff
        3. DNS alternatives - protocol fallbacks
        4. Rutas alternas originales + Playwright como último recurso
        """
        if not dominio:
            return None

        # 1. Intentar dominio original con técnicas robustas
        url_raiz = _construir_url(dominio)
        texto = self._leer_texto_url_robusto(url_raiz)
        if texto:
            logger.info(
                f"PropuestaValorAdapter: éxito con dominio original '{dominio}'"
            )
            return texto

        # 2. Intentar rutas alternas en dominio original (comportamiento previo preservado)
        logger.info(
            f"PropuestaValorAdapter: sin texto en raíz '{dominio}', probando rutas alternas..."
        )
        for ruta in _RUTAS_ALTERNAS:
            texto = self._leer_texto_url_robusto(url_raiz.rstrip("/") + ruta)
            if texto:
                logger.info(
                    f"PropuestaValorAdapter: éxito en ruta alterna '{ruta}' para '{dominio}'"
                )
                return texto

        # 3. NUEVA: Intentar variaciones de dominio (Domain Discovery)
        empresa_nombre = (
            getattr(self, "_empresa_nombre_actual", "") or dominio.split(".")[0]
        )
        variaciones_dominio = _generar_variaciones_dominio(empresa_nombre, dominio)

        if variaciones_dominio:
            logger.info(
                f"PropuestaValorAdapter: probando {len(variaciones_dominio)} variaciones de dominio para '{dominio}'"
            )
            for dominio_alt in variaciones_dominio[
                :3
            ]:  # Limitar a 3 para no ser muy lento
                url_alt = _construir_url(dominio_alt)
                texto = self._leer_texto_url_robusto(url_alt)
                if texto:
                    logger.info(
                        f"PropuestaValorAdapter: éxito con variación de dominio '{dominio_alt}' para '{dominio}'"
                    )
                    return texto

        # 4. Fallback Playwright (último recurso, comportamiento previo preservado)
        logger.info(
            f"PropuestaValorAdapter: todas las variaciones fallaron para '{dominio}', intentando Playwright..."
        )
        texto_render = _renderizar_con_playwright(url_raiz)
        if texto_render:
            texto_limpio = re.sub(r"\s+", " ", texto_render).strip()
            if texto_limpio:
                logger.info(
                    f"PropuestaValorAdapter: éxito con Playwright para '{dominio}'"
                )
                return texto_limpio[:_MAX_CARACTERES_TEXTO_HOMEPAGE]

        logger.warning(
            f"PropuestaValorAdapter: todos los métodos fallaron para '{dominio}'"
        )
        return None

    def _leer_texto_url_robusto(
        self, url: str, max_retries: int = _MAX_RETRIES
    ) -> str | None:
        """
        Descarga UNA url con técnicas de robustez integradas.
        Implementa: Exponential Backoff + User-Agent Rotation + Protocol Fallbacks
        Técnicas Prioridad 1: Anti-blocking + DNS alternatives
        """
        urls_intentar = [url] + _intentar_variaciones_protocolo(
            url.replace("https://", "").replace("http://", "")
        )

        for attempt, url_actual in enumerate(urls_intentar):
            for retry in range(max_retries):
                try:
                    headers = _get_headers_rotativos()
                    timeout = _REQUEST_TIMEOUT_SECS + (retry * 5)  # Timeout progresivo

                    response = requests.get(
                        url_actual,
                        timeout=timeout,
                        headers=headers,
                        allow_redirects=True,
                    )
                    response.raise_for_status()

                    # Procesar HTML exitosamente
                    return self._procesar_html_response(response, url_actual)

                except requests.exceptions.Timeout:
                    if retry < max_retries - 1:
                        wait_time = _BASE_BACKOFF_SECONDS * (2**retry) + random.uniform(
                            0.5, 1.5
                        )
                        logger.info(
                            f"PropuestaValorAdapter: timeout en '{url_actual}', reintentando en {wait_time:.1f}s (intento {retry + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(
                            f"PropuestaValorAdapter: timeout definitivo en '{url_actual}' después de {max_retries} intentos"
                        )

                except requests.exceptions.ConnectionError:
                    if retry < max_retries - 1:
                        wait_time = _BASE_BACKOFF_SECONDS * (2**retry) + random.uniform(
                            0.5, 1.5
                        )
                        logger.info(
                            f"PropuestaValorAdapter: error conexión '{url_actual}', reintentando en {wait_time:.1f}s"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(
                            f"PropuestaValorAdapter: no se pudo conectar a '{url_actual}' después de {max_retries} intentos"
                        )
                        break  # Probar siguiente variación de URL

                except requests.exceptions.HTTPError as exc:
                    if exc.response and exc.response.status_code == 429:  # Rate limited
                        if retry < max_retries - 1:
                            wait_time = _BASE_BACKOFF_SECONDS * (
                                2 ** (retry + 2)
                            )  # Backoff más agresivo para 429
                            logger.info(
                                f"PropuestaValorAdapter: rate limit '{url_actual}', esperando {wait_time}s"
                            )
                            time.sleep(wait_time)
                            continue

                    status_code = exc.response.status_code if exc.response else "?"
                    logger.warning(
                        f"PropuestaValorAdapter: HTTP {status_code} en '{url_actual}'"
                    )
                    break  # Probar siguiente variación de URL

                except requests.exceptions.SSLError:
                    logger.warning(
                        f"PropuestaValorAdapter: SSL error en '{url_actual}'"
                    )
                    break  # Probar siguiente variación de URL

                except Exception as exc:
                    logger.error(
                        f"PropuestaValorAdapter: error inesperado en '{url_actual}': {exc}"
                    )
                    break

        return None

    def _procesar_html_response(
        self, response: requests.Response, url: str
    ) -> str | None:
        """Procesa respuesta HTML exitosa - extraído para reutilización."""
        try:
            soup = BeautifulSoup(response.text, "html.parser")

            # Extraer title y meta description como antes
            texto_meta_partes: list[str] = []
            if soup.title and soup.title.string:
                texto_meta_partes.append(soup.title.string.strip())
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                texto_meta_partes.append(str(meta_desc["content"]).strip())
            texto_meta = " ".join(p for p in texto_meta_partes if p)

            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            texto_crudo = soup.get_text(separator=" ", strip=True)
        except Exception as exc:
            logger.error(
                f"PropuestaValorAdapter: error parseando HTML de '{url}': {exc}"
            )
            return None

        texto_limpio = re.sub(r"\s+", " ", texto_crudo).strip()

        # Fallback title/meta si body insuficiente
        if len(texto_limpio) < _MIN_CARACTERES_TEXTO_SUFICIENTE and texto_meta:
            logger.info(
                f"PropuestaValorAdapter: texto insuficiente ({len(texto_limpio)} chars) en '{url}', usando fallback title/meta"
            )
            texto_limpio = re.sub(r"\s+", " ", f"{texto_meta} {texto_limpio}").strip()

        if not texto_limpio:
            return None

        return texto_limpio[:_MAX_CARACTERES_TEXTO_HOMEPAGE]
