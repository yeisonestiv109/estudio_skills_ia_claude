"""
GroqICPAdapter — Implementación del PuertoAnalizadorICP usando la API de Groq.

Modelo: llama-3.3-70b-versatile
Manejo de Rate Limit: tenacity con backoff exponencial (configurable para tests).
Contrato de error: si Pydantic no puede validar la respuesta, se lanza ValueError
con máximo 3 preguntas de clarificación, conforme al contrato del Puerto.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import groq as groq_sdk
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.domain.models import (
    BaseLegal,
    CategoriaEmpresa,
    ManifiestoICP,
    TamanoEmpresa,
)
from src.core.ports.interfaces import PuertoAnalizadorICP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapa de campos fallidos → preguntas de clarificación legibles por el usuario
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Mapa de campos fallidos → preguntas de clarificación legibles por el usuario
# ---------------------------------------------------------------------------
_CLARIFICATION_QUESTIONS: dict[str, str] = {
    "anclaje_tecnologico": (
        "¿Qué tecnologías específicas usa la empresa objetivo? "
        "(Ej: Python, AWS, SAP, Salesforce)"
    ),
    "categoria_empresa": (
        "¿Qué tipo de empresa es o qué modelo de negocio tiene el cliente objetivo? "
        "(Ej: Agencia IT, B2B SaaS, Fintech regulada, Consultora IT)"
    ),
    "tamano_empresa": (
        "¿Cuántos empleados tiene aproximadamente la empresa? "
        "(Startup <50, SME 50-200, Mid-Market 200-1000, Enterprise >1000)"
    ),
    "cargos_decisores": (
        "¿Quiénes toman las decisiones tecnológicas en la empresa? "
        "(Ej: CTO, VP Engineering, Head of IT)"
    ),
    "base_legal": (
        "¿Bajo qué base legal se procesará el dato del prospecto? "
        "(Consentimiento explícito, Interés legítimo, o Ejecución de contrato)"
    ),
    "dolor_operativo": (
        "¿Cuál es el dolor operativo concreto de la empresa? "
        "Sea específico: ¿qué falla exactamente en sus procesos tecnológicos?"
    ),
    "vertical": (
        "¿A qué sector o vertical pertenece la empresa? "
        "(Ej: Retail, Salud, Finanzas, Logística)"
    ),
    "geografia": (
        "¿En qué país o región opera principalmente la empresa objetivo?"
    ),
}
  
 


def _construir_system_prompt() -> str:
    """
    Genera el system prompt inyectando los valores exactos de cada Enum.
    Esta función se llama una sola vez al construir el adaptador para evitar
    reconstruir el string en cada invocación.
    """
    categorias = " | ".join(e.value for e in CategoriaEmpresa)
    tamanos = " | ".join(e.value for e in TamanoEmpresa)
    bases_legales = " | ".join(e.value for e in BaseLegal)

    return f"""Eres un extractor de entidades JSON especializado en calificación de prospectos B2B para empresas tecnológicas en LATAM.

Tu única tarea es analizar la descripción del cliente ideal que te proporciona el usuario y extraer la información en el formato JSON especificado.

FORMATO DE RESPUESTA OBLIGATORIO (responde ÚNICAMENTE con este JSON, sin markdown, sin explicaciones, sin bloques de código):
{{
  "dolor_operativo": "<string con el dolor principal detectado, o null si no es accionable>",
  "pain_es_accionable": <true si el dolor es específico y operativo, false si es genérico o vago>,
  "anclaje_tecnologico": ["<tecnología_1>", "<tecnología_2>"],
  "categoria_empresa": "<VALOR_EXACTO del enum, o null si el usuario no especifica claramente el modelo de negocio>",
  "vertical": "<sector de negocio en texto libre, Ej: Retail, Salud, Logística, o null si no se especifica el sector>",
  "es_gov_facing": <true si la empresa vende o entrega servicios al gobierno colombiano, false en caso contrario>,
  "cargos_decisores": ["<cargo_1>", "<cargo_2>"],
  "tamano_empresa": "<VALOR_EXACTO del enum, o null si el usuario no especifica el tamaño o número de empleados>",
  "geografia": "<código ISO Alpha-2 de 2 letras, Ej: CO, US, MX, ES, o null si el usuario no especifica el país de interés>",
  "base_legal": "<VALOR_EXACTO del enum>"
}}

