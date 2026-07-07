# Hook: cost-audit (Post-Tarea · Auditoría de costos y tokens)

---
*   **Proyecto:** El Prospector - Vía B Greenfield Build
*   **Fecha de Creación:** 7 de Julio de 2026
*   **Autoría:** Yeison Estiven Delgado Ordoñez (Fundador)
---

> Especificación lógica del hook nativo de Kiro. Control financiero exacto del consumo de un modelo de
> alta capacidad (Claude Opus 4.8), donde output y reasoning son el costo dominante.

## Disparador (trigger)
- **Tipo:** fin de tarea (o invocación manual `/cost-audit`).

## Acción
1. Capturar métricas de la tarea: `tokens_in`, `tokens_out`, `tokens_reasoning`, `n_tool_calls`, modelo.
2. Estimar `costo_estimado_USD` según tarifa del modelo.
3. Escribir append-only en la pestaña `cost_ledger` del Google Sheet.
4. Evaluar el **circuit breaker** (ver abajo) y alertar si se supera el presupuesto.

## Esquema de la fila (cost_ledger)
| Columna | Contenido |
|---|---|
| `fecha` | Timestamp ISO |
| `tarea` | Descripción corta |
| `modelo` | ej. claude-opus-4.8 |
| `tokens_in` / `tokens_out` / `tokens_reasoning` | Enteros |
| `n_tool_calls` | Entero |
| `costo_estimado_USD` | Decimal |
| `estado_presupuesto` | ok \| alerta \| excedido |

## Circuit Breaker (conceptual)
- **Presupuesto por tarea:** umbral configurable (ej. `BUDGET_TASK_USD`).
- **Regla:** si `costo_estimado_USD > BUDGET_TASK_USD` → marcar `excedido`, escribir en rojo y **notificar al fundador**; recomendar pausar loops autónomos.
- **Umbral de alerta temprana:** al 75% del presupuesto → `alerta`.
- Conecta con la regla de oro "medir el dinero por unidad": la unidad es **costo por decisión de arquitectura validada**.

## MCP requerido
`google-sheets` (pestaña `cost_ledger`).
