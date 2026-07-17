# Arquitectura y Paradigmas — Build Nuevo e Independiente

> Recomendación para construir un **buen sistema** (prospector propio y futuros productos), **desde cero y limpio** (sin reutilizar arquitectura/flujos/metodología de la contratante — ver [`../../estrategia/situacion-contractual-y-sociedad.md`](../../estrategia/situacion-contractual-y-sociedad.md)), respetando las **3 reglas de oro**. Fecha: **4-jul-2026**. *Fuentes externas reformuladas; enlaces citados.*

## 0. Principio rector "clean room"

Puedes usar **herramientas generales** (FastAPI, Postgres, un LLM, etc.) — eso es conocimiento de industria, tuyo para siempre. Lo que **no** puedes reutilizar es la **implementación específica** de la contratante (su código, esquema de BD, prompts, "pain framework", diseño de flujos). Ventaja: diseñar una **arquitectura distinta y mejor** es a la vez tu protección legal y tu mejora de producto. **Documenta tus decisiones de diseño con fecha** = evidencia de creación independiente.

## 1. Paradigmas de base (el "cómo pensamos el sistema")

| Paradigma | Qué aporta | Por qué para nosotros |
|-----------|------------|------------------------|
| **12-Factor Agents** (humanlayer / Dex Horthy) | "Un agente confiable es, sobre todo, software bien hecho": observable, interrumpible, recuperable, auditable, testeable. Tú **posees el control de flujo**; el LLM se usa solo donde el razonamiento probabilístico ayuda | Es la mejor guía para que el prospector sea **confiable en producción** y **no** una caja negra frágil. También te ayuda a **no depender** de un framework pesado (diseño propio). [Repo](https://github.com/humanlayer/12-factor-agents) (~21,5k★ may-2026) |
| **Arquitectura Hexagonal / Ports & Adapters** (o Clean Architecture) | Aísla el **dominio** (lógica de prospección) de la **infraestructura** (scrapers, LLM, BD, APIs). Cambiar Hunter→otro proveedor no toca el dominio | Testeable, desacoplada y **estructuralmente distinta** a un pipeline monolítico → clean-room + calidad |
| **Diseño dirigido por dominio (DDD-lite)** | Modelar el negocio: `Lead`, `Empresa`, `Trigger`, `Campaña`, `ICP`, `Job` como entidades con reglas claras | Claridad y mantenibilidad; base para multi-tenant |
| **Event-driven / colas** | Pipeline de prospección como **jobs idempotentes y reanudables** | Recuperable ante fallos (12-factor), escala por volumen |
| **Spec-driven (Kiro) + Security-driven + SOLID** | Especificar antes de codear; seguridad desde el diseño | Ya es tu estándar; evita deuda técnica |
| **Cost-aware LLM pipeline** | Rutear modelos por complejidad, cachear, medir costo por job | Protege el margen (ver [`costo-por-lead.md`](costo-por-lead.md)) |

## 2. Stack técnico recomendado (pragmático, tu fortaleza)

| Capa | Opción recomendada | Alternativas / nota |
|------|--------------------|--------------------|
| Lenguaje | **Python** (tu fuerte) | — |
| Orquestación de agentes | **Diseño propio guiado por 12-factor** (tú posees el control de flujo) + **PydanticAI** para salidas tipadas/estructuradas | **LangGraph** si necesitas grafos de estado con branching complejo (es el default de producción, pero mayor curva). CrewAI solo para prototipos de roles. Elegir **una** y no sobre-ingeniar |
| API / backend | **FastAPI + Pydantic v2** (async) | — |
| Estructura | **Hexagonal** (dominio / puertos / adaptadores) | Distinta de un pipeline de scripts en cascada |
| Datos | **PostgreSQL (Supabase)** con **RLS** multi-tenant; **esquema propio** diseñado desde cero | No reutilizar el esquema de la contratante |
| Jobs / workers | **Arq** o **Celery/RQ**, o **Modal** serverless; jobs **idempotentes y reanudables** | — |
| Observabilidad | Logging estructurado + **métricas de costo por job** + trazas | Alimenta el modelo de costo por lead |
| Config | **Variables de entorno** (12-factor), workers **stateless** | Secretos fuera del repo |
| Enriquecimiento | Proveedores detrás de **adaptadores** (Hunter/Apollo/Tavily intercambiables) | Evita lock-in y baja el riesgo de "cuello de botella Hunter" |
| Cumplimiento | **Habeas Data by design**: base legal por campaña, opt-out, datos corporativos | Ley 1581/2012 (ver validación §7) |

## 2.1 Diagrama de Arquitectura General del Pipeline (M1 → M4)

> **Estado real del código a 15-Jul-2026.** Este diagrama consolida los 4 motores construidos
> (specs detalladas en `prospector-m1-m2-design.md`, `prospector-m3-m4-design.md` y
> `prospector-m4-design.md`). Muestra cómo cada motor entrega su salida al siguiente y **cierra el
> lazo**: el webhook de rebotes de M4 escribe de vuelta sobre el `Decisor` que produjo M3, cerrando
> el KPI de bounce rate pendiente del piloto.

```mermaid
graph TB
    IN([Input: texto libre del usuario]) --> M1

    subgraph M1 ["🧭 MOTOR 1 — Analizador ICP + Enrutador Dinámico"]
        direction TB
        M1_LLM["GroqICPAdapter<br/>(llama-3.3-70b-versatile)"] --> M1_MAN["ManifiestoICP"]
        M1_MAN --> M1_ROUTE["AdapterRoutingPolicy<br/>→ adaptadores activos"]
    end

    M1_ROUTE --> M2

    subgraph M2 ["📡 MOTOR 2 — Cascada de Triggers (5 adaptadores)"]
        direction TB
        M2_ADAPT["GoogleAlerts · TheirStack · Wappalyzer<br/>SECOP · GitHub<br/>(solo los activos por M1)"] --> M2_AGG["TriggerAggregationPolicy<br/>(mín. 2 orígenes distintos, &lt;45 días)"]
    end

    M2_AGG -->|"califica"| DTO1["ProspectoCalificado<br/>(Empresa + Triggers + ManifiestoICP)"]
    M2_AGG -->|"no califica"| M2_OUT([Descartado / cola futura])

    DTO1 --> M3

    subgraph M3 ["💰 MOTOR 3 — Enriquecimiento (escudo financiero)"]
        direction TB
        M3_APOLLO["ApolloClient<br/>(api_search → people/match)"] -->|"perfil + email candidato"| M3_HUNTER["HunterClient<br/>(verify / domain-search)"]
        M3_APOLLO -->|"0 perfiles"| M3_NORES(["NO_RESUELTO<br/>⛔ Hunter NO se invoca"])
        M3_HUNTER --> M3_MAP["PoliticaMapeoEstadoCorreo<br/>→ EstadoCorreo + confianza_dato"]
        M3_MAP --> M3_UMB["UmbralCalidadDecisor<br/>(confianza≥0.7 + VERIFICADO/INFERIDO)"]
    end

    M3_UMB -->|"aptos"| DTO2["PaqueteOutbound<br/>(ProspectoCalificado + decisores_aptos)"]
    M3_UMB -->|"no aptos"| M3_MANUAL([Cola manual])

    DTO2 --> M4

    subgraph M4 ["📤 MOTOR 4 — Outbound RAG (única salida real)"]
        direction TB
        M4_SEL["PoliticaSeleccionMejorDecisor<br/>(1 decisor por empresa)"] --> M4_RAG["TavilyContextoAdapter<br/>(PuertoContextoRAG)"]
        M4_RAG --> M4_RED["GroqRedactorAdapter<br/>(PuertoRedactorOutbound)"]
        M4_RED --> M4_HITL{{"👤 Modo Borrador<br/>(HITL aprueba/rechaza)"}}
        M4_HITL -->|"aprobado + legal OK + pacing OK"| M4_SEND["ResendEnvioAdapter<br/>(PuertoEnvioCorreo)"]
        M4_HITL -->|"rechazado"| M4_DESCARTE([Mensaje descartado])
    end

    M4_SEND -->|"webhook async"| M4_WEBHOOK["procesar_webhook_rebote()<br/>(función pura)"]
    M4_WEBHOOK --> M4_FEED["PoliticaRegistroRebote<br/>→ EstadoCorreo.REBOTADO"]
    M4_FEED -.->|"writeback — CIERRA EL KPI DE M3"| M3_MAP

    style IN fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    style DTO1 fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px
    style DTO2 fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px
    style M2_OUT fill:#ffebee,stroke:#c62828,stroke-width:2px
    style M3_NORES fill:#eceff1,stroke:#546e7a,stroke-width:2px
    style M3_MANUAL fill:#fff8e1,stroke:#f9a825,stroke-width:2px
    style M4_DESCARTE fill:#ffebee,stroke:#c62828,stroke-width:2px
    style M4_WEBHOOK fill:#fce4ec,stroke:#ad1457,stroke-width:2px
    style M4_FEED fill:#fce4ec,stroke:#ad1457,stroke-width:2px
```

**Cómo leerlo:**
- Cada motor es una compuerta de costo: M2 no deja pasar señales aisladas, M3 no deja pasar contactos
  dudosos, M4 no deja pasar mensajes sin revisión humana.
- La flecha punteada rosa (`M4_FEED -.-> M3_MAP`) es el **lazo de retroalimentación de rebotes**: es
  el mecanismo, no solo un adorno visual, que permite medir el bounce rate real y cerrar el KPI
  pendiente del piloto de M3 (ver `prospector-m3-m4-design.md` §3.5).
- `ApolloClient` aparece con su flujo real de 2 pasos (`api_search` → `people/match`), vigente desde
  el fix aplicado tras la depreciación del endpoint directo de Apollo.

---

## 3. Repos/recursos para ESTUDIAR (no copiar)

- **[humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents)** — principios de agentes confiables.
- **PydanticAI / LangGraph** (docs oficiales) — para decidir la capa de orquestación. Comparativas 2026: LangGraph = default de producción para flujos con estado; PydanticAI = agentes tipados más limpios ([aihaven](https://aihaven.com/guides/best-open-source-ai-agent-frameworks/), [olostep](https://www.olostep.com/blog/agentic-ai-frameworks)).
- **ECC** (ver [`evaluacion-ecc.md`](evaluacion-ecc.md)) — skills `cost-aware-llm-pipeline`, `api-design`, `backend-patterns` como referencia.
- Referencias de **Arquitectura Hexagonal / Clean Architecture** para estructurar el dominio.

## 3.1 Principios de Arquitectura Derivados del Blindaje Motor 2 (17-Jul-2026)

Los siguientes principios surgieron de los 3 bugs descubiertos en el caso Parcero/UK. Se elevan a principios de arquitectura porque aplican a cualquier adaptador del sistema, no solo al Motor 2.

### Principio: Fail-Closed para Datos de Terceros

> **Cuando un adaptador externo retorna datos insuficientes, ambiguos o un error, el resultado de la operación es siempre `INDETERMINADO/PENDIENTE_REVISIÓN`, nunca `PERMITIDO` por defecto.**

**Motivación:** el comportamiento fail-open (asumir que "sin señal de peligro" = "seguro") es correcto en sistemas donde el costo del falso negativo supera al costo del falso positivo. En El Prospector, el costo de un falso positivo es mucho mayor que el de un falso negativo (mandar un prospecto válido a revisión manual). La revisión manual es barata y local; el daño de reputación del dominio de correo es costoso y sistémico.

**Contraejemplo (fail-open, PROHIBIDO):**
```python
# Anti-patrón: interpretar None como "no hay problema"
if adapter_pv.clasificar(empresa) is None:
    return PERMITIDO  # ← BUG: "no pude analizar" ≠ "confirmado no competidor"
```

**Implementación correcta (tri-estado explícito):**
```python
es_vendor: bool | None = adapter_pv.es_vendor_it(empresa)
# True  → EXCLUIDO_DURO
# False → continúa el pipeline
# None  → PENDIENTE_REVISIÓN_MANUAL  ← fail-closed
```

---

### Principio: Caché por Instancia en Adaptadores Duales

> **Cuando un adaptador implementa múltiples puertos que requieren los mismos datos externos, se usa un `dict[UUID, resultado | None]` por instancia del adaptador para reutilizar el resultado de la primera llamada en todas las invocaciones posteriores sobre la misma entidad.**

**Motivación:** `PropuestaValorAdapter` implementa `PuertoClasificadorPropuestaValor` y `PuertoEstimadorTamano` más expone `es_vendor_it()` y `pais_hq()`. Sin caché, el orquestador pagaría 4 lecturas web + 4 llamadas LLM por empresa. Con caché por instancia: 1 lectura web + 1 llamada LLM, con los 4 resultados derivados del mismo análisis.

```python
class PropuestaValorAdapter:
    def __init__(self) -> None:
        self._cache: dict[uuid.UUID, _AnalisisPropuestaValor | None] = {}

    def _analizar(self, empresa: Empresa) -> _AnalisisPropuestaValor | None:
        if empresa.id in self._cache:
            return self._cache[empresa.id]
        resultado = self._analizar_sin_cache(empresa)  # 1 lectura + 1 LLM
        self._cache[empresa.id] = resultado
        return resultado
```

**Invariante:** el caché es por instancia (no global). Para un orquestador multi-tenant real, el TTL apropiado sería la duración de un job de descubrimiento.

---

### Principio: Datos Ausentes con Centinela Explícito

> **Un campo que "no se sabe" nunca toma el valor del contexto del llamador como default silencioso. Se usa un centinela explícito del Core que el código que lo consume detecta y trata de forma fail-closed.**

**Contraejemplo (PROHIBIDO):**
```python
pais = empresa_data.get("country_code", "CO") or "CO"
# ← Miente: asume el país del ICP del cliente cuando el dato es ausente
```

**Implementación correcta:**
```python
# En models.py — constante del Core
PAIS_DESCONOCIDO: str = "XX"  # ISO 3166-1 reservado — no colisiona con ningún país real

# En TheirStackAdapter
pais_raw = empresa_data.get("country_code")
pais = pais_raw.upper()[:2] if pais_raw else PAIS_DESCONOCIDO
```

`PoliticaValidacionGeografica` trata `PAIS_DESCONOCIDO` como `INDETERMINADO` (fail-closed), nunca como aprobación automática.

---

## 4. Arquitectura COMERCIAL (las 3 reglas de oro en el producto) Diseñar el producto como **SaaS multi-tenant** con:

| Componente | Qué hace | Regla de oro |
|------------|----------|--------------|
| **Planes + cuotas** (Natural/Negocio/Growth/Business) | Enforzar el tope de Hunter (~1.500) y el volumen por plan | Ahorra dinero (no te pasas de cupo) |
| **Medición de uso / metering** | Costo por lead vigilado por cliente | Protege margen |
| **Facturación** | **Wompi / Mercado Pago / PSE** (Colombia) o Stripe (exterior) | Ganar dinero (cobrar bien) |
| **Onboarding self-serve + CRM** | El cliente arranca rápido y ve valor (M5) | Ahorra tiempo + retención |
| **Dashboard de resultados** | Mostrar leads/triggers/respuestas → prueba de valor | Ganar dinero (justifica renovación) |

> **Diferenciación (recordatorio del Pilar 4):** el foso NO es el scraper (es commoditizable). Es **nicho + calidad de trigger/copy + el tiempo que le ahorras al cliente**. La arquitectura debe optimizar **calidad del lead**, no volumen bruto.

## 5. Secuencia recomendada (no sobre-ingeniar)

1. **Spec en Kiro** del MVP propio (dominio + casos de uso + criterios de aceptación).
2. **Diseñar el dominio (DDD-lite)** y la estructura hexagonal → documentar decisiones (evidencia clean-room).
3. **MVP delgado:** 1 flujo end-to-end (descubrir → trigger → decisor → verificar email → copy) con **tu** orquestación (12-factor), adaptadores para proveedores.
4. **Medir costo por job real** (cierra el número del pricing).
5. **Capa comercial mínima:** planes + cuota + un cliente piloto (Catalina).
6. Iterar por calidad de lead, no por features.

> ⚠️ El cuello de botella hoy **no es técnico, es comercial**: construir lo mínimo para vender y validar, no una plataforma perfecta antes del primer peso.
