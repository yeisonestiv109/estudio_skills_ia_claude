# Guía Práctica de Kiro — Specs, Steering, Hooks, MCP y Automatizaciones

> Cómo sacarle el máximo a Kiro como **centro de comando** de nuestros desarrollos. Todo se puede configurar **hablándole a la IA** (a mí) en el chat: yo escribo los archivos por ti. Fecha: **4-jul-2026**. *Fuentes: [kiro.dev/docs](https://kiro.dev/docs), reformulado.*

## 1. Los 5 pilares de Kiro (qué es cada cosa)

| Pilar | Qué es | Dónde vive | Para qué nos sirve |
|-------|--------|------------|--------------------|
| **Specs** | Desarrollo dirigido por especificación: requisitos → diseño → tareas, antes de codear | `.kiro/specs/` | Definir el MVP del prospector sin deuda de diseño |
| **Steering** | Reglas siempre-activas que moldean cómo trabaja la IA | `.kiro/steering/*.md` | Nuestro contexto/reglas (ya lo usamos) |
| **Agent Hooks** | Automatizaciones que se disparan por eventos del IDE | panel "Agent Hooks" / `.kiro/hooks/` | QA automática, tests, docs, seguridad |
| **MCP** | Conecta la IA a herramientas externas (BD, web, APIs) | `.kiro/settings/mcp.json` (workspace) o `~/.kiro/settings/mcp.json` (global) | Darle "manos" a los agentes |
| **Powers** | Paquetes que agrupan docs + steering + MCP | gestor de Powers | Reutilizar capacidades (ej. GitHub, Context7) |

## 2. Cómo configurar CADA cosa "hablándole a la IA"

No necesitas editar archivos a mano. En el chat de Kiro me pides y yo lo creo:

- **Steering:** *"Crea un steering file que obligue a usar Python tipado y tests con pytest"* → escribo el `.md` con su frontmatter (`inclusion: auto|fileMatch|manual`).
  - `auto` = se carga siempre (requiere `name`). `fileMatch` = solo al tocar ciertos archivos (requiere `fileMatchPattern`). `manual` = se invoca con `#nombre`.
  - Global (`~/.kiro`) aplica a todos tus proyectos; workspace (`.kiro/`) manda sobre el global.
- **Spec:** *"Arranca una spec para el MVP del prospector"* → genero requisitos, diseño y lista de tareas para aprobar antes de construir.
- **Hook:** *"Crea un hook que corra los tests cuando guarde un archivo .py"* → configuro el trigger y la acción.
- **MCP:** *"Conecta el MCP de Supabase / Playwright / Tavily"* → agrego el server a `mcp.json` con su `command`, `args`, `env` y `autoApprove`.
- **Power:** activar/usar Powers ya instaladas (GitHub, Context7) desde el gestor.

## 3. Automatizaciones (Agent Hooks) — su potencial y cómo exprimirlo

**Qué son:** disparadores automáticos que ejecutan un **prompt de agente** o un **comando shell** cuando pasa algo en el IDE (guardar, crear, borrar archivo; antes de un comando; al terminar el agente; manual). En vez de pedir tareas rutinarias a mano, se hacen solas. Fuente: [kiro.dev/docs/hooks](https://kiro.dev/docs/hooks/).

**Triggers disponibles:** `fileEdited`, `fileCreated`, `fileDeleted`, `userTriggered` (manual/botón), `promptSubmit`, `agentStop`, `preToolUse`, `postToolUse`.

**Hooks de alto valor para nosotros** (inspirados en el adaptador Kiro de ECC, ver [`evaluacion-ecc.md`](evaluacion-ecc.md)):

| Hook | Trigger | Qué hace | Regla de oro |
|------|---------|----------|--------------|
| **quality-gate** | manual (botón) | build + typecheck + lint + tests antes de commit/entrega | Ahorra tiempo, menos errores |
| **tests-on-save** | `fileEdited` (`*.py`) | corre tests/typecheck al guardar → detecta bugs temprano | Menos errores |
| **security-check-on-create** | `fileCreated` (`**/auth/**`, `**/api/**`) | chequeo de seguridad en zonas sensibles | Reputación, cumplimiento |
| **secret-scan** | `promptSubmit` / `preToolUse` | evita filtrar API keys/secretos | Seguridad |
| **extract-patterns** | `agentStop` | sugiere aprendizajes → los guarda en un `lessons-learned.md` | Mejora continua (memoria) |
| **session-summary** | `agentStop` | resume lo hecho en la sesión | Trazabilidad |
| **habeas-data-check** (propio) | `fileCreated` (scrapers/prospección) | recuerda base legal + opt-out (Ley 1581) | Legal (pilar 5) |

**Cómo exprimirlas:** empezar con **quality-gate + tests-on-save + secret-scan** (las que más previenen errores caros), y sumar `extract-patterns` para que el sistema **aprenda de cada sesión** y alimente nuestra memoria modular. No activar 13 hooks de golde — cada uno cuesta contexto/tiempo; activar los que dan ROI.

## 4. MCP — darle herramientas a los agentes

Formato en `.kiro/settings/mcp.json` (concepto):

```json
{
  "mcpServers": {
    "supabase": { "command": "npx", "args": ["-y", "@supabase/mcp-server"], "env": { "SUPABASE_URL": "...", "SUPABASE_KEY": "..." }, "autoApprove": [] }
  }
}
```

- **Workspace vs global:** `.kiro/settings/mcp.json` (este proyecto) o `~/.kiro/settings/mcp.json` (todos).
- **Cuidado con el contexto:** cada MCP consume tokens de la ventana. **Mantener pocos activos** (regla validada: <10 MCP, <80 tools). Activar los del [stack](stack-y-orquestacion.md) §4 según la fase.
- Pídeme *"conecta el MCP de X"* y lo dejo listo (sin exponer secretos en el repo).

## 5. Flujo recomendado en Kiro para el prospector

1. **Steering** del proyecto (reglas + arquitectura clean-room). *(ya tenemos base)*
2. **Spec** del MVP: *"spec del flujo descubrir→trigger→decisor→email→copy"*.
3. **MCP**: conectar Supabase + Context7 + (Tavily/Playwright según fase).
4. **Construir** por tareas de la spec (yo ejecuto; Antigravity en paralelo para lo pesado).
5. **Hooks**: quality-gate + tests-on-save + secret-scan activos.
6. **Verificar** y entregar; `extract-patterns` alimenta la memoria.

> Todo esto lo puedes disparar **pidiéndomelo en lenguaje natural**. Tu rol: dirigir, probar, validar y corregir. El mío: construir y dejarlo funcionando.
