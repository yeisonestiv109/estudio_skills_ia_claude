# Flujo Estructural: Motores 1 y 2 (El Prospector) — v6.1 (Apollo TAM + Signal-Based Selling + Auditoría Holística — 22-Jul-2026)

> **✅ ESTADO: ARQUITECTURA DE DESCUBRIMIENTO SEPARADA (v6.0, 21-Jul-2026)**
> Motor 1 usa exclusivamente **Apollo** para construir el TAM inicial basado en firmografía estricta (país, tamaño, sector). TheirStack fue degradado de Motor 1 a Motor 2, sirviendo exclusivamente como extractor de señales (vacantes). 
> **SECOP** fue optimizado con full-text search (`$q`) bajando latencia a 1s, y se implementó `pendientes.json` para persistencia humana. **RUES** fue descartado definitivamente como fuente automatizada.

Este documento destila la arquitectura técnica y operativa de los Motores 1 y 2.
**Cambio principal v6.0 (21-Jul-2026):** Separación total de concerns. M1 = Firmografía (Apollo). M2 = Señales (TheirStack, SECOP, Google Alerts). Se añade persistencia de decisiones humanas en el orquestador (`pendientes.json`).

---

## MOTOR 1: Analizador ICP + Enrutador Dinámico

**Objetivo:** Transformar lenguaje natural en un `ManifiestoICP` tipado, bloquear perfiles genéricos, y determinar qué adaptadores del Motor 2 tienen sentido según la categoría de empresa detectada.

### Puerto Requerido: `PuertoAnalizadorICP`

El Motor 1 no llama directamente a ningún LLM. Habla con la abstracción:

```python
class PuertoAnalizadorICP(ABC):
    @abstractmethod
    def analizar(self, descripcion_libre: str) -> ManifiestoICP:
        ...
```

El adaptador concreto (`ClaudeICPAdapter`, `OpenAIICPAdapter`, etc.) implementa este puerto. El Core no sabe qué LLM se usa.

### Flujo Lógico (v6.0 — corregido tras auditoría 22-Jul-2026):

> **Nota de honestidad (auditoría 22-Jul-2026):** las versiones previas de este
> documento describían un `ScoringPolicy.calcular()` con pesos ponderados
> (30% dolor, 25% tecnología, etc.) como parte del flujo del Motor 1. Esa
> clase **nunca se materializó en código** — no existe `ScoringPolicy` en
> `policies.py` ni en ningún otro módulo. Los únicos gates reales son los
> validadores Pydantic de `ManifiestoICP` (Gate A y Gate B, ambos vía
> `model_validator`/`Field(min_length=1)`, que lanzan `ValueError` y que
> `GroqICPAdapter` traduce a preguntas de clarificación). El diagrama se
> corrige para reflejar el código real; la tabla de pesos se retiene abajo
> solo como nota histórica de diseño, marcada explícitamente como no
> implementada.

```mermaid
graph TD
    A([Input: Texto libre del usuario]) -->|LLM / Groq| B(ManifiestoICP)
    B --> C{Gate A: Pydantic model_validator<br/>pain_es_accionable implica dolor_operativo}
    C -->|ValueError| D([BLOQUEO: GroqICPAdapter retorna preguntas al usuario])
    C -->|Válido| E{Gate B: Pydantic Field<br/>anclaje_tecnologico min_length=1}
    E -->|ValueError| F([BLOQUEO: pide tecnología concreta])
    E -->|Válido| J[AdapterRoutingPolicy.resolver]
    J -->|Calcula| K(Lista de Adaptadores Activos)
    K --> L([🟢 Pipeline arranca: Pasa al Motor 2])

    style A fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    style B fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px
    style L fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
```

**Nota sobre los Gates A y B (código real):**
Ambos Gates viven exclusivamente en `ManifiestoICP` (Pydantic v2), no en una
política separada:
1. **Gate A** — `@model_validator(mode="after") def validar_coherencia_dolor`:
   si `pain_es_accionable=True` y `dolor_operativo` es `None`, lanza `ValueError`.
2. **Gate B** — `anclaje_tecnologico: list[str] = Field(..., min_length=1)`:
   Pydantic rechaza el objeto si el LLM no devuelve al menos una tecnología.

En ambos casos, `GroqICPAdapter.analizar()` captura la `ValidationError` y la
traduce a un máximo de 3 preguntas de clarificación (`_generar_preguntas_clarificacion`),
conforme al contrato de `PuertoAnalizadorICP`. No hay un score numérico
intermedio: el objeto o es válido (pasa) o no lo es (bloquea con preguntas).

### AdapterRoutingPolicy — Lógica de Enrutamiento

Esta política es **lógica de dominio pura**. No conoce adaptadores concretos, solo `ManifiestoICP` y `OrigenTrigger`. Es testable unitariamente sin LLM.

**Reglas de enrutamiento derivadas de la investigación de mercado:**

