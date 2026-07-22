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
    AutoridadDecision,
    BaseLegal,
    CategoriaEmpresa,
    Decisor,
    EstadoConsensoTamano,
    EstadoCorreo,
    EstadoMensaje,
    EstadoValidacionGeografica,
    EstimacionTamano,
    ManifiestoICP,
    Mensaje,
    OrigenTrigger,
    PAIS_DESCONOCIDO,
    ResultadoEnvio,
    ResultadoExclusionCompetidor,
    Seniority,
    TamanoEmpresa,
    TierUrgencia,
    TipoTrigger,
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
            CategoriaEmpresa.CIBERSEGURIDAD,  # Ocultan stack deliberadamente
            CategoriaEmpresa.REGULADO_FINTECH,  # Core bancario no es web-visible
            CategoriaEmpresa.REGULADO_HEALTHTECH,
            CategoriaEmpresa.AI_ML_PLATFORM,  # Infraestructura no frontal
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
            CategoriaEmpresa.CIBERSEGURIDAD,  # Security teams suelen tener repos públicos
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


class UmbralCalidadDecisor:
    """
    Gate de calidad entre Motor 3 y Motor 4 (Enriquecimiento → Outbound).

    Protege la reputación de dominio: ningún correo dudoso se envía de forma
    automática. Un Decisor solo es apto para el Motor 4 si cumple AMBAS
    condiciones: confianza_dato >= CONFIANZA_MINIMA y estado_correo en un
    estado considerado suficientemente confiable.

    Regla de negocio (mecanismo financiero, no solo de calidad): cada correo
    REBOTADO enviado degrada la métrica de entregabilidad del dominio ante los
    proveedores de correo, afectando a TODOS los envíos futuros. Se prefiere
    descartar un contacto dudoso (barato y local) que arriesgar el canal
    completo (costoso y sistémico).
    """

    CONFIANZA_MINIMA: float = 0.7
    ESTADOS_APTOS: frozenset[EstadoCorreo] = frozenset(
        {
            EstadoCorreo.VERIFICADO,
            EstadoCorreo.INFERIDO,
        }
    )

    def es_apto_para_outbound(self, decisor: Decisor) -> bool:
        """
        True solo si el decisor cumple:
          1. confianza_dato >= 0.7
          2. estado_correo pertenece a {VERIFICADO, INFERIDO}

        Todo lo demás (REBOTADO, NO_RESUELTO, MANUAL, o INFERIDO con
        confianza_dato < 0.7) se descarta del envío automático y cae a la
        cola de trabajo manual.
        """
        return (
            decisor.confianza_dato >= self.CONFIANZA_MINIMA
            and decisor.estado_correo in self.ESTADOS_APTOS
        )

    def particionar(
        self, decisores: list[Decisor]
    ) -> tuple[list[Decisor], list[Decisor]]:
        """
        Separa (aptos_para_m4, cola_manual) en una sola pasada.
        No lanza excepciones; una lista vacía retorna ([], []).
        """
        aptos: list[Decisor] = []
        manual: list[Decisor] = []
        for decisor in decisores:
            if self.es_apto_para_outbound(decisor):
                aptos.append(decisor)
            else:
                manual.append(decisor)
        return aptos, manual


