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
        vacantes.append(
            {
                "id": f"job-{dominio[:4]}",
                "title": "Senior Python Developer",
                "date_posted": "2026-07-10",
                "technologies": [{"name": "Python"}, {"name": "AWS"}],
                "company_object": emp,
                "company": emp.get("name", ""),
            }
        )
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

            mock.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=mock
            )
        else:
            mock.raise_for_status.return_value = None
        return mock

    def test_descubre_empresas_unicas_de_vacantes(self, manifesto_saas: ManifiestoICP):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        data = _respuesta_discovery_mock(
            [
                {
                    "name": "Acme SaaS",
                    "domain": "acme.com",
                    "employee_count_range": "201-500",
                    "country_code": "CO",
                },
                {
                    "name": "Beta Corp",
                    "domain": "beta.co",
                    "employee_count_range": "51-200",
                    "country_code": "CO",
                },
                {
                    "name": "Gamma Tech",
                    "domain": "gamma.io",
                    "employee_count_range": "11-50",
                    "country_code": "CO",
                },
            ]
        )

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert len(empresas) == 3
        for emp in empresas:
            assert isinstance(emp, Empresa)
            assert emp.estado == EstadoEmpresa.DESCUBIERTA

    def test_empresas_descubiertas_tienen_estado_descubierta(
        self, manifesto_saas: ManifiestoICP
    ):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        data = _respuesta_discovery_mock(
            [
                {
                    "name": "Nueva Startup",
                    "domain": "nueva.io",
                    "employee_count_range": "11-50",
                    "country_code": "CO",
                },
            ]
        )

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert empresas[0].estado == EstadoEmpresa.DESCUBIERTA
        assert empresas[0].nombre == "Nueva Startup"
        assert empresas[0].dominio == "nueva.io"

    def test_tamano_reutiliza_cache_y_triggers_hace_query_precisa_1_credito(
        self, manifesto_saas: ManifiestoICP
    ):
        """Tras el discovery, estimar_tamano() reutiliza el employee_count
        cacheado SIN re-consultar (0 créditos), pero obtener_triggers() hace una
        query de banda para el aging REAL (vacante técnica vieja-y-abierta). Con
        80d abierta → TIER_0 (banda >=75d)."""
        from datetime import datetime, timedelta, timezone

        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
        from src.core.domain.models import TierUrgencia

        fecha_vieja = (datetime.now(timezone.utc) - timedelta(days=80)).strftime(
            "%Y-%m-%d"
        )
        data = {
            "data": [
                {
                    "id": "j1",
                    "job_title": "Backend Developer",
                    "date_posted": fecha_vieja,
                    "technologies": [{"name": "Python"}],
                    "company_object": {
                        "name": "Aged Co",
                        "domain": "agedco.com",
                        "employee_count": 120,
                        "country_code": "CO",
                    },
                    "company": "Aged Co",
                }
            ],
            "metadata": {},
        }

        with patch(
            "requests.post", return_value=self._mock_response(data)
        ) as mock_post:
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)
            assert len(empresas) == 1
            emp = empresas[0]
            assert mock_post.call_count == 1  # solo la llamada de discovery

            # obtener_triggers hace la query de banda TIER_0 [75-90d]; el mock la
            # satisface en la 1ª banda → +1 llamada (no llega a la banda TIER_1).
            triggers = adapter.obtener_triggers(emp)
            assert mock_post.call_count == 2  # discovery + query banda TIER_0
            payload_aging = mock_post.call_args.kwargs["json"]
            assert payload_aging["limit"] == 1
            # Ventana de fechas + solo abiertas + rol técnico a nivel vacante
            # (NO order_by deprecado, NO company_technology_slug).
            assert "order_by" not in payload_aging
            assert payload_aging["is_closed"] is False
            assert "posted_at_gte" in payload_aging
            assert "posted_at_lte" in payload_aging
            assert payload_aging.get("job_title_pattern_or")
            assert payload_aging["company_domain_or"] == [emp.dominio]
            assert len(triggers) == 1
            assert triggers[0].tier_urgencia == TierUrgencia.TIER_0  # aging 80d >= 75

            # estimar_tamano SÍ reutiliza la cache → NO re-consulta
            est = adapter.estimar_tamano(emp)
            assert mock_post.call_count == 2  # sigue en 2, sin llamada extra
            assert est is not None
            assert est.tamano_estimado == TamanoEmpresa.SME  # 120 empleados

    def test_obtener_triggers_fallback_cache_si_query_falla(
        self, manifesto_saas: ManifiestoICP
    ):
        """Si AMBAS bandas de la query de aging fallan (ej. créditos agotados →
        None), obtener_triggers cae al FALLBACK de cache del discovery (0 créditos)
        en vez de retornar []. Cache con 80d → TIER_0."""
        from datetime import datetime, timedelta, timezone

        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
        from src.core.domain.models import TierUrgencia

        fecha_vieja = (datetime.now(timezone.utc) - timedelta(days=80)).strftime(
            "%Y-%m-%d"
        )
        data_discovery = {
            "data": [
                {
                    "id": "j1",
                    "job_title": "Backend Developer",
                    "date_posted": fecha_vieja,
                    "technology_slugs": ["python"],
                    "company_object": {
                        "name": "Aged Co",
                        "domain": "agedco.com",
                        "employee_count": 120,
                        "country_code": "CO",
                    },
                    "company": "Aged Co",
                }
            ],
            "metadata": {},
        }
        # discovery OK; luego AMBAS bandas de aging (TIER_0 y TIER_1) dan 402.
        respuestas = [
            self._mock_response(data_discovery),
            self._mock_response({"data": []}, status_code=402),
            self._mock_response({"data": []}, status_code=402),
        ]
        with patch("requests.post", side_effect=respuestas) as mock_post:
            adapter = TheirStackAdapter(api_key="test-key")
            emp = adapter.descubrir_empresas(manifesto_saas)[0]
            triggers = adapter.obtener_triggers(emp)
            assert mock_post.call_count == 3  # discovery + 2 bandas (ambas fallan)
            assert len(triggers) == 1  # cache rescató el trigger
            assert triggers[0].tier_urgencia == TierUrgencia.TIER_0

    def test_obtener_triggers_query_si_empresa_no_descubierta(self):
        """Una empresa NO descubierta por esta instancia (sin cache) dispara las
        DOS bandas de query (TIER_0 y TIER_1); ambas vacías → sin trigger."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        emp = Empresa(
            nombre="Externa",
            dominio="externa.com",
            tamano=TamanoEmpresa.SME,
            vertical="X",
        )
        data = {"data": [], "metadata": {}}
        with patch(
            "requests.post", return_value=self._mock_response(data)
        ) as mock_post:
            adapter = TheirStackAdapter(api_key="test-key")
            triggers = adapter.obtener_triggers(emp)
            assert mock_post.call_count == 2  # 2 bandas (ambas vacías), sin cache
            assert triggers == []

    def test_sin_vacante_vieja_y_abierta_cae_a_cache_fresca_tier2(
        self, manifesto_saas: ManifiestoICP
    ):
        """CLAVE del rediseño 26-jul: si NINGUNA banda de la query de aging
        (TIER_0 [75-90d] ni TIER_1 [45-75d]) devuelve resultados (no hay
        sangrado; 0 créditos), obtener_triggers cae a la cache del discovery
        (vacante FRESCA) → TIER_2, no TIER_0."""
        from datetime import datetime, timedelta, timezone

        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter
        from src.core.domain.models import TierUrgencia

        fecha_fresca = (datetime.now(timezone.utc) - timedelta(days=5)).strftime(
            "%Y-%m-%d"
        )
        data_discovery = {
            "data": [
                {
                    "id": "j1",
                    "job_title": "Backend Developer",
                    "date_posted": fecha_fresca,
                    "technology_slugs": ["python"],
                    "company_object": {
                        "name": "Fresh Co",
                        "domain": "freshco.com",
                        "employee_count": 120,
                        "country_code": "CO",
                    },
                    "company": "Fresh Co",
                }
            ],
            "metadata": {},
        }
        # discovery trae la vacante fresca; AMBAS bandas de aging → 0 resultados.
        respuestas = [
            self._mock_response(data_discovery),
            self._mock_response({"data": []}),
            self._mock_response({"data": []}),
        ]
        with patch("requests.post", side_effect=respuestas) as mock_post:
            adapter = TheirStackAdapter(api_key="test-key")
            emp = adapter.descubrir_empresas(manifesto_saas)[0]
            triggers = adapter.obtener_triggers(emp)
            assert mock_post.call_count == 3  # discovery + 2 bandas (ambas vacías)
            assert len(triggers) == 1  # cache fresca rescató el contexto
            assert triggers[0].tier_urgencia == TierUrgencia.TIER_2  # aging 5d < 45

    def test_deduplica_empresas_del_mismo_dominio(self, manifesto_saas: ManifiestoICP):
        """Varias vacantes de la misma empresa deben producir UN solo objeto Empresa."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        # Tres vacantes distintas, todas de acme.com
        vacantes = [
            {
                "id": "j1",
                "title": "Dev",
                "date_posted": "2026-07-01",
                "technologies": [],
                "company": "Acme",
                "company_object": {
                    "name": "Acme",
                    "domain": "acme.com",
                    "employee_count": 300,
                    "country_code": "CO",
                },
            },
            {
                "id": "j2",
                "title": "Arch",
                "date_posted": "2026-07-02",
                "technologies": [],
                "company": "Acme",
                "company_object": {
                    "name": "Acme",
                    "domain": "acme.com",
                    "employee_count": 300,
                    "country_code": "CO",
                },
            },
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
            {
                "id": "j1",
                "title": "Dev",
                "date_posted": "2026-07-01",
                "technologies": [],
                "company": "",
                "company_object": {"name": "", "domain": ""},
            },
            {
                "id": "j2",
                "title": "Dev",
                "date_posted": "2026-07-01",
                "technologies": [],
                "company": "Valid Corp",
                "company_object": {
                    "name": "Valid Corp",
                    "domain": "valid.com",
                    "employee_count": 150,
                    "country_code": "CO",
                },
            },
        ]
        data = {"data": vacantes, "total": 2}

        with patch("requests.post", return_value=self._mock_response(data)):
            adapter = TheirStackAdapter(api_key="test-key")
            empresas = adapter.descubrir_empresas(manifesto_saas)

        assert len(empresas) == 1
        assert empresas[0].dominio == "valid.com"

    def test_respuesta_vacia_retorna_lista_vacia(self, manifesto_saas: ManifiestoICP):
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        with patch(
            "requests.post", return_value=self._mock_response({"data": [], "total": 0})
        ):
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

        data = _respuesta_discovery_mock(
            [
                {
                    "name": "X Corp",
                    "domain": "x.com",
                    "employee_count_range": "51-200",
                    "country_code": "CO",
                },
            ]
        )

        with patch(
            "requests.post", return_value=self._mock_response(data)
        ) as mock_post:
            # El constructor recibe tecnologías distintas al manifesto
            adapter = TheirStackAdapter(
                api_key="test-key", tecnologias_objetivo=["Java"]
            )
            adapter.descubrir_empresas(manifesto_saas)

        payload = mock_post.call_args.kwargs["json"]
        # Debe usar las tecnologías del manifesto (Python, AWS, Django)
        assert "python" in payload["company_technology_slug_or"]
        assert "aws" in payload["company_technology_slug_or"]
        # No las del constructor (Java)
        assert "java" not in payload["company_technology_slug_or"]
        # Filtro obligatorio de TheirStack (E-024): posted_at_max_age_days requerido.
        # Ventana = 90 días (Signal-First Discovery, 25-jul-2026): antes 30d, pero
        # eso jamás descubría vacantes ENVEJECIDAS (>30d = el trigger TIER_0 de
        # fallo de reclutamiento). 90d = corte duro de SHiFT! y ventana de decay CAUSA.
        assert payload["posted_at_max_age_days"] == 90
        # Filtro de TAMAÑO derivado del ICP (fix sesgo enterprise, 25-jul-2026).
        # manifesto_saas es MID_MARKET → 201-1000 empleados.
        assert payload["min_employee_count"] == 201
        assert payload["max_employee_count"] == 1000

    def test_discovery_filtra_por_tamano_sme_del_icp(self):
        """Un ICP SME (50-200) debe pedir a TheirStack ese rango de empleados,
        no traer grandes empresas y filtrarlas después."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        manifesto = ManifiestoICP(
            pain_es_accionable=False,
            anclaje_tecnologico=["Python"],
            categoria_empresa=CategoriaEmpresa.CONSULTORA_IT,
            vertical="Tecnología",
            cargos_decisores=["CTO"],
            tamano_empresa=TamanoEmpresa.SME,
            geografia="CO",
            base_legal=BaseLegal.DATO_PUBLICO,
        )
        data = _respuesta_discovery_mock([])
        with patch("requests.post", return_value=self._mock_response(data)) as mock_post:
            TheirStackAdapter(api_key="test-key").descubrir_empresas(manifesto)

        payload = mock_post.call_args.kwargs["json"]
        assert payload["min_employee_count"] == 50
        assert payload["max_employee_count"] == 200

    def test_tamano_empresa_mapeado_correctamente(self, manifesto_saas: ManifiestoICP):
        """Verifica que el entero employee_count se mapea al TamanoEmpresa correcto."""
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        data = _respuesta_discovery_mock(
            [
                {
                    "name": "Startup Corp",
                    "domain": "startup.co",
                    "employee_count": 30,
                    "country_code": "CO",
                },
                {
                    "name": "SME Corp",
                    "domain": "sme.co",
                    "employee_count": 150,
                    "country_code": "CO",
                },
                {
                    "name": "Mid Corp",
                    "domain": "mid.co",
                    "employee_count": 600,
                    "country_code": "CO",
                },
                {
                    "name": "Big Corp",
                    "domain": "big.co",
                    "employee_count": 5000,
                    "country_code": "CO",
                },
            ]
        )

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

        data = _respuesta_discovery_mock(
            [
                {
                    "name": "F49",
                    "domain": "f49.co",
                    "employee_count": 49,
                    "country_code": "CO",
                },
                {
                    "name": "F50",
                    "domain": "f50.co",
                    "employee_count": 50,
                    "country_code": "CO",
                },
                {
                    "name": "F200",
                    "domain": "f200.co",
                    "employee_count": 200,
                    "country_code": "CO",
                },
                {
                    "name": "F201",
                    "domain": "f201.co",
                    "employee_count": 201,
                    "country_code": "CO",
                },
                {
                    "name": "F1000",
                    "domain": "f1000.co",
                    "employee_count": 1000,
                    "country_code": "CO",
                },
                {
                    "name": "F1001",
                    "domain": "f1001.co",
                    "employee_count": 1001,
                    "country_code": "CO",
                },
            ]
        )

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
    def test_empresa_descubierta_puede_recibir_triggers(
        self, manifesto_saas: ManifiestoICP
    ):
        """
        Verifica el flujo orquestado completo del Caso B:
            1. descubrir_empresas() → lista de Empresa(DESCUBIERTA)
            2. obtener_triggers(empresa) → Trigger válido con empresa_id correcto
        """
        from src.adapters.triggers.theirstack_adapter import TheirStackAdapter

        # --- Discovery con 3 vacantes para Target Corp (mismo dominio) ---
        # Híbrido 25-jul: el scoring hace UNA query precisa (limit=1 ASC) para el
        # aging real. El mock devuelve el mismo payload (3 vacantes) también para
        # esa query, así que el parseo reporta nivel ALTA. El foco del test es el
        # cableado del flujo: empresa descubierta → trigger con empresa_id correcto.
        target_obj = {
            "name": "Target Corp",
            "domain": "target.co",
            "employee_count": 300,
            "country_code": "CO",
        }
        discovery_data = {
            "data": [
                {
                    "id": "j1",
                    "title": "Senior Python Dev",
                    "date_posted": "2026-07-10",
                    "technologies": [{"name": "Python"}],
                    "company_object": target_obj,
                    "company": "Target Corp",
                },
                {
                    "id": "j2",
                    "title": "AWS Architect",
                    "date_posted": "2026-07-08",
                    "technologies": [{"name": "AWS"}],
                    "company_object": target_obj,
                    "company": "Target Corp",
                },
                {
                    "id": "j3",
                    "title": "Django Backend",
                    "date_posted": "2026-07-05",
                    "technologies": [{"name": "Django"}],
                    "company_object": target_obj,
                    "company": "Target Corp",
                },
            ],
            "metadata": {},
        }

        mock_discovery = MagicMock()
        mock_discovery.status_code = 200
        mock_discovery.json.return_value = discovery_data
        mock_discovery.raise_for_status.return_value = None

        adapter = TheirStackAdapter(api_key="test-key")

        with patch("requests.post", return_value=mock_discovery) as mock_post:
            empresas = adapter.descubrir_empresas(manifesto_saas)
            assert len(empresas) == 1
            empresa = empresas[0]

            # La empresa descubierta tiene el estado correcto
            assert empresa.estado == EstadoEmpresa.DESCUBIERTA
            assert empresa.nombre == "Target Corp"

            # El scoring hace 1 query precisa de aging → +1 llamada
            triggers = adapter.obtener_triggers(empresa)
            assert mock_post.call_count == 2  # discovery + query aging

        assert len(triggers) == 1
        trigger = triggers[0]
        # El trigger referencia a la empresa descubierta por su id
        assert trigger.empresa_id == empresa.id
        from src.core.domain.models import NivelConfianza, OrigenTrigger

        assert trigger.nivel_confianza == NivelConfianza.ALTA  # mock devuelve 3
        assert trigger.origen == OrigenTrigger.THEIRSTACK
