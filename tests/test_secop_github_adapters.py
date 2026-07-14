"""
Tests unitarios de SecopSocrataAdapter y GitHubAdapter.
Mockea requests.get — sin llamadas reales a APIs externas.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
        nombre="Acme Tech SAS",
        dominio="acme.com",
        tamano=TamanoEmpresa.MID_MARKET,
        vertical="Software",
    )


def _mock_get(json_data, status_code: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.headers = {"X-RateLimit-Remaining": "59"}
    if status_code >= 400:
        import requests
        m.raise_for_status.side_effect = requests.exceptions.HTTPError(response=m)
    else:
        m.raise_for_status.return_value = None
    return m


# ──────────────────────────────────────────────────────────────────────────
# SECOP Adapter
# ──────────────────────────────────────────────────────────────────────────
class TestSecopSocrataAdapter:

    def _contrato(self, dias_atras: int = 30, valor: str = "150000000") -> dict:
        fecha = (datetime.now(timezone.utc) - timedelta(days=dias_atras)).strftime(
            "%Y-%m-%dT%H:%M:%S.000"
        )
        return {
            "numero_contrato": "CON-2026-001",
            "proveedor_adjudicado": "ACME TECH SAS",
            "objeto_contrato": "Desarrollo de plataforma de gestión documental",
            "entidad_nombre": "Ministerio de Tecnología",
            "valor_contrato": valor,
            "fecha_adjudicacion": fecha,
        }

    def test_contrato_reciente_genera_trigger_alta(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([self._contrato(dias_atras=30)])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert isinstance(t, Trigger)
        assert t.origen == OrigenTrigger.SECOP_SOCRATA
        assert t.nivel_confianza == NivelConfianza.ALTA
        assert t.empresa_id == empresa.id
        assert t.fecha_evento is not None

    def test_contrato_antiguo_con_baja_confianza(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([self._contrato(dias_atras=400)])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter(incluir_baja_confianza=True)
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.BAJA

    def test_contrato_antiguo_omitido_por_defecto(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([self._contrato(dias_atras=400)])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter(incluir_baja_confianza=False)
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_sin_contratos_retorna_vacio(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        with patch("requests.get", return_value=_mock_get([])):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_timeout_no_propaga_al_core(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
        import requests

        with patch("requests.get", side_effect=requests.exceptions.Timeout):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_http_error_no_propaga(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get({}, status_code=503)
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_descripcion_incluye_entidad_y_valor(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([self._contrato(dias_atras=10, valor="500000000")])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert "Ministerio de Tecnología" in triggers[0].descripcion
        assert "500" in triggers[0].descripcion

    def test_nombre_vacio_retorna_vacio(self):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        emp = Empresa(
            nombre="  ",
            dominio="sin-nombre.co",
            tamano=TamanoEmpresa.SME,
            vertical="Tech",
        )
        adapter = SecopSocrataAdapter()
        triggers = adapter.obtener_triggers(emp)
        assert triggers == []

    def test_contrato_medio_plazo_genera_media_confianza(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([self._contrato(dias_atras=200)])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.MEDIA


# ──────────────────────────────────────────────────────────────────────────
# GitHub Adapter
# ──────────────────────────────────────────────────────────────────────────
class TestGitHubAdapter:

    def _repo(self, name: str, lang: str = "Python", dias_atras: int = 5,
              issues: int = 3, archived: bool = False, fork: bool = False) -> dict:
        pushed = (datetime.now(timezone.utc) - timedelta(days=dias_atras)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return {
            "name": name,
            "language": lang,
            "pushed_at": pushed,
            "open_issues_count": issues,
            "archived": archived,
            "fork": fork,
        }

    def _mock_org_repos(self, repos: list[dict]) -> MagicMock:
        """Primer GET (org/repos) exitoso, segundo GET no llamado."""
        return _mock_get(repos)

    def test_repos_con_match_icp_generan_trigger_media(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [
            self._repo("backend-api", lang="Python"),
            self._repo("infra-aws", lang="Go"),
        ]
        with patch("requests.get", return_value=_mock_get(repos)):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python", "AWS"])
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        t = triggers[0]
        assert t.origen == OrigenTrigger.GITHUB
        assert t.nivel_confianza == NivelConfianza.MEDIA
        assert t.empresa_id == empresa.id
        assert "Python" in t.descripcion or "python" in t.descripcion.lower()

    def test_repos_sin_match_icp_no_generan_trigger(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("website", lang="PHP")]
        with patch("requests.get", return_value=_mock_get(repos)):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python", "AWS"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_org_no_encontrada_retorna_vacio(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter

        # 404 en org → fallback a user → 404 también
        with patch("requests.get", return_value=_mock_get({}, status_code=404)):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_rate_limit_403_retorna_vacio_no_lanza(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter

        m = MagicMock()
        m.status_code = 403
        m.headers = {"X-RateLimit-Remaining": "0"}

        with patch("requests.get", return_value=m):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_timeout_no_propaga_al_core(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter
        import requests

        with patch("requests.get", side_effect=requests.exceptions.Timeout):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_repos_archivados_y_forks_ignorados(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [
            self._repo("old-repo", lang="Python", archived=True),
            self._repo("forked-repo", lang="Python", fork=True),
        ]
        with patch("requests.get", return_value=_mock_get(repos)):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_trigger_tiene_fecha_evento(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("api", lang="Python", dias_atras=7)]
        with patch("requests.get", return_value=_mock_get(repos)):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers[0].fecha_evento is not None
        assert isinstance(triggers[0].fecha_evento, datetime)

    def test_extraccion_org_desde_dominio(self):
        from src.adapters.triggers.github_adapter import _extraer_org_name
        assert _extraer_org_name("acme.com") == "acme"
        assert _extraer_org_name("my-company.co.uk") == "my-company"
        assert _extraer_org_name("api.acme.io") == "api"
        assert _extraer_org_name("https://acme.com") == "acme"

    def test_enum_github_existe_en_origen_trigger(self):
        """Verifica que GITHUB fue añadido al Enum del Core."""
        assert OrigenTrigger.GITHUB.value == "GITHUB"
