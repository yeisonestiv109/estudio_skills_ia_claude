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
| Enriquecimiento | Proveedores detrás de **adaptadores** (Hunter/Apollo/Tavily/Apify intercambiables) | Evita lock-in y baja el riesgo de "cuello de botella Hunter" |
| Cumplimiento | **Habeas Data by design**: base legal por campaña, opt-out, datos corporativos | Ley 1581/2012 (ver validación §7) |

## 3. Repos/recursos para ESTUDIAR (no copiar)

- **[humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents)** — principios de agentes confiables.
- **PydanticAI / LangGraph** (docs oficiales) — para decidir la capa de orquestación. Comparativas 2026: LangGraph = default de producción para flujos con estado; PydanticAI = agentes tipados más limpios ([aihaven](https://aihaven.com/guides/best-open-source-ai-agent-frameworks/), [olostep](https://www.olostep.com/blog/agentic-ai-frameworks)).
- **ECC** (ver [`evaluacion-ecc.md`](evaluacion-ecc.md)) — skills `cost-aware-llm-pipeline`, `api-design`, `backend-patterns` como referencia.
- Referencias de **Arquitectura Hexagonal / Clean Architecture** para estructurar el dominio.

## 4. Arquitectura COMERCIAL (las 3 reglas de oro en el producto)

El software es la mitad; el negocio es la otra. Diseñar el producto como **SaaS multi-tenant** con:

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
