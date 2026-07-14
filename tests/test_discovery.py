"""
Tests de la Opción B: Dual-Mode Prospecting.

Cubre:
    1. EstadoEmpresa Enum (nuevo en el Core).
    2. Empresa.estado — ciclo de vida y valor por defecto.
    3. PuertoDescubridorEmpresas (ABC) — no es instanciable directamente.
    4. TheirStackAdapter.descubrir_empresas() — Caso B: Discovery.
    5. Integración: el flujo Discovery → obtener_triggers usa EstadoEmpresa.DESCUBIERTA.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.core.domain.models import (
    BaseLegal,
    CategoriaEmpresa,
    Empresa,
    EstadoEmpresa,
    ManifiestoICP,
    TamanoEmpresa,
)
from src.core.ports.interfaces import PuertoDescubridorEmpresas


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def manifesto_saas() -> ManifiestoICP:
    return ManifiestoICP(
        pain_es_accionable=True,
        dolor_operativo="Monolito que no escala, CTO atrapado apagando incendios",
        anclaje_tecnologico=["Python", "AWS", "Django"],
        categoria_empresa=CategoriaEmpresa.SAAS_B2B_HORIZONTAL,
        vertical="E-commerce",
        cargos_decisores=["CTO", "VP Engineering"],
        tamano_empresa=TamanoEmpresa.MID_MARKET,
        geografia="CO",
        base_legal=BaseLegal.CONSENTIMIENTO_EXPLICITO,
    )


def _respuesta_discovery_mock(empresas: list[dict]) -> dict:
    """
    Construye la respuesta JSON de TheirStack para discovery.

    Esquema real de TheirStack:
        - company_object → objeto anidado con domain, name, employee_count, country_code
        - company        → nombre de la empresa como string (fallback)
    """
    vacantes = []
    for emp in empresas:
        dominio = emp.get("domain", "unknown")
        vacantes.append({
            "id": f"job-{dominio[:4]}",
            "title": "Senior Python Developer",
            "date_posted": "2026-07-10",
            "technologies": [{"name": "Python"}, {"name": "AWS"}],
            "company_object": emp,
            "company": emp.get("name", ""),
        })
    return {"data": vacantes, "total": len(vacantes)}


# ---------------------------------------------------------------------------
# Bloque 1: EstadoEmpresa Enum y campo Empresa.estado
# ---------------------------------------------------------------------------
class TestEstadoEmpresaEnum:
    def test_estado_por_defecto_es_verificada(self):
        """Las empresas creadas manualmente deben tener estado VERIFICADA por defecto."""
        emp = Empresa(
            nombre="Acme",
            dominio="acme.com",
            tamano=TamanoEmpresa.MID_MARKET,
            vertical="SaaS",
        )
        assert emp.estado == EstadoEmpresa.VERIFICADA

    def test_empresa_descubierta_tiene_estado_correcto(self):
        """Las empresas creadas por el adaptador de discovery deben ser DESCUBIERTA."""
        emp = Empresa(
            nombre="Startup Nueva",
            dominio="startupnueva.com",
            tamano=TamanoEmpresa.SME,
            vertical="Fintech",
            estado=EstadoEmpresa.DESCUBIERTA,
        )
        assert emp.estado == EstadoEmpresa.DESCUBIERTA

    def test_todos_los_estados_definidos(self):
        """Los 4 estados del ciclo de vida deben estar presentes."""
        valores = {e.value for e in EstadoEmpresa}
        assert valores == {"DESCUBIERTA", "VERIFICADA", "EN_PIPELINE", "ARCHIVADA"}

    def test_empresa_es_inmutable_incluido_estado(self):
        """frozen=True aplica también al campo estado."""
        from pydantic import ValidationError
        emp = Empresa(
            nombre="Acme",
            dominio="acme.com",
            tamano=TamanoEmpresa.SME,
            vertical="Retail",
            estado=EstadoEmpresa.DESCUBIERTA,
        )
        with pytest.raises(ValidationError):
            emp.estado = EstadoEmpresa.VERIFICADA

    def test_empresa_existente_sin_estado_explicito_es_verificada(self):
        """Los 56 tests previos construyen Empresa sin estado — deben seguir válidos."""
        emp = Empresa(
            nombre="Legacy Corp",
            dominio="legacy.com",
            tamano=TamanoEmpresa.ENTERPRISE,
            vertical="Banca",
        )
        # Estado por defecto: VERIFICADA. No rompe nada existente.
        assert emp.estado == EstadoEmpresa.VERIFICADA


# ---------------------------------------------------------------------------
# Bloque 2: PuertoDescubridorEmpresas es un ABC no instanciable
# ---------------------------------------------------------------------------
class TestPuertoDescubridorEmpresasABC:
    def test_no_es_instanciable_directamente(self):
        with pytest.raises(TypeError):
            PuertoDescubridorEmpresas()  # type: ignore[abstract]

    def test_theirstack_implementa_ambos_puertos(self):
        """TheirStackAdapter debe ser instancia de ambos puertos."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
        from src.core.ports.interfaces import PuertoFuenteTriggers

        adapter = TheirStackAdapter(api_key="test-key")
        assert isinstance(adapter, PuertoFuenteTriggers)
        assert isinstance(adapter, PuertoDescubridorEmpresas)

    def test_google_alerts_solo_implementa_fuente_triggers(self):
        """GoogleAlertsRSSAdapter solo soporta Scoring, no Discovery."""
        from src.adapters.triggers.google_alerts_adapter import GoogleAlertsRSSAdapter
        from src.core.ports.interfaces import PuertoFuenteTriggers

        adapter = GoogleAlertsRSSAdapter(rss_urls=[])
        assert isinstance(adapter, PuertoFuenteTriggers)
        assert not isinstance(adapter, PuertoDescubridorEmpresas)


