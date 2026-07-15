"""
╔══════════════════════════════════════════════════════════════════╗
║   EL PROSPECTOR — Piloto LATAM del Motor 3 (Composition Root)    ║
║   Cascada Apollo → Hunter · UmbralCalidadDecisor · KPI de piloto ║
╚══════════════════════════════════════════════════════════════════╝

Propósito (ver `10-Memoria_Consolidada/tecnico/prospector-m3-m4-design.md` §3.5):
    Este script es el harness del PILOTO CONTROLADO DE 100 EMPRESAS
    COLOMBIANAS exigido antes de escalar el Motor 3 a producción masiva.
    Ejecutado a pequeña escala aquí (lista hardcodeada), sirve como plantilla
    del Composition Root real: el punto donde el Core (puertos, políticas) se
    conecta por primera vez a los adaptadores concretos (Apollo, Hunter) vía
    inyección de dependencias.

    Rol de Composition Root — lo que este script hace y el Core JAMÁS hace:
        1. Carga secretos del entorno (.env).
        2. Instancia los adaptadores concretos (ApolloClient, HunterClient,
           ApolloHunterCascadaAdapter).
        3. Resuelve el puerto PuertoEnriquecedorContactos a esa instancia
           concreta y lo inyecta en el flujo de negocio.
        4. Aplica las políticas puras del Core (UmbralCalidadDecisor) sobre
           el resultado, sin que esas políticas sepan de dónde vino el dato.

⚠️  ADVERTENCIA DE COSTO REAL:
    Este script hace llamadas de red REALES a Apollo.io y Hunter.io y
    CONSUME CRÉDITOS REALES de esas cuentas. NO es un test (los tests viven
    en `tests/test_enrichment_adapters.py` con mocks, sin costo). Ejecutar
    este script cuesta dinero. Se incluye una confirmación interactiva
    obligatoria antes de gastar un solo crédito.

KPI de aprobación del piloto (Principal Architect, 14-Jul-2026):
    - Costo estimado < $1.00 USD por Decisor APTO_M4.
    - Bounce rate real < 2% — ⚠️ NO medible por este script (requiere enviar
      correos reales vía Motor 4). Ver nota en el reporte final.

Uso:
    .venv\\Scripts\\python.exe sandbox_piloto_latam_m3.py

Requisitos en .env:
    APOLLO_API_KEY=xxxxxxxxxxxxxxxx   (obligatorio — sin esto, 0 costo pero 0 resultados)
    HUNTER_API_KEY=xxxxxxxxxxxxxxxx   (obligatorio — sin esto, 0 costo pero 0 resultados)
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime, timezone

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
from src.adapters.enrichment.apollo_client import ApolloClient
from src.adapters.enrichment.apollo_hunter_cascada_adapter import (
    ApolloHunterCascadaAdapter,
)
from src.adapters.enrichment.hunter_client import HunterClient
from src.core.domain.models import (
    BaseLegal,
    CategoriaEmpresa,
    Decisor,
    Empresa,
    EstadoCorreo,
    ManifiestoICP,
    NivelConfianza,
    OrigenTrigger,
    ProspectoCalificado,
    TamanoEmpresa,
    Trigger,
)
from src.core.domain.policies import UmbralCalidadDecisor

BANNER = f"""
{cian('╔══════════════════════════════════════════════════════════════════╗')}
{cian('║')}  {negrita('EL PROSPECTOR')} — Piloto LATAM del Motor 3                     {cian('║')}
{cian('║')}  {azul('Apollo')} (descubridor) → {magenta('Hunter')} (validador duro)              {cian('║')}
{cian('╚══════════════════════════════════════════════════════════════════╝')}
"""

# ---------------------------------------------------------------------------
# Estimaciones de costo — AJUSTAR con factura real tras el piloto.
# Fuente de referencia: 10-Memoria_Consolidada/validacion/validacion-fuentes.md §6.
# Estos valores son un piso conservador de precio de lista; el documento de
# validación advierte que el costo real corre 2-3x por encima una vez se
# suman overages. Por eso se reporta el costo "de lista" Y el "con colchón".
# ---------------------------------------------------------------------------
APOLLO_COSTO_POR_CREDITO_USD = 0.05  # ESTIMADO — 1 credito = 1 export de contacto
HUNTER_COSTO_POR_CREDITO_USD = 0.02  # ESTIMADO — 0.5 credito = 1 verificación
COLCHON_COSTO_OCULTO = 2.5  # Punto medio del rango 2-3x documentado en validación

CARGOS_OBJETIVO_DEFAULT = ["CTO", "VP Engineering", "Head of Talent"]


# ---------------------------------------------------------------------------
# Paso 1: Construcción de la lista de prueba (empresas colombianas reales)
# ---------------------------------------------------------------------------
def construir_prospectos_de_prueba() -> list[ProspectoCalificado]:
    """
    Empaqueta una pequeña muestra de empresas colombianas reales y conocidas
    en objetos ProspectoCalificado ficticios. El Trigger es un placeholder:
    no lo usa el enriquecedor (ver §3.3 del diseño), solo satisface el
    contrato de transición M2→M3 para que el DTO sea válido.

    Nota de compliance: se usa BaseLegal.DATO_PUBLICO (Art. 10, Ley 1581)
    porque el piloto opera sobre información profesional públicamente
    disponible de empresas reconocidas. Esto NO sustituye la asesoría legal
    real pendiente en validacion-fuentes.md §7 antes de producción masiva.
    """
    empresas_reales: list[dict] = [
        {
            "nombre": "Bancolombia",
            "dominio": "bancolombia.com",
            "tamano": TamanoEmpresa.ENTERPRISE,
            "vertical": "Banca y Servicios Financieros",
            "ciudad": "Medellín",
        },
        {
            "nombre": "Rappi",
            "dominio": "rappi.com",
            "tamano": TamanoEmpresa.ENTERPRISE,
            "vertical": "Delivery y Marketplace",
            "ciudad": "Bogotá",
        },
        {
            "nombre": "Platzi",
            "dominio": "platzi.com",
            "tamano": TamanoEmpresa.MID_MARKET,
            "vertical": "EdTech",
            "ciudad": "Bogotá",
        },
        {
            "nombre": "Addi",
            "dominio": "addi.com",
            "tamano": TamanoEmpresa.MID_MARKET,
            "vertical": "Fintech (BNPL)",
            "ciudad": "Bogotá",
        },
        {
            "nombre": "Merqueo",
            "dominio": "merqueo.com",
            "tamano": TamanoEmpresa.SME,
            "vertical": "Quick Commerce",
            "ciudad": "Bogotá",
        },
    ]

    prospectos: list[ProspectoCalificado] = []
    for datos in empresas_reales:
        empresa = Empresa(
            nombre=datos["nombre"],
            dominio=datos["dominio"],
            tamano=datos["tamano"],
            vertical=datos["vertical"],
            pais="CO",
            ciudad=datos["ciudad"],
        )

        # Trigger ficticio: satisface el contrato de ProspectoCalificado
        # (min_length=1) pero el enriquecedor no lo consume (§3.3 del diseño).
        trigger_ficticio = Trigger(
            empresa_id=empresa.id,
            origen=OrigenTrigger.GOOGLE_ALERTS,
            nivel_confianza=NivelConfianza.MEDIA,
            descripcion=(
                "Trigger ficticio del harness de piloto — no relevante para "
                "el Motor 3. Simula que esta empresa ya pasó "
                "TriggerAggregationPolicy en un pipeline real."
            ),
            fecha_evento=datetime.now(timezone.utc),
        )

        manifiesto_ficticio = ManifiestoICP(
            pain_es_accionable=False,
            anclaje_tecnologico=["Amazon Web Services"],
            categoria_empresa=CategoriaEmpresa.SAAS_B2B_HORIZONTAL,
            vertical=datos["vertical"],
            cargos_decisores=CARGOS_OBJETIVO_DEFAULT,
            tamano_empresa=datos["tamano"],
            geografia="CO",
            base_legal=BaseLegal.DATO_PUBLICO,
        )

        prospectos.append(
            ProspectoCalificado(
                empresa=empresa,
                triggers=[trigger_ficticio],
                manifiesto=manifiesto_ficticio,
            )
        )

    return prospectos


# ---------------------------------------------------------------------------
# Paso 2: Ejecución de la cascada (Composition Root en acción)
# ---------------------------------------------------------------------------
def ejecutar_piloto(
    prospectos: list[ProspectoCalificado],
    enriquecedor: ApolloHunterCascadaAdapter,
) -> dict[str, list[Decisor]]:
    """
    Por cada ProspectoCalificado, invoca el puerto (vía la implementación
    concreta inyectada) y acumula los Decisores retornados.

    El orquestador extrae `empresa` y `manifiesto.cargos_decisores` del DTO
    para llamar a `enriquecer(empresa, cargos)` — firma stateless, sin
    contexto de job persistido entre llamadas (§3.1 del diseño).
    """
    resultados: dict[str, list[Decisor]] = {}

    print(f"\n{SEP}\n")
    print(f"  {negrita('Ejecutando cascada Apollo → Hunter por empresa...')}\n")
    print(f"{SEP2}\n")

    for idx, prospecto in enumerate(prospectos, start=1):
        empresa = prospecto.empresa
        cargos = prospecto.manifiesto.cargos_decisores

        print(f"  {negrita(f'{idx:02d}.')} {negrita(empresa.nombre)} ({cian(empresa.dominio)})")
        try:
            decisores = enriquecedor.enriquecer(empresa, cargos)
        except Exception as exc:
            print(f"       {rojo(f'✗  Error inesperado: {exc}')}")
            decisores = []

        resultados[empresa.nombre] = decisores

        if not decisores:
            print(f"       {gris('Apollo: 0 perfiles → Hunter NO fue invocado (corte de costo).')}")
        else:
            for d in decisores:
                estado_color = {
                    EstadoCorreo.VERIFICADO: verde,
                    EstadoCorreo.INFERIDO: amarillo,
                    EstadoCorreo.REBOTADO: rojo,
                    EstadoCorreo.NO_RESUELTO: gris,
                    EstadoCorreo.MANUAL: gris,
                }.get(d.estado_correo, gris)
                print(
                    f"       [{estado_color(d.estado_correo.value):12s}] "
                    f"{gris(f'confianza={d.confianza_dato:.2f}')}  {d.nombre} — {d.cargo_original}"
                )
        print()

    return resultados


# ---------------------------------------------------------------------------
# Paso 3: Métricas del KPI del piloto (§3.5 del diseño)
# ---------------------------------------------------------------------------
def calcular_metricas(resultados: dict[str, list[Decisor]]) -> dict:
    total_empresas = len(resultados)
    todos_decisores: list[Decisor] = [d for lista in resultados.values() for d in lista]

    empresas_con_perfil = sum(1 for lista in resultados.values() if lista)
    tasa_resolucion_apollo = (
        (empresas_con_perfil / total_empresas * 100) if total_empresas else 0.0
    )

    distribucion_estado = Counter(d.estado_correo for d in todos_decisores)

    umbral = UmbralCalidadDecisor()
    aptos, cola_manual = umbral.particionar(todos_decisores)

    # Estimación de créditos consumidos (aproximación — ver constantes arriba).
    # Apollo: 1 credito de export por cada Decisor retornado (el perfil ya
    # costó el crédito de export aunque luego se descarte por calidad).
    creditos_apollo = len(todos_decisores) * 1

    # Hunter: distinguimos verify (perfil con email candidato) de
    # domain-search (perfil sin email, se intentó inferir patrón). El campo
    # `correo` del Decisor nos delata cuál camino tomó la cascada.
    decisores_con_email = [d for d in todos_decisores if d.correo is not None]
    decisores_sin_email = [d for d in todos_decisores if d.correo is None]
    creditos_hunter = (len(decisores_con_email) + len(decisores_sin_email)) * 0.5

    costo_lista_usd = (
        creditos_apollo * APOLLO_COSTO_POR_CREDITO_USD
        + creditos_hunter * HUNTER_COSTO_POR_CREDITO_USD
    )
    costo_con_colchon_usd = costo_lista_usd * COLCHON_COSTO_OCULTO

    costo_por_decisor_apto = (
        (costo_con_colchon_usd / len(aptos)) if aptos else None
    )

    return {
        "total_empresas": total_empresas,
        "empresas_con_perfil": empresas_con_perfil,
        "tasa_resolucion_apollo": tasa_resolucion_apollo,
        "total_decisores": len(todos_decisores),
        "distribucion_estado": distribucion_estado,
        "aptos_m4": aptos,
        "cola_manual": cola_manual,
        "creditos_apollo": creditos_apollo,
        "creditos_hunter": creditos_hunter,
        "costo_lista_usd": costo_lista_usd,
        "costo_con_colchon_usd": costo_con_colchon_usd,
        "costo_por_decisor_apto": costo_por_decisor_apto,
    }


# ---------------------------------------------------------------------------
# Paso 4: Reporte final — veredicto del KPI de aprobación del piloto
# ---------------------------------------------------------------------------
def imprimir_reporte(metricas: dict) -> None:
    print(f"{SEP}\n")
    print(f"  {negrita('📊  REPORTE DEL PILOTO — Motor 3 (Apollo → Hunter)')}\n")

    print(f"  {negrita('Cobertura:')}")
    print(
        f"    Empresas procesadas:        {negrita(str(metricas['total_empresas']))}"
    )
    print(
        f"    Empresas con ≥1 perfil:     {negrita(str(metricas['empresas_con_perfil']))}"
    )
    tasa_str = f"{metricas['tasa_resolucion_apollo']:.1f}%"
    print(f"    Tasa de resolución Apollo:  {negrita(tasa_str)}")
    print(f"    Decisores totales:          {negrita(str(metricas['total_decisores']))}\n")

    print(f"  {negrita('Distribución de estado_correo:')}")
    dist = metricas["distribucion_estado"]
    colores_estado = {
        EstadoCorreo.VERIFICADO: verde,
        EstadoCorreo.INFERIDO: amarillo,
        EstadoCorreo.REBOTADO: rojo,
        EstadoCorreo.NO_RESUELTO: gris,
        EstadoCorreo.MANUAL: gris,
    }
    if not dist:
        print(f"    {gris('— sin decisores —')}")
    for estado in EstadoCorreo:
        n = dist.get(estado, 0)
        if n == 0:
            continue
        color_fn = colores_estado.get(estado, gris)
        print(f"    {color_fn(estado.value):20s} {n}")
    print()

    print(f"  {negrita('Gate de calidad (UmbralCalidadDecisor):')}")
    print(f"    {verde('✓ Aptos para Motor 4:')}  {len(metricas['aptos_m4'])}")
    print(f"    {gris('— Cola manual:')}         {len(metricas['cola_manual'])}\n")

    print(f"  {negrita('Costo estimado (créditos simulados):')}")
    print(
        f"    Créditos Apollo consumidos: {metricas['creditos_apollo']:.1f}  "
        f"{gris(f'(${APOLLO_COSTO_POR_CREDITO_USD}/créd, ESTIMADO)')}"
    )
    print(
        f"    Créditos Hunter consumidos: {metricas['creditos_hunter']:.1f}  "
        f"{gris(f'(${HUNTER_COSTO_POR_CREDITO_USD}/créd, ESTIMADO)')}"
    )
    print(f"    Costo de lista:             ${metricas['costo_lista_usd']:.2f} USD")
    print(
        f"    Costo con colchón ({COLCHON_COSTO_OCULTO}x): "
        f"${metricas['costo_con_colchon_usd']:.2f} USD "
        f"{gris('(ver validacion-fuentes.md §6)')}\n"
    )

    print(f"{SEP}\n")
    print(f"  {negrita('🎯  VEREDICTO — KPI de aprobación del piloto (§3.5):')}\n")

    costo_apto = metricas["costo_por_decisor_apto"]
    if costo_apto is None:
        print(f"    {rojo('✗  Sin decisores APTOS — no se puede calcular costo/decisor.')}")
        print(f"    {rojo('   El piloto NO se aprueba con esta muestra.')}\n")
    else:
        cumple_costo = costo_apto < 1.00
        color_costo = verde if cumple_costo else rojo
        icono_costo = "✓" if cumple_costo else "✗"
        print(
            f"    {color_costo(f'{icono_costo}  Costo por decisor APTO_M4: ${costo_apto:.2f} USD')}"
            f"  {gris('(umbral: < $1.00 USD)')}"
        )

    print(
        f"\n    {amarillo('⚠  Bounce rate real < 2%: NO medible por este harness.')}"
    )
    print(
        f"    {gris('   Requiere enviar los correos APTOS vía Motor 4 y medir')}"
    )
    print(
        f"    {gris('   rebotes reales. El KPI de piloto solo se cierra con ese dato.')}\n"
    )

    print(f"{SEP}")
    print(
        f"\n  {gris('Nota: los valores de $/crédito son ESTIMADOS (validacion-fuentes.md §6).')}"
    )
    print(
        f"  {gris('Recalibrar con la factura real de Apollo/Hunter tras esta corrida.')}\n"
    )


# ---------------------------------------------------------------------------
# Main — Composition Root
# ---------------------------------------------------------------------------
def main() -> None:
    print(BANNER)

    apollo_key = os.getenv("APOLLO_API_KEY")
    hunter_key = os.getenv("HUNTER_API_KEY")

    if not apollo_key or not hunter_key:
        print(f"{amarillo('AVISO — faltan credenciales:')}")
        if not apollo_key:
            print(f"  {amarillo('APOLLO_API_KEY')} no configurada en .env")
        if not hunter_key:
            print(f"  {amarillo('HUNTER_API_KEY')} no configurada en .env")
        print(
            "\n  Sin ambas claves, la cascada retornará listas vacías para "
            "todas las empresas (costo $0, pero el piloto no arroja datos).\n"
        )

    print(f"  {rojo(negrita('⚠  ADVERTENCIA DE COSTO REAL'))}")
    print(
        f"  {gris('Este script llama a las APIs reales de Apollo y Hunter y')}"
    )
    print(
        f"  {gris('CONSUME CRÉDITOS REALES de esas cuentas. No es una simulación.')}"
    )
    print(f"  {gris('Empresas en esta corrida:')} "
          f"{negrita(str(len(construir_prospectos_de_prueba())))}\n")

    try:
        confirmacion = input(
            f"{cian('▶')} Escribe {negrita('CONFIRMO')} para gastar créditos reales "
            f"{gris('[Ctrl+C para cancelar]')}: "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {gris('Cancelado. Ningún crédito fue consumido.')}\n")
        sys.exit(0)

    if confirmacion != "CONFIRMO":
        print(f"\n  {gris('Confirmación no recibida. Ningún crédito fue consumido.')}\n")
        sys.exit(0)

    # ── Composition Root: instanciar adaptadores concretos e inyectar el puerto ──
    apollo_client = ApolloClient(api_key=apollo_key)
    hunter_client = HunterClient(api_key=hunter_key)
    enriquecedor: ApolloHunterCascadaAdapter = ApolloHunterCascadaAdapter(
        apollo_client=apollo_client,
        hunter_client=hunter_client,
    )

    prospectos = construir_prospectos_de_prueba()
    resultados = ejecutar_piloto(prospectos, enriquecedor)
    metricas = calcular_metricas(resultados)
    imprimir_reporte(metricas)


if __name__ == "__main__":
    main()
