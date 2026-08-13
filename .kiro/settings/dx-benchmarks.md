# DX Benchmarks 2026 — Plano de Optimización de la Cabina de Mando

---
*   **Proyecto:** El Prospector Greenfield Build
*   **Fecha de Creación:** 7 de Julio de 2026
*   **Autoría:** Yeison Estiven Delgado Ordoñez (Fundador)
*   **Tronco Principal Git:** setup/base-conocimiento
---

> Reglas deterministas de operación del agente (Kiro + Claude Opus 4.8) para controlar costo de tokens,
> automatizar documentación y evitar bucles de alucinación. Documento de entorno, no de producto.

---

## 1. Circuit Breakers y Throttling de Loops Autónomos

Kiro factura por créditos **sin rate limits** de plataforma → el freno es responsabilidad de esta config,
no del proveedor. Un loop desbocado no da error de cuota: da factura.

### Matriz de mitigación de errores de loops

| Freno | Qué limita | Regla para TBBC | Acción al superar |
|---|---|---|---|
| `max_iterations` | Nº total de tool-calls por tarea | Tope dinámico ≈ **percentil 75** del baseline; extender solo bajo demanda | Pausar y pedir confirmación |
| `max_consecutive_tool_calls` | Llamadas idénticas/redundantes seguidas | **2–3** | **Abortar bucle + alerta de alucinación + HITL** |
| `max_old_tool_call_tokens` | Contexto arrastrado de tool-calls viejos | Acotado; purgar output irrelevante | Compactar/descartar |

**Directrices:**
- **Turnos dinámicos, no fijos:** el límite fijo en p75 recorta 24–68% del costo con impacto mínimo; la
  extensión bajo demanda supera al límite fijo.
- **Verificador determinista dentro del loop:** tests/lint/validación de esquema que bloqueen el avance.
  La diferencia entre "compórtate bien" y confianza de producción es código determinista en el loop.
- **HITL como interruptor final:** ningún loop autónomo cierra sin verificación humana.

---

## 2. Aislamiento de Contexto (Narrow-by-Default)

Mecanismo: **progressive disclosure** de Skills. Solo la `description` del frontmatter vive en el contexto
general (router liviano); el cuerpo completo entra **únicamente** al activarse por match o slash-command `/`.

**Reglas:**
1. El `description` del frontmatter es lo único residente → corto y de alta precisión de disparo.
2. Todo el detalle operativo (procedimiento, ejemplos, reglas) vive en el **cuerpo** → costo cero en tokens
   hasta invocar `/auditar-arquitectura` o `/diseno-hexagonal`.
3. **Narrow por defecto:** en conversación general las Skills pesadas aportan solo su descripción.
4. Herencia controlable con `disableInheritingDefaultResources` para custom agents que no deban cargar todo.

**Por qué importa:** el output cuesta 5x el input; un system prompt inflado a cientos de miles de tokens
convierte centavos por consulta en dólares. Narrow-by-default es dinero, no estética.

---

## 3. Hooks + Ledger (google-sheets MCP), append-only y asíncrono

### 3.1 `/cerrar-decision` → `decision_ledger`
Compactación estricta: **máx. 3 líneas (verbo + objeto + razón)** + fuentes con fecha (o `N/A` + supuesto).
Columnas: `fecha | modulo | tipo | conclusion | fuentes | estado`. Nunca sobrescribe (histórico inmutable).

### 3.2 `cost-audit` → `cost_ledger`
Fórmula real Claude Opus 4.8 ($5/M input, $25/M output), **reasoning facturado a tarifa de output**:

```
costo_USD = (tokens_in * 5 + (tokens_out + tokens_reasoning) * 25) / 1_000_000
```

- **Alerta al 75%** de `BUDGET_TASK_USD` → estado `alerta`; `>100%` → `excedido` + notificar + pausar loops.
- **`fuente_conteo: "estimado"`** obligatorio: no hay telemetría fiable de reasoning-tokens en runtime; el
  ledger opera con estimación rotulada, no con medición exacta. No se vende precisión que no se tiene.

---

## 4. Gobernanza de Código y Skill Generators

- **Patrón coordinador–especialista:** delegar subtareas a sub-agentes con contexto acotado → menos goal drift y menos tokens.
- **Trust boundary explícita:** herramientas destructivas o de gasto (enriquecimiento, escritura masiva) NO se auto-aprueban.
- **Skill Generators con compuerta humana (no negociable):**
  1. El agente **detecta** un patrón recurrente y **propone** una skill (borrador en `.kiro/skills/`).
  2. El proceso **se detiene** hasta validación y **firma explícita del Fundador**.
  3. Se rechaza toda skill con `description` ambigua/solapada (envenena el router → context bloat).
  4. Skill aprobada = con bloque de metadatos + versionada en el tronco.

---

## 5. Síntesis (regla de oro protegida)

| Mecanismo | Config | Regla de oro |
|---|---|---|
| Turnos dinámicos p75 + breaker | tope + extensión bajo demanda | Ahorrar dinero |
| max_consecutive_tool_calls = 2–3 | abortar + HITL | Ahorrar dinero/tiempo |
| Skills narrow | description mínima; cuerpo bajo `/` | Ahorrar dinero |
| cost-audit (reasoning a output) | fórmula $5/$25 + `fuente_conteo` | Medir dinero por unidad |
| /cerrar-decision append-only | ledger compacto ≤3 líneas | Ahorrar tiempo |
| Verificador determinista en loop | tests/lint bloqueantes | Ganar dinero (calidad) |
| Compuerta humana para Skills | firma del Fundador | Gobernanza |
