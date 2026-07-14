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

from src.core.domain.models import Empresa, ManifiestoICP, Trigger


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
