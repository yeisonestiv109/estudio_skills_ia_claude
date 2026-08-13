"""
Tests unitarios del Motor 4 — adaptadores outbound, sin llamadas reales a APIs.

Mockea requests.get/post para Tavily y Resend, y el cliente groq.Groq para el
redactor. Ningún test de este archivo consume créditos reales de Tavily,
Groq o Resend: toda llamada de red/SDK está parcheada con unittest.mock.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.adapters.outbound.groq_redactor_adapter import GroqRedactorAdapter
from src.adapters.outbound.resend_envio_adapter import (
    ResendEnvioAdapter,
    procesar_webhook_rebote,
)
from src.adapters.outbound.tavily_contexto_adapter import TavilyContextoAdapter
from src.core.domain.models import (
    AutoridadDecision,
    Decisor,
    Empresa,
    EstadoMensaje,
    NivelConfianza,
    OrigenTrigger,
    ResultadoEnvio,
    Seniority,
    TamanoEmpresa,
    Trigger,
)
from datetime import datetime, timedelta, timezone


@pytest.fixture
def empresa() -> Empresa:
    return Empresa(
        nombre="Acme SaaS",
        dominio="acme.com",
        tamano=TamanoEmpresa.MID_MARKET,
        vertical="E-commerce",
        ciudad="Bogotá",
    )


@pytest.fixture
def decisor(empresa: Empresa) -> Decisor:
    return Decisor(
        empresa_id=empresa.id,
        nombre="Ana Torres",
        cargo_original="Chief Technology Officer",
        cargo_normalizado="CTO",
        seniority=Seniority.C_LEVEL,
        autoridad_decision=AutoridadDecision.DECISION_MAKER,
        correo="ana@acme.com",
        confianza_dato=0.90,
    )


@pytest.fixture
def trigger(empresa: Empresa) -> Trigger:
    return Trigger(
        empresa_id=empresa.id,
        origen=OrigenTrigger.THEIRSTACK,
        nivel_confianza=NivelConfianza.ALTA,
        descripcion="3 vacantes técnicas abiertas hace 10 días",
        fecha_evento=datetime.now(timezone.utc) - timedelta(days=10),
    )


def _mock_response(payload: dict, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = payload
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock)
    else:
        mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Bloque 1: TavilyContextoAdapter
# ---------------------------------------------------------------------------
class TestTavilyContextoAdapter:
    def test_busca_y_retorna_contexto_con_evidencias(
        self, empresa: Empresa, trigger: Trigger
    ):
        payload = {
            "results": [
                {
                    "content": "Acme SaaS anuncia expansión regional.",
                    "url": "https://a.com/1",
                },
                {"content": "Acme SaaS contrata nuevo CTO.", "url": "https://a.com/2"},
            ]
        }
        with patch("requests.post", return_value=_mock_response(payload)):
            adapter = TavilyContextoAdapter(api_key="test-key")
            ctx = adapter.obtener_contexto(empresa, [trigger])

        assert len(ctx.evidencias) == 2
        assert len(ctx.fuentes) == 2
        assert "https://a.com/1" in ctx.fuentes

    def test_cero_resultados_retorna_contexto_vacio(
        self, empresa: Empresa, trigger: Trigger
    ):
        with patch("requests.post", return_value=_mock_response({"results": []})):
            adapter = TavilyContextoAdapter(api_key="test-key")
            ctx = adapter.obtener_contexto(empresa, [trigger])

        assert ctx.evidencias == []
        assert ctx.fuentes == []

    def test_http_error_no_propaga_retorna_contexto_vacio(
        self, empresa: Empresa, trigger: Trigger
    ):
        with patch("requests.post", return_value=_mock_response({}, status_code=429)):
            adapter = TavilyContextoAdapter(api_key="test-key")
            ctx = adapter.obtener_contexto(empresa, [trigger])

        assert ctx.evidencias == []
        assert ctx.fuentes == []

    def test_timeout_no_propaga_retorna_contexto_vacio(
        self, empresa: Empresa, trigger: Trigger
    ):
        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            adapter = TavilyContextoAdapter(api_key="test-key")
            ctx = adapter.obtener_contexto(empresa, [trigger])

        assert ctx.evidencias == []

    def test_sin_api_key_no_llama_a_la_red(self, empresa: Empresa, trigger: Trigger):
        with patch("requests.post") as mock_post:
            adapter = TavilyContextoAdapter(api_key=None)
            adapter._api_key = None
            ctx = adapter.obtener_contexto(empresa, [trigger])

        assert ctx.evidencias == []
        mock_post.assert_not_called()

    def test_sin_triggers_no_lanza_y_construye_query_solo_con_empresa(
        self, empresa: Empresa
    ):
        with patch(
            "requests.post", return_value=_mock_response({"results": []})
        ) as mock_post:
            adapter = TavilyContextoAdapter(api_key="test-key")
            adapter.obtener_contexto(empresa, [])

        call_kwargs = mock_post.call_args.kwargs
        assert "Acme SaaS" in call_kwargs["json"]["query"]

    def test_resultado_sin_url_o_contenido_es_omitido(
        self, empresa: Empresa, trigger: Trigger
    ):
        payload = {
            "results": [
                {"content": "", "url": "https://a.com/1"},
                {"content": "Contenido válido", "url": ""},
                {"content": "Contenido bueno", "url": "https://a.com/3"},
            ]
        }
        with patch("requests.post", return_value=_mock_response(payload)):
            adapter = TavilyContextoAdapter(api_key="test-key")
            ctx = adapter.obtener_contexto(empresa, [trigger])

        assert ctx.evidencias == ["Contenido bueno"]
        assert ctx.fuentes == ["https://a.com/3"]


# ---------------------------------------------------------------------------
# Bloque 2: GroqRedactorAdapter
# ---------------------------------------------------------------------------
class TestGroqRedactorAdapter:
    def _mock_groq_client(self, contenido: str | None) -> MagicMock:
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=contenido))]
        mock_client.chat.completions.create.return_value = mock_completion
        return mock_client

    def test_redacta_mensaje_valido_en_borrador(
        self, decisor: Decisor, empresa: Empresa, trigger: Trigger
    ):
        from src.core.domain.models import ContextoRAG

        contenido = "Vi que Acme abrió vacantes técnicas\n---CUERPO---\nHola Ana, notamos que..."
        with patch("groq.Groq", return_value=self._mock_groq_client(contenido)):
            adapter = GroqRedactorAdapter(api_key="test-key")
            mensaje = adapter.redactar(decisor, empresa, [trigger], ContextoRAG())

        assert mensaje.estado == EstadoMensaje.BORRADOR
        assert mensaje.asunto == "Vi que Acme abrió vacantes técnicas"
        assert "Hola Ana" in mensaje.cuerpo
        assert mensaje.decisor_id == decisor.id

    def test_respuesta_sin_separador_produce_error_redaccion(
        self, decisor: Decisor, empresa: Empresa, trigger: Trigger
    ):
        from src.core.domain.models import ContextoRAG

        contenido = "Un texto sin el separador esperado"
        with patch("groq.Groq", return_value=self._mock_groq_client(contenido)):
            adapter = GroqRedactorAdapter(api_key="test-key")
            mensaje = adapter.redactar(decisor, empresa, [trigger], ContextoRAG())

        assert mensaje.estado == EstadoMensaje.ERROR_REDACCION

    def test_contenido_vacio_produce_error_redaccion(
        self, decisor: Decisor, empresa: Empresa, trigger: Trigger
    ):
        from src.core.domain.models import ContextoRAG

        with patch("groq.Groq", return_value=self._mock_groq_client(None)):
            adapter = GroqRedactorAdapter(api_key="test-key")
            mensaje = adapter.redactar(decisor, empresa, [trigger], ContextoRAG())

        assert mensaje.estado == EstadoMensaje.ERROR_REDACCION

    def test_rate_limit_error_no_propaga_produce_error_redaccion(
        self, decisor: Decisor, empresa: Empresa, trigger: Trigger
    ):
        import groq as groq_sdk

        from src.core.domain.models import ContextoRAG

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = groq_sdk.RateLimitError(
            message="rate limited", response=MagicMock(), body=None
        )
        with patch("groq.Groq", return_value=mock_client):
            adapter = GroqRedactorAdapter(api_key="test-key")
            mensaje = adapter.redactar(decisor, empresa, [trigger], ContextoRAG())

        assert mensaje.estado == EstadoMensaje.ERROR_REDACCION

    def test_error_inesperado_no_propaga_produce_error_redaccion(
        self, decisor: Decisor, empresa: Empresa, trigger: Trigger
    ):
        from src.core.domain.models import ContextoRAG

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("fallo simulado")
        with patch("groq.Groq", return_value=mock_client):
            adapter = GroqRedactorAdapter(api_key="test-key")
            mensaje = adapter.redactar(decisor, empresa, [trigger], ContextoRAG())

        assert mensaje.estado == EstadoMensaje.ERROR_REDACCION

    def test_sin_api_key_produce_error_redaccion_sin_llamar_red(
        self, decisor: Decisor, empresa: Empresa, trigger: Trigger
    ):
        from src.core.domain.models import ContextoRAG

        with patch("groq.Groq") as mock_groq_ctor:
            adapter = GroqRedactorAdapter(api_key=None)
            mensaje = adapter.redactar(decisor, empresa, [trigger], ContextoRAG())

        assert mensaje.estado == EstadoMensaje.ERROR_REDACCION
        mock_groq_ctor.assert_not_called()

    def test_fuentes_citadas_se_propagan_desde_contexto(
        self, decisor: Decisor, empresa: Empresa, trigger: Trigger
    ):
        from src.core.domain.models import ContextoRAG

        contenido = "Asunto de prueba\n---CUERPO---\nCuerpo de prueba"
        ctx = ContextoRAG(evidencias=["algo"], fuentes=["https://fuente.com/1"])
        with patch("groq.Groq", return_value=self._mock_groq_client(contenido)):
            adapter = GroqRedactorAdapter(api_key="test-key")
            mensaje = adapter.redactar(decisor, empresa, [trigger], ctx)

        assert mensaje.fuentes_citadas == ["https://fuente.com/1"]


# ---------------------------------------------------------------------------
# Bloque 3: ResendEnvioAdapter — mitad síncrona
# ---------------------------------------------------------------------------
class TestResendEnvioAdapter:
    def test_envio_exitoso_retorna_entregado(self, decisor: Decisor):
        from src.core.domain.models import Mensaje

        mensaje = Mensaje(
            decisor_id=decisor.id,
            asunto="Asunto",
            cuerpo="Cuerpo",
            estado=EstadoMensaje.APROBADO,
        )
        with patch("requests.post", return_value=_mock_response({"id": "abc123"})):
            adapter = ResendEnvioAdapter(
                api_key="test-key", remitente="ventas@prospector.com"
            )
            resultado = adapter.enviar(mensaje, decisor)

        assert resultado == ResultadoEnvio.ENTREGADO

    def test_http_error_4xx_retorna_rechazado(self, decisor: Decisor):
        from src.core.domain.models import Mensaje

        mensaje = Mensaje(
            decisor_id=decisor.id,
            asunto="Asunto",
            cuerpo="Cuerpo",
            estado=EstadoMensaje.APROBADO,
        )
        with patch("requests.post", return_value=_mock_response({}, status_code=422)):
            adapter = ResendEnvioAdapter(api_key="test-key")
            resultado = adapter.enviar(mensaje, decisor)

        assert resultado == ResultadoEnvio.RECHAZADO

    def test_timeout_retorna_error(self, decisor: Decisor):
        from src.core.domain.models import Mensaje

        mensaje = Mensaje(
            decisor_id=decisor.id,
            asunto="Asunto",
            cuerpo="Cuerpo",
            estado=EstadoMensaje.APROBADO,
        )
        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            adapter = ResendEnvioAdapter(api_key="test-key")
            resultado = adapter.enviar(mensaje, decisor)

        assert resultado == ResultadoEnvio.ERROR

    def test_sin_api_key_retorna_error_sin_llamar_red(self, decisor: Decisor):
        from src.core.domain.models import Mensaje

        mensaje = Mensaje(
            decisor_id=decisor.id,
            asunto="Asunto",
            cuerpo="Cuerpo",
            estado=EstadoMensaje.APROBADO,
        )
        with patch("requests.post") as mock_post:
            adapter = ResendEnvioAdapter(api_key=None)
            adapter._api_key = None
            resultado = adapter.enviar(mensaje, decisor)

        assert resultado == ResultadoEnvio.ERROR
        mock_post.assert_not_called()

    def test_decisor_sin_correo_retorna_error_sin_llamar_red(self, empresa: Empresa):
        from src.core.domain.models import Mensaje

        decisor_sin_correo = Decisor(
            empresa_id=empresa.id,
            nombre="Sin Correo",
            cargo_original="CTO",
            cargo_normalizado="CTO",
            seniority=Seniority.C_LEVEL,
            correo=None,
            confianza_dato=0.9,
        )
        mensaje = Mensaje(
            decisor_id=decisor_sin_correo.id,
            asunto="Asunto",
            cuerpo="Cuerpo",
            estado=EstadoMensaje.APROBADO,
        )
        with patch("requests.post") as mock_post:
            adapter = ResendEnvioAdapter(api_key="test-key")
            resultado = adapter.enviar(mensaje, decisor_sin_correo)

        assert resultado == ResultadoEnvio.ERROR
        mock_post.assert_not_called()

    def test_error_inesperado_no_propaga_retorna_error(self, decisor: Decisor):
        from src.core.domain.models import Mensaje

        mensaje = Mensaje(
            decisor_id=decisor.id,
            asunto="Asunto",
            cuerpo="Cuerpo",
            estado=EstadoMensaje.APROBADO,
        )
        with patch("requests.post", side_effect=RuntimeError("fallo simulado")):
            adapter = ResendEnvioAdapter(api_key="test-key")
            resultado = adapter.enviar(mensaje, decisor)

        assert resultado == ResultadoEnvio.ERROR


# ---------------------------------------------------------------------------
# Bloque 4: procesar_webhook_rebote — mitad asíncrona, función pura
# ---------------------------------------------------------------------------
class TestProcesarWebhookRebote:
    def test_evento_bounced_retorna_rebotado(self):
        payload = {"type": "email.bounced", "data": {"email_id": "abc"}}
        assert procesar_webhook_rebote(payload) == ResultadoEnvio.REBOTADO

    def test_evento_delivery_delayed_retorna_rebotado(self):
        payload = {"type": "email.delivery_delayed", "data": {}}
        assert procesar_webhook_rebote(payload) == ResultadoEnvio.REBOTADO

    def test_evento_delivered_retorna_entregado(self):
        payload = {"type": "email.delivered", "data": {}}
        assert procesar_webhook_rebote(payload) == ResultadoEnvio.ENTREGADO

    def test_evento_no_mapeado_retorna_none(self):
        payload = {"type": "email.opened", "data": {}}
        assert procesar_webhook_rebote(payload) is None

    def test_payload_sin_type_retorna_none(self):
        assert procesar_webhook_rebote({"data": {}}) is None

    def test_payload_no_dict_retorna_none_sin_lanzar(self):
        assert procesar_webhook_rebote("no soy un dict") is None  # type: ignore[arg-type]
        assert procesar_webhook_rebote(None) is None  # type: ignore[arg-type]
        assert procesar_webhook_rebote([1, 2, 3]) is None  # type: ignore[arg-type]

    def test_payload_vacio_retorna_none(self):
        assert procesar_webhook_rebote({}) is None


class TestTavilyDescribirEmpresa:
    """
    describir_empresa (respaldo de contexto, 26-jul-2026): busca en la web una
    descripción de la empresa para clasificar cuando la homepage no se pudo leer.
    """

    def _mock_post(self, data: dict, status_code: int = 200) -> MagicMock:
        mock = MagicMock()
        mock.status_code = status_code
        mock.json.return_value = data
        mock.raise_for_status.return_value = None
        return mock

    def test_describir_empresa_concatena_answer_y_resultados(self, empresa: Empresa):
        data = {
            "answer": "Acme es una fábrica de software colombiana.",
            "results": [
                {"content": "Desarrolla productos a la medida.", "url": "https://x"},
                {"content": "Sede en Bogotá.", "url": "https://y"},
            ],
        }
        with patch("requests.post", return_value=self._mock_post(data)):
            adapter = TavilyContextoAdapter(api_key="test-key")
            texto = adapter.describir_empresa(empresa)

        assert texto is not None
        assert "fábrica de software" in texto
        assert "Bogotá" in texto

    def test_describir_empresa_sin_api_key_es_none(self, empresa: Empresa):
        adapter = TavilyContextoAdapter(api_key=None)
        # Forzar ausencia de env var no es necesario: si _api_key es None,
        # describir_empresa retorna None sin tocar la red.
        adapter._api_key = None
        assert adapter.describir_empresa(empresa) is None

    def test_describir_empresa_error_red_es_none(self, empresa: Empresa):
        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            adapter = TavilyContextoAdapter(api_key="test-key")
            assert adapter.describir_empresa(empresa) is None
