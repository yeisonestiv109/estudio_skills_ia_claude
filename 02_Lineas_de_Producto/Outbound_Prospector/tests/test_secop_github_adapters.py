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
        """
        Esquema REAL del dataset jbjy-vk9h (confirmado por ingeniería inversa
        del endpoint, 2026-07) — reemplaza los nombres de columna anteriores
        que no existen en SECOP II (fecha_adjudicacion, entidad_nombre,
        objeto_contrato, valor_contrato, numero_contrato/id_proceso).
        """
        fecha = (datetime.now(timezone.utc) - timedelta(days=dias_atras)).strftime(
            "%Y-%m-%dT%H:%M:%S.000"
        )
        return {
            "id_contrato": "CON-2026-001",
            "proveedor_adjudicado": "ACME TECH SAS",
            "objeto_del_contrato": "Desarrollo de plataforma de gestión documental",
            "nombre_entidad": "Ministerio de Tecnología",
            "valor_del_contrato": valor,
            "fecha_de_firma": fecha,
            "es_pyme": "Sí",
            "urlproceso": {"url": "https://community.secop.gov.co/Public/Tendering/x"},
            "codigo_de_categoria_principal": "V1.81112006",
            "direcci_n_de_ejecuci_n_del_contrato": "Calle 1\nBogotá\nCOLOMBIA",
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
        """
        Regresión de causa raíz (full scan de LIKE '%...%'): un Timeout ahora
        reintenta _MAX_INTENTOS veces antes de rendirse. Se mockea
        time.sleep para no esperar los backoffs reales en el test.
        """
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
        import requests

        with (
            patch("requests.get", side_effect=requests.exceptions.Timeout),
            patch("src.adapters.triggers.secop_adapter.time.sleep"),
        ):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_timeout_reintenta_hasta_max_intentos(self, empresa: Empresa):
        """Verifica que un Timeout persistente agota exactamente _MAX_INTENTOS llamadas."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
        import requests

        with (
            patch("requests.get", side_effect=requests.exceptions.Timeout) as mock_get,
            patch("src.adapters.triggers.secop_adapter.time.sleep"),
        ):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []
        assert mock_get.call_count == 3

    def test_timeout_luego_exito_recupera_datos(self, empresa: Empresa):
        """Un Timeout en el primer intento no debe perder la señal si el reintento funciona."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
        import requests

        resp_ok = _mock_get([self._contrato(dias_atras=10)])
        with (
            patch(
                "requests.get",
                side_effect=[requests.exceptions.Timeout(), resp_ok],
            ),
            patch("src.adapters.triggers.secop_adapter.time.sleep"),
        ):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1

    def test_http_error_no_propaga(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get({}, status_code=503)
        with (
            patch("requests.get", return_value=resp),
            patch("src.adapters.triggers.secop_adapter.time.sleep"),
        ):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_503_reintenta_y_luego_tiene_exito(self, empresa: Empresa):
        """HTTP 503 (reintentable) seguido de un 200 debe recuperar los datos."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp_503 = _mock_get({}, status_code=503)
        resp_ok = _mock_get([self._contrato(dias_atras=10)])
        with (
            patch("requests.get", side_effect=[resp_503, resp_ok]),
            patch("src.adapters.triggers.secop_adapter.time.sleep"),
        ):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1

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

    def test_contrato_de_120_dias_es_media_no_alta(self, empresa: Empresa):
        """
        Alineación con el decay de CAUSA (_DIAS_ALTA=90, antes 180): un
        contrato de 120 días ya NO es ALTA/TIER_0 (habría puntuado 0 en el
        scoring), sino MEDIA/TIER_2. Fija la nueva frontera de 90 días.
        """
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
        from src.core.domain.models import TierUrgencia

        resp = _mock_get([self._contrato(dias_atras=120)])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.MEDIA
        assert triggers[0].tier_urgencia == TierUrgencia.TIER_2

    def test_contrato_de_80_dias_sigue_siendo_alta_tier0(self, empresa: Empresa):
        """Dentro de la ventana de 90 días → ALTA/TIER_0 (sangrado activo)."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
        from src.core.domain.models import TierUrgencia

        resp = _mock_get([self._contrato(dias_atras=80)])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.ALTA
        assert triggers[0].tier_urgencia == TierUrgencia.TIER_0

    def test_app_token_explicito_se_envia_en_header(self, empresa: Empresa):
        """Con app_token explícito, la request debe incluir X-App-Token."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([])
        with patch("requests.get", return_value=resp) as mock_get:
            adapter = SecopSocrataAdapter(app_token="test-token-123")
            adapter.obtener_triggers(empresa)

        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["headers"]["X-App-Token"] == "test-token-123"

    def test_app_token_desde_env_se_envia_en_header(
        self, empresa: Empresa, monkeypatch
    ):
        """Sin app_token explícito, debe leer SECOP_APP_TOKEN del entorno."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        monkeypatch.setenv("SECOP_APP_TOKEN", "env-token-456")
        resp = _mock_get([])
        with patch("requests.get", return_value=resp) as mock_get:
            adapter = SecopSocrataAdapter()
            adapter.obtener_triggers(empresa)

        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["headers"]["X-App-Token"] == "env-token-456"

    def test_sin_app_token_no_incluye_header(self, empresa: Empresa, monkeypatch):
        """Sin token disponible (ni explícito ni en entorno), el header no se envía."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        monkeypatch.delenv("SECOP_APP_TOKEN", raising=False)
        resp = _mock_get([])
        with patch("requests.get", return_value=resp) as mock_get:
            adapter = SecopSocrataAdapter(app_token=None)
            adapter.obtener_triggers(empresa)

        call_kwargs = mock_get.call_args.kwargs
        assert "X-App-Token" not in call_kwargs["headers"]

    def test_order_usa_fecha_de_firma_no_fecha_adjudicacion(self, empresa: Empresa):
        """
        Regresión de la causa raíz del HTTP 400: 'fecha_adjudicacion' no
        existe en el esquema real de jbjy-vk9h. El $order debe usar
        'fecha_de_firma', la columna que sí existe.
        """
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([])
        with patch("requests.get", return_value=resp) as mock_get:
            adapter = SecopSocrataAdapter()
            adapter.obtener_triggers(empresa)

        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["params"]["$order"] == "fecha_de_firma DESC"
        assert "fecha_adjudicacion" not in call_kwargs["params"]["$order"]

    def test_consulta_usa_q_no_where_like(self, empresa: Empresa):
        """
        Fix de rendimiento (causa raíz del timeout, confirmado en vivo:
        ~10.5s con `$where LIKE '%...%'` vs ~0.5-1s con `$q`). La consulta
        primaria debe usar `$q` (full-text indexado), no `$where` con
        wildcard inicial (full scan).
        """
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([])
        with patch("requests.get", return_value=resp) as mock_get:
            adapter = SecopSocrataAdapter()
            adapter.obtener_triggers(empresa)

        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["params"]["$q"] == empresa.nombre
        assert "$where" not in call_kwargs["params"]

    def test_filtro_verificacion_descarta_falsos_positivos_de_q(self, empresa: Empresa):
        """
        `$q` es full-text fuzzy y puede traer candidatos que NO son un match
        real del nombre buscado (ej. "$q=Acme Tech SAS" trae también
        "PAVIMENTOS ACM SAS"). El filtro de verificación en Python debe
        descartar esos falsos positivos antes de convertirlos en Trigger.
        """
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        contrato_real = self._contrato(dias_atras=10)
        contrato_falso_positivo = self._contrato(dias_atras=5)
        contrato_falso_positivo["proveedor_adjudicado"] = "PAVIMENTOS ACM SAS"

        resp = _mock_get([contrato_falso_positivo, contrato_real])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert "CON-2026-001" in triggers[0].descripcion

    def test_todos_falsos_positivos_retorna_vacio(self, empresa: Empresa):
        """Si ningún candidato de `$q` supera el filtro de verificación, retorna []."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        contrato_falso_positivo = self._contrato(dias_atras=5)
        contrato_falso_positivo["proveedor_adjudicado"] = "PAVIMENTOS ACM SAS"

        resp = _mock_get([contrato_falso_positivo])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_descripcion_incluye_url_proceso_y_unspsc(self, empresa: Empresa):
        """Los campos nuevos (urlproceso, UNSPSC, dirección) deben aparecer en la descripción."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([self._contrato(dias_atras=10)])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        descripcion = triggers[0].descripcion
        assert "community.secop.gov.co" in descripcion
        assert "V1.81112006" in descripcion
        assert "Bogotá" in descripcion

    def test_estimar_tamano_es_pyme_si_retorna_sme(self, empresa: Empresa):
        """Implementa PuertoEstimadorTamano: es_pyme='Sí' → TamanoEmpresa.SME."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
        from src.core.domain.models import OrigenTrigger, TamanoEmpresa

        contrato = self._contrato(dias_atras=10)
        contrato["es_pyme"] = "Sí"
        resp = _mock_get([contrato])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is not None
        assert estimacion.tamano_estimado == TamanoEmpresa.SME
        assert estimacion.origen == OrigenTrigger.SECOP_SOCRATA

    def test_estimar_tamano_es_pyme_no_retorna_mid_market(self, empresa: Empresa):
        """es_pyme='No' → TamanoEmpresa.MID_MARKET."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter
        from src.core.domain.models import TamanoEmpresa

        contrato = self._contrato(dias_atras=10)
        contrato["es_pyme"] = "No"
        resp = _mock_get([contrato])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is not None
        assert estimacion.tamano_estimado == TamanoEmpresa.MID_MARKET

    def test_estimar_tamano_sin_contratos_retorna_none(self, empresa: Empresa):
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is None

    def test_estimar_tamano_sin_es_pyme_retorna_none(self, empresa: Empresa):
        """Silencio válido: si el contrato no reporta es_pyme, no forzar opinión."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        contrato = self._contrato(dias_atras=10)
        contrato.pop("es_pyme", None)
        resp = _mock_get([contrato])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            estimacion = adapter.estimar_tamano(empresa)

        assert estimacion is None

    def test_obtener_triggers_y_estimar_tamano_usan_cache_una_sola_llamada_http(
        self, empresa: Empresa
    ):
        """
        Cache por instancia: llamar obtener_triggers() y luego estimar_tamano()
        sobre la MISMA empresa no debe duplicar la llamada HTTP.
        """
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get([self._contrato(dias_atras=10)])
        with patch("requests.get", return_value=resp) as mock_get:
            adapter = SecopSocrataAdapter()
            adapter.obtener_triggers(empresa)
            adapter.estimar_tamano(empresa)

        assert mock_get.call_count == 1

    def test_fallback_fecha_de_inicio_del_contrato_cuando_no_hay_fecha_de_firma(
        self, empresa: Empresa
    ):
        """Sin fecha_de_firma, debe usar fecha_de_inicio_del_contrato como fallback."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        fecha = (datetime.now(timezone.utc) - timedelta(days=20)).strftime(
            "%Y-%m-%dT%H:%M:%S.000"
        )
        contrato = {
            "id_contrato": "CON-2026-002",
            "proveedor_adjudicado": "ACME TECH SAS",
            "objeto_del_contrato": "Consultoría",
            "nombre_entidad": "Alcaldía de Bogotá",
            "valor_del_contrato": "80000000",
            "fecha_de_inicio_del_contrato": fecha,
        }
        resp = _mock_get([contrato])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].fecha_evento is not None
        assert triggers[0].nivel_confianza == NivelConfianza.ALTA

    def test_fallback_descripcion_del_proceso_cuando_no_hay_objeto_del_contrato(
        self, empresa: Empresa
    ):
        """Sin objeto_del_contrato, debe usar descripcion_del_proceso como fallback."""
        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        fecha = (datetime.now(timezone.utc) - timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M:%S.000"
        )
        contrato = {
            "id_contrato": "CON-2026-003",
            "proveedor_adjudicado": "ACME TECH SAS",
            "descripcion_del_proceso": "Suministro de equipos de cómputo",
            "nombre_entidad": "Ministerio de TIC",
            "valor_del_contrato": "30000000",
            "fecha_de_firma": fecha,
        }
        resp = _mock_get([contrato])
        with patch("requests.get", return_value=resp):
            adapter = SecopSocrataAdapter()
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert "Suministro de equipos de cómputo" in triggers[0].descripcion

    def test_403_con_token_emite_warning_autoexplicativo(
        self, empresa: Empresa, caplog
    ):
        """
        Hallazgo 1: un token 403 (Socrata rechaza "Clave API" en vez de
        "Token de la aplicación") debe producir un warning claro para el
        operador, no solo un log genérico de HTTP error.
        """
        import logging

        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get({}, status_code=403)
        with (
            caplog.at_level(logging.WARNING),
            patch("requests.get", return_value=resp),
        ):
            adapter = SecopSocrataAdapter(app_token="token-de-escritura-invalido")
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []
        mensajes = " ".join(r.message for r in caplog.records)
        assert "Token de la aplicación" in mensajes
        assert "Clave API" in mensajes

    def test_403_sin_token_no_emite_mensaje_de_token(self, empresa: Empresa, caplog):
        """Un 403 sin token configurado no es un problema de tipo de token."""
        import logging

        from src.adapters.triggers.secop_adapter import SecopSocrataAdapter

        resp = _mock_get({}, status_code=403)
        with (
            caplog.at_level(logging.WARNING),
            patch("requests.get", return_value=resp),
        ):
            adapter = SecopSocrataAdapter(app_token=None)
            adapter.obtener_triggers(empresa)

        mensajes = " ".join(r.message for r in caplog.records)
        assert "Token de la aplicación" not in mensajes


# ──────────────────────────────────────────────────────────────────────────
# GitHub Adapter
# ──────────────────────────────────────────────────────────────────────────
class TestGitHubAdapter:
    def _repo(
        self,
        name: str,
        lang: str = "Python",
        dias_atras: int = 5,
        issues: int = 3,
        archived: bool = False,
        fork: bool = False,
    ) -> dict:
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

    def _mock_perfil(self, blog: str = "https://acme.com") -> MagicMock:
        """
        Perfil de org/usuario de GitHub para la verificación de propiedad
        (FIX #4 — anti-colisión de nombre). El `blog` es el sitio web que la
        org declara; por defecto coincide con el dominio de la empresa fixture
        (acme.com) para que la verificación pase.
        """
        return _mock_get({"blog": blog, "login": "acme"})

    def test_repos_con_match_icp_generan_trigger_media(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [
            self._repo("backend-api", lang="Python"),
            self._repo("infra-aws", lang="Go"),
        ]
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), self._mock_perfil()],
        ):
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
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), self._mock_perfil()],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python", "AWS"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_javascript_no_colisiona_con_icp_java(self, empresa: Empresa):
        """
        Regresión bug de raíz: "java" es subcadena de "javascript". Antes del
        fix por palabra completa, un repo en JavaScript matcheaba
        falsamente la tecnología ICP "Java" (lenguaje distinto).
        """
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("frontend-app", lang="JavaScript")]
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), self._mock_perfil()],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Java"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_java_real_sigue_generando_match(self, empresa: Empresa):
        """El fix no debe romper la detección legítima de 'Java' como lenguaje."""
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("backend-service", lang="Java")]
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), self._mock_perfil()],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Java"])
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].nivel_confianza == NivelConfianza.MEDIA

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
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), self._mock_perfil()],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_trigger_tiene_fecha_evento(self, empresa: Empresa):
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("api", lang="Python", dias_atras=7)]
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), self._mock_perfil()],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers[0].fecha_evento is not None
        assert isinstance(triggers[0].fecha_evento, datetime)

    # ── FIX #4: verificación de propiedad de la org (anti-colisión de nombre) ──
    def test_org_cuyo_blog_coincide_con_dominio_genera_trigger(self, empresa: Empresa):
        """
        (a) La org de GitHub declara un sitio web (blog) cuyo dominio
        registrable coincide con el de la empresa → la org SÍ le pertenece,
        se aceptan sus repos y se genera trigger.
        """
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("backend-api", lang="Python")]
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), self._mock_perfil("https://www.acme.com/")],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert len(triggers) == 1
        assert triggers[0].origen == OrigenTrigger.GITHUB

    def test_org_homonima_con_blog_de_otro_dominio_no_genera_trigger(self):
        """
        (b) Caso real de la colisión: empresa forbes.co (Forbes Colombia) vs.
        org GitHub `forbes` cuyo sitio web declarado es forbes.com (Forbes
        EE.UU.). Los dominios registrables NO coinciden → NO se confía en esa
        org → sin trigger.
        """
        from src.adapters.triggers.github_adapter import GitHubAdapter

        empresa_forbes_co = Empresa(
            nombre="Forbes Colombia",
            dominio="forbes.co",
            tamano=TamanoEmpresa.SME,
            vertical="Medios",
        )
        repos = [self._repo("data-platform", lang="Python")]
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), self._mock_perfil("https://www.forbes.com")],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa_forbes_co)

        assert triggers == []

    def test_org_sin_blog_declarado_no_genera_trigger(self, empresa: Empresa):
        """
        (c) La org no declara sitio web (blog vacío/ausente): no es verificable
        → fail-closed, sin trigger.
        """
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("backend-api", lang="Python")]
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), _mock_get({"blog": "", "login": "acme"})],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_perfil_404_no_verificable_no_genera_trigger(self, empresa: Empresa):
        """(d) Si el perfil de la org no se puede leer (404) → sin trigger."""
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("backend-api", lang="Python")]
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), _mock_get({}, status_code=404)],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_perfil_403_rate_limit_no_genera_trigger(self, empresa: Empresa):
        """(d bis) Un 403 (rate limit / prohibido) al leer el perfil → sin trigger."""
        from src.adapters.triggers.github_adapter import GitHubAdapter

        repos = [self._repo("backend-api", lang="Python")]
        perfil_403 = MagicMock()
        perfil_403.status_code = 403
        perfil_403.headers = {"X-RateLimit-Remaining": "0"}
        with patch(
            "requests.get",
            side_effect=[_mock_get(repos), perfil_403],
        ):
            adapter = GitHubAdapter(tecnologias_objetivo=["Python"])
            triggers = adapter.obtener_triggers(empresa)

        assert triggers == []

    def test_extraccion_org_desde_dominio(self):
        from src.adapters.triggers.github_adapter import _extraer_org_name

        assert _extraer_org_name("acme.com") == "acme"
        assert _extraer_org_name("my-company.co.uk") == "my-company"
        assert _extraer_org_name("api.acme.io") == "api"
        assert _extraer_org_name("https://acme.com") == "acme"

    def test_enum_github_existe_en_origen_trigger(self):
        """Verifica que GITHUB fue añadido al Enum del Core."""
        assert OrigenTrigger.GITHUB.value == "GITHUB"
