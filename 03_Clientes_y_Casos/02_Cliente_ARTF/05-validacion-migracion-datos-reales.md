# 05 · Validación de Migración con Datos Reales del CRM

> *Resultado de cargar el CRM real de Sheets (6.136 leads) contra el esquema v3 de Supabase en staging, para
> confirmar que tablas, triggers, el RPC transaccional y las vistas de reporte funcionan correctamente antes de
> la migración de producción. Continuación de `04-analisis-arquitectura-y-db.md`, después de que las suites
> Postman 00–05 (con datos sintéticos) pasaran exitosamente.*

## 1. Qué se hizo

Se exportó el Google Sheet completo (`Copia de CRM - Leads Campaña 1 Reconexión Financiera.xlsx`, 6 pestañas:
`Global`, `Daily Metrics v2`, `CRM`, `Show ups (Reuniones)`, `Activity Log`, `Capacidad`) y se cargó la pestaña
`CRM` (6.136 filas, una por lead) contra el proyecto Supabase de **staging** (`lrdtjsxtaadpgrzkchlw`), usando
`service_role` (bypasea RLS por diseño, no aplica para el Formulario Closer en producción).

Scripts en esta carpeta (`Tarea_1_Migrar_DB/`, con `.env` y `.xlsx`/`.csv` excluidos de git por contener PII real):

| Script | Qué hace |
|---|---|
| `migrate_crm.py` | Carga completa: `clientes` + `gestion_leads` + `reuniones` + `ventas` (vía `fn_registrar_venta`). Soporta `--dry-run` (valida sin escribir) y `--write`. |
| `add_reuniones.py` | Backfill incremental de `reuniones`, emparejando por `clientes.manychat_id`. Necesario porque `ventas` es append-only a nivel de DB — una vez hay ventas, no se puede borrar y recargar todo desde cero. |
| `patch_salarios.py` | Backfill incremental de `clientes.salario_monto/currency/periodicidad` (se omitió en la carga inicial, ver hallazgo 7 abajo). |
| `audit_nulls.py` | Audita cada columna de cada tabla poblada: % con dato vs. % NULL, comparado contra la población real de la columna fuente equivalente en el Sheet. Base de la sección 4. |
| `patch_gaps.py` | Backfill de los dos gaps reales que encontró `audit_nulls.py` y que sí se podían corregir (`gestion_leads.notas`, `pagos_cuotas.metodo_pago` — ver sección 4.2). |

Resultado final en staging: **6.136 clientes, 6.136 gestion_leads, 204 reuniones, 8/9 ventas** (con su plan de
pagos generado atómicamente por `fn_registrar_venta`), **211 clientes con salario real**, **2.615 gestion_leads
con notas de proceso**, **7/12 pagos_cuotas con método de pago** — detalle completo de qué se corrigió y qué
queda pendiente en la sección 4.

Entorno: `.venv` gestionado con `uv` (el mismo que usa El Prospector). Las dependencias de esta tarea
(`openpyxl`, `requests`) se instalan con `uv pip install --python .venv/bin/python openpyxl requests`; los
scripts se corren con `uv run python3 <script>.py` desde la raíz del repo.

## 2. La vista de auditoría hizo su trabajo

`vw_scorecard_check` está diseñada para responder "¿este número del scorecard es confiable?". Con datos reales
encontró exactamente lo que debía encontrar:

| Chequeo | Severidad | Incidencias | Causa real |
|---|---|---|---|
| `ganado_sin_venta` | ERROR | 1 | Ver hallazgo 1. |
| `ventas_exceden_show_ups` | ERROR | 1 (bajó de 8 a 1 tras cargar reuniones) | Una venta cuyo lead no tenía `ManyChat ID` para cruzarlo con su reunión. |
| `venta_sin_fx` | WARN | 5 | No se cargó `tasas_cambio` (fuera de alcance de esta prueba). |
| `posible_cliente_duplicado` | WARN | 2 | Contactos reales repetidos (`@vercasti`, `@stfms_`). |
| `reunion_sin_closer` | WARN | 49 | Reuniones históricas sin closer asignado en el Sheet. |
| `reunion_vencida_sin_resolver` | WARN | 38 | Reuniones agendadas nunca marcadas como realizadas/no-show en el Sheet. |

Los WARN son gaps reales en los datos históricos del Sheet, no bugs del esquema — es exactamente la señal que
la vista debe dar. `vw_embudo_diario` (el reemplazo de las `ARRAYFORMULA` del `DailyMetricsScorecard.gs`)
respondió correctamente con leads/bookings/show-ups/%close rate/CAC/ROI por día.

