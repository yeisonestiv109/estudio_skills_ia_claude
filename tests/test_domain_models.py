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
    AutoridadDecision,
    BaseLegal,
    CategoriaEmpresa,
    ContextoRAG,
    Decisor,
    Empresa,
    EstadoConsensoTamano,
    EstadoCorreo,
    EstadoMensaje,
    EstadoValidacionGeografica,
    EstimacionTamano,
    ManifiestoICP,
    Mensaje,
    NivelConfianza,
    OrigenTrigger,
    PAIS_DESCONOCIDO,
    PaqueteOutbound,
    ProspectoCalificado,
    ResultadoEnvio,
    ResultadoExclusionCompetidor,
    Seniority,
    TamanoEmpresa,
    Trigger,
)
from src.core.domain.policies import (
    AdapterRoutingPolicy,
    PoliticaCorroboracionTamano,
    PoliticaExclusionCompetidores,
    PoliticaFronteraLegal,
    PoliticaFronterasEnvio,
    PoliticaRegistroRebote,
    PoliticaSeleccionMejorDecisor,
    PoliticaValidacionGeografica,
    TriggerAggregationPolicy,
    UmbralCalidadDecisor,
)
from src.core.ports.interfaces import (
    PuertoClasificadorPropuestaValor,
    PuertoContextoRAG,
    PuertoEnriquecedorContactos,
    PuertoEnvioCorreo,
    PuertoEstimadorTamano,
    PuertoRedactorOutbound,
)


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


# ===========================================================================
# MOTOR 4 (Outbound RAG) — Tests de modelos, puertos y políticas puras
# Diseño: 10-Memoria_Consolidada/tecnico/prospector-m4-design.md
# ===========================================================================


def _decisor(
    *,
    autoridad: AutoridadDecision = AutoridadDecision.UNKNOWN,
    seniority: Seniority = Seniority.IC,
    confianza: float = 0.9,
    estado_correo: EstadoCorreo = EstadoCorreo.VERIFICADO,
    nombre: str = "Persona X",
    empresa_id: uuid.UUID | None = None,
) -> Decisor:
    return Decisor(
        empresa_id=empresa_id or uuid.uuid4(),
        nombre=nombre,
        cargo_original="Cargo",
        cargo_normalizado="CARGO",
        seniority=seniority,
        autoridad_decision=autoridad,
        estado_correo=estado_correo,
        confianza_dato=confianza,
    )


# ---------------------------------------------------------------------------
# Bloque 10: Modelos M4 — Mensaje, ContextoRAG, PaqueteOutbound
# ---------------------------------------------------------------------------
class TestModelosMotor4:
    def test_mensaje_nace_en_estado_borrador(self):
        m = Mensaje(decisor_id=uuid.uuid4(), asunto="Hola", cuerpo="Cuerpo del mensaje")
        assert m.estado == EstadoMensaje.BORRADOR

    def test_mensaje_es_inmutable(self):
        m = Mensaje(decisor_id=uuid.uuid4(), asunto="Hola", cuerpo="Cuerpo")
        with pytest.raises(ValidationError):
            m.estado = EstadoMensaje.ENVIADO  # type: ignore[misc]

    def test_mensaje_rechaza_asunto_vacio(self):
        with pytest.raises(ValidationError):
            Mensaje(decisor_id=uuid.uuid4(), asunto="", cuerpo="Cuerpo")

    def test_mensaje_transicion_via_model_copy(self):
        """Las transiciones se hacen con model_copy, no mutando el original."""
        m = Mensaje(decisor_id=uuid.uuid4(), asunto="Hola", cuerpo="Cuerpo")
        aprobado = m.model_copy(update={"estado": EstadoMensaje.APROBADO})
        assert m.estado == EstadoMensaje.BORRADOR  # el original no cambió
        assert aprobado.estado == EstadoMensaje.APROBADO

    def test_contexto_rag_vacio_es_valido(self):
        ctx = ContextoRAG()
        assert ctx.evidencias == []
        assert ctx.fuentes == []

    def test_paquete_outbound_construccion_valida(
        self, empresa_valida: Empresa, manifesto_base: dict
    ):
        manifiesto = ManifiestoICP(**manifesto_base)
        trigger = Trigger(
            empresa_id=empresa_valida.id,
            origen=OrigenTrigger.GOOGLE_ALERTS,
            nivel_confianza=NivelConfianza.ALTA,
            descripcion="Nuevo CTO",
            fecha_evento=datetime.now(timezone.utc),
        )
        prospecto = ProspectoCalificado(
            empresa=empresa_valida, triggers=[trigger], manifiesto=manifiesto
        )
        paquete = PaqueteOutbound(
            prospecto=prospecto,
            decisores_aptos=[_decisor(empresa_id=empresa_valida.id)],
        )
        assert paquete.prospecto == prospecto
        assert len(paquete.decisores_aptos) == 1

    def test_paquete_outbound_requiere_al_menos_un_decisor(
        self, empresa_valida: Empresa, manifesto_base: dict
    ):
        manifiesto = ManifiestoICP(**manifesto_base)
        trigger = Trigger(
            empresa_id=empresa_valida.id,
            origen=OrigenTrigger.GOOGLE_ALERTS,
            nivel_confianza=NivelConfianza.ALTA,
            descripcion="Nuevo CTO",
            fecha_evento=datetime.now(timezone.utc),
        )
        prospecto = ProspectoCalificado(
            empresa=empresa_valida, triggers=[trigger], manifiesto=manifiesto
        )
        with pytest.raises(ValidationError):
            PaqueteOutbound(prospecto=prospecto, decisores_aptos=[])


