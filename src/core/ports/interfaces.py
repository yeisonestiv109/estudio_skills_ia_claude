"""
Puertos del Dominio (Interfaces Hexagonales) — El Prospector.

Transcripción fiel de `10-Memoria_Consolidada/modelos_dominio_core.md` (sección 6).

CRÍTICO:
    Estas interfaces abstractas son el contrato que el Core exige a los
    adaptadores. Ningún adaptador puede ser instanciado directamente por el
    Core. Solo se inyectan a través de estas interfaces (Inversión de
    Dependencias — la 'D' de SOLID).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.domain.models import (
    CategoriaEmpresa,
    ContextoRAG,
    Decisor,
    Empresa,
    EstimacionTamano,
    ManifiestoICP,
    Mensaje,
    ResultadoEnvio,
    Trigger,
)


class PuertoFuenteTriggers(ABC):
    """Puerto que todo adaptador del Motor 2 debe implementar."""

    @abstractmethod
    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Dada una Empresa, retorna la lista de Triggers detectados.

        Contrato: nunca lanza excepción hacia el Core. Los errores de red
        se capturan internamente y retornan lista vacía con log.
        """
        ...


class PuertoDescubridorEmpresas(ABC):
    """
    Puerto Caso B: Descubrimiento de empresas nuevas a partir de un ICP.

    Semántica distinta a PuertoFuenteTriggers:
        - PuertoFuenteTriggers  → SCORING:    ¿Tiene señales ESTA empresa conocida?
        - PuertoDescubridorEmpresas → DISCOVERY: ¿Qué empresas desconocidas encajan con este ICP?

    Separación justificada por:
        1. Contratos de entrada distintos (Empresa vs ManifiestoICP).
        2. Principio de Segregación de Interfaces (ISP — SOLID).
        3. Patrón de la industria: Apollo separa /enrich de /search;
           Clay distingue tabla-con-filas (enrichment) de tabla-vacía (discovery).

    Los adaptadores que soportan discovery (ej. TheirStackAdapter) implementan
    AMBOS puertos. Los que solo soportan scoring (ej. GoogleAlertsRSSAdapter)
    solo implementan PuertoFuenteTriggers.
    """

    @abstractmethod
    def descubrir_empresas(self, manifesto: ManifiestoICP) -> list[Empresa]:
        """
        Dado un ManifiestoICP, retorna una lista de Empresas candidatas
        que encajan con los criterios del ICP.

        Las empresas retornadas se crean con estado=EstadoEmpresa.DESCUBIERTA
        para indicar que son candidatas no verificadas manualmente.

        El orquestador de la capa de aplicación ejecuta luego
        PuertoFuenteTriggers.obtener_triggers() sobre cada empresa descubierta
        para validar señales antes de enviarlas al Motor 3.

        Contrato: nunca lanza excepción hacia el Core. Los errores de red
        se capturan internamente y retornan lista vacía con log.
        """
        ...


class PuertoEstimadorTamano(ABC):
    """
    Puerto Motor 2 — Estimación cruda de tamaño de empresa (waterfall de tamaño).

    Puerto SECUNDARIO y OPCIONAL: no todos los adaptadores del Motor 2 pueden
    estimar tamaño (ej. GoogleAlertsRSSAdapter no tiene señal firmográfica).
    Los que sí pueden (TheirStackAdapter, WappalyzerHeadlessAdapter, etc.)
    implementan este puerto ADEMÁS de PuertoFuenteTriggers — mismo patrón dual
    que ya usa TheirStackAdapter con PuertoDescubridorEmpresas (ISP — SOLID).

    Alimenta a PoliticaCorroboracionTamano, que exige consenso de al menos 2
    orígenes distintos antes de aceptar un TamanoEmpresa como válido.
    """

    @abstractmethod
    def estimar_tamano(self, empresa: Empresa) -> EstimacionTamano | None:
        """
        Retorna una EstimacionTamano cruda para la Empresa dada, o None si
        este origen no tiene señal suficiente para pronunciarse (silencio
        válido — no todo origen tiene que opinar sobre toda empresa).

        Contrato de error: nunca lanza excepción hacia el Core. Errores de
        red/API → None con log interno (idéntico al resto de puertos).
        """
        ...


class PuertoClasificadorPropuestaValor(ABC):
    """
    Puerto Motor 2 — Capa 2 del Negative ICP (análisis semántico profundo).

    Se invoca SOLO cuando PoliticaExclusionCompetidores.evaluar() retorna
    ResultadoExclusionCompetidor.REQUIERE_ANALISIS_SEMANTICO — es decir,
    únicamente sobre el subconjunto ambiguo de candidatos, no sobre el 100%
    del flujo (control de costo: LLM solo donde la Capa 1, gratis y pura, no
    pudo decidir).

    Lee el texto público de la empresa candidata (ej. "about us"/homepage) y
    usa un LLM para inferir si su lenguaje corresponde a un "vendor" (vende
    tecnología/servicios a terceros) o un "buyer" (usa tecnología para su
    propio negocio) — la misma heurística semántica documentada en la
    investigación de mercado (ver prospector-m3-m4-design.md).
    """

    @abstractmethod
    def clasificar(self, empresa: Empresa) -> CategoriaEmpresa | None:
        """
        Retorna la CategoriaEmpresa inferida a partir del texto público de la
        empresa candidata, o None si no hay suficiente texto/señal para
        clasificar con confianza.

        Contrato de error: nunca lanza excepción hacia el Core. Fallo de red,
        de scraping o del LLM → None con log interno. El orquestador decide
        qué hacer con un None (ej. enviar a cola manual, no descartar de plano).
        """
        ...