# ===========================================================================
# MOTOR 4 (Outbound RAG) — Políticas puras
# Diseño: 10-Memoria_Consolidada/tecnico/prospector-m4-design.md §4, §6, §7
# ===========================================================================
class PoliticaSeleccionMejorDecisor:
    """
    Selecciona el ÚNICO decisor a contactar por empresa (Motor 4 §4).

    Resuelve el anti-patrón spray-and-pray detectado en el piloto (5 VPs de
    Rappi). Determinista y pura. Criterio de orden descendente:
        1. autoridad_decision  (DECISION_MAKER > INFLUENCER > GATEKEEPER > UNKNOWN)
        2. confianza_dato       (mayor gana)
        3. seniority            (C_LEVEL > VP > ... > IC)

    Precondición (responsabilidad del orquestador): todos los decisores de la
    lista pertenecen a la MISMA empresa.
    """

    _RANK_AUTORIDAD: dict[AutoridadDecision, int] = {
        AutoridadDecision.DECISION_MAKER: 3,
        AutoridadDecision.INFLUENCER: 2,
        AutoridadDecision.GATEKEEPER: 1,
        AutoridadDecision.UNKNOWN: 0,
    }

    _RANK_SENIORITY: dict[Seniority, int] = {
        Seniority.C_LEVEL: 6,
        Seniority.VP: 5,
        Seniority.DIRECTOR: 4,
        Seniority.MANAGER: 3,
        Seniority.LEAD: 2,
        Seniority.IC: 1,
    }

    def seleccionar(self, decisores: list[Decisor]) -> Decisor | None:
        """
        Retorna el mejor decisor de la lista, o None si la lista está vacía.
        No lanza excepción.
        """
        if not decisores:
            return None
        return max(
            decisores,
            key=lambda d: (
                self._RANK_AUTORIDAD.get(d.autoridad_decision, 0),
                d.confianza_dato,
                self._RANK_SENIORITY.get(d.seniority, 0),
            ),
        )


class PoliticaFronteraLegal:
    """
    Gate de cumplimiento Habeas Data (Ley 1581/2012, Colombia) — Motor 4 §7.1.

    NO sustituye la asesoría legal real (pendiente en validacion-fuentes.md §7).
    Codifica el mínimo verificable por software: que exista una base legal
    declarada y válida bajo la Ley 1581.
    """

    BASES_LEGALES_VALIDAS: frozenset[BaseLegal] = frozenset(
        {
            BaseLegal.DATO_PUBLICO,
            BaseLegal.EJECUCION_CONTRATO,
            BaseLegal.CONSENTIMIENTO_EXPLICITO,
        }
    )

    def puede_contactar(self, manifiesto: ManifiestoICP) -> bool:
        """True solo si el manifiesto declara una base legal válida bajo Ley 1581."""
        return manifiesto.base_legal in self.BASES_LEGALES_VALIDAS


class PoliticaFronterasEnvio:
    """
    Compuerta de reputación de dominio (Motor 4 §7.2).

    Ningún Mensaje llega al PuertoEnvioCorreo sin cumplir SIMULTÁNEAMENTE:
        1. base legal OK (evaluada por PoliticaFronteraLegal, se pasa el bool),
        2. estado == APROBADO (un humano revisó el borrador — HITL),
        3. pacing no excedido (rate limiting anti-spam por dominio/día).
    """

    MAX_ENVIOS_POR_DOMINIO_DIA: int = 20

    def es_enviable(
        self, mensaje: Mensaje, base_legal_ok: bool, enviados_hoy: int
    ) -> bool:
        """
        True solo si se cumplen las tres condiciones. Determinista, sin efectos.
        """
        return (
            base_legal_ok
            and mensaje.estado == EstadoMensaje.APROBADO
            and enviados_hoy < self.MAX_ENVIOS_POR_DOMINIO_DIA
        )


class PoliticaRegistroRebote:
    """
    Lazo de retroalimentación de rebotes (Motor 4 §6).

    Traduce el ResultadoEnvio real a un cambio de EstadoCorreo del Decisor.
    Es el mecanismo que permite medir el bounce rate real (KPI pendiente de
    M3 §3.5). Decisor no es inmutable, pero por consistencia se retorna una
    copia vía model_copy(update=...) para no mutar el objeto de entrada.
    """

    def aplicar(self, decisor: Decisor, resultado: ResultadoEnvio) -> Decisor:
        """
        REBOTADO  → estado_correo=REBOTADO, confianza_dato=0.0 (sale del pipeline).
        Cualquier otro resultado → retorna el decisor sin cambios.
        No lanza excepción.
        """
        if resultado == ResultadoEnvio.REBOTADO:
            return decisor.model_copy(
                update={
                    "estado_correo": EstadoCorreo.REBOTADO,
                    "confianza_dato": 0.0,
                }
            )
        return decisor


