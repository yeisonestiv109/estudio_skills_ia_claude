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

## Fórmula de costeo (Claude Opus 4.8 · $5/M input, $25/M output)
**Los tokens de reasoning se facturan a la tarifa de OUTPUT ($25/M)**, no como input y no gratis:

```
costo_USD = (tokens_in * 5 + (tokens_out + tokens_reasoning) * 25) / 1_000_000
```

## Acción
1. Capturar métricas de la tarea: `tokens_in`, `tokens_out`, `tokens_reasoning`, `n_tool_calls`, modelo.
2. Calcular `costo_estimado_USD` con la fórmula de arriba.
3. Escribir append-only en la pestaña `cost_ledger` del Google Sheet, incluyendo `fuente_conteo`.
4. Evaluar el **circuit breaker** (ver abajo) y alertar si se supera el presupuesto.

## Esquema de la fila (cost_ledger)
| Columna | Contenido |
|---|---|
| `fecha` | Timestamp ISO |
| `tarea` | Descripción corta |
| `modelo` | ej. claude-opus-4.8 |
| `tokens_in` / `tokens_out` / `tokens_reasoning` | Enteros |
| `n_tool_calls` | Entero |
| `costo_estimado_USD` | Decimal (fórmula de arriba) |
| `estado_presupuesto` | ok \| alerta \| excedido |
| `fuente_conteo` | **`"estimado"`** (estático) — ver nota de telemetría |

## Nota de telemetría (humildad epistémica, obligatoria)
No hay medición fiable de reasoning-tokens en runtime desde el hook; los tokens de reasoning son invisibles.
Por eso `fuente_conteo` se fija en **`"estimado"`**: el ledger reporta una estimación rotulada, NO una
medición exacta. Si Kiro llegara a exponer telemetría de uso real, se cambiaría a `"telemetria"`.

## Circuit Breaker (conceptual)
- **Presupuesto por tarea:** umbral configurable (ej. `BUDGET_TASK_USD`).
- **Alerta temprana:** si `costo_estimado_USD >= 0.75 * BUDGET_TASK_USD` → estado `alerta`.
- **Excedido:** si `costo_estimado_USD > BUDGET_TASK_USD` → marcar `excedido`, escribir en rojo y **notificar al fundador**; recomendar pausar loops autónomos.
- Conecta con la regla de oro "medir el dinero por unidad": la unidad es **costo por decisión de arquitectura validada**.

## MCP requerido
`google-sheets` (pestaña `cost_ledger`).
