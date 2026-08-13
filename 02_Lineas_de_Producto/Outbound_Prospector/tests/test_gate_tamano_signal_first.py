"""
Tests del gate de tamaño ASIMÉTRICO de Signal-First Discovery (25-jul-2026).

Cubre `PoliticaCorroboracionTamano.excede_icp`: la regla que cierra el hueco por
el que pasaban scale-ups disfrazados de SME (default de _inferir_tamano ante
employee_count ausente). Asimetría:
    - Un número DURO de TheirStack (> tier del ICP) excluye SIN corroboración.
    - Un CONSENSO corroborado (> tier del ICP) también excluye (incl. MID_MARKET).
    - Confirmar SME (inclusión) sigue exigiendo 2 orígenes (lo cubre corroborar()).
"""

from __future__ import annotations

from src.core.domain.models import (
    EstadoConsensoTamano,
    EstimacionTamano,
    OrigenTrigger,
    TamanoEmpresa,
)
from src.core.domain.policies import PoliticaCorroboracionTamano


def _est(origen: OrigenTrigger, tamano: TamanoEmpresa, conf: float = 0.8) -> EstimacionTamano:
    return EstimacionTamano(origen=origen, tamano_estimado=tamano, confianza=conf)


class TestExcedeTamanoICP:
    def setup_method(self):
        self.politica = PoliticaCorroboracionTamano()

    def test_theirstack_hard_mid_market_excluye_sin_corroboracion(self):
        estimaciones = [_est(OrigenTrigger.THEIRSTACK, TamanoEmpresa.MID_MARKET)]
        excede, reportado = self.politica.excede_icp(
            estimaciones, EstadoConsensoTamano.SIN_CONSENSO, None, TamanoEmpresa.SME
        )
        assert excede is True
        assert reportado == TamanoEmpresa.MID_MARKET

    def test_theirstack_hard_enterprise_excluye(self):
        estimaciones = [_est(OrigenTrigger.THEIRSTACK, TamanoEmpresa.ENTERPRISE)]
        excede, reportado = self.politica.excede_icp(
            estimaciones, EstadoConsensoTamano.SIN_DATOS, None, TamanoEmpresa.SME
        )
        assert excede is True
        assert reportado == TamanoEmpresa.ENTERPRISE

    def test_theirstack_sme_no_excluye(self):
        estimaciones = [_est(OrigenTrigger.THEIRSTACK, TamanoEmpresa.SME)]
        excede, _ = self.politica.excede_icp(
            estimaciones, EstadoConsensoTamano.SIN_CONSENSO, None, TamanoEmpresa.SME
        )
        assert excede is False

    def test_startup_no_excluye(self):
        # STARTUP es MÁS PEQUEÑO que SME → no se excluye por este gate.
        estimaciones = [_est(OrigenTrigger.THEIRSTACK, TamanoEmpresa.STARTUP)]
        excede, _ = self.politica.excede_icp(
            estimaciones, EstadoConsensoTamano.SIN_CONSENSO, None, TamanoEmpresa.SME
        )
        assert excede is False

    def test_fuente_blanda_sola_no_excluye_sin_consenso(self):
        # PropuestaValor (inferencia blanda) diciendo MID_MARKET, SIN consenso,
        # NO debe excluir por sí sola (solo el número duro de TheirStack puede).
        estimaciones = [_est(OrigenTrigger.PROPUESTA_VALOR, TamanoEmpresa.MID_MARKET)]
        excede, _ = self.politica.excede_icp(
            estimaciones, EstadoConsensoTamano.SIN_CONSENSO, None, TamanoEmpresa.SME
        )
        assert excede is False

    def test_consenso_mid_market_excluye(self):
        estimaciones = [
            _est(OrigenTrigger.PROPUESTA_VALOR, TamanoEmpresa.MID_MARKET),
            _est(OrigenTrigger.SECOP_SOCRATA, TamanoEmpresa.MID_MARKET),
        ]
        excede, reportado = self.politica.excede_icp(
            estimaciones,
            EstadoConsensoTamano.CONSENSO,
            TamanoEmpresa.MID_MARKET,
            TamanoEmpresa.SME,
        )
        assert excede is True
        assert reportado == TamanoEmpresa.MID_MARKET

    def test_consenso_sme_no_excluye(self):
        estimaciones = [
            _est(OrigenTrigger.PROPUESTA_VALOR, TamanoEmpresa.SME),
            _est(OrigenTrigger.SECOP_SOCRATA, TamanoEmpresa.SME),
        ]
        excede, _ = self.politica.excede_icp(
            estimaciones,
            EstadoConsensoTamano.CONSENSO,
            TamanoEmpresa.SME,
            TamanoEmpresa.SME,
        )
        assert excede is False

    def test_sin_estimaciones_no_excluye(self):
        # Sin datos → no se puede afirmar "demasiado grande" → no excluye.
        excede, _ = self.politica.excede_icp(
            [], EstadoConsensoTamano.SIN_DATOS, None, TamanoEmpresa.SME
        )
        assert excede is False
