"""
Políticas de Dominio (Reglas de Negocio Puras) — El Prospector.

Transcripción fiel de:
    - `10-Memoria_Consolidada/modelos_dominio_core.md` (TriggerAggregationPolicy)
    - `10-Memoria_Consolidada/flujos_motor_1_y_2.md`   (AdapterRoutingPolicy)

REGLA: Estas políticas son lógica de dominio pura. No conocen adaptadores
concretos ni dependencias externas. Solo operan sobre modelos y enums del Core.
Son testables unitariamente sin red, sin LLM y sin base de datos.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.domain.models import (
    CategoriaEmpresa,
    ManifiestoICP,
    OrigenTrigger,
    Trigger,
)


class AdapterRoutingPolicy:
    """
    Enrutador Dinámico (Motor 1).

    Decide qué adaptadores del Motor 2 activar según el ManifiestoICP.
    Regla base: Google Alerts siempre activo (90% universal).
    Los demás se activan condicionalmente según la categoría de empresa.

    Retorna list[OrigenTrigger] (Enum del Core), NUNCA instancias de adaptadores.
    El orquestador de la capa de aplicación resuelve el Enum a la instancia
    concreta vía inyección de dependencias, preservando el aislamiento hexagonal.
    """

    CATEGORIAS_GOV_FACING: frozenset[CategoriaEmpresa] = frozenset(
        {
            CategoriaEmpresa.AGENCIA_IT,
            CategoriaEmpresa.CONSULTORA_IT,
            CategoriaEmpresa.BPO_MANAGED,
            CategoriaEmpresa.GOVTECH_REGTECH,
        }
    )

    CATEGORIAS_STACK_VISIBLE: frozenset[CategoriaEmpresa] = frozenset(
        {
            CategoriaEmpresa.SAAS_B2B_HORIZONTAL,
            CategoriaEmpresa.SAAS_B2B_VERTICAL,
            CategoriaEmpresa.AGENCIA_IT,
        }
    )

    CATEGORIAS_SIN_WAPPALYZER: frozenset[CategoriaEmpresa] = frozenset(
        {
            CategoriaEmpresa.CIBERSEGURIDAD,       # Ocultan stack deliberadamente
            CategoriaEmpresa.REGULADO_FINTECH,     # Core bancario no es web-visible
            CategoriaEmpresa.REGULADO_HEALTHTECH,
            CategoriaEmpresa.AI_ML_PLATFORM,       # Infraestructura no frontal
            CategoriaEmpresa.BPO_MANAGED,
        }
    )

    CATEGORIAS_SIN_THEIRSTACK: frozenset[CategoriaEmpresa] = frozenset(
        {
            CategoriaEmpresa.REGULADO_FINTECH,
            CategoriaEmpresa.REGULADO_HEALTHTECH,
        }
    )

    CATEGORIAS_CON_GITHUB: frozenset[CategoriaEmpresa] = frozenset(
        {
            CategoriaEmpresa.SAAS_B2B_HORIZONTAL,
            CategoriaEmpresa.SAAS_B2B_VERTICAL,
            CategoriaEmpresa.AGENCIA_IT,
            CategoriaEmpresa.CONSULTORA_IT,
            CategoriaEmpresa.AI_ML_PLATFORM,
            CategoriaEmpresa.CIBERSEGURIDAD,    # Security teams suelen tener repos públicos
        }
    )

    def resolver(self, manifesto: ManifiestoICP) -> list[OrigenTrigger]:
        # Google Alerts siempre activo (90% universal).
        activos: list[OrigenTrigger] = [OrigenTrigger.GOOGLE_ALERTS]

        # TheirStack: útil para todas las categorías excepto reguladas puras
        # (hiring discreto, alta tasa de falso positivo).
        if manifesto.categoria_empresa not in self.CATEGORIAS_SIN_THEIRSTACK:
            activos.append(OrigenTrigger.THEIRSTACK)

        # SECOP: solo si el perfil tiene naturaleza gov-facing.
        if (
            manifesto.es_gov_facing
            or manifesto.categoria_empresa in self.CATEGORIAS_GOV_FACING
        ):
            activos.append(OrigenTrigger.SECOP_SOCRATA)

        # Wappalyzer: solo donde el stack es web-visible y el dolor es
        # deuda técnica de frontend/backend observable.
        if (
            manifesto.categoria_empresa in self.CATEGORIAS_STACK_VISIBLE
            and manifesto.categoria_empresa not in self.CATEGORIAS_SIN_WAPPALYZER
        ):
            activos.append(OrigenTrigger.WAPPALYZER)

        # GitHub: empresas de producto / desarrollo / seguridad con repos públicos.
        if manifesto.categoria_empresa in self.CATEGORIAS_CON_GITHUB:
            activos.append(OrigenTrigger.GITHUB)

        return activos


class TriggerAggregationPolicy:
    """
    Valida el cruce de señales (Motor 2). Decide si un prospecto avanza al Motor 3.
    NO es un modelo Pydantic. Es lógica de dominio pura.
    """

    MINIMO_VECTORES: int = 2
    VENTANA_DIAS_DECAY: int = 45

    def evaluar(
        self,
        triggers: list[Trigger],
        adaptadores_activos: list[OrigenTrigger] | None = None,
    ) -> bool:
        """
        Retorna True si el prospecto cumple el umbral mínimo de señales.

        Regla 1: Mínimo MINIMO_VECTORES triggers de orígenes DISTINTOS.
                 Mismo origen repetido no cuenta como validación cruzada.
        Regla 2: Al menos uno debe tener fecha_evento dentro de VENTANA_DIAS_DECAY días.
        Regla 3 (v3.0): Si el enrutador solo habilitó 1 adaptador (caso edge),
                        el umbral se ajusta a min(MINIMO_VECTORES, len(adaptadores_activos)).
                        Esto evita bloquear prospectos válidos cuando la
                        AdapterRoutingPolicy conscientemente redujo el scope.
        """
        # Calcular el umbral mínimo real según adaptadores disponibles.
        umbral = self.MINIMO_VECTORES
        if adaptadores_activos is not None:
            umbral = min(self.MINIMO_VECTORES, len(adaptadores_activos))

        if len(triggers) < umbral:
            return False

        origenes_distintos = {t.origen for t in triggers}
        if len(origenes_distintos) < umbral:
            return False

        hoy = datetime.now(timezone.utc)
        ventana = timedelta(days=self.VENTANA_DIAS_DECAY)
        tiene_senial_fresca = any(
            t.fecha_evento is not None and (hoy - t.fecha_evento) <= ventana
            for t in triggers
        )

        return tiene_senial_fresca
