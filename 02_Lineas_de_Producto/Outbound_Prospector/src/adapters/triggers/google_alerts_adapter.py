"""
GoogleAlertsRSSAdapter — implementación del PuertoFuenteTriggers.

Parsea feeds RSS de Google Alerts / Google News para detectar eventos de
negocio y liderazgo en la empresa objetivo: rondas de inversión, llegada de
nuevos C-Levels técnicos, fusiones/adquisiciones.

VERIFICACIÓN SEMÁNTICA POR LLM (fix de raíz, hallazgo de corrida real):
    El query RSS busca el NOMBRE de la empresa en Google News. Para empresas
    que además son MEDIOS (Portafolio, Forbes, Revista Dinero) el feed
    devuelve sus PROPIOS artículos, y la clasificación por substring
    ("director", "nombrado", "nuevo") etiquetaba cualquier titular como
    "nuevo C-Level" — una fábrica de falsos positivos. El substring no
    distingue "nombraron nuevo CTO en <empresa>" de "el director técnico de
    la selección...".

    Por eso la clasificación por keywords se reemplazó por VERIFICACIÓN
    SEMÁNTICA con un LLM (Groq), reutilizando la misma infraestructura de
    failover con cooldown (`GroqKeyPool`) y el mismo patrón de
    PropuestaValorAdapter (una llamada con failover, JSON estructurado,
    response_format json_object, model llama-3.3-70b-versatile). Los sets de
    keywords se conservan ÚNICAMENTE como pre-filtro barato de co-ocurrencia
    de negocio, no como clasificador final.

Mapeo de eventos verificados a la jerarquía Signal-Based Selling (SHiFT!):
    ronda_inversion_o_capital → TIER_0 / CAUSA  (capacity shock), nivel ALTA
    nuevo_liderazgo_tecnico   → TIER_1 / CAUSA  (reorganización),  nivel ALTA
    fusion_o_adquisicion      → TIER_2 / CAUSA  (contexto/fit),    nivel MEDIA

Modo contexto-débil (degradación con gracia — CRÍTICO):
    Si NO hay claves Groq, o el LLM falla / da 429 sin failover / devuelve
    JSON inválido, el adaptador NO clasifica por substring. Retorna a lo sumo
    UN trigger TIER_3 / EFECTO / BAJA de "mención en medios" (aporta 0 al
    score de ScoreTriggerPolicy, pero deja trazabilidad y cuenta para el
    bonus multi-origen SOLO si existe además otra señal real de otro origen).
    Sin LLM el adaptador queda en modo contexto-débil: JAMÁS infla a
    TIER_0/TIER_1.

    Idéntico tratamiento cuando el LLM corre pero NO verifica ningún evento
    pese a que hubo menciones: a lo sumo el trigger TIER_3/BAJA de mención.

Cap por nombre corto/genérico (≤8 chars — riesgo de homónimo): aunque el LLM
    detecte un evento, un nombre de empresa muy corto NUNCA supera TIER_2
    (mismo espíritu que `_es_nombre_generico`), porque el riesgo de que el
    titular sea sobre un homónimo es alto.

Contrato de error: NUNCA propaga excepciones al Core. Cualquier error de red,
parseo o LLM se captura, se registra y se degrada (nunca lanza).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import NamedTuple

import requests

import feedparser
import groq as groq_sdk
from pydantic import BaseModel, Field, ValidationError

from src.adapters.llm.groq_key_pool import GroqKeyPool
from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    TierUrgencia,
    TipoTrigger,
    Trigger,
)
from src.core.ports.interfaces import PuertoFuenteTriggers

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Cuántas entradas RSS candidatas (título+resumen) se envían al LLM en UNA
# sola llamada por empresa (no una llamada por entrada).
_MAX_ENTRADAS_CANDIDATAS = 5

# ---------------------------------------------------------------------------
# Glosario de co-ocurrencia de negocio — PRE-FILTRO barato (Falla 3, caso
# "Parcero"). NO es un clasificador de tier: solo abarata la decisión de qué
# entradas vale la pena mandar al LLM. Un match de nombre por sí solo no basta
# como evidencia de que la mención es sobre LA empresa candidata (problema de
# significado, no de tokenización).
# ---------------------------------------------------------------------------
_GLOSARIO_COOCURRENCIA_NEGOCIO = frozenset(
    {
        "empresa",
        "compañía",
        "compania",
        "company",
        "startup",
        "software",
        "tecnología",
        "tecnologia",
        "technology",
        "agencia",
        "consultora",
        "consulting",
        "negocio",
        "business",
        "ceo",
        "cto",
        "cio",
        "cdo",
        "fundador",
        "founder",
        "director",
        "gerente",
        "inversión",
        "inversion",
        "funding",
        "ronda",
        "clientes",
        "servicios",
        "plataforma",
        "producto",
        "industria",
        "sector",
        "mercado",
        "market",
    }
)

# Nombres de empresa de longitud <= este umbral se consideran "genéricos/
# cortos": palabras comunes del lenguaje cotidiano colisionan con nombres de
# empresa cortos (ej. "parcero", "casa", "sol"). Aunque el LLM verifique un
# evento, un nombre corto NUNCA supera TIER_2 por el riesgo de homónimo.
_LONGITUD_MAXIMA_NOMBRE_GENERICO = 8


class _EntradaRSS(NamedTuple):
    titulo: str
    resumen: str
    enlace: str
    fecha: datetime | None


# ---------------------------------------------------------------------------
# Esquema de la respuesta estructurada del LLM (verificación semántica)
# ---------------------------------------------------------------------------
class _EventoLiderazgo(BaseModel):
    detectado: bool = False
    cargo: str | None = None
    titular_evidencia: str | None = None


class _EventoSimple(BaseModel):
    detectado: bool = False
    titular_evidencia: str | None = None


class _RespuestaVerificacion(BaseModel):
    nuevo_liderazgo_tecnico: _EventoLiderazgo = Field(default_factory=_EventoLiderazgo)
    ronda_inversion_o_capital: _EventoSimple = Field(default_factory=_EventoSimple)
    fusion_o_adquisicion: _EventoSimple = Field(default_factory=_EventoSimple)


_SYSTEM_PROMPT = """Eres un analista de señales de mercado B2B para un sistema de prospección.