VALORES EXACTOS PERMITIDOS PARA LOS ENUMS (usa solo estos, tal cual están escritos):
- categoria_empresa: {categorias}
- tamano_empresa: {tamanos}
- base_legal: {bases_legales}

REGLAS CRÍTICAS:
1. Si pain_es_accionable es true, dolor_operativo NO puede ser null ni vacío.
2. anclaje_tecnologico: Si el texto del usuario menciona tecnologías concretas (lenguajes, plataformas, vendors), extráelas. Si NO menciona ninguna tecnología concreta, devuelve una lista vacía []. NUNCA inventes ni agregues palabras genéricas como 'Software', 'Tecnología' o 'Automatización' para llenar este campo.
3. cargos_decisores debe tener al menos 1 elemento.
4. Solo puedes usar los valores de enum listados arriba. No inventes valores nuevos.
5. base_legal por defecto es "CONSENTIMIENTO_EXPLICITO" si no se especifica. NUNCA uses "interés legítimo": no existe como base legal en Colombia (Ley 1581/2012 exige consentimiento previo, expreso e informado). Valores válidos: CONSENTIMIENTO_EXPLICITO, EJECUCION_CONTRATO, DATO_PUBLICO.
6. GEOGRAFÍA — REGLA ESTRICTA E INVIOLABLE: el campo "geografia" DEBE ser
   EXCLUSIVAMENTE el código ISO 3166-1 Alpha-2 de EXACTAMENTE 2 letras mayúsculas.
   Ejemplos correctos: "CO" (Colombia), "US" (Estados Unidos), "MX" (México).
   Si el usuario no especifica qué país o geografía le interesa de forma explícita, DEBES devolver null. No asumas ni adivines el país bajo ninguna circunstancia.
   ESTÁ TERMINANTEMENTE PROHIBIDO devolver el nombre completo del país.
   INCORRECTO: "Estados Unidos", "Colombia", "México", "LATAM", "Bogotá".
   Si el usuario menciona "Estados Unidos" debes convertirlo a "US".
   Si menciona "Colombia" debes convertirlo a "CO". Nunca más de 2 letras.
7. anclaje_tecnologico — REGLA ESTRICTA DE NOMBRES OFICIALES COMPLETOS:
   Usa el NOMBRE OFICIAL COMPLETO de cada tecnología, NUNCA siglas ni abreviaturas.
   CORRECTO: ["Amazon Web Services", "Google Cloud Platform", "Python", "PostgreSQL", "Kubernetes"].
   INCORRECTO (siglas prohibidas): ["AWS", "GCP", "K8s"].
   Si el usuario dice "usan AWS", debes escribir "Amazon Web Services".
   Si dice "en GCP", debes escribir "Google Cloud Platform".
   PROHIBIDO incluir abstracciones, metodologías o procesos como:
   "Microservicios", "ETL", "ERP", "QA", "Frontend", "Backend", "DevOps", "Cloud",
   "Escalabilidad", "Integración", "Automatización", "Arquitectura".
   Si el texto menciona "microservicios en Python con AWS", extrae
   ["Python", "Amazon Web Services"], no ["Python", "AWS", "Microservicios"].