class PuertoAnalizadorICP(ABC):
    """Puerto que el adaptador LLM del Motor 1 debe implementar."""

    @abstractmethod
    def analizar(self, descripcion_libre: str) -> ManifiestoICP:
        """
        Dado texto libre, retorna un ManifiestoICP validado por Pydantic.

        El ManifiestoICP incluye categoria_empresa y es_gov_facing, que la
        AdapterRoutingPolicy usa para decidir qué adaptadores activar.

        Si el LLM no puede estructurar los datos, lanza ValueError con las
        preguntas de clarificación (máximo 3).
        """
        ...


class PuertoEnriquecedorContactos(ABC):
    """
    Puerto Caso C: Enriquecimiento de contactos (Motor 3).

    Semántica respecto a los puertos existentes:
        - PuertoDescubridorEmpresas   → DISCOVERY:   ¿Qué empresas encajan con el ICP?
        - PuertoFuenteTriggers        → SCORING:     ¿Tiene señales esta empresa?
        - PuertoEnriquecedorContactos → ENRICHMENT:  ¿Quién decide dentro de esta empresa
                                                      y cómo lo contacto de forma verificable?

    Firma stateless (decisión de arquitectura, 14-Jul-2026): el adaptador no
    retiene contexto de job entre llamadas. `cargos` viaja explícito en cada
    invocación (normalmente ManifiestoICP.cargos_decisores, resuelto por el
    orquestador), lo que habilita ejecución paralela segura (thread-safe)
    sobre múltiples empresas sin cargar un ManifiestoICP completo en el puerto.
    """

    @abstractmethod
    def enriquecer(self, empresa: Empresa, cargos: list[str]) -> list[Decisor]:
        """
        Dada una Empresa YA calificada por TriggerAggregationPolicy y la lista
        de cargos objetivo del ICP, retorna los Decisores encontrados con
        estado_correo y confianza_dato ya resueltos (ver PoliticaMapeoEstadoCorreo
        en 10-Memoria_Consolidada/tecnico/prospector-m3-m4-design.md §3.2).

        Contrato de error: nunca lanza excepción hacia el Core. Errores de red,
        rate limit o caída de proveedor se capturan internamente y retornan
        lista vacía con log.

        Contrato de salida: la lista puede venir vacía (empresa sin decisores
        resolubles); es un resultado válido, no un error. Este puerto NO filtra
        por calidad — devuelve todo lo que encontró. El filtrado hacia el Motor 4
        lo hace UmbralCalidadDecisor en la capa de orquestación.
        """
        ...


# ===========================================================================
# MOTOR 4 (Outbound RAG) — Puertos
# Diseño: 10-Memoria_Consolidada/tecnico/prospector-m4-design.md §5
# ===========================================================================
class PuertoContextoRAG(ABC):
    """
    Puerto Motor 4 — Recuperación de contexto (Caso D: RAG).

    Recupera evidencia fresca y verificable sobre la empresa/decisor para
    fundamentar el mensaje y evitar alucinación del LLM.
    Impl: TavilyContextoAdapter, PerplexityContextoAdapter.
    """

    @abstractmethod
    def obtener_contexto(
        self, empresa: Empresa, triggers: list[Trigger]
    ) -> ContextoRAG:
        """
        Retorna evidencia citable (snippets + URLs) alineada con los triggers.

        Contrato: nunca lanza excepción hacia el Core. Error de red o sin
        resultados → ContextoRAG vacío (evidencias=[], fuentes=[]).
        """
        ...


class PuertoRedactorOutbound(ABC):
    """
    Puerto Motor 4 — Redacción del mensaje (Caso E: LLM outbound).

    Genera un Mensaje tipado a partir del decisor + triggers + contexto RAG.
    Impl: LLMRedactorAdapter (Groq/Claude) detrás del puerto, salida validada.
    """

    @abstractmethod
    def redactar(
        self,
        decisor: Decisor,
        empresa: Empresa,
        triggers: list[Trigger],
        contexto: ContextoRAG,
    ) -> Mensaje:
        """
        Retorna un Mensaje en estado BORRADOR. NUNCA envía.

        Contrato: nunca lanza excepción hacia el Core. Si el LLM falla, retorna
        un Mensaje con estado EstadoMensaje.ERROR_REDACCION y log interno.
        """
        ...


class PuertoEnvioCorreo(ABC):
    """
    Puerto Motor 4 — Envío (Caso F: efecto externo).

    ÚNICO puerto del sistema que produce efectos externos irreversibles (enviar
    un correo real). Reporta el resultado real del envío para alimentar el lazo
    de retroalimentación de rebotes. Impl: ProveedorEnvioAdapter (Resend).
    """

    @abstractmethod
    def enviar(self, mensaje: Mensaje, decisor: Decisor) -> ResultadoEnvio:
        """
        Envía un Mensaje APROBADO y retorna el ResultadoEnvio real.

        Contrato: nunca lanza excepción hacia el Core. Error de red o de
        proveedor → ResultadoEnvio.ERROR con log interno.
        """
        ...