```python
class AdapterRoutingPolicy:
    """
    Decide qué adaptadores del Motor 2 activar según el ManifiestoICP.
    Regla base: Google Alerts siempre activo (90% universal).
    Los demás se activan condicionalmente según la categoría de empresa.
    """

    CATEGORIAS_GOV_FACING = {
        CategoriaEmpresa.AGENCIA_IT,
        CategoriaEmpresa.CONSULTORA_IT,
        CategoriaEmpresa.BPO_MANAGED,
        CategoriaEmpresa.GOVTECH_REGTECH,
    }

    CATEGORIAS_STACK_VISIBLE = {
        CategoriaEmpresa.SAAS_B2B_HORIZONTAL,
        CategoriaEmpresa.SAAS_B2B_VERTICAL,
        CategoriaEmpresa.AGENCIA_IT,
    }

    CATEGORIAS_SIN_WAPPALYZER = {
        CategoriaEmpresa.CIBERSEGURIDAD,    # Ocultan stack deliberadamente
        CategoriaEmpresa.REGULADO_FINTECH,  # Core bancario no es web-visible
        CategoriaEmpresa.REGULADO_HEALTHTECH,
        CategoriaEmpresa.AI_ML_PLATFORM,    # Infraestructura no frontal
        CategoriaEmpresa.BPO_MANAGED,
    }

    def resolver(self, manifesto: ManifiestoICP) -> list[OrigenTrigger]:
        activos: list[OrigenTrigger] = [OrigenTrigger.GOOGLE_ALERTS]  # Siempre activo

        # TheirStack: útil para todas las categorías excepto reguladas puras (hiring discreto)
        categorias_sin_theirstack = {
            CategoriaEmpresa.REGULADO_FINTECH,
            CategoriaEmpresa.REGULADO_HEALTHTECH,
        }
        if manifesto.categoria_empresa not in categorias_sin_theirstack:
            activos.append(OrigenTrigger.THEIRSTACK)

        # SECOP: solo si el perfil tiene naturaleza gov-facing
        if manifesto.es_gov_facing or manifesto.categoria_empresa in self.CATEGORIAS_GOV_FACING:
            activos.append(OrigenTrigger.SECOP_SOCRATA)

        # Wappalyzer: solo donde el stack es web-visible y el dolor es deuda técnica de frontend/backend
        if manifesto.categoria_empresa in self.CATEGORIAS_STACK_VISIBLE \
                and manifesto.categoria_empresa not in self.CATEGORIAS_SIN_WAPPALYZER:
            activos.append(OrigenTrigger.WAPPALYZER)

        return activos
```

**Ejemplo de enrutamiento en tiempo de ejecución:**

| Input del usuario | `categoria_empresa` detectada | Adaptadores activados |
|---|---|---|
| "Fintech colombiana que necesita seguridad" | `REGULADO_FINTECH` | Google Alerts solamente |
| "Agencia IT sobrevendida con contrato gobierno" | `AGENCIA_IT` + `es_gov_facing=True` | Google Alerts + TheirStack + SECOP + Wappalyzer |
| "SaaS B2B de 100 empleados con monolito" | `SAAS_B2B_HORIZONTAL` | Google Alerts + TheirStack + Wappalyzer |
| "Consultora de ciberseguridad LATAM" | `CIBERSEGURIDAD` | Google Alerts + TheirStack |

### ScoringPolicy (Pesos) — ⚠️ DISEÑO HISTÓRICO, NUNCA IMPLEMENTADO

> Esta tabla documenta una idea de diseño temprana que **no se materializó
> en código**. No existe la clase `ScoringPolicy` en el repositorio. El Gate
> real de calidad del ManifiestoICP es binario (Pydantic válido/inválido —
> ver Gates A/B arriba), no un score ponderado. Se conserva aquí únicamente
> como referencia histórica por si se decide implementar en el futuro.

| Dimensión             | Peso |
|-----------------------|------|
| Dolor Operativo       | 30%  |
| Anclaje Tecnológico   | 25%  |
| Cargos Decisores      | 15%  |
| Vertical / Sector     | 15%  |
| Tamaño de Empresa     | 10%  |
| Geografía             |  5%  |

---

## MOTOR 2: Cascada de Triggers (Ejecución Condicional)

**Objetivo:** Ejecutar únicamente los adaptadores habilitados por el Motor 1 y capturar señales de mercado deterministas.

**Regla de calificación (v5.0):** la calificación de un prospecto la resuelve `ScoreTriggerPolicy` mediante un score numérico de urgencia (ver la sección "Signal-Based Selling v5.0" más abajo, que es la fuente de verdad). El principio de fondo se mantiene: un prospecto de dolor latente no avanza solo — se exige urgencia suficiente (una señal Tier 0 basta; una Tier 1 requiere corroboración de otro origen).

> **Contexto histórico (v3.0, superado):** la política previa `TriggerAggregationPolicy` retornaba un booleano según una regla de conteo (mínimo 2 triggers de orígenes distintos, al menos uno con `fecha_evento` < 45 días, umbral dinámico `min(2, len(adaptadores_activos))`). Fue reemplazada por el scoring numérico de `ScoreTriggerPolicy` en v5.0; se conserva en el código en paralelo hasta retirar el sandbox heredado.

### Puerto Requerido: `PuertoFuenteTriggers`

```python
class PuertoFuenteTriggers(ABC):
    @abstractmethod
    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Contrato de error: nunca propaga excepciones al Core.
        Errores de red o API → retorna [] con log interno.
        """
        ...
```

### Adaptadores y su Condición de Activación

