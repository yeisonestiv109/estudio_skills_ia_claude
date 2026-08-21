---
name: cerrar-decision
description: "Registra una decisión o validación concluida en la bitácora local, append-only y con trazabilidad. Úsala cuando el fundador diga 'cierra esta decisión', 'registra en bitácora', o al concluir una decisión técnica/estratégica que deba quedar documentada con su porqué."
---

# Cerrar Decisión — El Prospector

> Reclasificado de hook a skill (24-jul-2026) y **reapuntado**: antes escribía en
> un `decision_ledger` de Google Sheets vía MCP; ese MCP se eliminó del proyecto
> (24-jul-2026, decisión del fundador). Ahora la trazabilidad vive 100% en el
> repo (fuente de verdad única, versionada en git).

1. **Resume la decisión** recién concluida en un registro estructurado de 1-3
   líneas accionables.

2. **Persiste en la bitácora local**, dentro de `01_Gobernanza_EOS/02_backlog_y_rocas.md`,
   sección "BITÁCORA DE DECISIONES HISTÓRICAS" (append-only, nunca sobrescribas
   entradas previas — agrega un bloque nuevo fechado). Esquema del bloque:
   - **Fecha:** timestamp ISO.
   - **Módulo:** M1 / M2 / M3 / M4 / entorno.
   - **Tipo:** decision | riesgo | investigacion.
   - **Conclusión:** el registro de 1-3 líneas.
   - **Fuentes:** URLs con fecha, o "N/A".
   - **Estado:** propuesto | validado | descartado.
   Para decisiones de arquitectura estructurales, considera además una entrada
   en el ledger append-only `.kiro/history/architecture_ledger.md`.

3. **Confirma en el chat** el archivo/entrada escrita para trazabilidad.

> ~~Paso 3 original: persistir en el Knowledge-Graph vía MCP `memory`.~~ Retirado
> 21-ago-2026 — ver `memory-preload/SKILL.md` (el MCP nunca se alimentó, se
> eliminó de `mcp.json`). La trazabilidad vive 100% en este archivo append-only,
> mismo criterio ya aplicado al retirar el `decision_ledger` de Sheets.

GUARDRAILS: append-only (nunca sobrescribas). Antipsicofancia: si la decisión
carece de fuente verificable, registra `fuentes=N/A` y márcala como supuesto.
No inventes datos. Respeta `AGENTS.md` y `estrategia-memoria.md`.