# ===========================================================================
# MOTOR 2 (Discovery) — Políticas de Corroboración de Tamaño y Exclusión
# de Competidores. Diseño: investigación "Waterfall Enrichment" / "Negative
# ICP" (10-Memoria_Consolidada/tecnico/prospector-m3-m4-design.md, sesión de
# afinamiento del Motor 2 post-piloto TBBC).
# ===========================================================================
class PoliticaCorroboracionTamano:
    """
    Waterfall de tamaño (Motor 2). Ningún origen individual (TheirStack,
    Wappalyzer, GitHub, etc.) es confiable por sí solo para TamanoEmpresa —
    ver hallazgos de la investigación de mercado (Enlyft: "predicting company
    size from sparse, multi-source signals"; LinkedIn headcount decay ~22%/año).

    Regla de negocio: un TamanoEmpresa solo se acepta como válido si al menos
    MINIMO_ORIGENES estimaciones de orígenes DISTINTOS corroboran el mismo
    rango, o rangos adyacentes en la escala ordinal STARTUP<SME<MID_MARKET<
    ENTERPRISE (mismo principio de "tier distance" de la investigación:
    un desacuerdo de 1 escalón es ruido de frontera; un desacuerdo de 2+
    escalones es una señal real de conflicto, no de consenso).

    Mismo principio que TriggerAggregationPolicy (mínimo 2 orígenes distintos
    antes de confiar), aplicado a un campo firmográfico en vez de a intención
    de compra.
    """

    MINIMO_ORIGENES: int = 2
    MAX_DISTANCIA_TIER_PARA_CONSENSO: int = 1

    _ORDEN_TIER: dict[TamanoEmpresa, int] = {
        TamanoEmpresa.STARTUP: 0,
        TamanoEmpresa.SME: 1,
        TamanoEmpresa.MID_MARKET: 2,
        TamanoEmpresa.ENTERPRISE: 3,
    }

    def corroborar(
        self, estimaciones: list[EstimacionTamano]
    ) -> tuple[EstadoConsensoTamano, TamanoEmpresa | None]:
        """
        Retorna (EstadoConsensoTamano, TamanoEmpresa | None).

        - SIN_DATOS, None            → lista vacía.
        - SIN_CONSENSO, None         → 2+ estimaciones pero sin acuerdo dentro
                                        de MAX_DISTANCIA_TIER_PARA_CONSENSO, o
                                        menos de MINIMO_ORIGENES orígenes
                                        DISTINTOS reportaron.
        - CONSENSO, TamanoEmpresa    → hay corroboración; se retorna la MODA
                                        (el tier más frecuente; a igualdad de
                                        frecuencia, el de mayor confianza
                                        promedio) como el tamaño validado.

        No lanza excepción. Determinista y pura: no importa adaptadores.
        """
        if not estimaciones:
            return EstadoConsensoTamano.SIN_DATOS, None

        origenes_distintos = {e.origen for e in estimaciones}
        if len(origenes_distintos) < self.MINIMO_ORIGENES:
            return EstadoConsensoTamano.SIN_CONSENSO, None

        # Agrupar por tier y calcular soporte (conteo + confianza promedio).
        conteo_por_tier: dict[TamanoEmpresa, int] = {}
        confianza_por_tier: dict[TamanoEmpresa, list[float]] = {}
        for est in estimaciones:
            conteo_por_tier[est.tamano_estimado] = (
                conteo_por_tier.get(est.tamano_estimado, 0) + 1
            )
            confianza_por_tier.setdefault(est.tamano_estimado, []).append(
                est.confianza
            )

        # Candidato ganador: mayor conteo; desempate por mayor confianza promedio.
        tier_ganador = max(
            conteo_por_tier,
            key=lambda t: (
                conteo_por_tier[t],
                sum(confianza_por_tier[t]) / len(confianza_por_tier[t]),
            ),
        )
        posicion_ganador = self._ORDEN_TIER[tier_ganador]

        # El soporte debe venir de orígenes DISTINTOS, no de duplicados del mismo.
        origenes_del_soporte = {
            est.origen
            for est in estimaciones
            if abs(self._ORDEN_TIER[est.tamano_estimado] - posicion_ganador)
            <= self.MAX_DISTANCIA_TIER_PARA_CONSENSO
        }

        if len(origenes_del_soporte) < self.MINIMO_ORIGENES:
            return EstadoConsensoTamano.SIN_CONSENSO, None

        return EstadoConsensoTamano.CONSENSO, tier_ganador