# ---------------------------------------------------------------------------
# Bloque 11: Puertos M4 — ABCs no instanciables
# ---------------------------------------------------------------------------
class TestPuertosMotor4ABC:
    def test_contexto_rag_no_instanciable(self):
        with pytest.raises(TypeError):
            PuertoContextoRAG()  # type: ignore[abstract]

    def test_redactor_outbound_no_instanciable(self):
        with pytest.raises(TypeError):
            PuertoRedactorOutbound()  # type: ignore[abstract]

    def test_envio_correo_no_instanciable(self):
        with pytest.raises(TypeError):
            PuertoEnvioCorreo()  # type: ignore[abstract]

    def test_enriquecedor_sigue_no_instanciable(self):
        """Regresión: el puerto de M3 sigue siendo abstracto tras añadir los de M4."""
        with pytest.raises(TypeError):
            PuertoEnriquecedorContactos()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Bloque 12: PoliticaSeleccionMejorDecisor — el filtro anti-Rappi
# ---------------------------------------------------------------------------
class TestPoliticaSeleccionMejorDecisor:
    policy = PoliticaSeleccionMejorDecisor()

    def test_lista_vacia_retorna_none(self):
        assert self.policy.seleccionar([]) is None

    def test_un_solo_decisor_se_retorna_a_si_mismo(self):
        d = _decisor()
        assert self.policy.seleccionar([d]) is d

    def test_autoridad_manda_sobre_confianza(self):
        """Un DECISION_MAKER con confianza menor gana a un UNKNOWN con confianza mayor."""
        decision_maker = _decisor(
            autoridad=AutoridadDecision.DECISION_MAKER, confianza=0.75, nombre="Jefe"
        )
        unknown_alto = _decisor(
            autoridad=AutoridadDecision.UNKNOWN, confianza=0.99, nombre="Desconocido"
        )
        elegido = self.policy.seleccionar([unknown_alto, decision_maker])
        assert elegido.nombre == "Jefe"

    def test_a_igual_autoridad_gana_mayor_confianza(self):
        bajo = _decisor(
            autoridad=AutoridadDecision.DECISION_MAKER, confianza=0.70, nombre="Bajo"
        )
        alto = _decisor(
            autoridad=AutoridadDecision.DECISION_MAKER, confianza=0.90, nombre="Alto"
        )
        elegido = self.policy.seleccionar([bajo, alto])
        assert elegido.nombre == "Alto"

    def test_a_igual_autoridad_y_confianza_gana_mayor_seniority(self):
        vp = _decisor(
            autoridad=AutoridadDecision.DECISION_MAKER,
            confianza=0.90,
            seniority=Seniority.VP,
            nombre="VP",
        )
        clevel = _decisor(
            autoridad=AutoridadDecision.DECISION_MAKER,
            confianza=0.90,
            seniority=Seniority.C_LEVEL,
            nombre="CLevel",
        )
        elegido = self.policy.seleccionar([vp, clevel])
        assert elegido.nombre == "CLevel"

    def test_caso_rappi_elige_al_cto_sobre_los_vps(self):
        """
        Reproducción del piloto real: 5 decisores de Rappi, 4 VPs + 1 CTO.
        La política debe devolver UN SOLO decisor: el CTO (C_LEVEL, 0.90).
        """
        empresa_id = uuid.uuid4()
        vps = [
            _decisor(
                autoridad=AutoridadDecision.DECISION_MAKER,
                seniority=Seniority.VP,
                confianza=0.90 if i != 1 else 0.70,
                nombre=f"VP Engineering {i}",
                empresa_id=empresa_id,
            )
            for i in range(4)
        ]
        cto = _decisor(
            autoridad=AutoridadDecision.DECISION_MAKER,
            seniority=Seniority.C_LEVEL,
            confianza=0.90,
            nombre="Leandro Reox",
            empresa_id=empresa_id,
        )
        elegido = self.policy.seleccionar([*vps, cto])
        assert elegido is not None
        assert elegido.nombre == "Leandro Reox"
        assert elegido.seniority == Seniority.C_LEVEL


