# Auditoría del Pipeline (Dashboard) — separación de roles, calificación manual y bug de palabra clave

**Fecha:** 21-ago-2026
**Alcance:** `artf-pipeline-app` (frontend Next.js) + esquema real de Supabase
(`lrdtjsxtaadpgrzkchlw`). Todo lo de abajo está verificado leyendo el código
real y la base real — nada reconstruido de memoria ni de documentación
vieja. Datos migrados de Excel (`origen_escritura <> 'worker_ia'`) se
excluyeron a propósito de toda medición del bug de palabra clave, por
instrucción explícita — son ruido conocido, no el problema a diagnosticar.

## 1. Contexto — cómo funcionan hoy los 12 estados reales

Catálogo real (`estados_lead`, verificado en vivo, no los "~11" aproximados
del brief sino exactamente 12):

`nuevo(10) → contactado(20) → calificado(30) → agendado(40) → {no_show(45) |
show_up(50)} → oferta_presentada(60) → reservo_oferta_valientes(65) →
ganado(70)*`, más 3 estados de salida terminales alcanzables desde varios
puntos: `perdido(80)`, `descalificado(85)`, `nutricion(90)`.

Las transiciones válidas viven en `estado_transiciones` (whitelist, 39 filas)
y se hacen cumplir con el trigger `fn_motor_etapas` (`BEFORE INSERT/UPDATE`
en `gestion_leads`) — cualquier `UPDATE estado_id` que no esté en la
whitelist revienta con `TRANSICION_INVALIDA` (`SQLSTATE 23514`). Solo **2**
transiciones de las 39 tienen `requiere_rol` fijado (`show_up→ganado` y
`oferta_presentada→ganado`, ambas `'closer'`) — es el único punto donde el
rol se exige a nivel de base de datos.

**Comparación con el Sheet legado** (`apps-script-crm-bridge.md`,
`mapEstado()`): el Estado ahí era un dropdown de texto libre con validación
de lista (`ESTADOS_VALIDOS`), escrito por el bot vía mapeo de `etapa_actual`
o por un humano directamente en la celda — sin ninguna máquina de estados
real, sin whitelist de transiciones, sin rol asociado. El ERD v2/v3
(Supabase) es la primera vez que existe una máquina de estados real; el
Pipeline actual hereda esa base sólida pero, como se documenta abajo, nunca
terminó de construir la capa de UI que la aprovechara bien.

## 2. Hallazgos reales y correcciones aplicadas

### 2.1 — CRÍTICO: "Ganado" no registraba ninguna venta

**Antes:** el botón genérico "Avanzar estado → Ganado" en `PipelineBoard.tsx`
hacía `supabase.from("gestion_leads").update({estado_id})` directo. Un Closer
podía marcar un lead como Ganado sin que se creara NUNCA una fila en
`ventas` — sin comisión, sin monto, sin plan de cuotas, rompiendo por
completo el modelo de inmutabilidad financiera de partida doble ya
documentado (`06-arquitectura-objetivo-diagrams-as-code.md`).

