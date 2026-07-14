"""
╔══════════════════════════════════════════════════════════════╗
║         EL PROSPECTOR — Simulador Interactivo Motor 1        ║
║          Prueba End-to-End del GroqICPAdapter en vivo         ║
╚══════════════════════════════════════════════════════════════╝

Uso:
    .venv\\Scripts\\python.exe sandbox_motor1.py

Requisito previo:
    Agrega tu API key de Groq en el archivo .env:
        GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxx
"""
from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Activar soporte ANSI en Windows (PowerShell/CMD moderno)
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    os.system("")  # Habilita secuencias de escape ANSI en la consola de Windows


# ---------------------------------------------------------------------------
# Helpers de color ANSI (degradan a texto plano si no hay TTY)
# ---------------------------------------------------------------------------
def _c(code: str, text: str) -> str:
    """Envuelve `text` con el código ANSI `code` si stdout es un terminal."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def verde(t: str) -> str:
    return _c("92", t)


def amarillo(t: str) -> str:
    return _c("33", t)


def rojo(t: str) -> str:
    return _c("91", t)


def cian(t: str) -> str:
    return _c("96", t)


def negrita(t: str) -> str:
    return _c("1", t)


def gris(t: str) -> str:
    return _c("90", t)


# ---------------------------------------------------------------------------
# Carga de variables de entorno (.env) ANTES de cualquier import del proyecto
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
except ImportError:
    print(rojo("ERROR: python-dotenv no está instalado."))
    print("Ejecuta: .venv\\Scripts\\pip install python-dotenv")
    sys.exit(1)

load_dotenv()

# ---------------------------------------------------------------------------
# Imports del proyecto (después de cargar .env)
# ---------------------------------------------------------------------------
from src.adapters.llm.groq_adapter import GroqICPAdapter
from src.core.domain.policies import AdapterRoutingPolicy


# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------
SEPARADOR = gris("─" * 62)
BANNER = f"""
{cian('╔══════════════════════════════════════════════════════════════╗')}
{cian('║')}    {negrita('EL PROSPECTOR')} — Motor 1: Analizador ICP + Enrutador      {cian('║')}
{cian('║')}    Modelo: {amarillo('llama-3.3-70b-versatile')} (Groq)                  {cian('║')}
{cian('╚══════════════════════════════════════════════════════════════╝')}
"""


def imprimir_manifiesto_y_rutas(adaptador: GroqICPAdapter, descripcion: str) -> None:
    """Ejecuta el análisis y muestra el resultado o las preguntas de clarificación."""
    print(f"\n{SEPARADOR}")
    print(gris("  Analizando con Groq..."))

    try:
        manifiesto = adaptador.analizar(descripcion)
    except ValueError as exc:
        # El adaptador cumplió su contrato: retorna preguntas de clarificación
        print(f"\n  {amarillo('⚠  Necesito más información para calificar este ICP:')}\n")
        for linea in str(exc).splitlines():
            print(f"    {amarillo(linea)}")
        print()
        return
    except Exception as exc:
        print(f"\n  {rojo('✗  Error inesperado en la API de Groq:')}")
        print(f"    {rojo(str(exc))}")
        print(f"  {gris('Comprueba tu GROQ_API_KEY y tu conexión a internet.')}\n")
        return

    # ── Éxito: mostrar el ManifiestoICP completo ───────────────────────────
    print(f"\n  {verde('✅  MANIFIESTO ICP GENERADO CON ÉXITO')}\n")
    print(manifiesto.model_dump_json(indent=2))

    # ── Enrutamiento: calcular y mostrar adaptadores activos ───────────────
    routing = AdapterRoutingPolicy()
    adaptadores_activos = routing.resolver(manifiesto)

    nombres = [o.value for o in adaptadores_activos]
    print(f"\n{SEPARADOR}")
    print(f"\n  {negrita('🤖  Motores de búsqueda activados para este ICP:')}\n")
    for nombre in nombres:
        print(f"    {verde('▶')}  {negrita(nombre)}")

    print(f"\n  {gris('(Estos son los adaptadores que el Motor 2 ejecutará en paralelo)')}")
    print(f"\n{SEPARADOR}\n")


def main() -> None:
    print(BANNER)

    # ── Inicializar el adaptador (falla rápido si falta la API key) ─────────
    try:
        adaptador = GroqICPAdapter()
    except ValueError as exc:
        print(f"\n{rojo('ERROR DE CONFIGURACIÓN:')}")
        print(f"  {rojo(str(exc))}")
        print(f"\n  Pasos para resolverlo:")
        print(f"  1. Abre el archivo {amarillo('.env')} en la raíz del proyecto.")
        print(f"  2. Agrega tu clave: {amarillo('GROQ_API_KEY=gsk_xxxxxxxxx')}")
        print(f"  3. Obtén tu clave gratis en: {cian('https://console.groq.com/keys')}\n")
        sys.exit(1)

    print(f"  {verde('✓')} Adaptador listo. Modelo: {amarillo(GroqICPAdapter.MODEL)}")
    print(f"  {verde('✓')} API Key cargada desde .env")
    print(f"\n  {gris('Escribe una descripción de tu cliente ideal en lenguaje natural.')}")
    print(f"  {gris('Ejemplo: \"Busco empresas SaaS colombianas con 100-500 empleados')}")
    print(f"  {gris('          que tengan deuda técnica en backend Python y busquen')}")
    print(f"  {gris('          arquitectos para escalar su plataforma.\"')}")
    print(f"\n  {gris('Escribe \"salir\" o presiona Ctrl+C para terminar.')}\n")

    # ── Bucle interactivo ────────────────────────────────────────────────────
    while True:
        try:
            descripcion = input(
                f"{cian('▶')} {negrita('Describe tu ICP')} {gris('[salir para terminar]')}: "
            ).strip()
        except KeyboardInterrupt:
            print(f"\n\n  {gris('Sesión terminada. ¡Hasta pronto!')}\n")
            break
        except EOFError:
            break

        if not descripcion:
            print(f"  {amarillo('La descripción no puede estar vacía. Inténtalo de nuevo.')}\n")
            continue

        if descripcion.lower() in {"salir", "exit", "quit", "q"}:
            print(f"\n  {gris('Sesión terminada. ¡Hasta pronto!')}\n")
            break

        imprimir_manifiesto_y_rutas(adaptador, descripcion)


if __name__ == "__main__":
    main()