| Adaptador                   | Siempre activo | Condición de activación                                                     | Cobertura          |
| --------------------------- | -------------- | --------------------------------------------------------------------------- | ------------------ |
| `GoogleAlertsRSSAdapter`    | ✅ SÍ           | Siempre                                                                     | 90% del árbol tech |
| `TheirStackAdapter`         | ❌ NO           | `categoria_empresa` no es REGULADO_FINTECH ni REGULADO_HEALTHTECH           | 65%                |
| `SecopSocrataAdapter`       | ❌ NO           | `es_gov_facing=True` o categoría gov-facing                                 | 40%                |
| `WappalyzerHeadlessAdapter` | ❌ NO           | `categoria_empresa` en {SAAS_B2B_HORIZONTAL, SAAS_B2B_VERTICAL, AGENCIA_IT} | 35%                |
| `GitHubAdapter`             | ❌ NO           | `categoria_empresa` en {SAAS_B2B_HORIZONTAL, SAAS_B2B_VERTICAL, AGENCIA_IT, CONSULTORA_IT, AI_ML_PLATFORM, CIBERSEGURIDAD} | ~40% (añadido en auditoría 22-Jul-2026, faltaba en esta tabla) |

#### 1. `GoogleAlertsRSSAdapter` — SIEMPRE ACTIVO
- **Implementación:** Google Alerts con salida RSS. Parseo con `feedparser`.
- **Input requerido de `Empresa`:** `nombre`.
- **Costo:** $0.
- **Triggers:** M&A, rondas de inversión, llegada nuevo C-Level técnico.
- **`nivel_confianza` ALTA:** Nuevo CTO/CIO/CDO confirmado < 6 meses.
- **`nivel_confianza` MEDIA:** Ronda de inversión anunciada.
- **`nivel_confianza` BAJA:** Mención en medios sin evento concreto.

#### 2. `TheirStackAdapter` — CONDICIONAL (activo para la mayoría)
- **Implementación:** API REST de TheirStack.
- **Input requerido de `Empresa`:** `nombre` y `dominio`.
- **Costo:** Según plan TheirStack (API key en secretos, nunca en Core).
- **Triggers:** Incompatibilidad de sistemas, crisis de talento.
- **`nivel_confianza` ALTA:** 3+ vacantes técnicas abiertas + nuevo stack adoptado simultáneamente.
- **`nivel_confianza` MEDIA:** 1-2 vacantes técnicas > 30 días.
- **`nivel_confianza` BAJA:** Vacante única, sin cruce con stack.
- **Descartado como criterio único:** ">30 días aislado" (alto volumen de ghost jobs).
- **Desactivado para:** `REGULADO_FINTECH`, `REGULADO_HEALTHTECH` (contratación discreta, alta tasa de falso positivo).

#### 3. `SecopSocrataAdapter` — CONDICIONAL (solo gov-facing)
- **Implementación:** `requests` + Socrata Open Data API (SODA) Colombia Compra Eficiente. Optimizado con full-text search `$q` en v6.0 (`$where LIKE` con wildcard inicial forzaba full scan, ~10.5s medido en vivo; `$q` es full-text indexado, ~0.5-1s medido en vivo). `$q` es fuzzy, por lo que `_buscar_contratos()` aplica un filtro de verificación en Python (`contiene_palabra_completa`) sobre los candidatos antes de convertirlos en Trigger.
- **Input requerido de `Empresa`:** `nombre` (usado como término de búsqueda `$q`; `nit_o_tax_id` no se usa hoy en la query, aunque el modelo lo expone).
- **Costo:** $0 (opcionalmente con `SECOP_APP_TOKEN` para elevar el límite de tasa).
- **Triggers:** Adjudicación de contratos a empresas tech. Extrae `es_pyme`, `urlproceso.url`, `codigo_de_categoria_principal` (UNSPSC) y `direccion_de_ejecucion_del_contrato`, incorporados a la descripción del Trigger.
- **`nivel_confianza` (código real, `_nivel_por_fecha()` en `secop_adapter.py`) — basado ÚNICAMENTE en antigüedad del contrato, SIN filtro de valor monetario:**
  - **ALTA:** contrato firmado hace ≤180 días (`_DIAS_ALTA`).
  - **MEDIA:** contrato firmado entre 180 y 365 días (`_DIAS_MEDIA`), o sin fecha parseable (default conservador).
  - **BAJA:** contrato firmado hace >365 días — omitido por defecto (`incluir_baja_confianza=False`).
- **`PuertoEstimadorTamano` (tercer origen del waterfall de tamaño, v6.0):** el campo `es_pyme` (dato verificado por la entidad contratante, no inferencia de LLM) se traduce a `SME` (si "Sí") o `MID_MARKET` (si "No"), con confianza `0.55`. Corregido en la auditoría 22-Jul-2026: el método existía pero no estaba conectado en `sandbox_tbbc_real.py::evaluar_consenso_tamano()`.
- **Desactivado para:** SaaS B2B puro, ciberseguridad, AI/ML platforms (no venden al gobierno en fase temprana) — vía `AdapterRoutingPolicy.CATEGORIAS_GOV_FACING`.

