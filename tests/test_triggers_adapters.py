"""
Tests unitarios de los adaptadores del Motor 2 — sin llamadas reales a APIs.

Mockea requests.get/post para TheirStack y feedparser.parse + groq.Groq para
Google Alerts (verificación semántica). Ningún test consume red ni créditos
reales de Groq.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

import groq as groq_sdk

from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    TamanoEmpresa,
    TierUrgencia,
    TipoTrigger,
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
        """
        CONTRATO NUEVO (dos ejes de tiempo, Signal-Based Selling v5.0): una
        vacante aún abierta es un estado CONTINUO, así que fecha_evento = now
        (frescura de observación), NO date_posted. Antes se asumía que
        fecha_evento era el date_posted de la primera vacante; ahora el
        date_posted alimenta el AGING (→ tier), no la fecha_evento (→ decay).
        """
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        fecha_10d = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
            "%Y-%m-%d"
        )
        vacantes = [
            self._vacante("Senior Dev", fecha=fecha_10d),
            self._vacante("Backend Dev", fecha=fecha_10d),
        ]
        respuesta_mock = self._mock_response(vacantes)

        antes = datetime.now(timezone.utc)
        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)
        despues = datetime.now(timezone.utc)

        fe = triggers[0].fecha_evento
        assert fe is not None
        assert isinstance(fe, datetime)
        # fecha_evento debe ser "ahora" (observación), no el date_posted (hace 10d)
        assert antes <= fe <= despues

    def test_aging_alto_genera_tier0_efecto_con_fecha_evento_ahora(
        self, empresa: Empresa
    ):
        """
        Vacante abierta con date_posted de hace 60 días → aging >= 45 →
        TIER_0/EFECTO, con fecha_evento ≈ now (estado continuo) para que el
        decay de EFECTO (45d) de ScoreTriggerPolicy no la elimine.
        """
        from src.core.domain.models import TierUrgencia, TipoTrigger
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        fecha_60d = (datetime.now(timezone.utc) - timedelta(days=60)).strftime(
            "%Y-%m-%d"
        )
        vacantes = [
            self._vacante("Senior Python Dev", fecha=fecha_60d),
            self._vacante("AWS Architect", fecha=fecha_60d),
            self._vacante("Django Engineer", fecha=fecha_60d),
        ]
        respuesta_mock = self._mock_response(vacantes)

        antes = datetime.now(timezone.utc)
        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)
        despues = datetime.now(timezone.utc)

        t = triggers[0]
        assert t.tier_urgencia == TierUrgencia.TIER_0
        assert t.tipo_trigger == TipoTrigger.EFECTO
        assert antes <= t.fecha_evento <= despues
        # El aging real (~60d) debe aparecer en la descripción para trazabilidad
        assert "días abierta" in t.descripcion

    def test_aging_bajo_genera_tier2(self, empresa: Empresa):
        """Vacante abierta hace 10 días → aging < 45 → TIER_2 (demanda fresca)."""
        from src.core.domain.models import TierUrgencia, TipoTrigger
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        fecha_10d = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
            "%Y-%m-%d"
        )
        vacantes = [
            self._vacante("Backend Dev", fecha=fecha_10d),
            self._vacante("Python Dev", fecha=fecha_10d),
        ]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        t = triggers[0]
        assert t.tier_urgencia == TierUrgencia.TIER_2
        assert t.tipo_trigger == TipoTrigger.EFECTO

    def test_aging_usa_vacante_mas_antigua_devuelta(self, empresa: Empresa):
        """
        El aging se estima con la vacante MÁS ANTIGUA devuelta (cota inferior).
        Con una vacante de hace 70d y otras recientes, el aging es 70 → TIER_0.
        """
        from src.core.domain.models import TierUrgencia
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        fecha_5d = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
        fecha_70d = (datetime.now(timezone.utc) - timedelta(days=70)).strftime(
            "%Y-%m-%d"
        )
        vacantes = [
            self._vacante("Reciente 1", fecha=fecha_5d),
            self._vacante("Reciente 2", fecha=fecha_5d),
            self._vacante("Antigua", fecha=fecha_70d),
        ]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert triggers[0].tier_urgencia == TierUrgencia.TIER_0

    def test_payload_scoring_sube_limit_para_aging(self, empresa: Empresa):
        """
        El payload de scoring debe pedir más vacantes (25) que las que reporta,
        para estimar el aging sin costo extra (TheirStack cobra por consulta).
        """
        from src.adapters.triggers.theirstack_adapter import (
            TheirStackAdapter,
            _LIMITE_VACANTES_AGING,
        )

        respuesta_mock = self._mock_response([self._vacante("Dev")])
        with patch("requests.post", return_value=respuesta_mock) as mock_post:
            adapter = TheirStackAdapter(api_key="test-key")
            adapter.obtener_triggers(empresa)

        payload = mock_post.call_args.kwargs["json"]
        assert payload["limit"] == _LIMITE_VACANTES_AGING
        assert _LIMITE_VACANTES_AGING >= 25
        # Se conserva el orden por date_posted desc
        assert payload["order_by"] == [{"desc": True, "field": "date_posted"}]

    def test_aging_no_estimable_sin_fecha_es_conservador_tier2(self, empresa: Empresa):
        """Sin date_posted parseable, aging=0 → TIER_2 (conservador, fail-closed)."""
        from src.core.domain.models import TierUrgencia
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [
            {"id": "j1", "title": "Dev", "date_posted": None, "technologies": []},
            {"id": "j2", "title": "Dev2", "date_posted": None, "technologies": []},
        ]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(empresa)

        assert triggers[0].tier_urgencia == TierUrgencia.TIER_2
        assert "no estimable" in triggers[0].descripcion

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

    # -- Tests de estimar_tamano (PuertoEstimadorTamano) ───────────────────
    def _vacante_con_company_object(
        self, titulo: str, employee_count: int | None
    ) -> dict:
        v = self._vacante(titulo)
        v["company_object"] = {"employee_count": employee_count} if employee_count is not None else {}
        return v

    def test_estimar_tamano_retorna_estimacion_con_origen_theirstack(
        self, empresa: Empresa
    ):
        from src.core.domain.models import EstimacionTamano, OrigenTrigger, TamanoEmpresa
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [self._vacante_con_company_object("Backend Dev", employee_count=120)]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            estimacion = adapter.estimar_tamano(empresa)

        assert isinstance(estimacion, EstimacionTamano)
        assert estimacion.origen == OrigenTrigger.THEIRSTACK
        assert estimacion.tamano_estimado == TamanoEmpresa.SME

    def test_estimar_tamano_enterprise_con_employee_count_alto(self, empresa: Empresa):
        from src.core.domain.models import TamanoEmpresa
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [self._vacante_con_company_object("VP Eng", employee_count=5000)]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion.tamano_estimado == TamanoEmpresa.ENTERPRISE

    def test_estimar_tamano_sin_employee_count_retorna_none(self, empresa: Empresa):
        """Sin dato real de headcount, el waterfall debe recibir silencio, no un relleno."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [self._vacante_con_company_object("Dev", employee_count=None)]
        respuesta_mock = self._mock_response(vacantes)

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is None

    def test_estimar_tamano_sin_vacantes_retorna_none(self, empresa: Empresa):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        respuesta_mock = self._mock_response([])

        with patch("requests.post", return_value=respuesta_mock):
            adapter = TheirStackAdapter(api_key="test-key")
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is None

    def test_estimar_tamano_sin_api_key_retorna_none_sin_llamar_red(
        self, empresa: Empresa
    ):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        with patch("requests.post") as mock_post:
            adapter = TheirStackAdapter(api_key=None)
            adapter._api_key = None
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is None
        mock_post.assert_not_called()

    def test_estimar_tamano_error_red_no_propaga_retorna_none(self, empresa: Empresa):
        import requests

        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            adapter = TheirStackAdapter(api_key="test-key")
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is None


