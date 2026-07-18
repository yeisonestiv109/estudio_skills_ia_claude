"""
Sandbox TBBC Real — Corrida del ICP real de TBBC (00-contexto-cliente.md §4).
Ejecuta Motor 1 (Groq) → Filtro Negative ICP → Waterfall de Tamaño → Motor 2
(5 fuentes) sin input() interactivo.

Nuevo en esta versión (afinamiento post-piloto):
    - PoliticaExclusionCompetidores (Capa 1, gratis): descarta de inmediato
      empresas cuyo nombre matchea un patrón genérico de "vendor de TI"
      (fábrica de software, consultora, agencia digital, etc.) igual a la
      categoría del propio cliente. Este es un heurístico BARATO de sandbox
      —no un clasificador real— que sustituye, mientras no exista uno mejor,
      a la señal "categoria_candidata" que Motor 2 hoy no produce gratis.
      Ver nota de diseño más abajo (_heuristica_categoria_candidata).
    - PropuestaValorAdapter (Capa 2, con costo — LLM sobre la homepage):
      se invoca SOLO cuando la Capa 1 no pudo pronunciarse (heurística sin
      match). Resuelve la ambigüedad leyendo la propuesta de valor real del
      candidato y, de paso, aporta una segunda EstimacionTamano gratuita
      (misma llamada al LLM, cacheada por instancia).
    - PoliticaCorroboracionTamano: exige que TheirStack y PropuestaValorAdapter
      corroboren el tamaño antes de aceptarlo. Si el consenso dice ENTERPRISE
      y el ICP de TBBC pide SME, la empresa se descarta antes de llegar a M3.

Uso:
    .venv\\Scripts\\python.exe sandbox_tbbc_real.py

Requisitos en .env:
    GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxx        (obligatorio — M1 y Capa 2)
    THEIRSTACK_API_KEY=ts_xxxxxxxxxxxxxxxxxx   (opcional — discovery)
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    os.system("")

# Forzar UTF-8 en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

from sandbox_motor_2_auto import (
    SEP,
    SEP2,
    amarillo,
    cian,
    ejecutar_discovery,
    ejecutar_motor_1,
    gris,
    imprimir_resultado_empresa,
    negrita,
    recolectar_triggers,
    rojo,
    verde,
)
from src.adapters.llm.groq_adapter import GroqICPAdapter
from src.adapters.triggers.propuesta_valor_adapter import PropuestaValorAdapter
from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
from src.core.domain.models import (
    CategoriaEmpresa,
    EstadoConsensoTamano,
    EstadoValidacionGeografica,
    Empresa,
    EstimacionTamano,
    ManifiestoICP,
    PAIS_DESCONOCIDO,
    ResultadoExclusionCompetidor,
    TamanoEmpresa,
)
from src.core.domain.policies import (
    AdapterRoutingPolicy,
    PoliticaCorroboracionTamano,
    PoliticaExclusionCompetidores,
    PoliticaValidacionGeografica,
    TriggerAggregationPolicy,
)

# ── BATCH DE PRUEBA CONTROLADO (escalamiento post-corrida de 3 empresas) ──
# Diagnóstico de la corrida anterior: los filtros (Waterfall de Tamaño,
# Negative ICP, TriggerAggregationPolicy) funcionaron correctamente — 0
# créditos de M3 desperdiciados. El problema fue volumen de entrada: con
# solo 3 candidatos descubiertos, la ley de promedios no tuvo margen para
# dejar pasar ni un SME con señales suficientes. Subir el techo de discovery
# (parámetro de EMBUDO, no de política) amplía la parte alta sin tocar
# ninguna regla de negocio ya validada.
TAMANO_BATCH_DISCOVERY: int = 15

# ── ICP REAL DE TBBC (de 00-contexto-cliente.md §4) ──────────────────────
ICP_TBBC = (
    "Somos TBBC, una consultora IT y system integrator en Colombia. "
    "Buscamos empresas colombianas de 51 a 200 empleados que publiquen "
    "vacantes de Python, Django, FastAPI, Amazon Web Services, Google Cloud Platform, "
    "PostgreSQL, Docker, Kubernetes, React o Node.js y no logren llenarlas. "
    "Esas empresas necesitan abasto en proyectos de tecnologia, tienen retrasos "
    "en las entregas por falta de talento tecnico adecuado, sistemas legacy mal "
    "estructurados y trabajo lento. Los cargos de decision son CTO, VP de Ventas "
    "y VP de Operaciones. Nuestra propuesta de valor es acompanamiento desde la "
    "preventa tecnica, diseno, implementacion y operacion de soluciones con "
    "Python, FastAPI, Amazon Web Services, PostgreSQL, Docker y Kubernetes."
)

# ---------------------------------------------------------------------------
# Heurística barata de categoria_candidata (Capa 1 del Negative ICP)
# ---------------------------------------------------------------------------
# NOTA DE DISEÑO IMPORTANTE: Motor 2 (discovery de TheirStack) hoy NO produce
# una CategoriaEmpresa real para la empresa candidata — solo la produce el
# LLM de Motor 1 y, para candidatos, el propio PropuestaValorAdapter (Capa 2,
# con costo). Mientras no exista un clasificador gratuito equivalente, este
# patrón de palabras clave sobre el NOMBRE público de la empresa actúa como
# el escalón "barato" de la cascada: es un heurístico genérico de modelo de
# negocio (no una lista negra de competidores nombrados) y su único trabajo
# es detectar los casos OBVIOS de vendor de TI sin gastar un token de LLM.
# Cualquier caso no obvio (la mayoría) se difiere honestamente a la Capa 2.
_PALABRAS_CLAVE_VENDOR_IT: frozenset[str] = frozenset(
    {
        "software",
        "tecnolog",  # cubre tecnología / tecnologia / technology / tech
        "consultora",
        "consulting",
        "it services",
        "systems",
        "solutions",
        "soluciones digitales",
        "digital agency",
        "agencia digital",
        "outsourcing",
        "development",
        "developers",
        "system integrator",
        "fábrica de software",
        "fabrica de software",
    }
)


def _heuristica_categoria_candidata(
    empresa: Empresa, categoria_cliente: CategoriaEmpresa
) -> CategoriaEmpresa | None:
    """
    Escalón GRATIS de la cascada. Si el nombre público de la empresa candidata
    matchea un patrón genérico de vendor de TI, se asume (como hipótesis, no
    como certeza) que su categoría es la MISMA que la del cliente — el único
    juicio que un simple keyword-match puede sostener honestamente. Si no hay
    match, retorna None: "no se pudo decidir gratis", que es la señal para
    diferir a la Capa 2 (PropuestaValorAdapter), NUNCA un "es seguro".
    """
    texto = empresa.nombre.lower()
    if any(palabra in texto for palabra in _PALABRAS_CLAVE_VENDOR_IT):
        return categoria_cliente
    return None


def evaluar_exclusion_competidor(
    empresa: Empresa,
    categoria_cliente: CategoriaEmpresa,
    adapter_pv: PropuestaValorAdapter,
) -> tuple[ResultadoExclusionCompetidor, str]:
    """
    Cascada completa de exclusión de competidores para UNA empresa candidata.

    Retorna (veredicto_final, motivo_legible). El veredicto final es
    PERMITIDO, EXCLUIDO_DURO o PENDIENTE_REVISION_MANUAL (fail-closed cuando
    la Capa 2 no pudo determinar es_vendor_it) — REQUIERE_ANALISIS_SEMANTICO
    nunca se retorna hacia el llamador porque esta función ya resuelve esa
    ambigüedad invocando la Capa 2 internamente antes de responder.
    """
    politica = PoliticaExclusionCompetidores()

    # Paso 1 (Capa 1, gratis): heurística de nombre.
    categoria_candidata_barata = _heuristica_categoria_candidata(
        empresa, categoria_cliente
    )
    if categoria_candidata_barata is not None:
        resultado = politica.evaluar(categoria_cliente, categoria_candidata_barata)
        if resultado == ResultadoExclusionCompetidor.EXCLUIDO_DURO:
            return resultado, "nombre coincide con patrón de vendor de TI (heurística gratis)"
        # PERMITIDO o (en teoría) REQUIERE_ANALISIS_SEMANTICO con la categoría
        # "prestada" del cliente no puede darse aquí, porque siempre comparamos
        # categoria_cliente contra sí misma. Si no fue EXCLUIDO_DURO, se cae
        # al mismo tratamiento que "sin match": diferir a la Capa 2 para no
        # asumir PERMITIDO sobre una hipótesis débil.

    # Paso 2 (Capa 2, con costo): análisis semántico real vía LLM.
    #
    # FAIL-CLOSED (fix Falla 1, caso Parcero/UK): si es_vendor_it() no pudo
    # determinarse (scraping falló, SPA sin texto útil, LLM no disponible),
    # NUNCA se interpreta como "confirmado no competidor". Antes este branch
    # retornaba PERMITIDO directamente ante analisis=None, lo cual dejó pasar
    # a un competidor real (agencia UK) sin ninguna evidencia a favor. Ahora
    # se distingue explícitamente "confirmado que NO es vendor" (es_vendor_it
    # == False) de "no se pudo determinar" (es_vendor_it is None) — solo el
    # primer caso es PERMITIDO; el segundo va a revisión manual.
    es_vendor = adapter_pv.es_vendor_it(empresa)
    if es_vendor is None:
        return (
            ResultadoExclusionCompetidor.PENDIENTE_REVISION_MANUAL,
            "análisis semántico indeterminado (scraping/LLM sin señal suficiente) — fail-closed",
        )

    if es_vendor:
        return (
            ResultadoExclusionCompetidor.EXCLUIDO_DURO,
            "propuesta de valor confirma vendor de TI (análisis semántico LLM)",
        )

    return (
        ResultadoExclusionCompetidor.PERMITIDO,
        "propuesta de valor confirma que NO es vendor de TI (análisis semántico LLM)",
    )


def evaluar_validacion_geografica(
    empresa: Empresa,
    manifiesto: ManifiestoICP,
    adapter_pv: PropuestaValorAdapter,
) -> tuple[EstadoValidacionGeografica, str]:
    """
    Waterfall geográfico (fix Falla 2, caso Parcero/UK) para UNA empresa
    candidata. Resuelve el país candidato con el mismo patrón barato→caro que
    el resto del Motor 2:

    1. Empresa.pais (ya viene de TheirStack/discovery). Si es un país
       conocido y distinto de PAIS_DESCONOCIDO, se usa directamente — no
       amerita gastar LLM para confirmar un dato firmográfico ya presente.
    2. Si Empresa.pais es PAIS_DESCONOCIDO (TheirStack no lo reportó), se
       recurre a PropuestaValorAdapter.pais_hq() (Capa 2, con costo — ya
       cacheada si la Capa 2 corrió antes para esta misma empresa en
       evaluar_exclusion_competidor()).

    Retorna (estado, motivo_legible). INDETERMINADO es fail-closed: el
    llamador debe tratarlo como revisión manual, nunca como aprobación.
    """
    politica = PoliticaValidacionGeografica()

    pais_candidato = empresa.pais
    origen_dato = "TheirStack (discovery)"
    if not pais_candidato or pais_candidato.strip().upper() == PAIS_DESCONOCIDO:
        pais_candidato = adapter_pv.pais_hq(empresa)
        origen_dato = "análisis semántico LLM (homepage)"

    estado = politica.evaluar(pais_candidato, manifiesto.geografia)

    if estado == EstadoValidacionGeografica.PERMITIDO:
        motivo = f"país candidato ({pais_candidato or 'sin restricción de ICP'}) coincide con geografía del ICP — origen: {origen_dato}"
    elif estado == EstadoValidacionGeografica.EXCLUIDO:
        motivo = f"país candidato '{pais_candidato}' no coincide con geografía del ICP '{manifiesto.geografia}' — origen: {origen_dato}"
    else:
        motivo = "país candidato indeterminado (ni TheirStack ni análisis semántico lo resolvieron) — fail-closed"

    return estado, motivo


def evaluar_consenso_tamano(
    empresa: Empresa,
    adapter_ts: TheirStackAdapter,
    adapter_pv: PropuestaValorAdapter,
) -> tuple[EstadoConsensoTamano, TamanoEmpresa | None]:
    """
    Recolecta EstimacionTamano de los dos orígenes disponibles (TheirStack —
    dato firmográfico real vía employee_count; PropuestaValorAdapter — señal
    semántica del lenguaje corporativo, ya cacheada si Capa 2 corrió antes
    para esta misma empresa) y las pasa por el waterfall de corroboración.
    """
    politica = PoliticaCorroboracionTamano()
    estimaciones: list[EstimacionTamano] = []

    try:
        est_ts = adapter_ts.estimar_tamano(empresa)
        if est_ts is not None:
            estimaciones.append(est_ts)
    except Exception:
        pass

    try:
        est_pv = adapter_pv.estimar_tamano(empresa)
        if est_pv is not None:
            estimaciones.append(est_pv)
    except Exception:
        pass

    return politica.corroborar(estimaciones)


def _imprimir_banner_exclusion(empresa: Empresa, motivo: str) -> None:
    print(f"  {rojo('▓' * 64)}")
    print(f"  {rojo('▓')}  {rojo(negrita('COMPETIDOR EXCLUIDO'))} — {negrita(empresa.nombre)}")
    print(f"  {rojo('▓')}  {gris(f'Motivo: {motivo}')}")
    print(f"  {rojo('▓')}  {gris('Costo evitado: 0 créditos de Motor 3 (Apollo/Hunter) gastados en esta empresa.')}")
    print(f"  {rojo('▓' * 64)}\n")


def _imprimir_banner_revision_manual(empresa: Empresa, motivo: str) -> None:
    print(f"  {cian('▒' * 64)}")
    print(f"  {cian('▒')}  {cian(negrita('PENDIENTE DE REVISIÓN MANUAL'))} — {negrita(empresa.nombre)}")
    print(f"  {cian('▒')}  {gris(f'Motivo: {motivo}')}")
    print(f"  {cian('▒')}  {gris('Fail-closed: no se confirma como competidor ni se descarta. Requiere revisión humana antes de avanzar a Motor 3.')}")
    print(f"  {cian('▒' * 64)}\n")


def _imprimir_banner_geografia_descartada(empresa: Empresa, motivo: str) -> None:
    print(f"  {amarillo('▒' * 64)}")
    print(f"  {amarillo('▒')}  {amarillo(negrita('DESCARTADA POR GEOGRAFÍA'))} — {negrita(empresa.nombre)}")
    print(f"  {amarillo('▒')}  {gris(f'Motivo: {motivo}')}")
    print(f"  {amarillo('▒' * 64)}\n")


def _imprimir_banner_tamano_descartado(
    empresa: Empresa, estado: EstadoConsensoTamano, tamano: TamanoEmpresa | None
) -> None:
    print(f"  {amarillo('░' * 64)}")
    print(f"  {amarillo('░')}  {amarillo(negrita('DESCARTADA POR TAMAÑO'))} — {negrita(empresa.nombre)}")
    if tamano is not None:
        print(f"  {amarillo('░')}  {gris(f'Consenso de tamaño ({estado.value}): {tamano.value} (ICP pide SME)')}")
    else:
        print(f"  {amarillo('░')}  {gris(f'Estado de consenso: {estado.value} — sin base confiable de tamaño')}")
    print(f"  {amarillo('░' * 64)}\n")


def main() -> None:
    print(f"\n{cian('=' * 64)}")
    print(f"  {negrita('SANDBOX TBBC REAL')} — ICP de 00-contexto-cliente.md")
    print(f"  {gris('+ Filtro Negative ICP + Waterfall de Tamaño (afinamiento Motor 2)')}")
    print(f"{cian('=' * 64)}")
    print(f"\n  {gris('ICP inyectado:')}")
    print(f"  {gris(ICP_TBBC[:80])}...")

    # Motor 1
    adaptador_icp = GroqICPAdapter()
    manifiesto: ManifiestoICP | None = ejecutar_motor_1(adaptador_icp, ICP_TBBC)
    if manifiesto is None:
        sys.exit(1)

    categoria_cliente = manifiesto.categoria_empresa
    print(f"\n  {negrita('Categoría del cliente (TBBC) para Negative ICP:')} {amarillo(categoria_cliente.value)}\n")

    # Enrutador
    routing = AdapterRoutingPolicy()
    adaptadores_activos = routing.resolver(manifiesto)
    nombres_activos = [o.value for o in adaptadores_activos]
    print(f"  {negrita('Adaptadores activados:')} {', '.join(amarillo(n) for n in nombres_activos)}\n")

    # Adaptadores del Motor 2 (afinamiento incluido)
    theirstack_key = os.getenv("THEIRSTACK_API_KEY")
    adapter_ts = TheirStackAdapter(
        api_key=theirstack_key,
        tecnologias_objetivo=manifiesto.anclaje_tecnologico,
        max_empresas_discovery=TAMANO_BATCH_DISCOVERY,
    )
    adapter_pv = PropuestaValorAdapter()  # lee GROQ_API_KEY del entorno
    print(
        f"  {gris(f'Batch de discovery configurado: {TAMANO_BATCH_DISCOVERY} empresas máx.')}\n"
    )

    # Motor 2A — Discovery
    empresas = ejecutar_discovery(manifiesto, adapter_ts)

    if not empresas:
        print(f"\n{SEP}\n")
        print(f"  {amarillo('Sin empresas de TheirStack. Verifica la API key.')}\n")
        sys.exit(0)

    # Motor 2B-D + Triangulación + Afinamiento (exclusión de competidores +
    # corroboración de tamaño), en ese orden, respetando barato→caro.
    policy_triggers = TriggerAggregationPolicy()
    print(f"{SEP}")
    print(f"\n  {negrita('Filtrando competidores y triangulando señales por empresa...')}\n")
    print(f"{SEP2}\n")

    empresas_calificadas = 0
    empresas_excluidas_competencia = 0
    empresas_pendientes_revision_manual = 0
    empresas_descartadas_tamano = 0
    empresas_descartadas_geografia = 0
    idx_mostrado = 0

    for empresa in empresas:
        # Paso 1: Negative ICP (Capa 1 gratis → Capa 2 con costo si ambiguo).
        # Fail-closed: PENDIENTE_REVISION_MANUAL va a cola manual, NUNCA se
        # trata como PERMITIDO (fix Falla 1, caso Parcero/UK).
        veredicto, motivo = evaluar_exclusion_competidor(
            empresa, categoria_cliente, adapter_pv
        )
        if veredicto == ResultadoExclusionCompetidor.EXCLUIDO_DURO:
            empresas_excluidas_competencia += 1
            _imprimir_banner_exclusion(empresa, motivo)
            continue
        if veredicto == ResultadoExclusionCompetidor.PENDIENTE_REVISION_MANUAL:
            empresas_pendientes_revision_manual += 1
            _imprimir_banner_revision_manual(empresa, motivo)
            continue

        # Paso 2: Waterfall geográfico (fix Falla 2, caso Parcero/UK).
        # Fail-closed: INDETERMINADO también va a revisión manual, no se
        # asume que "sin dato de país" signifique "país correcto".
        estado_geo, motivo_geo = evaluar_validacion_geografica(
            empresa, manifiesto, adapter_pv
        )
        if estado_geo == EstadoValidacionGeografica.EXCLUIDO:
            empresas_descartadas_geografia += 1
            _imprimir_banner_geografia_descartada(empresa, motivo_geo)
            continue
        if estado_geo == EstadoValidacionGeografica.INDETERMINADO:
            empresas_pendientes_revision_manual += 1
            _imprimir_banner_revision_manual(empresa, motivo_geo)
            continue

        # Paso 3: Waterfall de tamaño — descarta ENTERPRISE cuando el ICP pide SME.
        estado_tamano, tamano_consensuado = evaluar_consenso_tamano(
            empresa, adapter_ts, adapter_pv
        )
        if (
            estado_tamano == EstadoConsensoTamano.CONSENSO
            and tamano_consensuado == TamanoEmpresa.ENTERPRISE
            and manifiesto.tamano_empresa == TamanoEmpresa.SME
        ):
            empresas_descartadas_tamano += 1
            _imprimir_banner_tamano_descartado(empresa, estado_tamano, tamano_consensuado)
            continue

        # Paso 4: flujo original de Motor 2 (triggers + calificación).
        idx_mostrado += 1
        triggers = recolectar_triggers(empresa, adapter_ts, manifiesto, adaptadores_activos)
        califica = policy_triggers.evaluar(triggers, adaptadores_activos)
        if califica:
            empresas_calificadas += 1
        imprimir_resultado_empresa(idx_mostrado, empresa, triggers, califica)

    # Resumen
    print(f"{SEP}")
    print(f"\n  {negrita('Resumen del pipeline TBBC Real (con afinamiento):')}")
    print(f"    {verde('✓')} Empresas descubiertas:        {negrita(str(len(empresas)))}")
    print(f"    {rojo('✗')} Excluidas por competencia:    {negrita(str(empresas_excluidas_competencia))}")
    print(f"    {cian('~')} Pendientes revisión manual:   {negrita(str(empresas_pendientes_revision_manual))}")
    print(f"    {amarillo('✗')} Descartadas por geografía:    {negrita(str(empresas_descartadas_geografia))}")
    print(f"    {amarillo('✗')} Descartadas por tamaño:       {negrita(str(empresas_descartadas_tamano))}")
    print(f"    {verde('✓')} Analizadas en Motor 2:        {negrita(str(idx_mostrado))}")
    print(f"    {verde('✓')} Califican para Motor 3:       {negrita(str(empresas_calificadas))}")
    print(f"    {gris('Tecnologías buscadas:         ')}{', '.join(manifiesto.anclaje_tecnologico)}")
    print(f"    {gris('Categoría detectada (cliente):')}{manifiesto.categoria_empresa.value}")
    tasa = (empresas_calificadas / len(empresas) * 100) if empresas else 0
    print(f"    {gris('Tasa de calificación bruta:   ')}{tasa:.1f}%")
    print(f"\n  {gris('Próximo paso: Motor 3 — enriquecer contactos (Apollo + Hunter)')}\n")


if __name__ == "__main__":
    main()