#### 4. `WappalyzerHeadlessAdapter` — CONDICIONAL (solo stack web visible)
- **Implementación real (código, `wappalyzer_adapter.py`):** SOLO `requests` + `BeautifulSoup`. Lee headers HTTP y meta tags del HTML — **NO usa Playwright ni ninguna librería `wappalyzer-next`** (corregido en auditoría 22-Jul-2026; versiones previas de este documento afirmaban lo contrario). Playwright sí existe en el proyecto, pero como fallback de `PropuestaValorAdapter` (Capa 2 del Negative ICP, no este adaptador) — ver sección "Reintentos Técnicos" más abajo.
- **Input requerido de `Empresa`:** campo `dominio`.
- **Costo:** $0.
- **Triggers:** Stack EOL en producción, ausencia de tecnologías habilitadoras.
- **`nivel_confianza` ALTA:** Stack EOL con versión mayor > 2 años en producción.
- **`nivel_confianza` MEDIA:** Stack desactualizado con soporte activo.
- **`nivel_confianza` BAJA:** Header presente sin versión detectable.
- **Fallo controlado:** dominio no resuelve, SSL error, timeout, o HTML sin patrones detectables → retorna `[]`. Al no ejecutar JavaScript (sin Playwright), un sitio SPA sin server-side rendering no expone nada más allá de headers HTTP y meta tags estáticos.
- **⚠️ LIMITACIÓN DOCUMENTADA:** Solo lee la "corteza" web (frontend, scripts). No detecta deuda técnica de backend (BD colapsadas, microservicios internos). Útil únicamente cuando el síntoma es stack frontend/web observable. Para TBBC, es señal secundaria, no primaria.
- **Desactivado para:** Ciberseguridad (ocultan stack deliberadamente), Fintech core (backend no web-visible), BPO, AI/ML platforms.

#### 5. `GitHubAdapter` — CONDICIONAL (empresas de producto/desarrollo/seguridad)
> **Nota de auditoría (22-Jul-2026):** este adaptador existe en código
> (`github_adapter.py`), está registrado en `OrigenTrigger.GITHUB` y en
> `AdapterRoutingPolicy.CATEGORIAS_CON_GITHUB`, pero nunca se documentó en
> esta sección. Se agrega aquí para que el documento sea un espejo fiel del
> código.
- **Implementación:** API pública de GitHub REST (`api.github.com`), sin autenticación obligatoria (60 req/h; con `GITHUB_TOKEN` personal, 5000 req/h).
- **Input requerido de `Empresa`:** `dominio` (se infiere el nombre de la organización de GitHub, ej. `acme.com` → `acme`).
- **Costo:** $0.
- **Triggers:** repos públicos activos (no archivados, no forks) cuyo lenguaje principal matchea `anclaje_tecnologico` del ICP.
- **`nivel_confianza` MEDIA:** hay al menos un repo activo con match de tecnología.
- **Sin match o sin repos:** no genera Trigger (retorna `[]` — ruido bajo, no se reporta BAJA).
- **Fallo controlado:** 404 (org/usuario no existe) → intenta como usuario individual antes de rendirse; 403 con `X-RateLimit-Remaining: 0` → rate limit, retorna `[]`.
- **Activado para:** `SAAS_B2B_HORIZONTAL`, `SAAS_B2B_VERTICAL`, `AGENCIA_IT`, `CONSULTORA_IT`, `AI_ML_PLATFORM`, `CIBERSEGURIDAD` (equipos de seguridad suelen tener repos públicos de herramientas).

### Flujo de Ejecución del Motor 2 (v5.0 — con exclusión de competidores, validación geográfica y scoring de urgencia):

> **Corrección de auditoría (22-Jul-2026):** el diagrama original decía
> "Empresa descubierta por TheirStack" en el nodo de entrada — obsoleto
> desde la refactorización v6.0, donde Motor 1 usa exclusivamente Apollo
> para el discovery (`ApolloDiscoveryAdapter`). Corregido abajo. El nodo TAM
> también se actualiza para incluir el tercer origen (SECOP `es_pyme`),
> conectado en código durante esta misma auditoría.

```mermaid
graph TD
    A([Empresa descubierta por Apollo — firmografía pura]) --> B

    subgraph NEGATIVE_ICP ["🛡️ NEGATIVE ICP — Cascada 2 Capas"]
        B["Capa 1 gratuita<br/>_heuristica_categoria_candidata()<br/>(keywords en nombre de empresa)"]
        B -->|"match obvio<br/>vendor IT"| EX1([🔴 EXCLUIDO_DURO<br/>0 créditos gastados])
        B -->|"sin match — caso ambiguo"| C
        C["Capa 2 con costo<br/>PropuestaValorAdapter<br/>(scraping homepage + LLM)"]
        C -->|"es_vendor_it=True"| EX2([🔴 EXCLUIDO_DURO])
        C -->|"es_vendor_it=False"| GEO
        C -->|"es_vendor_it=None<br/>(scraping falló / SPA / LLM no disponible)"| MANUAL1([🟡 PENDIENTE_REVISIÓN_MANUAL<br/>fail-closed])
    end

    subgraph GEOGRAFIA ["🌍 VALIDACIÓN GEOGRÁFICA"]
        GEO["PoliticaValidacionGeografica<br/>pais_candidato vs manifiesto.geografia<br/>waterfall: Empresa.pais → pais_hq() semántico"]
        GEO -->|"EXCLUIDO<br/>(país conocido distinto del ICP)"| EX3([🔴 DESCARTADA POR GEOGRAFÍA])
        GEO -->|"INDETERMINADO<br/>(PAIS_DESCONOCIDO / None)"| MANUAL2([🟡 PENDIENTE_REVISIÓN_MANUAL<br/>fail-closed])
        GEO -->|"PERMITIDO"| TAM
    end

    subgraph TAMANO ["📏 WATERFALL DE TAMAÑO (3 orígenes desde 22-Jul-2026)"]
        TAM["PoliticaCorroboracionTamano<br/>TheirStack.estimar_tamano()<br/>+ PropuestaValorAdapter.estimar_tamano()<br/>+ SecopSocrataAdapter.estimar_tamano()"]
        TAM -->|"CONSENSO=ENTERPRISE<br/>e ICP pide SME"| EX4([🟠 DESCARTADA POR TAMAÑO])
        TAM -->|"CONSENSO=SME o MID_MARKET<br/>o SIN_DATOS / SIN_CONSENSO"| TRIGGERS
    end

    subgraph TRIGGERS ["📡 TRIGGERS + SCORING DE URGENCIA (v5.0)"]
        TRIGGERS_RUN["Recolectar triggers<br/>(adaptadores activos por M1)"]
        TRIGGERS_RUN --> AGG["ScoreTriggerPolicy<br/>decay CAUSA 90d / EFECTO 45d<br/>+ bonus cruce de orígenes"]
        AGG -->|"score ≥ 150"| OK([🟢 CALIFICA — avanza a Motor 3])
        AGG -->|"score &lt; 150"| NOOK([⬜ Nurturing / cola futura])
    end

    TRIGGERS_RUN --> AGG

    style A fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    style OK fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style EX1 fill:#ffebee,stroke:#c62828,stroke-width:2px
    style EX2 fill:#ffebee,stroke:#c62828,stroke-width:2px
    style EX3 fill:#ffebee,stroke:#c62828,stroke-width:2px
    style EX4 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style MANUAL1 fill:#fff9c4,stroke:#f9a825,stroke-width:2px
    style MANUAL2 fill:#fff9c4,stroke:#f9a825,stroke-width:2px
    style NOOK fill:#eceff1,stroke:#546e7a,stroke-width:2px
```

