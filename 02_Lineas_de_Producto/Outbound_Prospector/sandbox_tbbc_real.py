"""
Sandbox TBBC Real — Corrida del ICP real de TBBC (00-contexto-cliente.md §4).
Ejecuta Motor 1 (Groq) → Filtro Negative ICP → Waterfall de Tamaño → Motor 2
(5 fuentes) sin input() interactivo.

Negative ICP — 100% semántico (LLM), sin heurística de nombre (24-jul-2026):
    - Se ELIMINÓ por completo la Capa 1 "gratis" que matcheaba el NOMBRE de la
      empresa contra un patrón de palabras clave de vendor de TI (incluido el
      prefijo "tecnolog"). Producía falsos positivos (ej. "Tecnoaguas", que NO
      es vendor de TI) y falsos negativos (vendors sin la palabra clave en el
      nombre). Decisión del fundador: nada hardcodeado; el único juez es el LLM.
    - PropuestaValorAdapter (LLM sobre la homepage) es AHORA el único evaluador
      del Negative ICP: lee la propuesta de valor real del candidato y decide
      es_vendor_it (True/False/None). La misma llamada (cacheada por instancia)
      aporta además tipo_organizacion, pais_hq y una EstimacionTamano, así que
      no añade un costo nuevo para las empresas que de todos modos pasan por
      esos otros gates. Fail-CLOSED: es_vendor_it=None → revisión manual.
    - PoliticaCorroboracionTamano: exige que TheirStack y PropuestaValorAdapter
      corroboren el tamaño antes de aceptarlo. Si el consenso dice ENTERPRISE
      y el ICP de TBBC pide SME, la empresa se descarta antes de llegar a M3.

Signal-First Discovery (25-jul-2026) — REVIERTE el "Apollo-only" del 21-jul:
    Motor 1 ahora descubre el universo de trabajo DESDE una fuente de TRIGGER
    (TheirStack: empresas con vacantes técnicas), NO desde firmografía ciega
    (Apollo). Fundamento (SHiFT! + ABM + investigación web): no buscar por
    tamaño/sector y esperar señal (eso construía el Tier-3 TAM y traía 60% de
    colegios/ONGs que el gate de tipo descartaba), sino arrancar por el evento
    que abre la "ventana de insatisfacción" y validar el fit después.
    - TheirStack DISCOVERER primario (ventana 90d): trae empresas con vacantes;
      el aging >=45d las tiera a TIER_0 (fallo de reclutamiento = dolor de TBBC).
      Como filtra por tecnología del ICP, NO devuelve colegios/fundaciones.
    - SECOP permanece como fuente de CRUCE de señal (CAUSA → Regla de Oro con
      el EFECTO de TheirStack). SECOP-como-discoverer queda pendiente: da
      nombres sin dominio, y el downstream (Negative ICP homepage) exige
      dominio → requiere un resolutor de dominio (capa de enriquecimiento,
      diferida). Ver bitácora 2026-07-25.
    - Apollo SALE del loop M1/M2 (queda para enriquecimiento M3 más adelante).

Uso:
    .venv\\Scripts\\python.exe sandbox_tbbc_real.py

Requisitos en .env:
    GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxx        (obligatorio — M1 y Capa 2)
    THEIRSTACK_API_KEY=ts_xxxxxxxxxxxxxxxxxx   (obligatorio — DISCOVERER primario
                                                 Signal-First + señales de vacantes, Motor 2)
    SECOP_APP_TOKEN=xxxxxxxxxxxxxxxxxx         (opcional — cruce de señal CAUSA, Motor 2;
                                                 usar 'Token de la aplicación', NO 'Clave API')
    APOLLO_API_KEY=apllo_xxxxxxxxxxxxxxxxxx    (opcional — solo enriquecimiento Motor 3,
                                                 ya NO se usa en el discovery del Motor 1)
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
from src.adapters.llm.groq_key_pool import GroqKeyPool
from src.adapters.enrichment.apollo_hunter_cascada_adapter import (
    ApolloHunterCascadaAdapter,
)
from src.adapters.discovery.apollo_discovery_adapter import (
    ApolloDiscoveryAdapter,
)
from src.adapters.revision_manual.paquete_revision_adapter import (
    EstadoRevisionHumana,
    PaqueteRevisionAdapter,
)
from src.adapters.outbound.tavily_contexto_adapter import TavilyContextoAdapter
from src.adapters.triggers.propuesta_valor_adapter import PropuestaValorAdapter
from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
from src.core.domain.dominio import pais_por_tld
from src.core.domain.models import (
    EstadoConsensoTamano,
    EstadoValidacionGeografica,
    Empresa,
    EstimacionTamano,
    ManifiestoICP,
    OrigenTrigger,
    PAIS_DESCONOCIDO,
    ResultadoExclusionCompetidor,
    TamanoEmpresa,
    TierUrgencia,
    TipoOrganizacion,
)
from src.core.domain.policies import (
    AdapterRoutingPolicy,
    PoliticaCorroboracionTamano,
    PoliticaFitComprador,
    PoliticaTipoOrganizacion,
    PoliticaValidacionGeografica,
    ScoreTriggerPolicy,
)

# ── BATCH DE DISCOVERY (Signal-First, TheirStack) ─────────────────────────
# Este número es el LÍMITE DE VACANTES que TheirStack trae en la consulta de
# discovery (no de empresas): varias vacantes de la misma empresa se deduplican
# a un solo objeto Empresa, así que el nº de empresas descubiertas es menor.
#
# TOPE = 25: el PLAN FREE de TheirStack rechaza (HTTP 403, error E-020
# "Premium functionality limitation") cualquier `limit` > 25 por página.
# Confirmado en vivo (25-jul-2026): limit=25 → 200 OK; limit=50 → 403. Con un
# plan de pago se podría subir (y paginar). 25 es el máximo del plan actual.
TAMANO_BATCH_DISCOVERY: int = 25

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
def ejecutar_discovery_hibrido(
    manifiesto: ManifiestoICP,
    adapter_apollo: ApolloDiscoveryAdapter,
) -> list[Empresa]:
    """
    Discovery Híbrido (Apollo para TAM, TheirStack para scoring).
    Descubre el universo de trabajo usando firmografía pura (Apollo).
    """
    empresas_raw = adapter_apollo.descubrir_empresas(manifiesto)

    dominios_vistos: set[str] = set()
    empresas: list[Empresa] = []
    for e in empresas_raw:
        if not e.dominio or e.dominio in dominios_vistos:
            continue
        dominios_vistos.add(e.dominio)
        empresas.append(e)

    print(
        f"  {gris('Discovery Híbrido (Apollo para TAM, filtros anti-basura aplicados):')} "
        f"Total={negrita(str(len(empresas)))} empresa(s) en universo base"
    )
    return empresas


# ---------------------------------------------------------------------------
# Negative ICP — evaluación 100% semántica (LLM), sin heurística de nombre
# ---------------------------------------------------------------------------
# DECISIÓN 24-jul-2026 (fundador): se eliminó por completo la Capa 1 "gratis"
# que juzgaba por el NOMBRE de la empresa (palabras clave + prefijo "tecnolog").
# Motivo: nada hardcodeado. Un keyword-match sobre el nombre produce falsos
# positivos ("Tecnoaguas" NO es vendor de TI) y falsos negativos (vendors sin
# la palabra clave en su nombre). El ÚNICO juez del Negative ICP es ahora el
# análisis semántico del LLM sobre la propuesta de valor real (homepage), vía
# PropuestaValorAdapter.es_vendor_it().
def evaluar_exclusion_competidor(
    empresa: Empresa,
    adapter_pv: PropuestaValorAdapter,
) -> tuple[ResultadoExclusionCompetidor, str]:
    """
    Exclusión de competidores para UNA empresa candidata, decidida
    ÍNTEGRAMENTE por análisis semántico del LLM (PropuestaValorAdapter).

    Retorna (veredicto_final, motivo_legible): PERMITIDO, EXCLUIDO_DURO o
    PENDIENTE_REVISION_MANUAL (fail-closed cuando el LLM no pudo determinar
    es_vendor_it).

    FAIL-CLOSED (fix Falla 1, caso Parcero/UK): si es_vendor_it() no pudo
    determinarse (scraping falló, SPA sin texto útil, LLM no disponible),
    NUNCA se interpreta como "confirmado no competidor" — va a revisión
    manual. Solo es_vendor_it==False (confirmado positivamente que NO es
    vendor) produce PERMITIDO.
    """
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
    2. ccTLD del dominio (fix Falla ccTLD, caso Revista Dinero/dinero.com.ve):
       si Empresa.pais es desconocido, se intenta derivar el país del SUFIJO
       del dominio (estándar IANA) con pais_por_tld(). Es gratis (no red, no
       LLM) y resuelve inequívocamente los .ve/.mx/.gov.co/.com.co/etc. antes
       de gastar el scraping caro. Solo afirma país cuando el sufijo es
       inequívoco; ante ambigüedad (.co simple, .com, .io) retorna None y el
       waterfall sigue.
    3. Si el ccTLD tampoco resolvió, se recurre a PropuestaValorAdapter.
       pais_hq() (Capa 2, con costo — ya cacheada si la Capa 2 corrió antes
       para esta misma empresa en evaluar_exclusion_competidor()).

    Retorna (estado, motivo_legible). INDETERMINADO es fail-closed: el
    llamador debe tratarlo como revisión manual, nunca como aprobación.
    """
    politica = PoliticaValidacionGeografica()

    pais_candidato = empresa.pais
    origen_dato = "TheirStack (discovery)"
    if not pais_candidato or pais_candidato.strip().upper() == PAIS_DESCONOCIDO:
        pais_tld = pais_por_tld(empresa.dominio)
        if pais_tld:
            pais_candidato = pais_tld
            origen_dato = "ccTLD (sufijo de dominio, estándar IANA)"
        else:
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
) -> tuple[EstadoConsensoTamano, TamanoEmpresa | None, list[EstimacionTamano]]:
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

    estado, tamano = politica.corroborar(estimaciones)
    return estado, tamano, estimaciones


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


