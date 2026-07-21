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

Refactorización M1/M2 (post-corrida real, Hallazgo 2):
    Motor 1 (discovery de TAM) usa EXCLUSIVAMENTE ApolloDiscoveryAdapter
    (firmografía pura: sector, tamaño, país). TheirStackAdapter ya NO
    descubre empresas aquí — permanece activo únicamente dentro del
    Motor 2 (recolectar_triggers), donde busca señales de vacantes activas
    sobre las empresas que Apollo ya descubrió.

Uso:
    .venv\\Scripts\\python.exe sandbox_tbbc_real.py

Requisitos en .env:
    GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxx        (obligatorio — M1 y Capa 2)
    APOLLO_API_KEY=apllo_xxxxxxxxxxxxxxxxxx    (obligatorio — discovery TAM base, Motor 1)
    THEIRSTACK_API_KEY=ts_xxxxxxxxxxxxxxxxxx   (opcional — señales de vacantes, Motor 2)
    SECOP_APP_TOKEN=xxxxxxxxxxxxxxxxxx         (opcional — usar 'Token de la aplicación',
                                                 NO 'Clave API', en datos.gov.co)
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
    ejecutar_motor_1,
    gris,
    imprimir_resultado_empresa,
    negrita,
    recolectar_triggers,
    rojo,
    verde,
)
from src.adapters.llm.groq_adapter import GroqICPAdapter
from src.adapters.discovery.apollo_discovery_adapter import ApolloDiscoveryAdapter
from src.adapters.enrichment.apollo_hunter_cascada_adapter import (
    ApolloHunterCascadaAdapter,
)
from src.adapters.revision_manual.paquete_revision_adapter import (
    EstadoRevisionHumana,
    PaqueteRevisionAdapter,
)
from src.adapters.triggers.propuesta_valor_adapter import PropuestaValorAdapter
from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
from src.core.domain.text_matching import cualquiera_como_palabra_completa
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
    TierUrgencia,
)
from src.core.domain.policies import (
    AdapterRoutingPolicy,
    PoliticaCorroboracionTamano,
    PoliticaExclusionCompetidores,
    PoliticaValidacionGeografica,
    ScoreTriggerPolicy,
)

# ── BATCH DE PRUEBA CONTROLADO (escalamiento post-corrida de 3 empresas) ──
# Diagnóstico de la corrida anterior: los filtros (Waterfall de Tamaño,
# Negative ICP, TriggerAggregationPolicy) funcionaron correctamente — 0
# créditos de M3 desperdiciados. El problema fue volumen de entrada: con
# solo 3 candidatos descubiertos, la ley de promedios no tuvo margen para
# dejar pasar ni un SME con señales suficientes. Subir el techo de discovery
# (parámetro de EMBUDO, no de política) amplía la parte alta sin tocar
# ninguna regla de negocio ya validada.
TAMANO_BATCH_DISCOVERY: int = 10

# Batch del discoverer de TAM base (Apollo — firmografía pura). Único
# discoverer del Motor 1 tras la refactorización M1/M2 (Hallazgo 2).
#
# Subido de 25 a 50 (Hallazgo 3): Apollo, aunque el filtro geográfico ahora
# SÍ se aplica correctamente (ver nota de raíz en apollo_discovery_adapter.py),
# sigue siendo US-céntrico en su ranking de "mejor coincidencia" para SME
# latinoamericana. Un batch más grande le da al Motor 2 (PoliticaValidacion
# Geografica, Negative ICP, waterfall de tamaño) más candidatos reales de
# dónde filtrar colombianas, en vez de depender de que las primeras 25 ya
# sean las correctas.
TAMANO_BATCH_APOLLO_DISCOVERY: int = 50

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
# Discovery de TAM base: Apollo (firmografía pura)
# ---------------------------------------------------------------------------
# Refactorización M1/M2 (Hallazgo 2 de la corrida real): el Motor 1
# (discovery) ahora usa EXCLUSIVAMENTE ApolloDiscoveryAdapter — firmografía
# pura (sector, tamaño, país), sin importar si la empresa tiene vacantes
# activas en este momento. TheirStackAdapter.descubrir_empresas() dejó de
# invocarse aquí: la versión anterior sesgaba el TAM inicial únicamente a
# empresas que ya estaban contratando, colapsando M1 (discovery) con M2
# (señales). TheirStack se sigue usando — pero solo dentro de
# recolectar_triggers() (Motor 2), vía TheirStackAdapter.obtener_triggers(),
# que es donde el ManifiestoICP real ya lo invoca.
def ejecutar_discovery_combinado(
    manifiesto: ManifiestoICP,
    adapter_apollo: ApolloDiscoveryAdapter,
) -> list[Empresa]:
    """
    Descubre el TAM base usando únicamente Apollo (firmografía pura: sector,
    tamaño, país). Deduplica por dominio.

    Nombre de función conservado (`_combinado`) por compatibilidad con el
    resto del sandbox, aunque ya no combina TheirStack — ver nota de diseño
    arriba. TheirStack permanece activo en el Motor 2 (recolectar_triggers).
    """
    empresas_apollo_raw = adapter_apollo.descubrir_empresas(manifiesto)

    dominios_vistos: set[str] = set()
    empresas_combinadas: list[Empresa] = []
    for e in empresas_apollo_raw:
        if e.dominio in dominios_vistos:
            continue
        dominios_vistos.add(e.dominio)
        empresas_combinadas.append(e)

    print(
        f"  {gris('Discovery (Apollo, firmografía pura):')} "
        f"Total={negrita(str(len(empresas_combinadas)))}"
    )
    return empresas_combinadas


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

