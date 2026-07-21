"""
PropuestaValorAdapter — implementación de PuertoClasificadorPropuestaValor
y PuertoEstimadorTamano.

Diseño: investigación "Negative ICP" / "Waterfall Enrichment"
(10-Memoria_Consolidada/tecnico/prospector-m3-m4-design.md, sesión de
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
"""

from __future__ import annotations

import logging
import re
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

# Estrategia de reintentos técnicos (respuesta a hallazgo de corrida real:
# muchos casos que caen en PENDIENTE_REVISION_MANUAL no son ambigüedad
# semántica real, sino fallas técnicas de lectura — la raíz del dominio
# viene vacía pero la empresa SÍ tiene texto público en otra ruta). Se
# intentan, EN ORDEN, solo cuando la raíz del dominio no dio NINGÚN texto
# utilizable (ni body visible ni meta-fallback) — nunca cuando la raíz sí
# dio algo, por corto que sea (preserva el comportamiento histórico: un
# texto corto pero real sigue siendo mejor señal que gastar más llamadas).
_RUTAS_ALTERNAS: tuple[str, ...] = ("/nosotros", "/about", "/quienes-somos", "/about-us")

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
                page.goto(url, timeout=_PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
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
TRES preguntas sobre esa empresa, en base ÚNICAMENTE al texto proporcionado.

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
              adivines a partir del idioma del texto solamente: el idioma español no implica LATAM.>"
}

REGLAS CRÍTICAS:
1. Responde SOLO con el JSON. Sin explicaciones. Sin bloques de código markdown.
2. Si el texto es insuficiente para juzgar es_vendor_it con razonable confianza, aun así responde tu
   mejor estimación — el llamador ya sabe que esto es una inferencia, no un hecho verificado.
