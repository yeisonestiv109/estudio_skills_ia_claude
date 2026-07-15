"""
Tests unitarios del Motor 3 — cascada Apollo→Hunter, sin llamadas reales a APIs.

Mockea requests.get/post para ApolloClient y HunterClient. Verifica que la
cascada respeta la regla de corte de costo (0 perfiles Apollo → 0 llamadas
Hunter) y que PoliticaMapeoEstadoCorreo traduce correctamente al vocabulario
del Core (EstadoCorreo, confianza_dato).

Ningún test de este archivo consume créditos reales de Apollo/Hunter: todas
las llamadas de red están parcheadas con unittest.mock.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.adapters.enrichment.apollo_client import ApolloClient
from src.adapters.enrichment.apollo_hunter_cascada_adapter import (
    ApolloHunterCascadaAdapter,
)
from src.adapters.enrichment.hunter_client import HunterClient
from src.adapters.enrichment.mapeo_estado_correo import PoliticaMapeoEstadoCorreo
from src.core.domain.models import (
    AutoridadDecision,
    Decisor,
    Empresa,
    EstadoCorreo,
    Seniority,
    TamanoEmpresa,
)


@pytest.fixture
def empresa() -> Empresa:
    return Empresa(
        nombre="Acme SaaS",
        dominio="acme.com",
        tamano=TamanoEmpresa.MID_MARKET,
        vertical="E-commerce",
        ciudad="Bogotá",
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
# Bloque 1: PoliticaMapeoEstadoCorreo — lógica pura, sin red
# ---------------------------------------------------------------------------
class TestPoliticaMapeoEstadoCorreo:
    policy = PoliticaMapeoEstadoCorreo()

    def test_valid_score_alto_mapea_verificado(self):
        estado, confianza = self.policy.mapear(
            email_encontrado=True, hunter_status="valid", hunter_score=95
        )
        assert estado == EstadoCorreo.VERIFICADO
        assert confianza == 0.90

    def test_accept_all_score_80_mapea_inferido_0_70_apto(self):
        """Calibración aprobada: accept_all score>=80 -> confianza 0.70 (apto para M4)."""
        estado, confianza = self.policy.mapear(
            email_encontrado=True, hunter_status="accept_all", hunter_score=80
        )
        assert estado == EstadoCorreo.INFERIDO
        assert confianza == 0.70

    def test_webmail_score_79_mapea_inferido_0_65_no_apto(self):
        """Calibración aprobada: score 50-79 -> confianza 0.65 (cola manual)."""
        estado, confianza = self.policy.mapear(
            email_encontrado=True, hunter_status="webmail", hunter_score=79
        )
        assert estado == EstadoCorreo.INFERIDO
        assert confianza == 0.65

    def test_invalid_mapea_rebotado(self):
        estado, confianza = self.policy.mapear(
            email_encontrado=True, hunter_status="invalid", hunter_score=10
        )
        assert estado == EstadoCorreo.REBOTADO
        assert confianza == 0.10

    def test_score_bajo_50_mapea_rebotado_aunque_status_no_sea_invalid(self):
        """Score < 50 es motivo suficiente de REBOTADO, sin importar el status literal."""
        estado, confianza = self.policy.mapear(
            email_encontrado=True, hunter_status="unknown", hunter_score=30
        )
        assert estado == EstadoCorreo.REBOTADO

    def test_sin_email_con_patron_inferido_mapea_inferido_0_55(self):
        estado, confianza = self.policy.mapear(
            email_encontrado=False, patron_inferido=True
        )
        assert estado == EstadoCorreo.INFERIDO
        assert confianza == 0.55

    def test_sin_email_sin_patron_mapea_no_resuelto(self):
        estado, confianza = self.policy.mapear(
            email_encontrado=False, patron_inferido=False
        )
        assert estado == EstadoCorreo.NO_RESUELTO
        assert confianza == 0.0

    def test_email_encontrado_sin_invocar_hunter_mapea_no_resuelto(self):
        """Sin verificación de Hunter no hay base para confiar en el dato crudo de Apollo."""
        estado, confianza = self.policy.mapear(email_encontrado=True)
        assert estado == EstadoCorreo.NO_RESUELTO
        assert confianza == 0.0


# ---------------------------------------------------------------------------
# Bloque 2: ApolloClient — mockeado, sin red real
# ---------------------------------------------------------------------------
class TestApolloClient:
    def test_busca_perfiles_y_retorna_lista_cruda(self):
        payload = {
            "people": [{"name": "Ana Torres", "title": "CTO", "email": "ana@acme.com"}]
        }
        with patch("requests.post", return_value=_mock_response(payload)):
            client = ApolloClient(api_key="test-key")
            perfiles = client.buscar_perfiles("acme.com", ["CTO"])

        assert len(perfiles) == 1
        assert perfiles[0]["name"] == "Ana Torres"

    def test_cero_perfiles_retorna_lista_vacia(self):
        with patch("requests.post", return_value=_mock_response({"people": []})):
            client = ApolloClient(api_key="test-key")
            perfiles = client.buscar_perfiles("acme.com", ["CTO"])

        assert perfiles == []

    def test_http_error_no_propaga_retorna_vacio(self):
        with patch("requests.post", return_value=_mock_response({}, status_code=403)):
            client = ApolloClient(api_key="test-key")
            perfiles = client.buscar_perfiles("acme.com", ["CTO"])

        assert perfiles == []

    def test_timeout_no_propaga_retorna_vacio(self):
        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            client = ApolloClient(api_key="test-key")
            perfiles = client.buscar_perfiles("acme.com", ["CTO"])

        assert perfiles == []

    def test_sin_api_key_no_llama_a_la_red(self):
        with patch("requests.post") as mock_post:
            client = ApolloClient(api_key=None)
            # Aseguramos que ningún atributo de entorno cuele una key real
            client._api_key = None
            perfiles = client.buscar_perfiles("acme.com", ["CTO"])

        assert perfiles == []
        mock_post.assert_not_called()

    def test_sin_cargos_no_llama_a_la_red(self):
        with patch("requests.post") as mock_post:
            client = ApolloClient(api_key="test-key")
            perfiles = client.buscar_perfiles("acme.com", [])

        assert perfiles == []
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Bloque 3: HunterClient — mockeado, sin red real
# ---------------------------------------------------------------------------
class TestHunterClient:
    def test_verificar_email_retorna_status_y_score(self):
        payload = {"data": {"status": "valid", "score": 97}}
        with patch("requests.get", return_value=_mock_response(payload)):
            client = HunterClient(api_key="test-key")
            resultado = client.verificar_email("ana@acme.com")

        assert resultado == {"status": "valid", "score": 97}

    def test_verificar_email_http_error_retorna_none(self):
        with patch("requests.get", return_value=_mock_response({}, status_code=429)):
            client = HunterClient(api_key="test-key")
            resultado = client.verificar_email("ana@acme.com")

        assert resultado is None

    def test_verificar_email_timeout_retorna_none(self):
        with patch("requests.get", side_effect=requests.exceptions.Timeout):
            client = HunterClient(api_key="test-key")
            resultado = client.verificar_email("ana@acme.com")

        assert resultado is None

    def test_verificar_email_sin_api_key_retorna_none_sin_llamar_red(self):
        with patch("requests.get") as mock_get:
            client = HunterClient(api_key=None)
            client._api_key = None
            resultado = client.verificar_email("ana@acme.com")

        assert resultado is None
        mock_get.assert_not_called()

    def test_inferir_patron_dominio_true_cuando_hay_patron(self):
        payload = {"data": {"pattern": "{first}.{last}"}}
        with patch("requests.get", return_value=_mock_response(payload)):
            client = HunterClient(api_key="test-key")
            assert client.inferir_patron_dominio("acme.com") is True

    def test_inferir_patron_dominio_false_sin_patron(self):
        payload = {"data": {"pattern": None}}
        with patch("requests.get", return_value=_mock_response(payload)):
            client = HunterClient(api_key="test-key")
            assert client.inferir_patron_dominio("acme.com") is False

    def test_inferir_patron_dominio_error_red_retorna_false(self):
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
            client = HunterClient(api_key="test-key")
            assert client.inferir_patron_dominio("acme.com") is False


# ---------------------------------------------------------------------------
# Bloque 4: ApolloHunterCascadaAdapter — la cascada completa, con clientes fake
# ---------------------------------------------------------------------------
class TestApolloHunterCascadaAdapter:
    def test_apollo_cero_perfiles_no_invoca_hunter(self, empresa: Empresa):
        """
        REGLA DE CORTE DE COSTO (crítica): 0 perfiles de Apollo -> CERO llamadas
        de red a Hunter. Se verifica con un mock que falla si se le llama.
        """
        apollo_fake = MagicMock(spec=ApolloClient)
        apollo_fake.buscar_perfiles.return_value = []

        hunter_fake = MagicMock(spec=HunterClient)

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, ["CTO"])

        assert resultado == []
        hunter_fake.verificar_email.assert_not_called()
        hunter_fake.inferir_patron_dominio.assert_not_called()

    def test_sin_cargos_no_invoca_ni_apollo_ni_hunter(self, empresa: Empresa):
        apollo_fake = MagicMock(spec=ApolloClient)
        hunter_fake = MagicMock(spec=HunterClient)

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, [])

        assert resultado == []
        apollo_fake.buscar_perfiles.assert_not_called()
        hunter_fake.verificar_email.assert_not_called()

    def test_perfil_con_email_valido_produce_decisor_verificado(self, empresa: Empresa):
        apollo_fake = MagicMock(spec=ApolloClient)
        apollo_fake.buscar_perfiles.return_value = [
            {
                "name": "Ana Torres",
                "title": "Chief Technology Officer",
                "email": "ana@acme.com",
            }
        ]
        hunter_fake = MagicMock(spec=HunterClient)
        hunter_fake.verificar_email.return_value = {"status": "valid", "score": 95}

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, ["CTO"])

        assert len(resultado) == 1
        decisor = resultado[0]
        assert isinstance(decisor, Decisor)
        assert decisor.empresa_id == empresa.id
        assert decisor.nombre == "Ana Torres"
        assert decisor.estado_correo == EstadoCorreo.VERIFICADO
        assert decisor.confianza_dato == 0.90
        assert decisor.seniority == Seniority.C_LEVEL
        assert decisor.autoridad_decision == AutoridadDecision.DECISION_MAKER
        assert str(decisor.correo) == "ana@acme.com"
        hunter_fake.verificar_email.assert_called_once_with("ana@acme.com")
        hunter_fake.inferir_patron_dominio.assert_not_called()

    def test_perfil_sin_email_invoca_domain_search_no_verify(self, empresa: Empresa):
        """Perfil sin email: se debe invocar inferir_patron_dominio, NUNCA verificar_email."""
        apollo_fake = MagicMock(spec=ApolloClient)
        apollo_fake.buscar_perfiles.return_value = [
            {"name": "Carlos Ruiz", "title": "VP Engineering", "email": None}
        ]
        hunter_fake = MagicMock(spec=HunterClient)
        hunter_fake.inferir_patron_dominio.return_value = True

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, ["VP Engineering"])

        assert len(resultado) == 1
        decisor = resultado[0]
        assert decisor.estado_correo == EstadoCorreo.INFERIDO
        assert decisor.confianza_dato == 0.55
        assert decisor.correo is None
        hunter_fake.verificar_email.assert_not_called()
        hunter_fake.inferir_patron_dominio.assert_called_once_with("acme.com")

    def test_email_rebotado_no_pasa_confianza_alta(self, empresa: Empresa):
        apollo_fake = MagicMock(spec=ApolloClient)
        apollo_fake.buscar_perfiles.return_value = [
            {"name": "Luis Gómez", "title": "CTO", "email": "luis@acme.com"}
        ]
        hunter_fake = MagicMock(spec=HunterClient)
        hunter_fake.verificar_email.return_value = {"status": "invalid", "score": 5}

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, ["CTO"])

        assert resultado[0].estado_correo == EstadoCorreo.REBOTADO
        assert resultado[0].confianza_dato == 0.10

    def test_multiples_perfiles_generan_multiples_decisores(self, empresa: Empresa):
        apollo_fake = MagicMock(spec=ApolloClient)
        apollo_fake.buscar_perfiles.return_value = [
            {"name": "Ana Torres", "title": "CTO", "email": "ana@acme.com"},
            {"name": "Luis Gómez", "title": "VP Ventas", "email": "luis@acme.com"},
        ]
        hunter_fake = MagicMock(spec=HunterClient)
        hunter_fake.verificar_email.return_value = {"status": "valid", "score": 92}

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, ["CTO", "VP Ventas"])

        assert len(resultado) == 2
        assert hunter_fake.verificar_email.call_count == 2

    def test_perfil_incompleto_sin_nombre_es_omitido(self, empresa: Empresa):
        apollo_fake = MagicMock(spec=ApolloClient)
        apollo_fake.buscar_perfiles.return_value = [
            {"name": "", "title": "CTO", "email": "sin-nombre@acme.com"}
        ]
        hunter_fake = MagicMock(spec=HunterClient)

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, ["CTO"])

        assert resultado == []
        hunter_fake.verificar_email.assert_not_called()

    def test_error_inesperado_en_apollo_no_propaga_retorna_vacio(
        self, empresa: Empresa
    ):
        """Contrato de error: nunca propagar excepciones hacia el Core."""
        apollo_fake = MagicMock(spec=ApolloClient)
        apollo_fake.buscar_perfiles.side_effect = RuntimeError("fallo simulado")
        hunter_fake = MagicMock(spec=HunterClient)

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, ["CTO"])

        assert resultado == []
        hunter_fake.verificar_email.assert_not_called()

    def test_error_inesperado_en_hunter_no_interrumpe_otros_perfiles(
        self, empresa: Empresa
    ):
        """Un fallo en Hunter para un perfil no debe tumbar el procesamiento de los demás."""
        apollo_fake = MagicMock(spec=ApolloClient)
        apollo_fake.buscar_perfiles.return_value = [
            {"name": "Ana Torres", "title": "CTO", "email": "ana@acme.com"},
            {"name": "Luis Gómez", "title": "VP Ventas", "email": "luis@acme.com"},
        ]
        hunter_fake = MagicMock(spec=HunterClient)
        hunter_fake.verificar_email.side_effect = [
            RuntimeError("fallo simulado"),
            {"status": "valid", "score": 95},
        ]

        adapter = ApolloHunterCascadaAdapter(
            apollo_client=apollo_fake, hunter_client=hunter_fake
        )
        resultado = adapter.enriquecer(empresa, ["CTO", "VP Ventas"])

        # El primer perfil falla en Hunter -> mapea a NO_RESUELTO, no se pierde.
        # El segundo perfil se procesa con normalidad.
        assert len(resultado) == 2
        estados = {d.estado_correo for d in resultado}
        assert EstadoCorreo.NO_RESUELTO in estados
        assert EstadoCorreo.VERIFICADO in estados

    def test_no_hace_llamadas_de_red_reales_end_to_end(self, empresa: Empresa):
        """
        Test de integración ligera: usa ApolloClient/HunterClient reales pero con
        requests.get/post parcheados. Garantiza que ninguna llamada real sale
        del proceso al ejecutar la cascada completa.
        """
        apollo_payload = {
            "people": [{"name": "Ana Torres", "title": "CTO", "email": "ana@acme.com"}]
        }
        hunter_payload = {"data": {"status": "accept_all", "score": 85}}

        with (
            patch(
                "requests.post", return_value=_mock_response(apollo_payload)
            ) as mock_post,
            patch(
                "requests.get", return_value=_mock_response(hunter_payload)
            ) as mock_get,
        ):
            adapter = ApolloHunterCascadaAdapter(
                apollo_client=ApolloClient(api_key="test-key"),
                hunter_client=HunterClient(api_key="test-key"),
            )
            resultado = adapter.enriquecer(empresa, ["CTO"])

        assert len(resultado) == 1
        assert resultado[0].estado_correo == EstadoCorreo.INFERIDO
        assert resultado[0].confianza_dato == 0.70
        mock_post.assert_called_once()  # Apollo: 1 llamada
        mock_get.assert_called_once()  # Hunter: 1 llamada (verify, no domain-search)