# "tecnolog" es un PREFIJO deliberado (no una palabra completa): cubre
# tecnología/tecnologia/technology/tech con un solo fragmento. A diferencia
# del resto de _PALABRAS_CLAVE_VENDOR_IT (palabras completas — "systems",
# "solutions", etc. — que sí deben pasar por matching de palabra completa
# para evitar falsos positivos tipo "EcoSolutions"), este fragmento se
# evalúa aparte con matching de subcadena intencional.
_PREFIJO_TECNOLOGIA: str = "tecnolog"


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

    Matching por PALABRA COMPLETA para las palabras del set (evita que
    "solutions" matchee dentro de "EcoSolutions", o "systems" dentro de
    "Ecosystems Inc"). "tecnolog" es la única excepción deliberada: se
    evalúa por subcadena/prefijo a propósito (ver _PREFIJO_TECNOLOGIA).
    """
    texto = empresa.nombre.lower()
    if _PREFIJO_TECNOLOGIA in texto:
        return categoria_cliente
    if cualquiera_como_palabra_completa(texto, _PALABRAS_CLAVE_VENDOR_IT):
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
    adapter_secop: SecopSocrataAdapter,
) -> tuple[EstadoConsensoTamano, TamanoEmpresa | None]:
    """
    Recolecta EstimacionTamano de los TRES orígenes disponibles (TheirStack —
    dato firmográfico real vía employee_count; PropuestaValorAdapter — señal
    semántica del lenguaje corporativo, ya cacheada si Capa 2 corrió antes
    para esta misma empresa; SecopSocrataAdapter — dato `es_pyme` verificado
    por la entidad contratante, solo aporta si la empresa tiene contratos
    SECOP) y las pasa por el waterfall de corroboración.

    Auditoría 22-Jul-2026: SecopSocrataAdapter implementa PuertoEstimadorTamano
    desde el frente "SECOP $q" de la sesión anterior, pero nunca se conectó
    aquí — la documentación (estado_actual.md, flujos_motor_1_y_2.md) ya
    afirmaba que era un "tercer origen para el waterfall", así que se corrige
    el código para que la afirmación sea cierta.
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

    try:
        est_secop = adapter_secop.estimar_tamano(empresa)
        if est_secop is not None:
            estimaciones.append(est_secop)
    except Exception:
        pass

    return politica.corroborar(estimaciones)


def _aplicar_decision_humana_persistida(
    empresa: Empresa, adapter_revision: PaqueteRevisionAdapter
) -> ResultadoExclusionCompetidor | None:
    """
    Consulta si esta empresa ya tiene una decisión humana registrada en la
    cola de revisión manual (ver PaqueteRevisionAdapter). Si la tiene,
    retorna el veredicto equivalente para que el llamador la respete SIN
    volver a invocar la Capa 2 (evita re-gastar LLM en algo que un humano
    ya resolvió). Retorna None si no hay decisión persistida — el llamador
    debe proceder con la evaluación normal.
    """
    decision = adapter_revision.obtener_decision_humana(str(empresa.id))
    if decision == EstadoRevisionHumana.CONFIRMADO_PERMITIDO:
        return ResultadoExclusionCompetidor.PERMITIDO
    if decision == EstadoRevisionHumana.CONFIRMADO_EXCLUIDO:
        return ResultadoExclusionCompetidor.EXCLUIDO_DURO
    return None


