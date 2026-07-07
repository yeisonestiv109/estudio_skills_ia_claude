# Hook: memory-preload (Pre-Prompt · Memoria de contexto entre sesiones)

---
*   **Proyecto:** El Prospector - Vía B Greenfield Build
*   **Fecha de Creación:** 7 de Julio de 2026
*   **Autoría:** Yeison Estiven Delgado Ordoñez (Fundador)
---

> Especificación lógica del hook nativo de Kiro. Evita "trabajar a ciegas": antes de una tarea compleja,
> el agente recupera el conocimiento persistente del Prospector desde el **Memory MCP (knowledge-graph)**.
> NOTA: esta función NO la cubre `context7` (que es docs vivas de librerías, pausado hasta la fase de código).

## Disparador (trigger)
- **Tipo:** pre-prompt en tareas marcadas como complejas (diseño de módulo, auditoría, decisión estratégica),
  o invocación manual `/memory-load`.

## Acción
1. Consultar el `Memory MCP` por entidades/relaciones relevantes a la tarea (ej. "M1", "cascada de triggers", "reglas de oro").
2. Inyectar solo el subconjunto pertinente en el contexto (evitar context bloat).
3. Al cerrar la tarea, **persistir** las nuevas entidades/relaciones aprendidas (idealmente encadenado con `/cerrar-decision`).

## Por qué un knowledge-graph (y no context7)
- La memoria semántica entre sesiones requiere **entidades + relaciones persistentes en disco**, no recuperación de docs.
- `context7` inyecta documentación version-específica de librerías — útil al **codificar**, inútil como memoria.

## MCP requerido (a agregar)
`memory` (servidor knowledge-graph). Configuración en [`../settings/mcp.json`](../settings/mcp.json).

## Guardrails
- Cargar **solo lo pertinente** a la tarea (no todo el grafo) → disciplina de tokens.
- No sobrescribir memoria con datos no validados; marcar supuestos como tales.
