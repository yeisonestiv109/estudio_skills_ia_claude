"""
╔══════════════════════════════════════════════════════════════════╗
║   EL PROSPECTOR — Simulador de Descubrimiento + Triangulación    ║
║   Motor 1 (Groq ICP) + Motor 2 (TheirStack + Google + Wappalyzer)║
╚══════════════════════════════════════════════════════════════════╝

Flujo completo:
    1. Motor 1 (GroqICPAdapter)   → ManifiestoICP
    2. Motor 2A (TheirStack)      → descubrir_empresas()
    3. Motor 2B (TheirStack)      → obtener_triggers() por empresa
    4. Motor 2C (Google News RSS) → obtener_triggers() por empresa
    5. Motor 2D (Wappalyzer)      → obtener_triggers() por empresa
    6. TriggerAggregationPolicy   → ¿califica para Motor 3?

Uso:
    .venv\\Scripts\\python.exe sandbox_motor_2_auto.py

Requisitos en .env:
    GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxx        (obligatorio)
    THEIRSTACK_API_KEY=ts_xxxxxxxxxxxxxxxxxx   (opcional — discovery)
"""
from __future__ import annotations

import os
import sys
from urllib.parse import quote_plus

if sys.platform == "win32":
    os.system("")


# ── Helpers ANSI ──────────────────────────────────────────────────────────
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

def verde(t: str) -> str:    return _c("92", t)
def amarillo(t: str) -> str: return _c("33", t)
def rojo(t: str) -> str:     return _c("91", t)
def cian(t: str) -> str:     return _c("96", t)
def negrita(t: str) -> str:  return _c("1",  t)
def gris(t: str) -> str:     return _c("90", t)
def azul(t: str) -> str:     return _c("94", t)
def magenta(t: str) -> str:  return _c("95", t)

SEP  = gris("─" * 64)
SEP2 = gris("· " * 32)

# ── Carga de entorno ──────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv no instalado. Ejecuta: .venv\\Scripts\\pip install python-dotenv")
    sys.exit(1)

load_dotenv()

# ── Imports del proyecto ──────────────────────────────────────────────────
from src.adapters.llm.groq_adapter import GroqICPAdapter
from src.adapters.llm.groq_key_pool import GroqKeyPool
from src.adapters.triggers.github_adapter import GitHubAdapter
from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter
from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter
from src.core.domain.models import Empresa, EstadoEmpresa, ManifiestoICP, OrigenTrigger, Trigger
from src.core.domain.policies import TriggerAggregationPolicy, AdapterRoutingPolicy

BANNER = f"""
{cian('╔══════════════════════════════════════════════════════════════════╗')}
{cian('║')}  {negrita('EL PROSPECTOR')} — Motor 2 Absoluto (5 Fuentes)              {cian('║')}
{cian('║')}  {azul('TheirStack')} + {verde('Google News')} + {magenta('Wappalyzer')} + {amarillo('SECOP')} + {cian('GitHub')}      {cian('║')}
{cian('╚══════════════════════════════════════════════════════════════════╝')}
"""

# ── Helpers de presentación ───────────────────────────────────────────────

def _nivel_color(nivel_str: str) -> str:
    from src.core.domain.models import NivelConfianza
    colors = {
        NivelConfianza.ALTA.value:  verde,
        NivelConfianza.MEDIA.value: amarillo,
        NivelConfianza.BAJA.value:  gris,
    }
    fn = colors.get(nivel_str, gris)
    return fn(nivel_str)


# Tokens de sufijo legal (Colombia + comunes) que se quitan del nombre para
# obtener la MARCA. La noticia de funding usa la marca ("Aló Credit"), no el
# nombre legal completo ("Aló Credit Colombia S.A.S"), así que buscar por el
# nombre legal exacto perdía las noticias (hallazgo corrida #4, 26-jul-2026).
_TOKENS_LEGALES = {
    "sas", "s.a.s", "s.a.s.", "sa", "s.a", "s.a.", "ltda", "ltda.",
    "esp", "e.s.p", "e.s.p.", "eu", "e.u", "e.u.", "inc", "inc.",
    "corp", "corp.", "sca", "s.c.a", "s.c.a.", "cia", "cía", "cia.",
}

