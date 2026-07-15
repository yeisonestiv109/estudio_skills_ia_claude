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


class OrigenTrigger(str, Enum):
    WAPPALYZER = "WAPPALYZER"
    THEIRSTACK = "THEIRSTACK"
    SECOP_SOCRATA = "SECOP_SOCRATA"
    GOOGLE_ALERTS = "GOOGLE_ALERTS"
    GITHUB = "GITHUB"


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
