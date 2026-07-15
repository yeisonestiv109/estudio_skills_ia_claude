"""
ApolloClient — cliente HTTP delgado para la API de Apollo.io.

Rol en la cascada (ver `tecnico/prospector-m3-m4-design.md` §3.2): DESCUBRIDOR.
Encuentra perfiles de personas por cargo dentro de un dominio de empresa y
propone un email candidato. NO valida entregabilidad — eso es responsabilidad
de Hunter, el siguiente eslabón de la cascada.

Contrato de error: nunca propaga excepciones. Errores de red/API → [] con log.
Este cliente es deliberadamente "tonto": no conoce Decisor ni EstadoCorreo.
Esa traducción vive en ApolloHunterCascadaAdapter + PoliticaMapeoEstadoCorreo.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.apollo.io/v1"
_PEOPLE_SEARCH_ENDPOINT = f"{_BASE_URL}/mixed_people/search"
_REQUEST_TIMEOUT_SECS = 15


class ApolloClient:
    """
    Args:
        api_key: Clave de API de Apollo. Si None, lee de APOLLO_API_KEY.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("APOLLO_API_KEY")
        if not self._api_key:
            logger.warning(
                "APOLLO_API_KEY no configurada. "
                "ApolloClient retornará listas vacías hasta que se configure."
            )

    def buscar_perfiles(
        self, dominio: str, cargos: list[str], max_resultados: int = 5
    ) -> list[dict]:
        """
        Busca perfiles de personas en `dominio` cuyo cargo coincida con alguno
        de `cargos`. Retorna la lista cruda de perfiles (dicts) tal como los
        entrega Apollo: {"name", "title", "seniority", "email"}.

        `email` puede venir presente (candidato sin verificar) o ausente
        (None) si Apollo no logró asociar un correo al perfil.

        Contrato: nunca lanza excepción. Retorna [] ante cualquier fallo.
        """
        if not self._api_key:
            return []
        if not dominio or not cargos:
            return []

        payload = {
            "q_organization_domains": dominio,
            "person_titles": cargos,
            "per_page": max_resultados,
        }

        try:
            logger.info(
                "Apollo: buscando perfiles en '%s' para cargos %s", dominio, cargos
            )
            response = requests.post(
                _PEOPLE_SEARCH_ENDPOINT,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": self._api_key,
                },
                timeout=_REQUEST_TIMEOUT_SECS,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            logger.warning("Apollo: timeout para dominio '%s'. Retornando [].", dominio)
            return []
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Apollo: HTTP %s para dominio '%s'. Retornando [].",
                exc.response.status_code if exc.response else "?",
                dominio,
            )
            return []
        except requests.exceptions.RequestException as exc:
            logger.error("Apollo: error de red para dominio '%s': %s", dominio, exc)
            return []
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error("Apollo: error inesperado para dominio '%s': %s", dominio, exc)
            return []

        perfiles = data.get("people", [])
        if not isinstance(perfiles, list):
            logger.warning("Apollo: respuesta con forma inesperada para '%s'.", dominio)
            return []

        logger.info(
            "Apollo: %d perfil(es) encontrados en '%s'.", len(perfiles), dominio
        )
        return perfiles