# Términos de EVENTO de negocio (funding / liderazgo / M&A) para la búsqueda
# enfocada en Google News. Alineados con lo que el LLM del GoogleAlertsRSSAdapter
# ya verifica (ronda→TIER_0/CAUSA, liderazgo→TIER_1, M&A→TIER_2). También se
# pasan como palabras_clave_extra para que el pre-filtro deje pasar las entradas
# de evento aunque no contengan el nombre legal exacto (el LLM verifica luego).
_KEYWORDS_EVENTOS_NEGOCIO = [
    "inversión", "inversion", "financiación", "financiacion", "ronda",
    "levanta capital", "capital", "adquisición", "adquisicion", "fusión",
    "fusion", "funding", "nuevo cto", "nuevo cio", "director de tecnología",
    "vicepresidente de tecnología",
]


def _marca_desde_nombre(nombre_empresa: str) -> str:
    """
    Quita sufijos legales del final del nombre para obtener la marca buscable.
    "Aló Credit Colombia S.A.S" -> "Aló Credit Colombia".
    Si al quitarlos queda vacío, retorna el nombre original (fallback seguro).
    """
    tokens_norm = {t.strip(".") for t in _TOKENS_LEGALES}
    palabras = nombre_empresa.split()
    while palabras and palabras[-1].lower().strip(".,&") in tokens_norm:
        palabras.pop()
    return " ".join(palabras).strip(" .,-&") or nombre_empresa


def construir_rss_google_news(nombre_empresa: str, pais: str = "CO") -> str:
    """Feed general de noticias de la empresa (por marca, más recall que el
    nombre legal completo)."""
    marca = _marca_desde_nombre(nombre_empresa)
    query = quote_plus(f'"{marca}"')
    return f"https://news.google.com/rss/search?q={query}&hl=es-419&gl={pais}&ceid={pais}:es-419"


def construir_rss_eventos(nombre_empresa: str, pais: str = "CO") -> str:
    """
    Feed ENFOCADO en eventos de alto valor (funding, liderazgo técnico, M&A)
    de la empresa. Un funding round es de los triggers B2B más fuertes (capital
    fresco → nuevas contrataciones/herramientas = ganar/ahorrar). Reutiliza el
    adaptador y el LLM que YA existen; solo cambia la consulta que los alimenta.
    """
    marca = _marca_desde_nombre(nombre_empresa)
    terminos = (
        '(inversión OR financiación OR ronda OR "levanta capital" OR '
        'adquisición OR fusión OR "nuevo CTO" OR "director de tecnología")'
    )
    query = quote_plus(f'"{marca}" {terminos}')
    return f"https://news.google.com/rss/search?q={query}&hl=es-419&gl={pais}&ceid={pais}:es-419"


# ── Paso 1: Motor 1 ────────────────────────────────────────────────────────
def ejecutar_motor_1(adaptador: GroqICPAdapter, descripcion: str) -> ManifiestoICP | None:
    print(f"\n{SEP}")
    print(f"  {gris('Motor 1 — Analizando ICP con Groq...')}")
    try:
        manifiesto = adaptador.analizar(descripcion)
    except ValueError as exc:
        print(f"\n  {amarillo('⚠  Necesito más información:')}\n")
        for linea in str(exc).splitlines():
            print(f"    {amarillo(linea)}")
        print()
        return None
    except Exception as exc:
        print(f"\n  {rojo(f'✗  Error en Groq: {exc}')}\n")
        return None

    print(f"\n  {verde('✅  ManifiestoICP generado:')}")
    print(f"    {negrita('Categoría:')}    {manifiesto.categoria_empresa.value}")
    print(f"    {negrita('Tecnologías:')}  {', '.join(manifiesto.anclaje_tecnologico)}")
    print(f"    {negrita('Vertical:')}     {manifiesto.vertical}")
    industrias = ", ".join(manifiesto.industrias_objetivo) if manifiesto.industrias_objetivo else "(vacío → discovery amplio por tech+tamaño+país)"
    print(f"    {negrita('Industrias objetivo (compradoras):')} {industrias}")
    print(f"    {negrita('Tamaño ICP:')}   {manifiesto.tamano_empresa.value}")
    print(f"    {negrita('Geografía:')}    {manifiesto.geografia or 'no especificada'}")
    return manifiesto


