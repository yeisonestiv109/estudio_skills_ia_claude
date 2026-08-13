"""
GroqRedactorAdapter — implementación de PuertoRedactorOutbound.

Diseño: 02_Lineas_de_Producto/Outbound_Prospector/docs/tecnico/prospector-m4-design.md §5.

Rol en el pipeline (Motor 4, paso 3 de la máquina de estados del Mensaje):
redacta un Mensaje (asunto + cuerpo) a partir del Decisor, la Empresa, sus
Triggers (el gancho de personalización que en M3 viajaba sin usarse) y el
ContextoRAG recuperado por TavilyContextoAdapter.

Modelo: llama3-70b-8192 (rápido, adecuado para redacción de correo corto).
El prompt base aquí es intencionalmente simple — el prompt real de
producción (tono, estructura, longitud) se define en la siguiente fase de
pruebas con el negocio. Esta versión ensambla asunto y cuerpo de forma
determinista a partir de la salida del LLM.

Contrato de error: NUNCA propaga excepción al Core. Ante cualquier fallo
(rate limit, API caída, contenido vacío o sin el separador esperado) retorna
un Mensaje con estado EstadoMensaje.ERROR_REDACCION, nunca lanza.

Requisitos de cold email (validacion-fuentes.md §7): el prompt exige
identificación del remitente, motivo del contacto y opción de baja —
verificables después por PoliticaRedaccionOutbound (Core, pendiente).
"""

from __future__ import annotations

import logging
import os

import groq as groq_sdk

from src.core.domain.models import (
    ContextoRAG,
    Decisor,
    Empresa,
    EstadoMensaje,
    Mensaje,
    Trigger,
)
from src.core.ports.interfaces import PuertoRedactorOutbound

logger = logging.getLogger(__name__)

_SEPARADOR_ASUNTO_CUERPO = "---CUERPO---"

_SYSTEM_PROMPT_BASE = f"""Eres un redactor de correos de prospección B2B en español, profesional y breve.

Recibirás datos de un decisor, su empresa, una señal de mercado (trigger) reciente y evidencia de contexto.
Escribe UN solo correo de primer contacto, corto (máximo 120 palabras en el cuerpo), con tono directo y respetuoso.

El correo DEBE incluir:
1. Un gancho basado en el trigger recibido (nunca genérico).
2. Identificación clara de quién escribe.
3. Una opción de baja/no interesado al final (ej. "Si no es de tu interés, contéstame y no te escribo más.").

FORMATO DE RESPUESTA OBLIGATORIO (sin markdown, sin explicaciones):
<línea de asunto>
{_SEPARADOR_ASUNTO_CUERPO}
<cuerpo del correo>
"""


class GroqRedactorAdapter(PuertoRedactorOutbound):
    """
    Adaptador LLM que implementa PuertoRedactorOutbound usando la API de Groq.

    Args:
        api_key: Clave de API de Groq. Si None, lee de GROQ_API_KEY.
    """

    _DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or os.getenv("GROQ_API_KEY")
        self._client = groq_sdk.Groq(api_key=resolved_key) if resolved_key else None
        if not resolved_key:
            logger.warning(
                "GROQ_API_KEY no configurada. "
                "GroqRedactorAdapter retornará Mensaje en ERROR_REDACCION hasta que se configure."
            )

    def redactar(
        self,
        decisor: Decisor,
        empresa: Empresa,
        triggers: list[Trigger],
        contexto: ContextoRAG,
    ) -> Mensaje:
        """Implementa PuertoRedactorOutbound.redactar()."""
        if self._client is None:
            return self._mensaje_error(decisor)

        user_prompt = self._construir_user_prompt(decisor, empresa, triggers, contexto)

        try:
            logger.info(
                "Groq redactor: generando mensaje para decisor '%s' (%s)",
                decisor.nombre,
                empresa.nombre,
            )
            completion = self._client.chat.completions.create(
                model=self._DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT_BASE},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=400,
            )
            contenido = completion.choices[0].message.content
        except groq_sdk.RateLimitError as exc:
            logger.warning(
                "Groq redactor: rate limit para '%s': %s", empresa.nombre, exc
            )
            return self._mensaje_error(decisor)
        except groq_sdk.APIError as exc:
            logger.error(
                "Groq redactor: error de API para '%s': %s", empresa.nombre, exc
            )
            return self._mensaje_error(decisor)
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error(
                "Groq redactor: error inesperado para '%s': %s", empresa.nombre, exc
            )
            return self._mensaje_error(decisor)

        return self._parsear_respuesta(contenido, decisor, contexto)

    def _construir_user_prompt(
        self,
        decisor: Decisor,
        empresa: Empresa,
        triggers: list[Trigger],
        contexto: ContextoRAG,
    ) -> str:
        trigger_texto = (
            triggers[0].descripcion if triggers else "sin señal de mercado específica"
        )
        evidencia_texto = (
            "; ".join(contexto.evidencias[:2])
            if contexto.evidencias
            else "sin evidencia adicional"
        )
        return (
            f"Decisor: {decisor.nombre} — {decisor.cargo_original}\n"
            f"Empresa: {empresa.nombre} ({empresa.vertical})\n"
            f"Trigger: {trigger_texto}\n"
            f"Evidencia de contexto: {evidencia_texto}"
        )

    def _parsear_respuesta(
        self, contenido: str | None, decisor: Decisor, contexto: ContextoRAG
    ) -> Mensaje:
        if not contenido or _SEPARADOR_ASUNTO_CUERPO not in contenido:
            logger.warning(
                "Groq redactor: respuesta sin el formato esperado para decisor '%s'.",
                decisor.nombre,
            )
            return self._mensaje_error(decisor)

        asunto_crudo, cuerpo_crudo = contenido.split(_SEPARADOR_ASUNTO_CUERPO, 1)
        asunto = asunto_crudo.strip()
        if asunto.lower().startswith("asunto:"):
            asunto = asunto[7:].strip()
        cuerpo = cuerpo_crudo.strip()

        if not asunto or not cuerpo:
            logger.warning(
                "Groq redactor: asunto o cuerpo vacío tras el parseo para decisor '%s'.",
                decisor.nombre,
            )
            return self._mensaje_error(decisor)

        return Mensaje(
            decisor_id=decisor.id,
            asunto=asunto,
            cuerpo=cuerpo,
            estado=EstadoMensaje.BORRADOR,
            fuentes_citadas=list(contexto.fuentes),
        )

    def _mensaje_error(self, decisor: Decisor) -> Mensaje:
        """
        Construye un Mensaje válido (Pydantic exige asunto/cuerpo no vacíos)
        pero marcado como ERROR_REDACCION, para que el orquestador lo detecte
        y no lo pase nunca a HITL ni a envío.
        """
        return Mensaje(
            decisor_id=decisor.id,
            asunto="[ERROR DE REDACCIÓN]",
            cuerpo="El redactor no pudo generar contenido. Revisar manualmente.",
            estado=EstadoMensaje.ERROR_REDACCION,
        )