# ---------------------------------------------------------------------------
# Bloque 3: TheirStackAdapter.descubrir_empresas() — Caso B
# ---------------------------------------------------------------------------
class TestTheirStackDiscovery:

    def _mock_response(self, data: dict, status_code: int = 200) -> MagicMock:
        mock = MagicMock()
        mock.status_code = status_code
        mock.json.return_value = data
        if status_code >= 400:
            import requests
            mock.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock)
        else:
            mock.raise_for_status.return_value = None
        return mock

    def test_descubre_empresas_unicas_de_vacantes(self, manifesto_saas: ManifiestoICP):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        data = _respuesta_discovery_mock([
            {"name": "Acme SaaS", "domain": "acme.com", "employee_count_range": "201-500", "country_code": "CO"},
            {"name": "Beta Corp", "domain": "beta.co", "employee_count_range": "51-200", "country_code": "CO"},
            {"name": "Gamma Tech", "domain": "gamma.io", "employee_count_range": "11-50", "country_code": "CO"},
        ])

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert len(empresas) == 3
        for emp in empresas:
            assert isinstance(emp, Empresa)
            assert emp.estado == EstadoEmpresa.DESCUBIERTA

    def test_empresas_descubiertas_tienen_estado_descubierta(self, manifesto_saas: ManifiestoICP):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        data = _respuesta_discovery_mock([
            {"name": "Nueva Startup", "domain": "nueva.io", "employee_count_range": "11-50", "country_code": "CO"},
        ])

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert empresas[0].estado == EstadoEmpresa.DESCUBIERTA
        assert empresas[0].nombre == "Nueva Startup"
        assert empresas[0].dominio == "nueva.io"

    def test_deduplica_empresas_del_mismo_dominio(self, manifesto_saas: ManifiestoICP):
        """Varias vacantes de la misma empresa deben producir UN solo objeto Empresa."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        # Tres vacantes distintas, todas de acme.com
        vacantes = [
            {"id": "j1", "title": "Dev", "date_posted": "2026-07-01", "technologies": [],
             "company": "Acme",
             "company_object": {"name": "Acme", "domain": "acme.com",
                                "employee_count": 300, "country_code": "CO"}},
            {"id": "j2", "title": "Arch", "date_posted": "2026-07-02", "technologies": [],
             "company": "Acme",
             "company_object": {"name": "Acme", "domain": "acme.com",
                                "employee_count": 300, "country_code": "CO"}},
        ]
        data = {"data": vacantes, "total": 2}

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert len(empresas) == 1
        assert empresas[0].dominio == "acme.com"

    def test_vacantes_sin_dominio_son_omitidas(self, manifesto_saas: ManifiestoICP):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        vacantes = [
            {"id": "j1", "title": "Dev", "date_posted": "2026-07-01", "technologies": [],
             "company": "",
             "company_object": {"name": "", "domain": ""}},
            {"id": "j2", "title": "Dev", "date_posted": "2026-07-01", "technologies": [],
             "company": "Valid Corp",
             "company_object": {"name": "Valid Corp", "domain": "valid.com",
                                "employee_count": 150, "country_code": "CO"}},
        ]
        data = {"data": vacantes, "total": 2}

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert len(empresas) == 1
        assert empresas[0].dominio == "valid.com"

    def test_respuesta_vacia_retorna_lista_vacia(self, manifesto_saas: ManifiestoICP):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        with patch("requests.post", return_value=self._mock_response({"data": [], "total": 0})):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert empresas == []

    def test_sin_api_key_retorna_lista_vacia(self, manifesto_saas: ManifiestoICP):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
        import os
        original = os.environ.pop("THEIRSTACK_API_KEY", None)
        try:
            adapter = TheirStackAdapter(api_key=None)
            empresas = adapter.descubrir_empresas(manifesto_saas)
            assert empresas == []
        finally:
            if original is not None:
                os.environ["THEIRSTACK_API_KEY"] = original

    def test_error_red_no_propaga_al_core(self, manifesto_saas: ManifiestoICP):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
        import requests

        with patch("requests.post", side_effect=requests.exceptions.ConnectionError):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert empresas == []

    def test_payload_usa_tecnologias_del_manifesto(self, manifesto_saas: ManifiestoICP):
        """En discovery, las tecnologías del ICP (no del constructor) van en el payload."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        data = _respuesta_discovery_mock([
            {"name": "X Corp", "domain": "x.com", "employee_count_range": "51-200", "country_code": "CO"},
        ])

        with patch("requests.post", return_value=self._mock_response(data)) as mock_post:
            # El constructor recibe tecnologías distintas al manifesto
            adapter = TheirStackAdapter(api_key="test-key", tecnologias_objetivo=["Java"])
            adapter.descubrir_empresas(manifesto_saas)

        payload = mock_post.call_args.kwargs["json"]
        # Debe usar las tecnologías del manifesto (Python, AWS, Django)
        assert "python" in payload["company_technology_slug_or"]
        assert "aws" in payload["company_technology_slug_or"]
        # No las del constructor (Java)
        assert "java" not in payload["company_technology_slug_or"]
        # Filtro obligatorio de TheirStack (E-024): posted_at_max_age_days requerido
        assert payload["posted_at_max_age_days"] == 30

    def test_tamano_empresa_mapeado_correctamente(self, manifesto_saas: ManifiestoICP):
        """Verifica que el entero employee_count se mapea al TamanoEmpresa correcto."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        data = _respuesta_discovery_mock([
            {"name": "Startup Corp", "domain": "startup.co", "employee_count": 30, "country_code": "CO"},
            {"name": "SME Corp", "domain": "sme.co", "employee_count": 150, "country_code": "CO"},
            {"name": "Mid Corp", "domain": "mid.co", "employee_count": 600, "country_code": "CO"},
            {"name": "Big Corp", "domain": "big.co", "employee_count": 5000, "country_code": "CO"},
        ])

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        dominios = {e.dominio: e.tamano for e in empresas}
        assert dominios["startup.co"] == TamanoEmpresa.STARTUP
        assert dominios["sme.co"] == TamanoEmpresa.SME
        assert dominios["mid.co"] == TamanoEmpresa.MID_MARKET
        assert dominios["big.co"] == TamanoEmpresa.ENTERPRISE

    def test_limite_empleados_frontera(self, manifesto_saas: ManifiestoICP):
        """Casos frontera del mapeo: 49→STARTUP, 50→SME, 200→SME, 201→MID, 1000→MID, 1001→ENTERPRISE."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        data = _respuesta_discovery_mock([
            {"name": "F49", "domain": "f49.co", "employee_count": 49, "country_code": "CO"},
            {"name": "F50", "domain": "f50.co", "employee_count": 50, "country_code": "CO"},
            {"name": "F200", "domain": "f200.co", "employee_count": 200, "country_code": "CO"},
            {"name": "F201", "domain": "f201.co", "employee_count": 201, "country_code": "CO"},
            {"name": "F1000", "domain": "f1000.co", "employee_count": 1000, "country_code": "CO"},
            {"name": "F1001", "domain": "f1001.co", "employee_count": 1001, "country_code": "CO"},
        ])

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        m = {e.dominio: e.tamano for e in empresas}
        assert m["f49.co"] == TamanoEmpresa.STARTUP
        assert m["f50.co"] == TamanoEmpresa.SME
        assert m["f200.co"] == TamanoEmpresa.SME
        assert m["f201.co"] == TamanoEmpresa.MID_MARKET
        assert m["f1000.co"] == TamanoEmpresa.MID_MARKET
        assert m["f1001.co"] == TamanoEmpresa.ENTERPRISE


