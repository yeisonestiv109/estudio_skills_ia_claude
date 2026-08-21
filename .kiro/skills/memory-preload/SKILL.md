---
name: memory-preload
description: "RETIRADA (21-ago-2026). No usar. Ver nota de cierre abajo — el MCP `memory` que esta skill requería fue removido de mcp.json."
---

# Precarga de Memoria — El Prospector (RETIRADA)

> **Nota de cierre (21-ago-2026, decisión del fundador, auditoría de arquitectura
> de memoria):** el MCP `memory` (`@modelcontextprotocol/server-memory`, grafo en
> `.kiro/memory/prospector-knowledge-graph.json`) se retiró de `mcp.json` — el
> archivo llevaba semanas configurado y documentado sin una sola entidad escrita
> (`{}` vacío), sin problema de negocio real detrás (viola "Lo Aburrido es Oro" de
> `04_Segundo_Cerebro/directrices_globales.md`), y solapado con lo que ya cubren
> Graphify (relaciones de código) y la memoria auto-persistente de Claude Code
> (decisiones, contexto). Mismo criterio que ya se aplicó una vez en este proyecto
> al retirar el `decision_ledger` de Google Sheets (24-jul-2026, ver
> `.kiro/skills/cerrar-decision/SKILL.md`): la trazabilidad vive 100% en el repo.
>
> Detalle completo → `04_Segundo_Cerebro/guia_arquitectura_memoria.md` §1.2.
>
> **Si en el futuro aparece un caso de uso real** que ni Graphify ni los `.md`
> del repo cubran (ej. relaciones humanas/negocio no versionables), reevaluar
> activarlo de nuevo — no reescribir esta skill de memoria, crear una nueva con
> el caso de uso concreto documentado primero.

Contenido original conservado abajo solo como referencia histórica de qué hacía.

<details>
<summary>Procedimiento original (no ejecutable, el MCP ya no está registrado)</summary>

1. Deriva 2-4 entidades ancla del pedido actual.
2. Lee el Knowledge-Graph vía el MCP `memory` (`search_nodes`/`open_nodes`/`read_graph`).
3. Inyección selectiva: carga solo el subgrafo pertinente.
4. Al terminar, persiste nuevas entidades/relaciones y encadena con `cerrar-decision`.

</details>