**Estados de salida (v4.1 — expandidos):**

| Estado | Significado | Siguiente paso |
|---|---|---|
| 🟢 **CALIFICA** | Pasó todos los filtros y tiene señales suficientes | Avanza a Motor 3 |
| 🔴 **EXCLUIDO_DURO** | Competidor confirmado (Capa 1 o Capa 2) o país distinto del ICP | Descarte permanente — 0 créditos de M3 gastados |
| 🟠 **DESCARTADA POR TAMAÑO** | Consenso confirma ENTERPRISE cuando el ICP pide SME | Descarte del batch; podría revisitarse con ICP diferente |
| 🟡 **PENDIENTE_REVISIÓN_MANUAL** | Análisis indeterminado (scraping/LLM fallaron, país no resoluble) | Cola manual — nunca se aprueba automáticamente |
| ⬜ **SEÑALES INSUFICIENTES** | No alcanzó el umbral de score de `ScoreTriggerPolicy` (150) | Cola futura; puede reactivarse si llega un trigger adicional |

**Principio de diseño (fail-closed):** cualquier ambigüedad no resoluble va a `PENDIENTE_REVISIÓN_MANUAL`, nunca a `CALIFICA` por defecto. El costo de revisar manualmente un falso negativo es mucho menor que el costo de contaminar la reputación del dominio de correo con un falso positivo.

---

## Signal-Based Selling v5.0 — ScoreTriggerPolicy (reemplaza el bool de TriggerAggregationPolicy)

**Diagnóstico del pivote:** la vieja `TriggerAggregationPolicy` hacía la **pregunta equivocada** (¿hay 2+ señales distintas en <45d? → bool). La correcta es *cuán urgente es el dolor HOY y cuánto dura esa urgencia*. `ScoreTriggerPolicy` responde con un score numérico.

### Distinción Causa vs. Efecto (SHiFT! — Craig Elias)

| Tipo | Qué es | Ventana de decay | Ejemplos |
|---|---|---|---|
| **CAUSA** | Evento que GENERARÁ el dolor; llega **antes** de que el prospecto busque solución | **90 días** | Contrato SECOP ganado, ronda de inversión, nuevo CTO |
| **EFECTO** | Evidencia de que el dolor **ya existe** | **45 días** | Vacante publicada, stack legacy, mención en prensa |

El decay uniforme de 45d de la versión anterior era incorrecto: le daba a las CAUSAS (de ciclo más largo) la misma ventana corta que a los EFECTOS. El decay diferencial es la aportación más valiosa de SHiFT!.

### Pesos y umbral

```
PUNTOS_BASE:  TIER_0 = 200   TIER_1 = 100   TIER_2 = 50   TIER_3 = 0
DECAY_DIAS:   CAUSA = 90     EFECTO = 45
UMBRAL_CALIFICACION = 150
BONUS_MULTI_ORIGEN  = +30   (2+ orígenes distintos activos)
BONUS_TIER0_CRUCE   = +50   (TIER_0 + otro origen = lead de oro — "Regla de Oro" TBBC)
```

- **TIER_0 califica solo** (200 ≥ 150): sangrado activo, ventana abierta hoy.
- **TIER_1 solo NO califica** (100 < 150): va a nurturing hasta que aparezca una segunda señal.
- **TIER_1 + TIER_2** = 100+50+30 = 180 ✅.
- **TIER_0 + TIER_0 (SECOP + vacante aging)** = 200+200+30+50 = **480** = lead de máxima prioridad.

### Los dos ejes de tiempo del aging de TheirStack (fix decay-vs-aging)

