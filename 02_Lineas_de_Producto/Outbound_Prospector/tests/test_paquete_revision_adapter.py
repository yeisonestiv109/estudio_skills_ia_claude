"""
Tests unitarios de PaqueteRevisionAdapter — persistencia de la cola de
revisión manual. Usa tmp_path (pytest) para no tocar el filesystem real del
repo ni depender de estado entre tests.
"""

from __future__ import annotations

import json

import pytest

from src.adapters.revision_manual.paquete_revision_adapter import (
    EstadoRevisionHumana,
    PaqueteRevisionAdapter,
)
from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    TamanoEmpresa,
    TierUrgencia,
    TipoTrigger,
    Trigger,
)


@pytest.fixture
def empresa() -> Empresa:
    return Empresa(
        nombre="Acme Tech SAS",
        dominio="acme.com",
        nit_o_tax_id="900123456",
        tamano=TamanoEmpresa.SME,
        vertical="Software",
    )


@pytest.fixture
def adapter(tmp_path) -> PaqueteRevisionAdapter:
    return PaqueteRevisionAdapter(ruta_archivo=tmp_path / "pendientes.json")


class TestRegistrarPendiente:
    def test_registrar_crea_archivo_y_persiste(self, adapter, empresa, tmp_path):
        paquete = adapter.registrar_pendiente(
            empresa,
            motivo="análisis semántico indeterminado",
            snippet_homepage="Somos una empresa de tecnología...",
        )

        assert paquete.empresa_nombre == "Acme Tech SAS"
        assert paquete.estado_revision == EstadoRevisionHumana.PENDIENTE
        assert (tmp_path / "pendientes.json").exists()

    def test_links_de_verificacion_incluyen_google_linkedin_rues(
        self, adapter, empresa
    ):
        paquete = adapter.registrar_pendiente(empresa, motivo="ambiguo")

        assert "Acme" in paquete.links.google or "acme" in paquete.links.google.lower()
        assert "linkedin.com" in paquete.links.linkedin
        assert "rues" in paquete.links.rues_busqueda_avanzada.lower()
        assert "900123456" in paquete.links.rues_busqueda_avanzada

    def test_link_secop_se_extrae_de_trigger_con_url(self, adapter, empresa):
        trigger_con_url = Trigger(
            empresa_id=empresa.id,
            origen=OrigenTrigger.SECOP_SOCRATA,
            nivel_confianza=NivelConfianza.ALTA,
            descripcion=(
                "Contrato SECOP #123 adjudicado. "
                "URL: https://community.secop.gov.co/Public/Tendering/x"
            ),
            tipo_trigger=TipoTrigger.CAUSA,
            tier_urgencia=TierUrgencia.TIER_0,
        )
        paquete = adapter.registrar_pendiente(
            empresa, motivo="ambiguo", triggers=[trigger_con_url]
        )

        assert paquete.links.secop_urlproceso == (
            "https://community.secop.gov.co/Public/Tendering/x"
        )

    def test_sin_triggers_secop_url_es_none(self, adapter, empresa):
        paquete = adapter.registrar_pendiente(empresa, motivo="ambiguo", triggers=[])
        assert paquete.links.secop_urlproceso is None

    def test_reregistrar_empresa_pendiente_actualiza_motivo(self, adapter, empresa):
        adapter.registrar_pendiente(empresa, motivo="motivo original")
        paquete2 = adapter.registrar_pendiente(empresa, motivo="motivo actualizado")

        assert paquete2.motivo == "motivo actualizado"

    def test_reregistrar_empresa_ya_decidida_no_sobrescribe(self, adapter, empresa):
        adapter.registrar_pendiente(empresa, motivo="motivo original")
        adapter.marcar_decision(
            str(empresa.id), EstadoRevisionHumana.CONFIRMADO_PERMITIDO
        )

        paquete2 = adapter.registrar_pendiente(empresa, motivo="motivo nuevo, ignorado")

        assert paquete2.estado_revision == EstadoRevisionHumana.CONFIRMADO_PERMITIDO
        assert paquete2.motivo == "motivo original"


