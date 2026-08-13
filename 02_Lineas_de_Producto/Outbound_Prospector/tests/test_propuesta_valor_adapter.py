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

import groq as groq_sdk

from src.adapters.llm.groq_key_pool import GroqKeyPool
from src.adapters.triggers.propuesta_valor_adapter import PropuestaValorAdapter
from src.core.domain.models import (
    CategoriaEmpresa,
    Empresa,
    EstimacionTamano,
    OrigenTrigger,
    TamanoEmpresa,
    TipoOrganizacion,
)


def _rate_limit_error(mensaje: str) -> groq_sdk.RateLimitError:
    mock_response = MagicMock()
    mock_response.request = MagicMock()
    return groq_sdk.RateLimitError(mensaje, response=mock_response, body=None)


@pytest.fixture
def empresa() -> Empresa:
    return Empresa(
        nombre="Acme Consulting",
        dominio="acme-consulting.com",
        tamano=TamanoEmpresa.SME,
        vertical="Consultoría IT",
    )


@pytest.fixture(autouse=True)
def _dns_siempre_resuelve():
    """
    Mantiene los tests herméticos (sin red real). El pre-check DNS de
    _leer_texto_homepage (fix 25-jul-2026) llama socket.getaddrinfo; por defecto
    lo simulamos exitoso para que los tests que mockean requests.get sigan
    ejercitando la lectura de homepage. Los tests de TestDominioResuelveDNS
    sobreescriben este patch dentro de su propio `with`.
    """
    import src.adapters.triggers.propuesta_valor_adapter as mod

    with patch.object(
        mod.socket,
        "getaddrinfo",
        return_value=[(2, 1, 6, "", ("1.2.3.4", 0))],
    ):
        yield