Una vacante con aging >45 días es la señal de fill-rate failure más fuerte — pero si su `fecha_evento` fuera `date_posted`, el propio decay de 45d de EFECTO la eliminaría. Solución: **dos ejes**.
- **Aging** (`now - date_posted`) → determina el **TIER** (≥45d = TIER_0).
- **Frescura de observación** (`now`) → determina el **decay**. Una vacante aún listada es señal de *estado continuo*, fresca en cada re-observación. Por eso el TIER_0 de aging usa `fecha_evento = now`.

Regla general: eventos puntuales (SECOP, CTO, ronda) usan la fecha real del evento; estados continuos (vacante aún abierta) usan la fecha de observación.

### Defaults conservadores (migración gradual, fail-closed)

Los campos `tipo_trigger`/`tier_urgencia` del modelo `Trigger` son **opcionales** con default `EFECTO`/`TIER_2`. Un trigger legacy sin migrar hereda el comportamiento más conservador (nunca infla el score). Esto permitió migrar adaptador por adaptador sin romper los 299 tests. `ScoreTriggerPolicy` convive con `TriggerAggregationPolicy` hasta retirar el sandbox viejo.

### Proximidad Social (Spear Selling) — fuera del score, plan futuro

La Proximidad Social (empleado anterior, defensor, socio, referencia) decide *a través de quién* entrar, no *si* califica. **No entra en el scoring** (rompería fail-closed y requiere CRM inexistente). Plan futuro: un campo a nivel de cuenta (alimentado desde CRM) que **reordena la cola de prospectos ya calificados**, nunca los califica. Detalle en `modelos_dominio_core.md` §5.0.2.

---

## Exclusión de Competidores (Negative ICP) — Cascada de 2 Capas (v4.1)

### Capa 1 — Heurística de nombre (gratis, determinista)

```python
_PALABRAS_CLAVE_VENDOR_IT: frozenset[str] = frozenset({
    "software", "tecnolog", "consultora", "consulting", "it services",
    "systems", "solutions", "soluciones digitales", "digital agency",
    "agencia digital", "outsourcing", "development", "developers",
    "system integrator", "fábrica de software", ...
})
```

Si el nombre de la empresa candidata contiene alguna de estas palabras, se asume que tiene la misma `CategoriaEmpresa` que el cliente → `EXCLUIDO_DURO` instantáneo sin gastar un token de LLM.

### Capa 2 — PropuestaValorAdapter (con costo — LLM sobre la homepage)

Se invoca **solo** cuando la Capa 1 no pudo decidir. Lee el texto público de la homepage (con fallback a `<title>` + `<meta name="description">` para SPAs sin SSR) y llama a Groq `llama-3.3-70b-versatile` con un prompt JSON estructurado que retorna tres señales:

```json
{
  "es_vendor_it": true/false,
  "tamano_estimado": "STARTUP|SME|MID_MARKET|ENTERPRISE|null",
  "pais_hq": "CO|GB|MX|null"
}
```

- Si `es_vendor_it=True` → `EXCLUIDO_DURO`.
- Si `es_vendor_it=False` → continúa al waterfall geográfico.
- Si `es_vendor_it=None` (scraping falló, SPA opaca, LLM no disponible) → `PENDIENTE_REVISIÓN_MANUAL` (fail-closed). **NUNCA se interpreta como "no es competidor".**

El resultado se cachea en un `dict[UUID, _AnalisisPropuestaValor | None]` por instancia del adaptador, de modo que las tres señales (`es_vendor_it`, `tamano_estimado`, `pais_hq`) se obtienen de una sola lectura web + una sola llamada LLM, reutilizadas por `PoliticaCorroboracionTamano` y `PoliticaValidacionGeografica` sin costo adicional.

---

## PoliticaValidacionGeografica (nueva en v4.1)

```python
class PoliticaValidacionGeografica:
    def evaluar(self, pais_candidato: str | None, geografia_icp: str | None) -> EstadoValidacionGeografica:
        # Si el ICP no restringe geografía → PERMITIDO
        # Si pais_candidato es None / PAIS_DESCONOCIDO ("XX") → INDETERMINADO (fail-closed)
        # Si ambos códigos ISO Alpha-2 coinciden → PERMITIDO
        # Si son distintos y conocidos → EXCLUIDO
```

El país candidato se resuelve en waterfall barato→caro:
1. `Empresa.pais` (ya viene de TheirStack/discovery, corregido tras bug del default `"CO"`).
2. Si `Empresa.pais == PAIS_DESCONOCIDO` → se usa `PropuestaValorAdapter.pais_hq()` (ya cacheado).

---

## Filtro de Co-ocurrencia Semántica en Google Alerts (v4.1)

**Problema raíz:** cuando el nombre de una empresa coincide con una palabra de uso coloquial común, el `match` por subcadena genera falsos positivos. Las comillas exactas en el query RSS reducen el ruido de tokenización pero no el ruido semántico (p. ej. noticias deportivas o de entretenimiento que contienen el término sin referirse a la empresa).

**Fix:** antes de aceptar una entrada RSS como trigger válido, se exige co-ocurrencia con al menos una palabra del glosario de negocio:

```python
_GLOSARIO_COOCURRENCIA_NEGOCIO = frozenset({
    "empresa", "compañía", "company", "startup", "software",
    "tecnología", "agencia", "consultora", "ceo", "cto", "cio",
    "fundador", "inversión", "funding", "ronda", "clientes",
    "servicios", "plataforma", "producto", "mercado", ...
})
```