3. tamano_estimado y pais_hq pueden ser null; es_vendor_it NUNCA puede ser null (siempre true o false)."""


def _construir_url(dominio: str) -> str:
    dominio = dominio.strip().lower()
    if not dominio.startswith("http"):
        return f"https://{dominio}"
    return dominio


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


class _RespuestaClasificacion(BaseModel):
    """Esquema de validación de la respuesta cruda del LLM."""

    es_vendor_it: bool
    tamano_estimado: TamanoEmpresa | None = None
    pais_hq: str | None = None


@dataclass(frozen=True)
class _AnalisisPropuestaValor:
    """Resultado interno combinado: las tres señales de una sola llamada al LLM."""

    es_vendor_it: bool
    tamano_estimado: TamanoEmpresa | None
    pais_hq: str | None


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

        texto = self._leer_texto_homepage(empresa.dominio)
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
        logger.info(
            "PropuestaValorAdapter: '%s' → es_vendor_it=%s, tamano_estimado=%s, "
            "pais_hq=%s",
            empresa.nombre,
            respuesta.es_vendor_it,
            respuesta.tamano_estimado,
            pais_hq_normalizado,
        )
        return _AnalisisPropuestaValor(
            es_vendor_it=respuesta.es_vendor_it,
            tamano_estimado=respuesta.tamano_estimado,
            pais_hq=pais_hq_normalizado,
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
        Descarga la homepage pública del dominio y extrae texto visible
        limpio (sin scripts/estilos), truncado a _MAX_CARACTERES_TEXTO_HOMEPAGE.

        Estrategia de reintentos técnicos (respuesta a hallazgo de corrida
        real: un "indeterminado" frecuentemente no es ambigüedad semántica
        real sino una falla técnica de lectura — ver _RUTAS_ALTERNAS y
        _renderizar_con_playwright arriba). Cascada, del más barato al más
        caro, deteniéndose en el primer resultado utilizable:
            1. Raíz del dominio vía `requests` + BeautifulSoup (camino feliz,
               sin cambios respecto a la versión anterior).
            2. Si (1) no dio NADA de texto (ni body ni meta-fallback): rutas
               alternas comunes (/nosotros, /about, /quienes-somos,
               /about-us), mismo método liviano.
            3. Si ninguna ruta alterna dio texto: fallback pesado con
               Playwright (navegador real, ejecuta JS) sobre la raíz del
               dominio — último recurso para SPAs sin server-side rendering.

        Contrato: nunca lanza excepción. Cualquier fallo de red/parseo en
        TODA la cascada → None.
        """
        if not dominio:
            return None

        url_raiz = _construir_url(dominio)
        texto = self._leer_texto_url(url_raiz)
        if texto:
            return texto

        logger.info(
            "PropuestaValorAdapter: sin texto utilizable en raíz '%s'. "
            "Probando rutas alternas...",
            url_raiz,
        )
        for ruta in _RUTAS_ALTERNAS:
            texto = self._leer_texto_url(url_raiz.rstrip("/") + ruta)
            if texto:
                logger.info(
                    "PropuestaValorAdapter: texto recuperado en ruta alterna "
                    "'%s' para '%s'.",
                    ruta,
                    dominio,
                )
                return texto

        logger.info(
            "PropuestaValorAdapter: ninguna ruta alterna dio texto para '%s'. "
            "Intentando fallback Playwright (render con JS)...",
            dominio,
        )
        texto_render = _renderizar_con_playwright(url_raiz)
        if texto_render:
            texto_limpio = re.sub(r"\s+", " ", texto_render).strip()
            if texto_limpio:
                logger.info(
                    "PropuestaValorAdapter: texto recuperado vía Playwright "
                    "para '%s'.",
                    dominio,
                )
                return texto_limpio[:_MAX_CARACTERES_TEXTO_HOMEPAGE]

        return None

    def _leer_texto_url(self, url: str) -> str | None:
        """
        Descarga UNA url específica y extrae texto visible limpio (con el
        mismo fallback de title/meta description que el camino histórico).
        Sin cascada — es el bloque reusable que _leer_texto_homepage invoca
        tanto sobre la raíz del dominio como sobre cada ruta alterna.

        Contrato: nunca lanza excepción. Cualquier fallo de red/parseo → None.
        """
        try:
            response = requests.get(
                url,
                timeout=_REQUEST_TIMEOUT_SECS,
                headers=_BROWSER_HEADERS,
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.warning(
                "PropuestaValorAdapter: timeout leyendo '%s'. Retornando None.", url
            )
            return None
        except requests.exceptions.SSLError:
            logger.warning(
                "PropuestaValorAdapter: SSL error leyendo '%s'. Retornando None.", url
            )
            return None
        except requests.exceptions.ConnectionError:
            logger.warning(
                "PropuestaValorAdapter: no se pudo conectar a '%s'. Retornando None.",
                url,
            )
            return None
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "PropuestaValorAdapter: HTTP %s leyendo '%s'. Retornando None.",
                exc.response.status_code if exc.response else "?",
                url,
            )
            return None
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error(
                "PropuestaValorAdapter: error inesperado leyendo '%s': %s", url, exc
            )
            return None

        try:
            soup = BeautifulSoup(response.text, "html.parser")

            # Extraer <title> y <meta name="description"> ANTES de decompose,
            # como respaldo para SPAs en JS donde el body visible viene vacío
            # o casi vacío (sin server-side rendering, BeautifulSoup no
            # ejecuta JavaScript). Ambas etiquetas viven en <head> y son
            # texto público estático independiente del render del cliente.
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
        except Exception as exc:  # noqa: BLE001 — parseo de HTML no debe tumbar el flujo
            logger.error(
                "PropuestaValorAdapter: error parseando HTML de '%s': %s", url, exc
            )
            return None

        texto_limpio = re.sub(r"\s+", " ", texto_crudo).strip()

        # Fallback (Falla 1 — SPA sin texto visible): si el body visible es
        # insuficiente, se antepone el texto de title/meta description. No
        # sustituye al body (puede aportar señal adicional), solo lo complementa.
        if len(texto_limpio) < _MIN_CARACTERES_TEXTO_SUFICIENTE and texto_meta:
            logger.info(
                "PropuestaValorAdapter: texto visible insuficiente (%d "
                "caracteres) para '%s'. Usando fallback de title/meta "
                "description.",
                len(texto_limpio),
                url,
            )
            texto_limpio = re.sub(r"\s+", " ", f"{texto_meta} {texto_limpio}").strip()

        if not texto_limpio:
            return None

        return texto_limpio[:_MAX_CARACTERES_TEXTO_HOMEPAGE]
