# Hook: cerrar-decision (Post-Prompt · Documentación automática)

---
*   **Proyecto:** El Prospector - Vía B Greenfield Build
*   **Fecha de Creación:** 7 de Julio de 2026
*   **Autoría:** Yeison Estiven Delgado Ordoñez (Fundador)
---

> Especificación lógica del hook nativo de Kiro. Se materializa en el sistema de Hooks de Kiro
> (`.kiro/hooks/`, acción tipo *agent prompt*). Escribe el ledger de decisiones sin fricción para el fundador.

## Disparador (trigger)
- **Tipo:** invocación **manual** vía comando `/cerrar-decision`.
- **Por qué manual y no en cada turno:** disparar en cada mensaje quema tokens. El registro ocurre solo cuando una decisión se cierra de forma explícita.

## Acción (agent prompt)
1. Resumir la decisión/validación recién concluida en un registro estructurado.
2. Llamar al MCP `google-sheets` para **append-only** en la hoja `decision_ledger`.
3. Confirmar en el chat el `row` escrito (trazabilidad).

## Esquema de la fila (decision_ledger)
| Columna | Contenido |
|---|---|
| `fecha` | Timestamp ISO |
| `modulo` | Módulo/área afectada (ej. M1, M2, entorno) |
| `tipo` | decision \| riesgo \| investigacion |
| `conclusion` | Resumen accionable de 1–3 líneas |
| `fuentes` | URLs / referencias con fecha (o "N/A") |
| `estado` | propuesto \| validado \| descartado |

## Guardrails
- **Append-only:** nunca sobrescribe filas previas (ledger histórico inmutable).
- **Antipsicofancia:** si la decisión carece de fuente verificable, se registra `fuentes = N/A` y se marca como supuesto.
- **Sin datos inventados.**

## MCP requerido
`google-sheets` (ya autorizado). Herramientas típicas: `sheets_batch_get_values`, `sheets_append` / `sheets_batch_update`.