class PoliticaExclusionCompetidores:
    """
    Negative ICP (Motor 2). Excluye empresas candidatas que compiten con el
    modelo de negocio del propio cliente ANTES de gastar cualquier crédito de
    Motor 3 (Apollo/Hunter) en ellas.

    Diseño de 3 cubetas (framework validado de la industria — ver
    prospector-m3-m4-design.md, sección de investigación Negative ICP):
        - Hard exclusion:  misma CategoriaEmpresa que el cliente. Nunca se
                            contacta. Decisión determinista, sin LLM.
        - Conditional:      categorías "vecinas" donde el modelo de negocio
                            puede solaparse (ej. AGENCIA_IT vs CONSULTORA_IT)
                            pero no es seguro sin leer la propuesta de valor
                            real de la empresa candidata. Delega a la Capa 2
                            (PuertoClasificadorPropuestaValor, fuera del Core).
        - Permitido:        cualquier otra combinación. Sin restricción.

    Pura: no lee sitios web, no llama LLM, no conoce Tavily ni Groq. Solo
    compara dos valores de un Enum ya calculado por el Motor 1 (categoria del
    cliente) y por el proceso de discovery (categoria de la empresa candidata,
    inferida por el mismo LLM de M1 sobre su propio texto público — detalle de
    implementación de la Capa 2, no de esta política).
    """

    # Pares de categorías cuyo modelo de negocio se solapa lo bastante como
    # para requerir análisis semántico antes de decidir (no son idénticas,
    # pero tampoco son claramente distintas). Se declara sin dirección: el
    # par (A, B) cubre tanto cliente=A/candidata=B como cliente=B/candidata=A.
    CATEGORIAS_AMBIGUAS: frozenset[frozenset[CategoriaEmpresa]] = frozenset(
        {
            frozenset({CategoriaEmpresa.AGENCIA_IT, CategoriaEmpresa.CONSULTORA_IT}),
            frozenset(
                {CategoriaEmpresa.AGENCIA_IT, CategoriaEmpresa.SAAS_B2B_HORIZONTAL}
            ),
            frozenset(
                {CategoriaEmpresa.CONSULTORA_IT, CategoriaEmpresa.AI_ML_PLATFORM}
            ),
            frozenset(
                {CategoriaEmpresa.AGENCIA_IT, CategoriaEmpresa.AI_ML_PLATFORM}
            ),
        }
    )

    def evaluar(
        self,
        categoria_cliente: CategoriaEmpresa,
        categoria_candidata: CategoriaEmpresa,
    ) -> ResultadoExclusionCompetidor:
        """
        Retorna el veredicto de exclusión determinista para el par de
        categorías dado. No lanza excepción.

        1. Categorías idénticas         → EXCLUIDO_DURO (hard exclusion).
        2. Categorías en CATEGORIAS_AMBIGUAS → REQUIERE_ANALISIS_SEMANTICO
           (conditional exclusion; el orquestador debe invocar la Capa 2
           antes de decidir).
        3. Cualquier otro par            → PERMITIDO.
        """
        if categoria_cliente == categoria_candidata:
            return ResultadoExclusionCompetidor.EXCLUIDO_DURO

        par = frozenset({categoria_cliente, categoria_candidata})
        if par in self.CATEGORIAS_AMBIGUAS:
            return ResultadoExclusionCompetidor.REQUIERE_ANALISIS_SEMANTICO

        return ResultadoExclusionCompetidor.PERMITIDO