# ── Paso 2A: Motor 2 — Discovery TheirStack ────────────────────────────────
def ejecutar_discovery(manifiesto: ManifiestoICP, adapter_ts: TheirStackAdapter) -> list[Empresa]:
    print(f"\n{SEP}")
    print(f"\n  {azul('🔍  Motor 2A — Buscando empresas nuevas (TheirStack)...')}")
    empresas = adapter_ts.descubrir_empresas(manifiesto)
    if not empresas:
        print(f"  {amarillo('Sin resultados. Verifica THEIRSTACK_API_KEY o ajusta el ICP.')}")
    else:
        print(f"  {verde(f'✓ {len(empresas)} empresa(s) candidata(s) descubierta(s).')}\n")
    return empresas


# ── Paso 2B-D: Recolectar triggers de los 3 adaptadores por empresa ────────
def recolectar_triggers(
    empresa: Empresa,
    adapter_ts: TheirStackAdapter,
    manifiesto: ManifiestoICP,
    adaptadores_activos: list,
    key_pool_groq: GroqKeyPool | None = None,
) -> list[Trigger]:
    """
    Ejecuta los 5 adaptadores del Motor 2 según lo habilitado por el Enrutador.

    key_pool_groq: GroqKeyPool COMPARTIDO para la verificación semántica del
    GoogleAlertsRSSAdapter (mismo pool que PropuestaValorAdapter, para no
    duplicar pools ni el estado de cooldown de failover). Si es None, el
    adaptador construye su propio GroqKeyPool() por defecto.
    """
    todos_triggers: list[Trigger] = []

    # TheirStack — scoring (hiring: vacante técnica vieja-y-abierta)
    if OrigenTrigger.THEIRSTACK in adaptadores_activos:
        try:
            todos_triggers.extend(adapter_ts.obtener_triggers(empresa))
        except Exception:
            pass

    # Google News RSS — dinámico por nombre de empresa.
    # DOS feeds (fix 26-jul-2026): (1) uno ENFOCADO en eventos de alto valor
    # (funding/liderazgo/M&A), primero para que sus entradas tengan prioridad en
    # el top-5 que ve el LLM; (2) el general. Ambos por MARCA (no nombre legal),
    # que es como aparece la empresa en las noticias de funding. Las keywords de
    # evento se pasan al pre-filtro para que esas entradas pasen aunque no
    # contengan el nombre legal exacto (el LLM verifica que sean de la empresa).
    if OrigenTrigger.GOOGLE_ALERTS in adaptadores_activos:
        try:
            rss_eventos = construir_rss_eventos(empresa.nombre, empresa.pais)
            rss_general = construir_rss_google_news(empresa.nombre, empresa.pais)
            adapter_ga = GoogleAlertsRSSAdapter(
                rss_urls=[rss_eventos, rss_general],
                palabras_clave_extra=(
                    manifiesto.anclaje_tecnologico + _KEYWORDS_EVENTOS_NEGOCIO
                ),
                key_pool=key_pool_groq,
            )
            todos_triggers.extend(adapter_ga.obtener_triggers(empresa))
        except Exception:
            pass

    # Wappalyzer — inspección de headers/HTML
    if OrigenTrigger.WAPPALYZER in adaptadores_activos:
        try:
            adapter_wapp = WappalyzerHeadlessAdapter(
                tecnologias_objetivo=manifiesto.anclaje_tecnologico,
            )
            todos_triggers.extend(adapter_wapp.obtener_triggers(empresa))
        except Exception:
            pass

    # SECOP — contratos gubernamentales (solo si gov-facing)
    if OrigenTrigger.SECOP_SOCRATA in adaptadores_activos:
        try:
            adapter_secop = SecopSocrataAdapter()
            todos_triggers.extend(adapter_secop.obtener_triggers(empresa))
        except Exception:
            pass

    # GitHub — actividad de código / repos públicos
    if OrigenTrigger.GITHUB in adaptadores_activos:
        try:
            adapter_gh = GitHubAdapter(
                tecnologias_objetivo=manifiesto.anclaje_tecnologico,
            )
            todos_triggers.extend(adapter_gh.obtener_triggers(empresa))
        except Exception:
            pass

    return todos_triggers