def _imprimir_banner_tipo_descartado(empresa: Empresa, tipo: TipoOrganizacion) -> None:
    print(f"  {amarillo('▒' * 64)}")
    print(f"  {amarillo('▒')}  {amarillo(negrita('DESCARTADA POR TIPO DE ORGANIZACIÓN'))} — {negrita(empresa.nombre)}")
    print(f"  {amarillo('▒')}  {gris(f'Tipo detectado (LLM homepage): {tipo.value} — el ICP de TBBC busca EMPRESA_PRIVADA')}")
    print(f"  {amarillo('▒')}  {gris('Costo evitado: 0 créditos de Motor 3 gastados en un ente no-empresa.')}")
    print(f"  {amarillo('▒' * 64)}\n")


def _imprimir_banner_fit_descartado(empresa: Empresa) -> None:
    print(f"  {amarillo('▒' * 64)}")
    print(f"  {amarillo('▒')}  {amarillo(negrita('DESCARTADA POR FIT DE COMPRADOR'))} — {negrita(empresa.nombre)}")
    print(f"  {amarillo('▒')}  {gris('Multinacional / filial (LLM homepage): fuera del ICP (PYME colombiana independiente).')}")
    print(f"  {amarillo('▒')}  {gris('Su compra de TI suele ser global/centralizada — no la decide una consultora local.')}")
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
    print(f"\n  {negrita('Categoría del cliente (TBBC), detectada por Motor 1:')} {amarillo(categoria_cliente.value)}")
    print(f"  {gris('(El Negative ICP ya NO usa la categoría ni el nombre; decide 100% por LLM sobre la homepage.)')}\n")

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
    # GroqKeyPool COMPARTIDO: un solo pool que rota entre GROQ_API_KEY_1..N
    # del entorno (o GROQ_API_KEY como fallback de una sola clave) ante rate
    # limits — ver src/adapters/llm/groq_key_pool.py. Se comparte entre
    # PropuestaValorAdapter (Capa 2 Negative ICP / tamaño / país) y la
    # verificación semántica de GoogleAlertsRSSAdapter (dentro de
    # recolectar_triggers) para NO duplicar pools ni el estado de cooldown.
    groq_pool = GroqKeyPool()
    # Tavily como RESPALDO de contexto (26-jul-2026): si la homepage no se puede
    # leer (DNS muerto, SPA, 403), PropuestaValorAdapter busca en la web una
    # descripción de la empresa para clasificar en vez de caer a revisión manual
    # por falla técnica. Solo se construye si hay TAVILY_API_KEY; anti-bazuca:
    # solo gasta una búsqueda cuando el scraping falló.
    tavily_key = os.getenv("TAVILY_API_KEY")
    tavily_ctx = TavilyContextoAdapter() if tavily_key else None
    if tavily_ctx is not None:
        print(f"  {gris('Tavily: respaldo de contexto web activo (homepages muertas/SPA).')}")
    adapter_pv = PropuestaValorAdapter(
        key_pool=groq_pool,
        buscador_respaldo=(tavily_ctx.describir_empresa if tavily_ctx else None),
    )
    # Tercer origen del waterfall de tamaño (es_pyme verificado por la
    # entidad contratante) — solo aporta si la empresa tiene contratos SECOP.
    adapter_secop = SecopSocrataAdapter()
    # Paquete de Revisión Manual (persistente): registra evidencia
    # accionable para cada empresa PENDIENTE_REVISION_MANUAL/INDETERMINADO
    # y respeta decisiones humanas ya tomadas en corridas anteriores.
    adapter_revision = PaqueteRevisionAdapter()
    apollo_key = os.getenv("APOLLO_API_KEY")
    adapter_apollo = ApolloDiscoveryAdapter(
        api_key=apollo_key,
        max_empresas_discovery=TAMANO_BATCH_DISCOVERY,
    )

    print(
        f"  {gris(f'Discovery Híbrido (Apollo, límite {TAMANO_BATCH_DISCOVERY} empresas) → Scoring por TheirStack/SECOP.')}\n"
    )

    # Motor 1 — Discovery Híbrido (Apollo: firmografía amplia)
    empresas = ejecutar_discovery_hibrido(manifiesto, adapter_apollo)

    if not empresas:
        print(f"\n{SEP}\n")
        print(f"  {amarillo('Sin empresas descubiertas. Verifica THEIRSTACK_API_KEY y que el ICP tenga anclaje_tecnologico.')}\n")
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
    empresas_descartadas_tipo = 0
    empresas_descartadas_fit = 0
    idx_mostrado = 0

    politica_tipo_org = PoliticaTipoOrganizacion()
    politica_fit = PoliticaFitComprador()

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
                empresa, adapter_pv
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

        # Paso 1.5: Gate de TIPO DE ORGANIZACIÓN (fix: excluir gobierno/ONG/
        # medios/educación/gremio). Reutiliza la MISMA llamada LLM cacheada
        # que ya corrió en el Negative ICP (Capa 2) — sin gasto adicional.
        # Fail-OPEN en este eje: tipo indeterminado (None) NO excluye; solo un
        # tipo no-empresa afirmado positivamente descarta la empresa.
        tipo_org = adapter_pv.tipo_organizacion(empresa)
        if not politica_tipo_org.es_apta(tipo_org):
            empresas_descartadas_tipo += 1
            _imprimir_banner_tipo_descartado(empresa, tipo_org)
            continue

        # Paso 1.6: Gate de FIT DE COMPRADOR (B, 26-jul-2026). Descarta
        # multinacionales/filiales (fuera del ICP: PYME colombiana
        # independiente), usando la MISMA llamada LLM cacheada — 0 costo extra.
        # Fail-OPEN: None (sin señal) NO excluye; solo es_multinacional=True.
        # EXCEPCIÓN SECOP: una multinacional CON contrato público local activo
        # SÍ se permite (la plata pública local valida la compra local — caso
        # Atrys). El chequeo SECOP solo se hace si el LLM dijo multinacional y
        # SECOP está enrutado, y reutiliza la cache del adaptador (0 costo extra
        # cuando el scoring lo vuelva a pedir).
        es_multi = adapter_pv.es_multinacional(empresa)
        tiene_secop = False
        if es_multi and OrigenTrigger.SECOP_SOCRATA in adaptadores_activos:
            try:
                tiene_secop = bool(adapter_secop.obtener_triggers(empresa))
            except Exception:
                tiene_secop = False
        if not politica_fit.es_apta(es_multi, tiene_trigger_secop=tiene_secop):
            empresas_descartadas_fit += 1
            _imprimir_banner_fit_descartado(empresa)
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

        # Paso 3: Waterfall de tamaño — gate ENDURECIDO (25-jul-2026).
        # Antes solo descartaba CONSENSO=ENTERPRISE, y solo si había 2 orígenes
        # que corroboraran (fail-open ante dato único/ausente) → dejaba pasar
        # scale-ups (ej. Magneto) disfrazados de SME por el default de
        # _inferir_tamano. Ahora es ASIMÉTRICO respecto al ICP:
        #   (a) Número firmográfico DURO (employee_count de TheirStack) por sí
        #       solo basta para EXCLUIR un "demasiado grande" (> tier del ICP):
        #       es un dato duro, no una inferencia — no requiere corroboración
        #       para descartar. Fail-CLOSED en el eje "no malgastar en grandes".
        #   (b) Consenso corroborado de un tier mayor al ICP también excluye
        #       (incluye MID_MARKET, no solo ENTERPRISE).
        # Confirmar un tamaño como VÁLIDO (inclusión) sigue requiriendo 2
        # orígenes (PoliticaCorroboracionTamano); esta asimetría es deliberada.
        estado_tamano, tamano_consensuado, estimaciones_tamano = evaluar_consenso_tamano(
            empresa, adapter_ts, adapter_pv, adapter_secop
        )
        excede, tamano_reportado = PoliticaCorroboracionTamano().excede_icp(
            estimaciones_tamano,
            estado_tamano,
            tamano_consensuado,
            manifiesto.tamano_empresa,
        )
        if excede:
            empresas_descartadas_tamano += 1
            _imprimir_banner_tamano_descartado(empresa, estado_tamano, tamano_reportado)
            continue

        # Paso 4: recolección de triggers + scoring de urgencia (Signal-Based
        # Selling v5.0). El score numérico y el tier se muestran en el output.
        idx_mostrado += 1
        triggers = recolectar_triggers(
            empresa, adapter_ts, manifiesto, adaptadores_activos, groq_pool
        )
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
    print(f"    {amarillo('✗')} Descartadas por tipo org.:    {negrita(str(empresas_descartadas_tipo))}")
    print(f"    {amarillo('✗')} Descartadas por fit (multin.):{negrita(str(empresas_descartadas_fit))}")
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
