---
name: handoff-cierre-sesion
description: "Rutina de cierre de sesión de El Prospector. Úsala cuando el fundador diga 'cerremos sesión', 'handoff', 'deja listo para la próxima' o similar. Audita drift código↔spec, corre los tests, regenera el grafo Graphify, consolida la memoria en 3 niveles y deja el entorno listo para la siguiente sesión sin perder contexto."
---

# Handoff de Cierre de Sesión — El Prospector

> Antes era un hook `userTriggered`; se reclasificó como skill (24-jul-2026)
> porque es un procedimiento on-demand invocado por el fundador, no una
> reacción a un evento. Ver `.kiro/steering/estrategia-memoria.md`.

Ejecuta este protocolo en orden estricto. No inventes datos; si algo no se puede
verificar, dilo (antipsicofancia).

> Asume que se está cerrando sesión sobre `02_Lineas_de_Producto/Outbound_Prospector/`
> (única línea con código real hoy). Si el trabajo fue en Inbound_AI_SDR/ARTF, adapta
> las rutas de este protocolo a esa carpeta.

1. **AUDITORÍA DE DRIFT CÓDIGO↔SPEC:** compara
   `02_Lineas_de_Producto/Outbound_Prospector/src/core/domain/models.py`,
   `policies.py` e `interfaces.py` contra
   `02_Lineas_de_Producto/Outbound_Prospector/docs/modelos_dominio_core.md`.
   Si el código tiene enums, campos o puertos que la spec no documenta (o
   viceversa), sincroniza la spec AL código (el código ejecutable es la verdad).
   Para localizar rápido, usa `graphify query` antes de leer `src/` a mano.

2. **VERIFICACIÓN DE TESTS:** desde `02_Lineas_de_Producto/Outbound_Prospector/`,
   corre `uv run pytest -q` (entorno WSL2 de Yeisiton; NUNCA rutas de venv de
   Windows). Registra el nº de tests verdes. Si alguno falla, NO cierres la
   sesión: repórtalo y detente.

3. **RECONSTRUIR EL GRAFO:** `uv tool run --from graphifyy graphify extract . --code-only --force`
   seguido de `uv tool run --from graphifyy graphify cluster-only . --no-label --no-viz`
   para dejar `graphify-out/graph.json` y `GRAPH_REPORT.md` sincronizados.

4. **CONSOLIDAR MEMORIA EN 3 NIVELES:**
   - `01_Gobernanza_EOS/02_backlog_y_rocas.md`: qué se hizo, estado de cada Motor,
     objetivo de la próxima sesión (bloque fechado arriba, no borrar historial).
   - `02_Lineas_de_Producto/Outbound_Prospector/docs/`: si se validó un concepto
     nuevo, documéntalo.
   - `01_Gobernanza_EOS/02_backlog_y_rocas.md`, sección "BITÁCORA DE DECISIONES
     HISTÓRICAS": registra las decisiones técnicas con su porqué (encadena con
     la skill `cerrar-decision`).

5. **HIGIENE:** confirma que no quedaron archivos temporales ni secretos
   expuestos, que `.env` sigue en `.gitignore` y que `graphify-out/` está ignorado.

6. **REPORTE FINAL:** resumen de máximo 5 viñetas con el estado exacto para la
   sesión nueva; confirma LUZ VERDE o lista los bloqueos pendientes.

Respeta `AGENTS.md` y `estrategia-memoria.md`: antipsicofancia, no inventar
datos, citar fuente+fecha, poda sináptica (cada concepto en su nivel).
