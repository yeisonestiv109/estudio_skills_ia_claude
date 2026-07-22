"""
Modelos de Dominio y Contratos (Core) — El Prospector.

Transcripción fiel de `10-Memoria_Consolidada/modelos_dominio_core.md` (v3.0).

REGLA DE ARQUITECTURA ABSOLUTA:
    Estos modelos pertenecen al Core. Son estériles y agnósticos. No importan
    ninguna librería de adaptador (TheirStack, Playwright, feedparser, sodapy).
    Si un modelo importa algo externo, es una violación hexagonal inmediata.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# ---------------------------------------------------------------------------
# ENUMS COMPARTIDOS (Vocabulario Controlado del Dominio)
# ---------------------------------------------------------------------------
class CategoriaEmpresa(str, Enum):
    """
    Taxonomía de empresa detectada por el LLM (Motor 1).
    Alimenta la AdapterRoutingPolicy para decidir qué adaptadores activar.
    Basada en investigación de mercado B2B Tech LATAM 2026.
    """

    SAAS_B2B_HORIZONTAL = "SAAS_B2B_HORIZONTAL"  # CRM, ERP, HRIS, Marketing Automation
    SAAS_B2B_VERTICAL = "SAAS_B2B_VERTICAL"  # SaaS sectorial semi-regulado
    AGENCIA_IT = "AGENCIA_IT"  # Fábrica de software, desarrollo a medida
    CONSULTORA_IT = "CONSULTORA_IT"  # System integrators, transformación digital
    BPO_MANAGED = "BPO_MANAGED"  # Operación continua, outsourcing
    CIBERSEGURIDAD = "CIBERSEGURIDAD"  # Producto o servicio de seguridad
    AI_ML_PLATFORM = "AI_ML_PLATFORM"  # LLM tooling, MLOps, agentic frameworks
    REGULADO_FINTECH = "REGULADO_FINTECH"  # PSP, lending, cripto, open banking
    REGULADO_HEALTHTECH = "REGULADO_HEALTHTECH"  # EHR, diagnóstico, telemedicina
    GOVTECH_REGTECH = "GOVTECH_REGTECH"  # Gobierno electrónico, compliance automatizado


class TamanoEmpresa(str, Enum):
    STARTUP = "STARTUP"  # < 50 empleados
    SME = "SME"  # 50–200 empleados
    MID_MARKET = "MID_MARKET"  # 200–1000 empleados
    ENTERPRISE = "ENTERPRISE"  # > 1000 empleados


class BaseLegal(str, Enum):
    # Bases legales VÁLIDAS bajo la Ley 1581/2012 (Colombia).
    # NO existe "interés legítimo" (eso es GDPR europeo y NO aplica en Colombia):
    # la regla es consentimiento previo, expreso e informado (SIC como autoridad).
    CONSENTIMIENTO_EXPLICITO = "CONSENTIMIENTO_EXPLICITO"  # Regla general (Art. 9)
    EJECUCION_CONTRATO = "EJECUCION_CONTRATO"  # Relación contractual existente
    DATO_PUBLICO = "DATO_PUBLICO"  # Excepción de dato de fuente pública (Art. 10)


class NivelConfianza(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class TipoTrigger(str, Enum):
    """
    Naturaleza causal de una señal (Signal-Based Selling v5.0).

    CAUSA  → causa raíz / "capacity shock": el evento que crea la necesidad
             estructural (ej. un contrato SECOP ganado sin equipo suficiente
             para ejecutarlo). Su relevancia decae lento: ventana de decay de
             90 días (la aplica ScoreTriggerPolicy).
    EFECTO → síntoma observable derivado de esa causa (ej. vacantes técnicas
             abiertas). Señal de segundo orden, más volátil: ventana de decay
             de 45 días.

    Las ventanas de decay diferenciadas (CAUSA 90d, EFECTO 45d) las aplica
    ScoreTriggerPolicy, no este enum.
    """

    CAUSA = "CAUSA"
    EFECTO = "EFECTO"


class TierUrgencia(str, Enum):
    """
    Tier de urgencia de una señal (Signal-Based Selling v5.0), del más al
    menos urgente.

    TIER_0 → Sangrado Activo: dolor agudo en curso, máxima prioridad.
    TIER_1 → Reorganización: cambio estructural reciente que abre ventana.
    TIER_2 → Dolor latente / contexto: señal de fondo, no urgente por sí sola.
    TIER_3 → Contexto débil: señal marginal, casi ruido.
    """

    TIER_0 = "TIER_0"
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"


class OrigenTrigger(str, Enum):
    WAPPALYZER = "WAPPALYZER"
    THEIRSTACK = "THEIRSTACK"
    SECOP_SOCRATA = "SECOP_SOCRATA"
    GOOGLE_ALERTS = "GOOGLE_ALERTS"
    GITHUB = "GITHUB"
    PROPUESTA_VALOR = "PROPUESTA_VALOR"  # Capa 2 Negative ICP — PropuestaValorAdapter


class EstadoCorreo(str, Enum):
    VERIFICADO = "verificado"
    INFERIDO = "inferido"
    NO_RESUELTO = "no_resuelto"
    MANUAL = "manual"
    REBOTADO = "rebotado"


class Seniority(str, Enum):
    IC = "IC"  # Individual Contributor
    LEAD = "LEAD"
    MANAGER = "MANAGER"
    DIRECTOR = "DIRECTOR"
    VP = "VP"
    C_LEVEL = "C_LEVEL"


class AutoridadDecision(str, Enum):
    DECISION_MAKER = "DECISION_MAKER"
    INFLUENCER = "INFLUENCER"
    GATEKEEPER = "GATEKEEPER"
    UNKNOWN = "UNKNOWN"


# Centinela explícito de "país no reportado por la fuente" (Motor 2, waterfall
# geográfico — ver PoliticaValidacionGeografica). NUNCA usar un país real como
# valor por defecto ante dato ausente (bug corregido: caso Parcero/UK, donde
# TheirStack no reportó country_code y el adaptador asumía "CO" en silencio).
# No es un código ISO real: "XX" es el rango reservado ISO 3166-1 para "código
# de usuario/no asignado", por lo que no colisiona con ningún país verdadero.
PAIS_DESCONOCIDO: str = "XX"


class EstadoEmpresa(str, Enum):
    """
    Ciclo de vida de una Empresa en el pipeline de El Prospector.

    DESCUBIERTA    → creada por PuertoDescubridorEmpresas (Caso B). Aún no
                     validada manualmente. Sus triggers son candidatos, no
                     señales confirmadas.
    VERIFICADA     → validada por el equipo comercial o por cruce de datos.
                     Estado por defecto para empresas creadas manualmente.
    EN_PIPELINE    → está siendo trabajada activamente (outbound iniciado).
    ARCHIVADA      → descartada del pipeline activo (no es ICP, ya es cliente,
                     etc.). Se mantiene para auditoría y evitar re-descubrimiento.
    """

    DESCUBIERTA = "DESCUBIERTA"
    VERIFICADA = "VERIFICADA"
    EN_PIPELINE = "EN_PIPELINE"
    ARCHIVADA = "ARCHIVADA"


class EstadoConsensoTamano(str, Enum):
    """
    Resultado de PoliticaCorroboracionTamano (Motor 2 — waterfall de tamaño).

    CONSENSO      → al menos 2 orígenes distintos coincidieron en el mismo
                    TamanoEmpresa (o en rangos adyacentes). El tamaño es confiable.
    SIN_CONSENSO  → hay 2+ estimaciones pero NO coinciden entre sí. El tamaño
                    NO se fuerza; la empresa debe ir a revisión manual en vez
                    de arrastrar un dato firmográfico falso.
    SIN_DATOS     → no llegó ninguna estimación cruda (lista vacía). No hay
                    base para pronunciarse.
    """

    CONSENSO = "CONSENSO"
    SIN_CONSENSO = "SIN_CONSENSO"
    SIN_DATOS = "SIN_DATOS"


class ResultadoExclusionCompetidor(str, Enum):
    """
    Resultado de PoliticaExclusionCompetidores (Motor 2 — Negative ICP).

    PERMITIDO                    → la empresa candidata no compite con el
                                    modelo de negocio del cliente. Continúa
                                    en el pipeline sin restricciones.
    EXCLUIDO_DURO                → misma CategoriaEmpresa que el cliente
                                    (hard exclusion). Se descarta ANTES de
                                    gastar cualquier crédito de M3 en ella.
    REQUIERE_ANALISIS_SEMANTICO  → categorías vecinas/ambiguas (conditional
                                    exclusion). La política pura no puede
                                    decidir sola; requiere la Capa 2
                                    (PuertoClasificadorPropuestaValor) antes
                                    de aprobar o descartar.
    PENDIENTE_REVISION_MANUAL    → la Capa 2 no pudo determinar es_vendor_it
                                    (scraping falló, LLM no disponible, texto
                                    insuficiente). Fail-CLOSED (bug corregido,
                                    caso Parcero/UK): un análisis indeterminado
                                    NUNCA se trata como "confirmado no
                                    competidor". Va a cola manual en vez de
                                    PERMITIDO automático.
    """

    PERMITIDO = "PERMITIDO"
    EXCLUIDO_DURO = "EXCLUIDO_DURO"
    REQUIERE_ANALISIS_SEMANTICO = "REQUIERE_ANALISIS_SEMANTICO"
    PENDIENTE_REVISION_MANUAL = "PENDIENTE_REVISION_MANUAL"


class EstadoValidacionGeografica(str, Enum):
    """
    Resultado de PoliticaValidacionGeografica (Motor 2 — waterfall geográfico).

    PERMITIDO      → el país de la empresa candidata coincide con la
                     geografía del ICP (o el ICP no restringe geografía).
    EXCLUIDO       → el país candidato es conocido y NO coincide con la
                     geografía del ICP (caso Parcero: HQ en Londres vs.
                     ICP="CO").
    INDETERMINADO  → no hay ningún país confiable para evaluar (ni
                     TheirStack ni la Capa 2 semántica lo resolvieron).
                     Fail-CLOSED: nunca se traduce en PERMITIDO automático.
    """

    PERMITIDO = "PERMITIDO"
    EXCLUIDO = "EXCLUIDO"
    INDETERMINADO = "INDETERMINADO"


# ---------------------------------------------------------------------------
# 1. ManifiestoICP (Perfil de Cliente Ideal) — salida del Motor 1
# ---------------------------------------------------------------------------
class ManifiestoICP(BaseModel):
    """
    Salida estructurada del Analizador de Intención (Motor 1).
    Los pesos de scoring NO pertenecen a este modelo; viven en ScoringPolicy.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    dolor_operativo: Optional[str] = Field(
        default=None,
        description="Texto libre del dolor. Requerido si pain_es_accionable=True.",
    )
    pain_es_accionable: bool = Field(
        ...,
        description="False bloquea el pipeline en Gate A.",
    )
    anclaje_tecnologico: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Debe contener ÚNICAMENTE nombres OFICIALES COMPLETOS de lenguajes, herramientas "
            "o vendors, sin siglas. Ejemplos correctos: 'Amazon Web Services', "
            "'Google Cloud Platform', 'Python', 'Kubernetes', 'PostgreSQL', 'Snowflake'. "
            "PROHIBIDO usar siglas (NO usar 'AWS', 'GCP', 'K8s'; usar el nombre completo). "
            "PROHIBIDO incluir abstracciones, procesos o metodologías como: "
            "Microservicios, ETL, ERP, QA, Frontend, Backend, DevOps, Cloud, Escalabilidad. "
            "Solo nombres propios completos de software o plataformas."
        ),
    )
    categoria_empresa: CategoriaEmpresa = Field(
        ...,
        description="Taxonomía detectada por el LLM. Alimenta AdapterRoutingPolicy.",
    )
    vertical: str = Field(
        ...,
        description="Vertical de negocio en texto libre. Ej: 'Retail', 'Salud'.",
    )
    es_gov_facing: bool = Field(
        default=False,
        description="True si la empresa vende o entrega servicios al gobierno. Activa SecopSocrataAdapter.",
    )
    cargos_decisores: list[str] = Field(..., min_length=1)
    tamano_empresa: TamanoEmpresa = Field(...)
    geografia: str | None = Field(
        default=None,
        description=(
            "Debe ser estrictamente el código ISO Alpha-2 del país, por ejemplo "
            "'US' para Estados Unidos, 'CO' para Colombia. Nunca el nombre completo."
        ),
    )
    base_legal: BaseLegal = Field(
        ...,
        description="Cumplimiento Habeas Data Ley 1581.",
    )
    fecha_generacion: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @model_validator(mode="after")
    def validar_coherencia_dolor(self) -> "ManifiestoICP":
        if self.pain_es_accionable and not self.dolor_operativo:
            raise ValueError(
                "Estado incoherente: pain_es_accionable=True requiere dolor_operativo no nulo."
            )
        return self


