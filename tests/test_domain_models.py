"""
Pruebas unitarias del Core de Dominio — El Prospector.

Cubren los contratos de seguridad definidos en:
    10-Memoria_Consolidada/modelos_dominio_core.md (v3.0)

Todas las pruebas son deterministas, no requieren red, LLM ni base de datos.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.core.domain.models import (
    BaseLegal,
    CategoriaEmpresa,
    Decisor,
    Empresa,
    EstadoCorreo,
    ManifiestoICP,
    NivelConfianza,
    OrigenTrigger,
    ProspectoCalificado,
    Seniority,
    TamanoEmpresa,
    Trigger,
)
from src.core.domain.policies import (
    AdapterRoutingPolicy,
    TriggerAggregationPolicy,
    UmbralCalidadDecisor,
)
from src.core.ports.interfaces import PuertoEnriquecedorContactos


# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------
@pytest.fixture
def empresa_valida() -> Empresa:
    return Empresa(
        nombre="Acme SaaS",
        dominio="acme.com",
        tamano=TamanoEmpresa.MID_MARKET,
        vertical="Retail",
    )


@pytest.fixture
def manifesto_base() -> dict:
    """Datos mínimos para construir un ManifiestoICP válido."""
    return dict(
        pain_es_accionable=False,
        anclaje_tecnologico=["AWS"],
        categoria_empresa=CategoriaEmpresa.SAAS_B2B_HORIZONTAL,
        vertical="SaaS",
        cargos_decisores=["CTO"],
        tamano_empresa=TamanoEmpresa.SME,
        geografia="CO",
        base_legal=BaseLegal.CONSENTIMIENTO_EXPLICITO,
    )


# ---------------------------------------------------------------------------
# Bloque 1: Inmutabilidad de Empresa (frozen=True)
# ---------------------------------------------------------------------------
class TestEmpresaInmutabilidad:
    def test_empresa_no_permite_mutacion_de_nombre(self, empresa_valida: Empresa):
        """Empresa es un Value Object inmutable. Cualquier mutación debe fallar."""
        with pytest.raises(ValidationError):
            empresa_valida.nombre = "Otro Nombre"

    def test_empresa_no_permite_mutacion_de_dominio(self, empresa_valida: Empresa):
        with pytest.raises(ValidationError):
            empresa_valida.dominio = "otro.com"

    def test_empresa_no_permite_agregar_campo_nuevo(self, empresa_valida: Empresa):
        with pytest.raises((ValidationError, TypeError)):
            empresa_valida.campo_inexistente = "valor"  # type: ignore[attr-defined]

    def test_empresa_construida_correctamente(self, empresa_valida: Empresa):
        """Verificación de construcción válida sin efectos colaterales."""
        assert empresa_valida.nombre == "Acme SaaS"
        assert empresa_valida.dominio == "acme.com"
        assert empresa_valida.pais == "CO"  # valor por defecto
        assert isinstance(empresa_valida.fecha_captura, datetime)


# ---------------------------------------------------------------------------
# Bloque 2: Gate B — ManifiestoICP.anclaje_tecnologico vacío (min_length=1)
# ---------------------------------------------------------------------------
class TestGateBAnclajeTecnologico:
    def test_gate_b_bloquea_lista_vacia(self, manifesto_base: dict):
        """Lista vacía debe levantar ValidationError antes de llegar al Gate B."""
        manifesto_base["anclaje_tecnologico"] = []
        with pytest.raises(ValidationError) as exc_info:
            ManifiestoICP(**manifesto_base)
        # Confirmamos que el error es sobre el campo correcto
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("anclaje_tecnologico",) for e in errors)

    def test_gate_b_pasa_con_un_elemento(self, manifesto_base: dict):
        """Un solo elemento debe ser suficiente para pasar el Gate B."""
        manifesto_base["anclaje_tecnologico"] = ["Python"]
        manifesto = ManifiestoICP(**manifesto_base)
        assert manifesto.anclaje_tecnologico == ["Python"]

    def test_gate_b_pasa_con_multiples_tecnologias(self, manifesto_base: dict):
        manifesto_base["anclaje_tecnologico"] = ["Python", "FastAPI", "PostgreSQL"]
        manifesto = ManifiestoICP(**manifesto_base)
        assert len(manifesto.anclaje_tecnologico) == 3


# ---------------------------------------------------------------------------
# Bloque 3: Gate A — Estado incoherente pain_es_accionable + dolor_operativo
# ---------------------------------------------------------------------------
class TestGateACoherenciaDolor:
    def test_gate_a_bloquea_pain_true_sin_dolor(self, manifesto_base: dict):
        """pain_es_accionable=True sin dolor_operativo es estado imposible."""
        manifesto_base["pain_es_accionable"] = True
        # dolor_operativo ausente (None por defecto)
        with pytest.raises(ValidationError) as exc_info:
            ManifiestoICP(**manifesto_base)
        assert "pain_es_accionable" in str(exc_info.value) or "dolor_operativo" in str(
            exc_info.value
        )

    def test_gate_a_pasa_pain_true_con_dolor(self, manifesto_base: dict):
        """Con dolor_operativo poblado, el estado es coherente y debe pasar."""
        manifesto_base["pain_es_accionable"] = True
        manifesto_base["dolor_operativo"] = "No entregan a tiempo por deuda técnica"
        m = ManifiestoICP(**manifesto_base)
        assert m.pain_es_accionable is True
        assert m.dolor_operativo is not None

    def test_gate_a_pasa_pain_false_sin_dolor(self, manifesto_base: dict):
        """pain_es_accionable=False con dolor_operativo=None es válido."""
        manifesto_base["pain_es_accionable"] = False
        m = ManifiestoICP(**manifesto_base)
        assert m.pain_es_accionable is False
        assert m.dolor_operativo is None


# ---------------------------------------------------------------------------
# Bloque 4: Contratos de Decisor (confianza_dato, EmailStr, enums)
# ---------------------------------------------------------------------------
class TestDecisorContratos:
    def _base_decisor(self, **kwargs) -> dict:
        base = dict(
            empresa_id=uuid.uuid4(),
            nombre="Ana Torres",
            cargo_original="Chief Technology Officer",
            cargo_normalizado="CTO",
            seniority=Seniority.C_LEVEL,
            confianza_dato=0.85,
        )
        base.update(kwargs)
        return base

    def test_confianza_dato_rechaza_mayor_que_uno(self):
        with pytest.raises(ValidationError):
            Decisor(**self._base_decisor(confianza_dato=1.5))

    def test_confianza_dato_rechaza_negativo(self):
        with pytest.raises(ValidationError):
            Decisor(**self._base_decisor(confianza_dato=-0.1))

    def test_confianza_dato_acepta_extremos_validos(self):
        Decisor(**self._base_decisor(confianza_dato=0.0))
        Decisor(**self._base_decisor(confianza_dato=1.0))

    def test_correo_ausente_es_valido(self):
        d = Decisor(**self._base_decisor())
        assert d.correo is None
        assert d.estado_correo == EstadoCorreo.NO_RESUELTO

    def test_correo_invalido_rechazado(self):
        with pytest.raises(ValidationError):
            Decisor(**self._base_decisor(correo="no-es-un-email"))

    def test_correo_valido_aceptado(self):
        d = Decisor(**self._base_decisor(correo="ana@acme.com"))
        assert str(d.correo) == "ana@acme.com"


# ---------------------------------------------------------------------------
# Bloque 5: AdapterRoutingPolicy — Enrutamiento correcto
# ---------------------------------------------------------------------------
class TestAdapterRoutingPolicy:
    policy = AdapterRoutingPolicy()

    def _manifesto(
        self, categoria: CategoriaEmpresa, es_gov: bool = False
    ) -> ManifiestoICP:
        return ManifiestoICP(
            pain_es_accionable=False,
            anclaje_tecnologico=["Python"],
            categoria_empresa=categoria,
            vertical="Tech",
            es_gov_facing=es_gov,
            cargos_decisores=["CTO"],
            tamano_empresa=TamanoEmpresa.MID_MARKET,
            geografia="CO",
            base_legal=BaseLegal.CONSENTIMIENTO_EXPLICITO,
        )

    def test_google_alerts_siempre_activo(self):
        for cat in CategoriaEmpresa:
            result = self.policy.resolver(self._manifesto(cat))
            assert OrigenTrigger.GOOGLE_ALERTS in result, (
                f"GOOGLE_ALERTS ausente para {cat}"
            )

    def test_fintech_regulado_desactiva_wappalyzer_y_theirstack(self):
        result = self.policy.resolver(
            self._manifesto(CategoriaEmpresa.REGULADO_FINTECH)
        )
        assert OrigenTrigger.WAPPALYZER not in result
        assert OrigenTrigger.THEIRSTACK not in result

    def test_agencia_it_gov_facing_activa_todos(self):
        result = self.policy.resolver(
            self._manifesto(CategoriaEmpresa.AGENCIA_IT, es_gov=True)
        )
        # AGENCIA_IT gov-facing: Google Alerts + TheirStack + SECOP + Wappalyzer + GitHub
        assert set(result) == {
            OrigenTrigger.GOOGLE_ALERTS,
            OrigenTrigger.THEIRSTACK,
            OrigenTrigger.SECOP_SOCRATA,
            OrigenTrigger.WAPPALYZER,
            OrigenTrigger.GITHUB,
        }

    def test_saas_sin_gov_no_activa_secop(self):
        result = self.policy.resolver(
            self._manifesto(CategoriaEmpresa.SAAS_B2B_HORIZONTAL)
        )
        assert OrigenTrigger.SECOP_SOCRATA not in result


# ---------------------------------------------------------------------------
# Bloque 6: TriggerAggregationPolicy — Cruce de señales
# ---------------------------------------------------------------------------
class TestTriggerAggregationPolicy:
    policy = TriggerAggregationPolicy()

    def _trigger(self, origen: OrigenTrigger, dias_atras: int = 10) -> Trigger:
        return Trigger(
            empresa_id=uuid.uuid4(),
            origen=origen,
            nivel_confianza=NivelConfianza.ALTA,
            descripcion="señal de prueba",
            fecha_evento=datetime.now(timezone.utc) - timedelta(days=dias_atras),
        )

    def test_dos_origenes_distintos_fresco_pasa(self):
        t1 = self._trigger(OrigenTrigger.GOOGLE_ALERTS, dias_atras=5)
        t2 = self._trigger(OrigenTrigger.THEIRSTACK, dias_atras=30)
        assert self.policy.evaluar([t1, t2]) is True

    def test_mismo_origen_dos_veces_falla(self):
        t1 = self._trigger(OrigenTrigger.GOOGLE_ALERTS, dias_atras=5)
        t2 = self._trigger(OrigenTrigger.GOOGLE_ALERTS, dias_atras=10)
        assert self.policy.evaluar([t1, t2]) is False

    def test_un_solo_trigger_falla(self):
        t1 = self._trigger(OrigenTrigger.GOOGLE_ALERTS, dias_atras=5)
        assert self.policy.evaluar([t1]) is False

    def test_senal_obsoleta_mas_de_45_dias_falla(self):
        t1 = self._trigger(OrigenTrigger.GOOGLE_ALERTS, dias_atras=50)
        t2 = self._trigger(OrigenTrigger.THEIRSTACK, dias_atras=60)
        assert self.policy.evaluar([t1, t2]) is False

    def test_umbral_dinamico_un_adaptador_activo(self):
        """Si solo 1 adaptador estaba activo, 1 trigger con señal fresca es suficiente."""
        t1 = self._trigger(OrigenTrigger.GOOGLE_ALERTS, dias_atras=5)
        assert (
            self.policy.evaluar([t1], adaptadores_activos=[OrigenTrigger.GOOGLE_ALERTS])
            is True
        )

    def test_lista_vacia_de_triggers_falla(self):
        assert self.policy.evaluar([]) is False


# ---------------------------------------------------------------------------
# Bloque 7: PuertoEnriquecedorContactos — Contrato ABC (Motor 3)
# ---------------------------------------------------------------------------
class TestPuertoEnriquecedorContactosABC:
    def test_no_se_puede_instanciar_directamente(self):
        """El puerto es abstracto; el Core nunca instancia adaptadores directamente."""
        with pytest.raises(TypeError):
            PuertoEnriquecedorContactos()  # type: ignore[abstract]

    def test_implementacion_concreta_respeta_firma_stateless(
        self, empresa_valida: Empresa
    ):
        """
        Una implementación concreta debe aceptar (empresa, cargos) y retornar
        list[Decisor]. La firma es stateless: no requiere contexto de job.
        """

        class _EnriquecedorFake(PuertoEnriquecedorContactos):
            def enriquecer(self, empresa: Empresa, cargos: list[str]) -> list[Decisor]:
                return [
                    Decisor(
                        empresa_id=empresa.id,
                        nombre="Ana Torres",
                        cargo_original=cargos[0],
                        cargo_normalizado="CTO",
                        seniority=Seniority.C_LEVEL,
                        confianza_dato=0.9,
                        estado_correo=EstadoCorreo.VERIFICADO,
                    )
                ]

        adaptador = _EnriquecedorFake()
        resultado = adaptador.enriquecer(empresa_valida, ["CTO"])
        assert len(resultado) == 1
        assert resultado[0].estado_correo == EstadoCorreo.VERIFICADO

    def test_implementacion_puede_retornar_lista_vacia_sin_lanzar(
        self, empresa_valida: Empresa
    ):
        """Contrato de error: sin decisores resolubles → [] es un resultado válido."""

        class _EnriquecedorSinResultados(PuertoEnriquecedorContactos):
            def enriquecer(self, empresa: Empresa, cargos: list[str]) -> list[Decisor]:
                return []

        adaptador = _EnriquecedorSinResultados()
        assert adaptador.enriquecer(empresa_valida, ["CTO"]) == []


# ---------------------------------------------------------------------------
# Bloque 8: ProspectoCalificado — Contrato de transición Motor 2 → Motor 3
# ---------------------------------------------------------------------------
class TestProspectoCalificado:
    def _trigger(self, empresa_id: uuid.UUID) -> Trigger:
        return Trigger(
            empresa_id=empresa_id,
            origen=OrigenTrigger.GOOGLE_ALERTS,
            nivel_confianza=NivelConfianza.ALTA,
            descripcion="Nuevo CTO confirmado",
            fecha_evento=datetime.now(timezone.utc) - timedelta(days=5),
        )

    def test_construccion_valida(self, empresa_valida: Empresa, manifesto_base: dict):
        manifiesto = ManifiestoICP(**manifesto_base)
        trigger = self._trigger(empresa_valida.id)
        prospecto = ProspectoCalificado(
            empresa=empresa_valida, triggers=[trigger], manifiesto=manifiesto
        )
        assert prospecto.empresa == empresa_valida
        assert prospecto.triggers == [trigger]
        assert prospecto.manifiesto == manifiesto

    def test_es_inmutable(self, empresa_valida: Empresa, manifesto_base: dict):
        manifiesto = ManifiestoICP(**manifesto_base)
        trigger = self._trigger(empresa_valida.id)
        prospecto = ProspectoCalificado(
            empresa=empresa_valida, triggers=[trigger], manifiesto=manifiesto
        )
        with pytest.raises(ValidationError):
            prospecto.empresa = empresa_valida  # type: ignore[misc]

    def test_requiere_al_menos_un_trigger(
        self, empresa_valida: Empresa, manifesto_base: dict
    ):
        """
        Un ProspectoCalificado sin triggers rompe la premisa de M2→M3: solo
        llegan empresas que ya pasaron TriggerAggregationPolicy.
        """
        manifiesto = ManifiestoICP(**manifesto_base)
        with pytest.raises(ValidationError):
            ProspectoCalificado(
                empresa=empresa_valida, triggers=[], manifiesto=manifiesto
            )


# ---------------------------------------------------------------------------
# Bloque 9: UmbralCalidadDecisor — Gate de calidad Motor 3 → Motor 4
# ---------------------------------------------------------------------------
class TestUmbralCalidadDecisor:
    policy = UmbralCalidadDecisor()

    def _decisor(self, estado_correo: EstadoCorreo, confianza: float) -> Decisor:
        return Decisor(
            empresa_id=uuid.uuid4(),
            nombre="Ana Torres",
            cargo_original="Chief Technology Officer",
            cargo_normalizado="CTO",
            seniority=Seniority.C_LEVEL,
            estado_correo=estado_correo,
            confianza_dato=confianza,
        )

    def test_verificado_con_confianza_alta_es_apto(self):
        d = self._decisor(EstadoCorreo.VERIFICADO, 0.90)
        assert self.policy.es_apto_para_outbound(d) is True

    def test_inferido_con_confianza_0_70_es_apto(self):
        """Calibración aprobada: accept_all score>=80 → confianza 0.70 → apto."""
        d = self._decisor(EstadoCorreo.INFERIDO, 0.70)
        assert self.policy.es_apto_para_outbound(d) is True

    def test_inferido_con_confianza_0_65_no_es_apto(self):
        """Calibración aprobada: accept_all score 50-79 → confianza 0.65 → cola manual."""
        d = self._decisor(EstadoCorreo.INFERIDO, 0.65)
        assert self.policy.es_apto_para_outbound(d) is False

    def test_rebotado_nunca_es_apto_aunque_confianza_sea_alta(self):
        """Protección de reputación: REBOTADO se descarta sin importar confianza_dato."""
        d = self._decisor(EstadoCorreo.REBOTADO, 0.95)
        assert self.policy.es_apto_para_outbound(d) is False

    def test_no_resuelto_nunca_es_apto(self):
        d = self._decisor(EstadoCorreo.NO_RESUELTO, 0.0)
        assert self.policy.es_apto_para_outbound(d) is False

    def test_particionar_separa_correctamente(self):
        apto = self._decisor(EstadoCorreo.VERIFICADO, 0.9)
        manual = self._decisor(EstadoCorreo.INFERIDO, 0.65)
        descartado = self._decisor(EstadoCorreo.REBOTADO, 0.9)

        aptos, cola_manual = self.policy.particionar([apto, manual, descartado])

        assert aptos == [apto]
        assert cola_manual == [manual, descartado]

    def test_particionar_lista_vacia_retorna_dos_listas_vacias(self):
        assert self.policy.particionar([]) == ([], [])
