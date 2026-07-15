"""
Tests unitarios de los adaptadores del Motor 2 — sin llamadas reales a APIs.

Mockea requests.get/post para TheirStack y feedparser.parse para Google Alerts.
Verifica que ambos producen objetos Trigger válidos de Pydantic v2.
"""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    TamanoEmpresa,
    Trigger,
)


# ---------------------------------------------------------------------------
# Fixture de empresa de prueba
# ---------------------------------------------------------------------------
@pytest.fixture
def empresa() -> Empresa:
    return Empresa(
        nombre="Acme SaaS",
        dominio="acme.com",
        tamano=TamanoEmpresa.MID_MARKET,
        vertical="E-commerce",
        ciudad="Bogotá",
    )


# ---------------------------------------------------------------------------
# Tests de TheirStackAdapter
# ---------------------------------------------------------------------------
class TestTheirStackAdapter:
    # -- Helpers ──────────────────────────────────────────────────────────
    def _mock_response(self, vacantes: list[dict], status_code: int = 200) -> MagicMock:
        mock = MagicMock()
        mock.status_code = status_code
        mock.json.return_value = {"data": vacantes, "total": len(vacantes)}
        if status_code >= 400:
            import requests

            mock.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=mock
            )
        else:
            mock.raise_for_status.return_value = None
        return mock

    def _vacante(
        self, titulo: str, fecha: str = "2026-07-01", techs: list[str] | None = None
    ) -> dict:
        return {
            "id": f"job-{titulo[:5]}",
            "title": titulo,
            "company_name": "Acme SaaS",
            "date_posted": fecha,
            "technologies": [{"name": t} for t in (techs or [])],
        }

    # -- Tests ────────────────────────────────────────────────────────────
    def test_tres_vacantes_generan_trigger_alta_confianza(self, empresa: Empresa):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [
            self._vacante("Senior Python Dev", techs=["Python", "AWS"]),
            self._vacante("AWS Architect", techs=["AWS"]),
            self._vacante("Django Backend Engineer", techs=["Django"]),
        ]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(
                api_key="test-key",
                tecnologias_objetivo=["Python", "AWS"],
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert isinstance(t, Trigger)
        assert t.origen == OrigenTrigger.THEIRSTACK
        assert t.nivel_confianza == NivelConfianza.ALTA
        assert t.empresa_id == empresa.id
        assert "3" in t.descripcion or "vacante" in t.descripcion.lower()

    def test_dos_vacantes_generan_trigger_media_confianza(self, empresa: Empresa):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [
            self._vacante("Backend Engineer"),
            self._vacante("Python Developer"),
        ]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.MEDIA

    def test_cero_vacantes_retorna_lista_vacia(self, empresa: Empresa):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        respuesta_mock = self._mock_response([])

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_http_error_retorna_lista_vacia_no_lanza(self, empresa: Empresa):
        """El contrato del Puerto exige nunca propagar excepciones al Core."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        respuesta_mock = self._mock_response([], status_code=403)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_timeout_retorna_lista_vacia_no_lanza(self, empresa: Empresa):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
        import requests

        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_sin_api_key_retorna_lista_vacia(self, empresa: Empresa):
        """Sin API key no debe intentar llamar a la API."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        with patch.dict("os.environ", {}, clear=False):
            import os

            original = os.environ.pop("THEIRSTACK_API_KEY", None)
            try:
                adapter = TheirStackAdapter(api_key=None)
                triggers = adapter.obtener_triggers(empresa)
                assert triggers == []
            finally:
                if original is not None:
                    os.environ["THEIRSTACK_API_KEY"] = original

    def test_trigger_tiene_fecha_evento(self, empresa: Empresa):
        """La fecha_evento es crítica para TriggerAggregationPolicy (45 días)."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [
            self._vacante("Senior Dev", fecha="2026-07-05"),
            self._vacante("Backend Dev", fecha="2026-07-01"),
            self._vacante("Cloud Architect", fecha="2026-06-15"),
        ]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert triggers[0].fecha_evento is not None
        assert isinstance(triggers[0].fecha_evento, datetime)

    def test_descripcion_marca_tope_de_paginacion(self, empresa: Empresa):
        """Cuando las vacantes alcanzan el limit (3 por defecto), la descripción debe indicar '+3'."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        # 3 vacantes = el máximo por defecto (max_resultados_scoring=3)
        vacantes = [self._vacante(f"Dev {i}") for i in range(3)]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert "+3" in triggers[0].descripcion

    def test_descripcion_sin_tope_no_lleva_mas(self, empresa: Empresa):
        """Con menos vacantes que el limit (3), la descripción NO lleva el prefijo '+'."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [self._vacante(f"Dev {i}") for i in range(2)]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert "+2" not in triggers[0].descripcion
        assert "2 vacante" in triggers[0].descripcion

    def test_payload_incluye_tecnologias_objetivo(self, empresa: Empresa):
        """Verifica que las tecnologías del ICP se pasan a la query de TheirStack."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        respuesta_mock = self._mock_response([self._vacante("Dev")])

        with patch("requests.post", return_value=respuesta_mock) as mock_post:
            adapter = TheirStackAdapter(
                api_key="test-key",
                tecnologias_objetivo=["Python", "FastAPI"],
            )
            adapter.obtener_triggers(empresa)

        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs["json"]
        # Nombres de campo correctos según la API de TheirStack
        assert "python" in payload.get("company_technology_slug_or", [])
        assert "fastapi" in payload.get("company_technology_slug_or", [])
        # Scoring usa company_domain_or (lista), no company_domain (string)
        assert "acme.com" in payload.get("company_domain_or", [])


# ---------------------------------------------------------------------------
# Tests de GoogleAlertsRSSAdapter
# ---------------------------------------------------------------------------
class _EntradaRSSMock:
    """Simula un objeto entry de feedparser."""

    def __init__(
        self,
        title: str,
        summary: str = "",
        link: str = "https://example.com",
        published_parsed=None,
    ):
        self.title = title
        self.summary = summary
        self.link = link
        self.published_parsed = published_parsed or time.gmtime()


def _feed_mock(entries: list[_EntradaRSSMock], bozo: bool = False) -> MagicMock:
    mock = MagicMock()
    mock.entries = entries
    mock.bozo = bozo
    mock.get = lambda k, default=None: {"entries": entries, "bozo": bozo}.get(
        k, default
    )
    return mock


class TestGoogleAlertsRSSAdapter:
    def test_entrada_c_level_genera_trigger_alta(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS nombra nuevo CTO para liderar transformación digital",
                summary="Juan Torres se une como Chief Technology Officer.",
            )
        ]

        with patch("feedparser.parse", return_value=_feed_mock(entradas)):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/123"]
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert isinstance(t, Trigger)
        assert t.origen == OrigenTrigger.GOOGLE_ALERTS
        assert t.nivel_confianza == NivelConfianza.ALTA
        assert t.empresa_id == empresa.id

    def test_entrada_ronda_inversion_genera_trigger_media(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS levanta ronda Serie A de USD 5 millones",
                summary="La startup colombiana cierra su primera ronda de inversión.",
            )
        ]

        with patch("feedparser.parse", return_value=_feed_mock(entradas)):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/456"]
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.MEDIA

    def test_mencion_generica_genera_trigger_baja(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS participa en foro de tecnología en Bogotá",
                summary="La empresa estuvo presente en el evento.",
            )
        ]

        with patch("feedparser.parse", return_value=_feed_mock(entradas)):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/789"]
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.BAJA

    def test_entrada_sin_mencion_empresa_filtrada(self, empresa: Empresa):
        """Entradas que no mencionan a la empresa no deben generar Trigger."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Empresa XYZ levanta ronda de inversión millonaria",
                summary="Una empresa completamente diferente.",
            )
        ]

        with patch("feedparser.parse", return_value=_feed_mock(entradas)):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/000"]
            )
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_feed_vacio_retorna_lista_vacia(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        with patch("feedparser.parse", return_value=_feed_mock([])):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/empty"]
            )
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_sin_urls_retorna_lista_vacia(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        adapter = GoogleAlertsRSSAdapter(rss_urls=[])
        triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_error_feedparser_no_propaga_al_core(self, empresa: Empresa):
        """Contrato: nunca levantar excepción hacia el Core."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        with patch("feedparser.parse", side_effect=Exception("error de red simulado")):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/fail"]
            )
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_triggers_ordenados_alta_primero(self, empresa: Empresa):
        """Los triggers ALTA deben aparecer antes que BAJA."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS participa en evento tecnológico anual",
                summary="Mención genérica en medios.",
            ),
            _EntradaRSSMock(
                title="Acme SaaS nombra nuevo Chief Technology Officer",
                summary="Ana Gómez asumirá el cargo de CTO a partir de agosto.",
            ),
        ]

        with patch("feedparser.parse", return_value=_feed_mock(entradas)):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/mixed"],
                max_triggers_por_empresa=3,
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 2
        # ALTA (CTO) debe aparecer primero, BAJA (mención genérica) después
        assert triggers[0].nivel_confianza == NivelConfianza.ALTA
        assert triggers[1].nivel_confianza == NivelConfianza.BAJA

    def test_keyword_extra_filtra_por_dolor_icp(self, empresa: Empresa):
        """Keywords del ManifiestoICP deben capturar entradas sin nombre de empresa."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Crisis de talento backend en Colombia 2026",
                summary="Las empresas luchan por contratar arquitectos de software.",
            )
        ]

        with patch("feedparser.parse", return_value=_feed_mock(entradas)):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/keyword"],
                palabras_clave_extra=["talento backend", "arquitectos"],
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1

    def test_trigger_tiene_fecha_evento(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS nuevo CTO",
                summary="",
                published_parsed=time.gmtime(1720000000),  # Unix timestamp
            )
        ]

        with patch("feedparser.parse", return_value=_feed_mock(entradas)):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/date"]
            )
            triggers = adapter.obtener_triggers(empresa)

        assert triggers[0].fecha_evento is not None
        assert isinstance(triggers[0].fecha_evento, datetime)

    def test_max_triggers_respetado(self, empresa: Empresa):
        """No debe generar más triggers que max_triggers_por_empresa."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(title=f"Acme SaaS noticia {i}", summary="")
            for i in range(10)
        ]

        with patch("feedparser.parse", return_value=_feed_mock(entradas)):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/many"],
                max_triggers_por_empresa=2,
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) <= 2