class PoliticaValidacionGeografica:
    """
    Waterfall geográfico (Motor 2). Corrige la Falla 2 del caso Parcero: una
    empresa candidata con HQ fuera de la geografía del ICP (ej. Londres, UK)
    no debe calificar solo porque contrata remoto en LATAM o menciona
    tecnologías del stack objetivo.

    Pura y determinista: recibe el país candidato YA resuelto por el
    orquestador (típicamente el primero disponible en el waterfall
    Empresa.pais (TheirStack) → PropuestaValorAdapter.pais_hq() semántico) y
    lo cruza contra manifiesto.geografia. No conoce adaptadores ni hace red.

    Fail-CLOSED (mismo principio que ResultadoExclusionCompetidor.
    PENDIENTE_REVISION_MANUAL): un país candidato desconocido (PAIS_DESCONOCIDO
    o None) NUNCA se traduce en PERMITIDO automático — se retorna INDETERMINADO
    para que el orquestador lo mande a revisión manual en vez de asumir que
    "sin dato de país" significa "país correcto".
    """

    def evaluar(
        self, pais_candidato: str | None, geografia_icp: str | None
    ) -> EstadoValidacionGeografica:
        """
        Retorna el veredicto geográfico para el par (pais_candidato, geografia_icp).

        1. Si el ICP no restringe geografía (geografia_icp es None/vacío)
           → PERMITIDO: no hay criterio contra el cual comparar.
        2. Si el país candidato es desconocido (None, cadena vacía, o el
           centinela PAIS_DESCONOCIDO) → INDETERMINADO (fail-closed).
        3. Si ambos códigos (normalizados a mayúsculas) coinciden → PERMITIDO.
        4. Cualquier otro caso (países conocidos y distintos) → EXCLUIDO.

        No lanza excepción. No importa adaptadores.
        """
        if not geografia_icp or not geografia_icp.strip():
            return EstadoValidacionGeografica.PERMITIDO

        if not pais_candidato or pais_candidato.strip().upper() == PAIS_DESCONOCIDO:
            return EstadoValidacionGeografica.INDETERMINADO

        if pais_candidato.strip().upper() == geografia_icp.strip().upper():
            return EstadoValidacionGeografica.PERMITIDO

        return EstadoValidacionGeografica.EXCLUIDO