# ---------------------------------------------------------------------------
# Bloque 13: PoliticaFronteraLegal — gate Habeas Data
# ---------------------------------------------------------------------------
class TestPoliticaFronteraLegal:
    policy = PoliticaFronteraLegal()

    def _manifiesto(self, base_legal: BaseLegal, manifesto_base: dict) -> ManifiestoICP:
        datos = dict(manifesto_base)
        datos["base_legal"] = base_legal
        return ManifiestoICP(**datos)

    def test_dato_publico_permite_contactar(self, manifesto_base: dict):
        m = self._manifiesto(BaseLegal.DATO_PUBLICO, manifesto_base)
        assert self.policy.puede_contactar(m) is True

    def test_consentimiento_explicito_permite_contactar(self, manifesto_base: dict):
        m = self._manifiesto(BaseLegal.CONSENTIMIENTO_EXPLICITO, manifesto_base)
        assert self.policy.puede_contactar(m) is True

    def test_ejecucion_contrato_permite_contactar(self, manifesto_base: dict):
        m = self._manifiesto(BaseLegal.EJECUCION_CONTRATO, manifesto_base)
        assert self.policy.puede_contactar(m) is True


# ---------------------------------------------------------------------------
# Bloque 14: PoliticaFronterasEnvio — reputación + HITL + pacing
# ---------------------------------------------------------------------------
class TestPoliticaFronterasEnvio:
    policy = PoliticaFronterasEnvio()

    def _mensaje(self, estado: EstadoMensaje) -> Mensaje:
        return Mensaje(
            decisor_id=uuid.uuid4(),
            asunto="Asunto",
            cuerpo="Cuerpo",
            estado=estado,
        )

    def test_aprobado_legal_ok_y_pacing_ok_es_enviable(self):
        m = self._mensaje(EstadoMensaje.APROBADO)
        assert self.policy.es_enviable(m, base_legal_ok=True, enviados_hoy=0) is True

    def test_borrador_no_es_enviable_aunque_todo_lo_demas_este_ok(self):
        """Frontera de reputación: sin aprobación humana, no se envía."""
        m = self._mensaje(EstadoMensaje.BORRADOR)
        assert self.policy.es_enviable(m, base_legal_ok=True, enviados_hoy=0) is False

    def test_sin_base_legal_no_es_enviable(self):
        m = self._mensaje(EstadoMensaje.APROBADO)
        assert self.policy.es_enviable(m, base_legal_ok=False, enviados_hoy=0) is False

    def test_pacing_excedido_no_es_enviable(self):
        m = self._mensaje(EstadoMensaje.APROBADO)
        limite = PoliticaFronterasEnvio.MAX_ENVIOS_POR_DOMINIO_DIA
        assert (
            self.policy.es_enviable(m, base_legal_ok=True, enviados_hoy=limite) is False
        )

    def test_pacing_justo_por_debajo_del_limite_es_enviable(self):
        m = self._mensaje(EstadoMensaje.APROBADO)
        limite = PoliticaFronterasEnvio.MAX_ENVIOS_POR_DOMINIO_DIA
        assert (
            self.policy.es_enviable(m, base_legal_ok=True, enviados_hoy=limite - 1)
            is True
        )

    def test_rechazado_hitl_no_es_enviable(self):
        m = self._mensaje(EstadoMensaje.RECHAZADO_HITL)
        assert self.policy.es_enviable(m, base_legal_ok=True, enviados_hoy=0) is False


