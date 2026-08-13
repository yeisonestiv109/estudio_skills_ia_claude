---
name: memory-preload
description: "Antes de una tarea de alta complejidad arquitectónica (diseñar/auditar un módulo, tomar una decisión estratégica), recupera del Knowledge-Graph del MCP 'memory' el subgrafo pertinente para no trabajar a ciegas. Úsala cuando el fundador diga 'precarga memoria', 'qué sabemos de X', o antes de empezar un diseño complejo."
---

# Precarga de Memoria — El Prospector

> Reclasificado de hook a skill (24-jul-2026): es un procedimiento on-demand
> previo a tareas complejas, no una reacción a un evento.

Requiere el MCP `memory` activo (config en `.kiro/settings/mcp.json`,
`MEMORY_FILE_PATH` absoluto a `.kiro/memory/prospector-knowledge-graph.json`).

1. **Deriva 2-4 entidades ancla** del pedido actual (ej. Motor 2, Negative ICP,
   descubrimiento, ScoreTriggerPolicy, reglas de oro).

2. **Lee el Knowledge-Graph** vía el MCP `memory` (`search_nodes` / `open_nodes`
   / `read_graph`) sobre esas claves para traer decisiones previas, riesgos ya
   identificados y contratos de puertos relacionados.

3. **Inyección selectiva:** carga SOLO el subgrafo pertinente al contexto, nunca
   el grafo completo (anti context-bloat, disciplina de tokens).

4. **Al terminar la tarea**, persiste las nuevas entidades/relaciones
   (`create_entities` / `create_relations` / `add_observations`) y encadena con
   la skill `cerrar-decision`.

GUARDRAILS: cargar solo lo pertinente; no sobrescribir memoria con datos no
validados (marca supuestos como tales). Usa el MCP `memory`, NO context7.
Complementa —no reemplaza— la jerarquía de verdad de `estrategia-memoria.md`
(el código ejecutable siempre le gana a la memoria). Respeta `AGENTS.md`.