Recibirás el nombre y dominio de una EMPRESA OBJETIVO y una lista de titulares/resúmenes de
noticias que la mencionan. Tu tarea es verificar, SOLO con base en esos titulares, si ocurrió
alguno de estos tres eventos GENUINAMENTE sobre la EMPRESA OBJETIVO:

1. nuevo_liderazgo_tecnico: nombramiento reciente de un cargo técnico de alto nivel
   (CTO, VP Engineering, CIO, CDO, Head of Engineering, etc.) DENTRO de la empresa objetivo.
2. ronda_inversion_o_capital: la empresa objetivo levantó una ronda de inversión, recibió
   capital, financiamiento o una valoración relevante.
3. fusion_o_adquisicion: la empresa objetivo fue adquirida, se fusionó, o adquirió a otra.

FORMATO DE RESPUESTA OBLIGATORIO (responde ÚNICAMENTE con este JSON, sin markdown, sin explicaciones):
{
  "nuevo_liderazgo_tecnico": {"detectado": <bool>, "cargo": "<CTO|VP Engineering|CIO|...|null>", "titular_evidencia": "<titular exacto|null>"},
  "ronda_inversion_o_capital": {"detectado": <bool>, "titular_evidencia": "<titular exacto|null>"},
  "fusion_o_adquisicion": {"detectado": <bool>, "titular_evidencia": "<titular exacto|null>"}
}

REGLAS CRÍTICAS (fail-closed):
1. El evento debe ser sobre LA EMPRESA OBJETIVO, no sobre un homónimo, ni sobre otra empresa
   que solo se menciona de pasada, ni sobre el MEDIO que publica la noticia (si la empresa
   objetivo es un medio de comunicación como un periódico o revista, sus propios artículos NO
   son eventos sobre ella misma).
2. El evento debe ser REAL y reciente, no una mención genérica, una opinión, ni un artículo de
   tendencias que solo cite a la empresa.
3. Ante CUALQUIER duda de que el evento sea genuinamente sobre la empresa objetivo, responde
   detectado=false. Es MUCHO peor un falso positivo que un falso negativo.
4. titular_evidencia debe ser el titular exacto (o casi exacto) de la entrada que respalda el
   evento; usa null si detectado=false.
5. Responde SOLO con el JSON. Sin explicaciones. Sin bloques de código markdown."""


def _convertir_fecha_rss(entry) -> datetime | None:
    """Extrae la fecha de una entrada RSS (feedparser) y la convierte a UTC."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            ts = time.mktime(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    return None