**Regla adicional:** si el nombre de la empresa tiene ≤8 caracteres (nombre corto/genérico), el nivel de confianza máximo para ese trigger se limita a `BAJA`, y su `tier_urgencia`/`tipo_trigger` se capan a `TIER_2`/`EFECTO` (código real en `google_alerts_adapter.py::obtener_triggers()`) incluso si el texto contiene keywords de C-Level o inversión. Esto fuerza que `ScoreTriggerPolicy` (no `TriggerAggregationPolicy`, que quedó en desuso desde v5.0 — ver corrección de auditoría 22-Jul-2026) requiera corroboración de otra fuente antes de calificar el lead.

Los matches por `palabras_clave_extra` del ICP (dolor_operativo / anclaje_tecnologico) **no** pasan por este filtro adicional: ya son términos específicos de negocio.

---

## Mapa de Dependencias de Puertos — Vista Hexagonal v6.0 (corregido 22-Jul-2026)

> **Auditoría 22-Jul-2026:** el diagrama anterior (v3.0) no incluía
> `ApolloDiscoveryAdapter`, `PropuestaValorAdapter`, `GitHubAdapter`, ni los
> puertos `PuertoDescubridorEmpresas`, `PuertoEstimadorTamano` y
> `PuertoClasificadorPropuestaValor` — todos existen en código
> (`src/core/ports/interfaces.py`) desde el blindaje de Motor 2 (v4.1) y la
> refactorización de discovery (v6.0). Se actualiza el diagrama para que sea
> un espejo fiel del código real. `ScoringPolicy` se retira del diagrama
> (nunca se materializó — ver nota en la sección del Motor 1).

```mermaid
flowchart TB
    subgraph Core ["🧠 CORE (Lógica de Dominio Pura - Totalmente Agnóstico)"]
        direction TB
        subgraph Modelos ["Entidades y Value Objects"]
            M1[ManifiestoICP]
            M2[Empresa]
            M3[Trigger]
            M4[OrigenTrigger]
            M5[EstimacionTamano]
        end
        subgraph Politicas ["Políticas de Negocio"]
            P2[AdapterRoutingPolicy]
            P3[ScoreTriggerPolicy]
            P4[PoliticaExclusionCompetidores]
            P5[PoliticaValidacionGeografica]
            P6[PoliticaCorroboracionTamano]
        end
        subgraph Puertos ["Puertos (Interfaces Abstractas)"]
            PT1(PuertoAnalizadorICP)
            PT2(PuertoFuenteTriggers)
            PT3(PuertoDescubridorEmpresas)
            PT4(PuertoEstimadorTamano)
            PT5(PuertoClasificadorPropuestaValor)
        end
    end

    subgraph Adaptadores ["🔌 ADAPTADORES (Mundo Exterior)"]
        direction LR
        A1[GroqICPAdapter]
        A2[TheirStackAdapter]
        A3[GoogleAlertsRSSAdapter]
        A4[SecopSocrataAdapter]
        A5[GitHubAdapter]
        A6[WappalyzerHeadlessAdapter]
        A7[ApolloDiscoveryAdapter]
        A8[PropuestaValorAdapter]
    end

    A1 -.->|Implementa| PT1
    A2 -.->|Implementa| PT2
    A2 -.->|Implementa| PT3
    A2 -.->|Implementa| PT4
    A3 -.->|Implementa| PT2
    A4 -.->|Implementa| PT2
    A4 -.->|Implementa| PT4
    A5 -.->|Implementa| PT2
    A6 -.->|Implementa| PT2
    A7 -.->|Implementa| PT3
    A8 -.->|Implementa| PT4
    A8 -.->|Implementa| PT5

    style Core fill:#f8f9fa,stroke:#212529,stroke-width:2px,color:#000
    style Adaptadores fill:#e3f2fd,stroke:#0d47a1,stroke-width:2px,color:#000
    style Puertos fill:#e8f5e9,stroke:#1b5e20,stroke-width:1px,color:#000
```

**Notas del diagrama v6.0:**
- `TheirStackAdapter` es el único adaptador con **triple** implementación de puerto (`PuertoFuenteTriggers` + `PuertoDescubridorEmpresas` + `PuertoEstimadorTamano`), aunque `descubrir_empresas()` ya NO se invoca en el flujo real de `sandbox_tbbc_real.py` (Motor 1 solo usa Apollo — ver nota de "Separación de Concerns" al inicio de este documento). El método sigue existiendo y probado por si se reactiva.
- `SecopSocrataAdapter` implementa `PuertoFuenteTriggers` + `PuertoEstimadorTamano` (agregado en v6.0, corregido en la auditoría 22-Jul-2026 para conectarlo al waterfall real — ver sección SECOP arriba).
- `PropuestaValorAdapter` implementa `PuertoClasificadorPropuestaValor` + `PuertoEstimadorTamano`, y además expone métodos de conveniencia fuera de los puertos del Core (`es_vendor_it()`, `pais_hq()`, `snippet_homepage()`) consumidos directamente por el composition root (`sandbox_tbbc_real.py`), no por el Core.

> **REGLA ABSOLUTA:** El Core nunca importa a los adaptadores. La `AdapterRoutingPolicy` retorna `OrigenTrigger` (un Enum del Core), no instancias de adaptadores. El orquestador de la aplicación (capa de casos de uso) resuelve el Enum a la instancia concreta del adaptador vía inyección de dependencias.