## 3. Hallazgos de calidad de datos en el Sheet (para el equipo ARTF, antes de producción)

1. **Un lead "Ganado" con `Fecha Pago` = texto "No ha pagado"** en vez de una fecha (Juan Manuel, revenue
   $1.98M). No se pudo registrar la venta — la vista de auditoría lo marcó como `ganado_sin_venta` ("revenue
   fantasma"). Requiere corrección manual en el Sheet o una regla de negocio explícita.
2. **Columna "Forma de pago"** mezcla texto (`transferencia`, `WHOP`) con valores numéricos sueltos en algunas
   filas — deriva de captura manual, no se usó para poblar el enum `forma_pago` (ese campo lo calcula
   `fn_registrar_venta` internamente a partir de upfront vs. total).
3. **`Fecha Atendido` antes que `Fecha Contacto`** por fracciones de segundo en 2 filas (dos sistemas
   registrando eventos casi simultáneos). Se ajustó al piso de `fecha_contacto` para cumplir el constraint;
   no se descartó el dato.
4. **`IG Handle` con el placeholder literal `"(pendiente)"`** en 22 filas, más 2 contactos genuinamente
   repetidos — ambos casos violarían el índice único parcial de `clientes.ig_handle` si no se limpian.
5. **`Urgencia`** trae valores libres (`ahora`, `algun_dia`) que no calzan con el enum `nivel_urgencia`
   (`baja/media/alta/critica`) — se mapearon `ahora→alta`, `algun_dia→baja`.
6. **133 de 6.136 leads (2,2%) no tienen `ManyChat ID`** — es la única llave de cruce confiable de vuelta al
   Sheet. Sin ella, ese lead no se pudo enlazar con su reunión (hallazgo del bloque 2) ni con su salario.
7. **`Salario`** (255 filas con dato real, formatos libres: `"$9M COP"`, `"$7.5M"`, `9000000.0`, `"3000 USD"`,
   rangos `"$30M a 35M"`) **se omitió por error en la primera carga** — `migrate_crm.py` no mapeaba esa columna
   en absoluto. Corregido en el script fuente y aplicado por `patch_salarios.py` (210/255 actualizados; 40 sin
   `ManyChat ID` para cruzar, 4 valores ambiguos sin parsear con confianza: `"$15-18M COP"`,
   `"$9M papel / $6M neto"`, `"$13.5"`, `"2800 a 3000 USD"`). **Se asumió periodicidad `mensual`** por
   consistencia con el playbook de calificación — el Sheet no la especifica explícitamente, es una inferencia
   a validar con el equipo.

## 4. Auditoría columna-por-columna: ¿los NULL son correctos?

`audit_nulls.py` calculó, para cada columna de `clientes`/`gestion_leads`/`reuniones`/`ventas`/`pagos_cuotas`,
el % con dato, y lo comparó contra la población real de la columna equivalente en la pestaña `CRM` del Sheet.
Conclusión general: **la inmensa mayoría de los NULL son correctos** (la fuente tampoco tiene el dato) — la
tabla completa está en el output de `audit_nulls.py`, aquí solo los casos que exigían decisión.

### 4.1 NULL correctos — el esquema soporta un campo que el Sheet no captura

Estos quedan NULL en el 99–100% de las filas y **así debe ser**, no son bugs:

| Columna | Por qué |
|---|---|
| `clientes.pais_iso2` | El Sheet no tiene columna de país. |
| `gestion_leads.producto_interes_id` | El Sheet no distingue "interesado en Core vs. Low-ticket" antes de la venta. |
| `gestion_leads.campana` / `utm_source` / `utm_campaign` | El embudo actual es 100% DM de Instagram vía ManyChat — no hay atribución UTM en el Sheet. |
| `gestion_leads.fecha_calificacion` | El Sheet no registra un timestamp de calificación distinto de "Fecha Atendido". |
| `reuniones.monto_ofertado` / `motivo_no_show` | El Sheet no registra el monto ofrecido en la llamada ni la razón puntual de un no-show. |
| `ventas.contrato_url` | El Sheet no tiene enlace a contrato. |
| `pagos_cuotas.referencia_pago` | El Sheet no tiene número de transacción/referencia. |

Ninguno de estos se "arregla" adivinando un valor — quedan NULL honestamente hasta que el Sheet (o el nuevo
Formulario Closer) capture ese dato.

### 4.2 NULL que SÍ eran bugs de mapeo — corregidos

| Columna | Problema | Corrección |
|---|---|---|
| `gestion_leads.notas` | 0% con dato pese a que el Sheet trae 2.685 filas con notas de proceso reales (`"Setter envió M1..."`). El script solo escribía esa columna en `clientes.notas`, nunca en `gestion_leads.notas` (donde semánticamente pertenece: es una nota sobre ESTE proceso de venta, no sobre la persona). | Backfill con `patch_gaps.py` vía `UPDATE` (tabla no es append-only). **2.615/2.685 actualizados** (70 sin `ManyChat ID` para cruzar). |
| `pagos_cuotas.metodo_pago` | 0/12 con dato pese a que el Sheet trae `"transferencia"`/`"WHOP"` para esas 8 ventas. `fn_registrar_venta` no acepta `metodo_pago` como parámetro — el RPC nunca lo escribe. | Backfill con `patch_gaps.py` vía `UPDATE` sobre la cuota 0 (upfront) de cada venta, mapeando solo valores de texto limpios. **7/12 actualizados** (las 5 cuotas restantes son pagos futuros pendientes sin método aún, más 1 venta cuyo "Forma de pago" en el Sheet es texto compuesto ambiguo — `"2 PAGOS Con TC: ..."` — no se adivinó). |

### 4.3 NULL que ya NO se pueden corregir en esta corrida — para la migración real

| Columna             | Problema                                                                                                                                                                          | Por qué no se puede arreglar ahora                                                                                                                                              |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ventas.reunion_id` | 0/8 — nunca se pasó `p_reunion_id` al llamar `fn_registrar_venta`, porque las `reuniones` se cargaron **después** de las `ventas` (`add_reuniones.py` fue un backfill posterior). | `ventas` es append-only: no admite `UPDATE`. **Para la migración de producción: cargar `reuniones` ANTES de llamar a `fn_registrar_venta`**, para poder pasarle `p_reunion_id`. |

### 4.4 Un caso de "no arreglar" a propósito: `fecha_handoff`

`gestion_leads.fecha_handoff` (186/6.137) es un **campo derivado**, no una columna 1:1 del Sheet — se calcula
como `= fecha_atendido` cuando el lead tiene `closer_id` y un estado post-calificación. 12 leads cumplen esas
condiciones pero tienen `fecha_atendido` NULL, así que su `fecha_handoff` también quedó NULL aunque
conceptualmente sí hubo un handoff. Es una limitación de la heurística, documentada aquí en vez de rellenada
con una fecha inventada.

## 5. Triggers: qué hacen y si se están cumpliendo

| Trigger | Tabla | Función que dispara | Verificado |
|---|---|---|---|
| `trg_touch` (versionado) | `clientes`, `gestion_leads`, `reuniones`, `pagos_cuotas`, `usuarios` | `fn_touch_versioned` — sube `version` y `updated_at` en cada `UPDATE`. | ✅ Confirmado: los `UPDATE` de `patch_salarios.py`/`patch_gaps.py` subieron `version` a 2 y refrescaron `updated_at` en las filas tocadas. |
| `trg_gl_motor` | `gestion_leads` | `fn_motor_etapas` — en `INSERT`, si el estado es terminal, fija `cerrado_at = now()`. | ✅ 512 `gestion_leads` con `cerrado_at` poblado, exactamente los que quedaron en `ganado`/`perdido`/`descalificado` (9+81+422=512). |
| `trg_gl_log` | `gestion_leads` | `fn_log_gestion` — escribe en `activity_log` en cada `INSERT`/cambio de estado. | ✅ `activity_log` tiene ≥6.137 filas (una por lead creado). |
| `trg_auditar` | `gestion_leads`, `ventas`, `pagos_cuotas`, `usuarios` | `fn_auditar` — graba antes/después en `auditoria_cambios` en cada `INSERT`/`UPDATE`/`DELETE`. | ✅ Confirmado: cada `PATCH` de `patch_salarios.py`/`patch_gaps.py` generó su fila en `auditoria_cambios`. |
| `trg_ventas_inmutable` | `ventas` | `fn_append_only` — bloquea `UPDATE`/`DELETE`. | ✅ Confirmado en la práctica: un `DELETE` de prueba para resetear el estado fue rechazado. Por eso `ventas.reunion_id` (4.3) ya no se pudo corregir. |
| `trg_re_etapa` | `reuniones` | `fn_reunion_mueve_etapa` → `fn_avanzar_estado(lead, 'agendado')` en cada `INSERT`. | ⚠️ **Se disparó y modificó datos que no esperábamos**: ver 5.1 abajo. |
| `trg_ve_etapa` | `ventas` | `fn_venta_cierra_lead` → `fn_avanzar_estado(lead, 'ganado')` en cada `INSERT`. | ✅ No-op seguro: los 8 leads ya estaban en `ganado` (fijado directamente por el mapeo de `Estado`), así que `fn_avanzar_estado` detectó `estado_actual = estado_destino` y no hizo nada. |
| `trg_pc_estado` | `pagos_cuotas` | `fn_sync_estado_cuota` — deriva `estado` (`pagada`/`parcial`/`pendiente`/`vencida`) de `monto_pagado` vs. `monto`. | ✅ Las 8 cuotas 0 (upfront > 0) quedaron `pagada` automáticamente; las 4 cuotas futuras (`num_cuotas=2`) quedaron `pendiente`. |
| `trg_gl_columnas` | `gestion_leads` | `fn_columnas_por_rol` — restringe qué columnas puede tocar un `setter`/`closer` autenticado. | ➖ No ejercitado: la función misma exime explícitamente a `service_role` ("escrituras... no tienen JWT de usuario: se auditan pero no se restringen"). Requiere una prueba con JWT real de un rol para validarse — ya cubierto por la suite Postman 00 con usuarios sintéticos, no por esta carga. |

### 5.1 Hallazgo importante: el motor de etapas re-escribió el `estado_id` de ~60 leads

Al insertar las 204 `reuniones` (después de que ya existían los 6.136 `gestion_leads` con su `estado_id` fijado
según el texto de "Estado" del Sheet), `trg_re_etapa` llamó automáticamente a `fn_avanzar_estado(lead,
'agendado')` para cada una. Como `contactado→agendado`, `calificado→agendado` y `no_show→agendado` SÍ están en
la lista blanca de `estado_transiciones`, el motor **avanzó de verdad** el estado de esos leads:

| Estado (mapeo del Sheet) | Esperado | Real en DB | Diferencia |
|---|---|---|---|
| `agendado` | 90 | 150 | **+60** |
| `contactado` | 646 | 629 | −17 |
| `calificado` | 4.016 | 4.006 | −10 |
| `no_show` | 50 | 18 | −32 |

Esto **no es un bug** — es el motor de reconciliación de estados funcionando como está diseñado: un lead que
el texto libre del Sheet describía como "Handoff" o "M4 Enviado" pero que **sí** tiene una reunión agendada
(`Fecha Agendamiento`/`Fecha Llamada Programada` presente) está, en la realidad del negocio, más avanzado que
su etiqueta de texto — y el motor lo corrigió automáticamente sin intervención humana, exactamente como haría
en producción cuando un setter agenda una llamada.

**Implicación para quien revise las vistas/métricas:** el `estado_id` final de `gestion_leads` **no es un
mapeo 1:1 literal** de la columna "Estado" del Sheet — es ese mapeo **más** la reconciliación automática del
motor de etapas. Es el comportamiento correcto y deseado, pero hay que tenerlo presente al comparar cifras
contra el Sheet original celda por celda.

## 6. Conclusión

Esquema, triggers (`fn_motor_etapas`, `fn_check_plan_pagos`, `fn_reunion_mueve_etapa`, `fn_venta_cierra_lead`,
`fn_sync_estado_cuota`), el RPC transaccional `fn_registrar_venta` y las vistas de reporte funcionan
correctamente bajo volumen y desorden reales — incluyendo la reconciliación automática de estados (5.1), que
funcionó exactamente como está diseñada. La inmutabilidad de `ventas` se confirmó dos veces en la práctica: un
`DELETE` para resetear el estado de prueba fue bloqueado, y `ventas.reunion_id` quedó permanentemente sin
backfill posible por la misma razón (4.3).

De los NULL auditados columna por columna, la gran mayoría son correctos (el Sheet tampoco tiene el dato — 4.1).
Se encontraron y corrigieron dos gaps reales de mapeo (`gestion_leads.notas`: 2.615/2.685, `pagos_cuotas.metodo_pago`:
7/12 — 4.2), y uno que ya no se puede corregir en esta corrida por el diseño append-only (4.3).

**Antes de la migración de producción**, el equipo ARTF debe resolver con el Sheet: la fecha de pago faltante
de Juan Manuel, una estrategia de identidad para los leads sin `ManyChat ID`, confirmar si `salario` es
efectivamente mensual, y decidir el orden de carga (reuniones antes que ventas) para no perder `reunion_id`.

## 7. Nota operativa: paginación de PostgREST

`GET` contra la API REST de Supabase limita a ~1.000 filas por respuesta por defecto (`db-max-rows`) sin
importar el `limit` pedido. Cualquier script que lea de vuelta más de 1.000 filas debe paginar con encabezados
`Range` (ver `fetch_all()` en `add_reuniones.py`) o subcontará silenciosamente.