def _empresa_mencionada(empresa: Empresa, texto: str) -> bool:
    """
    Verifica si la empresa es mencionada en el texto de la entrada RSS.
    Usa el nombre y el dominio (sin extensión) como patrones de búsqueda.
    """
    nombre_normalizado = empresa.nombre.lower()
    dominio_raiz = empresa.dominio.split(".")[0].lower()  # "acme" de "acme.com"
    texto_lower = texto.lower()

    return nombre_normalizado in texto_lower or dominio_raiz in texto_lower


def _tiene_coocurrencia_negocio(texto: str) -> bool:
    """
    Pre-filtro barato (Falla 3 — caso Parcero): exige co-ocurrencia con
    vocabulario de negocio antes de aceptar una entrada que solo matchea por
    nombre. Filtra el ruido semántico sin descartar de plano el nombre exacto.
    """
    texto_lower = texto.lower()
    return any(palabra in texto_lower for palabra in _GLOSARIO_COOCURRENCIA_NEGOCIO)


def _es_nombre_generico(nombre_empresa: str) -> bool:
    """
    Heurística de longitud: nombres de empresa cortos son más propensos a
    colisionar con palabras coloquiales/genéricas (ej. "Parcero" = amigo en
    colombiano). Aunque el LLM verifique un evento, un nombre corto/genérico
    NUNCA supera TIER_2 por el alto riesgo de homónimo.
    """
    return len(nombre_empresa.strip()) <= _LONGITUD_MAXIMA_NOMBRE_GENERICO