# ---------------------------------------------------------------------------
# Bloque 15: PoliticaRegistroRebote — lazo de retroalimentación (cierra KPI M3)
# ---------------------------------------------------------------------------
class TestPoliticaRegistroRebote:
    policy = PoliticaRegistroRebote()

    def test_rebotado_marca_estado_correo_y_baja_confianza(self):
        d = _decisor(estado_correo=EstadoCorreo.VERIFICADO, confianza=0.90)
        actualizado = self.policy.aplicar(d, ResultadoEnvio.REBOTADO)
        assert actualizado.estado_correo == EstadoCorreo.REBOTADO
        assert actualizado.confianza_dato == 0.0

    def test_rebotado_no_muta_el_decisor_original(self):
        """Decisor de entrada no se muta: se retorna una copia (model_copy)."""
        d = _decisor(estado_correo=EstadoCorreo.VERIFICADO, confianza=0.90)
        self.policy.aplicar(d, ResultadoEnvio.REBOTADO)
        assert d.estado_correo == EstadoCorreo.VERIFICADO
        assert d.confianza_dato == 0.90

    def test_entregado_no_cambia_el_decisor(self):
        d = _decisor(estado_correo=EstadoCorreo.VERIFICADO, confianza=0.90)
        actualizado = self.policy.aplicar(d, ResultadoEnvio.ENTREGADO)
        assert actualizado.estado_correo == EstadoCorreo.VERIFICADO
        assert actualizado.confianza_dato == 0.90

    def test_diferido_no_cambia_el_decisor(self):
        d = _decisor(estado_correo=EstadoCorreo.INFERIDO, confianza=0.70)
        actualizado = self.policy.aplicar(d, ResultadoEnvio.DIFERIDO)
        assert actualizado.estado_correo == EstadoCorreo.INFERIDO


# ===========================================================================
# MOTOR 2 (Afinamiento) — PoliticaCorroboracionTamano, PoliticaExclusionCompetidores
# Diseño: investigación "Waterfall Enrichment" / "Negative ICP"
# ===========================================================================


def _estimacion(
    origen: OrigenTrigger, tamano: TamanoEmpresa, confianza: float = 1.0
) -> EstimacionTamano:
    return EstimacionTamano(origen=origen, tamano_estimado=tamano, confianza=confianza)


# ---------------------------------------------------------------------------
# Bloque 16: EstimacionTamano — ValueObject
# ---------------------------------------------------------------------------
class TestEstimacionTamano:
    def test_construccion_valida_con_confianza_default(self):
        est = EstimacionTamano(
            origen=OrigenTrigger.THEIRSTACK, tamano_estimado=TamanoEmpresa.SME
        )
        assert est.confianza == 1.0

    def test_es_inmutable(self):
        est = _estimacion(OrigenTrigger.THEIRSTACK, TamanoEmpresa.SME)
        with pytest.raises(ValidationError):
            est.tamano_estimado = TamanoEmpresa.ENTERPRISE  # type: ignore[misc]

    def test_confianza_fuera_de_rango_rechazada(self):
        with pytest.raises(ValidationError):
            EstimacionTamano(
                origen=OrigenTrigger.THEIRSTACK,
                tamano_estimado=TamanoEmpresa.SME,
                confianza=1.5,
            )


