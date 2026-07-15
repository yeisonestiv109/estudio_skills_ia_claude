"""
HunterClient — cliente HTTP delgado para la API de Hunter.io.

Rol en la cascada (ver `tecnico/prospector-m3-m4-design.md` §3.2): VALIDADOR DURO.
Verifica la entregabilidad real de un email que Apollo propuso, o infiere el
patrón de correo corporativo del dominio cuando Apollo no encontró email.

Regla de corte de costo (crítica): este cliente SOLO debe invocarse cuando ya
hay algo que verificar. La decisión de invocarlo o no vive en
ApolloHunterCascadaAdapter, no aquí — este cliente es un componente "tonto"
que simplemente ejecuta la llamada que se le pida.

Contrato de error: nunca propaga excepciones. Errores de red/API → None con log.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.hunter.io/v2"
_VERIFY_ENDPOINT = f"{_BASE_URL}/email-verifier"
_DOMAIN_SEARCH_ENDPOINT = f"{_BASE_URL}/domain-search"
_REQUEST_TIMEOUT_SECS = 15


class HunterClient:
    """
    Args:
        api_key: Clave de API de Hunter. Si None, lee de HUNTER_API_KEY.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("HUNTER_API_KEY")
        if not self._api_key:
            logger.warning(
                "HUNTER_API_KEY no configurada. "
                "HunterClient retornará None hasta que se configure."
            )

    def verificar_email(self, email: str) -> dict | None:
        """
        Verifica la entregabilidad de un email ya propuesto (por Apollo).
        Retorna {"status": str, "score": int} o None ante cualquier fallo.

        Contrato: nunca lanza excepción. Solo se debe llamar cuando ya existe
        un email candidato — el corte de costo (no llamar sin email) es
        responsabilidad del orquestador de la cascada, no de este método.
        """
        if not self._api_key or not email:
            return None

        try:
            logger.info("Hunter: verificando email '%s'", email)
            response = requests.get(
                _VERIFY_ENDPOINT,
                params={"email": email, "api_key": self._api_key},
                timeout=_REQUEST_TIMEOUT_SECS,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            logger.warning("Hunter: timeout verificando '%s'. Retornando None.", email)
            return None
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Hunter: HTTP %s verificando '%s'. Retornando None.",
                exc.response.status_code if exc.response else "?",
                email,
            )
            return None
        except requests.exceptions.RequestException as exc:
            logger.error("Hunter: error de red verificando '%s': %s", email, exc)
            return None
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error("Hunter: error inesperado verificando '%s': %s", email, exc)
            return None

        resultado = data.get("data", {})
        status = resultado.get("status")
        score = resultado.get("score")
        if status is None or score is None:
            logger.warning("Hunter: respuesta sin status/score para '%s'.", email)
            return None

        return {"status": status, "score": score}

    def inferir_patron_dominio(self, dominio: str) -> bool:
        """
        Consulta Hunter Domain Search para saber si existe un patrón de correo
        corporativo conocido y confiable para el dominio (ej. {first}.{last}@dominio).

        Retorna True si Hunter reporta un patrón, False en cualquier otro caso
        (incluidos errores de red — nunca lanza excepción).
        """
        if not self._api_key or not dominio:
            return False

        try:
            logger.info("Hunter: buscando patrón de dominio para '%s'", dominio)
            response = requests.get(
                _DOMAIN_SEARCH_ENDPOINT,
                params={"domain": dominio, "api_key": self._api_key},
                timeout=_REQUEST_TIMEOUT_SECS,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            logger.warning("Hunter: timeout en domain-search '%s'.", dominio)
            return False
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Hunter: HTTP %s en domain-search '%s'.",
                exc.response.status_code if exc.response else "?",
                dominio,
            )
            return False
        except requests.exceptions.RequestException as exc:
            logger.error("Hunter: error de red en domain-search '%s': %s", dominio, exc)
            return False
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error(
                "Hunter: error inesperado en domain-search '%s': %s", dominio, exc
            )
            return False

        patron = (data.get("data") or {}).get("pattern")
        return bool(patron)
