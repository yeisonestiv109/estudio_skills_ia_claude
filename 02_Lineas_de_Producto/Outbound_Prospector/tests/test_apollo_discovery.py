"""
Tests de ApolloDiscoveryAdapter — descubrimiento por firmografía + sector tech.

Fija el esquema request/response de la búsqueda de organizaciones de Apollo
(mixed_companies/search) que se validó empíricamente contra la API real, y
verifica el FIX del defecto de filtrado (antes solo tamaño+país → devolvía
ONGs, medios y entes públicos):
    (a) el payload incluye filtro de TECNOLOGÍA derivado de anclaje_tecnologico.
    (b) el payload incluye filtro de INDUSTRIA/keywords derivado de
        industrias_objetivo (industrias compradoras del ICP), NUNCA de la
        categoría del propio cliente (regresión del defecto del run #2).
    (c) sin api_key → [].
    (d) error de red → [].
    (e) parseo de organizations → Empresa(DESCUBIERTA), dedup por dominio, país
        = PAIS_DESCONOCIDO si ausente.
    (+) degradación con gracia ante HTTP 422 del filtro avanzado de tecnología.

Todas las llamadas mockean requests.post (sin red real).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.adapters.discovery.apollo_discovery_adapter import (
    _TECH_FILTER_KEY,
    ApolloDiscoveryAdapter,
)
from src.core.domain.models import (
    PAIS_DESCONOCIDO,
    BaseLegal,
    CategoriaEmpresa,
    Empresa,
    EstadoEmpresa,
    ManifiestoICP,
    TamanoEmpresa,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def manifesto_saas() -> ManifiestoICP:
    return ManifiestoICP(
        pain_es_accionable=True,
        dolor_operativo="Monolito que no escala, CTO apagando incendios",
        anclaje_tecnologico=["Amazon Web Services", "Python", "Node.js"],
        categoria_empresa=CategoriaEmpresa.SAAS_B2B_HORIZONTAL,
        vertical="E-commerce",
        industrias_objetivo=["retail", "logística"],
        cargos_decisores=["CTO", "VP Engineering"],
        tamano_empresa=TamanoEmpresa.SME,
        geografia="CO",
        base_legal=BaseLegal.CONSENTIMIENTO_EXPLICITO,
    )


def _mock_response(data: dict, status_code: int = 200, text: str = "") -> MagicMock:
    mock = MagicMock(spec=requests.Response)
    mock.status_code = status_code
    mock.text = text
    mock.json.return_value = data
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock)
    else:
        mock.raise_for_status.return_value = None
    return mock


def _respuesta_orgs(orgs: list[dict]) -> dict:
    return {"organizations": orgs, "pagination": {"total_entries": len(orgs)}}


# ---------------------------------------------------------------------------
# (a) Filtro de TECNOLOGÍA derivado de anclaje_tecnologico
# ---------------------------------------------------------------------------
class TestPayloadFiltroTecnologia:
    def test_payload_incluye_filtro_tecnologia_derivado_del_anclaje(
        self, manifesto_saas: ManifiestoICP
    ):
        with patch(
            "requests.post", return_value=_mock_response(_respuesta_orgs([]))
        ) as mock_post:
            ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(manifesto_saas)

        payload = mock_post.call_args.kwargs["json"]
        assert _TECH_FILTER_KEY in payload
        uids = payload[_TECH_FILTER_KEY]
        # Traducción de frontera nombre→uid (espacios/puntos → guion bajo).
        assert "amazon_web_services" in uids
        assert "python" in uids
        assert "node_js" in uids

    def test_slugs_deduplicados_y_sin_dobles_guiones(self):
        manifesto = ManifiestoICP(
            pain_es_accionable=False,
            anclaje_tecnologico=["Python", "python", "Google  Cloud"],
            categoria_empresa=CategoriaEmpresa.AI_ML_PLATFORM,
            vertical="Datos",
            cargos_decisores=["CTO"],
            tamano_empresa=TamanoEmpresa.STARTUP,
            base_legal=BaseLegal.DATO_PUBLICO,
        )
        with patch(
            "requests.post", return_value=_mock_response(_respuesta_orgs([]))
        ) as mock_post:
            ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(manifesto)

        uids = mock_post.call_args.kwargs["json"][_TECH_FILTER_KEY]
        assert uids.count("python") == 1
        assert "google_cloud" in uids  # doble espacio colapsado


# ---------------------------------------------------------------------------
# (b) Filtro de INDUSTRIA/keywords derivado de industrias_objetivo (path A)
# ---------------------------------------------------------------------------
class TestPayloadFiltroIndustria:
    def test_payload_incluye_keyword_tags_de_industrias_objetivo(
        self, manifesto_saas: ManifiestoICP
    ):
        with patch(
            "requests.post", return_value=_mock_response(_respuesta_orgs([]))
        ) as mock_post:
            ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(manifesto_saas)

        tags = mock_post.call_args.kwargs["json"]["q_organization_keyword_tags"]
        # Derivados de industrias_objetivo (industrias COMPRADORAS del ICP).
        assert "retail" in tags
        assert "logística" in tags

    def test_keyword_tags_nunca_incluyen_la_categoria_del_cliente(
        self, manifesto_saas: ManifiestoICP
    ):
        # Regresión del defecto del run #2: buscar por categoria_empresa del
        # propio cliente (SAAS_B2B_HORIZONTAL) devolvía competidores. Los tags
        # deben venir SOLO de industrias_objetivo, nunca de la categoría/vertical.
        with patch(
            "requests.post", return_value=_mock_response(_respuesta_orgs([]))
        ) as mock_post:
            ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(manifesto_saas)

        tags = mock_post.call_args.kwargs["json"]["q_organization_keyword_tags"]
        assert not any("saas" in t for t in tags)
        assert "e-commerce" not in tags  # el vertical del cliente ya no se usa

    def test_sin_industrias_objetivo_no_envia_filtro_de_keywords(self):
        # ICP sin industrias_objetivo → búsqueda más amplia (solo tech+tamaño+
        # país), sin q_organization_keyword_tags y sin sesgo a competidores.
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
        with patch(
            "requests.post", return_value=_mock_response(_respuesta_orgs([]))
        ) as mock_post:
            ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(manifesto)

        payload = mock_post.call_args.kwargs["json"]
        assert "q_organization_keyword_tags" not in payload

    def test_payload_conserva_tamano_y_pais(self, manifesto_saas: ManifiestoICP):
        with patch(
            "requests.post", return_value=_mock_response(_respuesta_orgs([]))
        ) as mock_post:
            ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(manifesto_saas)

        payload = mock_post.call_args.kwargs["json"]
        assert payload["organization_num_employees_ranges"] == ["51,100", "101,200"]
        assert payload["organization_locations"] == ["Colombia"]


# ---------------------------------------------------------------------------
# (c) Sin api_key → []
# ---------------------------------------------------------------------------
class TestSinApiKey:
    def test_sin_api_key_retorna_lista_vacia(self, manifesto_saas: ManifiestoICP):
        import os

        original = os.environ.pop("APOLLO_API_KEY", None)
        try:
            adapter = ApolloDiscoveryAdapter(api_key=None)
            with patch("requests.post") as mock_post:
                assert adapter.descubrir_empresas(manifesto_saas) == []
            mock_post.assert_not_called()
        finally:
            if original is not None:
                os.environ["APOLLO_API_KEY"] = original


# ---------------------------------------------------------------------------
# (d) Error de red → []
# ---------------------------------------------------------------------------
class TestErroresNoPropagados:
    def test_error_red_retorna_lista_vacia(self, manifesto_saas: ManifiestoICP):
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError):
            adapter = ApolloDiscoveryAdapter(api_key="k")
            assert adapter.descubrir_empresas(manifesto_saas) == []

    def test_timeout_retorna_lista_vacia(self, manifesto_saas: ManifiestoICP):
        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            adapter = ApolloDiscoveryAdapter(api_key="k")
            assert adapter.descubrir_empresas(manifesto_saas) == []

    def test_http_error_retorna_lista_vacia(self, manifesto_saas: ManifiestoICP):
        with patch("requests.post", return_value=_mock_response({}, status_code=500)):
            adapter = ApolloDiscoveryAdapter(api_key="k")
            assert adapter.descubrir_empresas(manifesto_saas) == []


# ---------------------------------------------------------------------------
# (e) Parseo de organizations → Empresa(DESCUBIERTA)
# ---------------------------------------------------------------------------
class TestParseoEmpresas:
    def test_parsea_organizations_a_empresa_descubierta(
        self, manifesto_saas: ManifiestoICP
    ):
        data = _respuesta_orgs(
            [
                {
                    "name": "Imagine Apps",
                    "primary_domain": "imagineapps.co",
                    "estimated_num_employees": 120,
                    "country": "Colombia",
                    "naics_codes": ["541511"],
                },
            ]
        )
        with patch("requests.post", return_value=_mock_response(data)):
            empresas = ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(
                manifesto_saas
            )

        assert len(empresas) == 1
        emp = empresas[0]
        assert isinstance(emp, Empresa)
        assert emp.estado == EstadoEmpresa.DESCUBIERTA
        assert emp.nombre == "Imagine Apps"
        assert emp.dominio == "imagineapps.co"
        assert emp.tamano == TamanoEmpresa.SME  # 120 empleados
        assert emp.vertical == "E-commerce"

    def test_deduplica_por_dominio(self, manifesto_saas: ManifiestoICP):
        data = _respuesta_orgs(
            [
                {
                    "name": "Acme",
                    "primary_domain": "acme.com",
                    "estimated_num_employees": 90,
                },
                {
                    "name": "Acme Dup",
                    "primary_domain": "acme.com",
                    "estimated_num_employees": 90,
                },
            ]
        )
        with patch("requests.post", return_value=_mock_response(data)):
            empresas = ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(
                manifesto_saas
            )
        assert len(empresas) == 1
        assert empresas[0].dominio == "acme.com"

    def test_pais_ausente_usa_centinela(self, manifesto_saas: ManifiestoICP):
        data = _respuesta_orgs(
            [
                {
                    "name": "SinPais",
                    "primary_domain": "sinpais.io",
                    "estimated_num_employees": 60,
                }
            ]
        )
        with patch("requests.post", return_value=_mock_response(data)):
            empresas = ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(
                manifesto_saas
            )
        assert empresas[0].pais == PAIS_DESCONOCIDO

    def test_org_sin_dominio_ni_website_es_omitida(self, manifesto_saas: ManifiestoICP):
        data = _respuesta_orgs(
            [
                {"name": "Sin dominio", "primary_domain": None},
                {
                    "name": "Con dominio",
                    "primary_domain": "ok.com",
                    "estimated_num_employees": 80,
                },
            ]
        )
        with patch("requests.post", return_value=_mock_response(data)):
            empresas = ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(
                manifesto_saas
            )
        assert len(empresas) == 1
        assert empresas[0].dominio == "ok.com"

    def test_deriva_dominio_de_website_url(self, manifesto_saas: ManifiestoICP):
        data = _respuesta_orgs(
            [
                {
                    "name": "Web Only",
                    "primary_domain": None,
                    "website_url": "https://www.webonly.com/about?x=1",
                    "estimated_num_employees": 70,
                }
            ]
        )
        with patch("requests.post", return_value=_mock_response(data)):
            empresas = ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(
                manifesto_saas
            )
        assert empresas[0].dominio == "webonly.com"


# ---------------------------------------------------------------------------
# (+) Degradación con gracia ante HTTP 422 del filtro avanzado de tecnología
# ---------------------------------------------------------------------------
class TestDegradacionFiltroAvanzado:
    def test_422_filtro_avanzado_reintenta_sin_tecnologia(
        self, manifesto_saas: ManifiestoICP
    ):
        resp_422 = _mock_response(
            {},
            status_code=422,
            text=(
                "Cannot access advanced filters currently_using_any_of_technology_uids "
                "on free plan. Please start a trial or upgrade."
            ),
        )
        resp_ok = _mock_response(
            _respuesta_orgs(
                [
                    {
                        "name": "BPT Software",
                        "primary_domain": "bpt.global",
                        "estimated_num_employees": 80,
                    }
                ]
            )
        )
        with patch("requests.post", side_effect=[resp_422, resp_ok]) as mock_post:
            empresas = ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(
                manifesto_saas
            )

        # Reintentó una vez (dos llamadas en total)
        assert mock_post.call_count == 2
        # El segundo payload YA NO lleva el filtro de tecnología...
        segundo_payload = mock_post.call_args_list[1].kwargs["json"]
        assert _TECH_FILTER_KEY not in segundo_payload
        # ...pero conserva el filtro de industria/keywords
        assert "q_organization_keyword_tags" in segundo_payload
        # Y se obtuvo la empresa tech del reintento
        assert len(empresas) == 1
        assert empresas[0].nombre == "BPT Software"

    def test_422_no_relacionado_no_reintenta(self, manifesto_saas: ManifiestoICP):
        resp_422 = _mock_response(
            {}, status_code=422, text="Some other validation error"
        )
        with patch("requests.post", side_effect=[resp_422]) as mock_post:
            empresas = ApolloDiscoveryAdapter(api_key="k").descubrir_empresas(
                manifesto_saas
            )
        assert mock_post.call_count == 1
        assert empresas == []