class GoogleAlertsRSSAdapter(PuertoFuenteTriggers):
    """
    Adaptador Motor 2 — señales de noticias y eventos de liderazgo (Google
    Alerts / Google News RSS) verificadas semánticamente por LLM.

    Args:
        rss_urls: Lista de URLs de feeds RSS de Google Alerts / Google News.
        palabras_clave_extra: Keywords adicionales para capturar entradas
            relevantes por dolor/anclaje del ManifiestoICP (ej. "talento
            backend"), sin exigir que mencionen el nombre de la empresa.
        max_triggers_por_empresa: Límite de Triggers a generar por empresa.
        api_key: Clave de API de Groq única. Si se provee, tiene prioridad
            sobre `key_pool` (construye un pool de una sola clave). Mismo
            contrato que PropuestaValorAdapter.
        key_pool: GroqKeyPool ya construido, inyectable para tests o para
            COMPARTIR el mismo pool entre varios adaptadores del Motor 2 en
            un mismo proceso (evita pools duplicados y comparte el estado de
            cooldown de failover). Si None y no se pasa `api_key`, se
            construye un GroqKeyPool() que descubre GROQ_API_KEY_1..N del
            entorno.

    Sin claves Groq (pool vacío) el adaptador queda en modo contexto-débil:
    a lo sumo genera el trigger TIER_3/BAJA de mención en medios, nunca un
    falso-alto TIER_0/TIER_1.
    """

    def __init__(
        self,
        rss_urls: list[str],
        palabras_clave_extra: list[str] | None = None,
        max_triggers_por_empresa: int = 3,
        api_key: str | None = None,
        key_pool: GroqKeyPool | None = None,
    ) -> None:
        self._rss_urls = rss_urls
        self._keywords_extra: frozenset[str] = frozenset(
            kw.lower() for kw in (palabras_clave_extra or [])
        )
        self._max_triggers = max_triggers_por_empresa

        if api_key is not None:
            self._pool = GroqKeyPool(api_keys=[api_key])
        elif key_pool is not None:
            self._pool = key_pool
        else:
            self._pool = GroqKeyPool()

        if not self._pool.tiene_claves:
            logger.warning(
                "GoogleAlerts: sin claves Groq (GROQ_API_KEY(_1..N)). El "
                "adaptador queda en modo contexto-débil: a lo sumo triggers "
                "TIER_3/BAJA de mención en medios, nunca TIER_0/TIER_1."
            )

    # ──────────────────────────────────────────────────────────────────────
    # Puerto
    # ──────────────────────────────────────────────────────────────────────
    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Implementa PuertoFuenteTriggers.obtener_triggers().

        1. Parsea los feeds RSS y pre-filtra las entradas que mencionan a la
           empresa (con co-ocurrencia de negocio) o que matchean keywords del
           ICP.
        2. Si no hay entradas relevantes → [].
        3. UNA llamada LLM por empresa verifica semánticamente los eventos.
        4. Genera Triggers SOLO para eventos verificados, mapeados a la
           jerarquía Signal-Based Selling; sin evento verificado (o sin LLM)
           degrada a lo sumo a un TIER_3/BAJA de "mención en medios".

        Nunca propaga excepciones al Core.
        """
        if not self._rss_urls:
            logger.debug("GoogleAlerts: sin URLs RSS configuradas. Retornando [].")
            return []

        entradas_relevantes: list[_EntradaRSS] = []
        for url in self._rss_urls:
            try:
                entradas_relevantes.extend(self._parsear_feed(url, empresa))
            except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
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

        candidatas = entradas_relevantes[:_MAX_ENTRADAS_CANDIDATAS]
        nombre_generico = _es_nombre_generico(empresa.nombre)

        # Verificación semántica (una sola llamada LLM por empresa). Si el
        # pool no tiene cliente disponible o el LLM falla, `verificacion` es
        # None → degradación a contexto-débil.
        verificacion = self._verificar_eventos(empresa, candidatas)

        if verificacion is None:
            # Modo contexto-débil: nunca clasificar por substring; a lo sumo
            # un trigger TIER_3/BAJA de mención en medios.
            return self._degradar_a_mencion(empresa, candidatas)

        triggers = self._construir_triggers_de_eventos(
            empresa, verificacion, candidatas, nombre_generico
        )
        if not triggers:
            # El LLM corrió pero no verificó ningún evento pese a las
            # menciones → mismo trato contexto-débil.
            return self._degradar_a_mencion(empresa, candidatas)

        return triggers[: self._max_triggers]

    # ──────────────────────────────────────────────────────────────────────
    # Parseo RSS + pre-filtro
    # ──────────────────────────────────────────────────────────────────────
    def _parsear_feed(self, url: str, empresa: Empresa) -> list[_EntradaRSS]:
        """
        Descarga y parsea un feed RSS usando headers de navegador para evadir
        WAF. Filtra entradas que mencionan a la empresa (con co-ocurrencia de
        negocio) o que matchean keywords del ICP.
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

            menciona_empresa = _empresa_mencionada(empresa, texto_completo)
            menciona_keyword = any(
                kw in texto_completo.lower() for kw in self._keywords_extra
            )

            if not (menciona_empresa or menciona_keyword):
                continue

            # Match por NOMBRE solo → exigir co-ocurrencia de negocio (Falla 3).
            # Los matches por keyword del ICP ya son términos específicos de
            # negocio, no pasan por este filtro.
            if menciona_empresa and not menciona_keyword:
                if not _tiene_coocurrencia_negocio(texto_completo):
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

    # ──────────────────────────────────────────────────────────────────────
    # Verificación semántica por LLM (con failover)
    # ──────────────────────────────────────────────────────────────────────
    def _verificar_eventos(
        self, empresa: Empresa, entradas: list[_EntradaRSS]
    ) -> _RespuestaVerificacion | None:
        """
        UNA llamada LLM por empresa. Retorna la verificación estructurada, o
        None ante cualquier fallo (sin claves/cooldown, error de red, JSON
        inválido) — el llamador lo trata como degradación a contexto-débil.
        """
        cliente = self._pool.cliente_activo()
        if cliente is None:
            logger.warning(
                "GoogleAlerts: sin clientes Groq disponibles (sin claves o "
                "todas en enfriamiento) para '%s'. Modo contexto-débil.",
                empresa.nombre,
            )
            return None

        contenido = self._construir_prompt_usuario(empresa, entradas)
        crudo = self._llamar_llm_con_failover(cliente, contenido, empresa)
        if not crudo:
            return None

        try:
            return _RespuestaVerificacion.model_validate_json(crudo)
        except ValidationError as exc:
            logger.warning(
                "GoogleAlerts: respuesta LLM con formato inválido para '%s': %s. "
                "Degradando a contexto-débil.",
                empresa.nombre,
                exc,
            )
            return None

    @staticmethod
    def _construir_prompt_usuario(empresa: Empresa, entradas: list[_EntradaRSS]) -> str:
        lineas = [
            f"EMPRESA OBJETIVO: {empresa.nombre}",
            f"DOMINIO: {empresa.dominio}",
            "",
            "TITULARES / RESÚMENES A VERIFICAR:",
        ]
        for i, e in enumerate(entradas, start=1):
            resumen = e.resumen.strip()
            if len(resumen) > 300:
                resumen = resumen[:300] + "..."
            lineas.append(f"{i}. Título: {e.titulo}")
            if resumen:
                lineas.append(f"   Resumen: {resumen}")
        return "\n".join(lineas)

    def _llamar_llm_con_failover(
        self, cliente: groq_sdk.Groq, contenido: str, empresa: Empresa
    ) -> str | None:
        """
        Invoca al LLM con el cliente activo. Ante 429 (RateLimitError),
        registra la clave agotada en el pool (cooldown) y reintenta UNA vez
        con la siguiente clave disponible. Si el pool queda agotado, o ante
        cualquier otro error, retorna None (degradación, nunca propaga).
        Mismo patrón que PropuestaValorAdapter.
        """
        try:
            return self._invocar_llm(cliente, contenido)
        except groq_sdk.RateLimitError as exc:
            logger.warning(
                "GoogleAlerts: rate limit para '%s': %s", empresa.nombre, exc
            )
            cliente_failover = self._pool.registrar_rate_limit(exc)
            if cliente_failover is None:
                logger.error(
                    "GoogleAlerts: pool de claves Groq agotado (todas en "
                    "enfriamiento). Sin reintento para '%s'.",
                    empresa.nombre,
                )
                return None
            try:
                return self._invocar_llm(cliente_failover, contenido)
            except groq_sdk.RateLimitError as exc2:
                logger.warning(
                    "GoogleAlerts: rate limit también en la clave de failover "
                    "para '%s': %s. Sin más reintentos.",
                    empresa.nombre,
                    exc2,
                )
                self._pool.registrar_rate_limit(exc2)
                return None
            except Exception as exc2:  # noqa: BLE001 — nunca propagar al Core
                logger.error(
                    "GoogleAlerts: error inesperado con LLM (failover) para '%s': %s",
                    empresa.nombre,
                    exc2,
                )
                return None
        except groq_sdk.APIError as exc:
            logger.error(
                "GoogleAlerts: error de API para '%s': %s", empresa.nombre, exc
            )
            return None
        except Exception as exc:  # noqa: BLE001 — nunca propagar al Core
            logger.error(
                "GoogleAlerts: error inesperado con LLM para '%s': %s",
                empresa.nombre,
                exc,
            )
            return None

    def _invocar_llm(self, cliente: groq_sdk.Groq, contenido: str) -> str | None:
        """Llamada directa al SDK. Sin manejo de errores — eso lo hace el llamador."""
        completion = cliente.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": contenido},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=400,
        )
        return completion.choices[0].message.content

    # ──────────────────────────────────────────────────────────────────────
    # Construcción de Triggers a partir de la verificación
    # ──────────────────────────────────────────────────────────────────────
    def _construir_triggers_de_eventos(
        self,
        empresa: Empresa,
        verificacion: _RespuestaVerificacion,
        entradas: list[_EntradaRSS],
        nombre_generico: bool,
    ) -> list[Trigger]:
        """
        Mapea los eventos verificados (detectado=True) a Triggers de la
        jerarquía Signal-Based Selling. Solo eventos verificados generan
        trigger. Orden de prioridad: ronda (TIER_0) → liderazgo (TIER_1) →
        M&A (TIER_2).
        """
        triggers: list[Trigger] = []

        ronda = verificacion.ronda_inversion_o_capital
        if ronda.detectado:
            tier, nivel = self._cap_generico(
                TierUrgencia.TIER_0, NivelConfianza.ALTA, nombre_generico
            )
            triggers.append(
                self._crear_trigger(
                    empresa,
                    tier,
                    nivel,
                    ronda.titular_evidencia,
                    entradas,
                    "Ronda de inversión / capital",
                )
            )

        liderazgo = verificacion.nuevo_liderazgo_tecnico
        if liderazgo.detectado:
            tier, nivel = self._cap_generico(
                TierUrgencia.TIER_1, NivelConfianza.ALTA, nombre_generico
            )
            cargo = liderazgo.cargo or "cargo técnico C-Level"
            triggers.append(
                self._crear_trigger(
                    empresa,
                    tier,
                    nivel,
                    liderazgo.titular_evidencia,
                    entradas,
                    f"Nuevo liderazgo técnico ({cargo})",
                )
            )

        ma = verificacion.fusion_o_adquisicion
        if ma.detectado:
            tier, nivel = self._cap_generico(
                TierUrgencia.TIER_2, NivelConfianza.MEDIA, nombre_generico
            )
            triggers.append(
                self._crear_trigger(
                    empresa,
                    tier,
                    nivel,
                    ma.titular_evidencia,
                    entradas,
                    "Fusión o adquisición",
                )
            )

        return triggers

    @staticmethod
    def _cap_generico(
        tier: TierUrgencia, nivel: NivelConfianza, nombre_generico: bool
    ) -> tuple[TierUrgencia, NivelConfianza]:
        """
        Cap por nombre corto/genérico (≤8 chars): aunque el LLM detecte el
        evento, un nombre corto NUNCA supera TIER_2 (riesgo de homónimo). Se
        rebaja también el nivel de confianza ALTA→MEDIA en ese caso.
        """
        if not nombre_generico:
            return tier, nivel
        if tier in (TierUrgencia.TIER_0, TierUrgencia.TIER_1):
            tier = TierUrgencia.TIER_2
        if nivel == NivelConfianza.ALTA:
            nivel = NivelConfianza.MEDIA
        return tier, nivel

    def _crear_trigger(
        self,
        empresa: Empresa,
        tier: TierUrgencia,
        nivel: NivelConfianza,
        titular_evidencia: str | None,
        entradas: list[_EntradaRSS],
        etiqueta: str,
    ) -> Trigger:
        titular = (titular_evidencia or "").strip()
        fecha = self._fecha_para_evidencia(titular, entradas)
        titular_mostrar = titular or (entradas[0].titulo if entradas else etiqueta)
        if len(titular_mostrar) > 120:
            titular_mostrar = titular_mostrar[:120] + "..."
        enlace = self._enlace_para_evidencia(titular, entradas)
        descripcion = (
            f"[GA] {etiqueta} (verificado por análisis semántico): "
            f"'{titular_mostrar}' — Fuente: {enlace or 'RSS'}"
        )
        return Trigger(
            empresa_id=empresa.id,
            origen=OrigenTrigger.GOOGLE_ALERTS,
            nivel_confianza=nivel,
            descripcion=descripcion,
            fecha_evento=fecha,
            tipo_trigger=TipoTrigger.CAUSA,
            tier_urgencia=tier,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Degradación con gracia (modo contexto-débil)
    # ──────────────────────────────────────────────────────────────────────
    def _degradar_a_mencion(
        self, empresa: Empresa, entradas: list[_EntradaRSS]
    ) -> list[Trigger]:
        """
        Genera a lo sumo UN trigger TIER_3 / EFECTO / BAJA de "mención en
        medios". Aporta 0 al score de ScoreTriggerPolicy (TIER_3 = 0 puntos),
        pero deja trazabilidad y cuenta para el bonus multi-origen SOLO si
        existe además otra señal real de otro origen. NUNCA infla a TIER_0/1.
        """
        if not entradas:
            return []
        entrada = entradas[0]
        titulo = entrada.titulo
        if len(titulo) > 120:
            titulo = titulo[:120] + "..."
        descripcion = (
            f"[GA] Mención en medios (contexto débil, sin evento verificado): "
            f"'{titulo}' — Fuente: {entrada.enlace or 'RSS'}"
        )
        trigger = Trigger(
            empresa_id=empresa.id,
            origen=OrigenTrigger.GOOGLE_ALERTS,
            nivel_confianza=NivelConfianza.BAJA,
            descripcion=descripcion,
            fecha_evento=entrada.fecha,
            tipo_trigger=TipoTrigger.EFECTO,
            tier_urgencia=TierUrgencia.TIER_3,
        )
        return [trigger]

    # ──────────────────────────────────────────────────────────────────────
    # Emparejar la evidencia del LLM con la entrada RSS (para fecha/enlace)
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _entrada_para_evidencia(
        titular: str, entradas: list[_EntradaRSS]
    ) -> _EntradaRSS | None:
        """
        Encuentra la entrada RSS cuyo título mejor coincide con el titular de
        evidencia devuelto por el LLM (co-ocurrencia por subcadena en
        cualquier dirección). Si no hay match, retorna None.
        """
        if not titular:
            return None
        titular_lower = titular.lower()
        for e in entradas:
            titulo_lower = e.titulo.lower()
            if titulo_lower and (
                titulo_lower in titular_lower or titular_lower in titulo_lower
            ):
                return e
        return None

    @classmethod
    def _fecha_para_evidencia(
        cls, titular: str, entradas: list[_EntradaRSS]
    ) -> datetime | None:
        """fecha_evento = fecha de la entrada RSS de evidencia si existe; si no, None."""
        entrada = cls._entrada_para_evidencia(titular, entradas)
        return entrada.fecha if entrada is not None else None

    @classmethod
    def _enlace_para_evidencia(cls, titular: str, entradas: list[_EntradaRSS]) -> str:
        entrada = cls._entrada_para_evidencia(titular, entradas)
        return entrada.enlace if entrada is not None else ""