def _mock_html_response(texto_visible: str, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = f"<html><body><p>{texto_visible}</p></body></html>"
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock)
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
    title: str = "",
    meta_description: str = "",
    body_visible: str = "",
    status_code: int = 200,
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
            patch(
                "requests.get",
                return_value=_mock_html_response("Somos una fábrica de software"),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado == CategoriaEmpresa.AGENCIA_IT

    def test_vendor_it_false_retorna_none(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": false, "tamano_estimado": "MID_MARKET"}'
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("Somos un banco regional"),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_es_vendor_it_expone_la_senal_binaria_cruda(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": false, "tamano_estimado": null}'
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("Somos un banco regional"),
            ),
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
        """
        Regresión (auditoría 22-Jul-2026): con la cascada de reintentos
        técnicos (rutas alternas + fallback Playwright), un Timeout en TODAS
        las rutas HTTP debe seguir cayendo al fallback de Playwright antes
        de rendirse — se mockea explícitamente para que ese fallback también
        falle, preservando la intención original del test (nunca llamar al
        LLM sin texto disponible), sin depender de que Playwright/Chromium
        estén o no instalados en el entorno de CI.
        """
        mock_client = MagicMock()
        with (
            patch("requests.get", side_effect=requests.exceptions.Timeout),
            patch("groq.Groq", return_value=mock_client),
            patch(
                "src.adapters.triggers.propuesta_valor_adapter._renderizar_con_playwright",
                return_value=None,
            ),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None
        # El cliente se instancia (lazy), pero nunca debe completar una llamada
        # al LLM si la lectura de la homepage falló antes.
        mock_client.chat.completions.create.assert_not_called()

    def test_http_error_leyendo_homepage_retorna_none(self, empresa: Empresa):
        with patch(
            "requests.get", return_value=_mock_html_response("", status_code=404)
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_llm_contenido_vacio_retorna_none(self, empresa: Empresa):
        with (
            patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ),
            patch("groq.Groq", return_value=_mock_groq_client(None)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_llm_respuesta_con_formato_invalido_retorna_none(self, empresa: Empresa):
        with (
            patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ),
            patch(
                "groq.Groq",
                return_value=_mock_groq_client('{"campo_incorrecto": true}'),
            ),
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
            patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ),
            patch("groq.Groq", return_value=mock_client),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_homepage_sin_texto_visible_retorna_none_sin_llamar_llm(
        self, empresa: Empresa
    ):
        """
        Regresión (auditoría 22-Jul-2026): ver nota en
        test_error_de_red_leyendo_homepage_retorna_none_sin_llamar_llm — se
        mockea el fallback de Playwright para que también falle, aislando
        el test del estado real de Chromium en el entorno de ejecución.
        """
        mock_html = MagicMock()
        mock_html.status_code = 200
        mock_html.text = "<html><body><script>solo_js();</script></body></html>"
        mock_html.raise_for_status.return_value = None

        mock_client = MagicMock()
        with (
            patch("requests.get", return_value=mock_html),
            patch("groq.Groq", return_value=mock_client),
            patch(
                "src.adapters.triggers.propuesta_valor_adapter._renderizar_con_playwright",
                return_value=None,
            ),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None
        mock_client.chat.completions.create.assert_not_called()


class TestPropuestaValorAdapterEstimarTamano:
    def test_retorna_estimacion_con_origen_propuesta_valor(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "MID_MARKET"}'
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("Somos una empresa mediana"),
            ),
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
            patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ) as mock_get,
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
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME", "pais_hq": "GB"}'
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
            patch(
                "requests.get",
                return_value=_mock_html_response("Texto sin pistas de país"),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.pais_hq(empresa)

        assert resultado is None

    def test_pais_hq_ausente_en_json_retorna_none(self, empresa: Empresa):
        """Compatibilidad hacia atrás: el campo es opcional en el esquema del LLM."""
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME"}'
        with (
            patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ),
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
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME", "pais_hq": "CO"}'
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
            meta_description="We build apps for clients worldwide. HQ London.",
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
        """
        Si NI el fallback de meta tags NI el fallback de Playwright tienen
        contenido, el comportamiento previo se preserva (regresión, auditoría
        22-Jul-2026 — ver nota en test_error_de_red_leyendo_homepage_...).
        """
        html_mock = _mock_html_response_spa(
            title="", meta_description="", body_visible=""
        )
        mock_client = MagicMock()

        with (
            patch("requests.get", return_value=html_mock),
            patch("groq.Groq", return_value=mock_client),
            patch(
                "src.adapters.triggers.propuesta_valor_adapter._renderizar_con_playwright",
                return_value=None,
            ),
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


class TestPropuestaValorAdapterReintentosTecnicos:
    """
    Estrategia de reintentos técnicos (respuesta a hallazgo de corrida real):
    muchos casos PENDIENTE_REVISION_MANUAL son fallas técnicas de lectura,
    no ambigüedad semántica real. La cascada es: raíz → rutas alternas
    (/nosotros, /about, /quienes-somos, /about-us) → fallback Playwright
    (render con JS), deteniéndose en el primer resultado utilizable.
    """

    def _mock_html_vacio(self) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 200
        mock.text = "<html><body><script>solo_js();</script></body></html>"
        mock.raise_for_status.return_value = None
        return mock

    def test_ruta_alterna_nosotros_recupera_texto_cuando_raiz_esta_vacia(
        self, empresa: Empresa
    ):
        """Si la raíz no da texto, debe probar /nosotros antes de rendirse."""
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME"}'
        respuesta_raiz_vacia = self._mock_html_vacio()
        respuesta_nosotros_con_texto = _mock_html_response(
            "Somos una consultora de tecnología con más de veinte años de "
            "experiencia ayudando a empresas a transformar sus procesos."
        )

        with (
            patch(
                "requests.get",
                side_effect=[respuesta_raiz_vacia, respuesta_nosotros_con_texto],
            ) as mock_get,
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado == CategoriaEmpresa.AGENCIA_IT
        # 1ra llamada a la raíz, 2da a /nosotros (primera ruta alterna probada).
        assert mock_get.call_count == 2
        segunda_url = mock_get.call_args_list[1].args[0]
        assert segunda_url.endswith("/nosotros")

    def test_prueba_multiples_rutas_alternas_en_orden_hasta_encontrar_texto(
        self, empresa: Empresa
    ):
        """Si /nosotros también está vacía, debe seguir con /about, etc."""
        json_llm = '{"es_vendor_it": false, "tamano_estimado": null}'
        vacio = self._mock_html_vacio()
        con_texto = _mock_html_response(
            "We are a regional bank serving clients across the country with "
            "a wide range of financial products and personalized service."
        )

        with (
            patch(
                "requests.get",
                side_effect=[vacio, vacio, con_texto],  # raíz, /nosotros, /about
            ) as mock_get,
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None  # es_vendor_it=false, pero SÍ se pudo clasificar
        assert mock_get.call_count == 3
        tercera_url = mock_get.call_args_list[2].args[0]
        assert tercera_url.endswith("/about")

    def test_raiz_con_texto_corto_no_activa_rutas_alternas(self, empresa: Empresa):
        """
        Si la raíz SÍ dio algo de texto (aunque corto), no debe gastar
        llamadas adicionales en rutas alternas — solo se activan si la raíz
        no dio absolutamente nada utilizable.
        """
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "STARTUP"}'
        respuesta_corta = _mock_html_response("Somos ACME.")

        with (
            patch("requests.get", return_value=respuesta_corta) as mock_get,
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            adapter.clasificar(empresa)

        mock_get.assert_called_once()

    def test_todas_las_rutas_alternas_vacias_activa_fallback_playwright(
        self, empresa: Empresa
    ):
        """
        Si NINGUNA ruta liviana (raíz + alternas) dio texto, debe invocarse
        el fallback pesado de Playwright como último recurso.
        """
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "MID_MARKET"}'
        vacio = self._mock_html_vacio()

        with (
            patch("requests.get", return_value=vacio),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
            patch(
                "src.adapters.triggers.propuesta_valor_adapter._renderizar_con_playwright",
                return_value="Somos una plataforma SaaS mediana con oficinas regionales.",
            ) as mock_playwright,
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        mock_playwright.assert_called_once()
        assert resultado == CategoriaEmpresa.AGENCIA_IT

    def test_playwright_tambien_falla_retorna_none_sin_lanzar(self, empresa: Empresa):
        """Si ni las rutas alternas ni Playwright dan texto, retorna None (no lanza)."""
        vacio = self._mock_html_vacio()

        with (
            patch("requests.get", return_value=vacio),
            patch(
                "src.adapters.triggers.propuesta_valor_adapter._renderizar_con_playwright",
                return_value=None,
            ),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_renderizar_con_playwright_sin_libreria_instalada_retorna_none(self):
        """Contrato de degradación: si playwright no está disponible, no debe lanzar."""
        import builtins

        from src.adapters.triggers.propuesta_valor_adapter import (
            _renderizar_con_playwright,
        )

        real_import = builtins.__import__

        def _import_bloqueando_playwright(name, *args, **kwargs):
            if name == "playwright.sync_api" or name.startswith("playwright"):
                raise ImportError("simulado: playwright no instalado")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_import_bloqueando_playwright):
            resultado = _renderizar_con_playwright("https://ejemplo.com")

        assert resultado is None

    def test_renderizar_con_playwright_excepcion_de_navegador_retorna_none(self):
        """Si Playwright está instalado pero el navegador falla al lanzar, retorna None."""
        from src.adapters.triggers.propuesta_valor_adapter import (
            _renderizar_con_playwright,
        )

        mock_pw_context = MagicMock()
        mock_pw_context.__enter__.side_effect = RuntimeError("navegador no disponible")

        with patch("playwright.sync_api.sync_playwright", return_value=mock_pw_context):
            resultado = _renderizar_con_playwright("https://ejemplo.com")

        assert resultado is None

    def test_renderizar_con_playwright_exito_retorna_texto(self):
        """Camino feliz del fallback: retorna el texto visible renderizado."""
        from src.adapters.triggers.propuesta_valor_adapter import (
            _renderizar_con_playwright,
        )

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Texto renderizado con JavaScript"
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_pw_instance = MagicMock(chromium=mock_chromium)
        mock_pw_context = MagicMock()
        mock_pw_context.__enter__.return_value = mock_pw_instance

        with patch("playwright.sync_api.sync_playwright", return_value=mock_pw_context):
            resultado = _renderizar_con_playwright("https://ejemplo.com")

        assert resultado == "Texto renderizado con JavaScript"
        mock_browser.close.assert_called_once()


class TestPropuestaValorAdapterTipoOrganizacion:
    """
    FIX #5: el LLM clasifica también el TIPO de organización en la MISMA
    llamada cacheada. Alimenta PoliticaTipoOrganizacion (gate de tipo).
    """

    def test_tipo_gobierno_extraido_correctamente(self, empresa: Empresa):
        json_llm = (
            '{"es_vendor_it": false, "tamano_estimado": "ENTERPRISE", '
            '"pais_hq": "CO", "tipo_organizacion": "GOBIERNO"}'
        )
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("Somos una entidad del Estado"),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.tipo_organizacion(empresa)

        assert resultado == TipoOrganizacion.GOBIERNO

    def test_tipo_empresa_privada_extraido_correctamente(self, empresa: Empresa):
        json_llm = (
            '{"es_vendor_it": false, "tamano_estimado": "SME", '
            '"tipo_organizacion": "EMPRESA_PRIVADA"}'
        )
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("Somos una empresa privada"),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.tipo_organizacion(empresa)

        assert resultado == TipoOrganizacion.EMPRESA_PRIVADA

    def test_tipo_ausente_o_null_retorna_none(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": false, "tamano_estimado": "SME", "tipo_organizacion": null}'
        with (
            patch("requests.get", return_value=_mock_html_response("Texto ambiguo")),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            resultado = adapter.tipo_organizacion(empresa)

        assert resultado is None

    def test_tipo_valor_no_reconocido_se_descarta_sin_romper_otras_senales(
        self, empresa: Empresa
    ):
        """
        Un tipo fuera del vocabulario NO debe invalidar toda la respuesta: se
        cae a None (tipo) pero es_vendor_it/tamaño/país siguen disponibles.
        """
        json_llm = (
            '{"es_vendor_it": true, "tamano_estimado": "SME", '
            '"tipo_organizacion": "COOPERATIVA_RARA"}'
        )
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("Somos una fábrica de software"),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            assert adapter.tipo_organizacion(empresa) is None
            # El resto de señales de la MISMA llamada sigue intacto.
            assert adapter.clasificar(empresa) == CategoriaEmpresa.AGENCIA_IT

    def test_tipo_normaliza_minusculas(self, empresa: Empresa):
        json_llm = (
            '{"es_vendor_it": false, "tamano_estimado": null, '
            '"tipo_organizacion": "medios"}'
        )
        with (
            patch(
                "requests.get", return_value=_mock_html_response("Portal de noticias")
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            assert adapter.tipo_organizacion(empresa) == TipoOrganizacion.MEDIOS

    def test_tipo_comparte_cache_con_clasificar_y_estimar_tamano(
        self, empresa: Empresa
    ):
        """(d) Una sola llamada LLM alimenta clasificar + estimar_tamano + tipo_organizacion."""
        json_llm = (
            '{"es_vendor_it": true, "tamano_estimado": "SME", '
            '"tipo_organizacion": "EMPRESA_PRIVADA"}'
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
            adapter.estimar_tamano(empresa)
            adapter.tipo_organizacion(empresa)

        mock_get.assert_called_once()
        mock_groq.chat.completions.create.assert_called_once()

    def test_tipo_sin_api_key_retorna_none(self, empresa: Empresa):
        adapter = PropuestaValorAdapter(api_key=None)
        assert adapter.tipo_organizacion(empresa) is None


class TestPropuestaValorAdapterSnippetHomepage:
    """
    snippet_homepage() expone el texto leído/enviado al LLM para el Paquete
    de Revisión Manual — sin duplicar lecturas de red.
    """

    def test_snippet_disponible_tras_clasificar(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME"}'
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("Somos una fábrica de software"),
            ) as mock_get,
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            adapter.clasificar(empresa)
            snippet = adapter.snippet_homepage(empresa)

        assert snippet is not None
        assert "fábrica de software" in snippet
        mock_get.assert_called_once()  # snippet_homepage no repite la lectura

    def test_snippet_forzado_sin_analisis_previo(self, empresa: Empresa):
        """Si se llama sin haber invocado clasificar()/estimar_tamano() antes."""
        with patch(
            "requests.get",
            return_value=_mock_html_response("Texto público de la empresa"),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            snippet = adapter.snippet_homepage(empresa)

        assert snippet is not None
        assert "Texto público" in snippet

    def test_snippet_none_cuando_no_hay_texto_disponible(self, empresa: Empresa):
        mock_vacio = MagicMock()
        mock_vacio.status_code = 200
        mock_vacio.text = "<html><body><script>solo_js();</script></body></html>"
        mock_vacio.raise_for_status.return_value = None

        with (
            patch("requests.get", return_value=mock_vacio),
            patch(
                "src.adapters.triggers.propuesta_valor_adapter._renderizar_con_playwright",
                return_value=None,
            ),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            snippet = adapter.snippet_homepage(empresa)

        assert snippet is None


class TestPropuestaValorAdapterFailoverMultiplesClaves:
    """
    Rotación reactiva con cooldown (Hallazgo de corrida real, 2026-07): un
    batch grande agota el límite de Tokens Por Día de una sola clave gratuita
    de Groq. Con un GroqKeyPool de varias claves inyectado, un 429 en la
    clave activa debe hacer failover automático a la siguiente en la MISMA
    llamada — sin que el llamador (orquestador del sandbox) note el fallo.
    """

    def test_rate_limit_en_primera_clave_hace_failover_y_completa_la_llamada(
        self, empresa: Empresa
    ):
        json_llm = '{"es_vendor_it": true, "tamano_estimado": "SME"}'

        with patch("groq.Groq") as mock_groq_cls:
            cliente_1 = MagicMock()
            cliente_1.chat.completions.create.side_effect = _rate_limit_error(
                "Please try again in 5s"
            )
            cliente_2 = MagicMock()
            cliente_2.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content=json_llm))]
            )
            mock_groq_cls.side_effect = [cliente_1, cliente_2]

            pool = GroqKeyPool(api_keys=["key-1", "key-2"])

            with patch(
                "requests.get",
                return_value=_mock_html_response("Somos una fábrica de software"),
            ):
                adapter = PropuestaValorAdapter(key_pool=pool)
                resultado = adapter.clasificar(empresa)

        assert resultado == CategoriaEmpresa.AGENCIA_IT
        cliente_1.chat.completions.create.assert_called_once()
        cliente_2.chat.completions.create.assert_called_once()

    def test_todas_las_claves_agotadas_retorna_none_sin_lanzar(self, empresa: Empresa):
        with patch("groq.Groq") as mock_groq_cls:
            cliente_1 = MagicMock()
            cliente_1.chat.completions.create.side_effect = _rate_limit_error(
                "Please try again in 5s"
            )
            cliente_2 = MagicMock()
            cliente_2.chat.completions.create.side_effect = _rate_limit_error(
                "Please try again in 5s"
            )
            mock_groq_cls.side_effect = [cliente_1, cliente_2]

            pool = GroqKeyPool(api_keys=["key-1", "key-2"])

            with patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ):
                adapter = PropuestaValorAdapter(key_pool=pool)
                resultado = adapter.clasificar(empresa)

        assert resultado is None

    def test_pool_ya_agotado_antes_de_llamar_retorna_none_sin_llamar_llm(
        self, empresa: Empresa
    ):
        """Si TODAS las claves ya están en enfriamiento, ni se intenta la llamada."""
        with patch("groq.Groq") as mock_groq_cls:
            cliente_1 = MagicMock()
            mock_groq_cls.return_value = cliente_1
            pool = GroqKeyPool(api_keys=["key-1"])
            pool.registrar_rate_limit(_rate_limit_error("Please try again in 999s"))

            with patch("requests.get") as mock_get:
                adapter = PropuestaValorAdapter(key_pool=pool)
                resultado = adapter.clasificar(empresa)

        assert resultado is None
        mock_get.assert_not_called()
        cliente_1.chat.completions.create.assert_not_called()

    def test_api_key_explicita_tiene_prioridad_sobre_key_pool(self, empresa: Empresa):
        """Compatibilidad hacia atrás: api_key sigue funcionando (pool de 1 clave)."""
        json_llm = '{"es_vendor_it": false, "tamano_estimado": null}'
        with (
            patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="clave-explicita")
            resultado = adapter.clasificar(empresa)

        assert resultado is None  # es_vendor_it=false -> comportamiento esperado
        assert adapter._pool.num_claves == 1

    def test_sin_api_key_ni_pool_descubre_del_entorno(
        self, empresa: Empresa, monkeypatch
    ):
        """Sin argumentos, el adaptador construye un GroqKeyPool() por defecto."""
        for i in range(1, 21):
            monkeypatch.delenv(f"GROQ_API_KEY_{i}", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with patch("groq.Groq"):
            adapter = PropuestaValorAdapter()

        assert adapter._pool.tiene_claves is False

    def test_segundo_429_en_clave_de_failover_tambien_retorna_none(
        self, empresa: Empresa
    ):
        """Con 2 claves, si la segunda TAMBIÉN da 429, no hay más reintentos."""
        with patch("groq.Groq") as mock_groq_cls:
            cliente_1 = MagicMock()
            cliente_1.chat.completions.create.side_effect = _rate_limit_error(
                "Please try again in 5s"
            )
            cliente_2 = MagicMock()
            cliente_2.chat.completions.create.side_effect = _rate_limit_error(
                "Please try again in 8s"
            )
            mock_groq_cls.side_effect = [cliente_1, cliente_2]

            pool = GroqKeyPool(api_keys=["key-1", "key-2"])

            with patch(
                "requests.get", return_value=_mock_html_response("Texto de la empresa")
            ):
                adapter = PropuestaValorAdapter(key_pool=pool)
                resultado = adapter.clasificar(empresa)

        assert resultado is None
        cliente_1.chat.completions.create.assert_called_once()
        cliente_2.chat.completions.create.assert_called_once()
        # Ambas claves deben haber quedado marcadas en enfriamiento
        assert pool.cliente_activo() is None


class TestGroqKeyPoolDescubrimientoEntorno:
    """
    Descubrimiento de claves GROQ_API_KEY_N del entorno.

    Fix 25-jul-2026: el escaneo debe TOLERAR HUECOS en la numeración. Antes se
    detenía en el primer índice ausente, así que añadir GROQ_API_KEY_4 sin tener
    la _3 dejaba la clave nueva sin usarse silenciosamente (bug real: el fundador
    agregó una 4ª clave para las pruebas y no se habría recolectado).
    """

    def _limpiar_claves(self, monkeypatch):
        for i in range(1, 21):
            monkeypatch.delenv(f"GROQ_API_KEY_{i}", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

    def test_recolecta_todas_las_claves_tolerando_huecos(self, monkeypatch):
        self._limpiar_claves(monkeypatch)
        # Hueco intencional en la _3 (simula GROQ_API_KEY_4 añadida sin la _3).
        monkeypatch.setenv("GROQ_API_KEY_1", "k1")
        monkeypatch.setenv("GROQ_API_KEY_2", "k2")
        monkeypatch.setenv("GROQ_API_KEY_4", "k4")

        pool = GroqKeyPool()

        assert pool.num_claves == 3
        assert pool._api_keys == ["k1", "k2", "k4"]

    def test_solo_clave_en_indice_alto_se_recolecta(self, monkeypatch):
        """Aunque falten _1.._4, una clave en _5 debe encontrarse."""
        self._limpiar_claves(monkeypatch)
        monkeypatch.setenv("GROQ_API_KEY_5", "k5")

        pool = GroqKeyPool()

        assert pool.num_claves == 1
        assert pool._api_keys == ["k5"]

    def test_fallback_a_groq_api_key_singular_si_no_hay_numeradas(self, monkeypatch):
        self._limpiar_claves(monkeypatch)
        monkeypatch.setenv("GROQ_API_KEY", "unica")

        pool = GroqKeyPool()

        assert pool._api_keys == ["unica"]


class TestDominioResuelveDNS:
    """
    Pre-check DNS (fix 25-jul-2026): antes de gastar HTTP + Playwright (~15s)
    sobre un dominio muerto, se resuelve el hostname por DNS con la stdlib
    (socket, costo cero). Casos reales que fallaban: bolsamercantil.com.co,
    comfandi.com.co (ERR_NAME_NOT_RESOLVED).
    """

    def test_dominio_que_resuelve_devuelve_true(self):
        import src.adapters.triggers.propuesta_valor_adapter as mod

        with patch.object(mod.socket, "getaddrinfo", return_value=[("info",)]):
            assert mod._dominio_resuelve("ejemplo.com") is True

    def test_dominio_con_esquema_extrae_hostname(self):
        import src.adapters.triggers.propuesta_valor_adapter as mod

        with patch.object(mod.socket, "getaddrinfo", return_value=[("info",)]) as m:
            assert mod._dominio_resuelve("https://www.ejemplo.com/ruta") is True
        assert m.call_args.args[0] == "www.ejemplo.com"

    def test_dominio_que_no_resuelve_devuelve_false(self):
        import socket

        import src.adapters.triggers.propuesta_valor_adapter as mod

        with patch.object(mod.socket, "getaddrinfo", side_effect=socket.gaierror):
            assert mod._dominio_resuelve("bolsamercantil.com.co") is False

    def test_dominio_vacio_o_basura_devuelve_false(self):
        import src.adapters.triggers.propuesta_valor_adapter as mod

        assert mod._dominio_resuelve("") is False
        assert mod._dominio_resuelve("   ") is False

    def test_homepage_no_lee_web_si_dominio_no_resuelve(self, empresa: Empresa):
        """Si el dominio no resuelve, NO se debe intentar requests.get ni Playwright."""
        import socket

        import src.adapters.triggers.propuesta_valor_adapter as mod

        adapter = PropuestaValorAdapter(api_key="test-key")
        with (
            patch.object(mod.socket, "getaddrinfo", side_effect=socket.gaierror),
            patch("requests.get") as mock_get,
            patch.object(mod, "_renderizar_con_playwright") as mock_render,
        ):
            texto = adapter._leer_texto_homepage("dominio-muerto.com.co")

        assert texto is None
        mock_get.assert_not_called()
        mock_render.assert_not_called()


class TestPropuestaValorAdapterEsMultinacional:
    """Fit de comprador (B, 26-jul-2026): 5º campo del LLM es_multinacional."""

    def test_es_multinacional_true(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": false, "es_multinacional": true}'
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response(
                    "Presencia global en 30 países, parte del grupo internacional X"
                ),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            assert adapter.es_multinacional(empresa) is True

    def test_es_multinacional_false(self, empresa: Empresa):
        json_llm = '{"es_vendor_it": false, "es_multinacional": false}'
        with (
            patch(
                "requests.get",
                return_value=_mock_html_response("PYME local en Bogotá, un solo país"),
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            assert adapter.es_multinacional(empresa) is False

    def test_es_multinacional_none_cuando_ausente(self, empresa: Empresa):
        """Si el LLM omite el campo, es None (sin señal) — no invalida el resto."""
        json_llm = '{"es_vendor_it": false}'
        with (
            patch(
                "requests.get", return_value=_mock_html_response("Texto ambiguo")
            ),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(api_key="test-key")
            assert adapter.es_multinacional(empresa) is None
            # Las otras señales de la misma llamada siguen intactas.
            assert adapter.es_vendor_it(empresa) is False


class TestPropuestaValorAdapterRespaldoWeb:
    """
    Respaldo de contexto (Tavily, 26-jul-2026): cuando la homepage no se puede
    leer (DNS muerto), se usa el buscador_respaldo inyectado para clasificar en
    vez de caer a None (fail-closed por falla técnica).
    """

    def test_usa_respaldo_cuando_homepage_no_resuelve(self, empresa: Empresa):
        import socket

        import src.adapters.triggers.propuesta_valor_adapter as mod

        json_llm = '{"es_vendor_it": true, "es_multinacional": false}'
        llamado: list = []

        def respaldo(emp: Empresa) -> str:
            llamado.append(emp)
            return "Acme es una fábrica de software colombiana; vende desarrollo a la medida."

        with (
            patch.object(mod.socket, "getaddrinfo", side_effect=socket.gaierror),
            patch("groq.Groq", return_value=_mock_groq_client(json_llm)),
        ):
            adapter = PropuestaValorAdapter(
                api_key="test-key", buscador_respaldo=respaldo
            )
            resultado = adapter.es_vendor_it(empresa)

        assert llamado, "el buscador_respaldo debió invocarse cuando el homepage falló"
        assert resultado is True  # clasificó con el texto del respaldo web

    def test_sin_respaldo_homepage_muerto_sigue_fail_closed(self, empresa: Empresa):
        """Sin buscador_respaldo, un homepage muerto sigue dando None (fail-closed)."""
        import socket

        import src.adapters.triggers.propuesta_valor_adapter as mod

        with patch.object(mod.socket, "getaddrinfo", side_effect=socket.gaierror):
            adapter = PropuestaValorAdapter(api_key="test-key")
            assert adapter.es_vendor_it(empresa) is None