**Corrección:** se quitó `"ganado"` de la lista de transiciones genéricas y
se agregó un formulario real de "Registrar venta" (producto, moneda, monto,
upfront, # cuotas) que llama a `fn_registrar_venta` — la única vía real por
la que `ventas` se crea y `gestion_leads` avanza a `ganado` (vía el trigger
`fn_venta_cierra_lead`, no un UPDATE directo del frontend).

**Bug propio encontrado y corregido en el camino** (verificación en sandbox
con `ROLLBACK`, no asumido): `fn_registrar_venta` con `p_num_cuotas > 1`
necesita `p_dia_cuota` no-nulo — lo usa para calcular `fecha_programada` de
cada cuota (`NOT NULL` en `pagos_cuotas`). Mi primer intento del formulario
mandaba `null` siempre y reventaba con `pagos_cuotas` `NOT NULL violation`
en cuanto alguien eligiera más de 1 cuota. Corregido: `p_dia_cuota = 30`
cuando `num_cuotas > 1`, `null` cuando es contado (1 sola cuota).

### 2.2 — No existía ninguna forma de guardar datos de calificación

**Antes:** `fn_columnas_por_rol` (trigger de seguridad a nivel de columna)
ya le daba a un Setter permiso de escribir `dolor`, `urgencia`, `califica`,
`fecha_calificacion`, `palabra_clave_ad`, `campana`, `utm_source`,
`utm_campaign`, `producto_interes_id` — pero el drawer del Pipeline solo
mostraba `dolor` como texto de solo lectura, y únicamente si ya existía.
Para los leads reales de Instagram (`fn_sync_bot_turn` solo captura
nombre/IG handle/fuente/último mensaje — `dolor`/`urgencia`/`califica` se
obtienen manualmente en la conversación, confirmado en sesiones previas), no
había NINGUNA manera de que un Setter guardara esos datos después de
calificar al lead. `NuevoLeadModal` solo cubre la creación manual de un
lead, no la edición de uno que ya llegó por el bot.

**Corrección:** nueva sección "Datos de calificación" en el drawer, visible
para Setter/Admin — `dolor` (textarea), `urgencia` (select), `califica`
(select) — que hace un `UPDATE` directo sobre las columnas que
`fn_columnas_por_rol` ya permitía. `fecha_calificacion` y `fecha_atendido`
se setean a `now()` la primera vez que se guarda (si no existían), sin
pisar un valor ya presente.

### 2.3 — Cero separación de roles en la UI (la base solo protege 1 paso)

**Antes:** cualquier usuario autenticado veía TODOS los botones de "Avanzar
estado" (incluidos los de después de `agendado`) y los de "Show Up / No
Show", sin importar su rol — la única barrera real era la que ya cubre
`fn_motor_etapas` para las 2 transiciones `→ganado`. Un Setter podía, por
ejemplo, mover un lead de `show_up` a `oferta_presentada` sin que nada se lo
impidiera (esa transición no tiene `requiere_rol`).

**Corrección — deliberadamente solo en la capa de UI, sin tocar
`estado_transiciones` ni ningún rol ya definido en la base** (restricción
explícita del encargo): se agregó `zonaDelEstado()` — Setter gestiona
`orden < 40` (nuevo/contactado/calificado), Closer gestiona `orden >= 40`
(agendado en adelante, inclusive, tal como se pidió: "Closers gestionan
DESDE agendado"). El bloque de "Avanzar estado" y el de "Show Up/No Show"
ahora se ocultan según esta zona y el rol del usuario logueado (Admin ve
ambas). Es un filtro de *qué se muestra*, no un cambio de qué es válido a
nivel de base — si algún día se decide que la base también debe exigirlo,
es un cambio aparte, fuera de este alcance.

### 2.4 — El bug de la palabra clave: SÍ se estaba registrando, nadie la veía

**Diagnóstico (no asumido — medido en vivo antes de tocar nada):**
`fn_derivar_palabra_clave()` funciona perfecto. De los 222 leads reales con
`origen_escritura='worker_ia'` (los de Instagram, excluyendo migración),
**el 100% tiene `palabra_clave_ad` poblada**, y se verificó contra el texto
real del mensaje (`activity_log.ultimo_msg_lead`) que el matching es
correcto: "Control" / "CONTROL 🔔" → `control` (176 casos), variantes de
"radiografía" → `radiografia` (31), el resto → `saludo_generico` (15). **La
causa raíz real no era de derivación, era de visibilidad**:
`vw_pipeline` — la única vista que consulta `getPipelineLeads()`, la fuente
de datos de todo el Pipeline — nunca seleccionaba esa columna, y ningún
archivo del frontend la mencionaba (`grep -rn "palabra_clave" src/` → 0
resultados antes de este cambio). El dato estaba perfecto en la base desde
el 18-ago; el Pipeline jamás lo pidió.

**Corrección:** migración
`20260821200523_vw_pipeline_expone_palabra_clave_ad.sql` — `CREATE OR
REPLACE VIEW` agregando `g.palabra_clave_ad` al final del `SELECT` (Postgres
exige mismo orden/nombres de columnas existentes en un `CREATE OR REPLACE
VIEW`, solo permite anexar). `security_invoker=true` se preservó explícito
(ya hay una regresión histórica documentada sobre justamente esto). Se
agregó al tipo `PipelineLead` y se muestra en el panel "Datos" del drawer
como "Palabra clave (IG)".

## 3. Cómo se verificó (no solo "debería funcionar")

- `npm run type-check` y `npm run lint`: verdes tras cada cambio.
- Suite E2E existente (`e2e/auth-and-panels.spec.ts`) corrida completa: el
  test de Incidencias pasó limpio; el de login falló una vez y pasó en
  aislamiento — coincide exactamente con la flakiness ya documentada en
  `AGENTS.md` ("timing del webServer reusado por Playwright, no una falla
  del bug en sí"), no es una regresión de este cambio.
- **Simulación de RLS real, no confianza ciega en el código:** dentro de una
  transacción con `ROLLBACK` al final (nada persistido), se simuló
  `SET LOCAL ROLE authenticated` + `request.jwt.claims` con el `auth_user_id`
  real de las cuentas fixture `QA Setter` y `QA Closer` (mismo patrón ya
  usado en sesiones previas del proyecto para verificar `fn_reclamar_lead`).
  Se probó, contra la base real: (a) un Setter guardando dolor/urgencia/
  califica sobre un lead ajeno recién creado — funcionó, RLS + columnas por
  rol lo permiten tal como se diseñó; (b) un Closer llamando
  `fn_registrar_venta` con 3 cuotas sobre un lead en `show_up` — **primero
  falló** (el bug de `p_dia_cuota` de la sección 2.1), después de corregirlo
  se confirmó `ventas` creada, `forma_pago='cuotas'`, 3 filas reales en
  `pagos_cuotas`, y `gestion_leads.estado_id` avanzado a `ganado` por el
  trigger — no por un UPDATE mío.
- **Verificación con navegador real** (script temporal, borrado después de
  usarlo — mismo patrón `_tmp-*` ya establecido en el proyecto): login real
  con la cuenta fixture `admin.qa@artf.test`, abrir un lead real del
  Pipeline en producción, confirmar que "Palabra clave (IG)" y "Datos de
  calificación" renderizan sin ningún error de consola.

## 4. Calificación final del sistema

**Backend/base de datos: sólido (9/10).** La máquina de estados, RLS,
inmutabilidad financiera y el diseño de columnas-por-rol ya estaban bien
pensados y correctamente implementados — el problema nunca fue el modelo de
datos, fue que la capa de UI se quedó a medio construir respecto a lo que la
base ya permitía y esperaba.

**Frontend/UX del Pipeline, antes de esta auditoría: 4/10.** Estados
básicos (nuevo→agendado) funcionaban bien, pero: cero forma de calificar un
lead real de IG, cero separación de roles visible, y el cierre de ventas
estaba, en la práctica, roto (nunca se generaba una venta real). Después de
esta auditoría: **7.5/10** — los 3 huecos de arriba están corregidos y
verificados en vivo, pero quedan pendientes reales fuera de este alcance
(ver sección 5) que le impiden un 9-10 honesto.

## 5. Lo que depende del desarrollo futuro de "Agenda" (fuera de este alcance, a propósito)

No se tocó nada de esto — pertenece a la sección 9 de "Planos ARTF"
(pausada explícitamente por decisión de Yeisiton, a la espera de diseñar
primero el flujo completo de Agenda):

- **`clientes.correo` vacío en la gran mayoría de leads reales**: hoy el
  lead escribe su correo directo en el formulario de Google Calendar
  Appointment Schedules, que nunca sincroniza de vuelta al CRM. Mientras
  Calendar siga bloqueado (permisos de organización, sin resolver), esto no
  tiene arreglo del lado del Pipeline — es create/booking flow de Agenda, no
  edición de lead.
- **Fechas reales de reunión / `reuniones.google_event_id`**: hoy siempre
  `NULL` para toda reunión nueva porque la integración con Calendar
  (`fn_registrar_evento_calendar`) sigue bloqueada — el fallback
  `fn_marcar_incidente_calendar` ya surge correctamente en el panel de
  Incidencias, no se tocó ni se necesitaba tocar.
- **El botón "Show Up / No Show"** (ahora gateado a Closer/Admin en esta
  auditoría) sigue funcionando hoy independientemente de Calendar — marca
  `reuniones.estado` directo, que es lo único de lo que depende
  `fn_reunion_mueve_etapa`. No bloqueado por Agenda, ya funcional.
- **Plan de cuotas real vs. reparto automático parejo**: `fn_registrar_venta`
  reparte el saldo en cuotas iguales; un plan de pagos custom (como el caso
  real de Edwar Martos, documentado en sesiones previas) sigue necesitando
  intervención manual en `pagos_cuotas` — no es parte de este alcance ni de
  Agenda, es una funcionalidad de ventas aparte, ya identificada como
  pendiente en rondas anteriores.

## 6. Archivos tocados

- `artf-pipeline-app/src/components/PipelineBoard.tsx` — formulario de
  calificación, filtro de zona por rol, formulario de registro de venta,
  muestra `palabra_clave_ad`.
- `artf-pipeline-app/src/lib/data/pipeline.ts` — `palabra_clave_ad` en el
  tipo `PipelineLead`, nuevo `getProductosActivos()`.
- `artf-pipeline-app/src/app/page.tsx` — pasa `productos` al Pipeline board.
- `artf-pipeline-app/supabase/migrations/20260821200523_vw_pipeline_expone_palabra_clave_ad.sql`
  — único cambio de esquema real, ya aplicado en producción y verificado.

Ningún estado, transición ni rol de `estado_transiciones`/`fn_columnas_por_rol`
se modificó — tal como pedía la restricción explícita del encargo.
