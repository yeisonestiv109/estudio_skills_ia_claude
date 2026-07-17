"""
Tests unitarios de PropuestaValorAdapter — sin llamadas reales a red ni LLM.

Mockea requests.get (lectura de homepage) y groq.Groq (clasificación).
Ningún test de este archivo consume créditos reales de Groq ni hace
peticiones HTTP reales.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.adapters.triggers.propuesta_valor_adapter import PropuestaValorAdapter
from src.core.domain.models import (
    CategoriaEmpresa,
    Empresa,
    EstimacionTamano,
    OrigenTrigger,
    TamanoEmpresa,
)


@pytest.fixture
def empresa() -> Empresa:
    return Empresa(
        nombre="Acme Consulting",
        dominio="acme-consulting.com",
        tamano=TamanoEmpresa.SME,
        vertical="Consultoría IT",
    )


def _mock_html_response(texto_visible: str, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = f"<html><body><p>{texto_visible}</p></body></html>"
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock
        )
    else:
        mock.raise_for_status.return_value = None
    return mock


def _mock_groq_client(contenido_json: str | None) -> MagicMock:
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content=contenido_json))]
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


def _mock_html_response_spa(
    title: str = "", meta_description: str = "", body_visible: str = "", status_code: int = 200
) -> MagicMock:
    """
    Simula una SPA en JavaScript: <head> con title/meta description estáticos,
    pero <body> con poco o ningún texto visible sin ejecutar JS (caso Parcero).
    """
    meta_tag = (
        f'<meta name="description" content="{meta_description}">'
        if meta_description
        else ""
    )
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = (
        f"<html><head><title>{title}</title>{meta_tag}</head>"
        f"<body><div id='root'>{body_visible}</div></body></html>"
    )
    mock.raise_for_status.return_value = None
    return mock


class TestPropuestaValorAdapterClasificar:
    def test_vendor_it_true_mapea_a_agencia_it(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME"}'
        with (
            patch("requests.get", return_value=_mock_html_response("Somos una fábrica de software")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado == CategoriaEmpresa.AGENCIA_IT

    def test_vendor_it_false_retorna_none(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": false, "tamano_estimado": "MID_MARKET"}'
        with (
            patch("requests.get", return_value=_mock_html_response("Somos un banco regional")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_es_vendor_it_expone_la_senal_binaria_cruda(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": false, "tamano_estimado": null}'
        with (
            patch("requests.get", return_value=_mock_html_response("Somos un banco regional")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.es_vendor_it(empresa)

        assert resultado is False

    def test_sin_api_key_retorna_none_sin_llamar_red(self, empresa: Empresa):
        with patch("requests.get") as mock_get:
            adapter = PropuestaValorAdapter(api_key=None)
            resultado = adapter.clasificar(empresa)

        assert resultado is None
        mock_get.assert_not_called()

    def test_error_de_red_leyendo_homepage_retorna_none_sin_llamar_llm(
        self, empresa: Empresa
    ):
        mock_client = MagicMock()
        with (
            patch("requests.get", side_effect=requests.exceptions.Timeout),
            patch("groq.Groq", return_value=mock_client),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None
        # El cliente se instancia (lazy), pero nunca debe completar una llamada
        # al LLM si la lectura de la homepage falló antes.
        mock_client.chat.completions.create.assert_not_called()

    def test_http_error_leyendo_homepage_retorna_none(self, empresa: Empresa):
        with patch("requests.get", return_value=_mock_html_response("", status_code=404)):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_llm_contenido_vacio_retorna_none(self, empresa: Empresa):
        with (
            patch("requests.get", return_value=_mock_html_response("Texto de la empresa")),
            patch("groq.Groq", return_value=_mock_groq_client(None)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_llm_respuesta_con_formato_invalido_retorna_none(self, empresa: Empresa):
        with (
            patch("requests.get", return_value=_mock_html_response("Texto de la empresa")),
            patch("groq.Groq", return_value=_mock_groq_client('{"campo_incorrecto": true}')),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_rate_limit_error_no_propaga_retorna_none(self, empresa: Empresa):
        import groq as groq_sdk

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = groq_sdk.RateLimitError(
            message="rate limited", response=MagicMock(), body=None
        )
        with (
            patch("requests.get", return_value=_mock_html_response("Texto de la empresa")),
            patch("groq.Groq", return_value=mock_client),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_homepage_sin_texto_visible_retorna_none_sin_llamar_llm(
        self, empresa: Empresa
    ):
        mock_html = MagicMock()
        mock_html.status_code = 200
        mock_html.text = "<html><body><script>solo_js();</script></body></html>"
        mock_html.raise_for_status.return_value = None

        mock_client = MagicMock()
        with (
            patch("requests.get", return_value=mock_html),
            patch("groq.Groq", return_value=mock_client),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None
        mock_client.chat.completions.create.assert_not_called()


class TestPropuestaValorAdapterEstimarTamano:
    def test_retorna_estimacion_con_origen_propuesta_valor(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "MID_MARKET"}'
        with (
            patch("requests.get", return_value=_mock_html_response("Somos una empresa mediana")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            estimacion = adapter.estimar_tamano(empresa)

        assert isinstance(estimacion, EstimacionTamano)
        assert estimacion.origen == OrigenTrigger.PROPUESTA_VALOR
        assert estimacion.tamano_estimado == TamanoEmpresa.MID_MARKET
        assert estimacion.confianza < 1.0  # señal semántica, no dato firmográfico real

    def test_tamano_null_del_llm_retorna_none(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": null}'
        with (
            patch("requests.get", return_value=_mock_html_response("Texto ambiguo")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is None

    def test_sin_api_key_retorna_none(self, empresa: Empresa):
        adapter = PropuestaValorAdapter(api_key=None)
        assert adapter.estimar_tamano(empresa) is None

    def test_una_sola_llamada_llm_alimenta_ambos_puertos(self, empresa: Empresa):
        """
        clasificar() y estimar_tamano() sobre la MISMA empresa deben compartir
        el cache interno: una sola lectura de homepage + una sola llamada LLM.
        """
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME"}'
        mock_groq = _mock_groq_client(json_llm)

        with (
            patch("requests.get", return_value=_mock_html_response("Texto de la empresa")) as mock_get,
            patch("groq.Groq", return_value=mock_groq),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            adapter.clasificar(empresa)
            adapter.estimar_tamano(empresa)

        mock_get.assert_called_once()
        mock_groq.chat.completions.create.assert_called_once()


class TestPropuestaValorAdapterPaisHq:
    """Fix Falla 2 (caso Parcero/UK): señal semántica de país de HQ."""

    def test_pais_hq_extraido_correctamente(self, empresa: Empresa):
        json_llm = (
            '{"es_vendor_it": true, "tamano_estimado": "SME", "pais_hq": "GB"}'
        )
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("HQ en Londres, Reino Unido"),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.pais_hq(empresa)

        assert resultado == "GB"

    def test_pais_hq_null_del_llm_retorna_none(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": null, "pais_hq": null}'
        with (
            patch("requests.get", return_value=_mock_html_response("Texto sin pistas de país")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.pais_hq(empresa)

        assert resultado is None

    def test_pais_hq_ausente_en_json_retorna_none(self, empresa: Empresa):
        """Compatibilidad hacia atrás: el campo es opcional en el esquema del LLM."""
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME"}'
        with (
            patch("requests.get", return_value=_mock_html_response("Texto de la empresa")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.pais_hq(empresa)

        assert resultado is None

    def test_pais_hq_normaliza_minusculas_a_mayusculas(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME", "pais_hq": "gb"}'
        with (
            patch("requests.get", return_value=_mock_html_response("HQ en Londres")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.pais_hq(empresa)

        assert resultado == "GB"

    def test_pais_hq_valor_alucinado_no_alpha2_se_descarta(self, empresa: Empresa):
        """
        Defensa contra alucinación: si el LLM responde el nombre completo del
        país ("United Kingdom") en vez del código ISO Alpha-2, se descarta
        como None en vez de propagar basura a PoliticaValidacionGeografica.
        """
        json_llm = (
            '{"es_vendor_it": true, "tamano_estimado": "SME", '
            '"pais_hq": "United Kingdom"}'
        )
        with (
            patch("requests.get", return_value=_mock_html_response("HQ en Londres")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.pais_hq(empresa)

        assert resultado is None

    def test_pais_hq_sin_api_key_retorna_none(self, empresa: Empresa):
        adapter = PropuestaValorAdapter(api_key=None)
        assert adapter.pais_hq(empresa) is None

    def test_pais_hq_comparte_cache_con_clasificar(self, empresa: Empresa):
        """Mismo patrón de cache que estimar_tamano(): una sola llamada LLM."""
        json_llm = (
            '{"es_vendor_it": true, "tamano_estimado": "SME", "pais_hq": "CO"}'
        )
        mock_groq = _mock_groq_client(json_llm)

        with (
            patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ) as mock_get,
            patch("groq.Groq", return_value=mock_groq),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            adapter.clasificar(empresa)
            adapter.pais_hq(empresa)

        mock_get.assert_called_once()
        mock_groq.chat.completions.create.assert_called_once()


class TestPropuestaValorAdapterFallbackMetaTags:
    """
    Fix Falla 1 (fail-open, caso Parcero): fallback de <title>/<meta
    name="description"> cuando el texto visible del body es insuficiente
    (típico de SPAs en JavaScript sin server-side rendering).
    """

    def test_fallback_usa_title_y_meta_description_cuando_body_vacio(
        self, empresa: Empresa
    ):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME", "pais_hq": "GB"}'
        html_mock = _mock_html_response_spa(
            title="Parcero | Digital Agency",
            meta_description="We build apps and sites for clients worldwide. HQ London, UK.",
            body_visible="",  # SPA: nada renderizado sin JS
        )
        mock_client = _mock_groq_client(json_llm)

        with (
            patch("requests.get", return_value=html_mock),
            patch("groq.Groq", return_value=mock_client),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        # El LLM SÍ fue invocado (antes del fix, el texto vacío hacía que
        # _leer_texto_homepage retornara None y la llamada nunca ocurriera).
        mock_client.chat.completions.create.assert_called_once()
        assert resultado == CategoriaEmpresa.AGENCIA_IT

        # El texto enviado al LLM debe contener el contenido del fallback.
        texto_enviado = mock_client.chat.completions.create.call_args.kwargs[
            "messages"
        ][1]["content"]
        assert "Digital Agency" in texto_enviado
        assert "London" in texto_enviado

    def test_sin_title_ni_meta_y_body_vacio_sigue_retornando_none(
        self, empresa: Empresa
    ):
        """Si NI el fallback tiene contenido, el comportamiento previo se preserva."""
        html_mock = _mock_html_response_spa(title="", meta_description="", body_visible="")
        mock_client = MagicMock()

        with (
            patch("requests.get", return_value=html_mock),
            patch("groq.Groq", return_value=mock_client),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None
        mock_client.chat.completions.create.assert_not_called()

    def test_body_suficiente_no_activa_fallback_pero_no_lo_rompe(
        self, empresa: Empresa
    ):
        """Con body visible suficiente, el título/meta no son necesarios (pero no dañan)."""
        json_llm = '{"es_vendor_it": false, "tamano_estimado": "MID_MARKET"}'
        html_mock = _mock_html_response_spa(
            title="Acme Bank",
            meta_description="A regional bank.",
            body_visible=(
                "Somos un banco regional con más de cien años de historia "
                "sirviendo a nuestros clientes en toda la región con productos "
                "financieros diversos y atención personalizada de alta calidad."
            ),
        )
        mock_client = _mock_groq_client(json_llm)

        with (
            patch("requests.get", return_value=html_mock),
            patch("groq.Groq", return_value=mock_client),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None
        mock_client.chat.completions.create.assert_called_once()
