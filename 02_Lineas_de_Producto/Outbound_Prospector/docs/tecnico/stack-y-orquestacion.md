# Stack y Orquestación — Ciclo de Vida Comercial y Técnico

> Stack real adaptado a las herramientas que **hoy** tenemos (sin Claude Code todavía). Fecha: **4-jul-2026**. *Fuentes externas reformuladas; enlaces citados.*
>
> **Reparto de trabajo (acordado):** el fundador **orquesta, prueba, valida, encuentra los cuellos de botella por los que un cliente paga, informa y corrige**. Kiro (con los modelos de Claude) **hace el trabajo técnico**. Modelo: humano dirige + IA ejecuta.

## 1. Herramientas que tenemos hoy

| Herramienta | Qué es | Rol en nuestro flujo | Estado |
|-------------|--------|----------------------|--------|
| **Kiro (IDE)** | IDE agéntico con specs, steering, hooks, MCP, powers | **Centro de comando**: especificar, generar código, memoria, automatizaciones | ✅ En uso (aquí) |
| **Antigravity Pro (CLI `agy`)** | IDE/CLI agéntico de Google (Gemini 3.5 Flash por defecto; Claude Opus 4.8/Sonnet 4.6 vía API key). Vista Manager orquesta agentes en paralelo | **Segundo agente ejecutor** + tareas en background + agentes paralelos | ✅ Tienes Pro |
| **Google Stitch** | Diseñador UI de Google Labs (Gemini): texto/imagen → pantallas, prototipos, exporta HTML/CSS + Figma, y **hace handoff a Antigravity** | **Capa de diseño** (UI de la app y de propuestas) | ✅ Gratis |
| **Claude Code** | CLI de Anthropic (programador) | Ejecutor premium — **lo pagamos después** | ⏳ Pendiente de recursos |

> ⚠️ Nota: Antigravity CLI (`agy`) reemplazó a Gemini CLI (apagado 18-jun-2026). Fuentes: [networkershome](https://www.networkershome.com/blog/google-antigravity-guide/), [aibuilderclub](https://www.aibuilderclub.com/blog/antigravity-cli-guide). Stitch: [nxcode](https://www.nxcode.io/resources/news/google-stitch-complete-guide-vibe-design-2026).

## 2. Mapeo del "método de agencia unipersonal" a NUESTRO stack

El método que circula habla del ecosistema Claude ("Cloud Code/Design/Dispatch/Cowork"). Traducimos por **función** (algunos nombres son marketing; lo que importa es la función):

| Función del método | Herramienta original | **Nuestro equivalente hoy** |
|--------------------|----------------------|------------------------------|
| Programador (planifica, codea, se autocorrige) | Claude Code | **Kiro + Antigravity CLI (`agy`)** |
| Diseñador (texto → UI, landing, paneles) | Claude Design | **Google Stitch** → exporta a Antigravity/código |
| Coordinador remoto (móvil → PC) | "Claude Dispatch" | No prioritario (el fundador lo descarta). Alternativa: tareas en background de `agy` |
| Redactor de propuestas comerciales | "Claude Cowork" | **Kiro/Antigravity** + nuestras plantillas ([presentación](../fundamentos/presentacion-fundadores.md), [playbooks M4/M5](../../proyectos/catalina-prospector/README.md)) |
| Subagentes en paralelo | Claude Code subagents | **Antigravity Manager** (agentes en paralelo) + subagents de Kiro |

## 3. Orquestación del ciclo de vida (comercial + técnico)

```
COMERCIAL (el fundador dirige)                TÉCNICO (Kiro/Antigravity ejecutan)
─────────────────────────────────            ─────────────────────────────────────
1. Investigar dolores del nicho     ──►  Kiro + MCP de búsqueda (Tavily/Exa/fetch)
   (foros, Reddit, competencia)
2. Propuesta irresistible           ──►  Kiro redacta (plantillas) → Stitch la maqueta
   (lenguaje del cliente + demo visual)
3. Cerrar (M4) / validar delivery   ──►  —
4. Spec del MVP                     ──►  Kiro (spec-driven): requisitos + diseño + tareas
5. Diseño UI                        ──►  Google Stitch → export a Antigravity
6. Construir MVP                    ──►  Antigravity CLI (agentes paralelos) + Kiro
7. Verificar/QA                     ──►  Hooks de Kiro (quality-gate, tests) + Antigravity (browser/E2E)
8. Entregar + mantenimiento (M5)    ──►  Recurrencia mensual = ingreso estable
9. Documentar/marketing            ──►  Kiro genera posts desde notas de voz/updates
```

## 4. MCPs a conectar (para que los agentes tengan herramientas, no codeen "a ciegas")

Un agente sin herramientas adivina; con MCP, **actúa sobre sistemas reales**. Prioridad para nuestro build:

| MCP | Para qué | Prioridad |
|-----|----------|-----------|
| **GitHub** | Clonar, PRs, issues (ya lo usamos vía Power) | 🔥 Alta |
| **Context7** | Documentación actualizada de librerías (ya disponible como Power) | 🔥 Alta |
| **Filesystem** | Leer/escribir archivos del proyecto | 🔥 Alta (nativo) |
| **Supabase / Postgres** | Crear tablas, RLS, queries del prospector | 🔥 Alta |
| **Playwright / browser** | E2E + automatización web + verificación visual | Media-Alta |
| **Tavily / Exa / fetch** | Investigación de dolores/competencia y prospección | Media (clave para ) |
| **Stripe/Wompi (cuando toque)** | Facturación del SaaS | Baja (después del MVP) |

> Regla del steering (pilar 5 de Vibe Coding): **priorizar APIs limpias / integración externa eficiente**. Los MCP son la forma de darle "manos" a los agentes. Ver [guía práctica de Kiro](kiro-guia-practica.md) para conectarlos.

## 5. Regla anti-sobreingeniería

El cuello de botella hoy **es comercial, no técnico**. El stack ya alcanza para construir y entregar. Prioridad: **especificar bien → MVP delgado → validar con cliente**, no montar toda la plataforma antes del primer peso. La calidad se asegura con hooks/QA, no con perfeccionismo.