# ---------------------------------------------------------------------------
# Helpers de mock para Google Alerts (RSS + LLM Groq)
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


def _mock_groq_client(contenido_json: str | None) -> MagicMock:
    """Cliente Groq mockeado que devuelve `contenido_json` como respuesta LLM."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content=contenido_json))]
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


def _rate_limit_error(mensaje: str) -> groq_sdk.RateLimitError:
    return groq_sdk.RateLimitError(mensaje, response=MagicMock(), body=None)


@contextmanager
def _rss(entradas: list[_EntradaRSSMock], bozo: bool = False):
    """
    Contexto que simula la descarga RSS sin red: requests.get falla (para caer
    al fallback de feedparser) y feedparser.parse devuelve el feed mockeado.
    """
    with (
        patch("requests.get", side_effect=requests.exceptions.ConnectionError()),
        patch("feedparser.parse", return_value=_feed_mock(entradas, bozo)),
    ):
        yield


# JSON de verificación semántica (respuesta estructurada del LLM)
_JSON_TODO_FALSE = (
    '{"nuevo_liderazgo_tecnico": {"detectado": false, "cargo": null, '
    '"titular_evidencia": null}, "ronda_inversion_o_capital": {"detectado": '
    'false, "titular_evidencia": null}, "fusion_o_adquisicion": {"detectado": '
    'false, "titular_evidencia": null}}'
)


def _json_liderazgo(cargo: str, titular: str) -> str:
    return (
        f'{{"nuevo_liderazgo_tecnico": {{"detectado": true, "cargo": "{cargo}", '
        f'"titular_evidencia": "{titular}"}}, "ronda_inversion_o_capital": '
        f'{{"detectado": false, "titular_evidencia": null}}, '
        f'"fusion_o_adquisicion": {{"detectado": false, "titular_evidencia": null}}}}'
    )


def _json_ronda(titular: str) -> str:
    return (
        f'{{"nuevo_liderazgo_tecnico": {{"detectado": false, "cargo": null, '
        f'"titular_evidencia": null}}, "ronda_inversion_o_capital": '
        f'{{"detectado": true, "titular_evidencia": "{titular}"}}, '
        f'"fusion_o_adquisicion": {{"detectado": false, "titular_evidencia": null}}}}'
    )


_JSON_TODOS_TRUE = (
    '{"nuevo_liderazgo_tecnico": {"detectado": true, "cargo": "CTO", '
    '"titular_evidencia": "nuevo CTO"}, "ronda_inversion_o_capital": '
    '{"detectado": true, "titular_evidencia": "ronda"}, "fusion_o_adquisicion": '
    '{"detectado": true, "titular_evidencia": "adquisición"}}'
)


# ---------------------------------------------------------------------------
# Tests de GoogleAlertsRSSAdapter (verificación semántica por LLM)
# ---------------------------------------------------------------------------
class TestGoogleAlertsRSSAdapter:
    # -- Casos estructurales (sin necesidad de LLM) ────────────────────────
    def test_sin_urls_retorna_lista_vacia(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        adapter = GoogleAlertsRSSAdapter(rss_urls=[], api_key="test-key")
        assert adapter.obtener_triggers(empresa) == []

    def test_feed_vacio_retorna_lista_vacia(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        with _rss([]):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/empty"], api_key="test-key"
            )
            assert adapter.obtener_triggers(empresa) == []

    def test_entrada_sin_mencion_empresa_filtrada(self, empresa: Empresa):
        """Entradas que no mencionan a la empresa no llegan al LLM ni generan Trigger."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Empresa XYZ levanta ronda de inversión millonaria",
                summary="Una empresa completamente diferente.",
            )
        ]
        with _rss(entradas):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/000"], api_key="test-key"
            )
            assert adapter.obtener_triggers(empresa) == []

    def test_error_feedparser_no_propaga_al_core(self, empresa: Empresa):
        """Contrato: nunca levantar excepción hacia el Core."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        with (
            patch("requests.get", side_effect=requests.exceptions.ConnectionError()),
            patch("feedparser.parse", side_effect=Exception("error de red simulado")),
        ):
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/fail"], api_key="test-key"
            )
            assert adapter.obtener_triggers(empresa) == []

    # -- (a) LLM confirma nuevo CTO → 1 trigger TIER_1/CAUSA ───────────────
    def test_llm_confirma_liderazgo_genera_tier1_causa(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        titular = "Acme SaaS nombra nuevo CTO para liderar transformación digital"
        entradas = [
            _EntradaRSSMock(
                title=titular,
                summary="Juan Torres se une como Chief Technology Officer de la empresa.",
            )
        ]
        with _rss(entradas):
            with patch(
                "groq.Groq",
                return_value=_mock_groq_client(_json_liderazgo("CTO", titular)),
            ):
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/1"], api_key="test-key"
                )
                triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert t.origen == OrigenTrigger.GOOGLE_ALERTS
        assert t.tier_urgencia == TierUrgencia.TIER_1
        assert t.tipo_trigger == TipoTrigger.CAUSA
        assert t.nivel_confianza == NivelConfianza.ALTA
        assert t.empresa_id == empresa.id

    # -- (b) LLM confirma ronda → TIER_0/CAUSA ─────────────────────────────
    def test_llm_confirma_ronda_genera_tier0_causa(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        titular = "Acme SaaS levanta ronda Serie A de USD 5 millones"
        entradas = [
            _EntradaRSSMock(
                title=titular,
                summary="La startup colombiana cierra su primera ronda de inversión.",
            )
        ]
        with _rss(entradas):
            with patch(
                "groq.Groq", return_value=_mock_groq_client(_json_ronda(titular))
            ):
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/2"], api_key="test-key"
                )
                triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert t.tier_urgencia == TierUrgencia.TIER_0
        assert t.tipo_trigger == TipoTrigger.CAUSA
        assert t.nivel_confianza == NivelConfianza.ALTA

    # -- (c) LLM dice todo false pese a titulares con "director" ───────────
    def test_llm_todo_false_no_genera_liderazgo_solo_mencion(self, empresa: Empresa):
        """
        El titular tiene "director/nuevo" (que el substring habría marcado como
        C-Level), pero el LLM verifica que NO es un evento sobre la empresa.
        No debe generar trigger de liderazgo; a lo sumo TIER_3/BAJA de mención.
        """
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS y el nuevo director técnico de la selección",
                summary="La empresa patrocina el fútbol; nombran nuevo director del equipo.",
            )
        ]
        with _rss(entradas):
            with patch("groq.Groq", return_value=_mock_groq_client(_JSON_TODO_FALSE)):
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/3"], api_key="test-key"
                )
                triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert t.tier_urgencia == TierUrgencia.TIER_3
        assert t.nivel_confianza == NivelConfianza.BAJA
        assert t.tipo_trigger == TipoTrigger.EFECTO
        # Nunca infla a TIER_0/1 por substring.
        assert t.tier_urgencia not in (TierUrgencia.TIER_0, TierUrgencia.TIER_1)

    # -- (d) sin claves Groq → degradación TIER_3/BAJA, nunca TIER_0/1 ─────
    def test_sin_claves_groq_degrada_a_mencion_tier3(
        self, empresa: Empresa, monkeypatch
    ):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        for i in range(1, 21):
            monkeypatch.delenv(f"GROQ_API_KEY_{i}", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS nombra nuevo CTO",
                summary="La empresa de software confirma el nombramiento.",
            )
        ]
        with _rss(entradas):
            # Sin api_key ni pool y sin GROQ_* en el entorno → pool vacío.
            adapter = GoogleAlertsRSSAdapter(
                rss_urls=["https://alerts.google.com/rss/4"], api_key=None
            )
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert t.tier_urgencia == TierUrgencia.TIER_3
        assert t.nivel_confianza == NivelConfianza.BAJA
        assert t.tier_urgencia not in (TierUrgencia.TIER_0, TierUrgencia.TIER_1)

    # -- (e) nombre corto ≤8 → cap a TIER_2 ────────────────────────────────
    def test_nombre_corto_capa_evento_a_tier2(self):
        """
        Aunque el LLM confirme una ronda (que sería TIER_0), un nombre de
        empresa corto/genérico (≤8 chars, riesgo de homónimo) nunca supera
        TIER_2. El nivel ALTA se rebaja a MEDIA.
        """
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        empresa_corta = Empresa(
            nombre="Parcero",  # 7 chars
            dominio="parcero.digital",
            tamano=TamanoEmpresa.SME,
            vertical="Agencia digital",
        )
        titular = "Parcero, la agencia digital, levanta ronda de inversión Serie A"
        entradas = [
            _EntradaRSSMock(
                title=titular,
                summary="El CEO de la empresa confirmó la ronda de capital.",
            )
        ]
        with _rss(entradas):
            with patch(
                "groq.Groq", return_value=_mock_groq_client(_json_ronda(titular))
            ):
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/5"], api_key="test-key"
                )
                triggers = adapter.obtener_triggers(empresa_corta)

        assert len(triggers) == 1
        t = triggers[0]
        assert t.tier_urgencia == TierUrgencia.TIER_2  # capado desde TIER_0
        assert t.nivel_confianza == NivelConfianza.MEDIA  # rebajado desde ALTA

    # -- (f) rate limit / JSON inválido → degradación sin lanzar ───────────
    def test_rate_limit_sin_failover_degrada_a_mencion(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS nombra nuevo CTO",
                summary="La empresa de software confirma el nombramiento.",
            )
        ]
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = _rate_limit_error(
            "Please try again in 5s"
        )
        with _rss(entradas):
            with patch("groq.Groq", return_value=cliente):
                # api_key única → pool de 1 clave: el 429 no tiene failover.
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/6"], api_key="test-key"
                )
                triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].tier_urgencia == TierUrgencia.TIER_3
        assert triggers[0].nivel_confianza == NivelConfianza.BAJA

    def test_json_invalido_degrada_a_mencion(self, empresa: Empresa):
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS nombra nuevo CTO",
                summary="La empresa de software confirma el nombramiento.",
            )
        ]
        with _rss(entradas):
            with patch(
                "groq.Groq", return_value=_mock_groq_client("no soy json {roto")
            ):
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/7"], api_key="test-key"
                )
                triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].tier_urgencia == TierUrgencia.TIER_3
        assert triggers[0].nivel_confianza == NivelConfianza.BAJA

    # -- Otros contratos ──────────────────────────────────────────────────
    def test_trigger_verificado_tiene_fecha_evento_de_la_evidencia(
        self, empresa: Empresa
    ):
        """fecha_evento = fecha de la entrada RSS cuyo título coincide con la evidencia."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        titular = "Acme SaaS nombra nuevo CTO"
        entradas = [
            _EntradaRSSMock(
                title=titular,
                summary="La empresa de software confirma el nombramiento del CTO.",
                published_parsed=time.gmtime(1720000000),
            )
        ]
        with _rss(entradas):
            with patch(
                "groq.Groq",
                return_value=_mock_groq_client(_json_liderazgo("CTO", titular)),
            ):
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/8"], api_key="test-key"
                )
                triggers = adapter.obtener_triggers(empresa)

        assert triggers[0].fecha_evento is not None
        assert isinstance(triggers[0].fecha_evento, datetime)

    def test_max_triggers_respetado_con_multiples_eventos(self, empresa: Empresa):
        """El LLM confirma los 3 eventos, pero max_triggers_por_empresa=2 los limita."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Acme SaaS: nuevo CTO, ronda Serie A y adquisición",
                summary="La empresa de software anuncia varios hitos de negocio.",
            )
        ]
        with _rss(entradas):
            with patch("groq.Groq", return_value=_mock_groq_client(_JSON_TODOS_TRUE)):
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/9"],
                    max_triggers_por_empresa=2,
                    api_key="test-key",
                )
                triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) <= 2

    def test_keyword_extra_captura_entrada_sin_nombre_y_degrada_a_mencion(
        self, empresa: Empresa
    ):
        """
        Una keyword del ICP captura una entrada que no menciona el nombre de la
        empresa; el LLM no verifica evento sobre la empresa → mención TIER_3.
        """
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        entradas = [
            _EntradaRSSMock(
                title="Crisis de talento backend en Colombia 2026",
                summary="Las empresas luchan por contratar arquitectos de software.",
            )
        ]
        with _rss(entradas):
            with patch("groq.Groq", return_value=_mock_groq_client(_JSON_TODO_FALSE)):
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/10"],
                    palabras_clave_extra=["talento backend", "arquitectos"],
                    api_key="test-key",
                )
                triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].tier_urgencia == TierUrgencia.TIER_3

    def test_key_pool_compartido_se_reutiliza(self, empresa: Empresa):
        """Se puede inyectar un GroqKeyPool compartido (mismo pool que PropuestaValor)."""
        from src.adapters.llm.groq_key_pool import GroqKeyPool
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter

        titular = "Acme SaaS levanta ronda Serie A"
        entradas = [
            _EntradaRSSMock(
                title=titular, summary="La empresa de software cierra ronda de inversión."
            )
        ]
        with _rss(entradas):
            with patch(
                "groq.Groq", return_value=_mock_groq_client(_json_ronda(titular))
            ):
                pool = GroqKeyPool(api_keys=["k1", "k2"])
                adapter = GoogleAlertsRSSAdapter(
                    rss_urls=["https://alerts.google.com/rss/11"], key_pool=pool
                )
                triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].tier_urgencia == TierUrgencia.TIER_0
        assert adapter._pool is pool