# ---------------------------------------------------------------------------
# Bloque 17: PoliticaCorroboracionTamano — waterfall de tamaño
# ---------------------------------------------------------------------------
class TestPoliticaCorroboracionTamano:
    policy = PoliticaCorroboracionTamano()

    def test_lista_vacia_retorna_sin_datos(self):
        estado, tamano = self.policy.corroborar([])
        assert estado == EstadoConsensoTamano.SIN_DATOS
        assert tamano is None

    def test_un_solo_origen_retorna_sin_consenso(self):
        """Un solo origen, sin importar su confianza, no basta (mínimo 2 distintos)."""
        estimaciones = [_estimacion(OrigenTrigger.THEIRSTACK, TamanoEmpresa.SME)]
        estado, tamano = self.policy.corroborar(estimaciones)
        assert estado == EstadoConsensoTamano.SIN_CONSENSO
        assert tamano is None

    def test_dos_origenes_distintos_mismo_tamano_da_consenso(self):
        estimaciones = [
            _estimacion(OrigenTrigger.THEIRSTACK, TamanoEmpresa.SME),
            _estimacion(OrigenTrigger.WAPPALYZER, TamanoEmpresa.SME),
        ]
        estado, tamano = self.policy.corroborar(estimaciones)
        assert estado == EstadoConsensoTamano.CONSENSO
        assert tamano == TamanoEmpresa.SME

    def test_dos_origenes_en_tiers_adyacentes_da_consenso(self):
        """STARTUP y SME son adyacentes (distancia 1): se acepta como consenso."""
        estimaciones = [
            _estimacion(OrigenTrigger.THEIRSTACK, TamanoEmpresa.STARTUP),
            _estimacion(OrigenTrigger.WAPPALYZER, TamanoEmpresa.SME),
        ]
        estado, tamano = self.policy.corroborar(estimaciones)
        assert estado == EstadoConsensoTamano.CONSENSO

    def test_dos_origenes_en_tiers_lejanos_da_sin_consenso(self):
        """SME vs ENTERPRISE (distancia 3): conflicto real, no se fuerza un tamaño."""
        estimaciones = [
            _estimacion(OrigenTrigger.THEIRSTACK, TamanoEmpresa.SME),
            _estimacion(OrigenTrigger.WAPPALYZER, TamanoEmpresa.ENTERPRISE),
        ]
        estado, tamano = self.policy.corroborar(estimaciones)
        assert estado == EstadoConsensoTamano.SIN_CONSENSO
        assert tamano is None

    def test_mismo_origen_repetido_no_cuenta_como_dos(self):
        """Dos estimaciones del MISMO origen no satisfacen el mínimo de 2 distintos."""
        estimaciones = [
            _estimacion(OrigenTrigger.THEIRSTACK, TamanoEmpresa.SME),
            _estimacion(OrigenTrigger.THEIRSTACK, TamanoEmpresa.SME),
        ]
        estado, tamano = self.policy.corroborar(estimaciones)
        assert estado == EstadoConsensoTamano.SIN_CONSENSO
        assert tamano is None

    def test_tres_origenes_mayoria_gana_desempate_por_confianza(self):
        """2 orígenes dicen SME, 1 dice ENTERPRISE aislado: gana SME por mayoría."""
        estimaciones = [
            _estimacion(OrigenTrigger.THEIRSTACK, TamanoEmpresa.SME, confianza=0.9),
            _estimacion(OrigenTrigger.WAPPALYZER, TamanoEmpresa.SME, confianza=0.8),
            _estimacion(OrigenTrigger.GITHUB, TamanoEmpresa.ENTERPRISE, confianza=1.0),
        ]
        estado, tamano = self.policy.corroborar(estimaciones)
        assert estado == EstadoConsensoTamano.CONSENSO
        assert tamano == TamanoEmpresa.SME


