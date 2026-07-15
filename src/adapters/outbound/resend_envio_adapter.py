"""
ResendEnvioAdapter — implementación de PuertoEnvioCorreo.

Diseño: 10-Memoria_Consolidada/tecnico/prospector-m4-design.md §5, §6.

Rol en el pipeline (Motor 4, paso 5 de la máquina de estados del Mensaje):
ÚNICO adaptador del sistema que produce un efecto externo irreversible
(enviar un correo real). Decisión aprobada por el Architect: Resend como
proveedor (mejor DX que SES, webhooks nativos limpios para rebotes).

Dos responsabilidades separadas y desacopladas, como pidió el Architect:

1. ResendEnvioAdapter.enviar() — la mitad SÍNCRONA: hace el POST a la API de
   Resend y retorna un resultado inicial. Resend confirma "aceptado para
   entrega" en la respuesta HTTP 2xx, NO que el correo fue efectivamente
   entregado. Por eso el resultado inicial es ENTREGADO como aproximación
   optimista del envío exitoso — el rebote real, si ocurre, llega DESPUÉS
   y de forma asíncrona vía webhook.

2. procesar_webhook_rebote() — la mitad ASÍNCRONA: función pura (sin llamar
   a self, sin estado), separada intencionalmente del adaptador. Parsea el
   payload JSON que Resend envía al webhook cuando ocurre un evento de
   rebote real. El controlador HTTP que reciba el webhook (fuera de alcance
   de esta fase — vive en la capa de aplicación) llama a esta función y
   luego inyecta el ResultadoEnvio resultante a PoliticaRegistroRebote.

Contrato de error: ninguna de las dos funciones propaga excepción. Errores
de red/API en enviar() → ResultadoEnvio.ERROR. Payload de webhook mal
formado en procesar_webhook_rebote() → None (el controlador decide qué
hacer con un webhook no reconocido; no es responsabilidad de este adaptador).
"""

from __future__ import annotations

import logging
import os

import requests

from src.core.domain.models import Decisor, Mensaje, ResultadoEnvio
from src.core.ports.interfaces import PuertoEnvioCorreo

logger = logging.getLogger(__name__)

_RESEND_SEND_URL = "https://api.resend.com/emails"
_REQUEST_TIMEOUT_SECS = 15

# Tipos de evento de webhook de Resend que representan un rebote real.
# Ver: https://resend.com/docs/dashboard/webhooks/event-types
_EVENTOS_REBOTE: frozenset[str] = frozenset({"email.bounced", "email.delivery_delayed"})
_EVENTOS_ENTREGADO: frozenset[str] = frozenset({"email.delivered"})


class ResendEnvioAdapter(PuertoEnvioCorreo):
    """
    Args:
        api_key: Clave de API de Resend. Si None, lee de RESEND_API_KEY.
        remitente: Dirección "from" verificada en Resend (dominio propio).
    """

    def __init__(
        self, api_key: str | None = None, remitente: str | None = None
    ) -> None:
        self._api_key = api_key or os.getenv("RESEND_API_KEY")
        self._remitente = remitente or os.getenv("RESEND_REMITENTE", "prospector@example.com")
        if not self._api_key:
            logger.warning(
                "RESEND_API_KEY no configurada. "
                "ResendEnvioAdapter retornará ResultadoEnvio.ERROR hasta que se configure."
            )

    def enviar(self, mensaje: Mensaje, decisor: Decisor) -> ResultadoEnvio:
        """
        Implementa PuertoEnvioCorreo.enviar().

        Mitad SÍNCRONA de la cascada de envío. NO representa el resultado
        final de entregabilidad: solo confirma que Resend aceptó el correo
        para procesamiento. El estado real (rebote incluido) llega después
        vía webhook — ver procesar_webhook_rebote().
        """
        if not self._api_key:
            return ResultadoEnvio.ERROR

        if decisor.correo is None:
            logger.warning(
                "Resend: decisor '%s' sin correo. No se puede enviar.", decisor.nombre
            )
            return ResultadoEnvio.ERROR

        payload = {
            "from": self._remitente,
            "to": [str(decisor.correo)],
            "subject": mensaje.asunto,
            "text": mensaje.cuerpo,
        }

        try:
            logger.info(
                "Resend: enviando mensaje a '%s' <%s>", decisor.nombre, decisor.correo
            )
            response = requests.post(
                _RESEND_SEND_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=_REQUEST_TIMEOUT_SECS,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.warning("Resend: timeout enviando a '%s'.", decisor.correo)
            return ResultadoEnvio.ERROR
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Resend: HTTP %s enviando a '%s'.",
                exc.response.status_code if exc.response else "?",
                decisor.correo,
            )
            return ResultadoEnvio.RECHAZADO
        except requests.exceptions.RequestException as exc:
            logger.error("Resend: error de red enviando a '%s': %s", decisor.correo, exc)
            return ResultadoEnvio.ERROR
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error(
                "Resend: error inesperado enviando a '%s': %s", decisor.correo, exc
            )
            return ResultadoEnvio.ERROR

        logger.info("Resend: correo aceptado para entrega a '%s'.", decisor.correo)
        # Aproximación optimista: Resend aceptó el correo. El resultado real
        # (incluido rebote) se conocerá vía webhook — ver procesar_webhook_rebote.
        return ResultadoEnvio.ENTREGADO


def procesar_webhook_rebote(payload: dict) -> ResultadoEnvio | None:
    """
    Parsea el payload JSON que Resend envía a un webhook cuando ocurre un
    evento de entrega/rebote asíncrono.

    Función pura, desacoplada de ResendEnvioAdapter a propósito: el
    controlador HTTP que recibe el webhook (capa de aplicación, fuera de
    alcance de esta fase) la invoca y luego inyecta el resultado a
    PoliticaRegistroRebote.aplicar(decisor, resultado).

    Args:
        payload: cuerpo JSON ya deserializado del webhook de Resend.
                 Forma esperada: {"type": "email.bounced", "data": {...}}.

    Returns:
        ResultadoEnvio.REBOTADO si el evento es un rebote real.
        ResultadoEnvio.ENTREGADO si el evento confirma entrega.
        None si el payload no tiene forma reconocible o el tipo de evento
        no es uno de los mapeados (el controlador decide si lo ignora).

    Contrato: nunca lanza excepción, ni ante payload vacío o malformado.
    """
    if not isinstance(payload, dict):
        logger.warning("Resend webhook: payload no es un dict. Ignorado.")
        return None

    tipo_evento = payload.get("type")
    if not isinstance(tipo_evento, str):
        logger.warning("Resend webhook: sin campo 'type' válido. Ignorado.")
        return None

    if tipo_evento in _EVENTOS_REBOTE:
        logger.info("Resend webhook: evento de rebote '%s' recibido.", tipo_evento)
        return ResultadoEnvio.REBOTADO

    if tipo_evento in _EVENTOS_ENTREGADO:
        logger.info("Resend webhook: evento de entrega '%s' recibido.", tipo_evento)
        return ResultadoEnvio.ENTREGADO

    logger.debug("Resend webhook: tipo de evento '%s' no mapeado. Ignorado.", tipo_evento)
    return None