# ── Presentación de resultados por empresa ─────────────────────────────────
def imprimir_resultado_empresa(
    idx: int,
    empresa: Empresa,
    triggers: list[Trigger],
    califica: bool,
) -> None:
    from src.core.domain.models import OrigenTrigger

    estado_label = magenta("DESCUBIERTA") if empresa.estado == EstadoEmpresa.DESCUBIERTA else verde("VERIFICADA")
    califica_label = verde("✅ CALIFICA → Motor 3") if califica else gris("✗  Sin señales suficientes")

    print(f"  {negrita(f'{idx:02d}.')}  {negrita(empresa.nombre)}")
    print(f"       {gris('Dominio:')}   {cian(empresa.dominio)}")
    print(f"       {gris('Estado:')}    {estado_label}  |  {gris('Tamaño:')} {empresa.tamano.value}")
    print(f"       {gris('Veredicto:')} {califica_label}")

    if triggers:
        origen_icons = {
            OrigenTrigger.THEIRSTACK:    azul("TS"),
            OrigenTrigger.GOOGLE_ALERTS: verde("GA"),
            OrigenTrigger.WAPPALYZER:    magenta("WA"),
            OrigenTrigger.SECOP_SOCRATA: amarillo("SC"),
            OrigenTrigger.GITHUB:        cian("GH"),
        }
        print(f"       {gris('Triggers:')}")
        for t in triggers:
            icono = origen_icons.get(t.origen, gris("?"))
            nivel = _nivel_color(t.nivel_confianza.value)
            # Mostrar el TIER explícito (TIER_0 = sangrado activo) y NO truncar
            # antes del dato de aging (iba al final de la descripción y se perdía).
            tier = t.tier_urgencia.value
            tier_col = verde(tier) if tier == "TIER_0" else (amarillo(tier) if tier == "TIER_1" else gris(tier))
            desc_corta = t.descripcion if len(t.descripcion) <= 150 else t.descripcion[:150] + "..."
            print(f"         [{icono}] {nivel:6s} {tier_col}  {gris(desc_corta)}")
    else:
        print(f"       {gris('Triggers:   —  ninguno detectado')}")
    print()