# ---------------------------------------------------------------------------
# Bloque 4: Integración Discovery → Scoring (flujo completo Caso B)
# ---------------------------------------------------------------------------
class TestFlujoDiscoveryScoring:
    def test_empresa_descubierta_puede_recibir_triggers(self, manifesto_saas: ManifiestoICP):
        """
        Verifica el flujo orquestado completo del Caso B:
            1. descubrir_empresas() → lista de Empresa(DESCUBIERTA)
            2. obtener_triggers(empresa) → Trigger válido con empresa_id correcto
        """
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        # --- Paso 1: Discovery ---
        discovery_data = _respuesta_discovery_mock([
            {"name": "Target Corp", "domain": "target.co",
             "employee_count_range": "201-500", "country_code": "CO"},
        ])

        # --- Paso 2: Scoring (3 vacantes para trigger ALTA) ---
        scoring_data = {
            "data": [
                {"id": "j1", "title": "Senior Python Dev", "date_posted": "2026-07-10",
                 "technologies": [{"name": "Python"}]},
                {"id": "j2", "title": "AWS Architect", "date_posted": "2026-07-08",
                 "technologies": [{"name": "AWS"}]},
                {"id": "j3", "title": "Django Backend", "date_posted": "2026-07-05",
                 "technologies": [{"name": "Django"}]},
            ],
            "total": 3,
        }

        mock_discovery = MagicMock()
        mock_discovery.status_code = 200
        mock_discovery.json.return_value = discovery_data
        mock_discovery.raise_for_status.return_value = None

        mock_scoring = MagicMock()
        mock_scoring.status_code = 200
        mock_scoring.json.return_value = scoring_data
        mock_scoring.raise_for_status.return_value = None

        adapter = TheirStackAdapter(api_key="test-key")

        with patch("requests.post", side_effect=[mock_discovery, mock_scoring]):
            empresas = adapter.descubrir_empresas(manifesto_saas)
            assert len(empresas) == 1
            empresa = empresas[0]

            # La empresa descubierta tiene el estado correcto
            assert empresa.estado == EstadoEmpresa.DESCUBIERTA
            assert empresa.nombre == "Target Corp"

            # El scoring sobre la empresa descubierta genera triggers válidos
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        trigger = triggers[0]
        # El trigger referencia a la empresa descubierta por su id
        assert trigger.empresa_id == empresa.id
        from src.core.domain.models import NivelConfianza, OrigenTrigger
        assert trigger.nivel_confianza == NivelConfianza.ALTA
        assert trigger.origen == OrigenTrigger.THEIRSTACK