# ---------------------------------------------------------------------------
# 2. Empresa — entidad principal del pre-CRM (inmutable por diseño DDD)
# ---------------------------------------------------------------------------
class Empresa(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    nombre: str = Field(..., min_length=1)
    dominio: str = Field(..., description="Ej: acme.com. Clave para Wappalyzer.")
    nit_o_tax_id: Optional[str] = Field(
        default=None, description="NIT colombiano u equivalente."
    )
    tamano: TamanoEmpresa = Field(...)
    vertical: str = Field(...)
    pais: str = Field(default="CO")
    ciudad: Optional[str] = Field(default=None)
    estado: EstadoEmpresa = Field(
        default=EstadoEmpresa.VERIFICADA,
        description=(
            "Ciclo de vida de la empresa en el pipeline. "
            "Las empresas creadas por PuertoDescubridorEmpresas se marcan como DESCUBIERTA. "
            "El valor por defecto (VERIFICADA) preserva compatibilidad con registros existentes."
        ),
    )
    fecha_captura: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# 2.1 EstimacionTamano — ValueObject para el waterfall de tamaño (Motor 2)
# ---------------------------------------------------------------------------
class EstimacionTamano(BaseModel):
    """
    ValueObject inmutable: una estimación CRUDA de tamaño de empresa,
    reportada por UN solo origen (adaptador).

    Diseño (investigación "Waterfall Enrichment" / Enlyft, ver
    10-Memoria_Consolidada/tecnico/prospector-m3-m4-design.md y hallazgos de
    auditoría): ningún adaptador individual es confiable por sí solo para
    firmográficos. PoliticaCorroboracionTamano recibe una list[EstimacionTamano]
    de distintos orígenes y exige consenso de al menos 2 antes de aceptar un
    TamanoEmpresa como válido.

    No reemplaza a Trigger: una EstimacionTamano no es una señal de compra,
    es un dato firmográfico crudo. Se modela por separado para no forzar a
    TriggerAggregationPolicy (que evalúa señales de intención) a interpretar
    también datos de tamaño.
    """

    model_config = ConfigDict(frozen=True)

    origen: OrigenTrigger = Field(
        ..., description="Adaptador que produjo esta estimación (mismo Enum que Trigger)."
    )
    tamano_estimado: TamanoEmpresa = Field(
        ..., description="Rango de tamaño que el origen infiere para la empresa."
    )
    confianza: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "Confianza propia del origen en su estimación (0.0-1.0). Por defecto "
            "1.0 para orígenes que no distinguen grados de certeza."
        ),
    )