# ── Main ───────────────────────────────────────────────────────────────────
def main() -> None:
    print(BANNER)

    # Inicializar Motor 1
    try:
        adaptador_icp = GroqICPAdapter()
    except ValueError as exc:
        print(f"\n{rojo('ERROR — Motor 1:')}")
        print(f"  {rojo(str(exc))}")
        print(f"\n  Agrega en {amarillo('.env')}: {amarillo('GROQ_API_KEY=gsk_xxx')}")
        print(f"  Obtén tu clave gratis: {cian('https://console.groq.com/keys')}\n")
        sys.exit(1)

    theirstack_key = os.getenv("THEIRSTACK_API_KEY")
    if not theirstack_key:
        print(f"\n{amarillo('AVISO — THEIRSTACK_API_KEY no configurada.')}")
        print(f"  El discovery retornará lista vacía.")
        print(f"  Agrega en {amarillo('.env')}: {amarillo('THEIRSTACK_API_KEY=ts_xxx')}\n")

    print(f"  {verde('✓')} Motor 1 (Groq) inicializado.")
    print(f"  {verde('✓')} Motor 2 — {azul('TheirStack')} + {verde('Google News')} + {magenta('Wappalyzer')} + {amarillo('SECOP')} + {cian('GitHub')} listos.")
    print(f"\n  {gris('Describe tu ICP (texto libre):')}")
    ejemplo = 'Ej: "SaaS colombiano gov-facing con monolito Django"'
    print(f"  {gris(ejemplo)}\n")

    # Input del usuario
    try:
        descripcion = input(
            f"{cian('▶')} {negrita('Describe tu ICP')} {gris('[Ctrl+C para cancelar]')}: "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {gris('Cancelado.')}\n")
        sys.exit(0)

    if not descripcion:
        print(f"\n  {amarillo('Descripción vacía.')}\n")
        sys.exit(1)

    # Motor 1
    manifiesto = ejecutar_motor_1(adaptador_icp, descripcion)
    if manifiesto is None:
        sys.exit(1)

    # Mostrar adaptadores activos según la AdapterRoutingPolicy
    routing = AdapterRoutingPolicy()
    adaptadores_activos = routing.resolver(manifiesto)
    nombres_activos = [o.value for o in adaptadores_activos]
    print(f"\n  {negrita('🤖  Adaptadores activados:')} {', '.join(amarillo(n) for n in nombres_activos)}\n")

    # Motor 2A — Discovery
    adapter_ts = TheirStackAdapter(
        api_key=theirstack_key,
        tecnologias_objetivo=manifiesto.anclaje_tecnologico,
    )
    empresas = ejecutar_discovery(manifiesto, adapter_ts)

    if not empresas:
        print(f"\n{SEP}\n")
        print(f"  {amarillo('No hay empresas para analizar.')}")
        ejemplo = 'Verifica THEIRSTACK_API_KEY y la disponibilidad del ICP.\n'
        print(f"  {gris(ejemplo)}\n")

        sys.exit(0)

    # Motor 2B-D + Política de Agregación
    policy = TriggerAggregationPolicy()
    print(f"\n{SEP}")
    print(f"\n  {negrita('Recolectando y triangulando señales por empresa...')}\n")
    print(f"{SEP2}\n")

    empresas_calificadas = 0

    # Pool de claves Groq COMPARTIDO por todas las empresas para la
    # verificación semántica de Google Alerts (evita construir un pool por
    # empresa y comparte el estado de cooldown de failover entre llamadas).
    key_pool_groq = GroqKeyPool()

    for idx, empresa in enumerate(empresas, start=1):
        triggers = recolectar_triggers(
            empresa, adapter_ts, manifiesto, adaptadores_activos, key_pool_groq
        )
        califica = policy.evaluar(triggers, adaptadores_activos)
        if califica:
            empresas_calificadas += 1
        imprimir_resultado_empresa(idx, empresa, triggers, califica)

    # Resumen final
    print(f"{SEP}")
    print(f"\n  {negrita('Resumen del pipeline:')}")
    print(f"    {verde('✓')} Empresas descubiertas:  {negrita(str(len(empresas)))}")
    print(f"    {verde('✓')} Califican para Motor 3: {negrita(str(empresas_calificadas))}")
    print(f"    {gris('Tecnologías buscadas:    ')}{', '.join(manifiesto.anclaje_tecnologico)}")
    print(f"\n  {gris('Próximo paso: Motor 3 — enriquecer contactos (Apollo + Hunter)')}\n")


if __name__ == "__main__":
    main()