class TestObtenerDecisionHumana:
    def test_empresa_nunca_registrada_retorna_none(self, adapter, empresa):
        assert adapter.obtener_decision_humana(str(empresa.id)) is None

    def test_empresa_pendiente_retorna_pendiente(self, adapter, empresa):
        adapter.registrar_pendiente(empresa, motivo="ambiguo")
        assert (
            adapter.obtener_decision_humana(str(empresa.id))
            == EstadoRevisionHumana.PENDIENTE
        )

    def test_empresa_confirmada_excluida_se_respeta(self, adapter, empresa):
        adapter.registrar_pendiente(empresa, motivo="ambiguo")
        adapter.marcar_decision(
            str(empresa.id), EstadoRevisionHumana.CONFIRMADO_EXCLUIDO
        )

        assert (
            adapter.obtener_decision_humana(str(empresa.id))
            == EstadoRevisionHumana.CONFIRMADO_EXCLUIDO
        )


class TestMarcarDecision:
    def test_marcar_decision_empresa_no_registrada_lanza_keyerror(self, adapter):
        with pytest.raises(KeyError):
            adapter.marcar_decision(
                "id-inexistente", EstadoRevisionHumana.CONFIRMADO_PERMITIDO
            )

    def test_marcar_decision_con_nota_humana_se_persiste(self, adapter, empresa):
        adapter.registrar_pendiente(empresa, motivo="ambiguo")
        adapter.marcar_decision(
            str(empresa.id),
            EstadoRevisionHumana.CONFIRMADO_PERMITIDO,
            nota_humana="Verificado en LinkedIn: es un banco regional, no compite.",
        )

        pendientes = adapter.listar_pendientes()
        assert pendientes == []  # ya no está pendiente


class TestListarPendientes:
    def test_lista_vacia_sin_registros(self, adapter):
        assert adapter.listar_pendientes() == []

    def test_solo_lista_los_pendientes_no_los_decididos(self, adapter, tmp_path):
        empresa_a = Empresa(
            nombre="A SAS", dominio="a.com", tamano=TamanoEmpresa.SME, vertical="X"
        )
        empresa_b = Empresa(
            nombre="B SAS", dominio="b.com", tamano=TamanoEmpresa.SME, vertical="X"
        )

        adapter.registrar_pendiente(empresa_a, motivo="ambiguo a")
        adapter.registrar_pendiente(empresa_b, motivo="ambiguo b")
        adapter.marcar_decision(
            str(empresa_a.id), EstadoRevisionHumana.CONFIRMADO_PERMITIDO
        )

        pendientes = adapter.listar_pendientes()
        assert len(pendientes) == 1
        assert pendientes[0].empresa_nombre == "B SAS"


class TestPersistenciaEntreInstancias:
    def test_una_nueva_instancia_lee_lo_que_persistio_otra(self, tmp_path, empresa):
        ruta = tmp_path / "pendientes.json"
        adapter1 = PaqueteRevisionAdapter(ruta_archivo=ruta)
        adapter1.registrar_pendiente(empresa, motivo="ambiguo")

        adapter2 = PaqueteRevisionAdapter(ruta_archivo=ruta)
        assert (
            adapter2.obtener_decision_humana(str(empresa.id))
            == EstadoRevisionHumana.PENDIENTE
        )

    def test_archivo_json_es_legible_y_editable_a_mano(self, tmp_path, empresa):
        ruta = tmp_path / "pendientes.json"
        adapter = PaqueteRevisionAdapter(ruta_archivo=ruta)
        adapter.registrar_pendiente(empresa, motivo="ambiguo")

        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        clave = str(empresa.id)
        assert contenido[clave]["estado_revision"] == "PENDIENTE"

        # Simula edición manual del humano en el archivo.
        contenido[clave]["estado_revision"] = "CONFIRMADO_EXCLUIDO"
        ruta.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")

        adapter2 = PaqueteRevisionAdapter(ruta_archivo=ruta)
        assert (
            adapter2.obtener_decision_humana(str(empresa.id))
            == EstadoRevisionHumana.CONFIRMADO_EXCLUIDO
        )

    def test_json_corrupto_lanza_error_en_vez_de_silenciar(self, tmp_path):
        ruta = tmp_path / "pendientes.json"
        ruta.write_text("{esto no es json valido", encoding="utf-8")

        adapter = PaqueteRevisionAdapter(ruta_archivo=ruta)
        with pytest.raises(json.JSONDecodeError):
            adapter.listar_pendientes()

    def test_archivo_inexistente_no_lanza_error(self, tmp_path):
        adapter = PaqueteRevisionAdapter(ruta_archivo=tmp_path / "no_existe.json")
        assert adapter.listar_pendientes() == []
