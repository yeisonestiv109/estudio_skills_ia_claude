"""
╔══════════════════════════════════════════════════════════════════╗
║   EL PROSPECTOR — Sandbox Motor 4 (Outbound RAG)                 ║
║   Selección → Tavily (RAG) → Groq (Redacción) → Resend (Envío)  ║
╚══════════════════════════════════════════════════════════════════╝

Propósito (ver `10-Memoria_Consolidada/tecnico/prospector-m4-design.md`):
    Composition Root del Motor 4. Simula la salida real del piloto de M3 (los
    8 decisores aptos, incluidos los 4 VPs + 1 CTO de Rappi) y ejecuta el flujo
    completo: PoliticaSeleccionMejorDecisor (desduplicación) → PuertoContextoRAG
    (Tavily) → PuertoRedactorOutbound (Groq) → Modo Borrador (HITL) →
    PuertoEnvioCorreo (Resend).

    Este script NO implementa el webhook de rebotes (fuera de alcance, ver
    §6 de la spec): es deliberadamente SÍNCRONO. El resultado que Resend
    retorna aquí es la aproximación optimista "aceptado para entrega", no la
    confirmación real de entregabilidad — esa llega después, de forma
    asíncrona, vía el webhook que se construirá en otra fase.

⚠️  ADVERTENCIA DE EFECTOS REALES E IRREVERSIBLES:
    Si el usuario aprueba explícitamente al final, este script ENVÍA CORREOS
    REALES a personas reales (los decisores de la muestra) a través de la
    API de Resend, y CONSUME CRÉDITOS REALES de Tavily y Groq incluso si el
    usuario cancela el envío final (el RAG y la redacción ya ocurrieron antes
    de esa pregunta). No es una simulación.

Uso:
    .venv\\Scripts\\python.exe sandbox_motor_4_outbound.py

Requisitos en .env:
    TAVILY_API_KEY=xxxxxxxxxxxxxxxx   (obligatorio — sin esto, contexto vacío)
    GROQ_API_KEY=xxxxxxxxxxxxxxxx     (obligatorio — sin esto, ERROR_REDACCION)
    RESEND_API_KEY=xxxxxxxxxxxxxxxx   (obligatorio solo si se aprueba el envío)
    RESEND_REMITENTE=tu_dominio_verificado@ejemplo.com  (opcional)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

if sys.platform == "win32":
    os.system("")


# ── Helpers ANSI ──────────────────────────────────────────────────────────
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


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


def azul(t: str) -> str:
    return _c("94", t)


def magenta(t: str) -> str:
    return _c("95", t)


def rojo_fondo(t: str) -> str:
    return _c("97;41", t)


SEP = gris("─" * 68)
SEP2 = gris("· " * 34)

# ── Carga de entorno ──────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv no instalado. Ejecuta: .venv\\Scripts\\pip install python-dotenv")
    sys.exit(1)

load_dotenv()

# ── Imports del proyecto ──────────────────────────────────────────────────
from src.adapters.outbound.groq_redactor_adapter import GroqRedactorAdapter
from src.adapters.outbound.resend_envio_adapter import ResendEnvioAdapter
from src.adapters.outbound.tavily_contexto_adapter import TavilyContextoAdapter
from src.core.domain.models import (
    AutoridadDecision,
    BaseLegal,
    CategoriaEmpresa,
    ContextoRAG,
    Decisor,
    Empresa,
    EstadoMensaje,
    ManifiestoICP,
    Mensaje,
    NivelConfianza,
    OrigenTrigger,
    ProspectoCalificado,
    ResultadoEnvio,
    Seniority,
    TamanoEmpresa,
    Trigger,
)
from src.core.domain.policies import PoliticaSeleccionMejorDecisor

BANNER = f"""
{cian('╔══════════════════════════════════════════════════════════════════╗')}
{cian('║')}  {negrita('EL PROSPECTOR')} — Sandbox Motor 4 (Outbound RAG)                {cian('║')}
{cian('║')}  {azul('Selección')} → {verde('Tavily')} → {magenta('Groq')} → {amarillo('Modo Borrador')} → {rojo('Resend')}          {cian('║')}
{cian('╚══════════════════════════════════════════════════════════════════╝')}
"""


# ---------------------------------------------------------------------------
# Paso 0: Input simulado — "los 8 del piloto" (incluye los 5 de Rappi)
# ---------------------------------------------------------------------------
def construir_prospectos_del_piloto() -> list[ProspectoCalificado]:
    """
    Reproduce la salida real del piloto de M3: Rappi con 4 VPs + 1 CTO
    (el caso que motivó PoliticaSeleccionMejorDecisor) y Platzi con su CTO.
    Cada ProspectoCalificado empaqueta la Empresa + un Trigger ficticio +
    el ManifiestoICP, tal como lo definió el contrato de transición M2→M3.
    """
    ahora = datetime.now(timezone.utc)

    def _manifiesto(vertical: str, tamano: TamanoEmpresa) -> ManifiestoICP:
        return ManifiestoICP(
            pain_es_accionable=False,
            anclaje_tecnologico=["Amazon Web Services"],
            categoria_empresa=CategoriaEmpresa.SAAS_B2B_HORIZONTAL,
            vertical=vertical,
            cargos_decisores=["CTO", "VP Engineering"],
            tamano_empresa=tamano,
            geografia="CO",
            base_legal=BaseLegal.DATO_PUBLICO,
        )

    def _trigger(empresa_id, descripcion: str, dias_atras: int = 10) -> Trigger:
        return Trigger(
            empresa_id=empresa_id,
            origen=OrigenTrigger.THEIRSTACK,
            nivel_confianza=NivelConfianza.ALTA,
            descripcion=descripcion,
            fecha_evento=ahora - timedelta(days=dias_atras),
        )

    # --- Rappi: reproducción exacta del caso real del piloto (4 VPs + 1 CTO) ---
    rappi = Empresa(
        nombre="Rappi",
        dominio="rappi.com",
        tamano=TamanoEmpresa.ENTERPRISE,
        vertical="Delivery y Marketplace",
        pais="CO",
        ciudad="Bogotá",
    )
    rappi_decisores = [
        Decisor(
            empresa_id=rappi.id,
            nombre="Matias Salamone",
            cargo_original="VP of Engineering",
            cargo_normalizado="VP OF ENGINEERING",
            seniority=Seniority.VP,
            autoridad_decision=AutoridadDecision.DECISION_MAKER,
            correo="matias.salamone@example-rappi.com",
            confianza_dato=0.90,
        ),
        Decisor(
            empresa_id=rappi.id,
            nombre="Ignacio Lizaso",
            cargo_original="VP of Engineering",
            cargo_normalizado="VP OF ENGINEERING",
            seniority=Seniority.VP,
            autoridad_decision=AutoridadDecision.DECISION_MAKER,
            correo="ignacio.lizaso@example-rappi.com",
            confianza_dato=0.70,
        ),
        Decisor(
            empresa_id=rappi.id,
            nombre="Marcos Luna Huizzi",
            cargo_original="VP of Engineering",
            cargo_normalizado="VP OF ENGINEERING",
            seniority=Seniority.VP,
            autoridad_decision=AutoridadDecision.DECISION_MAKER,
            correo="marcos.luna@example-rappi.com",
            confianza_dato=0.90,
        ),
        Decisor(
            empresa_id=rappi.id,
            nombre="Pablo Dominguez",
            cargo_original="VP of Engineering & AI",
            cargo_normalizado="VP OF ENGINEERING & AI",
            seniority=Seniority.VP,
            autoridad_decision=AutoridadDecision.DECISION_MAKER,
            correo="pablo.dominguez@example-rappi.com",
            confianza_dato=0.90,
        ),
        Decisor(
            empresa_id=rappi.id,
            nombre="Leandro Reox",
            cargo_original="Chief Technology Officer",
            cargo_normalizado="CTO",
            seniority=Seniority.C_LEVEL,
            autoridad_decision=AutoridadDecision.DECISION_MAKER,
            correo="leandro.reox@example-rappi.com",
            confianza_dato=0.90,
        ),
    ]
    prospecto_rappi = ProspectoCalificado(
        empresa=rappi,
        triggers=[
            _trigger(rappi.id, "3 vacantes técnicas de backend abiertas hace 8 días", 8)
        ],
        manifiesto=_manifiesto("Delivery y Marketplace", TamanoEmpresa.ENTERPRISE),
    )

    # --- Platzi: caso simple, un solo decisor apto ---
    platzi = Empresa(
        nombre="Platzi",
        dominio="platzi.com",
        tamano=TamanoEmpresa.MID_MARKET,
        vertical="EdTech",
        pais="CO",
        ciudad="Bogotá",
    )
    platzi_decisores = [
        Decisor(
            empresa_id=platzi.id,
            nombre="Juan Pablo Rojas",
            cargo_original="CTO & CPO",
            cargo_normalizado="CTO & CPO",
            seniority=Seniority.C_LEVEL,
            autoridad_decision=AutoridadDecision.DECISION_MAKER,
            correo="yeisonestivendelgado109@gmail.com",
            confianza_dato=0.90,
        )
    ]
    prospecto_platzi = ProspectoCalificado(
        empresa=platzi,
        triggers=[
            _trigger(platzi.id, "Nuevo curso de IA lanzado, expansión de equipo técnico", 5)
        ],
        manifiesto=_manifiesto("EdTech", TamanoEmpresa.MID_MARKET),
    )

    return [
        (prospecto_rappi, rappi_decisores),
        (prospecto_platzi, platzi_decisores),
    ]  # type: ignore[return-value]  # devolvemos tuplas (prospecto, decisores_aptos) para este harness


# ---------------------------------------------------------------------------
# Paso 1: Desduplicación — PoliticaSeleccionMejorDecisor
# ---------------------------------------------------------------------------
def ejecutar_seleccion(
    pares: list[tuple[ProspectoCalificado, list[Decisor]]],
    politica: PoliticaSeleccionMejorDecisor,
) -> list[tuple[ProspectoCalificado, Decisor]]:
    print(f"\n{SEP}\n")
    print(f"  {negrita('Paso 1 — Desduplicación (PoliticaSeleccionMejorDecisor)')}\n")

    seleccionados: list[tuple[ProspectoCalificado, Decisor]] = []
    for prospecto, decisores in pares:
        empresa = prospecto.empresa
        elegido = politica.seleccionar(decisores)

        if elegido is None:
            print(f"  {amarillo(f'{empresa.nombre}: sin decisores. Omitida.')}")
            continue

        descartados = [d.nombre for d in decisores if d.id != elegido.id]
        if descartados:
            lista_descartados = ", ".join(descartados)
            texto_descartados = f'{len(descartados)} ({lista_descartados})'
            texto_cargo = f'({elegido.cargo_original})'
            print(
                f"  {negrita(empresa.nombre)}: descartando "
                f"{gris(texto_descartados)}, "
                f"{verde(f'seleccionando a {elegido.nombre}')} "
                f"{gris(texto_cargo)}"
            )

        else:
            print(
                f"  {negrita(empresa.nombre)}: único decisor disponible → "
                f"{verde(elegido.nombre)} {gris(f'({elegido.cargo_original})')}"
            )

        seleccionados.append((prospecto, elegido))

    print(
        f"\n  {gris(f'Total: {sum(len(d) for _, d in pares)} decisores de entrada')} "
        f"→ {verde(f'{len(seleccionados)} mensaje(s) a redactar')}\n"
    )
    return seleccionados


# ---------------------------------------------------------------------------
# Paso 2: RAG (Tavily) + Redacción (Groq)
# ---------------------------------------------------------------------------
def ejecutar_rag_y_redaccion(
    seleccionados: list[tuple[ProspectoCalificado, Decisor]],
    contexto_adapter: TavilyContextoAdapter,
    redactor_adapter: GroqRedactorAdapter,
) -> list[tuple[Decisor, Mensaje]]:
    print(f"{SEP}\n")
    print(f"  {negrita('Paso 2 — Contexto RAG (Tavily) + Redacción (Groq)')}\n")
    print(f"{SEP2}\n")

    borradores: list[tuple[Decisor, Mensaje]] = []
    for prospecto, decisor in seleccionados:
        empresa = prospecto.empresa
        triggers = prospecto.triggers

        print(f"  {negrita(empresa.nombre)} → {cian(decisor.nombre)} ({decisor.cargo_original})")

        try:
            contexto = contexto_adapter.obtener_contexto(empresa, triggers)
        except Exception as exc:
            print(f"       {rojo(f'✗  Error inesperado en Tavily: {exc}')}")
            contexto = ContextoRAG()

        n_evidencias = len(contexto.evidencias)
        print(f"       {gris(f'Tavily: {n_evidencias} evidencia(s) recuperada(s).')}")

        try:
            mensaje = redactor_adapter.redactar(decisor, empresa, triggers, contexto)
        except Exception as exc:
            print(f"       {rojo(f'✗  Error inesperado en Groq: {exc}')}")
            mensaje = Mensaje(
                decisor_id=decisor.id,
                asunto="[ERROR DE REDACCIÓN]",
                cuerpo="Error inesperado. Revisar manualmente.",
                estado=EstadoMensaje.ERROR_REDACCION,
            )

        if mensaje.estado == EstadoMensaje.ERROR_REDACCION:
            print(f"       {rojo('✗  ERROR_REDACCION — Groq no pudo generar el mensaje.')}\n")
        else:
            print(f"       {verde('✓  Borrador generado.')}\n")

        borradores.append((decisor, mensaje))

    return borradores


# ---------------------------------------------------------------------------
# Modo Borrador (frontera de reputación) — impresión de asunto/cuerpo
# ---------------------------------------------------------------------------
def imprimir_borradores(borradores: list[tuple[Decisor, Mensaje]]) -> None:
    print(f"{SEP}\n")
    print(f"  {negrita('📝  MODO BORRADOR — revisión humana antes de cualquier envío')}\n")
    print(f"{SEP2}\n")

    for decisor, mensaje in borradores:
        estado_color = amarillo if mensaje.estado == EstadoMensaje.BORRADOR else rojo
        print(f"  {negrita(f'Para: {decisor.nombre} <{decisor.correo}>')}")
        print(f"  {gris('Estado:')} {estado_color(mensaje.estado.value)}")
        print(f"  {negrita('Asunto:')} {mensaje.asunto}")
        print(f"  {negrita('Cuerpo:')}")
        for linea in mensaje.cuerpo.splitlines():
            print(f"    {gris(linea)}")
        if mensaje.fuentes_citadas:
            print(f"  {gris('Fuentes citadas:')} {', '.join(mensaje.fuentes_citadas)}")
        print()


# ---------------------------------------------------------------------------
# Frontera Legal y de Costo — confirmación bloqueante antes de enviar
# ---------------------------------------------------------------------------
def solicitar_aprobacion_envio(borradores: list[tuple[Decisor, Mensaje]]) -> bool:
    enviables = [
        (d, m) for d, m in borradores if m.estado == EstadoMensaje.BORRADOR
    ]

    print(f"{SEP}\n")
    print(f"  {rojo_fondo(negrita('  ⚠  ADVERTENCIA — ESTO ENVIARÁ CORREOS REALES  '))}")
    print(f"  {rojo_fondo('  A LAS PERSONAS LISTADAS A CONTINUACIÓN.                ')}\n")

    if not enviables:
        print(f"  {amarillo('No hay borradores en estado válido para enviar. Nada que aprobar.')}\n")
        return False

    for decisor, _ in enviables:
        print(f"    - {decisor.nombre} <{decisor.correo}>")

    print(
        f"\n  {gris('Este envío es real, vía Resend, y no se puede deshacer una vez despachado.')}"
    )
    print(
        f"  {gris('El resultado inicial (ENTREGADO) es una aproximación optimista;')}"
    )
    print(
        f"  {gris('el rebote real, si ocurre, llega después vía webhook (fuera de este sandbox).')}\n"
    )

    try:
        respuesta = input(
            f"{cian('▶')} Escribe {negrita('APROBAR_Y_ENVIAR')} para despachar vía Resend, "
            f"o presiona Enter para cancelar: "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {gris('Cancelado. Ningún correo fue enviado.')}\n")
        return False

    if respuesta != "APROBAR_Y_ENVIAR":
        print(f"\n  {gris('Confirmación no recibida. Ningún correo fue enviado.')}\n")
        return False

    return True


# ---------------------------------------------------------------------------
# Paso 3: Envío real vía Resend
# ---------------------------------------------------------------------------
def ejecutar_envio(
    borradores: list[tuple[Decisor, Mensaje]], envio_adapter: ResendEnvioAdapter
) -> None:
    print(f"\n{SEP}\n")
    print(f"  {negrita('Paso 3 — Despacho vía Resend')}\n")

    colores_resultado = {
        ResultadoEnvio.ENTREGADO: verde,
        ResultadoEnvio.REBOTADO: rojo,
        ResultadoEnvio.DIFERIDO: amarillo,
        ResultadoEnvio.RECHAZADO: rojo,
        ResultadoEnvio.ERROR: rojo,
    }

    for decisor, mensaje in borradores:
        if mensaje.estado != EstadoMensaje.BORRADOR:
            print(
                f"  {gris(f'{decisor.nombre}: omitido (estado {mensaje.estado.value}, no enviable).')}"
            )
            continue

        # Frontera de reputación: el mensaje pasa a APROBADO justo antes del
        # único puerto con efectos externos (PuertoEnvioCorreo).
        mensaje_aprobado = mensaje.model_copy(update={"estado": EstadoMensaje.APROBADO})

        try:
            resultado = envio_adapter.enviar(mensaje_aprobado, decisor)
        except Exception as exc:
            print(f"  {rojo(f'✗  Error inesperado enviando a {decisor.nombre}: {exc}')}")
            resultado = ResultadoEnvio.ERROR

        color_fn = colores_resultado.get(resultado, gris)
        print(f"  {decisor.nombre} <{decisor.correo}> → {color_fn(resultado.value)}")

        print(
            f"\n  {gris('Nota: el resultado ENTREGADO aquí es la respuesta síncrona de Resend')}"
        )
    
        msg_nota = '("aceptado para procesar"), no la confirmación final de entregabilidad.'
        print(f"  {gris(msg_nota)}")


        print(
            f"  {gris('El rebote real, si ocurre, se captura después vía webhook (no incluido).')}\n"
        )


# ---------------------------------------------------------------------------
# Main — Composition Root del Motor 4
# ---------------------------------------------------------------------------
def main() -> None:
    print(BANNER)

    tavily_key = os.getenv("TAVILY_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    resend_key = os.getenv("RESEND_API_KEY")

    faltantes = []
    if not tavily_key:
        faltantes.append("TAVILY_API_KEY")
    if not groq_key:
        faltantes.append("GROQ_API_KEY")
    if not resend_key:
        faltantes.append("RESEND_API_KEY")

    if faltantes:
        print(f"{amarillo('AVISO — faltan credenciales:')} {', '.join(faltantes)}")
        print(
            f"  {gris('Sin ellas, los adaptadores correspondientes degradan a resultado vacío/error')}"
        )
        print(f"  {gris('(contrato de error del Core: nunca lanzan excepción).')}\n")

    print(f"  {rojo(negrita('⚠  ADVERTENCIA DE EFECTOS REALES'))}")
    print(
        f"  {gris('Este script llama a las APIs reales de Tavily y Groq (consumo de créditos)')}"
    )
    print(
        f"  {gris('y, si se aprueba al final, envía correos reales vía Resend. No es una simulación.')}\n"
    )

    try:
        confirmacion_inicial = input(
            f"{cian('▶')} Escribe {negrita('CONFIRMO')} para iniciar (gasta créditos de Tavily/Groq) "
            f"{gris('[Ctrl+C para cancelar]')}: "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {gris('Cancelado. Ningún crédito fue consumido.')}\n")
        sys.exit(0)

    if confirmacion_inicial != "CONFIRMO":
        print(f"\n  {gris('Confirmación no recibida. Ningún crédito fue consumido.')}\n")
        sys.exit(0)

    # ── Composition Root: instanciar adaptadores concretos ──
    contexto_adapter = TavilyContextoAdapter(api_key=tavily_key)
    redactor_adapter = GroqRedactorAdapter(api_key=groq_key)
    envio_adapter = ResendEnvioAdapter(
        api_key=resend_key, remitente=os.getenv("RESEND_REMITENTE")
    )
    politica_seleccion = PoliticaSeleccionMejorDecisor()

    pares = construir_prospectos_del_piloto()

    seleccionados = ejecutar_seleccion(pares, politica_seleccion)
    if not seleccionados:
        print(f"{SEP}\n")
        print(f"  {amarillo('Nadie sobrevivió a la selección. Nada que redactar.')}\n")
        sys.exit(0)

    borradores = ejecutar_rag_y_redaccion(seleccionados, contexto_adapter, redactor_adapter)
    imprimir_borradores(borradores)

    aprobado = solicitar_aprobacion_envio(borradores)
    if not aprobado:
        print(f"{SEP}")
        print(f"\n  {gris('Sandbox finalizado en Modo Borrador. Ningún correo fue enviado.')}\n")
        sys.exit(0)

    ejecutar_envio(borradores, envio_adapter)

    print(f"{SEP}")
    print(f"\n  {verde('Sandbox del Motor 4 completado.')}\n")


if __name__ == "__main__":
    main()