# ---------------------------------------------------------------------------
# 3. Trigger (Señal de Mercado) — capturado por el PuertoFuenteTriggers
# ---------------------------------------------------------------------------
class Trigger(BaseModel):
    """
    Señal de mercado. Un lead nunca se aprueba con un solo Trigger;
    la evaluación cruzada ocurre en TriggerAggregationPolicy.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    empresa_id: uuid.UUID = Field(
        ..., description="FK a Empresa. Obligatorio para cruce de señales."
    )
    origen: OrigenTrigger = Field(...)
    nivel_confianza: NivelConfianza = Field(...)
    descripcion: str = Field(
        ..., min_length=1, description="Descripción legible del trigger detectado."
    )
    fecha_captura: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fecha_evento: Optional[datetime] = Field(
        default=None,
        description="Fecha del evento original (ej. fecha del contrato SECOP). Obligatorio para calcular data decay.",
    )
    tipo_trigger: TipoTrigger = Field(
        default=TipoTrigger.EFECTO,
        description=(
            "Naturaleza causal de la señal (Signal-Based Selling v5.0). Por "
            "defecto EFECTO (síntoma observable) para no romper adaptadores "
            "que crean Trigger sin especificarlo. Los adaptadores que detectan "
            "una causa raíz (ej. SECOP: contrato ganado) lo fijan a CAUSA. "
            "Determina la ventana de decay que aplica ScoreTriggerPolicy "
            "(CAUSA 90d, EFECTO 45d)."
        ),
    )
    tier_urgencia: TierUrgencia = Field(
        default=TierUrgencia.TIER_2,
        description=(
            "Tier de urgencia de la señal (Signal-Based Selling v5.0). Por "
            "defecto TIER_2 (dolor latente/contexto) para no romper adaptadores "
            "que crean Trigger sin especificarlo. ScoreTriggerPolicy lo traduce "
            "a puntos de score y lo usa para elegir el tier final del prospecto."
        ),
    )


# ---------------------------------------------------------------------------
# 4. Decisor (Contacto) — relación N:1 con Empresa
# ---------------------------------------------------------------------------
class Decisor(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    empresa_id: uuid.UUID = Field(..., description="FK a Empresa.")
    nombre: str = Field(...)
    cargo_original: str = Field(..., description="Texto exacto del cargo en la fuente.")
    cargo_normalizado: str = Field(..., description="Cargo estandarizado internamente.")
    seniority: Seniority = Field(...)
    autoridad_decision: AutoridadDecision = Field(default=AutoridadDecision.UNKNOWN)
    correo: Optional[EmailStr] = Field(
        default=None,
        description="Ausencia válida. Pasa a estado no_resuelto.",
    )
    estado_correo: EstadoCorreo = Field(default=EstadoCorreo.NO_RESUELTO)
    ultima_verificacion: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    confianza_dato: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confianza del dato entre 0.0 y 1.0.",
    )


# ---------------------------------------------------------------------------
# 5. ProspectoCalificado — Contrato de transición Motor 2 → Motor 3
# ---------------------------------------------------------------------------
class ProspectoCalificado(BaseModel):
    """
    Contrato de transición M2 → M3. Inmutable.

    Es todo lo que el Motor 3 necesita saber del trabajo previo del pipeline:
    la Empresa ya calificada por TriggerAggregationPolicy, sus Triggers
    validados y el ManifiestoICP que originó la búsqueda.

    Nota de diseño: PuertoEnriquecedorContactos NO recibe este DTO completo.
    El orquestador extrae `empresa` y `manifiesto.cargos_decisores` para
    llamar a `enriquecer(empresa, cargos)` (firma stateless). Los `triggers`
    no los usa el enriquecedor; viajan hacia el Motor 4 para personalizar
    el mensaje de outbound.
    """

    model_config = ConfigDict(frozen=True)

    empresa: Empresa = Field(
        ..., description="Empresa ya calificada por TriggerAggregationPolicy."
    )
    triggers: list[Trigger] = Field(
        ...,
        min_length=1,
        description=(
            "Señales validadas por el Motor 2. No las usa el enriquecedor; "
            "viajan hacia el Motor 4 para personalizar el mensaje."
        ),
    )
    manifiesto: ManifiestoICP = Field(
        ...,
        description="Fuente de cargos_decisores: qué perfiles busca el enriquecedor.",
    )


# ===========================================================================
# MOTOR 4 (Outbound RAG) — Modelos y enums
# Diseño: 10-Memoria_Consolidada/tecnico/prospector-m4-design.md §5
# ===========================================================================
class EstadoMensaje(str, Enum):
    """Ciclo de vida de un Mensaje outbound (Motor 4)."""

    BORRADOR = "BORRADOR"  # generado por el LLM, aún no revisado
    APROBADO = "APROBADO"  # HITL dio visto bueno
    RECHAZADO_HITL = "RECHAZADO_HITL"  # un humano lo descartó
    ENVIADO = "ENVIADO"  # entregado al PuertoEnvioCorreo
    ERROR_REDACCION = "ERROR_REDACCION"  # el LLM falló al redactar


class ResultadoEnvio(str, Enum):
    """Resultado real reportado por el proveedor de envío (ej. webhooks Resend)."""

    ENTREGADO = "ENTREGADO"
    REBOTADO = "REBOTADO"
    DIFERIDO = "DIFERIDO"
    RECHAZADO = "RECHAZADO"
    ERROR = "ERROR"


class ContextoRAG(BaseModel):
    """
    Evidencia citable recuperada por el PuertoContextoRAG (Tavily/Perplexity).
    Fundamenta el mensaje y previene alucinación del LLM. Inmutable.
    """

    model_config = ConfigDict(frozen=True)

    evidencias: list[str] = Field(
        default_factory=list,
        description="Snippets citables alineados con los triggers de la empresa.",
    )
    fuentes: list[str] = Field(
        default_factory=list,
        description="URLs de respaldo. Trazabilidad anti-alucinación.",
    )


class Mensaje(BaseModel):
    """
    Borrador tipado de un correo outbound (Motor 4). Inmutable.

    Las transiciones de estado NO mutan el objeto: se crea una copia con
    model_copy(update={...}). El estado por defecto es BORRADOR — un Mensaje
    nunca nace enviado.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    decisor_id: uuid.UUID = Field(..., description="FK al Decisor destinatario.")
    asunto: str = Field(..., min_length=1)
    cuerpo: str = Field(..., min_length=1)
    estado: EstadoMensaje = Field(default=EstadoMensaje.BORRADOR)
    fuentes_citadas: list[str] = Field(
        default_factory=list,
        description="URLs del ContextoRAG usadas en el mensaje. Trazabilidad.",
    )


class PaqueteOutbound(BaseModel):
    """
    Contrato de transición M3 → M4. Inmutable.

    Empaqueta el ProspectoCalificado (Empresa + Triggers + ManifiestoICP) más
    los decisores YA filtrados por UmbralCalidadDecisor (solo VERIFICADO/INFERIDO
    con confianza_dato >= 0.7). Ver prospector-m4-design.md §3.

    Los Triggers, que en M3 solo viajaban como metadata, aquí SÍ se usan: son
    el gancho de personalización del mensaje.
    """

    model_config = ConfigDict(frozen=True)

    prospecto: ProspectoCalificado = Field(
        ..., description="Empresa + Triggers + ManifiestoICP proveniente de M2/M3."
    )
    decisores_aptos: list[Decisor] = Field(
        ...,
        min_length=1,
        description="Salida de UmbralCalidadDecisor.particionar()[0] (aptos para M4).",
    )