## Paquete de Revisión Persistente — `PaqueteRevisionAdapter` (v6.0)

**Problema que resuelve:** antes de esta pieza, cada empresa que caía en
`PENDIENTE_REVISION_MANUAL` (Negative ICP indeterminado) o `INDETERMINADO`
(geografía indeterminada) se imprimía como un banner en consola y se perdía
— la siguiente corrida repetía exactamente el mismo trabajo de LLM/scraping
sobre la misma empresa, sin memoria de que ya había sido evaluada.

**Implementación real** (`src/adapters/revision_manual/paquete_revision_adapter.py`):
- Persiste en un archivo JSON local (`revision_manual/pendientes.json`,
  fuera del control de versiones — ver `.gitignore`) un registro por empresa
  con: `motivo`, `snippet_homepage` (el mismo texto que ya leyó
  `PropuestaValorAdapter`, sin costo adicional), links de verificación de un
  clic (Google, LinkedIn, RUES búsqueda avanzada, y `urlproceso` de SECOP si
  hay un Trigger con esa URL), y `estado_revision`.
- `EstadoRevisionHumana`: `PENDIENTE` | `CONFIRMADO_PERMITIDO` | `CONFIRMADO_EXCLUIDO`.
- El orquestador (`sandbox_tbbc_real.py::main()`) consulta
  `obtener_decision_humana()` como **Paso 0**, ANTES del Negative ICP: si un
  humano ya marcó la empresa como `CONFIRMADO_PERMITIDO`/`CONFIRMADO_EXCLUIDO`
  en una corrida anterior, esa decisión se respeta sin volver a gastar LLM.
- Si una empresa cae en revisión manual, `_registrar_pendiente_con_evidencia()`
  llama a `adapter_pv.snippet_homepage(empresa)` (reutiliza el cache interno
  de `PropuestaValorAdapter`, no dispara una lectura de red adicional) y
  persiste el registro completo.

## Reintentos Técnicos en la Capa 2 (v6.0)

**Problema que resuelve:** muchos casos que terminaban en
`PENDIENTE_REVISION_MANUAL` no eran ambigüedad semántica real, sino fallas
técnicas de lectura (la raíz del dominio no tenía texto útil, pero la
empresa sí tenía contenido público en otra ruta).

**Implementación real** (`PropuestaValorAdapter._leer_texto_homepage()`),
cascada del más barato al más caro, deteniéndose en el primer resultado
utilizable:
1. Raíz del dominio vía `requests` + `BeautifulSoup` (comportamiento histórico).
2. Si (1) no dio NADA de texto (ni body visible ni fallback de meta tags):
   rutas alternas `/nosotros`, `/about`, `/quienes-somos`, `/about-us`, mismo
   método liviano.
3. Si ninguna ruta alterna dio texto: fallback pesado con **Playwright**
   (`_renderizar_con_playwright()`, Chromium headless, ejecuta JavaScript)
   sobre la raíz del dominio — último recurso para SPAs sin
   server-side rendering. Requiere `playwright install chromium` en el
   entorno (dependencia opcional en runtime: si no está disponible, retorna
   `None` sin lanzar excepción, mismo contrato del resto del adaptador).

---
*v3.0 — Motor 1 evolucionado a Enrutador Dinámico. AdapterRoutingPolicy documentada.*
*Wappalyzer rebajado a adaptador condicional con limitaciones documentadas.*
*v4.1 (17-Jul-2026) — Robustez de precisión del Motor 2: exclusión de competidores (Negative ICP) en cascada de 2 capas, PoliticaValidacionGeografica, co-ocurrencia semántica en Google Alerts, techo de confianza BAJA para nombres genéricos. Estados de salida expandidos. PropuestaValorAdapter documentado como adaptador dual con caché por instancia.*
*v5.0 (19-Jul-2026) — Signal-Based Selling materializado: ScoreTriggerPolicy reemplaza el bool de TriggerAggregationPolicy.*
*v6.0 (21-Jul-2026) — Separación de Concerns. Apollo es el único puerto de Discovery (M1) para asegurar un TAM puramente firmográfico. TheirStack pasa a ser exclusivo de Motor 2 (Señales). Optimización SECOP ($q full-text). Implementación de persistencia manual `pendientes.json` gestionada por `PaqueteRevisionAdapter` en el orquestador.*
*v6.1 (22-Jul-2026, auditoría holística) — Corregidas 6 discrepancias código↔documentación: (1) `SecopSocrataAdapter.estimar_tamano()` estaba implementado pero desconectado del waterfall real — conectado en `sandbox_tbbc_real.py`; (2) `GITHUB_TOKEN`/`SECOP_APP_TOKEN` faltaban en `.env.example`; (3) `ScoringPolicy` documentado como código real nunca existió — marcado como diseño histórico no implementado; (4) tabla de adaptadores no incluía `GitHubAdapter`; (5) Wappalyzer documentado erróneamente con Playwright (el código real usa solo `requests`+`BeautifulSoup`; Playwright es fallback de `PropuestaValorAdapter`); (6) umbrales de SECOP con montos en COP no existen en código (el criterio real es solo antigüedad del contrato). Diagramas Mermaid actualizados para reflejar Apollo como discoverer real y el tercer origen SECOP en el waterfall de tamaño. Documentadas las secciones "Paquete de Revisión Persistente" y "Reintentos Técnicos en la Capa 2", que existían en código sin documentación formal en este archivo.*