# ---------------------------------------------------------------------------
# Bloque 18: PoliticaExclusionCompetidores — Negative ICP (3 cubetas)
# ---------------------------------------------------------------------------
class TestPoliticaExclusionCompetidores:
    policy = PoliticaExclusionCompetidores()

    def test_categorias_identicas_es_excluido_duro(self):
        """Caso TBBC: cliente AGENCIA_IT descubre otra AGENCIA_IT → hard exclusion."""
        resultado = self.policy.evaluar(
            categoria_cliente=CategoriaEmpresa.AGENCIA_IT,
            categoria_candidata=CategoriaEmpresa.AGENCIA_IT,
        )
        assert resultado == ResultadoExclusionCompetidor.EXCLUIDO_DURO

    def test_categorias_ambiguas_requiere_analisis_semantico(self):
        resultado = self.policy.evaluar(
            categoria_cliente=CategoriaEmpresa.AGENCIA_IT,
            categoria_candidata=CategoriaEmpresa.CONSULTORA_IT,
        )
        assert resultado == ResultadoExclusionCompetidor.REQUIERE_ANALISIS_SEMANTICO

    def test_ambiguedad_es_simetrica_sin_importar_el_orden(self):
        resultado_ab = self.policy.evaluar(
            categoria_cliente=CategoriaEmpresa.CONSULTORA_IT,
            categoria_candidata=CategoriaEmpresa.AGENCIA_IT,
        )
        resultado_ba = self.policy.evaluar(
            categoria_cliente=CategoriaEmpresa.AGENCIA_IT,
            categoria_candidata=CategoriaEmpresa.CONSULTORA_IT,
        )
        assert resultado_ab == resultado_ba == ResultadoExclusionCompetidor.REQUIERE_ANALISIS_SEMANTICO

    def test_categorias_claramente_distintas_es_permitido(self):
        """TBBC (AGENCIA_IT) buscando un cliente fintech regulado: sin conflicto."""
        resultado = self.policy.evaluar(
            categoria_cliente=CategoriaEmpresa.AGENCIA_IT,
            categoria_candidata=CategoriaEmpresa.REGULADO_FINTECH,
        )
        assert resultado == ResultadoExclusionCompetidor.PERMITIDO

    def test_no_lanza_excepcion_con_cualquier_par_de_enum(self):
        """La política debe resolver TODOS los pares posibles sin lanzar."""
        for cat_cliente in CategoriaEmpresa:
            for cat_candidata in CategoriaEmpresa:
                resultado = self.policy.evaluar(cat_cliente, cat_candidata)
                assert isinstance(resultado, ResultadoExclusionCompetidor)


# ---------------------------------------------------------------------------
# Bloque 19: Puertos nuevos del Motor 2 — ABCs no instanciables
# ---------------------------------------------------------------------------
class TestPuertosMotor2AfinamientoABC:
    def test_estimador_tamano_no_instanciable(self):
        with pytest.raises(TypeError):
            PuertoEstimadorTamano()  # type: ignore[abstract]

    def test_clasificador_propuesta_valor_no_instanciable(self):
        with pytest.raises(TypeError):
            PuertoClasificadorPropuestaValor()  # type: ignore[abstract]

    def test_implementacion_concreta_de_estimador_tamano_respeta_firma(
        self, empresa_valida: Empresa
    ):
        class _EstimadorFake(PuertoEstimadorTamano):
            def estimar_tamano(self, empresa: Empresa) -> EstimacionTamano | None:
                return _estimacion(OrigenTrigger.GITHUB, TamanoEmpresa.SME)

        resultado = _EstimadorFake().estimar_tamano(empresa_valida)
        assert resultado.tamano_estimado == TamanoEmpresa.SME

    def test_implementacion_concreta_de_clasificador_puede_retornar_none(
        self, empresa_valida: Empresa
    ):
        class _ClasificadorFake(PuertoClasificadorPropuestaValor):
            def clasificar(self, empresa: Empresa) -> CategoriaEmpresa | None:
                return None

        assert _ClasificadorFake().clasificar(empresa_valida) is None