def _imprimir_banner_exclusion(empresa: Empresa, motivo: str) -> None:
    print(f"  {rojo('▓' * 64)}")
    print(f"  {rojo('▓')}  {rojo(negrita('COMPETIDOR EXCLUIDO'))} — {negrita(empresa.nombre)}")
    print(f"  {rojo('▓')}  {gris(f'Motivo: {motivo}')}")
    print(f"  {rojo('▓')}  {gris('Costo evitado: 0 créditos de Motor 3 (Apollo/Hunter) gastados en esta empresa.')}")
    print(f"  {rojo('▓' * 64)}\n")


def _registrar_pendiente_con_evidencia(
    empresa: Empresa,
    motivo: str,
    adapter_pv: PropuestaValorAdapter,
    adapter_revision: PaqueteRevisionAdapter,
) -> None:
    """
    Registra el Paquete de Revisión con toda la evidencia disponible: el
    snippet de homepage que YA leyó la Capa 2 (sin costo adicional — usa el
    cache de PropuestaValorAdapter) más los links de verificación de un clic.
    """
    snippet = adapter_pv.snippet_homepage(empresa)
    adapter_revision.registrar_pendiente(empresa, motivo, snippet_homepage=snippet)


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


def _color_por_tier(tier: TierUrgencia) -> str:
    """Colorea la etiqueta del tier según su urgencia (rojo=más urgente)."""
    etiqueta = tier.value
    if tier == TierUrgencia.TIER_0:
        return rojo(negrita(etiqueta))
    if tier == TierUrgencia.TIER_1:
        return amarillo(negrita(etiqueta))
    return gris(etiqueta)


def _imprimir_score_urgencia(
    score: int, tier_final: TierUrgencia, califica: bool
) -> None:
    """
    Muestra el resultado de ScoreTriggerPolicy (Signal-Based Selling v5.0):
    el score numérico de urgencia, el tier más alto detectado y el veredicto.
    """
    umbral = ScoreTriggerPolicy.UMBRAL_CALIFICACION
    veredicto = (
        verde(negrita(f"CALIFICA (score {score} ≥ {umbral})"))
        if califica
        else gris(f"nurturing (score {score} < {umbral})")
    )
    print(
        f"       {gris('Signal-Based Selling:')} "
        f"score={negrita(str(score))} · tier={_color_por_tier(tier_final)} · {veredicto}"
    )


