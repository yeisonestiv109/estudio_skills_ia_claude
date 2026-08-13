"""
TavilyContextoAdapter — implementación de PuertoContextoRAG.

Diseño: 02_Lineas_de_Producto/Outbound_Prospector/docs/tecnico/prospector-m4-design.md §5.

Rol en el pipeline (Motor 4, paso 2 de la máquina de estados del Mensaje):
recupera evidencia fresca y verificable sobre la empresa (vía búsqueda web de
Tavily) para fundamentar el mensaje del PuertoRedactorOutbound y reducir el
riesgo de alucinación del LLM.

API de Tavily: REST simple (POST /search), sin SDK — usamos `requests`, ya
pineado en requirements.txt, igual que el resto de adaptadores del proyecto.

Contrato de error: nunca propaga excepción al Core. Cualquier fallo de red,
rate limit o respuesta inesperada retorna ContextoRAG vacío (evidencias=[],
fuentes=[]) con log, sin romper la cadena de ejecución del Motor 4.
"""

from __future__ import annotations

import logging
import os

import requests

from src.core.domain.models import ContextoRAG, Empresa, Trigger
from src.core.ports.interfaces import PuertoContextoRAG

logger = logging.getLogger(__name__)

_TAVILY_SEARCH_URL = "https://api.tavily.com/search"
_REQUEST_TIMEOUT_SECS = 15
_MAX_RESULTADOS = 5
_MAX_LONGITUD_SNIPPET = 300


class TavilyContextoAdapter(PuertoContextoRAG):
    """
    Args:
        api_key: Clave de API de Tavily. Si None, lee de TAVILY_API_KEY.
        max_resultados: Tope de resultados de búsqueda a convertir en evidencias.
    """

    def __init__(
        self, api_key: str | None = None, max_resultados: int = _MAX_RESULTADOS
    ) -> None:
        self._api_key = api_key or os.getenv("TAVILY_API_KEY")
        self._max_resultados = max_resultados
        if not self._api_key:
            logger.warning(
                "TAVILY_API_KEY no configurada. "
                "TavilyContextoAdapter retornará ContextoRAG vacío hasta que se configure."
            )

    def describir_empresa(self, empresa: Empresa) -> str | None:
        """
        Respaldo de contexto para la clasificación semántica del Motor 2
        (Negative ICP / fit de comprador) cuando la homepage NO se pudo leer
        (DNS muerto, SPA sin SSR, 403). Busca en la web una descripción de la
        empresa y devuelve el texto concatenado de los resultados (o None si no
        hay API key, no hay resultados, o error).

        Se inyecta como `buscador_respaldo` en PropuestaValorAdapter. Anti-bazuca:
        el adaptador solo lo invoca cuando el scraping de homepage falló, así que
        no consume búsquedas para las empresas cuya homepage sí se leyó.

        Contrato de error: nunca propaga excepción (retorna None).
        """
        if not self._api_key:
            return None

        query = (
            f'"{empresa.nombre}" {empresa.dominio} '
            "a qué se dedica la empresa perfil compañía"
        )
        try:
            response = requests.post(
                _TAVILY_SEARCH_URL,
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": self._max_resultados,
                    "include_answer": True,
                },
                headers={"Content-Type": "application/json"},
                timeout=_REQUEST_TIMEOUT_SECS,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001 — respaldo opcional, nunca romper
            logger.warning(
                "Tavily: respaldo de descripción falló para '%s': %s. Sin texto.",
                empresa.nombre,
                exc,
            )
            return None

        partes: list[str] = []
        # El "answer" sintetizado de Tavily (si include_answer) es el mejor
        # resumen; va primero.
        respuesta_sintetizada = (data.get("answer") or "").strip()
        if respuesta_sintetizada:
            partes.append(respuesta_sintetizada)
        for r in data.get("results", []) or []:
            contenido = (r.get("content") or "").strip()
            if contenido:
                partes.append(contenido)

        if not partes:
            logger.debug(
                "Tavily: respaldo sin resultados para '%s'.", empresa.nombre
            )
            return None

        texto = "\n".join(partes)
        # Mismo tope que la lectura de homepage para no inflar el prompt del LLM.
        return texto[:2000]

    def obtener_contexto(
        self, empresa: Empresa, triggers: list[Trigger]
    ) -> ContextoRAG:
        """
        Implementa PuertoContextoRAG.obtener_contexto().

        Construye una query de búsqueda a partir del nombre de la empresa
        (siempre) y, si hay triggers, del más reciente/relevante (mejora la
        alineación entre el contexto recuperado y el gancho de personalización
        que usará el redactor).
        """
        if not self._api_key:
            return ContextoRAG()

        query = self._construir_query(empresa, triggers)

        try:
            logger.info("Tavily: buscando contexto para '%s'", empresa.nombre)
            response = requests.post(
                _TAVILY_SEARCH_URL,
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": self._max_resultados,
                },
                headers={"Content-Type": "application/json"},
                timeout=_REQUEST_TIMEOUT_SECS,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            logger.warning(
                "Tavily: timeout buscando contexto para '%s'. ContextoRAG vacío.",
                empresa.nombre,
            )
            return ContextoRAG()
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Tavily: HTTP %s para '%s'. ContextoRAG vacío.",
                exc.response.status_code if exc.response else "?",
                empresa.nombre,
            )
            return ContextoRAG()
        except requests.exceptions.RequestException as exc:
            logger.error(
                "Tavily: error de red para '%s': %s. ContextoRAG vacío.",
                empresa.nombre,
                exc,
            )
            return ContextoRAG()
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error(
                "Tavily: error inesperado para '%s': %s. ContextoRAG vacío.",
                empresa.nombre,
                exc,
            )
            return ContextoRAG()

        return self._parsear_resultados(data, empresa)

    def _construir_query(self, empresa: Empresa, triggers: list[Trigger]) -> str:
        base = f'"{empresa.nombre}" noticias recientes'
        if triggers:
            # El trigger más reciente por fecha_evento es el más relevante
            # para alinear el contexto con el gancho de personalización.
            triggers_con_fecha = [t for t in triggers if t.fecha_evento is not None]
            if triggers_con_fecha:
                trigger_relevante = max(
                    triggers_con_fecha, key=lambda t: t.fecha_evento
                )
                base = f"{base} {trigger_relevante.descripcion[:80]}"
        return base

    def _parsear_resultados(self, data: dict, empresa: Empresa) -> ContextoRAG:
        resultados = data.get("results", [])
        if not isinstance(resultados, list) or not resultados:
            logger.debug("Tavily: 0 resultados para '%s'.", empresa.nombre)
            return ContextoRAG()

        evidencias: list[str] = []
        fuentes: list[str] = []
        for r in resultados:
            contenido = (r.get("content") or "").strip()
            url = (r.get("url") or "").strip()
            if not contenido or not url:
                continue
            snippet = (
                contenido[:_MAX_LONGITUD_SNIPPET] + "..."
                if len(contenido) > _MAX_LONGITUD_SNIPPET
                else contenido
            )
            evidencias.append(snippet)
            fuentes.append(url)

        logger.info(
            "Tavily: %d evidencia(s) recuperadas para '%s'.",
            len(evidencias),
            empresa.nombre,
        )
        return ContextoRAG(evidencias=evidencias, fuentes=fuentes)
