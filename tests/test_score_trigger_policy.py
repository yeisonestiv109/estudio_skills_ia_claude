"""
Tests de ScoreTriggerPolicy — fijan la spec canónica v5.0 "Signal-Based
Selling" documentada en flujos_motor_1_y_2.md (sección "Signal-Based Selling
v5.0", fuente de verdad).

Pesos y umbral fijados por la spec:
    PUNTOS_BASE:  TIER_0=200  TIER_1=100  TIER_2=50  TIER_3=0
    DECAY_DIAS:   CAUSA=90    EFECTO=45
    UMBRAL_CALIFICACION = 150
    BONUS_MULTI_ORIGEN  = +30  (>=2 orígenes distintos que contribuyen)
    BONUS_TIER0_CRUCE   = +50  (>=1 TIER_0 que contribuye Y >=2 orígenes)

Se usan fechas relativas a datetime.now(timezone.utc) para que los factores de
decay sean estables sin importar cuándo corran los tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.core.domain.models import (
    OrigenTrigger,
    TierUrgencia,
    TipoTrigger,
    Trigger,
)
from src.core.domain.policies import ScoreTriggerPolicy


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _trigger(
    tier: TierUrgencia,
    origen: OrigenTrigger,
    tipo: TipoTrigger = TipoTrigger.EFECTO,
    dias_atras: int | None = 0,
) -> Trigger:
    """
    Construye un Trigger de prueba.

    dias_atras=0    → fecha_evento = ahora (factor de decay = 1.0).
    dias_atras=None → fecha_evento = None (factor de decay = 1.0 por contrato).
    dias_atras>0    → fecha_evento en el pasado (factor según tipo).
    """
    fecha_evento = None if dias_atras is None else _ahora() - timedelta(days=dias_atras)
    return Trigger(
        empresa_id=uuid.uuid4(),
        origen=origen,
        nivel_confianza="ALTA",
        descripcion="trigger de prueba",
        fecha_evento=fecha_evento,
        tipo_trigger=tipo,
        tier_urgencia=tier,
    )


@pytest.fixture
def policy() -> ScoreTriggerPolicy:
    return ScoreTriggerPolicy()


# ---------------------------------------------------------------------------
# Pesos y umbral canónicos
# ---------------------------------------------------------------------------
def test_constantes_canonicas():
    assert ScoreTriggerPolicy.UMBRAL_CALIFICACION == 150
    assert ScoreTriggerPolicy.PUNTOS_BASE[TierUrgencia.TIER_0] == 200
    assert ScoreTriggerPolicy.PUNTOS_BASE[TierUrgencia.TIER_1] == 100
    assert ScoreTriggerPolicy.PUNTOS_BASE[TierUrgencia.TIER_2] == 50
    assert ScoreTriggerPolicy.PUNTOS_BASE[TierUrgencia.TIER_3] == 0
    assert ScoreTriggerPolicy.BONUS_MULTI_ORIGEN == 30
    assert ScoreTriggerPolicy.BONUS_TIER0_CRUCE == 50
    assert ScoreTriggerPolicy.VENTANA_DECAY_DIAS[TipoTrigger.CAUSA] == 90
    assert ScoreTriggerPolicy.VENTANA_DECAY_DIAS[TipoTrigger.EFECTO] == 45


# ---------------------------------------------------------------------------
# Ejemplos canónicos de calificación
# ---------------------------------------------------------------------------
def test_tier0_solo_califica(policy: ScoreTriggerPolicy):
    """TIER_0 solo = 200 ≥ 150 → califica."""
    score, tier, califica = policy.evaluar(
        [_trigger(TierUrgencia.TIER_0, OrigenTrigger.SECOP_SOCRATA, TipoTrigger.CAUSA)]
    )
    assert score == 200
    assert tier == TierUrgencia.TIER_0
    assert califica is True


def test_tier1_solo_no_califica(policy: ScoreTriggerPolicy):
    """TIER_1 solo = 100 < 150 → NO califica (sin bonus, un solo origen)."""
    score, tier, califica = policy.evaluar(
        [_trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS)]
    )
    assert score == 100
    assert tier == TierUrgencia.TIER_1
    assert califica is False


def test_tier1_mas_tier2_dos_origenes_da_180_y_califica(policy: ScoreTriggerPolicy):
    """TIER_1 + TIER_2 de 2 orígenes distintos = 100+50+30 = 180 ≥ 150."""
    triggers = [
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS),
        _trigger(TierUrgencia.TIER_2, OrigenTrigger.THEIRSTACK),
    ]
    score, tier, califica = policy.evaluar(triggers)
    assert score == 180
    assert tier == TierUrgencia.TIER_1  # el más urgente entre contribuyentes
    assert califica is True


def test_tier0_mas_tier0_dos_origenes_da_480(policy: ScoreTriggerPolicy):
    """TIER_0 + TIER_0 de 2 orígenes = 200+200+30(multi)+50(tier0 cruce) = 480."""
    triggers = [
        _trigger(TierUrgencia.TIER_0, OrigenTrigger.SECOP_SOCRATA, TipoTrigger.CAUSA),
        _trigger(TierUrgencia.TIER_0, OrigenTrigger.THEIRSTACK),
    ]
    score, tier, califica = policy.evaluar(triggers)
    assert score == 480
    assert tier == TierUrgencia.TIER_0
    assert califica is True


def test_tier1_mas_tier2_mismo_origen_colapsan_a_la_mejor(policy: ScoreTriggerPolicy):
    """
    Agregación MEJOR-POR-ORIGEN: dos triggers del MISMO origen NO se suman;
    colapsan a la mejor contribución del origen. TIER_1 (100) + TIER_2 (50)
    del mismo Google Alerts = 100 (la mejor), no 150. Un solo origen: sin
    BONUS_MULTI_ORIGEN. 100 < 150 → NO califica.
    """
    triggers = [
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS),
        _trigger(TierUrgencia.TIER_2, OrigenTrigger.GOOGLE_ALERTS),
    ]
    score, tier, califica = policy.evaluar(triggers)
    assert score == 100  # solo la mejor del origen, sin sumar la peor ni +30
    assert tier == TierUrgencia.TIER_1
    assert califica is False  # 100 < 150: un origen ruidoso no califica solo


def test_tier0_solo_no_da_bonus_tier0_cruce(policy: ScoreTriggerPolicy):
    """El BONUS_TIER0_CRUCE exige >=2 orígenes: un TIER_0 solo no lo recibe."""
    score, _, _ = policy.evaluar(
        [_trigger(TierUrgencia.TIER_0, OrigenTrigger.SECOP_SOCRATA, TipoTrigger.CAUSA)]
    )
    assert score == 200  # 200 sin +30 ni +50


# ---------------------------------------------------------------------------
# Decay diferencial CAUSA (90d) vs EFECTO (45d)
# ---------------------------------------------------------------------------
def test_causa_a_60_dias_aun_aporta(policy: ScoreTriggerPolicy):
    """
    Un TIER_0/CAUSA a 60 días: ventana 90d, factor = 1 - 60/90 = 0.333...
    score = 200 * 0.333... ≈ 67 (> 0, aún contribuye).
    """
    score, tier, _ = policy.evaluar(
        [
            _trigger(
                TierUrgencia.TIER_0,
                OrigenTrigger.SECOP_SOCRATA,
                TipoTrigger.CAUSA,
                dias_atras=60,
            )
        ]
    )
    assert score == 67  # round(200 * (1 - 60/90)) = round(66.66) = 67
    assert tier == TierUrgencia.TIER_0  # sigue siendo contribuyente


def test_efecto_a_60_dias_no_aporta(policy: ScoreTriggerPolicy):
    """
    Un EFECTO a 60 días: ventana 45d, factor = max(0, 1 - 60/45) = 0.
    No contribuye: score 0, tier_final degrada a TIER_3.
    """
    score, tier, califica = policy.evaluar(
        [
            _trigger(
                TierUrgencia.TIER_0,
                OrigenTrigger.THEIRSTACK,
                TipoTrigger.EFECTO,
                dias_atras=60,
            )
        ]
    )
    assert score == 0
    assert tier == TierUrgencia.TIER_3
    assert califica is False


def test_fecha_evento_none_no_decae(policy: ScoreTriggerPolicy):
    """Sin fecha_evento el factor es 1.0 (no se penaliza lo que no se puede fechar)."""
    score, tier, califica = policy.evaluar(
        [_trigger(TierUrgencia.TIER_0, OrigenTrigger.SECOP_SOCRATA, dias_atras=None)]
    )
    assert score == 200
    assert tier == TierUrgencia.TIER_0
    assert califica is True


# ---------------------------------------------------------------------------
# Contribuyentes, tier_final y bonus con decay
# ---------------------------------------------------------------------------
def test_tier0_totalmente_decaido_no_cuenta_ni_da_bonus(policy: ScoreTriggerPolicy):
    """
    Un TIER_0/EFECTO totalmente decaído (60d, factor 0) NO cuenta como
    contribuyente: no aporta puntos, no cuenta como origen distinto y no
    dispara el BONUS_TIER0_CRUCE. Queda un TIER_1 fresco solo = 100 < 150.
    """
    triggers = [
        _trigger(
            TierUrgencia.TIER_0,
            OrigenTrigger.THEIRSTACK,
            TipoTrigger.EFECTO,
            dias_atras=60,  # decae a 0
        ),
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS, dias_atras=0),
    ]
    score, tier, califica = policy.evaluar(triggers)
    assert score == 100  # solo el TIER_1; sin multi-origen (1 contribuyente)
    assert tier == TierUrgencia.TIER_1  # el TIER_0 decaído no es contribuyente
    assert califica is False


def test_tier_final_es_el_mas_urgente_entre_contribuyentes(policy: ScoreTriggerPolicy):
    """tier_final = el tier MÁS urgente (TIER_0 > TIER_1 > TIER_2 > TIER_3)."""
    triggers = [
        _trigger(TierUrgencia.TIER_2, OrigenTrigger.THEIRSTACK),
        _trigger(TierUrgencia.TIER_0, OrigenTrigger.SECOP_SOCRATA, TipoTrigger.CAUSA),
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS),
    ]
    _, tier, _ = policy.evaluar(triggers)
    assert tier == TierUrgencia.TIER_0


# ---------------------------------------------------------------------------
# Casos borde
# ---------------------------------------------------------------------------
def test_lista_vacia(policy: ScoreTriggerPolicy):
    assert policy.evaluar([]) == (0, TierUrgencia.TIER_3, False)


def test_adaptadores_activos_no_gatea(policy: ScoreTriggerPolicy):
    """
    El parámetro adaptadores_activos es reservado por compatibilidad y NO
    cambia el resultado: el umbral de score es la única compuerta.
    """
    triggers = [
        _trigger(TierUrgencia.TIER_0, OrigenTrigger.SECOP_SOCRATA, TipoTrigger.CAUSA)
    ]
    sin_arg = policy.evaluar(triggers)
    con_arg = policy.evaluar(triggers, adaptadores_activos=[OrigenTrigger.THEIRSTACK])
    assert sin_arg == con_arg


def test_fecha_evento_futura_no_penaliza(policy: ScoreTriggerPolicy):
    """dias < 0 (evento en el futuro) → factor 1.0."""
    score, _, _ = policy.evaluar(
        [
            _trigger(
                TierUrgencia.TIER_0,
                OrigenTrigger.SECOP_SOCRATA,
                TipoTrigger.CAUSA,
                dias_atras=-5,
            )
        ]
    )
    assert score == 200


# ---------------------------------------------------------------------------
# Agregación MEJOR-POR-ORIGEN (fail-closed: un origen ruidoso no califica solo)
# ---------------------------------------------------------------------------
def test_tres_triggers_mismo_origen_colapsan_a_la_mejor(policy: ScoreTriggerPolicy):
    """
    Caso raíz del fix: tres TIER_1 del MISMO origen (Google Alerts, feed
    ruidoso) NO suman 300. Colapsan a la mejor contribución del origen = 100.
    Un solo origen contribuyente → sin BONUS_MULTI_ORIGEN. 100 < 150 → NO
    califica: una sola fuente ruidosa no puede calificar un lead por sí sola.
    """
    triggers = [
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS),
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS),
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS),
    ]
    score, tier, califica = policy.evaluar(triggers)
    assert score == 100  # NO 300
    assert tier == TierUrgencia.TIER_1
    assert califica is False


def test_dos_origenes_con_multiples_triggers_cada_uno(policy: ScoreTriggerPolicy):
    """
    Dos orígenes, cada uno con varios triggers. Cada origen aporta SOLO su
    mejor contribución:
        - Google Alerts: TIER_1 (100) + TIER_2 (50)  → mejor = 100
        - TheirStack:    TIER_2 (50)  + TIER_1 (100) → mejor = 100
    score_base = 100 + 100 = 200; +30 multi-origen = 230. Sin TIER_0, sin
    cruce TIER_0. 230 ≥ 150 → califica; tier_final = TIER_1 (el más urgente
    entre los contribuyentes).
    """
    triggers = [
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS),
        _trigger(TierUrgencia.TIER_2, OrigenTrigger.GOOGLE_ALERTS),
        _trigger(TierUrgencia.TIER_2, OrigenTrigger.THEIRSTACK),
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.THEIRSTACK),
    ]
    score, tier, califica = policy.evaluar(triggers)
    assert score == 230  # 100 + 100 + 30, sin doble conteo del segundo trigger
    assert tier == TierUrgencia.TIER_1
    assert califica is True


def test_mejor_por_origen_respeta_el_decay(policy: ScoreTriggerPolicy):
    """
    La "mejor" contribución de un origen es la de mayor puntaje YA DECAYADO,
    no la del mayor tier nominal. En un mismo origen:
        - TIER_0/CAUSA a 60 días: 200 * (1 - 60/90) = 66.6 → ~67
        - TIER_1 fresco:          100 * 1.0 = 100
    Aunque TIER_0 tiene mayor base (200), su decay lo deja por debajo del
    TIER_1 fresco. La mejor-por-origen es el TIER_1 (100). Un solo origen →
    sin bonus. score = 100.
    """
    triggers = [
        _trigger(
            TierUrgencia.TIER_0,
            OrigenTrigger.GOOGLE_ALERTS,
            TipoTrigger.CAUSA,
            dias_atras=60,
        ),
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS, dias_atras=0),
    ]
    score, tier, califica = policy.evaluar(triggers)
    assert score == 100  # la mejor por decay es el TIER_1 fresco, no el TIER_0 viejo
    # tier_final sigue siendo TIER_0: ese trigger AÚN contribuye (factor > 0),
    # aunque no sea la mejor contribución de su origen para el score.
    assert tier == TierUrgencia.TIER_0
    assert califica is False


def test_bonus_tier0_cruce_exige_que_tier0_sea_la_mejor_del_origen(
    policy: ScoreTriggerPolicy,
):
    """
    El BONUS_TIER0_CRUCE (+50) exige que la MEJOR contribución de algún origen
    sea TIER_0. Aquí:
        - Origen A (Google Alerts): TIER_0/CAUSA muy decayado (85d de 90 →
          200 * (5/90) ≈ 11) + TIER_1 fresco (100). Mejor = TIER_1 (100).
        - Origen B (TheirStack): TIER_1 fresco (100). Mejor = TIER_1 (100).
    Ningún origen tiene como MEJOR un TIER_0 → NO se aplica +50, solo el +30
    multi-origen. score = 100 + 100 + 30 = 230.
    """
    triggers = [
        _trigger(
            TierUrgencia.TIER_0,
            OrigenTrigger.GOOGLE_ALERTS,
            TipoTrigger.CAUSA,
            dias_atras=85,  # decae casi por completo
        ),
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.GOOGLE_ALERTS, dias_atras=0),
        _trigger(TierUrgencia.TIER_1, OrigenTrigger.THEIRSTACK, dias_atras=0),
    ]
    score, tier, califica = policy.evaluar(triggers)
    assert score == 230  # 100 + 100 + 30 (multi), SIN el +50 de cruce TIER_0
    assert tier == TierUrgencia.TIER_0  # el TIER_0 decayado aún contribuye a tier_final
    assert califica is True