# ===========================================================================
# MOTOR 2 (Scoring de Urgencia) — Signal-Based Selling v5.0
# Reemplaza el bool de TriggerAggregationPolicy por un score numérico de
# urgencia con decay diferencial por naturaleza de la señal (CAUSA 90d,
# EFECTO 45d). Diseño: sesión "Signal-Based Selling" post-piloto TBBC.
# ===========================================================================
class ScoreTriggerPolicy:
    """
    Scoring de urgencia de un prospecto (Signal-Based Selling v5.0).

    En vez de un booleano "¿cruza el mínimo de vectores?" (TriggerAggregation
    Policy), esta política acumula un SCORE numérico de urgencia ponderando
    cada trigger por su TierUrgencia y aplicando un decay lineal por el tiempo
    transcurrido desde el evento — decay diferenciado según la naturaleza de
    la señal: una CAUSA raíz ("capacity shock", ej. un contrato SECOP ganado)
    envejece más lento (90 días) que un EFECTO observable (ej. una vacante
    abierta, 45 días).

    Diseño (regla del 74% de SHiFT!): el presupuesto caro de Motor 3
    (Apollo/Hunter) debe gastarse primero en los leads de mayor urgencia. El
    score permite ordenar; el tier_final permite explicar.

    Ejemplos (con señales frescas, factor de decay ≈ 1.0):
        - Un TIER_0/CAUSA fresco (240 pts) CALIFICA solo (240 ≥ 150).
        - Dos TIER_0 frescos ≈ 480 pts (sangrado activo doble).
        - Un solo TIER_1 (90 pts) NO cruza el umbral (90 < 150): necesita
          corroboración de otra señal para calificar.

    Pura: no importa adaptadores ni hace red. Determinista salvo por el paso
    del tiempo (datetime.now), inherente al concepto de data decay.
    """

    UMBRAL_CALIFICACION: int = 150

    PUNTOS_POR_TIER: dict[TierUrgencia, int] = {
        TierUrgencia.TIER_0: 240,
        TierUrgencia.TIER_1: 90,
        TierUrgencia.TIER_2: 40,
        TierUrgencia.TIER_3: 15,
    }

    VENTANA_DECAY_DIAS: dict[TipoTrigger, int] = {
        TipoTrigger.CAUSA: 90,
        TipoTrigger.EFECTO: 45,
    }

    # Rango ordinal de urgencia: TIER_0 es el MÁS urgente (rango más bajo).
    _RANGO_URGENCIA: dict[TierUrgencia, int] = {
        TierUrgencia.TIER_0: 0,
        TierUrgencia.TIER_1: 1,
        TierUrgencia.TIER_2: 2,
        TierUrgencia.TIER_3: 3,
    }

    def _factor_decay(self, trigger: Trigger) -> float:
        """
        Factor de decay lineal en [0.0, 1.0] para un trigger.

        - Sin fecha_evento → 1.0 (no penalizar lo que no se puede fechar).
        - fecha_evento en el futuro (dias < 0) → 1.0 (no premiar ni penalizar).
        - En otro caso → max(0.0, 1.0 - dias/ventana), con ventana según
          tipo_trigger (CAUSA 90d, EFECTO 45d).
        """
        if trigger.fecha_evento is None:
            return 1.0
        dias = (datetime.now(timezone.utc) - trigger.fecha_evento).days
        if dias < 0:
            return 1.0
        ventana = self.VENTANA_DECAY_DIAS[trigger.tipo_trigger]
        return max(0.0, 1.0 - dias / ventana)

    def evaluar(
        self,
        triggers: list[Trigger],
        adaptadores_activos: list[OrigenTrigger] | None = None,
    ) -> tuple[int, TierUrgencia, bool]:
        """
        Retorna (score, tier_final, califica).

        - score        → round(Σ PUNTOS_POR_TIER[t.tier_urgencia] *
                          factor_decay(t)) sobre todos los triggers. Lista
                          vacía → 0.
        - tier_final   → el tier MÁS urgente (TIER_0 es el más urgente) entre
                          los triggers que aún contribuyen (factor de decay
                          > 0). Si ninguno contribuye (o lista vacía) →
                          TierUrgencia.TIER_3.
        - califica     → score >= UMBRAL_CALIFICACION.

        El parámetro `adaptadores_activos` se acepta por compatibilidad de
        firma con el sandbox y otras políticas del Motor 2; queda RESERVADO y
        no gatea el resultado: el umbral de score es la única compuerta de
        calificación en esta versión. No lanza excepción.
        """
        if not triggers:
            return 0, TierUrgencia.TIER_3, False

        score_acumulado = 0.0
        tiers_contribuyentes: list[TierUrgencia] = []
        for trigger in triggers:
            factor = self._factor_decay(trigger)
            score_acumulado += self.PUNTOS_POR_TIER[trigger.tier_urgencia] * factor
            if factor > 0:
                tiers_contribuyentes.append(trigger.tier_urgencia)

        score = round(score_acumulado)

        if tiers_contribuyentes:
            tier_final = min(
                tiers_contribuyentes, key=lambda tu: self._RANGO_URGENCIA[tu]
            )
        else:
            tier_final = TierUrgencia.TIER_3

        califica = score >= self.UMBRAL_CALIFICACION
        return score, tier_final, califica
