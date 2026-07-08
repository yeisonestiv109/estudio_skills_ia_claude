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

## Estructura del pre-prompt (antes de tareas de alta complejidad arquitectónica)
Se ejecuta ANTES de diseñar/auditar un módulo o tomar una decisión estratégica:

1. **Derivar claves de la tarea:** extraer 2–4 entidades ancla del pedido (ej. `M3`, `CRM`, `BANT`, `reglas de oro`).
2. **Leer el Knowledge-Graph:** `search_nodes` / `open_nodes` / `read_graph` sobre esas claves para traer
   decisiones previas, riesgos ya identificados y contratos de puertos relacionados.
3. **Inyección selectiva:** cargar SOLO el subgrafo pertinente al contexto (nunca el grafo completo → anti context-bloat).
4. **Cierre:** al terminar, persistir las nuevas entidades/relaciones (encadenar con `/cerrar-decision`).

## Almacenamiento del Knowledge-Graph (nota honesta)
El `Memory MCP` estándar persiste el KG en **archivo** (`MEMORY_FILE_PATH`), que es lo que queda activo por
defecto y funciona sin infraestructura extra. Si más adelante se prefiere un **backend relacional**
(Postgres/Supabase) para el KG, se cambia el servidor de memoria por uno con adaptador relacional **sin
tocar la lógica de este hook** — el hook consulta el puerto de memoria, no el motor de almacenamiento.

## Por qué un knowledge-graph (y no context7)
- La memoria semántica entre sesiones requiere **entidades + relaciones persistentes**, no recuperación de docs.
- `context7` inyecta documentación version-específica de librerías — útil al **codificar**, inútil como memoria.

## MCP requerido
`memory` (servidor knowledge-graph). Configuración en [`../settings/mcp.json`](../settings/mcp.json).

## Guardrails
- Cargar **solo lo pertinente** a la tarea (no todo el grafo) → disciplina de tokens.
- No sobrescribir memoria con datos no validados; marcar supuestos como tales.
