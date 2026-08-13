"""
PoliticaMapeoEstadoCorreo — traducción de resultados Apollo→Hunter a EstadoCorreo.

Diseño completo: `02_Lineas_de_Producto/Outbound_Prospector/docs/tecnico/prospector-m3-m4-design.md` §3.2.

DECISIÓN DE UBICACIÓN (Fase 2, 14-Jul-2026):
    Esta política vive en la capa de ADAPTADOR, no en `src/core/domain/policies.py`.
    Motivo: su vocabulario de entrada (status "valid"/"accept_all"/"webmail"/"invalid",
    scores 0-100 de Hunter) es semántica específica de proveedor. Meterla en el Core
    violaría la regla absoluta de pureza (el Core no conoce nombres de proveedor ni
    su vocabulario). Sigue siendo lógica pura y determinista: no importa `requests`,
    no hace I/O, y es 100% testeable sin red ni mocks de HTTP.

Tabla de mapeo canónica (calibración aprobada por el Principal Architect, 14-Jul-2026):

    | Apollo             | Hunter (status / score)          | estado_correo | confianza_dato |
    |--------------------|-----------------------------------|----------------|-----------------|
    | email encontrado   | valid, score >= 90                | VERIFICADO     | 0.90            |
    | email encontrado   | accept_all/webmail, score >= 80   | INFERIDO       | 0.70            |
    | email encontrado   | accept_all/webmail, score 50-79   | INFERIDO       | 0.65            |
    | email encontrado   | invalid / score < 50              | REBOTADO       | 0.10            |
    | perfil sin email   | patrón de dominio inferido        | INFERIDO       | 0.55            |
    | 0 perfiles / sin patrón | —                             | NO_RESUELTO    | 0.0             |
"""

from __future__ import annotations

from src.core.domain.models import EstadoCorreo


class PoliticaMapeoEstadoCorreo:
    """
    Traduce el resultado crudo de la cascada Apollo→Hunter al vocabulario del
    Core (EstadoCorreo + confianza_dato). Lógica pura, sin dependencias de red.
    """

    UMBRAL_SCORE_VERIFICADO: int = 90
    UMBRAL_SCORE_INFERIDO_ALTO: int = 80
    UMBRAL_SCORE_INFERIDO_BAJO: int = 50

    CONFIANZA_VERIFICADO: float = 0.90
    CONFIANZA_INFERIDO_ALTO: float = 0.70
    CONFIANZA_INFERIDO_BAJO: float = 0.65
    CONFIANZA_INFERIDO_PATRON: float = 0.55
    CONFIANZA_REBOTADO: float = 0.10
    CONFIANZA_NO_RESUELTO: float = 0.0

    STATUS_HUNTER_ACCEPT_ALL: frozenset[str] = frozenset({"accept_all", "webmail"})
    STATUS_HUNTER_VALIDO: frozenset[str] = frozenset({"valid"})
    STATUS_HUNTER_INVALIDO: frozenset[str] = frozenset(
        {"invalid", "disposable", "undeliverable"}
    )

    def mapear(
        self,
        *,
        email_encontrado: bool,
        hunter_status: str | None = None,
        hunter_score: int | None = None,
        patron_inferido: bool = False,
    ) -> tuple[EstadoCorreo, float]:
        """
        Args:
            email_encontrado: True si Apollo descubrió un email candidato para el perfil.
            hunter_status: status crudo de Hunter Email Verifier ("valid", "accept_all",
                "webmail", "invalid", "disposable", "undeliverable", etc.). None si Hunter
                no fue invocado (sin email que verificar, o sin API key configurada).
            hunter_score: score 0-100 de Hunter. None si Hunter no fue invocado.
            patron_inferido: True si, ante ausencia de email, Hunter Domain Search
                encontró un patrón de correo corporativo válido para el dominio.

        Returns:
            (EstadoCorreo, confianza_dato) — nunca lanza excepción.
        """
        if not email_encontrado:
            if patron_inferido:
                return EstadoCorreo.INFERIDO, self.CONFIANZA_INFERIDO_PATRON
            return EstadoCorreo.NO_RESUELTO, self.CONFIANZA_NO_RESUELTO

        # Apollo encontró un email pero Hunter no fue invocado (sin API key, o error
        # de red ya contenido por el adaptador). Sin verificación no hay base para
        # confiar en el dato: tratamos como NO_RESUELTO en vez de asumir validez.
        if hunter_status is None or hunter_score is None:
            return EstadoCorreo.NO_RESUELTO, self.CONFIANZA_NO_RESUELTO

        status = hunter_status.lower().strip()
        score = hunter_score

        if (
            status in self.STATUS_HUNTER_INVALIDO
            or score < self.UMBRAL_SCORE_INFERIDO_BAJO
        ):
            return EstadoCorreo.REBOTADO, self.CONFIANZA_REBOTADO

        if (
            status in self.STATUS_HUNTER_VALIDO
            and score >= self.UMBRAL_SCORE_VERIFICADO
        ):
            return EstadoCorreo.VERIFICADO, self.CONFIANZA_VERIFICADO

        # Bandas de INFERIDO: aplica tanto a accept_all/webmail como a "valid" con
        # score por debajo del umbral de VERIFICADO (caso conservador: no asumimos
        # entregabilidad perfecta sin score alto, aunque Hunter lo marque "valid").
        if score >= self.UMBRAL_SCORE_INFERIDO_ALTO:
            return EstadoCorreo.INFERIDO, self.CONFIANZA_INFERIDO_ALTO

        return EstadoCorreo.INFERIDO, self.CONFIANZA_INFERIDO_BAJO