8. TAMAÑO DE EMPRESA — REGLA ESTRICTA: si el usuario no especifica de forma explícita el número de empleados o el tamaño de las empresas que busca (ej. 'startups', 'medianas', 'grandes', '>1000 empleados'), DEBES devolver null en "tamano_empresa". No intentes adivinar ni asumir un tamaño por defecto.
9. CATEGORÍA Y VERTICAL — REGLA ESTRICTA: si el texto no da indicios claros del modelo de negocio (B2B, SaaS, etc.) o del sector (salud, retail, etc.), devuelve null en "categoria_empresa" y "vertical" respectivamente. No adivines.
10. Responde SOLO con el JSON. Sin explicaciones. Sin bloques de código markdown."""


class GroqICPAdapter(PuertoAnalizadorICP):
    """
    Adaptador LLM que implementa PuertoAnalizadorICP usando la API de Groq.

    El cliente del Core solo conoce PuertoAnalizadorICP (ABC).
    Esta clase concreta solo vive en la capa de adaptadores.

    Args:
        api_key: Clave de API de Groq. Si no se provee, lee de GROQ_API_KEY.
        wait_strategy: Estrategia de espera de tenacity. Inyectada para facilitar
                       el testing sin esperas reales (usa wait_none() en tests).
        max_retries: Número máximo de reintentos ante Rate Limit (429).
    """

    MODEL = "llama-3.3-70b-versatile"

    def __init__(
        self,
        api_key: str | None = None,
        wait_strategy: Any = None,
        max_retries: int = 3,
    ) -> None:
        resolved_key = api_key or os.getenv("GROQ_API_KEY")
        if not resolved_key:
            raise ValueError(
                "GROQ_API_KEY no está configurada. "
                "Define la variable en el archivo .env o pásala como argumento."
            )

        self._client = groq_sdk.Groq(api_key=resolved_key)
        self._system_prompt = _construir_system_prompt()

        # Construir el método de llamada con tenacity dinámicamente
        # para permitir inyección del wait_strategy en tests.
        _wait = wait_strategy or wait_exponential(multiplier=1, min=4, max=60)
        self._llamar_con_retry = retry(
            retry=retry_if_exception_type(groq_sdk.RateLimitError),
            wait=_wait,
            stop=stop_after_attempt(max_retries),
            before_sleep=lambda state: logger.warning(
                "Rate limit alcanzado (429). Reintento %d de %d en %.1fs...",
                state.attempt_number,
                max_retries,
                state.next_action.sleep if state.next_action else 0,
            ),
            reraise=True,
        )(self._llamar_api_groq)

    def _llamar_api_groq(self, descripcion_libre: str) -> str:
        """
        Llamada directa a la API de Groq. Separada del método público para
        permitir que tenacity la envuelva con la estrategia de retry correcta.

        Returns:
            Contenido JSON crudo de la respuesta del modelo.

        Raises:
            groq.RateLimitError: Capturado y reintentado por tenacity.
            groq.APIError: Propagado al método público para manejo.
        """
        completion = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": descripcion_libre},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Baja temperatura para salidas deterministas
            max_tokens=1024,
        )
        raw_content = completion.choices[0].message.content
        if raw_content is None:
            raise ValueError("La API de Groq retornó un contenido vacío.")
        return raw_content

    def analizar(self, descripcion_libre: str) -> ManifiestoICP:
        """
        Implementa PuertoAnalizadorICP.analizar().

        Transforma texto libre en un ManifiestoICP validado por Pydantic v2.

        Returns:
            ManifiestoICP validado.

        Raises:
            ValueError: Si el LLM no puede estructurar los datos correctamente.
                        Incluye máximo 3 preguntas de clarificación para el usuario.
            groq.APIError: Si la API falla por razones distintas al Rate Limit.
        """
        if not descripcion_libre or not descripcion_libre.strip():
            raise ValueError(
                "La descripción del cliente ideal no puede estar vacía. "
                "Describe qué tipo de empresa buscas y cuál es su dolor principal."
            )

        logger.info("Llamando a Groq (%s) para analizar ICP...", self.MODEL)

        try:
            json_crudo = self._llamar_con_retry(descripcion_libre)
        except groq_sdk.RateLimitError:
            raise ValueError(
                "La API de Groq alcanzó el límite de velocidad después de varios "
                "reintentos. Espera un momento e inténtalo de nuevo."
            )
        except groq_sdk.APIError as exc:
            logger.error("Error en la API de Groq: %s", exc)
            raise

        logger.debug("Respuesta cruda de Groq: %s", json_crudo)

        try:
            manifiesto = ManifiestoICP.model_validate_json(json_crudo)
        except ValidationError as exc:
            preguntas = self._generar_preguntas_clarificacion(exc)
            raise ValueError(
                "No pude estructurar tu descripción correctamente. "
                "Por favor responde:\n" + "\n".join(f"  {i+1}. {p}" for i, p in enumerate(preguntas))
            ) from exc

        # ── Validación semántica post-Pydantic ───────────────────────────────
        # Detecta lista vacía O palabras genéricas de alucinación que la IA
        # pudo haber colado para evitar fallar la validación de Pydantic.
        _PALABRAS_ALUCINACION = {
            "software", "tecnología", "tecnologia", "automatización", "automatizacion",
            "sistemas", "soluciones", "plataforma", "cloud", "digital", "it",
            "integración", "integracion", "arquitectura", "devops", "backend",
            "frontend", "microservicios", "escalabilidad",
        }
        tecnologias_validas = [
            t for t in manifiesto.anclaje_tecnologico
            if t.lower().strip() not in _PALABRAS_ALUCINACION
        ]
        if not tecnologias_validas:
            raise ValueError(
                "No pude identificar tecnologías concretas en tu descripción. "
                "Por favor responde:\n"
                "  1. " + _CLARIFICATION_QUESTIONS["anclaje_tecnologico"]
            )

        # Reasignar solo las tecnologías válidas (sin alucinaciones)
        manifiesto = manifiesto.model_copy(
            update={"anclaje_tecnologico": tecnologias_validas}
        )

        # Validar semánticamente los campos opcionales que requerimos del usuario
        # Evaluamos uno por uno de forma secuencial para preguntar solo una cosa por turno
        if manifiesto.categoria_empresa is None:
            raise ValueError(
                "Necesito afinar algunos detalles de tu descripción. Por favor responde:\n"
                f"  1. {_CLARIFICATION_QUESTIONS['categoria_empresa']}"
            )
        if manifiesto.vertical is None:
            raise ValueError(
                "Necesito afinar algunos detalles de tu descripción. Por favor responde:\n"
                f"  1. {_CLARIFICATION_QUESTIONS['vertical']}"
            )
        if manifiesto.tamano_empresa is None:
            raise ValueError(
                "Necesito afinar algunos detalles de tu descripción. Por favor responde:\n"
                f"  1. {_CLARIFICATION_QUESTIONS['tamano_empresa']}"
            )
        if manifiesto.geografia is None:
            raise ValueError(
                "Necesito afinar algunos detalles de tu descripción. Por favor responde:\n"
                f"  1. {_CLARIFICATION_QUESTIONS['geografia']}"
            )
        # Validar semánticamente los campos opcionales que requerimos del usuario
        # Evaluamos uno por uno de forma secuencial para preguntar solo una cosa por turno
        if manifiesto.categoria_empresa is None:
            raise ValueError(
                "Necesito afinar algunos detalles de tu descripción. Por favor responde:\n"
                f"  1. {_CLARIFICATION_QUESTIONS['categoria_empresa']}"
            )

        logger.info(
            "ManifiestoICP generado correctamente. "
            "categoria=%s tamano=%s pain_accionable=%s",
            manifiesto.categoria_empresa.value,
            manifiesto.tamano_empresa.value,
            manifiesto.pain_es_accionable,
        )
        return manifiesto

    @staticmethod
    def _generar_preguntas_clarificacion(exc: ValidationError) -> list[str]:
        """
        Extrae los campos fallidos de la ValidationError y los mapea a
        preguntas legibles por el usuario (máximo 1 para flujo secuencial).
        """
        campos_fallidos: list[str] = []
        for error in exc.errors():
            loc = error.get("loc", ())
            if loc:
                campo = str(loc[0])
                if campo not in campos_fallidos:
                    campos_fallidos.append(campo)

        preguntas: list[str] = []
        for campo in campos_fallidos:
            if campo in _CLARIFICATION_QUESTIONS:
                preguntas.append(_CLARIFICATION_QUESTIONS[campo])
            if len(preguntas) == 1:  # Preguntar solo 1 cosa a la vez para flujo conversacional
                break

        # Pregunta de fallback si ningún campo mapeó a una pregunta conocida
        if not preguntas:
            preguntas.append(
                "¿Puedes describir con más detalle el tipo de empresa, "
                "las tecnologías que usa y el cargo de la persona que toma decisiones?"
            )

        return preguntas
