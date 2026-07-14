"""
Tests unitarios del WappalyzerHeadlessAdapter.
Mockea requests.get — sin llamadas reales a internet.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    TamanoEmpresa,
    Trigger,
)


@pytest.fixture
def empresa() -> Empresa:
    return Empresa(
        nombre="Acme SaaS",
        dominio="acme.com",
        tamano=TamanoEmpresa.MID_MARKET,
        vertical="E-commerce",
    )


def _mock_response(
    body: str = "",
    headers: dict | None = None,
    status_code: int = 200,
) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = body
    mock.headers = headers or {}
    if status_code >= 400:
        import requests
        mock.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock)
    else:
        mock.raise_for_status.return_value = None
    return mock


class TestWappalyzerHeadlessAdapter:

    def test_detecta_php_en_header_y_genera_trigger_media(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        resp = _mock_response(headers={"X-Powered-By": "PHP/8.1", "Server": "Apache"})
        with patch("requests.get", return_value=resp):
            adapter = WappalyzerHeadlessAdapter(tecnologias_objetivo=["PHP", "Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert t.origen == OrigenTrigger.WAPPALYZER
        assert t.nivel_confianza == NivelConfianza.MEDIA
        assert t.empresa_id == empresa.id
        assert "php" in t.descripcion.lower()

    def test_detecta_wordpress_en_html_y_genera_trigger_baja_sin_match(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        html = "<html><head><meta name='generator' content='WordPress 6.0'></head></html>"
        resp = _mock_response(body=html)
        with patch("requests.get", return_value=resp):
            # ICP pide Python/AWS, WordPress no hace match → BAJA → omitido por defecto
            adapter = WappalyzerHeadlessAdapter(
                tecnologias_objetivo=["Python", "AWS"],
                incluir_baja_confianza=False,
            )
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_incluir_baja_confianza_activa_el_trigger(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        html = "<html><head><meta name='generator' content='WordPress 6.0'></head></html>"
        resp = _mock_response(body=html)
        with patch("requests.get", return_value=resp):
            adapter = WappalyzerHeadlessAdapter(
                tecnologias_objetivo=["Python"],
                incluir_baja_confianza=True,
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.BAJA

    def test_detecta_eol_y_genera_trigger_alta(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        # PHP 5 es EOL → ALTA
        resp = _mock_response(
            headers={"X-Powered-By": "PHP/5.6.40"},
            body="<html></html>",
        )
        with patch("requests.get", return_value=resp):
            adapter = WappalyzerHeadlessAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.ALTA
        assert "EOL" in triggers[0].descripcion

    def test_sin_tecnologias_detectadas_retorna_vacio(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        resp = _mock_response(body="<html><body>Hello</body></html>")
        with patch("requests.get", return_value=resp):
            adapter = WappalyzerHeadlessAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_timeout_retorna_lista_vacia_no_lanza(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter
        import requests

        with patch("requests.get", side_effect=requests.exceptions.Timeout):
            adapter = WappalyzerHeadlessAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_ssl_error_retorna_lista_vacia_no_lanza(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter
        import requests

        with patch("requests.get", side_effect=requests.exceptions.SSLError):
            adapter = WappalyzerHeadlessAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_connection_error_retorna_lista_vacia_no_lanza(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter
        import requests

        with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
            adapter = WappalyzerHeadlessAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_dominio_vacio_retorna_lista_vacia(self):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        emp_sin_dominio = Empresa(
            nombre="Sin Dominio",
            dominio=" ",
            tamano=TamanoEmpresa.SME,
            vertical="Tech",
        )
        adapter = WappalyzerHeadlessAdapter(tecnologias_objetivo=["Python"])
        triggers = adapter.obtener_triggers(emp_sin_dominio)

        assert triggers == []

    def test_detecta_react_en_scripts_html(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        html = """<html><head></head><body>
        <script src="/static/js/react.production.min.js"></script>
        </body></html>"""
        resp = _mock_response(body=html)
        with patch("requests.get", return_value=resp):
            adapter = WappalyzerHeadlessAdapter(
                tecnologias_objetivo=["React", "Python"],
                incluir_baja_confianza=True,
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) >= 1
        assert any("react" in t.descripcion.lower() for t in triggers)

    def test_detecta_next_js_en_links(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        html = """<html><head>
        <link rel="preload" href="/_next/static/chunks/main.js"/>
        </head></html>"""
        resp = _mock_response(body=html)
        with patch("requests.get", return_value=resp):
            adapter = WappalyzerHeadlessAdapter(
                tecnologias_objetivo=["Next.js"],
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.MEDIA

    def test_trigger_es_instancia_valida_pydantic(self, empresa: Empresa):
        from src.adapters.triggers.wappalyzer_adapter import WappalyzerHeadlessAdapter

        resp = _mock_response(headers={"X-Powered-By": "PHP/8.1"})
        with patch("requests.get", return_value=resp):
            adapter = WappalyzerHeadlessAdapter(tecnologias_objetivo=["PHP"])
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert isinstance(t, Trigger)
        assert t.empresa_id == empresa.id
        assert t.origen == OrigenTrigger.WAPPALYZER