# ---------------------------------------------------------------------------
# Bloque 20: PoliticaValidacionGeografica — waterfall geográfico (fix Falla 2,
# caso Parcero/UK)
# ---------------------------------------------------------------------------
class TestPoliticaValidacionGeografica:
    policy = PoliticaValidacionGeografica()

    def test_paises_coincidentes_es_permitido(self):
        resultado = self.policy.evaluar(pais_candidato="CO", geografia_icp="CO")
        assert resultado == EstadoValidacionGeografica.PERMITIDO

    def test_paises_coincidentes_normaliza_minusculas(self):
        """El cruce debe ser insensible a mayúsculas/minúsculas."""
        resultado = self.policy.evaluar(pais_candidato="co", geografia_icp="CO")
        assert resultado == EstadoValidacionGeografica.PERMITIDO

    def test_paises_distintos_es_excluido(self):
        """Caso Parcero: HQ en Londres (GB) vs. ICP='CO' → EXCLUIDO."""
        resultado = self.policy.evaluar(pais_candidato="GB", geografia_icp="CO")
        assert resultado == EstadoValidacionGeografica.EXCLUIDO

    def test_icp_sin_restriccion_geografica_es_permitido(self):
        """Si el ICP no declara geografía, no hay criterio para excluir."""
        resultado = self.policy.evaluar(pais_candidato="GB", geografia_icp=None)
        assert resultado == EstadoValidacionGeografica.PERMITIDO

    def test_icp_con_geografia_vacia_es_permitido(self):
        resultado = self.policy.evaluar(pais_candidato="GB", geografia_icp="   ")
        assert resultado == EstadoValidacionGeografica.PERMITIDO

    def test_pais_candidato_none_es_indeterminado_fail_closed(self):
        """
        Fail-closed: sin ningún país candidato disponible, NUNCA se aprueba
        automáticamente, incluso si el ICP sí restringe geografía.
        """
        resultado = self.policy.evaluar(pais_candidato=None, geografia_icp="CO")
        assert resultado == EstadoValidacionGeografica.INDETERMINADO

    def test_pais_candidato_desconocido_centinela_es_indeterminado(self):
        """El centinela PAIS_DESCONOCIDO ('XX') se trata igual que None."""
        resultado = self.policy.evaluar(
            pais_candidato=PAIS_DESCONOCIDO, geografia_icp="CO"
        )
        assert resultado == EstadoValidacionGeografica.INDETERMINADO

    def test_pais_candidato_cadena_vacia_es_indeterminado(self):
        resultado = self.policy.evaluar(pais_candidato="", geografia_icp="CO")
        assert resultado == EstadoValidacionGeografica.INDETERMINADO

    def test_indeterminado_nunca_se_confunde_con_permitido(self):
        """Sanidad de enum: INDETERMINADO y PERMITIDO son valores distintos."""
        assert (
            EstadoValidacionGeografica.INDETERMINADO
            != EstadoValidacionGeografica.PERMITIDO
        )

    def test_no_lanza_excepcion_con_ninguna_combinacion(self):
        paises = [None, "", "XX", "CO", "GB", "co", "gb"]
        for candidato in paises:
            for icp in paises:
                resultado = self.policy.evaluar(candidato, icp)
                assert isinstance(resultado, EstadoValidacionGeografica)


# ---------------------------------------------------------------------------
# Bloque 21: ResultadoExclusionCompetidor.PENDIENTE_REVISION_MANUAL (fix
# fail-open → fail-closed, Falla 1, caso Parcero/UK)
# ---------------------------------------------------------------------------
class TestResultadoExclusionCompetidorFailClosed:
    def test_pendiente_revision_manual_existe_como_valor_del_enum(self):
        assert (
            ResultadoExclusionCompetidor.PENDIENTE_REVISION_MANUAL
            == "PENDIENTE_REVISION_MANUAL"
        )

    def test_pendiente_revision_manual_es_distinto_de_permitido(self):
        """
        Sanidad del fix: un análisis indeterminado NUNCA debe ser igual a
        (ni confundirse con) un análisis que confirmó ausencia de competencia.
        """
        assert (
            ResultadoExclusionCompetidor.PENDIENTE_REVISION_MANUAL
            != ResultadoExclusionCompetidor.PERMITIDO
        )

    def test_pendiente_revision_manual_es_distinto_de_excluido_duro(self):
        assert (
            ResultadoExclusionCompetidor.PENDIENTE_REVISION_MANUAL
            != ResultadoExclusionCompetidor.EXCLUIDO_DURO
        )

    def test_enum_completo_tiene_cuatro_valores(self):
        """El enum extendido debe conservar los 3 valores originales + 1 nuevo."""
        valores = {r.value for r in ResultadoExclusionCompetidor}
        assert valores == {
            "PERMITIDO",
            "EXCLUIDO_DURO",
            "REQUIERE_ANALISIS_SEMANTICO",
            "PENDIENTE_REVISION_MANUAL",
        }