def _imprimir_banner_decisor(empresa: Empresa, decisor) -> None:
    """Muestra un Decisor enriquecido por la cascada Apollo→Hunter (Motor 3)."""
    from src.core.domain.models import EstadoCorreo

    _colores_estado = {
        EstadoCorreo.VERIFICADO: verde,
        EstadoCorreo.INFERIDO: amarillo,
        EstadoCorreo.NO_RESUELTO: gris,
        EstadoCorreo.REBOTADO: rojo,
    }
    color_fn = _colores_estado.get(decisor.estado_correo, gris)
    correo_str = str(decisor.correo) if decisor.correo else "(sin correo)"
    print(
        f"    {verde('✓')} {negrita(decisor.nombre)} — {decisor.cargo_original} "
        f"({empresa.nombre})"
    )
    print(
        f"      {gris('correo:')} {correo_str}  "
        f"{gris('estado:')} {color_fn(decisor.estado_correo.value)}  "
        f"{gris('confianza:')} {decisor.confianza_dato:.2f}  "
        f"{gris('autoridad:')} {decisor.autoridad_decision.value}"
    )


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
    apollo_key = os.getenv("APOLLO_API_KEY")
    adapter_ts = TheirStackAdapter(
        api_key=theirstack_key,
        tecnologias_objetivo=manifiesto.anclaje_tecnologico,
        max_empresas_discovery=TAMANO_BATCH_DISCOVERY,
    )
    adapter_apollo = ApolloDiscoveryAdapter(
        api_key=apollo_key,
        max_empresas_discovery=TAMANO_BATCH_APOLLO_DISCOVERY,
    )
    # Sin argumentos: construye un GroqKeyPool() que rota entre
    # GROQ_API_KEY_1..N del entorno (o GROQ_API_KEY como fallback de una
    # sola clave) ante rate limits — ver src/adapters/llm/groq_key_pool.py.
    adapter_pv = PropuestaValorAdapter()
    # Tercer origen del waterfall de tamaño (es_pyme verificado por la
    # entidad contratante) — solo aporta si la empresa tiene contratos SECOP.
    adapter_secop = SecopSocrataAdapter()
    # Paquete de Revisión Manual (persistente): registra evidencia
    # accionable para cada empresa PENDIENTE_REVISION_MANUAL/INDETERMINADO
    # y respeta decisiones humanas ya tomadas en corridas anteriores.
    adapter_revision = PaqueteRevisionAdapter()
    print(
        f"  {gris(f'Batch TheirStack (señales activas): {TAMANO_BATCH_DISCOVERY} empresas máx.')}\n"
        f"  {gris(f'Batch Apollo (TAM base, firmografía): {TAMANO_BATCH_APOLLO_DISCOVERY} empresas máx.')}\n"
    )

    # Motor 1 — Discovery de TAM base (Apollo, firmografía pura)
    empresas = ejecutar_discovery_combinado(manifiesto, adapter_apollo)

    if not empresas:
        print(f"\n{SEP}\n")
        print(f"  {amarillo('Sin empresas descubiertas. Verifica APOLLO_API_KEY.')}\n")
        sys.exit(0)

    # Motor 2B-D + Triangulación + Afinamiento (exclusión de competidores +
    # corroboración de tamaño), en ese orden, respetando barato→caro.
    # Signal-Based Selling v5.0: ScoreTriggerPolicy reemplaza el bool de
    # TriggerAggregationPolicy por un score numérico de urgencia con decay
    # diferencial CAUSA(90d)/EFECTO(45d).
    policy_score = ScoreTriggerPolicy()
    print(f"{SEP}")
    print(f"\n  {negrita('Filtrando competidores y triangulando señales por empresa...')}\n")
    print(f"{SEP2}\n")

    empresas_calificadas = 0
    empresas_excluidas_competencia = 0
    empresas_pendientes_revision_manual = 0
    empresas_descartadas_tamano = 0
    empresas_descartadas_geografia = 0
    idx_mostrado = 0

    # Acumula las empresas que califican (score >= UMBRAL_CALIFICACION) junto
    # con su score, para ordenarlas por urgencia descendente ANTES de pasarlas
    # al Motor 3 (regla del 74% de SHiFT!: gastar Apollo/Hunter primero en los
    # leads Tier 0 dobles, no en los Tier 1 simples).
    candidatos_motor3: list[tuple[Empresa, int, TierUrgencia]] = []

    for empresa in empresas:
        # Paso 0: si un humano YA decidió sobre esta empresa en una corrida
        # anterior (ver PaqueteRevisionAdapter), se respeta esa decisión sin
        # volver a gastar Capa 2 (LLM) en ella.
        decision_previa = _aplicar_decision_humana_persistida(empresa, adapter_revision)
        if decision_previa == ResultadoExclusionCompetidor.EXCLUIDO_DURO:
            empresas_excluidas_competencia += 1
            _imprimir_banner_exclusion(empresa, "confirmado por revisión humana previa")
            continue
        # decision_previa == PERMITIDO cae directo a Paso 2 (salta Paso 1).

        # Paso 1: Negative ICP (Capa 1 gratis → Capa 2 con costo si ambiguo).
        # Fail-closed: PENDIENTE_REVISION_MANUAL va a cola manual, NUNCA se
        # trata como PERMITIDO (fix Falla 1, caso Parcero/UK).
        if decision_previa != ResultadoExclusionCompetidor.PERMITIDO:
            veredicto, motivo = evaluar_exclusion_competidor(
                empresa, categoria_cliente, adapter_pv
            )
            if veredicto == ResultadoExclusionCompetidor.EXCLUIDO_DURO:
                empresas_excluidas_competencia += 1
                _imprimir_banner_exclusion(empresa, motivo)
                continue
            if veredicto == ResultadoExclusionCompetidor.PENDIENTE_REVISION_MANUAL:
                empresas_pendientes_revision_manual += 1
                _registrar_pendiente_con_evidencia(
                    empresa, motivo, adapter_pv, adapter_revision
                )
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
            _registrar_pendiente_con_evidencia(
                empresa, motivo_geo, adapter_pv, adapter_revision
            )
            _imprimir_banner_revision_manual(empresa, motivo_geo)
            continue

        # Paso 3: Waterfall de tamaño — descarta ENTERPRISE cuando el ICP pide SME.
        estado_tamano, tamano_consensuado = evaluar_consenso_tamano(
            empresa, adapter_ts, adapter_pv, adapter_secop
        )
        if (
            estado_tamano == EstadoConsensoTamano.CONSENSO
            and tamano_consensuado == TamanoEmpresa.ENTERPRISE
            and manifiesto.tamano_empresa == TamanoEmpresa.SME
        ):
            empresas_descartadas_tamano += 1
            _imprimir_banner_tamano_descartado(empresa, estado_tamano, tamano_consensuado)
            continue

        # Paso 4: recolección de triggers + scoring de urgencia (Signal-Based
        # Selling v5.0). El score numérico y el tier se muestran en el output.
        idx_mostrado += 1
        triggers = recolectar_triggers(empresa, adapter_ts, manifiesto, adaptadores_activos)
        score, tier_final, califica = policy_score.evaluar(triggers, adaptadores_activos)
        if califica:
            empresas_calificadas += 1
            candidatos_motor3.append((empresa, score, tier_final))
        imprimir_resultado_empresa(idx_mostrado, empresa, triggers, califica)
        _imprimir_score_urgencia(score, tier_final, califica)

    # ── Motor 3 — Enriquecimiento de Contactos (Apollo → Hunter) ──────────
    # Orquestación (Propuesta 1): ordenar candidatos por score_urgencia
    # descendente ANTES de invocar la cascada — gasta el presupuesto de
    # Apollo/Hunter primero en los leads Tier 0 dobles (score 480+), no en
    # los Tier 1 simples que apenas cruzaron el umbral (150).
    total_decisores = 0
    if candidatos_motor3:
        candidatos_motor3.sort(key=lambda item: item[1], reverse=True)

        print(f"{SEP}")
        print(
            f"\n  {negrita('MOTOR 3 — Enriquecimiento de Contactos')} "
            f"{gris(f'({len(candidatos_motor3)} empresa(s), ordenadas por score_urgencia desc.)')}\n"
        )
        print(f"{SEP2}\n")

        adapter_cascada = ApolloHunterCascadaAdapter()  # lee APOLLO_API_KEY / HUNTER_API_KEY
        cargos_objetivo = manifiesto.cargos_decisores

        for empresa, score, tier in candidatos_motor3:
            print(
                f"  {negrita(empresa.nombre)} "
                f"{gris(f'(score={score}, tier={tier.value})')}"
            )
            decisores = adapter_cascada.enriquecer(empresa, cargos_objetivo)
            if not decisores:
                print(f"    {gris('Sin decisores resueltos (0 créditos de Hunter gastados si Apollo no encontró perfiles válidos).')}\n")
                continue
            for decisor in decisores:
                _imprimir_banner_decisor(empresa, decisor)
            total_decisores += len(decisores)
            print()

    # Resumen
    print(f"{SEP}")
    print(f"\n  {negrita('Resumen del pipeline TBBC Real (con afinamiento):')}")
    print(f"    {verde('✓')} Empresas descubiertas:        {negrita(str(len(empresas)))}")
    print(f"    {rojo('✗')} Excluidas por competencia:    {negrita(str(empresas_excluidas_competencia))}")
    print(f"    {cian('~')} Pendientes revisión manual:   {negrita(str(empresas_pendientes_revision_manual))}")
    print(f"    {amarillo('✗')} Descartadas por geografía:    {negrita(str(empresas_descartadas_geografia))}")
    print(f"    {amarillo('✗')} Descartadas por tamaño:       {negrita(str(empresas_descartadas_tamano))}")
    print(f"    {verde('✓')} Analizadas en Motor 2:        {negrita(str(idx_mostrado))}")
    print(f"    {verde('✓')} Califican para Motor 3:       {negrita(str(empresas_calificadas))} {gris(f'(ScoreTriggerPolicy, umbral {ScoreTriggerPolicy.UMBRAL_CALIFICACION})')}")
    print(f"    {gris('Tecnologías buscadas:         ')}{', '.join(manifiesto.anclaje_tecnologico)}")
    print(f"    {gris('Categoría detectada (cliente):')}{manifiesto.categoria_empresa.value}")
    tasa = (empresas_calificadas / len(empresas) * 100) if empresas else 0
    print(f"    {gris('Tasa de calificación bruta:   ')}{tasa:.1f}%")
    print(f"    {verde('✓')} Decisores enriquecidos (M3):  {negrita(str(total_decisores))} {gris('(Apollo → Hunter, ordenado por urgencia)')}")
    print(f"\n  {gris('Próximo paso: Motor 4 — redactar y enviar outbound (Tavily + Groq + Resend)')}\n")


if __name__ == "__main__":
    main()
