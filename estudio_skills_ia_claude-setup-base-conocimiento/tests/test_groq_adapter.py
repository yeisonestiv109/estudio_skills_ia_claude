"""
Tests unitarios del GroqICPAdapter — sin llamadas reales a la API.

Usa unittest.mock.patch para simular respuestas de Groq.
El wait_strategy se inyecta con wait_none() para tests instantáneos.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import groq as groq_sdk
import pytest
from tenacity import wait_none

from src.adapters.llm.groq_adapter import GroqICPAdapter
from src.core.domain.models import (
    BaseLegal,
    CategoriaEmpresa,
    ManifiestoICP,
    TamanoEmpresa,
)


# ---------------------------------------------------------------------------
# Helpers y fixtures
# ---------------------------------------------------------------------------
GROQ_JSON_PERFECTO = json.dumps({
    "dolor_operativo": "No entregan proyectos a tiempo por deuda técnica acumulada en el monolito",
    "pain_es_accionable": True,
    "anclaje_tecnologico": ["Python", "AWS", "Django"],
    "categoria_empresa": "SAAS_B2B_HORIZONTAL",
    "vertical": "E-commerce",
    "es_gov_facing": False,
    "cargos_decisores": ["CTO", "VP Engineering"],
    "tamano_empresa": "MID_MARKET",
    "geografia": "Colombia",
    "base_legal": "CONSENTIMIENTO_EXPLICITO",
})

GROQ_JSON_CAMPO_INVALIDO = json.dumps({
    "dolor_operativo": None,
    "pain_es_accionable": True,  # Incoherente: True pero dolor=null → ValidationError
    "anclaje_tecnologico": ["Python"],
    "categoria_empresa": "SAAS_B2B_HORIZONTAL",
    "vertical": "Tech",
    "es_gov_facing": False,
    "cargos_decisores": ["CTO"],
    "tamano_empresa": "SME",
    "geografia": "Colombia",
    "base_legal": "CONSENTIMIENTO_EXPLICITO",
})


def _mock_completion(json_content: str) -> MagicMock:
    """Crea un objeto ChatCompletion falso con el contenido JSON indicado."""
    choice = MagicMock()
    choice.message.content = json_content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _adaptador_con_mock_client(mock_create_response) -> tuple[GroqICPAdapter, MagicMock]:
    """
    Construye un GroqICPAdapter con el cliente de Groq mockeado.
    Usa wait_none() para que los tests de retry sean instantáneos.
    """
    with patch("src.adapters.llm.groq_adapter.groq_sdk.Groq") as MockGroq:
        mock_client = MockGroq.return_value
        mock_client.chat.completions.create.return_value = mock_create_response
        adapter = GroqICPAdapter(
            api_key="test-key-fake-12345",
            wait_strategy=wait_none(),
        )
        # Necesitamos devolver el mock_client para poder cambiar side_effect en tests
        adapter._client = mock_client
        # Reconstruir el callable de retry con el cliente ya inyectado
        from tenacity import retry, retry_if_exception_type, stop_after_attempt
        adapter._llamar_con_retry = retry(
            retry=retry_if_exception_type(groq_sdk.RateLimitError),
            wait=wait_none(),
            stop=stop_after_attempt(3),
            reraise=True,
        )(adapter._llamar_api_groq)
    return adapter, mock_client


# ---------------------------------------------------------------------------
# Test 1: JSON Perfecto → ManifiestoICP correcto
# ---------------------------------------------------------------------------
class TestGroqAdapterJSONPerfecto:
    def test_retorna_manifesto_icp_valido(self):
        """El adaptador debe retornar un ManifiestoICP cuando Groq entrega JSON válido."""
        adapter, mock_client = _adaptador_con_mock_client(
            _mock_completion(GROQ_JSON_PERFECTO)
        )
        mock_client.chat.completions.create.return_value = _mock_completion(GROQ_JSON_PERFECTO)

        resultado = adapter.analizar("Busco empresas SaaS con deuda técnica en Colombia")

        assert isinstance(resultado, ManifiestoICP)
        assert resultado.categoria_empresa == CategoriaEmpresa.SAAS_B2B_HORIZONTAL
        assert resultado.tamano_empresa == TamanoEmpresa.MID_MARKET
        assert resultado.pain_es_accionable is True
        assert "Python" in resultado.anclaje_tecnologico
        assert resultado.base_legal == BaseLegal.CONSENTIMIENTO_EXPLICITO
        assert resultado.es_gov_facing is False

    def test_llama_al_modelo_correcto(self):
        """Verifica que se llama al modelo llama-3.3-70b-versatile."""
        adapter, mock_client = _adaptador_con_mock_client(
            _mock_completion(GROQ_JSON_PERFECTO)
        )
        mock_client.chat.completions.create.return_value = _mock_completion(GROQ_JSON_PERFECTO)
        adapter.analizar("Busco empresas fintech")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "llama-3.3-70b-versatile"

    def test_usa_json_object_response_format(self):
        """Verifica que se fuerza el response_format JSON."""
        adapter, mock_client = _adaptador_con_mock_client(
            _mock_completion(GROQ_JSON_PERFECTO)
        )
        mock_client.chat.completions.create.return_value = _mock_completion(GROQ_JSON_PERFECTO)
        adapter.analizar("descripción de prueba")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["response_format"] == {"type": "json_object"}

    def test_system_prompt_contiene_enums(self):
        """El system prompt debe incluir los valores de los Enums para evitar alucinaciones."""
        adapter, _ = _adaptador_con_mock_client(_mock_completion(GROQ_JSON_PERFECTO))

        assert "SAAS_B2B_HORIZONTAL" in adapter._system_prompt
        assert "REGULADO_FINTECH" in adapter._system_prompt
        assert "MID_MARKET" in adapter._system_prompt
        assert "ENTERPRISE" in adapter._system_prompt
        assert "DATO_PUBLICO" in adapter._system_prompt
        assert "CONSENTIMIENTO_EXPLICITO" in adapter._system_prompt


# ---------------------------------------------------------------------------
# Test 2: Rate Limit 429 → Reintento con tenacity
# ---------------------------------------------------------------------------
class TestGroqAdapterRateLimit:
    def test_reintenta_tras_rate_limit_y_tiene_exito(self):
        """
        Si el primer intento lanza RateLimitError y el segundo tiene éxito,
        el adaptador debe retornar el ManifiestoICP correctamente.
        """
        # Creamos una respuesta mock que simula el error de rate limit de Groq.
        # groq.RateLimitError requiere response y body en v1.x
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "1"}
        rate_limit_error = groq_sdk.RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )

        adapter, mock_client = _adaptador_con_mock_client(
            _mock_completion(GROQ_JSON_PERFECTO)
        )
        # 1er intento: RateLimitError. 2do intento: éxito.
        mock_client.chat.completions.create.side_effect = [
            rate_limit_error,
            _mock_completion(GROQ_JSON_PERFECTO),
        ]

        resultado = adapter.analizar("Busco empresas con deuda técnica")

        assert isinstance(resultado, ManifiestoICP)
        # Verificar que se llamó 2 veces (1 fallido + 1 exitoso)
        assert mock_client.chat.completions.create.call_count == 2

    def test_agota_reintentos_lanza_value_error(self):
        """Después de max_retries intentos fallidos, debe lanzar ValueError al usuario."""
        from tenacity import retry, retry_if_exception_type, stop_after_attempt

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        rate_limit_error = groq_sdk.RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )

        adapter, mock_client = _adaptador_con_mock_client(
            _mock_completion(GROQ_JSON_PERFECTO)
        )
        # Reconstruir el callable con max_retries=2 y wait_none para tests rápidos
        adapter._llamar_con_retry = retry(
            retry=retry_if_exception_type(groq_sdk.RateLimitError),
            wait=wait_none(),
            stop=stop_after_attempt(2),
            reraise=True,
        )(adapter._llamar_api_groq)

        # Todos los intentos fallan con RateLimitError
        mock_client.chat.completions.create.side_effect = rate_limit_error

        with pytest.raises(ValueError, match="límite de velocidad"):
            adapter.analizar("descripción cualquiera")

        # Confirmar que se hicieron exactamente 2 intentos (stop_after_attempt=2)
        assert mock_client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# Test 3: JSON inválido de Groq → ValueError con preguntas de clarificación
# ---------------------------------------------------------------------------
class TestGroqAdapterValidationError:
    def test_json_incoherente_lanza_value_error_con_preguntas(self):
        """
        Si Groq retorna JSON que no pasa la validación de ManifiestoICP
        (ej: pain_accionable=True pero dolor=null), debe lanzar ValueError
        con preguntas de clarificación.
        """
        adapter, mock_client = _adaptador_con_mock_client(
            _mock_completion(GROQ_JSON_CAMPO_INVALIDO)
        )
        mock_client.chat.completions.create.return_value = _mock_completion(GROQ_JSON_CAMPO_INVALIDO)

        with pytest.raises(ValueError) as exc_info:
            adapter.analizar("descripción vaga sin tecnología")

        error_msg = str(exc_info.value)
        assert "responde" in error_msg.lower() or "clarifi" in error_msg.lower() or "Por favor" in error_msg

    def test_descripcion_vacia_lanza_value_error(self):
        """Una descripción vacía debe ser rechazada antes de llamar a la API."""
        adapter, mock_client = _adaptador_con_mock_client(
            _mock_completion(GROQ_JSON_PERFECTO)
        )

        with pytest.raises(ValueError, match="vacía"):
            adapter.analizar("")

        with pytest.raises(ValueError, match="vacía"):
            adapter.analizar("   ")

        # La API NO debe haber sido llamada
        mock_client.chat.completions.create.assert_not_called()

    def test_respuesta_vacia_de_groq_lanza_value_error(self):
        """Si Groq retorna contenido null/vacío, debe lanzar ValueError."""
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_completion_empty = MagicMock()
        mock_completion_empty.choices = [mock_choice]

        adapter, mock_client = _adaptador_con_mock_client(mock_completion_empty)
        mock_client.chat.completions.create.return_value = mock_completion_empty

        with pytest.raises(ValueError):
            adapter.analizar("Busco empresas fintech colombianas")


# ---------------------------------------------------------------------------
# Test 4: Constructor — validación de API key
# ---------------------------------------------------------------------------
class TestGroqAdapterConstructor:
    def test_constructor_falla_sin_api_key(self):
        """Sin API key en env ni en argumento, debe lanzar ValueError."""
        # Aseguramos que la variable de entorno no esté definida en este test
        with patch.dict("os.environ", {}, clear=False):
            import os
            original = os.environ.pop("GROQ_API_KEY", None)
            try:
                with pytest.raises(ValueError, match="GROQ_API_KEY"):
                    GroqICPAdapter(api_key=None)
            finally:
                if original is not None:
                    os.environ["GROQ_API_KEY"] = original

    def test_constructor_usa_api_key_del_argumento(self):
        """Si se pasa api_key como argumento, no lee del entorno."""
        with patch("src.adapters.llm.groq_adapter.groq_sdk.Groq") as MockGroq:
            GroqICPAdapter(api_key="mi-clave-de-prueba", wait_strategy=wait_none())
            MockGroq.assert_called_once_with(api_key="mi-clave-de-prueba")
