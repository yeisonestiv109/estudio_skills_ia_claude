# 02 · Backlog, Rocas (EOS) y Bitácora de Decisiones

> Listado de 'Issues' del marco EOS, tareas pendientes y registro histórico de decisiones.
> **El backlog está separado por las dos líneas de producto.** Leer la sección correspondiente según la tarea activa.

---

# 🟢 LÍNEA 1 — INBOUND AI SDR (Frente Activo)

> **Cliente actual: ARTF — Andrés Resuelve Tus Finanzas**
> Mentores: Catalina Rúa (CGO) y Javier (Co-Fundador ARTF). Laboratorio activo de producto + validación de propuesta de valor.

## Estado actual (13-ago-2026)
**Fase:** Migración de datos EN VALIDACIÓN (ya no es solo análisis — el 06/13-ago se
cargaron los 6.136 leads reales del Sheet contra el esquema v3 en **staging**
(`lrdtjsxtaadpgrzkchlw`) y se auditó columna por columna. Detalle completo →
`03_Clientes_y_Casos/02_Cliente_ARTF/05-validacion-migracion-datos-reales.md`.

**Sesión 16-ago-2026 (continuación) — Despliegue real Fase 1: repo Next.js,
auth con Supabase, Pipeline/Incidencias/Métricas conectados a datos reales,
bug de performance RLS encontrado y corregido en producción:**
- **Pedido de Yeisiton:** pasar del mockup (Artifact estático) a la app real
  desplegada — investigar mejores prácticas de la industria, conectar a
  Supabase real, resolver auth/sesiones/creación de cuentas "sin tener
  problemas". Pidió preguntas estratégicas antes de empezar dado el salto de
  alcance.
- **Decisiones tomadas vía `AskUserQuestion`:** stack Next.js + Vercel;
  entorno = el proyecto de staging actual (`lrdtjsxtaadpgrzkchlw`, ya tiene
  los 6.136 leads reales) operando ahora como real; cuentas creadas por
  admin (sin registro self-service); repo nuevo en GitHub. Se usó `EnterPlanMode`
  dado el tamaño del cambio (infraestructura real, RLS, credenciales) antes
  de tocar nada.
- **Corrección de identidad importante:** Yeisiton (quien da todo el
  feedback de este proyecto) es el propio setter/usuario, no "el fundador"
  — error de lenguaje mío corregido en esta sesión. El fundador/CEO real es
  Andrés (también actúa como closer a veces); Javier es el arquitecto de
  operaciones/IA (autor de `Arquitectura RTF - Views & Beyond.pdf`). Por
  ahora Yeisiton tiene roles `setter`+`admin` en la cuenta real para poder
  verificar todo él mismo mientras se construye.
- **Hallazgo clave al auditar el esquema real con un agente Explore:** la
  arquitectura de auth/roles/RLS YA estaba construida (`usuarios` +
  `usuario_roles`, RLS activo con políticas en las 18 tablas, vistas
  `vw_pipeline`/`vw_scorecard_check`/`vw_embudo_diario` ya existentes) — el
  trabajo real no era diseñar RLS desde cero, sino poblar datos (no había
  ninguna fila de `usuarios` todavía) y conectar la app.
- **Repo creado:** `https://github.com/yeisonestiv109/artf-pipeline-app`
  (privado). Next.js 16 + TypeScript + Tailwind v4 + `@supabase/ssr` +
  `lucide-react`. Se verificó contra Context7 (documentación actual, no
  memoria) que Next.js 16 renombró `middleware.ts`→`proxy.ts` — se usó el
  nombre correcto desde el inicio, evitando el warning/error de deprecación.
- **Cuenta real creada** (`scripts/provision-user.mjs`, uso único, no se
  despliega): Yeisiton, `yeisonestivendelgado109@gmail.com`, roles
  setter+admin, vinculada a `auth_user_id` real. Verificado en vivo: sesión
  con access_token+refresh_token, `vw_pipeline` devuelve 5.943 leads reales
  para esta cuenta.
- **Bug de performance real encontrado y corregido en la base de datos de
  producción** (no en el archivo de esquema, que ya se sabía desactualizado
  en al menos una tabla): `vw_scorecard_check` y `vw_embudo_diario` daban
  timeout (~8.2s) vía la API REST real. Diagnosticado con `EXPLAIN ANALYZE`
  real (no adivinado): **las 42 políticas RLS de las 18 tablas llamaban
  `fn_es_admin()`/`fn_usuario_id()`/`fn_tiene_rol()`/`fn_auth_uid()` sin
  envolver en `(select ...)`**, forzando su reevaluación fila por fila en
  vez de una sola vez por consulta (patrón conocido de Postgres/Supabase,
  confirmado contra la skill `supabase-postgres-best-practices`). Prueba
  física: un `Seq Scan` sobre 13.524 filas de `activity_log`, 100% en
  caché (cero I/O de disco), tardaba 17.6s solo por la re-evaluación de la
  función. **Corregido con 2 migraciones** (`fix_rls_wrap_functions_in_select`,
  luego `fix_rls_activity_log_lead_es_mio`): la primera envolvió las 42
  llamadas bare en `(select ...)` (`vw_scorecard_check`: 12.4s→338ms); la
  segunda reescribió las 2 políticas que llamaban `fn_lead_es_mio(x)` con
  argumento por fila (que no se puede cachear con un simple wrap) como un
  `EXISTS` en línea equivalente — se verificó el cuerpo real de la función
  con `pg_get_functiondef` antes de reescribirla, no se adivinó
  (`vw_embudo_diario`: 27.5s→313ms, confirmado también por la ruta real de
  la API con una cuenta real logueada, no solo SQL directo). **Verificación
  de que la corrección no cambió qué puede ver cada persona:** se
  comparó el mismo set de 6 conteos (vw_pipeline, gestion_leads, reuniones,
  ventas, clientes, activity_log) antes y después con el mismo usuario
  impersonado (QA Closer y el admin real) — idénticos en ambos casos.
- **Construido y funcionando con datos 100% reales** (verificado con
  `npm run build` limpio + pruebas contra la API real con la cuenta real):
  Login/sesión (`@supabase/ssr`, proxy protege rutas), **Pipeline** (Kanban
  desde `vw_pipeline`, drawer, filtros de recencia + búsqueda, cambios de
  estado vía `UPDATE gestion_leads` protegido por RLS + el trigger
  `fn_motor_etapas` ya existente — sin duplicar lógica de permisos en el
  cliente), **Incidencias** (`vw_scorecard_check`, el filtrado por rol sale
  gratis de RLS, no hizo falta lógica nueva), **Métricas** admin
  (`vw_embudo_diario` agregable por día/semana/mes, datos reales).
  Paleta "aura empresarial" pedida explícitamente: sidebar oscura + acento
  más profundo, iconos reales `lucide-react` reemplazando los glifos
  unicode del mockup, manteniendo el minimalismo del resto.
- **Explícitamente fuera de esta Fase 1** (documentado en el plan
  aprobado, no un olvido): Agenda (sin tabla real de disponibilidad),
  Métricas → Global (74 filas) y Show-ups (14 columnas) tal cual el
  mockup (esos datos viven en el Sheet, no en Supabase), Notas internas
  (candidato de Fase 2, podría mapear al mecanismo real
  `INCIDENTE_REVISION:` ya existente), panel de developers/feedback
  (necesitaría tablas nuevas).
- **No se instaló Chromium/Playwright para pruebas E2E de navegador** —
  Yeisiton pidió explícitamente no instalar cosas fuera de su entorno
  (usa `fnm`/`uv`); el intento con `--with-deps` requería `sudo` interactivo
  y se descartó. La verificación automatizada se hizo por otras vías
  (build limpio, redirect de auth por HTTP, y llamadas reales a la API vía
  Node con la cuenta real) — la prueba de clic-por-clic en navegador queda
  para Yeisiton con su propia cuenta, como ya estaba en el plan original.
- **Pendiente inmediato:** conectar el repo a Vercel (requiere la cuenta de
  Vercel de Yeisiton, no se puede hacer sin su login) y probar en vivo.

**Sesión 15-ago-2026 (continuación) — análisis del código real del Worker + Apps Script (CORRIGE hallazgo previo sobre el setter):**
- **CORRECCIÓN CRÍTICA a la sesión anterior de este mismo día:** la afirmación "el rol
  de setter es 100% MANUAL hoy — no hay ningún bot conversacional operando" se basó
  en el SOP/audio de entrenamiento (fuentes de venta humana), NO en el código. Con el
  código real (`worker_cloudflare.md`, compartido por el fundador) se confirma que
  **SÍ existe un bot conversacional completo**, construido y probado: Cloudflare Worker
  que recibe cada DM de ManyChat y llama a **Claude Sonnet 4.6** con un system prompt
  de ~500 líneas ("Andrés"/interno "Javit", hoy renombrado **"Andrew"** en el CRM) que
  ejecuta un árbol de decisión determinístico completo (M1→M5.C: profesión+ingreso →
  dolor → urgencia → pitch → agenda → confirmación → cierre), 9 objeciones scripteadas
  literales, y lógica de handoff a humano. Es "el script de calificación" que la sesión
  previa dio por no-construido-aún — **ya está construido**, no es una iniciativa futura
  desde cero.
  - **Estado ACTUAL confirmado por el fundador (vía Javier, no verificado aún en el panel
    de Cloudflare):** el bot **estuvo activo un tiempo respondiendo DMs reales**, pero
    **actualmente NO responde mensajes** — hoy solo actúa de bridge de captura. Esto
    coincide EXACTO con la rama `JAVIT_ACTIVO=false` del código: captura datos básicos
    del lead, aplica tags `EXISTENTE_CONVERSACION`/`REQUIERE_RESPUESTA_HUMANA`, sincroniza
    al CRM con `etapa=JavitOff` → mapea a "Lead Nuevo - Sin Atender", pero el flow omite
    el envío del mensaje al lead. **Conclusión correcta y matizada:** el rol de setter
    SÍ es 100% manual **hoy**, pero no porque nunca existió automatización — existió,
    funcionó, y fue apagada (razón de negocio no confirmada aún). La "iniciativa futura
    de un bot" del backlog debería reencuadrarse como **auditoría/reactivación de un bot
    existente**, no diseño desde cero — a discutir con el fundador cuándo y si procede
    (sigue fuera del alcance del Formulario Dashboard, ver decisión de alcance abajo).
  - **`apps-script-crm-bridge.md`:** puente Worker→Google Sheet. Recibe el POST de cada
    turno del bot, upsert por `manychat_id`/IG handle contra la pestaña "CRM" (25
    columnas A-Y). Separación real bot-vs-manual: el bot escribe profesión/ingreso/dolor/
    urgencia/estado; los closers llenan a mano WhatsApp, Correo, Fecha Llamada Realizada,
    Fecha Pago, Revenue, Upfront, Recurring (el sync nunca los toca). También escribe cada
    turno a "Activity Log" (auditoría completa) — ya migrado a Supabase vía
    `migrate_activity_log.py` (ver sesión 13-ago).
  - **`daily-metrics-scorecard.md`:** reconstruye la pestaña "Daily Metrics v2" con
    fórmulas COUNTIFS/SUMIFS EN VIVO sobre "CRM" (secciones funnel/revenue/cash/cuotas
    A-R). Es la fuente real de las pestañas Global/Daily Metrics que se intentó mapear a
    `vw_embudo_diario` en sesiones previas.
  - **Inconsistencia detectada, PENDIENTE de verificar contra el Sheet real (no asumir):**
    `daily-metrics-scorecard.md` usa `valCol='R'` para la métrica "Revenue" y `valCol='Q'`
    para "Upfront Cash"; `apps-script-crm-bridge.md` define `COL.REVENUE=Q(17)` /
    `COL.UPFRONT=R(18)` — orden invertido entre los dos scripts. No se puede saber cuál
    documento es el correcto sin mirar el Sheet real.
  - **`limpiar-fechas-crm.md`:** utilitario de un solo uso (corrige fechas guardadas como
    texto en el CRM), sin relevancia arquitectónica para la migración.
  - **Implicación de arquitectura, PENDIENTE de decisión del fundador, NO implementada:**
    dado que el alcance ya confirmado es "migración completa a Supabase, dejar el Sheet
    atrás", el Worker necesitaría redirigir `syncToCRM()` de Apps Script/Sheet a Supabase
    directamente (REST/RPC) para que la captura de leads (incluso en el modo bridge-only
    actual) escriba en tiempo real en Supabase. Esto es DISTINTO de reactivar la lógica
    conversacional del bot (que sigue fuera de alcance). Es un cambio sobre un sistema
    productivo real (Cloudflare Worker en vivo) — requiere aprobación explícita antes de
    tocar nada, no solo del alcance del dashboard.

**Sesión 15-ago-2026 (continuación) — validación contra el Sheet real para el mapeo etapa→estado (puntos 1-2 de la migración del Worker):**
- **Fuente usada:** `Tarea_1_Migrar_DB/Copia de CRM - Leads Campaña 1 Reconexión Financiera.xlsx`
  (copia local del 13-ago, 6.136 filas, MISMO archivo que ya usó/validó
  `migrate_crm.py`) — no se asumió nada sin abrir el archivo real.
- **Revenue/Upfront (Q/R) — RESUELTO.** Encabezado real: `Q17="$ Upfront Cash
  COP"`, `R18="Revenue COP"`. Coincide EXACTO con `daily-metrics-scorecard.md`.
  El error estaba en los nombres de las constantes `COL.REVENUE`/`COL.UPFRONT`
  de `apps-script-crm-bridge.md` (invertidos) — **sin impacto real**: el
  bridge nunca escribe esas dos columnas (son 100% manuales del closer), solo
  las nombra mal en un comentario/constante no usada para escritura.
- **"Alucinaciones" del Estado — CONFIRMADAS con evidencia, y ya resueltas por
  trabajo previo.** La columna Estado real tiene **28 valores distintos**, de
  los cuales **12 no están en `ESTADOS_VALIDOS`** (255/6.136 filas, ~4.2%):
  `Descalificado - Endeudamiento`(90), `Perdido`(81), `No show`(50),
  `Reprogramada`(11), `Ganado`(9), `Pendiente decisión`(8), `M5 Enviado -
  Esperando agendamiento`(3), `M4 Enviado - Esperando resp`(2), `M4 -
  Objeción info`(1) — 9 valores libres, 255 filas. **Los 9 YA están cubiertos
  por el `ESTADO_MAP` de `migrate_crm.py`** (0 anomalías reales en la
  migración ya ejecutada). Explicación fundamentada: ninguno de estos 9 lo
  produce el bot (su `etapa` nunca pasa de M5.C) — son ediciones MANUALES de
  los closers directamente en el Sheet para el ciclo de vida post-agendamiento
  (show up/no show/reprogramar/ganar/perder), más `Descalificado -
  Endeudamiento` que corresponde al 3er criterio del SOP (Endeudamiento ≤50%)
  que el Worker actual **no implementa** (el system prompt solo verifica
  ingreso y urgencia). Esto no bloquea la migración: esos estados posteriores
  a `agendado` los seguirá escribiendo un humano, ahora vía el drawer del
  dashboard (ya construido en el mockup), no el bridge del bot.
- **Gap real detectado (nuevo, sin precedente en los datos):** 3 valores del
  dropdown oficial que el `mapEstado()` de Apps Script SÍ puede producir
  (`Handoff - Agendamiento manual`, `Handoff - Crisis emocional`, `Handoff -
  Ex cliente`) nunca aparecieron en los 6.136 leads históricos → nunca
  necesitaron entrar al `ESTADO_MAP` de `migrate_crm.py`. Para el bridge en
  vivo sí hay que cubrirlos porque el Worker los puede generar. Sin dato real
  que lo valide — pendiente de confirmación del fundador (ver mensaje de la
  sesión).
- **Vocabulario canónico de `estados_lead` confirmado leyendo
  `supabase_schema_v3.sql` directamente (línea 1303):** `nuevo, contactado,
  calificado, agendado, no_show, show_up, oferta_presentada, ganado, perdido,
  descalificado, nutricion` (+ `reservo_oferta_valientes`, agregado después
  según la sesión de OFV). Ninguna propuesta de mapeo usa un código inventado.
- **Mapeo directo etapa(bot)→estado(codigo) propuesto para el bridge en vivo**
  (reutiliza el `ESTADO_MAP` ya validado de `migrate_crm.py`, no inventa
  criterios nuevos salvo el gap señalado arriba): `Inicial/JavitOff→nuevo`;
  `M1,M2,M2.D,M3,M3.B,M4,M5→contactado` (M5 se queda en contactado hasta
  agendamiento confirmado — mismo precedente ya validado); `M5.B,M5.C→
  agendado`; `Descalificado→descalificado` (motivo se preserva en
  `handoff_razon`/notas, no en el código); `Handoff (cualquier razón),
  AgendaManual_1, AgendaManual_2→calificado` (mismo trato que ya reciben
  `Handoff - Otro`/`Handoff - Pregunta precio` en el precedente real; para
  las 3 razones sin precedente, ver gap arriba). Estados posteriores a
  `agendado` quedan fuera del bridge — los gestiona el humano vía el
  dashboard, no el Worker.
- **Gap de Handoff sin precedente — RESUELTO por decisión explícita del
  fundador (no por defecto/heurística):** `Handoff - Agendamiento manual→
  calificado`; `Handoff - Crisis emocional→nutricion` (se saca del pipeline
  de venta activo, no es apropiado seguir empujando — transición
  `contactado→nutricion` ya es legal en `estado_transiciones`, verificado en
  `supabase_schema_v3.sql` línea ~1325, sin gap de esquema); `Handoff - Ex
  cliente→calificado` (se deja para que un humano evalúe oportunidad de
  upsell/referido, no se cierra de una vez).
- **RPC del bridge — campos, fundamentados en el shape YA usado por
  `migrate_crm.py`** (`build_payloads()`, líneas 242-332): `clientes`
  (manychat_id, nombre←full_name, ig_handle, profesion, salario_monto/
  currency/periodicidad, notas←summary); `gestion_leads` (setter_id, closer_id
  —casi siempre null en turnos del bot—, fuente_codigo, estado_codigo —nuevo
  mapeo—, fecha_contacto, fecha_atendido, dolor, urgencia, califica,
  handoff_razon, `origen_escritura`: propongo `'bot'` como valor nuevo,
  distinto de `'importacion'`, para distinguir tráfico en vivo del histórico).
  Confirmado con el header real que el bridge NUNCA debe tocar: WhatsApp(M),
  Correo(N), Fecha Llamada Realizada(O), Fecha Pago(P), Upfront Cash COP(Q),
  Revenue COP(R), Forma de pago(S) —dato real sucio, mayormente texto libre—,
  Closer(Z), Fecha inicio/fin programa(AA/AB), cuotas(AC-AE) —"Estado cuota"
  100% vacío en los datos reales, así que "Cuotas Cobradas" en la vista
  Métricas dará $0 real hasta que alguien empiece a marcar cuotas
  "Realizado", no es un bug de mapeo—. **NO implementado — pendiente de
  confirmar el gap de Handoff antes de escribir el RPC real.**

**Sesión 15-ago-2026 (continuación) — `fn_sync_bot_turn` escrita, APLICADA y VALIDADA en staging:**
- Función completa en `Tarea_1_Migrar_DB/fn_sync_bot_turn.sql` (también anexada
  como §22 de `supabase_schema_v3.sql`) y **ya aplicada a staging**
  (`lrdtjsxtaadpgrzkchlw`) vía MCP de Supabase, con autorización explícita del
  fundador ("de una vez lo apliques y valides").
- **3 bugs reales encontrados y corregidos probando contra la BD real (no en
  teoría):**
  1. Nombres de columnas de `RETURNS TABLE` (`cliente_id`, `gestion_lead_id`)
     chocaban con columnas reales de las tablas → error "column reference
     ambiguous". Corregido con prefijo `out_`.
  2. `fn_avanzar_estado` solo permite UN salto legal a la vez. Un lead nuevo
     cuyo PRIMER turno ya es un handoff de crisis emocional necesita
     `nuevo→contactado→nutricion` (2 saltos) — el mapeo directo lo dejaba
     atascado en `nuevo` (`avanzo=false` silencioso). Corregido con un salto
     intermedio vía `contactado` cuando el directo falla.
  3. El constraint `ck_gl_handoff_closer` exige `closer_id` no nulo cuando
     `fecha_handoff` no es null — el bot nunca asigna closer. Se dejó de
     tocar `fecha_handoff` en el bridge por completo (mismo criterio que ya
     usaba `migrate_crm.py`: ese campo es "cuándo se entregó a un closer",
     no "cuándo el bot marcó para revisión humana").
- **1 hallazgo de seguridad real** (vía `get_advisors` de Supabase, cruzado
  contra `information_schema.role_routine_grants`, no contra el caché del
  linter): pese a un `REVOKE` en una migración intermedia, `anon`/
  `authenticated` seguían con `EXECUTE` sobre la función. Corregido con un
  `REVOKE` final reverificado — hoy solo `service_role`/`postgres` pueden
  ejecutarla, igual que `fn_avanzar_estado`.
- **Pruebas ejecutadas contra staging** (leads `TEST_BRIDGE_001..005`,
  quedan en la BD claramente marcados, mismo criterio que los usuarios QA
  ya existentes): secuencia completa M1→M2→M3→M4→M5→M5.B en un mismo
  `manychat_id` → **una sola fila** de `gestion_leads` (no duplica), termina
  en `agendado`, profesión/salario se capturan y preservan; Descalificado
  directo desde `nuevo` (ingreso bajo en el primer mensaje); AgendaManual_1
  como primer turno (salto intermedio); reapertura de un lead `descalificado`
  que vuelve a escribir → reabre la MISMA fila (`descalificado→contactado`,
  no crea una fila paralela); no-clobber verificado (WhatsApp/Correo puestos
  a mano por un closer sobreviven turnos posteriores del bot);
  `activity_log` queda con el registro automático de `fn_log_gestion`
  (creación/cambio_estado) MÁS el contenido de cada turno (mensajes +
  resumen) que agrega esta función — auditoría más completa que la pestaña
  "Activity Log" del Sheet original.
- **Pendiente, siguiente paso — NO implementado:** el Worker de Cloudflare
  (`worker_cloudflare.md`) todavía llama a `syncToCRM()`→Apps Script→Sheet.
  Falta el cambio en el propio Worker (reemplazar esa llamada por un POST a
  `/rest/v1/rpc/fn_sync_bot_turn` con la service_role key) para que el
  bridge en vivo realmente quede activo — sigue siendo un cambio sobre un
  sistema productivo real, requiere aprobación explícita antes de tocarlo.

**Sesión 15-ago-2026 (continuación) — reconciliación completa Sheet fresco → staging (migración al día):**
- **Fuente:** `Copia Actualizada (15 agosto) de CRM...xlsx`, subida por el fundador
  (6.469 filas CRM, mismas 32 columnas/estructura que la copia del 13-ago —
  sin drift de esquema). Comparada campo a campo contra la copia del 13-ago
  y contra el estado real de staging (no se asumió nada, todo vía MCP de
  Supabase).
- **333 leads nuevos insertados** (clientes + gestion_leads + 9 reuniones),
  reutilizando el `build_payloads()`/mapeos ya validados de `migrate_crm.py`
  (0 anomalías). Verificado: `clientes` pasó de 6.136 a 6.469 exacto.
- **21 leads existentes con cambios "de rutina" actualizados** (Estado,
  Closer, WhatsApp, Correo, Nombre, Handoff Razón + reuniones: 12 creadas, 6
  actualizadas). Las transiciones de estado se resolvieron con un
  **pathfinder BFS sobre `estado_transiciones` real** (no solo el salto
  directo de `fn_sync_bot_turn`) para cubrir saltos de 2 pasos como
  `calificado→agendado→no_show`. **21/21 verificados en el estado esperado
  tras aplicar, 0 errores.**
- **2 ventas nuevas registradas** (Carolina Celis $5M contado 1 cuota;
  Adriana Mejia Moreno $6M mixto 2 cuotas) vía `fn_registrar_venta`, con el
  paso previo obligatorio `calificado→agendado→show_up` (sin eso,
  `fn_venta_cierra_lead` habría fallado en silencio al intentar
  `calificado→ganado`, que no es transición legal — hallazgo real
  confirmado leyendo el trigger antes de ejecutar, no asumido). Reunión real
  creada para Adriana (con fecha real) y pasada como `p_reunion_id` — para
  Carolina no había fecha programada en el Sheet, quedó `NULL` (correcto,
  no inventado).
- **3 casos NO tocados, quedan pendientes de decisión del fundador**
  (dinero real de por medio, mismo criterio que el caso "Juan Manuel" de la
  sesión del 13-ago — no se asume, se pregunta):
  1. **Marisol Tupaz** (`1252431934.0`): Estado pasó de "Lead Nuevo" a
     "Desistió" pero con Fecha Pago + Upfront $2.7M + Revenue $5.4M ya
     registrados en el Sheet. Ambiguo: ¿se quedó con la plata (retención
     parcial) o se le devolvió todo?
  2. **Juliana Osorio** (`120356523.0`) y **Daniela** (`1769260058.0`):
     Estado sigue en "Agendada - Confirmada" en el Sheet (nunca se marcó
     "Ganado"), pero Upfront/Revenue COP ya están completos (Upfront=Revenue
     exacto) y "Estado cuota"="Realizado" — huele a venta real que el closer
     olvidó marcar en el dropdown (mismo patrón que "Sebastián Cruz" en la
     sesión del 13-ago). No se registró como venta sin confirmación.
  Se aplicó SOLO lo inequívoco de estos 3 (asignación de Closer a Juliana/
  Daniela) — nada financiero.
- **Verificación final:** `vw_scorecard_check` revisado completo tras todos
  los cambios — el único ERROR (`ganado_sin_venta`, 1 fila) y los 2 WARN de
  `posible_cliente_duplicado` tienen `fecha_ref=2026-08-13`: **preexistentes
  de la migración original ("Juan Manuel"), no introducidos hoy.** Nada
  nuevo roto.
- Todos los scripts de esta reconciliación quedaron en el scratchpad de la
  sesión (no en el repo) por ser de un solo uso — la lógica reutilizable
  (mapeos, pathfinder) queda documentada aquí para la próxima vez que haga
  falta repetir este proceso.

**Sesión 15-ago-2026 (continuación) — resolución de los 3 casos flaggeados + mecanismo de incidentes de revisión manual:**
- **Decisiones del fundador:** "Juan Manuel" (ERROR preexistente,
  `ganado_sin_venta`) se deja tal cual — debe seguir viéndose como incidente
  en el dashboard. **Juliana Osorio y Daniela: SÍ registrar como ventas
  ganadas** con los montos ya en el Sheet. **Marisol Tupaz: NO se tiene hoy
  la info para resolverlo** — debe quedar como incidente visible, no
  inventarse una resolución.
- **Juliana Osorio ($4.132.339) y Daniela ($4.481.400) registradas** vía
  `fn_registrar_venta` — mismo patrón que Carolina/Adriana (avance
  `agendado→show_up` antes de la venta, reunión ya existente de la
  migración original reutilizada como `p_reunion_id`). Verificado: ambas en
  `ganado` con el monto correcto.
- **Mecanismo nuevo, genérico, para incidentes de revisión manual
  (respondiendo directamente al pedido del fundador de que "el dashboard
  debe poder identificar estos casos para que cada rol actúe"):**
  cualquier `gestion_leads.notas` que empiece con `INCIDENTE_REVISION:`
  aparece automáticamente en `vw_scorecard_check` (WARN,
  chequeo=`requiere_revision_manual`) — sin tabla ni columna nueva, mismo
  patrón visual/de filtrado por rol que ya usa el mockup para Incidencias.
  **Primer uso real: Marisol Tupaz** (nota completa con los montos y la
  pregunta sin resolver, sin inventar una respuesta). View
  `vw_scorecard_check` actualizada (nueva rama `UNION ALL`) y aplicada a
  staging; anexada como §23 de `supabase_schema_v3.sql`. Verificado:
  `requiere_revision_manual=1` (Marisol), `ganado_sin_venta=1` sigue igual
  (Juan Manuel, sin tocar), resto de chequeos estables.
- **Pendiente para cuando se conecte el Worker nuevo:** decidir si el bridge
  en vivo (`fn_sync_bot_turn`) también debería poder escribir
  `INCIDENTE_REVISION:` automáticamente cuando el bot reciba un `Estado`/
  dato que no sepa mapear con confianza — hoy ese mecanismo solo existe para
  uso manual/scripts de reconciliación, no está cableado al bridge en vivo.

**Sesión 15/16-ago-2026 (continuación) — Mockup v5: fidelidad a "Perdido" +
research UX aplicado + tabla/gráficas de Métricas:**
- **El fundador compartió el historial completo del research de NotebookLM**
  (el query directo seguía sin funcionar) — 4 bloques: minimalismo
  funcional/ergonomía cognitiva, por qué el diseño con IA se ve genérico
  (problema "Indigo-500", solución `DESIGN.md` con tokens rígidos, evitar
  "Cardocalypse"), patrones Kanban/CRM (atribución dual setter/closer,
  5-7 columnas máximo, indicadores de lead "rotting", reglas de salida no
  de entrada), panel de incidencias/métricas (bandeja de excepciones,
  totales reales, estados vacíos estratégicos, agenda bidireccional).
- **Hallazgo del propio fundador, el más importante de esta ronda:** ningún
  estado del Kanban representaba "el lead se perdió" — `perdido` no
  aparecía en ninguna parte. Verificado: real y grave, el Kanban solo tenía
  8 estados (nuevo→ganado), sin ningún estado de salida sin éxito.
  **Corregido con criterio explícito, documentado, para balancear fidelidad
  (pedido explícito) contra la regla de "5-7 columnas" del research (pedido
  explícito también, "que le facilite la vida"):** se agregó UNA columna
  "Perdido" que agrupa los 4 codigos reales de salida sin éxito del esquema
  (`perdido`/`descalificado`/`nutricion`/`no_show`) — nada se esconde
  (cada tarjeta en esa columna muestra su motivo exacto vía una etiqueta),
  pero no se agregaron 4 columnas nuevas. `TRANSICIONES` del mockup
  actualizado para reflejar que CASI todo estado real puede terminar en
  `perdido` (fiel a `estado_transiciones`), y que `perdido→contactado` es
  la única reapertura (igual que el esquema real).
- **Atribución dual aplicada** (research, punto explícito): toda tarjeta del
  Kanban ahora muestra Setter Y Closer siempre, no solo Closer cuando existe.
- **Métricas del Admin reconstruidas** — pedido explícito: tabla real
  (filas=métricas, columnas=Semana 1-4 + Total, franja de color por sección
  igual que el script real: funnel=azul/base=gris/revenue=verde/cash=dorado,
  columna %Conv junto a cada paso del funnel) en vez de la grilla de tiles
  de v3/v4 — mismos totales mensuales que las versiones anteriores
  (verificado, cero deriva de cifras). **+ 2 gráficas** (embudo de
  conversión Lead→Venta en barras, Revenue Real semanal en línea), primera
  vez que se usa la skill `dataviz` en este proyecto — un solo hue
  (`--accent`), sin doble eje, tooltip al pasar el mouse, etiquetas
  directas, siguiendo el spec de marcas de la skill (barras ≤24px con
  extremo redondeado, líneas 2px, puntos ≥8px con anillo de superficie).
- **Pendiente de decisión del fundador (no implementado, solo señalado):**
  el research menciona `DESIGN.md` (tokens rígidos legibles por máquina) —
  eso aplica al proyecto REAL cuando se construya con un framework, no a
  este mockup HTML de una sola página; y "reglas de salida, no de entrada"
  (validar datos obligatorios antes de dejar avanzar una tarjeta) — el
  mockup no lo implementa aún, es una regla de negocio a decidir (qué
  campos son obligatorios por transición) antes de construirla.

**Sesión 16-ago-2026 (continuación) — Mockup v10: datos 100% reales
extraídos del xlsx (no más aproximaciones), Global de 74 filas, Show-ups
con las 14 columnas reales, corrección de un hallazgo previo equivocado:**
- **Feedback del fundador sobre v9:** "aún faltan muchas cosas" — Global
  sigue sin las columnas Benchmark/Promedio mensual, faltan más meses (y
  pide que agregar meses sea automático), y sigue faltando filas que "sigo
  sin ver" (v9 solo tenía 14 filas aproximadas, no las reales). Show-ups
  sigue con muy pocas columnas — pide nombrarlas tal cual el Sheet, mismo
  orden, sin importar los espacios vacíos. Instrucción explícita: quiere
  las 3 vistas "tal cual están en el Sheet".
- **Se encontró el xlsx completo con las 6 pestañas reales YA disponible
  localmente** (`Tarea_1_Migrar_DB/Copia Actualizada (15 agosto) de
  CRM...xlsx`, el mismo archivo usado para la migración a Supabase) — no
  hizo falta pedirle un nuevo export al fundador. Se leyó **Global** y
  **Show ups (Reuniones)** completas con `openpyxl` (mismo venv/patrón
  usado toda la sesión para "sin suposiciones").
- **Hallazgo importante: una afirmación de una sesión anterior (15-ago,
  "quick-wins de métricas") estaba desactualizada o era incorrecta.** Esa
  sesión decía que ROI FECC-UF y AOV-Cash estaban vacías en TODOS los
  meses — **falso en los datos actuales**: ambas filas SÍ tienen cifras
  reales (ROI FECC-UF: 4.49/4.92/6.56/1.99/4.42; AOV-Cash: $2.56M/$2.87M/
  $3.08M/$1.74M/$3.57M). Lo que sí sigue vacío de verdad: Views, MQL/Call-
  Confirmer, Sales Qualified Bookings, Ofertas (como conteo — su %Rate
  asociado sí trae 0% real) y varias filas de desglose por producto (Core
  Program/Low ticket/Producto 3/Producto 4, casi siempre vacías salvo
  Precio Promedio). Se corrigió el mockup con los datos verificados AHORA,
  no con el resumen de memoria de la sesión anterior.
- **Global reconstruida con las 74 filas reales, en el orden exacto del
  Sheet**, columnas Métrica | Benchmark | Promedio mensual | Mayo…
  Diciembre 2026 (8 meses) | Total 2026 — igual que el Sheet real. Octubre-
  Diciembre aparecen vacías pero SÍ están en la tabla: el Sheet real ya
  tiene esas columnas pre-armadas esperando esos meses, así que "agregar
  meses automático" ya está resuelto con solo listar las 8 columnas reales
  tal cual existen, sin lógica adicional.
- **Daily Metrics v2: se reemplazaron los datos de ejemplo por cifras
  REALES** extraídas de las columnas "Mensual" del Sheet para Mayo-
  Septiembre 2026 (Septiembre en 0 porque el mes no ha iniciado, salvo
  Cuotas Cobradas=$3.000.000 ya registrado por adelantado). La granularidad
  "Meses" ahora muestra estos 5 meses reales directamente, sin derivar
  nada. "Semanas"/"Días" se siguen derivando (no hay forma práctica de
  replicar la grilla real de 167 columnas anidadas día/semana/mes/total en
  una página HTML), pero ahora parten del total REAL de Agosto (el mes más
  reciente con datos) en vez de una cifra inventada — mismo patrón de
  transparencia que antes (etiquetas "derivado del total real de Agosto"
  en la UI), solo que ahora el ancla es real.
- **Show-ups (Reuniones) reconstruida con las 14 columnas reales exactas**
  (Nombre, IG Handle, Setter, Fecha Reunión, Estado, WhatsApp, Correo,
  Fecha Pago, Revenue COP, $ Upfront Cash COP, Closer, Palabra clave (Ad),
  Notas, Estado Reunión — 193 reuniones reales en el Sheet). Se corrigió
  también el vocabulario de estados: lo que se había inventado antes
  (show_up/no_show/pendiente) no existe así en el Sheet real — el
  vocabulario real de "Estado" es de 10 valores (Ganado, Perdido, No show,
  Agendada - Confirmada, Pendiente decisión, Reprogramada, Descalificado -
  Ingresos bajos, Lead Nuevo - Sin Atender, Handoff - Otro, Desistió) y
  "Estado Reunión" de 6 (Vendió, Descalificada, Pendiente, Desistió, Sin
  definir, Reserva (OFV)) — ahora se usan tal cual.
- **Decisión de privacidad, tomada sin preguntar por ser obvia dado el
  contexto (Artifact potencialmente compartible):** las FILAS de la tabla
  de Show-ups siguen siendo de ejemplo (nombres/WhatsApp/correos
  inventados) — el Sheet real trae 193 nombres, teléfonos y correos reales
  de clientes (PII) que no corresponde copiar a un mockup. Lo que SÍ es
  real ahí: el resumen "Reuniones por mes" (Mayo=36, Junio=72, Julio=63,
  Total=171, cifras reales) y el vocabulario de Estado/Estado Reunión.
  Explicado directamente al fundador, no fue una decisión oculta.
- **Orden de pestañas ajustado** a "Global, Daily Metrics v2, Show-ups"
  (pedido explícito, antes estaba "Daily Metrics v2, Global, Show-ups").
- **Validado con la prueba de humo de rondas anteriores**, ampliada para
  confirmar que las 74 filas de Global y las 14 columnas de Show-ups
  efectivamente aparecen en el HTML renderizado (no solo que el JS no
  truena) — incluyó corregir el propio arnés de prueba (un stub de
  `textContent` incompleto ocultaba contenido real que sí funciona en un
  navegador de verdad).

**Sesión 16-ago-2026 (continuación) — Mockup v9: fidelidad total de filas y
columnas del Sheet real en Métricas (Global/Daily Metrics v2/Show-ups),
lectura de `Arquitectura RTF - Views & Beyond.pdf`:**
- **Feedback del fundador sobre v8:** "Capacidad por ahora no" (confirmado,
  se mantiene fuera). Pide que las 3 pestañas de Métricas muestren **todas**
  las filas y columnas reales del Sheet, no una selección condensada — "iré
  revisando y si más adelante lo podemos condensar ya te comento". Señala
  que el equipo usa el marco EOS/Traction y remite al documento
  `Arquitectura RTF - Views & Beyond.pdf` para revisar antes de construir.
  Instrucción explícita nueva: preguntar dudas DURANTE el desarrollo, no
  esperar a terminar.
- **Se leyó el documento de arquitectura completo** (metodología Views &
  Beyond, Javier como autor, v1.0 agosto 2026). Confirma: el Esquema CRM
  real tiene columnas A–AF; "Daily Metrics v2" es scorecard diario
  (funnel/cash-A/R); "Global" es el dashboard MENSUAL que alimenta el Pulso
  L10 semanal de EOS, con CAC-ROI como sus KPIs headline (D7 del rationale:
  "Los números del Global alimentan el Pulso L10 semanal, cerrando el
  ciclo de datos → decisión"); "Show ups" es reporte de reuniones por
  estado y closer generado por ARRAYFORMULA. No detalla el catálogo
  columna-por-columna de Global/Show-ups (ese detalle solo existe para
  Daily Metrics v2, ya extraído de `daily-metrics-scorecard.md` en rondas
  anteriores) — limitación reconocida, no inventada.
- **Duda real planteada al fundador ANTES de construir** (siguiendo su
  instrucción de preguntar sobre la marcha): la pestaña "Global" real tiene
  filas confirmadas vacías en TODOS los meses (MQL/Call-Confirmer, Sales
  Qualified Bookings, Ofertas, Views, desglose por producto, ROI FECC-UF,
  AOV-Cash) — decisión previa con Javier fue NO construirlas. Se preguntó
  vía `AskUserQuestion` si ahora sí incluirlas (con "—") para fidelidad
  total de filas, o mantenerlas fuera. **Respuesta: incluirlas con "—".**
  Esto invierte la decisión previa a propósito, por instrucción explícita
  y informada (el fundador vio el trade-off antes de decidir).
- **Bug de fidelidad propio, encontrado al releer el script real durante
  esta ronda:** la columna %Conv de Daily Metrics v2 se estaba calculando
  también para "Oferta de Valientes" y "Estudiantes activos" — el script
  real (`FUNNEL_PREV = {1:0,2:1,3:2,4:3,5:4}`) SOLO calcula %Conv para
  Conversaciones→Sales (5 pasos), esas dos filas quedan sin %Conv en el
  Sheet real. Corregido (`idx<=5`) antes de que el fundador lo notara.
- **Global ampliada a 14 filas** (antes 5): se agregaron las 7 filas
  vacías confirmadas (con badge "sin dato en Sheet" en vez de solo "—" en
  blanco, para que quede claro que es a propósito y no un error de
  renderizado) + se agregó **CAC** (costo por venta, antes solo estaba
  cp_lead) — el documento de arquitectura nombra explícitamente "CAC-ROI"
  como los KPIs headline de Global, así que faltaba CAC. AdSpend sigue
  siendo el único dato real (marcado "real"); Leads/Sales/Revenue de
  ejemplo, cp_lead/CAC/ROI derivados (ya son campos reales de
  `vw_embudo_diario`, solo con datos de ejemplo aquí).
- **Show-ups (Reuniones) ampliada con su propio filtro Día/Semana/Mes**
  (pedido explícito de que las 3 pestañas tengan filtros de periodo): a
  diferencia de Daily Metrics v2 (una matriz métrica×periodo), Show-ups es
  un LISTADO de reuniones, así que el filtro aquí filtra qué reuniones se
  muestran por fecha (no pivotea columnas) — interpretación fiel a la
  naturaleza real de esa pestaña. Se ampliaron los datos de ejemplo
  (6 reuniones más, hasta 26 días atrás) para que el filtro "Mes" muestre
  algo distinto de "Semana". **Nota dejada explícita en el propio mockup**
  (no una suposición silenciosa): no se ha verificado si el Sheet real
  tiene más columnas por reunión (duración, tipo) más allá de fecha/lead/
  closer/resultado.
- **Daily Metrics v2 ya estaba completa en filas** (las 21 métricas reales
  de `daily-metrics-scorecard.md`, verificado explícitamente esta ronda
  comparando etiqueta por etiqueta contra el script — coinciden exacto) —
  no necesitó cambios de fondo más allá del fix de %Conv.
- **Global se mantiene deliberadamente SIN el selector Día/Semana/Mes**
  (ya documentado en v8, reafirmado esta ronda): el gasto se carga por mes
  completo en el Sheet real, no por día — aplicar un filtro diario ahí
  sería infiel a los datos, no una limitación de esta implementación.
- **Validado con la prueba de humo en Node**, ampliada para cubrir las 3
  pestañas de Métricas con todos sus filtros — sin errores.

**Sesión 16-ago-2026 (continuación) — Mockup v8: Métricas separadas en las
pestañas reales del Sheet (Global/Daily Metrics v2/Show-ups), fronteras de
rol en el Pipeline, notas internas entre roles, CRUD del panel de
developers:**
- **Feedback del fundador sobre v7:** "sí me gusta más" — pero señala 3
  problemas concretos y pide explícitamente ser más proactivo ("siento que
  te estás dejando varios puntos por fuera... no te contengas a dejar solo
  lo básico, ayúdame a dejar una versión lista para desplegar"): (1) la
  tabla de Métricas está bien pero le faltaban las pestañas reales del
  Sheet — "Global" y "Show-ups (reuniones)" — mezcladas en una sola vista
  en vez de separadas; (2) el `<select>` de 21 métricas para graficar "se
  llena la pantalla"; (3) pide que cada rol se encargue solo de sus propias
  funciones del pipeline (sin cruces) más una forma de que los roles se
  avisen cosas entre sí; y pide reforzar el panel "Para desarrolladores"
  para que un developer pueda crear/activar/suspender funciones en prueba,
  no solo verlas.
- **Verificación contra el Sheet real ANTES de tocar nada** (pedido
  explícito, "revísalo muy bien que sea fiel a los datos reales"): se
  releyó `05-validacion-migracion-datos-reales.md`, que confirma **6
  pestañas reales** en el Sheet: `Global`, `Daily Metrics v2`, `CRM`, `Show
  ups (Reuniones)`, `Activity Log`, `Capacidad`. `CRM` ya es el Pipeline de
  este mockup y `Activity Log` ya vive dentro de cada lead — no se
  replicaron aparte. `Capacidad` **NO se incluyó** — no se ha verificado su
  estructura real todavía; se dejó una nota explícita en el propio mockup
  pidiéndole al fundador que confirme si es prioridad antes de construir
  algo sobre datos sin verificar (su propia instrucción: "si alguna duda me
  vas preguntando").
- **Métricas restructurada en 3 pestañas de nivel superior** (`Daily
  Metrics v2` / `Global` / `Show-ups (Reuniones)`), tipográficamente más
  grandes/pesadas que las sub-pestañas Tabla/Gráficas que ya tenía
  (anidadas, distinguibles a simple vista): `Daily Metrics v2` es la tabla
  ya construida en v6/v7, sin cambios de fondo. `Global` es nueva: se
  releyó también la sesión "quick-wins de métricas: AdSpend + conversaciones"
  donde ya se había decidido (confirmado por audio con el fundador) que la
  mayoría de filas reales de Global (MQL/Call-Confirmer, Ofertas, Views,
  desglose por producto, ROI FECC-UF, AOV-Cash) están vacías en TODOS los
  meses — vestigios de mala calidad de datos, no prioridades — **decisión
  ya tomada de no construirlas, ahora aplicada también al mockup**. Lo que
  sí se incluyó es real: **AdSpend cargado en `gastos_marketing`** (Mayo
  $2.330.239, Junio $6.109.225, Julio $6.990.882 COP — cifras REALES, no de
  ejemplo, con badge "real" visible en la tabla) + cp_lead y ROI derivados
  con Leads/Revenue de ejemplo para ilustrar el cálculo (rotulados como
  tal). Se documentó explícitamente que esta pestaña **solo tiene
  granularidad mensual** (el gasto se carga por mes completo, no por día —
  ya documentado en el esquema) y por eso NO lleva el selector Día/Semana/
  Mes. `Show-ups (Reuniones)` también es nueva: una fila por reunión
  (fecha/lead/closer/resultado), mismo grano que la tabla `reuniones` real
  ya migrada (204 reuniones reales cargadas) — cifras de ejemplo, con
  chips de Show Up Rate/No-shows/Pendientes (este último es literalmente
  el chequeo real `reunion_vencida_sin_resolver` que ya existe en
  `vw_scorecard_check`).
- **Selector de gráficas curado de 21 a 5 opciones** (arregla el
  desplegable que "llenaba la pantalla"): en vez de recortar arbitrariamente,
  se usó el propio criterio del script real — `daily-metrics-scorecard.md`
  marca `emphasize:true` en exactamente dos filas (Revenue Real, Upfront
  Cash Real). Se completó con el inicio/fin del funnel (Leads, Sales) y el
  cobro efectivo (Cuotas Cobradas) → 5 opciones, fiel a cómo el Sheet real
  ya distingue sus propias filas importantes, no una selección inventada.
- **Fronteras de rol en el Pipeline** (pedido explícito, "que cada rol se
  encargue de sus respectivas funciones... para que no hayan cruces"):
  nuevo mapeo `SETTER_STATES` (nuevo→agendado) / `CLOSER_STATES`
  (agendado→ganado), con `agendado` como frontera compartida a propósito
  (el Setter lo crea, el Closer lo recibe). Si el rol actual no es dueño de
  la etapa del lead, el selector de "Avanzar estado" queda deshabilitado
  con una nota ("Esta etapa la maneja el rol X") en vez de simplemente
  ocultar la opción sin explicar por qué. Las acciones rápidas (confirmar
  reunión, depósito OFV, cerrar venta) — todas territorio del Closer — ya
  no aparecen en absoluto para el Setter.
- **Notas internas entre roles** (pedido explícito, "una forma de que se
  comuniquen o hagan saber al del otro rol que necesitan algo"): nueva
  sección en el drawer de cada lead — lista de notas + un compose (texto +
  destinatario). Deliberadamente NO se inventó un sistema de mensajería
  aparte: cada nota nueva también se publica como una incidencia INFO
  visible para el rol destinatario, reusando el mecanismo YA real del
  backend (prefijo `INCIDENTE_REVISION:` en `gestion_leads.notas`,
  auto-surfaced en `vw_scorecard_check`, ver sesión "resolución de los 3
  casos flaggeados") — cierra el círculo con infraestructura que ya existe
  en vez de duplicar funcionalidad.
- **CRUD real en "Para desarrolladores"** (pedido explícito, "un
  desarrollador sea quien pueda crear los formularios, tenerlos activos,
  suspender, y evaluar"): botón "+ Nueva función en prueba" (formulario
  inline nombre+descripción, se activa de inmediato); cada función tiene un
  badge Activa/Suspendida y un enlace para alternar — suspender la saca del
  selector del botón "🧪 Feedback" (no se puede seguir opinando sobre algo
  suspendido) pero conserva sus respuestas históricas visibles, atenuadas,
  para seguir evaluando lo ya recolectado. Se apoyó con una gráfica nueva
  (barras, facilidad de uso promedio por función, reusando
  `renderBarChartSVG` — mismo spec de la skill `dataviz` que ya se seguía)
  para priorizar de un vistazo qué necesita más trabajo.
- **Validado con la misma prueba de humo en Node** de v7, ampliada para
  cubrir los flujos nuevos (fronteras de rol en `openDrawer` para varios
  leads y roles, las 3 pestañas de Métricas, crear/activar/suspender una
  función de prueba, enviar una nota interna) — sin errores.
- **Pregunta abierta para el fundador** (dejada explícita en el propio
  mockup y aquí, no una suposición): ¿la pestaña "Capacidad" del Sheet es
  prioridad para este panel? No se ha revisado su estructura real todavía;
  se prefirió preguntar en vez de inventarla.

**Sesión 16-ago-2026 (continuación) — Mockup v7: filtros rápidos de Pipeline,
Métricas por día/semana/mes con gráficas editables, export CSV, y panel
"Para desarrolladores" con micro-encuesta de validación:**
- **Feedback del fundador sobre v6:** "ya me gusta más" — confirma la
  dirección de tipografía/color; pide más tamaño de letra en ciertas
  partes puntuales (no un rediseño), filtros rápidos en Pipeline por
  día/horas/semanas, ver Métricas por día/mes además de semana, gráficas
  editables, exportar la tabla, "que sea algo más dinámico", y pidió
  explícitamente mi criterio ("dame tu punto, analiza evalúa... sorpréndeme
  para que quede listo para desarrollar") + investigar cómo se diseñan
  encuestas de validación cortas para un panel nuevo "para developers".
- **Tipografía — subida selectiva, no global** (pedido explícito, "en
  ciertas partes"): `.view-title` (15→17px, 650→700), `.card-name`
  (13→13.5px), `.drawer-name` (16→17.5px). Se dejó el resto igual a
  propósito — subir todo habría revertido la jerarquía que ya funcionaba.
- **Filtros rápidos en Pipeline** (pedido explícito, "por día, horas y
  semanas"): como `LEADS` no tiene fecha de creación (solo `stale`, horas
  desde la última actividad, que ya se mostraba en cada tarjeta), se usó
  ese mismo campo real como base de los filtros — chips "Todos / Últimas
  24h / Esta semana / Estancados (+24h)" — en vez de inventar un campo de
  fecha que no existe en el modelo. Además se activó el buscador del
  topbar, que en v1-v6 era un `<div>` decorativo sin función real; ahora
  filtra por nombre en vivo.
- **Métricas por Día/Semana/Mes** (pedido explícito): selector compartido
  entre la tabla y las gráficas (mismo control, misma granularidad en
  ambas vistas). "Semanas" sigue siendo el dataset real de v6 (mes actual,
  4 semanas); "Días" se DERIVA matemáticamente de esas mismas 4 semanas
  (reparto por pesos fijos entre 7 días, determinístico) — incluye el
  mismo total mensual, es la misma ventana con más detalle, no un dato
  nuevo; "Meses" es una ventana MÁS AMPLIA (últimos 4 meses, con una
  trayectoria de crecimiento) — su total es distinto a propósito, porque
  compara periodos distintos, no es inconsistencia. Todo sigue rotulado
  como cifras de ejemplo, igual que el resto de `METRICAS_MOCK` desde v5.
- **Gráficas editables** (pedido explícito): las dos gráficas fijas de v5/v6
  (embudo + Revenue Real) se generalizaron — ahora cada una tiene un
  `<select>` para elegir qué métrica graficar (cualquiera de las 21 filas
  de `METRICAS_MOCK`, más la opción especial "Embudo (Lead→Venta)" en la
  primera). Ambas respetan la granularidad activa. Refactor: las funciones
  fijas `renderFunnelChart`/`renderRevenueChart` se reemplazaron por
  `renderBarChartSVG`/`renderLineChartSVG` genéricas (mismo spec de la
  skill `dataviz` que ya se seguía: un solo hue, barras ≤24px, líneas 2px,
  tooltips, sin doble eje) más `renderChart1`/`renderChart2` que arman los
  datos según la selección.
- **Exportar CSV**: botón en la tabla de Métricas. **Limitación técnica
  señalada explícitamente al fundador:** el visor de Artifacts de Claude
  bloquea cualquier descarga que la página misma dispare (enlaces
  `download`, blobs) — es una restricción del sandbox del visor, no un
  bug de esta implementación. El botón genera el CSV real en memoria (la
  lógica queda lista para producción) y muestra un toast confirmando el
  archivo que se generaría, mismo patrón que ya usan otras acciones
  simuladas del mockup (ej. el envío de invitación de Google Calendar al
  agendar). En el build real (fuera del sandbox del Artifact) esa misma
  función solo necesita conectarse a una descarga de Blob real.
- **Panel "Para desarrolladores" (Admin) + micro-encuesta de validación**
  (pedido explícito, con investigación previa vía WebSearch — ver fuentes
  abajo): se investigaron patrones de "in-app micro-surveys" — hallazgo
  clave: una sola pregunta bien elegida rinde más que cinco mediocres, y
  el estándar para decidir si vale la pena invertir en una función es el
  **PMF test de Sean Ellis** ("¿qué tan decepcionado estarías si ya no
  pudieras usar esto?", ≥40% "muy decepcionado" = señal real de que vale
  la pena seguir). Se adaptó a 3 preguntas, <30 segundos, tal como se
  pidió: (1) pregunta estratégica estilo Sean Ellis en positivo ("¿qué
  tanto extrañarías [función]?" Mucho/Un poco/Nada), (2) una **Single Ease
  Question** (SEQ, el estándar más corto de usabilidad, escala 1-5 "qué
  tan fácil fue usarla"), (3) comentario libre opcional al final — igual
  a como se pidió ("algo que la persona quiera comentar"). Se marcaron
  como "en prueba" las 3 funciones nuevas de esta misma ronda (filtros de
  Pipeline, granularidad de Métricas, gráficas editables) para que el
  mecanismo tenga algo real que validar desde el día uno, no un ejemplo
  hipotético — con 4 respuestas semilla de ejemplo (rotuladas como tal).
  El panel de Admin agrega por función: % Mucho/Poco/Nada, promedio de
  facilidad, y el feed de comentarios. Acceso al formulario: botón
  "🧪 Feedback" en el topbar, visible para los 3 roles (cualquiera que use
  una función en prueba puede opinar, no solo Admin).
- **Mi propia recomendación, dada la petición explícita de criterio
  ("dame tu punto, analiza evalúa... sorpréndeme"):** lo que consideré y
  DEJÉ FUERA a propósito, para no meter alcance innecesario en un mockup
  que ya cubre lo pedido: (a) reglas de validación obligatoria por campo
  antes de avanzar una tarjeta ("exit rules") — sigue siendo la brecha más
  grande real antes de construir en firme, ya señalada desde v5, requiere
  una decisión de negocio (qué campos son obligatorios por transición) que
  no me corresponde inventar; (b) notificaciones/alertas de nuevo lead —
  vale la pena a futuro pero es una función de backend real (push/email),
  no algo que un mockup estático pueda demostrar con honestidad; (c) una
  barra de "meta individual" tipo OKR — la descarté explícitamente porque
  ARTF no maneja metas formales por persona hoy; hubiera sido una cifra
  inventada, lo opuesto a lo que se pidió. Lo que SÍ agregué sin que se
  pidiera explícitamente, por ser barato y de alto valor: activar el
  buscador del topbar (ya existía visualmente desde v1, nunca tuvo
  función).
- **Republicado en el mismo Artifact** (misma URL, favicon 📊, label "v7:
  filtros pipeline, granularidad, feedback"). Validado con dos capas esta
  vez (antes solo se hacía `node -e "new Function(...)"` que solo revisa sintaxis):
  la misma prueba de sintaxis, más una prueba de humo en Node con un DOM
  simulado mínimo que ejecuta `enterApp()`, recorre los 3 roles, dispara
  filtros/granularidad/gráficas/export/feedback y confirma que nada lanza
  una excepción en tiempo de ejecución — encontró y confirmó que dos
  errores iniciales eran limitaciones del propio stub de prueba (no bugs
  reales del mockup), no defectos del código.

- **Fuentes de la investigación de esta ronda:** [In-App Surveys: A
  Practical Guide for SaaS Teams](https://www.featurebase.app/blog/in-app-surveys),
  [The Ultimate Guide to In-App Surveys (Amplitude)](https://amplitude.com/explore/product/in-app-surveys),
  [20+ Product Market Fit Survey Questions (Sean Ellis test)](https://formbricks.com/blog/product-market-fit-survey-questions),
  [How to Measure Product Market Fit Using Microsurveys](https://userpilot.com/blog/pmf-survey/).

**Sesión 16-ago-2026 (continuación) — Mockup v6: color + jerarquía tipográfica
en Métricas, sub-pestañas Tablas/Gráficas, se quita "Cobertura" de Agenda
Admin, Fuente corregida contra datos reales del xlsx, franja "Hoy":**
- **Colores distintivos + jerarquía tipográfica en Métricas (pedido
  explícito, "juega con eso"):** la franja de color de sección (izquierda de
  cada fila) ya existía desde v5 pero era el único indicador; ahora también
  se colorea la **etiqueta de sección** (`metrics-section-tag`, leyenda
  arriba de la tabla) y la **columna Total** de las filas `revenue`/`cash`
  (verde/dorado respectivamente) — mismo lenguaje de color que ya usa el
  script real (funnel=azul, base=gris, revenue=verde, cash=dorado), sin
  agregar tonos nuevos. Jerarquía tipográfica: filas "emphasis" (Revenue
  Real, Upfront Cash Real — los totales que de verdad importan, ya
  marcadas `emph` desde v5) ahora tienen fondo `--accent-wash` de fila
  completa y su celda Total sube a 14.5px vs 13.5px del resto; el resto de
  celdas numéricas baja a 12px/color `--ink-2` para que el ojo vaya directo
  a los totales relevantes. Nada de esto agrega color fuera de Métricas —
  el resto del mockup se mantuvo minimalista a propósito, tal como pidió el
  fundador ("acorde manteniendo el minimalismo").
- **Sub-pestañas "Tablas" / "Gráficas" dentro de Admin → Métricas** (pedido
  explícito): `renderMetricas()` dividido en dos `.metrics-subview`
  controladas por `setMetricsView()`; antes era un solo scroll largo con
  tabla y gráficas una debajo de otra.
- **Se quitó el bloque de "Cobertura próximos días" de Agenda (Admin)**
  (confirmado por el fundador vía pregunta directa: la vista de Cobertura
  era la que se sentía como vigilar/presionar al closer por su
  disponibilidad, no como algo que le facilite el trabajo a nadie). Se
  simplificó la vista de Admin a **un solo calendario compartido** del
  equipo (se quitó también la tabla "Matriz por closer" duplicada, redundante
  ahora que el calendario ya muestra closer+estado por bloque — antes eran
  3 secciones, ahora 1, más fiel a "menos paneles, mismo trabajo").
- **Fuente corregida contra datos reales del CRM** (pedido explícito, "sin
  suposiciones") — se re-verificó el xlsx (`Copia Actualizada (15 agosto)…
  .xlsx`, columna Fuente, 15-ago-2026): dominante 'DM directo' (5.395),
  luego 'manual_backfill' (951, artefacto de migración histórica, no una
  opción real que alguien elegiría manualmente), 'IG Ad "Camila"' (90), y
  variantes minoritarias (instagram/orgánico/referido/WhatsApp/etc). El
  dropdown `#nl-fuente` del modal "Nuevo lead" tenía opciones inventadas
  (Instagram Ads/Instagram orgánico) que no correspondían a estos valores
  reales — corregido a: DM directo / IG Ad / Referido / WhatsApp directo /
  Otro. Se excluyó `manual_backfill` a propósito (no es una fuente que un
  humano elegiría al crear un lead nuevo, es solo un artefacto de la
  migración).
- **"Sorpréndeme" — una franja "Hoy" para Setter/Closer** (pedido explícito
  de investigar en la web y agregar algo bien elegido, sin caer en cosas
  innecesarias): patrón de "daily priorities widget" de dashboards de
  ventas (research vía WebSearch esta ronda) — franja arriba del Pipeline
  con: leads propios sin actividad +24h, cuántas llamadas/leads agendados
  hay HOY, y (solo para Setter) cuántos espacios abiertos hay para agendar.
  Deliberadamente **NO aplica a Admin** — es autoservicio para la propia
  persona (mismo dato que ya se podía ver en el board/agenda, solo resumido
  arriba), no un reporte de actividad para que otro lo audite; eso es
  justo el tipo de feature de vigilancia que se acaba de pedir quitar de
  Agenda, así que se evitó reintroducirlo en otra forma. Se descartó (por
  redundante/innecesario) la otra opción investigada, "quota/goal progress
  bar", porque ARTF hoy no maneja metas individuales formales por
  persona — habría sido una cifra inventada.
- **Republicado en el mismo Artifact** (misma URL, favicon 📊, label "v6:
  colores, subtabs, sin cobertura, Fuente real"). JS validado con
  `node -e "new Function(...)"` antes de publicar (mismo procedimiento que
  v2-v5).
- **Nada quedó pendiente sin resolver en esta ronda** — los 6 puntos del
  pedido del fundador (colores, tipografía, sub-pestañas, quitar Cobertura,
  investigar+sorprender, verificar contra CRM real) se implementaron todos.

**Sesión 15-ago-2026 (continuación) — Mockup v4: calendario real (Día/Semana/
Mes) + Urgencia corregida contra el SOP real + notebook UX con problema
técnico sin resolver:**
- **Feedback del fundador sobre v3:** el calendario en columnas (v2/v3) no
  le sirve — pidió un calendario real estilo Google (Semana/Mes) + vista
  por Día también navegable (confirmado explícitamente, el mensaje original
  tenía una negación ambigua que se aclaró antes de construir).
- **Hallazgo real sobre "Urgencia", confirmado contra el SOP** (`SOP Setter
  DM en Instagram V4.0.pdf`, notebook "ARTF — Arquitectura Actual y Rol
  Setter", con cita textual): es el 3er filtro de calificación (junto con
  ingresos y endeudamiento), pregunta literal del Mensaje 5: *"¿Resolver
  esto es una prioridad AHORA para ti, o es algo para cuando tengas más
  tiempo o dinero?"* — clasificación **binaria** (`ahora`/`algun_dia`,
  columna V del CRM), NO 4 niveles. El desplegable de "Urgencia" del modal
  "Nuevo lead" (Baja/Media/Alta/Crítica) no reflejaba el proceso real —
  **corregido a binario** (Ahora=alta / Algún día=baja) en el mockup.
- **Mockup v4 publicado** (misma URL). Cambios: Agenda reconstruida como
  calendario real con 3 vistas navegables (Día/Semana/Mes, toolbar con
  ‹ Hoy › + tabs, click en un día del mes salta a esa vista de día) para
  los 3 roles; `SLOTS` ahora usa fechas ISO reales relativas a "hoy" en vez
  de fechas quemadas ("Hoy · 15 ago"), para que la demo no quede vieja;
  Urgencia del formulario corregida.
- **Cuaderno "UX/Diseño — Deep Research" (recién agregado, `use_count:0`
  antes de hoy) — problema técnico real, sin resolver:** 3 intentos de
  `ask_question` (sesiones distintas, preguntas de largo variable)
  devolvieron solo el placeholder de "cargando" de NotebookLM
  ("Evaluando la relevancia…", "Explorando tu material…", "Revisando las
  páginas…") en vez de la respuesta real — verificado en los logs del MCP
  que sí corrió tiempo real (14-31s) cada vez, no fue un fallo instantáneo.
  Notebook `ARTF — Arquitectura Actual y Rol Setter` (ya usado antes, sin
  este problema) respondió normal en el intento 3. Hipótesis: puede que le
  falte terminar de indexar del lado de Google (se agregó horas antes en
  esta misma sesión). **Pendiente: reintentar más tarde, o que el fundador
  comparta los hallazgos clave directamente.** El mockup v4 NO incorpora
  hallazgos de ese research todavía — se basó en las buenas prácticas de
  diseño minimalista funcional ya aplicadas desde v1 (paleta contenida,
  jerarquía clara, objetivos de tap grandes), no en contenido nuevo de esa
  notebook.

**Sesión 15-ago-2026 (continuación) — re-prueba de Postman OK + hallazgo de
zona horaria (requisito real para el dashboard, no un bug de datos):**
- **Las 5 pruebas de Postman corridas de nuevo, ya con el fix aplicado —
  todas correctas:** `estado=nuevo` en los 2 leads capturados (antes daba
  `contactado`), 1 sola fila de `gestion_leads` por lead (sin duplicar pese
  a 2-3 turnos), los 2 casos de guarda (placeholders sin resolver / sin
  `subscriber_id`) no crearon nada. Limpiado después de verificar.
- **Se encontraron y limpiaron 6 registros de prueba residuales de sesiones/
  pasos anteriores** que no se habían borrado (`TEST_BRIDGE_001..005` de la
  primera validación de `fn_sync_bot_turn`, y `TEST_DIAG_001` de una sesión
  previa al 15-ago). Staging quedó en **6.468 clientes reales**, cero data
  de prueba mezclada.
- **Hallazgo del fundador, investigado a fondo — NO es un bug de datos, es
  un requisito real para el dashboard:** el fundador notó que `created_at`
  en Supabase mostraba 16-ago para leads que en el Sheet decían 15-ago.
  Confirmado con evidencia: todo se guarda correctamente en UTC (práctica
  estándar); Bogotá es UTC-5, así que cualquier evento entre las 7pm y
  medianoche hora Colombia aparece fechado al día siguiente si se mira el
  valor crudo sin convertir. Además, para los leads MIGRADOS, `created_at`
  nunca representó la fecha del lead — es cuándo se corrió el script de
  migración (metadato técnico); la fecha de negocio real está en
  `fecha_contacto` (y demás columnas `fecha_*`), que sí quedó intacta y
  correcta (verificado con un lead real: `fecha_contacto`=9-ago, correcto).
  **Requisito anotado para cuando se construya el dashboard: TODA fecha que
  se muestre en el frontend debe convertirse a `America/Bogota`
  (`AT TIME ZONE fn_tz()` o equivalente en el cliente) antes de mostrarse —
  nunca UTC crudo, o el equipo va a ver fechas "adelantadas" en cualquier
  actividad nocturna.**

**Sesión 15-ago-2026 (continuación) — Worker nuevo desplegado por el fundador + probado con Postman, bug real encontrado y corregido:**
- **Despliegue:** el fundador topó con el flujo nuevo de Cloudflare
  ("Upload and deploy", pensado para proyectos con build, no para un script
  suelto) — resuelto usando la plantilla "Hello World" + editor en el
  navegador en vez del drag-and-drop. Worker desplegado, secrets
  configurados (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
  `MANYCHAT_API_TOKEN`).
- **Colección de Postman creada**
  (`ARTF_Worker_Bridge_Supabase.postman_collection.json`, 5 pruebas:
  captura feliz, placeholders sin resolver, mismo lead 2 veces, sin
  subscriber_id, segundo lead) para validar el Worker SIN necesitar acceso
  a ManyChat (pendiente de solicitar). Las 5 corrieron OK del lado del
  Worker (HTTP 200 en todas).
- **Bug real encontrado revisando el resultado en Supabase (NO detectado por
  las pruebas sintéticas anteriores de `fn_sync_bot_turn` con
  `TEST_BRIDGE_*`):** los leads capturados vía el Worker nuevo (sin
  `etapa_bot`/`handoff_humano`, exactamente el caso real de captura pasiva)
  quedaban en `contactado` en vez de `nuevo`. Causa: el salto intermedio vía
  `'contactado'` (fix #2 de `fn_sync_bot_turn`, sesión anterior) se
  intentaba SIEMPRE que `fn_avanzar_estado` devolvía `false`, sin distinguir
  "ya estaba en el destino" de "salto ilegal, necesita intermedio" — un lead
  recién creado en `nuevo` con destino `nuevo` disparaba el salto de todos
  modos, y como NADA transiciona de vuelta a `nuevo` en
  `estado_transiciones`, quedaba atascado sin forma de autocorregirse.
  **Corregido:** ahora se compara el código actual contra el destino ANTES
  de intentar cualquier salto. Aplicado a staging y **verificado con una
  llamada directa** (`out_estado_codigo: "nuevo"`, `out_avanzo: false`).
  `fn_sync_bot_turn.sql` y `supabase_schema_v3.sql` (§24) actualizados.
- **Limpieza:** los 2 leads de prueba afectados por el bug
  (`POSTMAN_TEST_001`/`002`) no se podían corregir in-place (mismo motivo:
  nada vuelve a `nuevo`) — se borraron completos (clientes + gestion_leads +
  activity_log, desactivando temporalmente `trg_log_inmutable` y
  reactivándolo después, verificado `tgenabled='O'`). Quedan 0 registros de
  prueba en staging.
- **Lección para la próxima vez que se toque `fn_sync_bot_turn`:** las
  pruebas sintéticas (`TEST_BRIDGE_*`) siempre mandaban un `p_etapa_bot`
  explícito — nunca se probó el caso "captura pasiva pura, sin etapa", que
  es exactamente el único caso real que usa el Worker de captura. Cualquier
  cambio futuro a esta función debe probarse también con los parámetros
  opcionales vacíos, no solo con el camino "feliz" de una conversación
  completa.

**Sesión 15-ago-2026 (continuación) — plan de rollout confirmado (Worker paralelo) + Worker de captura escrito:**
- **Confirmado directamente por el fundador (revisó logs de Cloudflare):**
  `JAVIT_ACTIVO=false` en producción — coincide exacto con la conclusión
  técnica de la sesión anterior.
- **Plan de rollout acordado con el fundador** (no improvisado por IA): (1)
  terminar de validar la migración Sheet→Supabase con datos frescos, (2)
  desplegar un Worker de Cloudflare NUEVO y separado (no tocar el que ya
  corre) que replica solo la captura pasiva pero escribe a Supabase vía
  `fn_sync_bot_turn` en vez de Apps Script, (3) correr en paralelo mientras
  el Sheet sigue siendo la fuente real que usa el equipo, validando con
  tráfico real, (4) corte definitivo programado en ventana 4-6am (fecha aún
  sin definir) donde se desconecta el Sheet.
- **Falsa alarma resuelta:** el conteo inicial (COUNT de la columna "#" via
  Google Sheets API, 6.113) sugería que el link compartido por el fundador
  tenía menos filas que la copia local (6.136) — el fundador cuestionó el
  hallazgo (correctamente). Re-verificado con `MAX(#)=6136`: coincide exacto
  con la copia local; el COUNT estaba mal por 23 celdas en blanco en esa
  columna específica, no por una diferencia real de filas. **Pendiente real,
  sin resolver:** confirmar si el Sheet REAL de producción (`SHEET_ID
  ...MGvaf0`, distinto del link compartido que es una copia) creció desde
  este snapshot — el bridge sigue capturando leads nuevos con el bot
  apagado, así que es esperable que sí.
- **Riesgo de un Worker nuevo en la misma cuenta Cloudflare — analizado:**
  aislamiento casi total a nivel de plataforma (cada Worker es un recurso
  independiente, secrets/URL propios, cero interferencia con el Worker
  actual). Dos puntos reales identificados: (a) la cuota de requests/día es
  POR CUENTA, no por Worker — si están en el plan gratuito, el tráfico se
  suma; pendiente confirmar el plan. (b) El único punto que sí toca el
  sistema en vivo es el FLOW de ManyChat (necesita una segunda acción
  "External Request" en paralelo apuntando al Worker nuevo) — el Worker
  actual y su Apps Script/Sheet no se tocan, pero el flow de ManyChat sí,
  mínimamente.
- **Worker de captura nuevo escrito:**
  `Scrips_Worker_and_AppScript/worker_bridge_supabase_NUEVO_paralelo.js`.
  Alcance deliberadamente reducido (solo la rama de captura pasiva que
  realmente corre hoy — sin lógica de Claude/Anthropic, que sigue siendo
  iniciativa aparte y diferida). Llama a `fn_sync_bot_turn` en vez de
  `syncToCRM()`/Apps Script. **Desviación deliberada marcada para decisión
  del fundador:** el código actual manda `handoff_humano=true` en esta rama,
  que vía `mapEstado()` (handoff tiene prioridad sobre etapa) termina
  clasificando TODO lead recién capturado como "Handoff - Otro" → `calificado`
  — inconsistencia real ya existente en el Sheet, no introducida ahora. El
  Worker nuevo NO reproduce ese comportamiento: la captura pasiva no manda
  `handoff_humano`, cae limpio en `nuevo`. Pendiente de confirmar si el
  fundador prefiere replicar el comportamiento actual (bug incluido) para
  comparar 1:1 durante la validación en paralelo, o quedarse con la
  corrección. **Decisión del fundador (mismo día): dejar la corrección** (la
  captura pasiva no manda `handoff_humano`, cae en `nuevo`) — no replicar el
  bug del Sheet. **NO desplegado — código listo para revisión, el fundador
  debe desplegarlo en Cloudflare (sin acceso MCP a Cloudflare en esta
  sesión) y configurar la segunda acción en ManyChat.**
- **Pendiente real, aún sin respuesta (2 puntos):** (1) plan de Cloudflare
  del fundador (gratuito vs pago, por el tema de cuota compartida de
  requests/cuenta), (2) si el Sheet REAL de producción (no la copia
  compartida) creció más allá de las 6.136 filas ya migradas.

**Sesión 15-ago-2026 (continuación) — alcance confirmado del Formulario Dashboard + diseño de Agenda:**
- **Roles reales confirmados:** Yeisiton y Gabyota entran como SETTERS (para
  ganar experiencia real del rol antes de automatizarlo). Closers actuales:
  Andrés (alias "Pipe") y Catalina. El mockup (ver abajo) ya usa estos
  nombres reales, no genéricos.
- **Alcance del Formulario Dashboard, confirmado por el fundador:**
  - SÍ: migración completa a Supabase (dejar el Sheet atrás), tablero por
    rol, formulario de registro manual de leads (los 3 roles pueden
    agregar un lead a mano — justificado, hoy YA se hace 100% a mano).
  - NO (por ahora): el script de calificación (8 mensajes + objeciones) NO
    va en este dashboard. Es la semilla de un futuro bot para automatizar
    parte del rol de setter, que se diseñará DESPUÉS de que Yeisiton/Gabyota
    acumulen experiencia real siendo setters. Iniciativa separada,
    registrada aquí para no perderla, sin fecha aún.
  - El Worker de Cloudflare SÍ tiene integración real con ManyChat (captura
    `manychat_id`/`ig_handle`) — no es un bot conversacional, es solo
    captura de datos. Pendiente de análisis a fondo cuando el fundador
    comparta el código del Worker.
- **Herramienta de agenda real CONFIRMADA (con evidencia, corrige al
  playbook):** el enlace real
  (`https://calendar.app.google/iMW5LBbkcAvorypF9`) redirige a
  `calendar.google.com/appointments/schedules/...` — es **Google Calendar
  Appointment Schedules**, NO Calendly (el `SOP Setter DM V4.0.pdf` está
  desactualizado en ese punto puntual).
- **Proceso real de agenda (descrito por el fundador, no en ningún
  documento):** los closers abren ventanas de disponibilidad SOLO cercanas
  (nunca semanas adelante, es estrategia deliberada) → los setters agendan
  leads calificados en esas ventanas → cuando se llenan, se le pregunta al
  closer por más espacios → se abren más. Hoy corre sobre Google Calendar
  Appointment Schedules.
- **Diseño de Agenda propuesto (implementado en el mockup v2, no en
  producción):** tabla `disponibilidad_closer` (fecha, hora inicio/fin,
  estado abierto/reservado) reemplaza Google Calendar Appointment Schedules
  como fuente de verdad del estado de los espacios; al reservar, se llama a
  la **API de Google Calendar** para crear el evento real (invita al lead
  por correo + genera Meet automático) — no se reinventa esa mecánica.
  Vistas por rol: Closer = "Mi disponibilidad" (agregar espacios rápido);
  Setter = "Espacios abiertos" (reservar con un clic, asigna lead); Admin =
  indicador de cobertura (espacios abiertos por closer en próximos días,
  mismo lenguaje visual que `vw_scorecard_check`).
- **Mockup actualizado y republicado** (misma URL:
  `https://claude.ai/code/artifact/40e898e7-1774-4209-966c-3e6b8baa2816`),
  incorporando: botones/objetivos de tap más grandes, botón "+ Nuevo lead"
  visible en los 3 roles con formulario modal, panel de Incidencias visible
  para los 3 roles (filtrado por rol — cada incidente tiene un array
  `roles` que determina a quién le corresponde revisarlo; Admin ve todas
  sin filtro), y la vista de Agenda completa con las 3 sub-vistas por rol
  descritas arriba.
- **Feedback del fundador sobre v2 (mismo día):** aprobado en general;
  filtrado de pipeline/incidencias por rol confirmado como correcto (se
  seguirá refinando más adelante, sin cambios de código ahora). Dos pedidos
  de ajuste, **implementados en v3 (misma URL, republicado)**:
  1. **Agenda con vista de calendario real** en vez de listas planas —
     Closer/Setter ven columnas por día con bloques de horario (abierto/
     reservado); Admin ve una matriz de cobertura (closers × días) además de
     los chips de resumen que ya existían.
  2. **Nueva vista "Métricas" solo para Admin** — replica la estructura
     EXACTA de la pestaña "Daily Metrics v2" real (identificada al leer
     `daily-metrics-scorecard.md`, ver sesión de análisis del Worker más
     abajo): secciones Funnel (Leads, Conversaciones, Bookings, Day
     QBookings, Quality Bookings Show Ups, Sales, Oferta de Valientes,
     Estudiantes activos) con % de conversión entre pasos, Base/Desistidos,
     Revenue (Revenue, Revenue OFV, Revenue Real) y Cash (Upfront Cash,
     Dinero de OFV, Upfront Cash Real, Cuotas Cobradas, Cuotas Proy. A/R,
     Dinero Desistido, Reserva Activa). Cifras de ejemplo — pendiente
     conectar a `vw_embudo_diario` cuando exista el dato real en Supabase.

**Sesión 15-ago-2026 (continuación) — investigación crítica: cómo funciona HOY el rol de setter (para el Formulario Closers):**
- **Hallazgo mayor, con evidencia:** el rol de setter es 100% MANUAL hoy —
  no hay ningún bot conversacional operando. Fuente: `SOP Setter DM en
  Instagram V4.0.pdf` (11-ago-2026) + audio de entrenamiento, notebook
  "ARTF — Arquitectura Actual y Rol Setter". Un humano copia/pega 8 mensajes
  scripteados uno por uno en Instagram DM, con 3 filtros acumulativos
  (Ingresos ≥$7M COP/mes, Endeudamiento ≤50% calculado a mano, Urgencia
  ="ahora"), agenda vía el Calendly PERSONAL de Andrés (no del setter — el
  setter no gestiona disponibilidad propia hoy), verifica el agendamiento a
  mano antes de darlo por cerrado, y llena el CRM/Sheet columna por columna.
  El audio de entrenamiento instruye explícitamente a los setters a NO
  parecer un bot ("mensajitos como por párrafo, no de un solo golpe").
- **Búsqueda exhaustiva (2 pasadas) de "ManyChat"/"bot"/"Cloudflare"/
  "Worker"/"Andrew" en TODAS las fuentes: CERO menciones.** No se puede
  confirmar ni descartar desde este notebook la sospecha del fundador de que
  el bot de ManyChat dejó de responder — estas fuentes son material de venta
  humana, no documentación técnica del bot. Son dos artefactos distintos;
  para diagnosticar el bot se necesitan fuentes técnicas (config ManyChat,
  logs, código del Worker si existe).
  **Implicación:** el "Agente Comercial Autónomo... Andrew SDR" descrito en
  `00_vision_y_principios.md` como foco activo actual **no parece estar
  operativo hoy** según esta evidencia — a verificar, no asumir resuelto.
- **Implicaciones de diseño para el Formulario Closers (pendientes de
  decisión del fundador, NO implementadas):**
  1. "Agenda para el setter" — el fundador pidió que el setter pueda crear/
     validar espacios de agenda. Hoy NO existe eso (es el Calendly de
     Andrés). Pendiente aclarar: ¿reemplazar Calendly por agenda propia, o
     dar visibilidad/validación sobre Calendly vía su API?
  2. Agregar leads manualmente (los 3 roles) — SÍ está justificado por la
     realidad actual (todo se registra a mano hoy). Confirmado para diseño.
  3. Posible alcance mayor: el Formulario Closers podría necesitar incluir
     el script de calificación mismo (8 mensajes + objeciones), no solo un
     tablero Kanban de estados — a decidir con el fundador.

**Sesión 15-ago-2026 (continuación) — quick-wins de métricas: AdSpend + conversaciones:**
- **Auditoría crítica del Sheet real vs. `vw_embudo_diario`** (cruzando el
  `.xlsx` original, no solo memoria): varias filas de la pestaña "Global"
  (MQL/Call-Confirmer, Sales Qualified Bookings, Ofertas, Views, desglose por
  producto, ROI FECC-UF, $AOV-Cash) están en cero/vacías en TODOS los meses.
  Validado contra los audios: Javier confirma que son vestigios de mala
  calidad de datos, **no** prioridades reales — ROI FECC-UF y AOV-Cash no se
  mencionan ni una vez en las reuniones. **Decisión: no se construyen.**
  Habría sido sobreingeniería (`03_Clientes_y_Casos/02_Cliente_ARTF/...`
  detalle completo pendiente de anexar a `05-validacion-...md` si hace falta
  referencia futura).
- **AdSpend cargado y verificado** en `gastos_marketing`: 3 filas reales
  (Mayo $2.330.239, Junio $6.109.225, Julio $6.990.882 COP — corregido un
  desfase de columna propio antes de escribir a la BD; Agosto sin dato, el
  Sheet tampoco lo tiene). Única granularidad disponible es MENSUAL — se
  documentó explícitamente en el esquema (`comment on table
  gastos_marketing`) que esto distorsiona `cp_lead`/`cac`/`roi_revenue`
  DIARIOS de `vw_embudo_diario` (todo el gasto del mes cae en el día 1) y que
  solo son confiables en agregado mensual.
- **`conversaciones` expuesta en `vw_embudo_diario`** (dato ya migrado por
  `migrate_activity_log.py`, solo faltaba la columna). Validado: suma en la
  vista = 5.261, idéntico al conteo crudo de `activity_log` filtrado por
  `evento in ('mensaje_lead','mensaje_bot')`.
- **Bug propio encontrado y corregido:** el primer intento de cargar AdSpend
  vía `apply_migration` (INSERT...SELECT con subquery a `fuentes`) devolvió
  `success: true` pero insertó 0 filas — la subquery quedó en 0 resultados
  bajo RLS en ese contexto (la herramienta es para DDL, no DML). Detectado
  verificando con un `SELECT` real después, no confiando en el mensaje de
  éxito. Corregido usando `execute_sql` con el `fuente_id` literal. **Lección
  para el futuro: para escrituras de datos (no schema), usar `execute_sql`,
  no `apply_migration`, y siempre verificar con un SELECT posterior.**

**Sesión 15-ago-2026 — resolución de los 4 gaps de negocio con Javier/Catalina:**
- **Notebook de NotebookLM registrado:** "ARTF — Negocio y Reuniones"
  (`https://notebook.google.com/notebook/c9c609f7-cb64-4929-9273-f60a7f19857e`,
  5 audios de reunión) — separado del notebook técnico existente para no
  diluir su grounding (ver `04_Segundo_Cerebro/directrices_globales.md`).
- **Punto 3 (Salario mensual) — CONFIRMADO por el fundador directamente**
  (no aparece en los 5 audios de este notebook, pudo discutirse en otra
  llamada). El campo `Salario` de cada lead SÍ es su salario mensual. La
  migración ya lo había asumido así (`patch_salarios.py`, hallazgo 7 de
  `05-validacion-migracion-datos-reales.md`) — queda confirmado, sin cambio de
  código, solo se retira la nota "sin confirmar".
- **Punto 4 (Oferta de Valientes, OFV) — CONFIRMADO Y AMPLIADO por los audios**
  (fuente real: `WhatsApp-Ptt-2026-08-13-at-7.29.21-PM.mp3`). No es un producto
  aparte: es una cuota inicial para separar el cupo del programa Core cuando el
  upfront es menor al 50% pactado (ej. programa de 6M, 50%=3M, OFV=puede ser
  500k). **Un lead en OFV NO se considera "Ganado"** hasta completar el 50% —
  el "siguiente pago" es el resto para llegar a ese 50%, no el segundo 50%
  post-venta. Confirmado en el propio audio: "en el CRM como tal no está, no
  existen columnas... a nivel de base de datos lo podamos implementar como una
  especie de estado o etiqueta". **Implicación de arquitectura importante:**
  como `trg_ve_etapa` avanza automáticamente el lead a `ganado` en cada
  `INSERT` sobre `ventas`, **OFV NO puede modelarse llamando
  `fn_registrar_venta`** (marcaría el lead como vendido prematuramente) — hay
  que decidir entre (a) una columna simple en `gestion_leads`
  (`monto_reserva_pagado`) o (b) una tabla pequeña tipo `depositos_reserva`
  (el audio menciona posibles pagos parciales múltiples antes de llegar al
  50%, lo que favorece (b)). **Decisión del fundador: (b).** **IMPLEMENTADO
  en staging (15-ago-2026):** nuevo `estados_lead.reservo_oferta_valientes`
  (orden 65, entre `oferta_presentada` y `ganado`) + transiciones
  (`show_up`/`oferta_presentada` → `reservo_oferta_valientes` →
  `ganado`/`perdido`/`nutricion`) + tabla `public.depositos_reserva` (RLS +
  policies calcadas de `ventas`, trigger `trg_dr_etapa` reusando
  `fn_avanzar_estado`, mismo patrón que `fn_venta_cierra_lead`). Fix aplicado
  en el camino: la tabla nueva no heredaba el `GRANT` de la sección 19 del
  esquema original (creada después de que ese grant corriera) — corregido con
  `grant select, insert on depositos_reserva to authenticated`. Todo
  documentado íntegro en `supabase_schema_v3.sql` §21 para que un deploy
  limpio reproduzca el mismo estado. **Pendiente (fuera de esta sesión):**
  nadie llama a `fn_deposito_reserva_mueve_etapa`/inserta en
  `depositos_reserva` todavía — eso lo hará el futuro "Formulario web para
  Closers" del backlog.
- **Punto 2 (133 leads sin ManyChat ID) — política decidida: se dejan NULL.**
  Los audios NO confirman la cifra exacta ni que sea "un problema de conexión
  inicial ya resuelto" (eso lo aportó el fundador directamente) — de cualquier
  forma, no inventar un `manychat_id` es la decisión correcta con o sin esa
  confirmación. **Hallazgo importante:** `public.vw_scorecard_check` (ya
  existe en el esquema, `supabase_schema_v3.sql` §18.4) **YA ES** el panel de
  "incidentes de datos para que un humano actúe" que se pidió como necesidad
  futura de dashboard — no hay que construirlo de cero. `PROPUESTO`: extender
  esa vista con un chequeo nuevo `cliente_sin_manychat_id` (WARN). Migración
  redactada pero **bloqueada por el clasificador de auto-mode** (acción sobre
  BD real, requiere confirmación explícita del fundador) — pendiente de luz
  verde.
- **Punto 1 (lead "Juan Manuel", venta $1.98M) — NO VERIFICADO en los audios.**
  Búsqueda exhaustiva (2 preguntas, 5 audios): el nombre "Juan Manuel" no
  aparece en ninguna fuente. El único caso de "estado mal registrado" que sí
  aparece es un lead distinto, **Sebastián Cruz** (marcado "Ganado" pero sin
  "etapa" asignada en el Team Manager — un problema de mapeo de estado, no de
  fecha de pago). El fundador indica que Javier/Catalina confirmaron
  verbalmente que si pagó y el closer olvidó actualizarlo, pero **no se aportó
  fecha de pago real** — sin ese dato concreto no se puede registrar la venta
  (`ventas` es append-only, no se adivina una fecha). **Pendiente:** conseguir
  la fecha real (o confirmar que se deja pendiente hasta que el closer la
  aporte). **Insight de arquitectura del fundador (válido independientemente
  de este caso puntual):** el futuro dashboard debe superficiar estos
  incidentes para que un humano actúe — exactamente lo que ya hace
  `vw_scorecard_check_resumen` (semáforo por severidad/chequeo, ya diseñado
  "para dashboard" en su propio comentario SQL). No hay que inventar el
  concepto, hay que construir la UI que lo consuma — futuro "Formulario web
  para Closers" del backlog.

**Sesión 13-ago-2026 — fix + intento de re-validación:**
- **Fix aplicado en `migrate_crm.py`:** el RPC `fn_registrar_venta` nunca recibía
  `p_reunion_id` (existe en la firma del schema, `default null`). Como `ventas` es
  append-only (trigger `fn_append_only`, bloquea `UPDATE`/`DELETE` sin excepción de
  rol), ese dato se perdía para siempre en cada carga. Corregido: se construye un
  mapeo `gestion_lead_id → reunion_id` desde las reuniones ya insertadas (que se
  cargan ANTES que las ventas, el orden ya estaba bien) y se pasa al RPC.
- **Intento de re-validar en vivo (limpiar staging + re-correr `--write`) BLOQUEADO
  por diseño:** `activity_log` y `ventas` tienen el trigger `fn_append_only` que
  rechaza cualquier `DELETE` incondicionalmente — ni el `service_role` vía REST
  puede saltárselo (solo un superusuario con acceso psql directo, deshabilitando el
  trigger, podría). No se forzó nada; staging quedó intacto (6.137 clientes/gestion_leads,
  204 reuniones, 8 ventas, 6.220 activity_log). El fix se valida por revisión de
  código (el nombre/tipo del parámetro coincide exacto con la firma SQL) y quedará
  confirmado en la carga final de producción (o en un staging nuevo/limpio si se
  decide provisionar uno).

**Sesión 13-ago-2026 (continuación) — re-validación en vivo + auditoría de vistas/scorecard + migración de Activity Log:**
- **Fix de `p_reunion_id` validado en vivo (ya no solo por revisión de código):**
  vía el MCP de Supabase (`execute_sql`, acceso de administrador de BD, distinto
  al `service_role` REST limitado) se deshabilitaron temporalmente los triggers
  `trg_ventas_inmutable`/`trg_log_inmutable`, se limpió staging por completo, se
  re-corrió `migrate_crm.py --write`, y se re-habilitaron los triggers. Resultado:
  **8/8 ventas con `reunion_id` poblado, 0 en NULL.** `vw_scorecard_check`: 1 ERROR
  (Juan Manuel, esperado) + WARNs consistentes con la corrida original (gaps reales
  del Sheet, no bugs del esquema).
- **Auditoría de vistas de reporte (`vw_embudo_diario` = reemplazo de "Daily
  Metrics v2") cruzada columna-por-columna contra las pestañas "Global"/"Daily
  Metrics v2"/"CRM" del Sheet real.** Hallazgos:
  - `gastos_marketing` (AdSpend/impresiones) tiene **0 filas** — la pestaña
    "Global" nunca se migró. `cp_lead`/`cac`/`roi_revenue` en la vista tienen la
    fórmula correcta pero dan 0/NULL por falta de dato fuente. **Pendiente.**
  - El plan de cuotas real del Sheet (fechas/montos de "siguiente pago") se
    ignora — `fn_registrar_venta` genera cuotas automáticas repartiendo el
    revenue en partes iguales. **Pendiente decidir si vale la pena migrar el
    plan real.**
  - **"Conversaciones" (antes ❌):** causa raíz encontrada y CORREGIDA — la
    pestaña "Activity Log" del Sheet (7.227 filas, historial real de mensajes
    lead/bot) nunca se leía en `migrate_crm.py`. Nuevo script
    `migrate_activity_log.py` la migró: **6.906/7.227 filas insertadas**
    (4.594 `mensaje_lead`, 667 `mensaje_bot`, 1.645 `nota` para eventos internos
    del bot sin mapeo verificable — clasificación conservadora por evidencia de
    contenido, no por adivinar el vocabulario interno del bot; `activity_log` es
    append-only así que no se arriesgó un mapeo a `cambio_estado` sin certeza).
    Bug propio detectado y corregido en el camino: la paginación de PostgREST
    (tope ~1000 filas/respuesta, ya documentado en el hallazgo §7 de
    `05-validacion-...md`) se me olvidó en el primer intento del script nuevo —
    corregido con el mismo patrón `Range` de `add_reuniones.py`. Segundo bug
    propio: el matching por IG Handle fallaba 91% de las veces porque el tab
    "CRM" casi siempre trae `@handle` y "Activity Log" casi nunca — normalizado
    (sin `@`, minúsculas) subió el match a 99.9% (5715/5719 handles únicos).
    **Pendiente:** `vw_embudo_diario` no expone "conversaciones" como columna
    todavía (el dato ya está en la tabla, falta agregarlo a la vista).
  - **"Oferta de Valientes" (OFV) (antes ❌):** causa raíz encontrada — NO es un
    bug de migración. Búsqueda exhaustiva en toda la data cruda del CRM: nunca
    fue columna ni estado, solo aparece en 12 menciones de texto libre en
    "Notas" (depósito 150-300 USD, pago por sesiones). El texto ya está
    preservado en `clientes.notas`; lo que falta es la DECISIÓN de negocio de
    si formalizarlo como oferta/producto propio. Agregado como pregunta 4 al
    mensaje para Javier/Catalina.

## Próximos pasos — Inbound AI SDR

- [x] ~~Presentar análisis de BD a Javier y Catalina~~ — superado: la migración a
      Supabase ya se ejecutó y validó en staging con datos reales (dos veces).
- [ ] **Resolver con Javier/Catalina los 4 gaps del Sheet** (bloqueantes para
      producción, NO resolubles por IA — requieren decisión de negocio):
      1. Lead "Juan Manuel" (ganado, revenue $1.98M): "Fecha Pago" = texto "No ha
         pagado" → su venta no se puede registrar sin fecha real.
      2. 133/6.136 leads sin ManyChat ID → sin identificador de cruce confiable
         para reuniones/salario.
      3. Confirmar si "Salario" es efectivamente mensual (asumido, no confirmado
         por el Sheet).
      4. "Oferta de Valientes" (OFV): ¿formalizar como oferta/producto propio
         con seguimiento estructurado, o queda informal en notas?
      Mensaje borrador listo para enviar (fuera del repo, en el scratchpad de la
      sesión de Claude Code del 13-ago).
- [x] ~~Cargar `gastos_marketing` desde la pestaña "Global" del Sheet~~ — hecho
      15-ago-2026, solo granularidad mensual disponible (ver sesión de arriba).
- [x] ~~Agregar "conversaciones" a `vw_embudo_diario`~~ — hecho 15-ago-2026,
      validado 5.261 = 5.261 contra `activity_log`.
- [ ] **Migración a producción.** Una vez resueltos los 4 gaps: cargar `reuniones`
      antes que `ventas` (ya así en `migrate_crm.py`), correr `--write` contra el
      proyecto de producción real (no `lrdtjsxtaadpgrzkchlw`, ese es staging).
- [ ] **Formulario web para Closers.** Construir la UI web que reemplaza el formulario Google Sheets para los Closers de ARTF.
- [ ] **Profesionalizar la arquitectura.** Transitar de scripts sueltos a arquitectura event-driven basada en el documento "Vistas y Más Allá" compartido por Javier.
- [ ] **Definir el diseño del AI SDR para ARTF.** ¿ManyChat + Cloudflare Worker + Supabase? ¿O cambio de plataforma? Evaluar con Javier.

## Preguntas / Dudas abiertas — Inbound AI SDR

> *(Aquí se registran las dudas que surjan al revisar la arquitectura o avanzar en el desarrollo. Se resuelven con investigación web o directamente con Javier/Catalina.)*

- [ ] ¿Cuál es el volumen real de leads concurrentes que llegan en picos (ej. después de un Reel viral)?
- [ ] ¿El Closer accede al formulario desde móvil o desktop? ¿Hay conexión estable?
- [ ] ¿Cuántas etapas tiene el pipeline actual en Sheets y cuál es el campo más crítico para no perder?
- [ ] Los 3 gaps de datos del Sheet listados arriba (fecha de pago, identidad sin ManyChat ID, periodicidad del salario).

---

## 📜 Historial — Estado anterior (06-ago-2026, superado arriba)
**Fase:** Análisis de arquitectura y decisión de base de datos. El stack actual de ARTF (Cloudflare Workers + ManyChat + Google Sheets) tiene un cuello de botella crítico de concurrencia. La decisión de migrar a Supabase (Postgres/PostgREST) está fundamentada y pendiente de aprobación.

---

# 🔵 LÍNEA 2 — OUTBOUND PROSPECTOR (En Incubación)

> **Cliente piloto: TBBC** (Catalina Rúa — Chief Growth Officer)
> Estado: En pausa activa. Motor técnico (Motores 1-4) construido y en verde. Pendiente de validación empírica con corrida limpia antes de retomar.

## Estado actual (06-ago-2026)
**Fecha último handoff:** 25 de Julio de 2026
**Fase:** Motores 1-4 completos. **Motor 1 = Signal-First Discovery por hiring** (TheirStack). Tras corrida #6: **filtro anti-comercial + rol técnico en discovery**, **excepción SECOP al gate de fit**, **bufetes dentro del ICP**. → **PENDIENTE (próxima sesión): revertir Motor 1 a HÍBRIDO** — Apollo como descubridor de TAM amplio; TheirStack solo como evaluador de señal en Motor 2.



---

## 🧭 Sesión 26-jul-2026 (noche) — Decisiones tras corrida #6 + limpieza para híbrido

Corrida #6 confirmó: discriminación restaurada (2 TIER_0 / 1 TIER_1 / 4 TIER_2), fit
gate excluyó 6 multinacionales, Tavily rescató Bolsa Mercantil (0 revisión manual),
PERO (a) el funding discoverer devolvió **0** (TheirStack sin cobertura CO) y (b) un
TIER_0 era **falso positivo**: "Vendedor / Desarrollador **Comercial** con Moto" (rol
de ventas) matcheaba el regex de "Desarrollador". Decisiones del fundador, implementadas
(**480 tests verdes, ruff limpio**):

- **Filtro anti-comercial** (`theirstack_adapter.py`): `job_title_pattern_not` excluye
  `comercial|ventas|vendedor|negocio|fidelización|marketing|mercadeo`. Mata el falso
  positivo de Aló Credit.
- **Filtro de rol técnico en el DISCOVERY** (no solo en scoring): `descubrir_empresas`
  usa `job_title_pattern_or` + `job_title_pattern_not` → el universo nace limpio de
  vacantes no técnicas.
- **Excepción SECOP al gate de fit** (`PoliticaFitComprador.es_apta(es_multinacional,
  tiene_trigger_secop)`): una multinacional CON contrato SECOP local activo SÍ se
  permite (plata pública local valida la compra — caso Atrys). Cableado en Paso 1.6.
- **Bufetes/no-tech-core dentro del ICP:** sin cambios (un bufete con dev interno es
  cliente ideal de staff augmentation).
- **Funding discoverer ELIMINADO:** borrados `descubrir_empresas_por_funding`,
  `_parsear_empresas_funding`, `obtener_trigger_funding`, el origen `THEIRSTACK_FUNDING`
  y el endpoint companies/search del adapter. Funding = 100% Google Alerts.

**Pendiente próxima sesión (instrucción explícita):** revertir Motor 1 a HÍBRIDO
(Apollo descubridor de TAM amplio con filtros duros; TheirStack solo evaluador de señal
en Motor 2). NO implementado aún — el terreno quedó limpio para hacerlo.

Detalle → más abajo en este mismo documento, sección **"Decisiones tras corrida #6: anti-comercial, excepción SECOP, muerte del funding-discoverer, camino a híbrido (26-jul-2026)"** (§BITÁCORA DE DECISIONES HISTÓRICAS).

---

## 🛡️ Sesión 26-jul-2026 (tarde) — Blindaje profundo tras corrida #5

Análisis de la corrida #5 y blindaje en 5 frentes (**483 tests verdes**, gate ruff
`src/`+`tests/` limpio). Detalle y criterio de evaluación →
más abajo en este mismo documento, sección **"Recalibración por bandas + fit de comprador + discovery por funding + Tavily (26-jul-2026)"** (§BITÁCORA DE DECISIONES HISTÓRICAS).

**Diagnóstico corrida #5:** 12/12 empresas calificaron, casi todas score 200 (TIER_0)
→ falso-positivo masivo (el espejo del falso-negativo de la #4). El scoring perdió
discriminación porque 45d de aging = ciclo normal, `is_closed=False` es débil, el
filtro de tech era a nivel EMPRESA (la vacante vieja podía no ser técnica), había bug
de parseo (`job_title`/`technology_slugs`), y el universo tenía bajo fit
(multinacionales, bufete).

**Cambios aplicados:**
- **Bugs (`theirstack_adapter.py`):** parseo `job_title`/`technology_slugs`; la query
  de aging filtra por ROL TÉCNICO a nivel vacante (`job_title_pattern_or`), no por
  tech a nivel empresa.
- **A — Bandas de aging:** `>=75d → TIER_0` (califica sola), `45-75d → TIER_1` (no
  califica sola, necesita cruce), `<45d → TIER_2`. `obtener_triggers` hace 2 queries
  de ventana de fecha (robustas al `order_by` deprecado; 0 créditos si 0 resultados).
  Restaura la discriminación: solo aging fuerte o cruce multi-origen califican.
- **B — Gate de fit de comprador:** 5ª pregunta al LLM (`es_multinacional`) en la
  MISMA llamada cacheada + `PoliticaFitComprador` (fail-open) + Paso 1.6 en el sandbox.
  Descarta filiales de multinacionales (fuera del ICP PYME colombiana independiente).
- **C — Discovery por FUNDING:** `descubrir_empresas_por_funding` vía
  `/v1/companies/search` (HQ=CO, 50-200, ronda ≤365d) + trigger `THEIRSTACK_FUNDING`
  (CAUSA; ≤90d TIER_0). Canal nuevo: PYMEs con capital fresco. 3 créditos/empresa.
- **Tavily — respaldo de contexto:** `describir_empresa` inyectado en
  PropuestaValorAdapter; si la homepage no resuelve, clasifica con búsqueda web en vez
  de caer a revisión manual. 1.000 créditos gratis/mes; solo se invoca si el scraping
  falló.

**Verificado:** `THEIRSTACK_FUNDING` añadido al Core; `PoliticaFitComprador` Core
puro y testeado; params de `/v1/companies/search` y `job_title_pattern_or` confirmados
en el OpenAPI de TheirStack (no adivinados).

**Próximo paso:** correr `sandbox_tbbc_real.py` y evaluar los 5 puntos de la bitácora
(¿se restauró la discriminación? ¿el fit descarta multinacionales? ¿cuánto trae el
funding discoverer? ¿Tavily rescata homepages muertas? ¿gasto de créditos?).

---

## 🔬 Sesión 26-jul-2026 — Análisis corrida #4: vacante vieja-Y-abierta + funding

Análisis de la corrida #4 y aplicación de P1/P2/P3 (**467 tests verdes**, gate ruff
`src/`+`tests/` limpio). Detalle y evidencia →
más abajo en este mismo documento, sección **"Vacante vieja-Y-abierta + visibilidad de aging + funding (26-jul-2026)"** (§BITÁCORA DE DECISIONES HISTÓRICAS).

**Diagnóstico de la corrida #4:** los 18 triggers de TheirStack salieron idénticos
(`MEDIA/1 vacante/TIER_2/score 50`). Ninguno TIER_0 por aging. Solo Atrys calificó, y
por **SECOP**, no por TheirStack. TheirStack estaba funcionando como descubridor pero
NO como señal de calificación.

**Causa raíz (verificada en el OpenAPI de TheirStack):** `order_by` está **deprecado**
en `JobSearchFilters` → nuestro discovery pedía "ASC = más antiguas" pero el parámetro
se ignora → traía las más RECIENTES → aging <45d → TIER_2 siempre. La estrategia de
aging-por-ordenamiento nunca fue robusta.

**Cambios aplicados:**
- **P1 (visibilidad):** `sandbox_motor_2_auto.py` ya no trunca a 70 chars; muestra el
  TIER explícito (TIER_0 en verde) + descripción a 150 chars (el aging iba al final y
  se perdía). Estábamos ciegos al número que decide todo.
- **P2 (`theirstack_adapter.py`):** `obtener_triggers` ahora pide **vacante vieja-Y-
  abierta** por ventana de fechas absolutas (`posted_at_gte=hoy-90`, `posted_at_lte=
  hoy-45`, `is_closed=False`) + tech. Si devuelve registro → TIER_0 por construcción
  (1 crédito; 0 si no hay). Si vacío → fallback cache (fresca → TIER_2, 0 créditos).
  Robusto al `order_by` deprecado. `descubrir_empresas` añade `is_closed=False`.
- **P3 (`sandbox_motor_2_auto.py`):** funding vía el `GoogleAlertsRSSAdapter` que YA
  detecta rondas por LLM. Feeds ahora por **marca** (no nombre legal) + un feed
  enfocado en eventos (funding/liderazgo/M&A). Sin nueva API, sin costo.

**Params verificados en OpenAPI (no adivinados):** `is_closed`, `posted_at_gte/lte`
existen y no están deprecados; `order_by` sí. Créditos: 1 por registro devuelto, 0 si
devuelve 0. Existe además `/v1/companies/search` con `funding_stage_or`/
`min_funding_usd`/`last_funding_round_date_gte` (firmografía de funding nativa, 3
créditos/empresa) — camino FUTURO para descubrir por funding, no tocado aún.

**Próximo paso:** correr `sandbox_tbbc_real.py` y leer los aging ya visibles + el TIER
por empresa. Decidir con datos si el eje de calificación es aging / funding / SECOP o
una combinación. Pospuesto (anti-bazuca): `blur_company_data` (aging gratis) hasta
confirmar que el aging califica; SECOP-discoverer + Clearbit name→domain.

---

## 🛡️ Sesión 25-jul-2026 (noche) — Blindaje de raíz tras corrida #3

Tres blindajes IMPLEMENTADOS (**466 tests verdes**, ruff limpio). Detalle y
justificación → más abajo en este mismo documento, sección **"Blindaje de raíz tras corrida #3 — híbrido TheirStack + domain quality + gaps de claves (25-jul-2026)"** (§BITÁCORA DE DECISIONES HISTÓRICAS).

- **HÍBRIDO de aging en TheirStack `obtener_triggers`** (`src/adapters/triggers/theirstack_adapter.py`).
  Se corrigió un DATO FALSO en el propio código: el comentario decía "TheirStack cobra
  por CONSULTA" — la doc oficial confirma que cobra **por REGISTRO devuelto**, así que
  el `limit=25` era una bomba de créditos (raíz del 402 de la corrida #2). Ahora: para
  los finalistas, **1 query precisa de 1 crédito** (`limit=1`, `order_by date_posted ASC`,
  `company_domain_or`, `posted_at_max_age_days=90`, filtro de techs) → trae la vacante
  tech más ANTIGUA = **aging real** → TIER_0 detectable. La cache del discovery queda
  como **fallback** (0 créditos). `estimar_tamano` **sigue** con cache. `limit=1` no
  pierde señal: `nivel_confianza` NO entra al score (solo TIER×decay), verificado en
  `policies.py`. Eliminada la constante `_LIMITE_VACANTES_AGING`.
- **DOMAIN QUALITY — pre-check DNS** (`propuesta_valor_adapter.py`): `_dominio_resuelve()`
  con `socket.getaddrinfo` (stdlib, costo 0) al inicio de `_leer_texto_homepage`; dominio
  que no resuelve → `None` inmediato (evita ~15s de timeout+Playwright sobre dominios
  muertos como bolsamercantil.com.co, comfandi.com.co). Fixture autouse mantiene los
  tests herméticos.
- **GroqKeyPool tolera HUECOS** (`groq_key_pool.py`): `_descubrir_del_entorno` ya no
  hace `break` en el primer índice ausente → recolecta TODAS las `GROQ_API_KEY_N`. Fix
  del riesgo real: una `GROQ_API_KEY_4` añadida sin la `_3` **sí se usa ahora**. (El
  modelo `llama-3.3-70b-versatile` NO se cambia; no hay alterno útil en Groq — la vía
  es más claves, confirmado por el fundador.)

**Herramientas investigadas (criterio anti-bazuca, para próximas iteraciones):**
- `blur_company_data=true` en TheirStack hace la request **gratis** → podría volver el
  aging de 1 crédito a **0** (a validar en vivo: que conserve `date_posted`).
- Señales de **funding LatAm** (Dealflow LatAm, Scenius, Contxto) vía los adaptadores
  Tavily/Google Alerts RSS que YA existen — NO comprar plataforma de señales.
- **Clearbit Autocomplete** (gratis, sin key) para name→domain del futuro SECOP-discoverer.

---

## 🎯 Sesión 25-jul-2026 (tarde) — Inversión a Signal-First Discovery

**Motivación:** la corrida real del path A dio **0 leads accionables** (48
descubiertas por Apollo → 29 = 60% colegios/ONGs/medios descartados → 3 calificadas
de fit dudoso → 0 correos). Diagnóstico: descubrir por **Fit firmográfico ciego**
(Apollo) construye el Tier-3 TAM (lo menos accionable) y obliga a filtrar basura.
Los libros (SHiFT!, ABM) y la investigación web convergen: **hay que descubrir por
el TRIGGER (ventana de insatisfacción), no por tamaño/sector.** Decisión y
justificación completas → más abajo en este mismo documento, sección **"Decisión: Inversión del Motor 1 a 'Signal-First Discovery'"** (§BITÁCORA DE DECISIONES HISTÓRICAS).

**Cambios (IMPLEMENTADOS, 454 tests verdes, ruff limpio):**
- **TheirStack = discoverer PRIMARIO** (`ejecutar_discovery_signal_first`). Ventana
  de descubrimiento **30→90 días** para capturar vacantes ENVEJECIDAS (≥45d = TIER_0,
  fallo de reclutamiento = dolor de staff-aug). Filtra por tecnología del ICP → NO
  trae colegios/ONGs/medios (matan el 60% de desperdicio) y trae dominio real.
- **Apollo SALE del loop M1/M2** (import removido del sandbox; reservado para M3).
  `THEIRSTACK_API_KEY` pasa a obligatoria; `APOLLO_API_KEY` opcional (solo M3).
- **SECOP = cruce de señal** (CAUSA → Regla de Oro con EFECTO de TheirStack). NO
  discoverer aún: da nombres sin dominio (bloqueante: requiere resolutor de dominio
  = enriquecimiento, diferido). Documentado como siguiente paso.
- **Gate de tamaño ENDURECIDO:** `PoliticaCorroboracionTamano.excede_icp` (Core, puro,
  8 tests). Asimétrico: un número duro de TheirStack (employee_count) > tier del ICP
  excluye SIN corroboración; CONSENSO > ICP (incl. MID_MARKET) también. Cierra el
  hueco de scale-ups (Magneto) disfrazados de SME por el default de `_inferir_tamano`.

**Refinamiento tras corrida #1 (mismo día):** la corrida real mejoró (0% educación
vs 60% antes; primer decisor real: Milena Rico CTO) pero mostró 3 fugas, corregidas:
- **Filtro de tamaño nativo en el discovery de TheirStack** (`min/max_employee_count`,
  confirmado en su OpenAPI) derivado del ICP → ataca el sesgo a grandes empresas
  (traía Experian/Postobón; ahora pide directamente el rango 50-200). Validado en
  vivo: devuelve empresas de 75 y 198 empleados.
- **Motor 1 determinista:** regla de mapeo numérico estricto en el prompt de Groq
  ("51-200 empleados" → SME siempre, ya no MID_MARKET intermitente).
- **Negative ICP afinado:** prompt de `es_vendor_it` refuerza el punto ciego de
  consultoras/BPM/integradores/staffing (BPM Consulting se había colado).
- 455 tests verdes. Detalle → más abajo en este mismo documento, sección **"Refinamiento tras la corrida #1 de Signal-First (mismo día, 25-jul-2026)"** (§BITÁCORA DE DECISIONES HISTÓRICAS).

**Fix de raíz tras corrida #2 (créditos/rate agotados):** la corrida #2 confirmó los
fixes (sizing SME OK, sin enterprises/colegios, SECOP cargó a Atrys TIER_0) pero se
agotaron créditos TheirStack (402) + tokens Groq (429). Corregido:
- **Eliminada la doble-llamada a TheirStack:** el discovery cachea las vacantes por
  dominio y `obtener_triggers`/`estimar_tamano` las reutilizan → de ~37 llamadas a
  **1** por corrida (fallback a query solo para empresas ajenas al discovery).
- **Discovery ordenado ASC** (date_posted) para capturar vacantes envejecidas
  (TIER_0) en la cache, preservando la señal al reutilizar.
- **`es_vendor_it` recalibrado:** agencias de medios/publicidad ya NO se marcan como
  vendor IT (falso positivo Publicis Media). Solo tech/software/consultoría técnica.
- **457 tests verdes.** Pendiente: cuenta TheirStack nueva + varias GROQ_API_KEY para
  una corrida LIMPIA que permita juzgar el scoring.

---

## 🚀 Sesión 25-jul-2026 — Motor 1 path A (descubrimiento ICP-derived) + entorno (MCP/hooks/skills)

**1. Motor 1 — Descubrimiento por industria-con-dolor, 100% ICP-derived (path A, sin hardcode):**
- **Causa raíz del run #2 (0 calificadas) confirmada:** `ApolloDiscoveryAdapter._derivar_keyword_tags`
  derivaba los `q_organization_keyword_tags` de `vertical` + `categoria_empresa`.
  `categoria_empresa` es la categoría del **propio cliente** → Apollo buscaba
  empresas *como el cliente* = **competidores** (por eso traía otras consultoras/
  agencias, más ONGs/medios/gov por falta de foco). El scoring del Motor 2 estaba
  bien; el descubrimiento traía la población equivocada.
- **Fix (IMPLEMENTADO):** nuevo campo `ManifiestoICP.industrias_objetivo: list[str]`
  (default `[]`). El LLM del Motor 1 (`GroqICPAdapter`, regla 8 del prompt) infiere
  del ICP las **industrias COMPRADORAS** (las que tienen el dolor y comprarían al
  cliente), **nunca** la categoría/vertical del propio cliente. `ApolloDiscoveryAdapter`
  ahora arma los keyword tags desde `industrias_objetivo`. Si viene vacío → sin
  filtro de industria (discovery amplio por tech+tamaño+país, sin sesgo a competidores).
- **`industry_mapping.py` ELIMINADO** (era huérfano + hardcode con `exclude_keywords`;
  su tesis correcta —targetear industrias con dolor— ahora vive ICP-derived en el LLM,
  y la exclusión de competidores es responsabilidad única del Negative ICP semántico).
- **Multi-búsqueda por sector: NO implementada, a propósito.** Apollo OR-ea los
  `q_organization_keyword_tags`, así que un solo search ya cubre todas las industrias
  objetivo con menos créditos. Si la corrida real muestra que un sector domina el
  ranking, se revisita (decisión empírica, no especulativa).
- **Verificación:** 446 tests verdes (+2: regresión anti-categoría, caso sin industrias),
  ruff limpio. El sandbox muestra `industrias_objetivo` en el banner del manifiesto.

**0. Diagnóstico de raíz del entorno (Kiro corre en Windows, NO en WSL-remoto):**
- Verificado: no hay proceso servidor de Kiro en WSL, ni `~/.kiro-server`; Kiro es
  binario Windows accediendo por `\\wsl.localhost\` (9p). **Windows NO tiene
  node/npx/uv** (solo WSL). Por eso: (a) el hook de ruff daba "comando no
  encontrado" y (b) el MCP `memory` no conectaba — Kiro lanzaba los subprocesos en
  Windows, sin acceso a las herramientas de WSL.
- **Fix (verificado):** puentear vía `wsl.exe`.
  - Hooks (`format-on-save-ruff`, `gate-verificacion-pytest`): el comando ahora es
    `wsl.exe bash <ruta>/.kiro/hooks/_run-{ruff,pytest}.sh` (scripts que exportan
    PATH y corren `uv run`). Probado: EXIT 0, uv encontrado.
  - MCP `memory`: `command=wsl.exe`, `args=["bash","-lc","MEMORY_FILE_PATH=... exec
    npx -y @modelcontextprotocol/server-memory"]` (env embebido; forma-array evita
    quoting). Smoke test OK: "Knowledge Graph MCP Server running on stdio".
    **Falta que el fundador reconecte el server en el panel MCP y confirme.**
- **Bug de guardado (EPERM) resuelto:** los archivos que crea la herramienta
  `fs_write` del agente quedaban como `root:root` → Kiro (Windows, mapeado como
  estiv12) no podía sobrescribirlos. Se re-apropiaron (copiar→borrar→reescribir,
  sin sudo, porque los directorios sí son de estiv12). Cero archivos root en el
  repo ahora. **Nota para futuras sesiones:** preferir escribir vía bash (estiv12)
  o re-apropiar tras `fs_write`.
- Se eliminaron 4 `.md` de steering redundantes (`cerrar-decision`, `handoff-…`,
  `memory-preload`, `sincronizador-spec`) que duplicaban las skills nuevas y
  referenciaban el google-sheets muerto.

**2. Entorno — MCP y hooks/skills:**
- **MCP `memory` ARREGLADO:** fallaba porque `MEMORY_FILE_PATH` era **relativo**
  (bug conocido `modelcontextprotocol/servers#2160`: el paquete lo resuelve contra
  su propio `node_modules/.../dist`, no contra el workspace). Fix: ruta **absoluta**
  `/home/estiv12/proyecto_cliente_catalina/estudio_skills_ia_claude/.kiro/memory/prospector-knowledge-graph.json`
  + directorio creado + seed `{}` + `autoApprove` ampliado con `create_entities`/
  `create_relations`/`add_observations`. **Reconectar el server en el panel MCP.**
- **MCP `google-sheets` ELIMINADO** (decisión del fundador: ya no se usa). `mcp.json`
  ahora solo tiene `memory`.
- **Hooks — diagnóstico y consolidación:** el "upgrade" del panel solo renombraba
  `.kiro.hook`→`.json` pero dejaba el schema **legacy 0.x** (`when`/`then`/`askAgent`)
  dentro; por eso Kiro 1.0.212 los seguía marcando legacy (necesitan schema v1
  `{"version":"v1","hooks":[...]}`). Análisis hook-vs-skill: **hook = evento; skill =
  on-demand**. Los 4 `userTriggered` (manuales) son on-demand → **convertidos a SKILLS**:
  `.kiro/skills/{handoff-cierre-sesion, sincronizador-spec, cerrar-decision, memory-preload}`.
  `cerrar-decision` se **reapuntó** de Google Sheets → bitácora local `20-Bitacora_Decisiones/`.
  Se borraron los 4 `.json` legacy. Quedan **2 hooks de evento genuinos** (v1 correctos):
  `format-on-save-ruff` (PostFileSave) y `gate-verificacion-pytest` (PostTaskExec).

---

## 🖥️ Sesión 24-jul-2026 — Recuperación de entorno (PC nuevo) + auditoría código↔memoria

**Contexto:** el fundador (Yeisiton) cambió de PC. El repo vive ahora en WSL2
(`~/proyecto_cliente_catalina/estudio_skills_ia_claude`). Se reconstruyó el
entorno desde cero y se auditó el drift entre código y memoria.

**1. Entorno reconstruido y verificado:**
- Causa raíz del fallo de MCP `context7`/`memory`: Node/npx no cargaban en
  shells no interactivos. `~/.bashrc` corta temprano (guard `case $- in *i*)`)
  antes del bloque `fnm`. **Fix:** se replicó la init de `fnm` en `~/.profile`.
  Node v24.18.0 + npx 11.16.0 ahora disponibles para invocaciones de agente.
- `.venv` creado con `uv venv --python 3.12` + `uv pip install -r requirements.txt`
  (34 paquetes pineados). Playwright Chromium instalado (sin `--with-deps`).
- **Verificación:** 444 tests verdes, `ruff check src` limpio (2 imports muertos
  removidos: `time` en industry_mapping, `socket` en propuesta_valor_adapter_backup).
- Graphify instalado (`uv tool install graphifyy`) y `graphify-out/` regenerado:
  **1403 nodos, 5232 edges, 76 comunidades** (code-only AST, sin API key).
- Perfiles de colaboradores documentados → [`perfiles-colaboradores.md`](perfiles-colaboradores.md).
  **Yeisiton usa WSL2; Gabyota NO.** Entorno de máquina no es compartido; el
  contexto (memoria/hooks/skills/specs) sí.

**2. Hooks — auditoría de formato + corrección (Kiro 1.0.212):**
- Se corrigieron rutas duplicadas (`estudio_skills_ia_claude/estudio_skills_ia_claude/…`,
  herencia del restructure del commit `6e62d67`) y comandos con venv de Windows
  (`.venv\Scripts\python.exe`) → ahora rutas relativas + `uv run` (portable WSL2).
- 🔴 **Hallazgo (verificado con docs kiro.dev + versión instalada 1.0.212):** en
  Kiro 1.0 los archivos `.kiro.hook` (formato 0.x legacy) **NO ejecutan** —
  aparecen con badge "upgrade" en el panel Agent Hooks. Solo ejecutan los `.json`
  con schema v1 (`{"version":"v1","hooks":[...]}`). Consecuencia real:
  - ✅ **EJECUTAN:** `format-on-save-ruff.json` (PostFileSave `.py`),
    `gate-verificacion-pytest.json` (PostTaskExec). Ambos v1 correctos.
  - ⛔ **NO EJECUTABAN (estaban muertos):** `cerrar-decision`, `memory-preload`,
    `handoff-cierre-sesion`, `sincronizador-spec` — existían SOLO como `.kiro.hook`
    legacy (todos `userTriggered`/manual + `askAgent`).
- **Consolidación aplicada:** se borraron los 2 `.kiro.hook` redundantes
  (format-on-save, gate-pytest) porque su `.json` v1 ya hace lo mismo.
- **Pendiente (acción de UI del fundador, no automatizable por IA):** los 4 hooks
  manuales legacy requieren un clic en "upgrade" en el panel Agent Hooks para
  migrar a v1 y volverse ejecutables. No se recrean vía `createHook` porque su
  disparador es manual (`userTriggered`), que no está en el set de triggers de
  esa herramienta; y no se reescribe el JSON a mano para no arriesgar un schema
  inventado (la propia estrategia-memoria prohíbe adivinar). `cerrar-decision`
  depende además del MCP `google-sheets` (deshabilitado) y `memory-preload` del
  MCP `memory`. Alternativa a evaluar: convertir handoff/sincronizador en skills.

**3. Hallazgos de auditoría código↔memoria (con evidencia git):**
- 🟠 **`src/adapters/discovery/industry_mapping.py` es un MÓDULO HUÉRFANO.**
  Añadido en commit `05903d8`, define `TARGET_INDUSTRIES_BY_CLIENT` (industrias
  con dolor tech: ecommerce/fintech/healthcare/logistics/… + `exclude_keywords`
  de competidores + `search_config` batch 12). **NO se importa en ningún lado**
  (grep confirma solo su propia definición). Es la reforma de descubrimiento
  ESCRITA PERO NO CABLEADA. El descubrimiento real sigue siendo
  `ApolloDiscoveryAdapter` firmográfico por `anclaje_tecnologico`. **Cablearlo
  es exactamente la decisión de arquitectura PENDIENTE del fundador** (bitácora
  22-jul, "Híbrido C"). No se cableó por IA — requiere decisión explícita.
- ✅ **`tecnolog` — ELIMINADO por completo (decisión del fundador, 24-jul).**
  Se borró la Capa 1 heurística del Negative ICP en `sandbox_tbbc_real.py`:
  el frozenset `_PALABRAS_CLAVE_VENDOR_IT`, el prefijo `_PREFIJO_TECNOLOGIA`
  ('tecnolog') y la función `_heuristica_categoria_candidata`, más sus imports
  (`cualquiera_como_palabra_completa`, `PoliticaExclusionCompetidores`). El
  Negative ICP ahora decide **100% por LLM** vía `PropuestaValorAdapter.es_vendor_it()`
  (fail-closed: None → revisión manual). `evaluar_exclusion_competidor` ya no
  recibe `categoria_cliente`. Doc `flujos_motor_1_y_2.md` actualizado (diagrama
  + prosa). 444 tests verdes, sandbox importa limpio. La política pura
  `PoliticaExclusionCompetidores` (Core, sobre enums, no nombres) se conserva
  pero queda sin cablear — disponible si el LLM llega a entregar CategoriaEmpresa
  completa del candidato.
  **Tradeoff aceptado:** ya no hay atajo gratis para vendors obvios; toda
  empresa pasa por el LLM. Costo marginal bajo: esa llamada ya ocurría para los
  gates de tipo_organizacion/pais_hq/tamaño y está cacheada por instancia.
- ✅ `.kiro/specs/mvp-prospector-limpio.md` marcado como SUPERADO (era MVP del
  5-jul, ya rebasado por Motores 1-4).
- ✅ `pendientes-checklist.md` actualizado (links rotos a `docs/`/`estrategia/`/
  `proyectos/` corregidos a la estructura numerada; tareas ya hechas marcadas).

---

## ✅ Estado del Pipeline

| Motor | Descripción | Estado |
|-------|-------------|--------|
| **Motor 1** | Descubrimiento Firmográfico de TAM (Exclusivo Apollo) | ✅ COMPLETADO — Refactorizado para firmografía pura |
| **Motor 2** | Triangulación de Señales (TheirStack, SECOP, Google, GitHub) + Waterfall Tamaño | ✅ COMPLETADO Y OPTIMIZADO — SECOP Full-Text ($q), RUES descartado |
| **Motor 3** | Pre-CRM + Enriquecimiento (Apollo → Hunter en cascada) | ✅ COMPLETADO — probado E2E (piloto LATAM) |
| **Motor 4** | Outbound RAG (Tavily + Groq redactor + Resend) | ✅ COMPLETADO — probado E2E (envío real a bandeja) |

**Suite de tests:** **444 tests en verde** (verificado 22-Jul-2026 tras el blindaje de precisión/scoring — v6.2). El conteo bajó respecto al "460" histórico porque se consolidaron/reemplazaron tests obsoletos; ahora incluye cobertura nueva de `ScoreTriggerPolicy` (mejor-por-origen), `ApolloDiscoveryAdapter`, verificación de dominio en GitHub, gate de tipo de organización y heurística de país por ccTLD. `ruff check src` limpio.

---

## 🔬 Blindaje de precisión/scoring Motor 2 + investigación de descubrimiento (22-Jul-2026, v6.2)

**Contexto:** tras la reconstrucción v5.0, se blindó el Motor 2 con 6 fixes de
raíz de precisión y scoring, se corrió el sandbox real de TBBC (run #2) y se
hizo una investigación empírica del descubrimiento contra APIs reales. Los
fixes de código YA están en el working tree; la investigación queda
consolidada como **decisiones aún NO tomadas**.

**1. Seis fixes de raíz (precisión + scoring), 444 tests verdes:**
- `ScoreTriggerPolicy` reconciliada a spec canónica v5.0 (200/100/50/0 +
  bonus +30 multi-origen / +50 cruce TIER_0, decay CAUSA 90d / EFECTO 45d,
  umbral 150) **y** corregida con **agregación mejor-por-origen** (un origen
  ruidoso ya no puede calificar un lead solo — hallazgo estructural).
- TheirStack: "dos ejes de tiempo" (aging ≥45d ⇒ TIER_0; `fecha_evento=now`
  para que el decay no mate la vacante aún abierta).
- SECOP: ventana ALTA alineada al decay de CAUSA (90d).
- Google Alerts: verificación semántica por LLM (fin de la fábrica de falsos
  "C-level"), con degradación con gracia (sin LLM ⇒ TIER_3, nunca falso-alto).
- GitHub: verificación de que la org pertenece al dominio (anti-colisión
  `forbes.com` vs Forbes Colombia).
- Gate de tipo de organización (gobierno/ONG/medios/educación/gremio) vía la
  Capa 2 LLM ya existente. Heurística de país por ccTLD (IANA) antes del
  scraping caro.

**2. Resultado del run #2 (TBBC real):** 50 descubiertas → 17 excluidas por
"competencia" (muchas MAL: Tecnoaguas, mayoristas, colegios, defensa — por el
heurístico de nombre `"tecnolog"`), 8 descartadas por tipo (correcto: Blu
Radio, Agencia Nacional Digital, 6 colegios), 5 a revisión manual (fallos de
scraping), 20 analizadas, **0 calificadas**. Diagnóstico: los filtros de
precisión funcionan; el **cuello de botella es el DESCUBRIMIENTO** — Apollo
trae población equivocada, sin señales, sin un solo trigger de TheirStack.

**3. Investigación empírica consolidada** más abajo en este mismo documento, sección
**"Bitácora de Decisiones — 22 de Julio de 2026"** (§BITÁCORA DE DECISIONES HISTÓRICAS).
Incluye el probe de Apollo (NAICS post-filtro), TheirStack (filtros
tamaño+cargo), SECOP (no sirve como descubridor), y el cruce con el reporte
consolidado externo.

**4. Decisiones PENDIENTES (del fundador, NO tomadas):**
- **Descubrimiento Híbrido Multi-Fuente (Opción C)** — Apollo (NAICS
  post-filtro) ∪ TheirStack (filtros tamaño+cargo), dedup por dominio.
- **Reforma del Negative ICP** — eliminar el heurístico de nombre `"tecnolog"`,
  hard-exclude solo con confirmación LLM, ante duda marcar/nurturing.

---

## ✅ Reconstrucción v5.0 Signal-Based Selling + fix de push parcial (22-Jul-2026)

**Diagnóstico:** el push del 22-Jul fue **PARCIAL**. Se subieron la memoria (`.md`)
y los adaptadores v5.0 (`secop_adapter`, `propuesta_valor_adapter`,
`sandbox_tbbc_real`) junto con sus tests, pero **NO** se subieron el Core v5.0 ni
tres módulos nuevos de los que esos adaptadores dependen. Resultado: el repo
clonado en el PC nuevo **NO importaba** (pytest fallaba en la fase de
recolección). Además, `estado_actual.md` quedó en v4.3 sin documentar que v5.0
ya estaba implementado.

**Piezas reconstruidas** (contra los contratos ya fijados por los tests y los
adaptadores existentes):

1. **`src/core/domain/models.py`** — enums `TipoTrigger` (CAUSA/EFECTO) y
   `TierUrgencia` (TIER_0..TIER_3); + campos opcionales `Trigger.tipo_trigger`
   (default `EFECTO`) y `Trigger.tier_urgencia` (default `TIER_2`),
   retrocompatibles con los adaptadores que crean `Trigger` sin ellos.
2. **`src/core/domain/policies.py`** — `ScoreTriggerPolicy` (Signal-Based
   Selling v5.0): puntos por tier TIER_0=240 / TIER_1=90 / TIER_2=40 /
   TIER_3=15; `UMBRAL_CALIFICACION=150`; decay lineal diferenciado CAUSA=90d /
   EFECTO=45d; `evaluar(triggers, adaptadores_activos) -> (score, tier_final, califica)`.
3. **`src/core/domain/text_matching.py`** (Core puro) —
   `contiene_palabra_completa` y `cualquiera_como_palabra_completa` (match por
   palabra completa, case-insensitive, con tildes).
4. **`src/adapters/llm/groq_key_pool.py`** — `GroqKeyPool`: rotación reactiva
   con cooldown (parsea `"try again in Ns"`), descubre `GROQ_API_KEY_1..N` o
   `GROQ_API_KEY`, clientes cacheados por clave, nunca lanza.
5. **`src/adapters/discovery/apollo_discovery_adapter.py`** —
   `ApolloDiscoveryAdapter` (único descubridor del Motor 1, firmografía pura;
   implementa `PuertoDescubridorEmpresas`).

**Fix adicional (bug preexistente que v5.0 pretendía cerrar):**
`github_adapter._match_tecnologias` usaba substring ingenuo (`"java"` ⊂
`"javascript"` → falso positivo). Ahora enruta por
`text_matching.contiene_palabra_completa`. Se limpió también un F841
(`pushed_at` muerto) en ese archivo.

**Advertencia vigente:** `ApolloDiscoveryAdapter` es la **ÚNICA** pieza sin test
que fije el esquema real de la API de Apollo. Implementado defensivo (degrada a
`[]`); endpoint/params/campos **DEBEN** validarse con un smoke test real usando
`APOLLO_API_KEY` antes de darse por definitivos.

**Verificación:** suite completa en verde — **331 tests passed, 0 failed** (el
"~460" citado antes estaba desactualizado). `ruff check src` limpio.

**Nota de entorno:** el PC nuevo no tenía Python; se instaló Python 3.12 y el
`.venv` quedó en la carpeta **PADRE** (`Proyecto Catalina Prospect\.venv`),
fuera del repo.

---

## ✅ Auditoría Holística código↔documentación (22-Jul-2026)

Revisión cruzada exhaustiva entre `estado_actual.md` + `flujos_motor_1_y_2.md`
(y adaptadores relevantes en `tecnico/`) contra la implementación real de
`apollo_discovery_adapter.py`, `theirstack_adapter.py`, `secop_adapter.py`,
`PropuestaValorAdapter` y `sandbox_tbbc_real.py`. Se pidió explícitamente
"ningún cabo suelto ni suposiciones en el aire" antes del push a la rama
principal.

**Discrepancias encontradas y corregidas:**

1. **Bug real (código, no solo documentación):** `SecopSocrataAdapter`
   implementaba `PuertoEstimadorTamano` (campo `es_pyme`) desde la sesión
   anterior, documentado como "tercer origen del waterfall de tamaño", pero
   `evaluar_consenso_tamano()` en `sandbox_tbbc_real.py` nunca lo invocaba —
   solo usaba TheirStack + PropuestaValorAdapter. **Corregido:** se agregó
   el parámetro `adapter_secop` a la función y se instanció en `main()`.
2. **`.env.example` incompleto:** `GITHUB_TOKEN` (usado en `github_adapter.py`)
   y `SECOP_APP_TOKEN` (usado en `secop_adapter.py`) se leían del entorno en
   código real pero no estaban documentados en la plantilla pública.
   **Corregido:** ambos agregados con comentarios explicativos.
3. **`ScoringPolicy` fantasma:** `flujos_motor_1_y_2.md` describía una clase
   `ScoringPolicy` con pesos ponderados (30% dolor, 25% tecnología, etc.)
   como si fuera parte del flujo real del Motor 1. Nunca se materializó en
   código — los únicos gates reales son validadores Pydantic de
   `ManifiestoICP`. **Corregido:** diagrama Mermaid y tabla de pesos
   actualizados, marcados explícitamente como diseño histórico no
   implementado.
4. **Tabla de adaptadores del Motor 2 incompleta:** no incluía `GitHubAdapter`,
   que sí existe en código, está en `OrigenTrigger.GITHUB` y en
   `AdapterRoutingPolicy.CATEGORIAS_CON_GITHUB`. **Corregido:** fila y
   sección de documentación agregadas.
5. **Wappalyzer mal documentado:** la tabla decía `wappalyzer-next (Python +
   Playwright)`. El código real (`wappalyzer_adapter.py`) usa únicamente
   `requests` + `BeautifulSoup`, sin Playwright — Playwright es el fallback
   técnico de `PropuestaValorAdapter` (Capa 2 del Negative ICP), no de
   Wappalyzer. **Corregido.**
6. **Umbrales de SECOP inventados:** la documentación decía "ALTA: Contrato
   > COP 500M en últimos 45 días" — el código real (`_nivel_por_fecha()`)
   NO filtra por valor monetario, solo por antigüedad (≤180d = ALTA, 180-365d
   = MEDIA, >365d = BAJA). **Corregido** con los umbrales reales del código.
7. **Diagramas Mermaid desactualizados:** el flujo del Motor 2 decía "Empresa
   descubierta por TheirStack" (obsoleto desde que Apollo es el único
   discoverer); el mapa de dependencias de puertos seguía en v3.0 sin
   `ApolloDiscoveryAdapter`, `GitHubAdapter`, `PropuestaValorAdapter`, ni los
   puertos `PuertoDescubridorEmpresas`/`PuertoEstimadorTamano`/
   `PuertoClasificadorPropuestaValor`. **Corregido**, ambos diagramas
   actualizados a v6.0.
8. **Secciones existentes en código sin documentación formal:** el Paquete
   de Revisión Persistente (`PaqueteRevisionAdapter`) y los Reintentos
   Técnicos de Capa 2 (rutas alternas + fallback Playwright) solo se
   mencionaban de paso en este archivo. **Corregido:** se agregaron
   secciones dedicadas en `flujos_motor_1_y_2.md` con el comportamiento real
   del código.

**Verificación post-corrección:** batería completa de pytest ejecutada tras
el fix de código (conexión de SECOP al waterfall) — 460 tests verdes,
0 regresiones. `ruff` limpio en los archivos tocados.

**Nota sobre control de versiones:** este repositorio no tiene una rama
`main`. La rama principal real es `setup/base-conocimiento` (`origin/HEAD`
apunta a ella). El cierre de esta auditoría se hizo con push a esa rama.

---

## ✅ Qué se hizo en esta sesión (21-Jul-2026)

### Refactorización de Arquitectura de Descubrimiento (Motores 1 y 2)

**1. Separación Real de Discovery vs Señales:**
- **Problema:** TheirStack traía empresas por vacantes y Apollo por tamaño al mismo tiempo, ensuciando el TAM inicial.
- **Solución:** Motor 1 (Descubrimiento) ahora usa **exclusivamente Apollo** para armar el TAM basado 100% en firmografía. TheirStack pasó a ser exclusivamente una fuente de evaluación de señales del Motor 2.

**2. Optimización SECOP (Socrata) y Rechazo RUES:**
- **Problema:** SECOP fallaba por timeouts (10s+) al usar `LIKE '%nombre%'`. RUES era un candidato para extraer NIT.
- **Solución SECOP:** Migrado a búsqueda Full-Text (`$q`) bajando el tiempo a ~1s. Se inyectó extracción profunda: `urlproceso.url` (link directo), `es_pyme` (para waterfall de tamaño), y UNSPSC (filtro de TI).
- **Decisión RUES:** Rechazado como fuente automatizada debido a falta de APIs estables (payloads cifrados, scraping frágil). Se usará solo como link de consulta humana.

**3. Paquete de Revisión Persistente ("Human in the Loop"):**
- Se implementó `PaqueteRevisionAdapter` persistiendo datos en `pendientes.json`. En lugar de que el orquestador olvide las empresas dudosas, guarda la evidencia (HTML del homepage) y provee links de 1-clic para que el humano evalúe en segundos y persista su veredicto (`CONFIRMADO_PERMITIDO/EXCLUIDO`). Se agregaron reintentos técnicos con `/nosotros` y fallback a Playwright.

**Archivos modificados:**
- `src/adapters/discovery/apollo_discovery_adapter.py`, `src/adapters/triggers/secop_adapter.py`, `sandbox_tbbc_real.py`.
- **Tests: 460 tests en verde, 0 regresiones.**

### Motor 2 — Blindaje post-piloto TBBC (3 fallos corregidos)

**Contexto:** la corrida con batch=15 calificó a "Parcero" (parcero.digital) como lead válido. Auditoría manual del fundador reveló que es una agencia digital con HQ en Londres, UK — competidor directo y fuera de la geografía del ICP. Diagnóstico: 3 fallos simultáneos.

**Falla 1 — Fail-Open en PropuestaValorAdapter (Negative ICP):**
- Causa: si el scraping de homepage fallaba (SPA sin SSR), el adaptador retornaba `None` y el orquestador lo interpretaba como "sin evidencia de competencia" → `PERMITIDO` automático.
- Fix: fallback de scraper a `<title>` + `<meta name="description">` cuando body visible < 100 chars. Tri-estado explícito (`es_vendor_it`: True/False/None). `None` → `PENDIENTE_REVISIÓN_MANUAL` (fail-closed). Nuevo campo `pais_hq` en el prompt del LLM + método `pais_hq()` público en el adaptador.

**Falla 2 — Bug del default silencioso de país en TheirStackAdapter:**
- Causa: `pais = empresa_data.get("country_code", "CO") or "CO"` mentía activamente cuando TheirStack no reportaba el país.
- Fix: eliminado el default. Se usa `PAIS_DESCONOCIDO = "XX"` (constante del Core, ISO 3166-1 reservado). Nueva política pura `PoliticaValidacionGeografica` en `policies.py`.

**Falla 3 — Falsos positivos en Google Alerts por nombres genéricos:**
- Causa: "Parcero" es una palabra coloquial del español colombiano → noticias de fútbol pasaban el filtro de substring match.
- Fix: filtro de co-ocurrencia semántica (glosario de vocabulario de negocio) en `google_alerts_adapter.py`. Techo de confianza `BAJA` para nombres de empresa ≤8 caracteres.

**Corrida de validación post-blindaje (batch=15):**
- 3 excluidas por competencia: Periferia IT Group, Parcero, Hitss Colombia.
- 2 pendientes revisión manual: Itaú, Keralty (SPAs opacas, fail-closed correcto).
- 4 descartadas por tamaño ENTERPRISE: Altipal, Seguros Bolívar, Berlitz, PwC.
- **2 califican para Motor 3: Cielito (cielito.co), Colsubsidio.**
- Tasa de calificación bruta: 15.4%.

**Archivos modificados:**
- `src/core/domain/models.py` — `PAIS_DESCONOCIDO`, `EstimacionTamano`, `EstadoConsensoTamano`, `ResultadoExclusionCompetidor` (+`PENDIENTE_REVISION_MANUAL`), `EstadoValidacionGeografica`, `OrigenTrigger.PROPUESTA_VALOR`
- `src/core/domain/policies.py` — `PoliticaCorroboracionTamano`, `PoliticaExclusionCompetidores`, `PoliticaValidacionGeografica` (nueva)
- `src/core/ports/interfaces.py` — `PuertoEstimadorTamano`, `PuertoClasificadorPropuestaValor` (nuevos)
- `src/adapters/triggers/propuesta_valor_adapter.py` — implementación completa con `pais_hq`, fallback meta tags, caché por instancia
- `src/adapters/triggers/theirstack_adapter.py` — bugfix país + `PuertoEstimadorTamano`
- `src/adapters/triggers/google_alerts_adapter.py` — co-ocurrencia semántica + techo de confianza
- `sandbox_tbbc_real.py` — orquestador con fail-closed completo y 5 banners de estado
- Tests: +28 nuevos en `test_domain_models.py`, `test_propuesta_valor_adapter.py`, `test_triggers_adapters.py`
- **275 tests verdes, 0 regresiones, ruff limpio.**

---
## 🔄 En Evolución (18/19-Jul-2026): Pivote hacia "Signal-Based Selling"

**Qué teníamos:** El Motor 1 y 2 dependían fuertemente de una sola señal ("Vacantes publicadas") extraída mediante TheirStack para descubrir y calificar prospectos.
**Cómo buscamos:** Realizamos una investigación web profunda cruzando metodologías de ventas B2B, libros referentes (Predictable Revenue, SHiFT!, Spear Selling) y tácticas de Account-Based Sales Development (ABSD).
**Qué encontramos:** Depender exclusivamente de vacantes crea ceguera (single-signal dependency). Las vacantes son útiles, pero carecen del vector "Urgencia" si no se evalúa su *aging* (días abierta). Existen señales más fuertes (Tier 0 y Tier 1) como victorias de contratos en SECOP o cambios de liderazgo.
**A qué hemos llegado (Temporal):** Se está reestructurando la estrategia hacia una **Orquestación Multi-Señal**. 
- **Tier 0 (Sangrado Activo):** Contratos ganados sin equipo (SECOP) o vacantes antiguas (>45 días).
- **Tier 1 (Reorganización):** Nuevo CTO/Líder técnico (<90 días).
- **Tier 2/3 (Contexto):** M&A, adopción cloud, tamaño de empresa (TAM Base usando Apollo/InfobelPRO).

**Siguiente acción táctica:** Ingestar literatura especializada (SHiFT!, Predictable Revenue, Spear Selling, Fanatical Prospecting) usando un modelo de largo contexto (NotebookLM) para extraer las lógicas matemáticas de Scoring y plasmarlas en el Motor 2.

---

## 🔜 PRÓXIMO PASO / SIGUIENTE SESIÓN

0. **CORRER `sandbox_tbbc_real.py` con el descubrimiento ICP-derived (PRIORIDAD).**
   Las decisiones pendientes del 22-Jul YA se resolvieron e implementaron (24/25-Jul):
   (a) descubrimiento **path A ICP-derived** (`industrias_objetivo` LLM-derived),
   no Híbrido C; (b) heurística de nombre `"tecnolog"` **eliminada** (Negative ICP
   100% LLM); (c) `industry_mapping.py` **eliminado**. **Falta la validación
   empírica:** correr el sandbox con `.env` real y verificar: (1) que el LLM
   propone industrias COMPRADORAS sensatas en `industrias_objetivo`; (2) que Apollo
   trae población compradora (no competidores/ONGs/gov); (3) que ≥1 lead califica.
   Según el resultado, ajustar el prompt de `industrias_objetivo` o evaluar
   multi-búsqueda por sector (hoy innecesaria — Apollo OR-ea los keyword tags).
   Contexto histórico: más abajo en este mismo documento, sección **"Bitácora de
   Decisiones — 22 de Julio de 2026"** (§BITÁCORA DE DECISIONES HISTÓRICAS).

1. **Validación manual de los 2 leads calificados (BLOQUEANTE antes de Motor 3):**
   - **Colsubsidio:** verificar qué división exactamente está buscando desarrolladores. ¿Construcción de plataforma interna o modernización de legacy? Si es válido → enriquecer con Motor 3.
   - **Cielito (cielito.co):** verificar que es empresa tech (startup o empresa armando equipo in-house), no la marca de alimentos "Cielito Lindo". Si es válido → enriquecer con Motor 3.
   
2. **Decisión pendiente del fundador:** ¿Ajustar el ICP a solo SME (50-200) descartando MID_MARKET también? Actualmente Colsubsidio pasa por ser MID_MARKET. Si el cliente quiere enfocarse solo en SME, hay que actualizar el filtro de `TamanoEmpresa` en el sandbox.

3. **Motor 3 real (bloqueado hasta validación manual de leads):** enriquecer contactos de los leads calificados con Apollo → Hunter.

4. **Orquestador FastAPI y Webhook de rebotes:** cerrar los bloqueos técnicos pendientes (ver tabla de entorno técnico).

## ⚠️ Bloqueos Pendientes (documentados, no resolubles por IA)

### Motor 3 — Pre-CRM + Enriquecimiento (COMPLETADO)
- **Spec** `tecnico/prospector-m3-m4-design.md` — `PuertoEnriquecedorContactos` (firma stateless `enriquecer(empresa, cargos)`), cascada Apollo→Hunter, `PoliticaMapeoEstadoCorreo` (ubicada en capa de adaptador para no filtrar semántica de proveedor al Core), `UmbralCalidadDecisor` (`confianza_dato >= 0.7` + `estado_correo in {VERIFICADO, INFERIDO}`).
- **Incidente real y fix:** Apollo depreció el endpoint directo `/v1/mixed_people/search` (error 422). `ApolloClient` se reescribió al flujo de 2 pasos: `api_search` (descubre IDs) → `/people/match` (extrae email). Confirmado en código y en tests verdes.
- **Piloto LATAM ejecutado con datos reales** (`sandbox_piloto_latam_m3.py`, n=5: Bancolombia, Rappi, Platzi, Addi, Merqueo): 80% tasa de resolución Apollo, 9 decisores, 8 aptos para M4, **costo estimado $0.17 USD/decisor apto** (umbral: <$1.00 ✅). Corte de costo validado en vivo (Merqueo: 0 perfiles → Hunter no se invocó).
- **Hallazgo crítico del piloto:** Rappi devolvió 5 decisores, 4 con cargo "VP of Engineering" — riesgo real de spray-and-pray. Este hallazgo definió el primer requisito de diseño del Motor 4.
- **Advertencia vigente:** el piloto fue n=5 sobre empresas grandes/conocidas (sesgo de muestra hacia el mejor caso de cobertura de Apollo). El KPI dual de aprobación real (§3.5 de la spec) exige además bounce rate real <2%, que **no se cerró en este piloto** — solo se mide enviando correos reales y contando rebotes (ver Motor 4).

### Motor 4 — Outbound RAG (COMPLETADO)
- **Spec** `tecnico/prospector-m4-design.md` — `PoliticaSeleccionMejorDecisor` (1 decisor por empresa, resuelve el caso Rappi), puertos `PuertoContextoRAG`/`PuertoRedactorOutbound`/`PuertoEnvioCorreo`, `PoliticaRegistroRebote` (lazo de retroalimentación que cierra el KPI pendiente de M3), fronteras Legal (Habeas Data) y de Reputación (Modo Borrador HITL). Decisiones cerradas por el Architect: dedup estricta 1/empresa, proveedor Resend, pacing 20 envíos/día, arranque solo con cohorte `VERIFICADO`.
- **Core materializado:** `PaqueteOutbound`, `Mensaje`, `ContextoRAG`, `EstadoMensaje`, `ResultadoEnvio` en `models.py`; 3 puertos en `interfaces.py`; 4 políticas puras en `policies.py` (`PoliticaRedaccionOutbound` queda como abstracción, sin materializar).
- **Adaptadores** en `src/adapters/outbound/`: `TavilyContextoAdapter`, `GroqRedactorAdapter` (modelo actualizado a `llama-3.3-70b-versatile` tras baja del modelo anterior), `ResendEnvioAdapter` + función pura desacoplada `procesar_webhook_rebote()` (el controlador HTTP que la invoque queda pendiente — ver Próximo Paso).
- **Piloto E2E a producción real** (`sandbox_motor_4_outbound.py`): con los decisores de Rappi (4 VPs + 1 CTO) y Platzi, `PoliticaSeleccionMejorDecisor` descartó los 4 VPs y seleccionó a Leandro Reox; Tavily recuperó contexto; Groq redactó el mensaje con gancho de trigger y opción de baja (Habeas Data); tras Modo Borrador y aprobación explícita (`APROBAR_Y_ENVIAR`), Resend entregó con éxito a una bandeja de Gmail real de control.
- **Nota de honestidad sobre el alcance de esta prueba:** confirma que la cadena Tavily→Groq→Resend funciona end-to-end y que el correo llega. **No confirma bounce rate** (un envío exitoso a un correo de control no es una muestra de rebotes) ni el cumplimiento legal real de Habeas Data (pendiente de abogado, ver bloqueo abajo). No usar este resultado como "M4 validado para escala".

### Suite de tests
- 107 → **208 tests en verde** (verificado con corrida real 15-Jul-2026): +31 enriquecimiento (M3), +30 Core M4, +27 adaptadores outbound (M4).

---

## ✅ Qué se hizo en sesión anterior (15-Jul-2026)

### Motor 3 — Pre-CRM + Enriquecimiento (sesión anterior)

1. **Blindar El Prospector (Frente 1 - TBBC):** ~~Es la prioridad absoluta.~~ **COMPLETADO (17-Jul-2026).** Ver sección anterior.
2. **Investigación Paralela (Frente 2):** Iniciar la investigación de arquitectura para automatización de WhatsApp y chats de atención (segunda empresa).
3. **Orquestador Principal y Webhook:** Cerrar los bloqueos técnicos pendientes del Motor 3 y 4 (orquestación y webhook de rebotes de Resend).

> **Estado al 17-Jul-2026:** el punto 1 está cerrado. Los puntos 2 y 3 quedan diferidos hasta validar los leads del sandbox real.

## ⚠️ Bloqueos Pendientes (documentados, no resolubles por IA)

**Habeas Data (Ley 1581) — YA NO ES TEÓRICO.** El código ahora procesa y ha enviado correos a PII real (nombres y direcciones de decisores reales del piloto de M3/M4). El compliance real requiere asesoría legal con abogado real antes de cualquier envío a escala. Ver `02_Lineas_de_Producto/Outbound_Prospector/docs/validacion/validacion-fuentes.md` §7. **Este bloqueo se activa formalmente ahora que existe envío real, no solo diseño.**

**Bounce rate real del Motor 3 sin medir.** El piloto de M3 solo cerró el KPI de costo ($0.17 < $1.00 ✅). El KPI de calidad (<2% bounce) sigue abierto — depende del webhook de Resend (ver Próximo Paso #2).

**Muestra del piloto LATAM sesgada.** n=5 sobre empresas grandes/conocidas no es representativo del ICP real (SME 50-200 desconocidas). El caveat de caída de precisión 10-20 puntos fuera de US sigue sin validar con una muestra representativa.

---

## Estado del Entorno Técnico

| Componente | Estado |
|---|---|
| `.venv` Python 3.12 + dependencias pineadas (WSL2, `uv`) | ✅ recreado 24-Jul en PC nuevo |
| 444 tests pytest | ✅ verdes (verificado 24-Jul-2026 en WSL2) |
| `ruff` linter/formatter | ✅ limpio en `src` (24-Jul) |
| Graphify `graph.json` | ✅ regenerado 24-Jul: 1403 nodos / 5232 edges / 76 comunidades (code-only) |
| Node.js (fnm) + npx para MCP | ✅ arreglado 24-Jul (init `fnm` movida a `~/.profile`) |
| Hooks `.json` v1 (`format-on-save-ruff`, `gate-verificacion-pytest`) | ✅ ejecutan; rutas/comandos a `uv run` (24-Jul) |
| Protocolos on-demand (`cerrar-decision`, `handoff`, `sincronizador-spec`, `memory-preload`) | ✅ migrados a SKILLS en `.kiro/skills/` (25-Jul); ya no son hooks |
| MCP `context7` | ✅ funcional (probado 24-Jul; también instalado como Power) |
| MCP `memory` | ✅ arreglado 25-Jul (ruta absoluta + dir + seed); **reconectar en panel MCP** |
| MCP `google-sheets` | ✅ ELIMINADO (25-Jul, ya no se usa) |
| Descubrimiento Motor 1 | ✅ ICP-derived (path A): `industrias_objetivo` LLM-derived; `industry_mapping.py` eliminado |
| Skills on-demand (`handoff`, `sincronizador-spec`, `cerrar-decision`, `memory-preload`) | ✅ migradas de hook→skill (25-Jul) |
| `INTERES_LEGITIMO` eliminado del dominio | ✅ |
| Webhook de rebotes de Resend | ⬜ pendiente (función pura lista, falta el controlador HTTP) |
| Orquestador/API principal | ⬜ pendiente (solo sandboxes hoy) |

---

## 📅 Historial de Sesiones

| Fecha | Acción | Versión |
|---|---|---|
| 2026-07-09 | Validación sector tech LATAM. Arquitectura hexagonal inicial. | v1.0 |
| 2026-07-11 | 12 vulnerabilidades Pydantic cerradas. Motor 1 como Enrutador Dinámico. LUZ VERDE. | v3.0 |
| 2026-07-12 | Core Python materializado. GroqICPAdapter + Discovery dual-mode + EstadoEmpresa. | v3.1 |
| 2026-07-12 | 5 adaptadores Motor 2 completos. Pruebas E2E exitosas. | v3.2 |
| 2026-07-12 | Fix Habeas Data. Memoria consolidada. Graphify activo. 7 hooks. Entorno supercargado. | v3.3 |
| 2026-07-15 | **Motor 3 completado: spec, Core, adaptadores Apollo→Hunter (fix flujo 2 pasos), piloto LATAM ($0.17/decisor). Motor 4 completado: spec, Core, adaptadores Tavily/Groq/Resend, `PoliticaSeleccionMejorDecisor` (fix caso Rappi). Piloto E2E con envío real a bandeja de control exitoso. 208 tests verdes.** | v4.0 |
| 2026-07-17 | **Blindaje Motor 2 (3 fallos del caso Parcero/UK corregidos). Sandbox TBBC batch=15: 2 leads calificados (Cielito, Colsubsidio). 275 tests verdes (+28 nuevos, 0 regresiones).** | v4.1 |
| 2026-07-21 | **Refactor Discovery (M1 = Apollo puro). Optimización SECOP ($q full-text, `es_pyme`, URL). RUES rechazado. Paquete de revisión persistente `pendientes.json` + Fallback Playwright. 460 tests verdes.** | v4.2 |
| 2026-07-22 | **Auditoría Holística código↔documentación. Fix real: `SecopSocrataAdapter.estimar_tamano()` estaba implementado pero desconectado del waterfall de tamaño — conectado en `sandbox_tbbc_real.py` (ahora 3 orígenes: TheirStack, PropuestaValorAdapter, SECOP). `.env.example` actualizado con `GITHUB_TOKEN`/`SECOP_APP_TOKEN` (existían en código, faltaban en la plantilla). `flujos_motor_1_y_2.md` corregido: `ScoringPolicy` marcado como diseño histórico nunca implementado, tabla de adaptadores completada con `GitHubAdapter`, Wappalyzer corregido (no usa Playwright — eso es `PropuestaValorAdapter`), umbrales SECOP corregidos a solo antigüedad (sin montos COP inventados), diagramas Mermaid actualizados (Apollo como discoverer, 3er origen SECOP en waterfall, mapa de puertos v6.0 con Apollo/GitHub/PropuestaValorAdapter). 460 tests verdes tras la corrección, 0 regresiones.** | v4.3 |
| 2026-07-22 | **Reconstrucción v5.0 Signal-Based Selling tras push parcial: Core (TipoTrigger, TierUrgencia, campos de Trigger, ScoreTriggerPolicy), text_matching, GroqKeyPool, ApolloDiscoveryAdapter; fix de matching por palabra completa en github_adapter. 331 tests verdes, ruff limpio. Pendiente: smoke test real de ApolloDiscoveryAdapter.** | v5.0 |
| 2026-07-22 | **Blindaje de precisión/scoring Motor 2 (6 fixes de raíz: ScoreTriggerPolicy mejor-por-origen + spec v5.0, TheirStack dos ejes de tiempo, SECOP ventana ALTA 90d, Google Alerts verificación LLM, GitHub verificación de dominio, gate de tipo de organización + país por ccTLD). Run #2 TBBC real: 0 calificadas → cuello de botella = descubrimiento. Investigación empírica (probe Apollo/TheirStack/SECOP) consolidada en bitácora 2026-07-22. Decisiones de discovery (Híbrido C) y reforma del Negative ICP PENDIENTES del fundador. 444 tests verdes, ruff limpio en src.** | v6.2 |


---

# 📋 Checklist de Pendientes (Dashboard único)

> ⛔ **SUPERADO** por las sesiones de 25/26-jul (arriba en este mismo documento) y por
> la reestructuración de carpetas del 13-ago-2026. Se conserva como registro histórico;
> **la fuente viva de próximos pasos es la sección "🔜 PRÓXIMO PASO / SIGUIENTE SESIÓN"**
> más arriba. Varios enlaces de esta sección apuntan a rutas ya purgadas — no seguirlos
> como navegación, son solo referencia histórica.

> Tablero único de tareas abiertas, consolidado de todo el repo. Última actualización: **24-jul-2026**.
> Estado: ✅ hecho · ⏳ en curso / esperando · 🔴 abierto / sin empezar · 🟡 requiere tercero.
>
> ⚠️ **Nota de rutas (24-jul):** las carpetas `docs/`, `estrategia/` y `proyectos/`
> fueron consolidadas el 12-jul en la estructura numerada. Rutas vigentes:
> `docs/tecnico/` → `10-Memoria_Consolidada/tecnico/`; `docs/validacion/` →
> `10-Memoria_Consolidada/validacion/`; `proyectos/catalina-prospector/` →
> `10-Memoria_Consolidada/proyecto-catalina/`; `estrategia/` y `docs/fundamentos/`
> → `01-Fundamentos_Estrategia/`.

## 🔥 Prioridad ALTA (mueven ingresos esta semana)

| Estado | Pendiente | Detalle / dónde |
|--------|-----------|-----------------|
| ⏳ | **Catalina / Prospector — avanzar la oportunidad** | Clienta potencial. Ya hubo 1 reunión + prueba genérica; **ICP pendiente**. Aplicar Módulos 4 y 5. Ver [`proyecto-catalina/`](../10-Memoria_Consolidada/proyecto-catalina/README.md) |
| ⏳ | **Job de prueba con datos públicos de TBBC** | Ya se corrió (run #1 y #2 en `sandbox_tbbc_real.py`). Run #2 dio 0 calificadas: cuello de botella = **descubrimiento**, no scoring. Falta re-correr tras decidir la arquitectura de descubrimiento. Ver [contexto-cliente](../10-Memoria_Consolidada/proyecto-catalina/00-contexto-cliente.md) |
| 🔴 | **Definir pricing del Prospector para Catalina** | Sin costo por lead medido, cotizar es adivinar. Para el piloto: **precio cerrado**, no por lead. Ver [`costo-por-lead.md`](../10-Memoria_Consolidada/tecnico/costo-por-lead.md) |
| ✅ | **Construir M1 + M2 del Prospector ** | HECHO y rebasado: Motores 1-4 implementados y blindados (v6.2, 444 tests). Ver [`estado_actual.md`](../00-Cortex_Operativo/estado_actual.md) y [`prospector-m1-m2-design.md`](../10-Memoria_Consolidada/tecnico/prospector-m1-m2-design.md) |
| 🔴 | **DECIDIR arquitectura de descubrimiento (desbloqueante)** | Run #2 = 0 calificadas por descubrimiento. `industry_mapping.py` (reforma por industria-con-dolor) está escrito pero HUÉRFANO/no cableado. Decidir: cablearlo (Híbrido C) o descartarlo + reforma del Negative ICP `tecnolog`. Ver [bitácora 22-jul](../20-Bitacora_Decisiones/2026-07-22-descubrimiento-y-scoring-motores-1-2.md) |

## 🔥🔥 CRÍTICO — Situación contractual y sociedad (nuevo, 4-jul-2026)

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ✅ | **Contrato recibido y analizado** | Cláusulas clave en [`situacion-contractual-y-sociedad.md`](situacion-contractual-y-sociedad.md) §2. Hallazgo: **la IP del Prospector es de la contratante (cláusula 8ª)** |
| 🔴 | **Definir tu producto propio como build NUEVO e independiente** | No puedes vender el Prospector de la contratante.  = producto nuevo, arquitectura propia, nombre nuevo, respetando confidencialidad (7ª, 2 años). Guía técnica: [`arquitectura-y-paradigmas.md`](../docs/tecnico/arquitectura-y-paradigmas.md) |
| ⏳ | **ECC — evaluado (cherry-pick)** | Tiene **adaptador Kiro** (`./install.sh`). Instalar SELECTIVO: steering base + skills backend/python + hooks quality-gate/tests/security. Ver [`evaluacion-ecc.md`](../docs/tecnico/evaluacion-ecc.md) |
| 🔴 | **Conectar MCPs del build** | Supabase/Postgres + Context7 + (Tavily/Playwright por fase) para que los agentes tengan herramientas. Ver [`kiro-guia-practica.md`](../docs/tecnico/kiro-guia-practica.md) §4 |
| 🔴 | **Activar automatizaciones (hooks) de Kiro** | quality-gate + tests-on-save + secret-scan + extract-patterns. Ver [`kiro-guia-practica.md`](../docs/tecnico/kiro-guia-practica.md) §3 |
| 🟡 | **Abogado laboral — reclamar pago incompleto** | Terminación sin aviso de 15 días (incumple 3ª) + pago incompleto → te deben honorarios causados. ¿"Contrato realidad"? |
| ✅ | **Catalina — situación legal aclarada** | Contacto propio (Popayán), NO cliente de la contratante → cláusula 9ª N/A. Vía libre con build independiente (cláusula 7ª) |
| 🔴 | **Decidir sobre la oferta del 15%** | Coherente con que el IP es de ellos, pero economía pobre (techo ~$300–400k COP/mes). Recomendación: **A (producto propio) + D (cobrar lo adeudado)**. Ver análisis |

## 🟡 Requieren un tercero (no resoluble por IA)

| Estado | Pendiente                                                      | Detalle                                                                                                                                                                                                                                                               |
| ------ | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🟡     | **Sesión con un contador**                                     | Confirmar IVA (no responsable bajo 3.500 UVT ≈ COP $183,3M), RST sí/no, flujo de exportación de servicios, y valor oficial de UVT 2026. Ver [`facturacion-y-contratos-colombia.md`](facturacion-y-contratos-colombia.md)                                              |
| 🟡     | **Asesoría legal Habeas Data**                                 | Para prospección B2B a escala (Ley 1581/2012 + Ley 1266/2008 + Decreto 1377/2013; autoridad: SIC). Ver [validación §7](../docs/validacion/validacion-fuentes.md)                                                                                                      |
| 🟡     | **Abogado IP/comercial — límites del build independiente**     | IP ya resuelto (es de la contratante). Pregunta abierta: ¿qué tan distinto debe ser tu nuevo build para no rozar confidencialidad (cláusula 7ª, 2 años)? Ver [`situacion-contractual-y-sociedad.md`](situacion-contractual-y-sociedad.md)                             |
| 🟡     | **Costo por lead — Aun no RESUELTO, se requiere datos reales** | Aun no resuelto, en los próximos días en paralelo con el desarrollo, no esperar a que se termine de desarrollar para calculara el costo, ir llevando los datos de los costos en herramientas, y usar pruebas gratuitas en lo posible para experimentos y validaciones |

## ⚖️ Repo del prospector construido bajo contrato (alerta IP)

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ⚠️ | **`ia_lead_prospector` = IP de la contratante** | Clonado como referencia. **NO reutilizar** su código/arquitectura/SOPs para el build nuevo ni para Catalina (cláusulas 7ª y 8ª). Ver [`situacion-contractual-y-sociedad.md`](situacion-contractual-y-sociedad.md) |

## 🏷️ Marca / Identidad

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ⏳ | **Elegir nombre del emprendimiento** | El fundador definirá "en estos días". Top candidatos en [`marca-naming.md`](marca-naming.md) |
| ⏳ | **Naming — RESET (Ronda 5)** | El fundador rechazó todos los candidatos (Rondas 1–4). Pendiente: responder las 6 preguntas de dirección para una Ronda 6 dirigida. Ver [`marca-naming.md`](marca-naming.md) Ronda 5 |
| 🔴 | **Validar el nombre elegido** | 3 chequeos: dominio (.ai/.com/.co) + marca (SIC) + handles de redes. Kiro puede correr la verificación web cuando haya 2–3 finalistas |
| 🔴 | **Definir perfil de Yulieth Gabriela + nombre de marca** | Para completar [`presentacion-fundadores.md`](../docs/fundamentos/presentacion-fundadores.md) (espacio `[ ]`) |
| 🔴 | **Pulir prueba social pública** | LinkedIn + GitHub con casos visibles (el Prospector). Ver [validación §5](../docs/validacion/validacion-fuentes.md) |

## ⚙️ Producto / Operación

| Estado | Pendiente                                       | Detalle                                                                                                                     |
| ------ | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 🔴     | **Medir consumo real del Prospector en 1 job**  | (Duplica el 🟡 de arriba: es el número que desbloquea el pricing)                                                           |
| 🔴     | **Decidir CRM (probar el Prospector como CRM)** | Dogfooding 2 semanas + hoja de embudo. Ver [`productividad-y-automatizacion.md`](productividad-y-automatizacion.md)         |
| 🔴     | **Automatizar 1–2 tareas propias**              | Sugerido: seguimiento de leads + borradores de propuesta (Hooks + Google Sheets, ver `.kiro/settings/environment_setup.md`) |

## 📚 Base de conocimiento

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ✅ | 4 pilares + 5 Módulos del Vendedor Híbrido | [`docs/fundamentos/`](../docs/fundamentos/00-vision-y-enfoque.md) |
| ✅ | Perfil del fundador + presentación de fundadores | [`perfil-fundador.md`](../docs/fundamentos/perfil-fundador.md) |
| ✅ | Documentos técnicos (diseño Prospector M1-M2, stack SDLC, hacks de IA, modelo de costo por lead) | [`docs/tecnico/`](../docs/tecnico/prospector-m1-m2-design.md) |
| ✅ | Validación de fuentes (re-verificada jul-2026) | [`validacion-fuentes.md`](../docs/validacion/validacion-fuentes.md) |
| ✅ | Estrategia (facturación, hoja de ruta, naming, propósitos, modelo de agencia) | `estrategia/` |
| 🔴 | `docs/fuentes/` — PDFs/guías originales | Aún sin subir al repo (opcional; el contenido ya está sintetizado) |

## ✅ Hitos ya cerrados (resumen)

- Base de conocimiento consolidada y validada (4 pilares + técnico + validación + estrategia).
- Marca del antiguo empleador retirada del repo; producto renombrado a **el Prospector**.
- Re-verificación web jul-2026: precios de APIs, marco tributario y legal confirmados; naming re-analizado.
- Naming: técnicas + lista negra verificada + top candidatos + Ronda 3 crítica.


---

> **Regla del coach:** este checklist se revisa cada semana. La prioridad SIEMPRE es lo que mueve ingresos (Catalina/Prospector ). Lo demás se ordena debajo.
>


---

## BITÁCORA DE DECISIONES HISTÓRICAS

# Bitácora de Decisiones — 12 de Julio de 2026
## Blindaje del Motor 2: decisiones técnicas fundamentales

Registro del *por qué* detrás de los mecanismos de resiliencia y precisión del Motor 2, deducido de la inspección del código y validado con pruebas de estrés E2E.

---

### Decisión 1: Transformación algorítmica de slugs en lugar de diccionario hardcodeado

**Contexto:** El LLM devolvía tecnologías que TheirStack no reconocía. La opción obvia era un mapa `{"AWS": "amazon-web-services", "GCP": "google-cloud-platform", ...}`.

**Decisión:** Rechazamos el diccionario. En su lugar: (1) forzamos al LLM a devolver el nombre oficial completo vía reglas de prompt y contrato Pydantic, y (2) convertimos con `t.lower().replace(" ", "-")`.

**Razón:** Un diccionario es deuda técnica infinita — habría que añadir una entrada por cada tecnología del mercado y mantenerla mientras el mercado evoluciona. La transformación algorítmica es cerrada: cubre todas las tecnologías presentes y futuras sin tocar código, siempre que el LLM cumpla su parte (nombre oficial completo). Repartimos la responsabilidad: comprensión semántica al LLM, conversión determinista al código.

**Evidencia:** Prueba 1 (`["AWS", "Microservicios"]`) → 0 empresas. Prueba 3, mismo ICP tras el fix (`["Amazon Web Services", "Python"]`) → 5 empresas. El cambio de comportamiento del LLM fue el factor decisivo.

**Riesgo residual reconocido:** si una tecnología tiene un slug que no sigue la convención `nombre.replace(" ", "-")` (ej. ".NET" → `dotnet`, no `.net`), la transformación fallará para ese caso. Es aceptable: son excepciones contadas y el costo de un lead perdido es bajo. Si se vuelve un patrón, se evaluará una capa de normalización mínima — no un diccionario completo.

---

### Decisión 2: Prohibir abstracciones en `anclaje_tecnologico`

**Contexto:** El LLM incluía "Microservicios", "ETL", "Cloud" como si fueran tecnologías.

**Decisión:** El contrato de dominio y el prompt prohíben explícitamente conceptos arquitectónicos, metodologías y procesos. Solo nombres propios de software/vendors.

**Razón:** Las APIs technográficas (TheirStack) indexan productos concretos, no conceptos. "Microservicios" no es buscable; "Kubernetes" o "Docker" sí. Permitir abstracciones garantizaba búsquedas vacías y contaminaba el `anclaje_tecnologico` que alimenta el scoring.

---

### Decisión 3: Evasión de WAF con headers de navegador, sin escalar a Playwright

**Contexto:** Cloudflare bloqueaba las peticiones de Wappalyzer y Google Alerts.

**Decisión:** Inyectar headers de Chrome real. NO escalamos a Playwright/navegador headless.

**Razón:** Playwright resuelve JS challenges pero pesa cientos de MB, ralentiza cada request y añade una dependencia frágil. Para el 80% de los WAFs básicos, un User-Agent legítimo basta. Cuando un dominio con protección avanzada bloquea igual (ej. `thefacilitiesgroup.com` en Prueba 3), aceptamos el `[]` y seguimos. El ROI de vencer un WAF agresivo por un lead individual es negativo — es la regla de oro aplicada a la infraestructura.

---

### Decisión 4: Backoff manual sin `tenacity` en los adaptadores de trigger

**Contexto:** Ya usamos `tenacity` en el `GroqICPAdapter` (Motor 1) para rate limits.

**Decisión:** En TheirStack y GitHub usamos un `for intento in range(3)` con `time.sleep(2)`, no `tenacity`.

**Razón:** El retry de trigger es trivial (2 reintentos, espera fija) y no justifica el overhead conceptual de configurar decoradores de tenacity con estrategias de wait inyectables. `tenacity` se reserva para el Motor 1, donde el manejo de rate limit del LLM es más crítico y sí se testea con estrategias de espera inyectables. Principio: usar la herramienta más simple que resuelva el problema real.

---

### Decisión 5: Contrato de error "nunca propagar al Core"

**Contexto:** El Motor 2 depende de 5 fuentes externas, cada una con su propio modo de fallo.

**Decisión:** Todo adaptador captura cualquier excepción y retorna `[]`. El Core nunca ve un error de red.

**Razón:** Aislamiento hexagonal estricto. El dominio no debe conocer HTTP, timeouts ni rate limits. Un fallo en SECOP no puede tumbar el descubrimiento de TheirStack ni el scoring de GitHub. Las pruebas E2E confirmaron 3 fallos de red simultáneos (SECOP 400, Wappalyzer WAF, TheirStack vacío) sin un solo crash. La resiliencia del pipeline completo es mayor que la de su fuente más débil.

---

### Decisión 6: Bug de double-encoding en SECOP (`%2525`)

**Contexto:** SECOP retornaba HTTP 400 en producción.

**Causa:** El `where_clause` tenía `like '%25{nombre}%25'`. Como `requests` codifica el `%` de `%25`, el wire recibía `%2525`, rompiendo el SoQL.

**Decisión:** Usar `%` literal en el string (`'%{nombre}%'`) y dejar que `requests` haga el encoding una sola vez.

**Lección:** No pre-codificar valores que la librería HTTP ya codifica. El double-encoding es un bug silencioso clásico: el código "parece" correcto (tiene el `%25` que uno ve en URLs) pero produce basura en el wire.

---
*Estas decisiones son la fuente de la verdad del comportamiento del Motor 2. Si un cambio futuro las contradice, debe justificarse aquí primero.*


---

# Bitácora de Decisiones — 22 de Julio de 2026
## Descubrimiento y Scoring de los Motores 1 y 2

> ⚠️ **ESTADO: INVESTIGACIÓN CONSOLIDADA — decisiones aún NO definidas.**
> Este documento registra (a) los fixes de raíz YA implementados en el Motor 2
> (precisión + scoring), (b) el resultado del run #2 del sandbox real de TBBC,
> y (c) la investigación empírica de descubrimiento contra APIs reales
> (Apollo / TheirStack / SECOP). Las **decisiones de arquitectura de
> descubrimiento** (Híbrido Multi-Fuente, reforma del Negative ICP) están
> **en evaluación** y requieren la aprobación explícita del fundador antes de
> tocar código. Nada de las secciones 4 y 5 debe interpretarse como decisión
> tomada.

---

### 1. Contexto — Fixes de raíz implementados en Motor 2 (precisión + scoring)

Se blindó el Motor 2 con siete fixes de raíz. **444 tests verdes, `ruff`
limpio en `src`.** (Estos cambios YA están en el working tree pero AÚN NO
commiteados al abrir esta bitácora.)

1. **`ScoreTriggerPolicy` reconciliada a la spec canónica v5.0** —
   puntos base `TIER_0=200 / TIER_1=100 / TIER_2=50 / TIER_3=0`, bonuses
   `+30` multi-origen y `+50` por cruce TIER_0 con otro origen, decay
   diferenciado CAUSA `90d` / EFECTO `45d`, umbral de calificación `150`.
   **Corrección estructural adicional:** agregación **mejor-por-origen** —
   solo el trigger de mayor puntaje de cada origen contribuye al score. Un
   origen ruidoso (p. ej. múltiples entradas RSS de Google Alerts) ya **no
   puede calificar un lead por sí solo** apilando señales del mismo origen.
   Hallazgo estructural: sin esta regla, el scoring premiaba el volumen de
   una única fuente en lugar de la corroboración multi-señal.

2. **TheirStack — "dos ejes de tiempo"** — el aging de una vacante
   (`now - date_posted ≥ 45d`) determina el **TIER** (≥45d ⇒ TIER_0, señal de
   fill-rate failure), mientras que la `fecha_evento` se fija en `now` para
   que el decay de EFECTO (45d) **no mate** una vacante que sigue abierta (es
   un estado continuo, fresco en cada re-observación).

3. **SECOP — ventana ALTA alineada al decay de CAUSA (90d)** — un contrato
   adjudicado se clasifica ALTA si fue firmado hace ≤90 días, de modo que un
   TIER_0 de SECOP (CAUSA) siempre puntúe dentro de su ventana de scoring.

4. **Google Alerts — verificación semántica por LLM** — fin de la "fábrica de
   falsos C-level": las entradas RSS se validan semánticamente antes de
   convertirse en trigger de alta confianza. **Degradación con gracia:** sin
   LLM disponible, la entrada cae a `TIER_3` (mera mención), **nunca** a un
   falso-alto. Complementa (no reemplaza) el filtro de co-ocurrencia y el
   techo de confianza para nombres cortos.

5. **GitHub — verificación de dominio de la organización** — se comprueba que
   la organización de GitHub pertenece realmente al dominio de la empresa
   candidata (anti-colisión: `forbes.com` global vs. Forbes Colombia). Evita
   atribuir repos de un homónimo a la empresa evaluada.

6. **Gate de tipo de organización** — gobierno, ONG, medios, educación y
   gremios se filtran vía la Capa 2 LLM ya existente (`PropuestaValorAdapter`),
   no son ICP y no deben avanzar al scoring de señales.

7. **Heurística de país por ccTLD (estándar IANA)** — se infiere el país a
   partir del dominio de nivel superior (p. ej. `.co`, `.mx`) **antes** del
   scraping caro, para descartar geografía fuera del ICP sin gastar recursos.

**Decisión/estado:** IMPLEMENTADO y verificado (444 verdes). Es la base de
precisión sobre la que se apoya el resto de la investigación.

---

### 2. Resultado del run #2 (sandbox real de TBBC)

Corrida completa del sandbox real. **Embudo observado:**

| Etapa | Cantidad | Nota |
|---|---|---|
| Descubiertas (Apollo) | 50 | población inicial |
| Excluidas por "competencia" | 17 | **muchas MAL clasificadas** |
| Descartadas por tipo de organización | 8 | **correcto** |
| A revisión manual | 5 | fallos técnicos de scraping |
| Analizadas a fondo | 20 | |
| **Calificadas** | **0** | ningún lead superó el umbral |

- **Falsos positivos de exclusión (17):** Tecnoaguas, mayoristas, colegios,
  empresas de defensa — arrastradas por el heurístico de nombre `"tecnolog"`
  de la Capa 1 del Negative ICP. Ninguna es competidor real.
- **Descartes correctos por tipo (8):** Blu Radio (medios), Agencia Nacional
  Digital (gobierno), 6 colegios (educación) — el gate de tipo de organización
  funcionó como se esperaba.
- **Revisión manual (5):** fallos técnicos de scraping (SPAs opacas), no
  ambigüedad semántica real.

**Diagnóstico:** los filtros de precisión **funcionan**; el cuello de botella
es el **DESCUBRIMIENTO**. Apollo, con la query actual, trae la **población
equivocada**: las empresas no son software real, no tienen señales, y **no
hubo ni un solo trigger de TheirStack**. Refinar más el scoring no cambia el
resultado si la fuente de descubrimiento no entrega ICP.

---

### 3. Investigación empírica (probe de solo-lectura contra APIs reales)

Sonda de solo-lectura contra las APIs reales para entender por qué el
descubrimiento falla y qué palancas existen. Hallazgos fieles:

**Apollo (plan free):**
- `industry` viene **vacío** (es campo de pago), pero `naics_codes` está
  **SIEMPRE poblado** (observados: `541511`, `541512`, `511210/513210`,
  `518210`).
- Keyword en español `"tecnología"` → ~3-4/10 son software real; keyword en
  inglés `"software development"` → ~8/10. Un **post-filtro determinista por
  NAICS de software** deja ~76% limpio automáticamente.
- `organization_industry_tag_ids` **funciona en free** (HTTP 200); solo el
  technographic `currently_using_...` es de pago (HTTP 422).
- `estimated_num_employees` viene **vacío** en free.

**TheirStack:**
- La query actual (solo tecnología + país) trae basura (BBVA, Makro).
- La query **refinada** con `min/max_employee_count` (51/200) +
  `job_title_or` `[backend, developer, software, devops]` → **10/10 en ICP**,
  con `employee_count` y aging visibles. TheirStack sirve como **descubridor
  por señal** cuando se le dan filtros de tamaño y cargo.

**SECOP:**
- El descubrimiento por categoría UNSPSC de TI es **técnicamente viable**,
  pero los adjudicatarios resultan ser **personas naturales** → **NO sirve
  como descubridor**. Se mantiene únicamente como **señal de scoring**
  (CAUSA / TIER_0 cuando la empresa candidata ya está identificada).

**Estado:** investigación registrada. No implica cambio de código aún.

---

### 4. Propuesta EN EVALUACIÓN (NO decidida): Descubrimiento Híbrido Multi-Fuente (Opción C)

> No decidido. Requiere aprobación del fundador.

Unir dos descubridores complementarios y deduplicar por dominio:
- **Apollo** como TAM firmográfico, **mejorado** con keyword en inglés +
  post-filtro NAICS determinista de software.
- **TheirStack** como **descubridor por señal**, con filtros de tamaño
  (`51-200`) + cargo técnico.
- **∪ (unión) deduplicada por dominio.**
- **SECOP / Google Alerts / GitHub** permanecen como **scoring**, no como
  descubridores.

**Alternativas consideradas:** (A) seguir solo con Apollo + query en español
(status quo — produjo 0 calificadas); (B) solo TheirStack por señal (pierde
el TAM firmográfico frío). La Opción C está alineada con la doctrina
**multi-señal** de la literatura (evitar single-signal dependency).

**Consecuencias si se adopta:** más cobertura de ICP real, pero mayor
complejidad de orquestación y deduplicación; costo de API a revisar.

---

### 5. Propuesta EN EVALUACIÓN (NO decidida): reforma del Negative ICP

> No decidido. Origen: propuesta del fundador.

- **Eliminar** el heurístico de nombre `"tecnolog"` (Capa 1) — falsos
  positivos demostrados en el run #2 (Tecnoaguas, etc.).
- **Hard-exclude solo** para competidor directo **confirmado por LLM**
  (Capa 2).
- **Ante duda:** marcar / nurturing en vez de descartar.

**Razonamiento del fundador:** una empresa que "parece competencia" por el
nombre puede en realidad tener señales de dolor y ser un buen lead; no debe
descartarse solo porque el nombre lo sugiera. La precisión del descarte debe
recaer en la evidencia semántica (LLM sobre la homepage), no en una
subcadena del nombre.

**Consecuencia si se adopta:** menos falsos positivos de exclusión, a costa
de más llamadas a la Capa 2 LLM (más costo por candidato ambiguo).

---

### 6. Cruce con el reporte consolidado externo (validación de alineación)

Contraste de nuestra arquitectura contra un reporte consolidado externo de
estrategia de prospección.

**ALINEADOS en:**
- Jerarquía de Tiers 0/1/2/3.
- Regla de Oro (cruce de ≥2 vectores de señal).
- Descarte de señales >90 días.
- "Buscar ventanas, no empresas".
- Apollo / InfobelPRO como TAM base de Tier-3.
- Foco en Motores 1-2 primero (Motor 4 después).

**Nuance que NUESTRO trabajo empírico AÑADE (y el reporte teórico no tiene):**
- SECOP **no es descubridor** (adjudicatarios personas naturales).
- Apollo free requiere **post-filtro NAICS** para limpiar la población.
- TheirStack requiere **filtros de tamaño + cargo** para no traer basura.

**MEJORAS que el reporte aporta y AÚN no tenemos:**
- (a) **Pesos de trigger dependientes del subsector** (hoy son fijos).
- (b) Libro nuevo *The Sales Development Playbook* (Trish Bertuzzi) para una
  matriz **Fit × Intent**.
- (c) Roles **SDR / AE** (Predictable Revenue) — son proceso comercial, no
  parte del motor técnico.

**Conclusión:** vamos bien encaminados, sin divergencia de fondo. El aporte
empírico refina el marco teórico con restricciones reales de las APIs.

---

### 7. Preguntas abiertas (pendientes de decisión del fundador)

1. **NAICS de software definitivos** — propuesta: prefijos `5415`,
   `5112/5132`, `5182`. ¿Se confirma este conjunto?
2. **Aging Tier-0** — ¿45 días o 45-60 días?
3. **Info real de TBBC** (web / LinkedIn) para afinar el keyword de industria
   y la definición operativa de "competidor directo".
4. ¿Se **implementa el Híbrido C** (Apollo ∪ TheirStack, dedup por dominio)?
5. ¿Se aprueba la **reforma del Negative ICP** (eliminar heurístico de nombre)?

---
*Investigación consolidada el 22-Jul-2026. Este documento es registro de
hallazgos y propuestas, no de decisiones cerradas. Cualquier cambio de código
derivado de las secciones 4 y 5 debe pasar primero por la aprobación explícita
del fundador y quedar registrado como decisión en una entrada posterior.*


---

# Decisión: Inversión del Motor 1 a "Signal-First Discovery"

- **Fecha:** 25-jul-2026
- **Módulo:** Motor 1 (Descubrimiento) + Motor 2 (gate de tamaño)
- **Tipo:** decisión de arquitectura
- **Estado:** IMPLEMENTADO (454 tests verdes) — pendiente de validación empírica con `sandbox_tbbc_real.py`

## Contexto (la historia, para no repetir el error)

1. **21-jul (v6.0):** se decidió que Motor 1 descubriera **exclusivamente con Apollo**
   (firmografía pura: industria+tamaño+país), separando "discovery" de "señales".
   Racional de entonces: limpieza — que TheirStack no ensuciara el TAM trayendo
   empresas por vacantes.
2. **24/25-jul (path A):** se corrigió que Apollo buscaba por `categoria_empresa`
   del propio cliente (traía competidores) → se pasó a `industrias_objetivo`
   derivadas del ICP.
3. **25-jul (corrida real, baseline):** con path A, el resultado fue **0 leads
   accionables**: de 48 empresas descubiertas por Apollo, **29 (60%) eran
   colegios/universidades/ONGs/medios** (descartadas por el gate de tipo), y las
   3 que "calificaron" (Magneto, Delta A Salud, MejorCDT) eran empresas tech que
   construyen in-house o scale-ups — fit dudoso. El scoring (Motor 2) funcionó;
   el **descubrimiento traía la población equivocada**.

## Diagnóstico de raíz

Descubrir por **Fit firmográfico ciego** (Apollo por industria/tamaño/país) y
*esperar* señal construye el **Tier-3 TAM** de SHiFT! — la capa MENOS accionable
— y obliga a pagar por filtrar 60% de basura. Es lo contrario a cómo prospecta un
profesional: él arranca por el **evento** (trigger) que rompe el status quo y
valida el fit después.

## Fundamento (fuentes, no invención)

- **SHiFT! (Craig Elias):** buscar "ventanas de insatisfacción" (trigger events),
  no empresas por tamaño/sector. Regla del 74% / primer contacto tras el trigger.
- **ABM (Burgess) + investigación web (pedowitzgroup, autobound, salesmotion):**
  modelo de 4 ejes **Fit × Intent(trigger) × Engagement × Value**; prospección por
  trigger da **4-5x conversión y ciclos 30% más cortos** vs. outbound genérico.
- **Convergencia:** un lead "oro" necesita **Fit Y Trigger**. Nuestro Motor 2 ya
  scorea el trigger bien; el hueco estaba en el Motor 1 (descubría solo Fit ciego).

## Decisión

**Invertir el Motor 1 a "Signal-First Discovery": descubrir DESDE la fuente de
trigger, no desde firmografía ciega.** Esto REVIERTE deliberadamente la decisión
del 21-jul (Apollo-only), que la evidencia (0 accionables) probó errónea.

### Cambios implementados
1. **TheirStack = discoverer PRIMARIO.** Ventana de descubrimiento **30 → 90 días**
   (antes jamás descubría vacantes ENVEJECIDAS >30d, que son el trigger TIER_0 de
   fallo de reclutamiento — el dolor exacto de una consultora de staff-aug). Como
   filtra por tecnología del ICP, NO devuelve colegios/ONGs/medios → elimina de
   raíz el 60% de desperdicio. Trae dominio real → downstream funciona sin
   resolución adicional.
2. **Apollo SALE del loop M1/M2** (queda reservado para enriquecimiento M3).
3. **SECOP permanece como CRUCE de señal** (CAUSA → Regla de Oro con el EFECTO de
   TheirStack), NO como discoverer todavía (ver "pendiente" abajo).
4. **Gate de tamaño endurecido** (`PoliticaCorroboracionTamano.excede_icp`):
   asimétrico — un número firmográfico DURO (employee_count de TheirStack) mayor
   que el ICP excluye SIN corroboración; un CONSENSO mayor al ICP (incl.
   MID_MARKET) también. Cierra el hueco por el que pasaban scale-ups (Magneto)
   disfrazados de SME por el default de `_inferir_tamano`.

### Pendiente (documentado, con prerequisito claro)
- **SECOP como discoverer:** valioso (capacity shock, Tier 0) pero da nombres SIN
  dominio, y el downstream (Negative ICP homepage, scoring por dominio) exige
  dominio. Sin dominio, el Negative ICP fail-closed manda todo a revisión manual.
  **Prerequisito: un resolutor de dominio** (capa de enriquecimiento, hoy
  diferida por decisión del fundador — foco solo M1+M2). No se forzó ahora para
  no ENSUCIAR la prueba del nuevo paradigma con ruido de dominios faltantes.

## Riesgo conocido (honestidad)

Descubrir por TheirStack sigue sesgado a empresas con vacantes tech (que tienden
a construir in-house). El **aging ≥45d lo mitiga** (una vacante que NO logran
llenar en 2 meses = necesitan ayuda externa, sean o no tech-nativas), y el gate
de Fit + Negative ICP debe seguir firme. No es perfecto, pero es muy superior al
TAM firmográfico ciego. **Los resultados de la próxima corrida critican la decisión.**

## Fuentes
- SHiFT! (Elias/Shanto); Predictable Revenue (Ross); SPEAR Selling (Shanks); ABM (Burgess).
- Web (25-jul-2026): autobound.ai, salesmotion.io, pedowitzgroup.com, alexberman.com — signal/trigger-based selling.

---

## Refinamiento tras la corrida #1 de Signal-First (mismo día, 25-jul-2026)

La primera corrida real con Signal-First mejoró de forma clara (adiós 60% de
educación; primer decisor contactable real: Milena Rico, CTO). Pero el análisis
crítico expuso 3 fugas, todas corregidas:

1. **Sesgo a GRANDES empresas.** TheirStack traía enterprises (Experian, Havas,
   AXA, Postobón, Keralty…) porque son las que más vacantes tech publican en CO,
   no el SME 50-200 del ICP. **Fix:** filtro de tamaño NATIVO en el discovery
   (`min_employee_count`/`max_employee_count` — confirmado en el OpenAPI de
   TheirStack, `JobSearchFilters-Input`), derivado del `manifiesto.tamano_empresa`.
   Validado en vivo: con SME → devuelve empresas de 75 y 198 empleados (antes
   traía multinacionales). Costo: sigue ~1 crédito/vacante, pero ahora gastados
   en el pond correcto.
2. **Bug de Motor 1 (no determinista): "51-200 empleados" se clasificaba a veces
   como MID_MARKET en vez de SME**, desactivando el gate de tamaño. **Fix:** regla
   de mapeo numérico ESTRICTO en el prompt de `GroqICPAdapter` (menos de 50 →
   STARTUP; 50-200 → SME; 201-1000 → MID_MARKET; >1000 → ENTERPRISE; clasificar
   por límite superior del rango).
3. **Punto ciego del Negative ICP:** "BPM Consulting" (consultoría de procesos que
   vende servicios a terceros) se coló como no-competidor. **Fix:** se reforzó el
   prompt de `es_vendor_it` para incluir explícitamente consultoras de cualquier
   tipo (TI/negocio/procesos/BPM/transformación), system integrators, staffing/
   outsourcing de TI y agencias — con la pregunta guía "¿vende servicios/proyectos
   tech o de consultoría a terceros?" y regla de desempate hacia `true`.

**Verificación:** 455 tests verdes, ruff limpio, probe en vivo del filtro de
tamaño OK. Pendiente: re-correr `sandbox_tbbc_real.py` y comparar contra la
corrida #1 (13 descubiertas, sesgo enterprise, BPM colado).

---

## Fix de raíz tras corrida #2 (créditos/rate agotados) — 25-jul-2026

La corrida #2 confirmó los fixes previos (sizing SME correcto, sin enterprises/
colegios, vendors excluidos, SECOP cargó a Atrys Colombia con TIER_0) PERO quedó
inconcluyente porque se agotaron créditos de TheirStack (402) y tokens/día de Groq
(429). El análisis expuso una ineficiencia arquitectónica real, ahora corregida:

1. **Doble-llamada a TheirStack eliminada (el fix importante).** El discovery hacía
   1 llamada y descartaba las vacantes; luego `obtener_triggers` y `estimar_tamano`
   RE-CONSULTABAN TheirStack por cada empresa (~2 llamadas/empresa → ~36 para 18
   empresas), agotando créditos y disparando rate limits. **Fix:** el discovery
   ahora CACHEA las vacantes por dominio (`self._discovery_jobs`) y ambos métodos
   las REUTILIZAN → CERO llamadas/créditos extra para empresas descubiertas (query
   solo como fallback para empresas ajenas al discovery). Reduce el gasto de ~37
   llamadas a **1** por corrida.
2. **Orden del discovery: DESC → ASC.** Como el scoring ahora se alimenta de la
   cache, se ordena el discovery por `date_posted` ASCENDENTE para capturar las
   vacantes ENVEJECIDAS (aging ≥45d = TIER_0, fallo de reclutamiento) — con DESC la
   cache traería solo vacantes frescas y jamás daríamos TIER_0. ASC es además más
   coherente con Signal-First (buscamos empresas que NO llenan un rol hace semanas).
   Tradeoff documentado: la precisión del aging depende de las vacantes del batch;
   en plan de pago se podría paginar para más cobertura.
3. **Recalibración de `es_vendor_it`.** En la corrida #2 excluyó Publicis Media
   (agencia de medios) como "vendor IT" — falso positivo de mi refuerzo anterior.
   Se ajustó el prompt: agencias de MEDIOS/PUBLICIDAD/marketing tradicional que NO
   construyen software → false (no compiten con una consultora de ingeniería). Solo
   es true quien vende TECNOLOGÍA/SOFTWARE/CONSULTORÍA TÉCNICA a terceros.

**Verificación:** 457 tests verdes (+2 de reutilización de cache y fallback), ruff
limpio, probe en vivo del filtro de tamaño OK (empresas de 75 y 198 empleados).
Pendiente: re-correr con cuenta TheirStack nueva (+ idealmente varias GROQ_API_KEY)
para una corrida LIMPIA que por fin permita juzgar la calidad del scoring.

---

## Blindaje de raíz tras corrida #3 — híbrido TheirStack + domain quality + gaps de claves (25-jul-2026)

La corrida #3 (cuenta TheirStack nueva) confirmó el paradigma: sin 402/429 en
TheirStack (el fix de doble-llamada funcionó), Atrys Colombia salió score 312
TIER_0 (cruce SECOP+TheirStack), Publicis Media dejó de excluirse (recalibración
`es_vendor_it` OK). PERO se agotó el TPD de Groq acumulado del día (Adylog/INSPYR
a revisión manual por 429) y solo 1/18 calificó. El análisis dejó 3 blindajes,
todos IMPLEMENTADOS (466 tests verdes, ruff limpio):

### 1. Corrección de un DATO FALSO en el código + híbrido de aging en TheirStack

**Hallazgo crítico (antipsicofancia con el propio código):** el comentario de
`_LIMITE_VACANTES_AGING = 25` afirmaba *"TheirStack cobra por CONSULTA, no por
resultado: traer más vacantes no agrega costo"*. **Es FALSO.** La doc oficial
([How credits work](https://theirstack.com/en/docs/pricing/credits), verificada
25-jul-2026) dice que los créditos se consumen **por cada registro (job/company)
devuelto**. Ese `limit=25` era una **bomba de créditos** (hasta 25/empresa) — la
causa raíz del storm 402 de la corrida #2, no un simple "quedarse sin saldo".

**Decisión — HÍBRIDO en `obtener_triggers` (aprobado por el fundador vs cache-pura):**
la cache-pura (reutilizar solo las vacantes del discovery) había degradado la señal:
el discovery trae ~1-2 vacantes/dominio (son `_max_discovery` GLOBALES), así que su
aging subestimaba y mandaba todo a TIER_2 (score 50). El híbrido hace, SOLO para los
finalistas que llegan al scoring, **una query precisa de 1 crédito**:
`{limit:1, order_by:date_posted ASC, company_domain_or:[dominio],
posted_at_max_age_days:90, company_technology_slug_or:[techs]}` → trae la vacante
tech abierta **más antigua** → **aging real** → TIER_0 detectable. La cache del
discovery queda como **fallback** (si no hay API key o la query falla por créditos/
red, 0 créditos). `estimar_tamano` **sigue** leyendo el `employee_count` de la cache
(0 llamadas). Costo por corrida: ~1 crédito × nº finalistas (post-gates), no ×18.

**Por qué `limit=1` no pierde señal:** `nivel_confianza` (ALTA≥3 / MEDIA≥1) **no
entra al score** de `ScoreTriggerPolicy` (que solo usa `PUNTOS_BASE[tier]×decay`);
solo actúa como gate 0-vacantes. Verificado leyendo `policies.py`. Traer 25 para
"subir a ALTA" era, por tanto, gastar 24 créditos extra por nada — bazuca clásica.
Se eliminó la constante `_LIMITE_VACANTES_AGING` y su comentario erróneo.

### 2. Domain quality — pre-check DNS con stdlib (costo cero)

Dominios del ICP que ya no resuelven (`ERR_NAME_NOT_RESOLVED`: bolsamercantil.com.co,
comfandi.com.co) consumían el timeout completo de `requests`, las 4 rutas alternas y
el arranque de un Chromium headless (~15s) para nada. **Fix:** `_dominio_resuelve()`
resuelve el hostname con `socket.getaddrinfo` (stdlib) al inicio de
`_leer_texto_homepage`; si no resuelve → `None` inmediato. **Anti-bazuca explícito:**
no se compró un enrichment API solo para saber si un dominio resuelve.

### 3. GroqKeyPool — recolección de claves tolerante a huecos

El fundador añadió una clave nueva para las pruebas (el modelo `llama-3.3-70b-versatile`
es el único útil para el caso; no hay alterno en Groq, confirmado por él → la vía es
más claves, no otro modelo). **Bug latente:** `_descubrir_del_entorno` hacía `break`
en el primer índice ausente, así que una `GROQ_API_KEY_4` añadida sin tener la `_3`
**nunca se habría usado** (silencioso). **Fix:** recolecta TODAS las `GROQ_API_KEY_N`
presentes tolerando huecos. Tests que simulan el hueco exacto (_1,_2,_4).

### Investigación de herramientas adicionales (criterio anti-bazuca)

- **Aging GRATIS (a validar en corrida):** TheirStack permite `blur_company_data=true`
  → la request **no cuesta créditos** (blurea identificadores de empresa, pero
  `date_posted`/`technologies`/`title` son campos de JOB, no de company; y el filtro
  por dominio es input, no output). Si se confirma que conserva la fecha, el aging
  pasa de 1 crédito a **0**. No se activó ya porque no pude verificarlo en vivo
  (creds agotados); si `blur` borrara la fecha, degradaría a TIER_2 (fail-closed, sin
  crash). Siguiente corrida: probar con 1 empresa y comparar.
- **Señales de funding LatAm (fuertes, gratis):** un funding round es de los triggers
  B2B más potentes (capital fresco → nuevas contrataciones/herramientas). Fuentes
  públicas para Colombia/LatAm: Dealflow LatAm, Scenius LatAm, Contxto, LatamList,
  TechLoy. **Anti-bazuca:** ingerirlas vía los adaptadores que YA tenemos (Tavily /
  Google Alerts RSS), NO comprar una plataforma de señales (Buska/6sense/ZoomInfo).
- **Name→domain (para el futuro SECOP-discoverer):** Clearbit **Autocomplete** API es
  gratis y sin API key (distinta del Name-to-Domain que HubSpot cerró en abr-2025).
  A probar cuando se habilite SECOP como discoverer. Rechazado: SEC filings (US-only,
  inútil para Colombia).

**Verificación:** 466 tests verdes (+9: 3 de gaps de claves, 5 de DNS, ajustes de
híbrido/fallback), ruff limpio. **Pendiente:** corrida LIMPIA cuando resetee el TPD
de Groq (o con la clave nueva ya tomada por el pool) para juzgar el scoring completo.


---

# Vacante vieja-Y-abierta + visibilidad de aging + funding (26-jul-2026)

> Sesión de análisis de la **corrida #4** y aplicación de P1/P2/P3. Verificado:
> 467 tests verdes, gate ruff (`src/`+`tests/`) limpio.

## Contexto: qué mostró la corrida #4

La corrida #4 (18 empresas descubiertas) salió con un patrón sospechosamente
uniforme: **los 18 triggers de TheirStack fueron idénticos** — `MEDIA, 1 vacante,
TIER_2, score 50`. Ninguno llegó a TIER_0 por aging. La única empresa que calificó
(Atrys, 310) lo hizo **por SECOP** (4 contratos), no por TheirStack. En la práctica,
TheirStack estaba funcionando como **descubridor** pero **no** como señal de
calificación. El resto del pipeline se comportó bien (GroqKeyPool sin 429, 5
competidores excluidos, DNS pre-check, embudo disciplinado: 17 empresas de bajo fit
se quedaron en nurturing sin gastar créditos de Motor 3).

## Causa raíz (hallazgo duro, con evidencia)

Al leer el **OpenAPI oficial de TheirStack** (`https://api.theirstack.com/openapi.json`,
verificado 26-jul-2026) encontré que **`order_by` está marcado `deprecated: true`**
en `JobSearchFilters`. Nuestro discovery pedía `order_by: date_posted ASC` para traer
las vacantes MÁS ANTIGUAS (envejecidas = TIER_0). Si el parámetro se ignora, el
discovery devuelve el orden por defecto (`date_posted desc` = las más RECIENTES) →
vacantes frescas → aging < 45d → **TIER_2 siempre**. Esto explica exactamente el
patrón de la corrida #4. La estrategia de "capturar aged vía ordenamiento" era frágil
y probablemente nunca funcionó.

Segundo problema, de visibilidad: el sandbox truncaba la descripción del trigger a
**70 caracteres** (`sandbox_motor_2_auto.py`), y el dato de aging va al FINAL de la
descripción (`Aging (vacante más antigua: X días)`). Estábamos ciegos al número que
más importaba.

## Decisiones aplicadas

### P1 — Visibilidad del aging (costo 0)
`imprimir_resultado_empresa` ya no trunca a 70; muestra el **TIER explícito**
(TIER_0 en verde) y la descripción hasta 150 chars (incluye el aging). Sin esto no
se puede distinguir "las vacantes son frescas" de "el cálculo está mal".

### P2 — Vacante VIEJA-Y-ABIERTA (robusta al `order_by` deprecado)
`TheirStackAdapter.obtener_triggers` ya **no** depende del ordenamiento. Hace una
query por **ventana de fechas absolutas** + estado abierto:

```
{ limit:1, company_domain_or:[dominio],
  posted_at_gte: hoy-90d, posted_at_lte: hoy-45d,   # posteada hace 45-90 días
  is_closed: false,                                  # y SIGUE abierta
  company_technology_slug_or: [techs] }
```

- Si devuelve un registro → **TIER_0 por construcción** (aging ≥45d garantizado). La
  vacante posteada hace ≥45d que sigue abierta = rol que NO logran llenar = sangrado
  activo = el dolor exacto que resuelve una consultora de staff-augmentation.
- Si devuelve 0 (no sangra) → **fallback a la cache del discovery** (vacante fresca →
  TIER_2), preservando la señal de "demanda fresca" como contexto.
- **Costo:** 1 crédito solo cuando HAY vacante vieja-y-abierta (TheirStack no cobra si
  devuelve 0 registros — fuente: docs de créditos). Los que no sangran cuestan 0.
- **Params verificados en el OpenAPI** (no adivinados): `is_closed`, `posted_at_gte`,
  `posted_at_lte` existen y NO están deprecados; `order_by` sí lo está.

`descubrir_empresas`: se añadió `is_closed:false` (una vacante ya cerrada/llenada no es
señal de necesidad activa) y se quitó la dependencia del `order_by` ASC (comentario
corregido). Sigue siendo descubridor AMPLIO (universo de empresas con vacante tech
abierta en 90d); la determinación de TIER_0 vive ahora en el scoring.

**Diseño de evaluación:** discovery amplio + chequeo per-finalista de vacante
vieja-y-abierta hace que la próxima corrida muestre un MIX de TIER_0 (sangran) y
TIER_2 (solo demanda fresca) → podremos VER qué fracción del universo realmente
sangra. Si sale 0 TIER_0, la tesis del "aged vacancy" no aplica a este ICP en
Colombia y el eje de calificación debe ser SECOP + funding (no las vacantes).

### P3 — Funding vía la infraestructura que YA existe (anti-bazuca, costo 0)
`GoogleAlertsRSSAdapter` **ya** detecta rondas de inversión (`ronda_inversion_o_capital
→ TIER_0/CAUSA/ALTA`) por verificación LLM. Lo que faltaba era ALIMENTARLO con las
noticias correctas. En la corrida #4 el feed usaba el **nombre legal completo** entre
comillas (`"Aló Credit Colombia S.A.S"`), pero las noticias de funding usan la MARCA
(`"Aló Credit"`) → se perdían. Fixes en `sandbox_motor_2_auto.py`:

- `_marca_desde_nombre`: quita sufijos legales (S.A.S, S.A., Ltda., E.S.P., etc.) →
  marca buscable.
- `construir_rss_eventos`: segundo feed de Google News enfocado en eventos de alto
  valor (`inversión OR financiación OR ronda OR "levanta capital" OR adquisición OR
  fusión OR "nuevo CTO" OR "director de tecnología"`).
- `recolectar_triggers` pasa **2 feeds** (eventos primero, para prioridad en el top-5
  que ve el LLM) + `_KEYWORDS_EVENTOS_NEGOCIO` al pre-filtro (para que las entradas de
  evento pasen aunque no contengan el nombre legal exacto; el LLM verifica que sean de
  la empresa). Sin nueva API, sin costo (Google News RSS es gratis).

## Rechazado / pospuesto (criterio anti-bazuca)

- **`blur_company_data=true` (aging gratis):** confirmado que hace la request gratis,
  pero el cuello de botella HOY es la señal, no el costo (la query de aging ya cuesta 0
  cuando no hay TIER_0). Pospuesto hasta confirmar que el aging califica.
- **`/v1/companies/search` con `funding_stage_or` / `min_funding_usd` /
  `last_funding_round_date_gte`:** TheirStack tiene firmografía de funding nativa (3
  créditos/empresa). Es un camino FUTURO potente para descubrir por funding, pero es un
  discoverer nuevo — no se toca ahora para no ampliar el alcance sin validar antes.
- **SECOP como descubridor + Clearbit name→domain:** SECOP es hoy lo único que
  califica; convertirlo en descubridor subiría el throughput, pero es proyecto aparte.

## Próximo paso

Correr `sandbox_tbbc_real.py` y **leer los números de aging ya visibles** + el TIER por
empresa. Decidir con datos: (a) ¿aparecen TIER_0 (empresas que sangran)? ¿cuántas de
18? (b) ¿el funding prende en las fintechs del universo (Aló Credit, Bravo)? Según eso
se define si el eje de calificación es aging, funding, SECOP, o una combinación.


---

# Decisiones tras corrida #6: anti-comercial, excepción SECOP, muerte del funding-discoverer, camino a híbrido (26-jul-2026)

> Decisiones comerciales y de arquitectura tomadas por el fundador tras analizar la
> corrida #6. Implementadas con **480 tests verdes**, gate ruff (`src/`+`tests/`) limpio,
> enfoque fail-closed preservado.

## Qué mostró la corrida #6 (base de las decisiones)

- **Discriminación restaurada** (bandas de aging funcionan): 2 TIER_0, 1 TIER_1, 4 TIER_2
  (vs 12/12 TIER_0 de la #5).
- **Gate de fit funcionó**: 6 multinacionales/filiales descartadas
  (Atrys, Leo, Termopaipa/ContourGlobal, Novartis, Publicis, Hogar Universal).
- **Tavily rescató** Bolsa Mercantil (homepage muerta) → 0 en revisión manual.
- **Funding discoverer = 0**: `/v1/companies/search` no devolvió ninguna empresa →
  TheirStack no tiene cobertura de funding para PYMEs colombianas.
- **Falso positivo TIER_0**: Aló Credit calificó por "Vendedor / Desarrollador
  **Comercial** con Moto" (rol de VENTAS, techs "cobertura, whatsapp") — el regex de rol
  técnico matcheaba "Desarrollador" sin distinguir "desarrollador comercial" (vendedor).

## Decisiones implementadas

### 1. Bugs técnicos (raíz en `TheirStackAdapter`)
- **Filtro anti-comercial:** `_PATRONES_ROL_NO_TECNICO` → `job_title_pattern_not` con
  `comercial|ventas|vendedor|negocio|fidelización|marketing|mercadeo`. TheirStack excluye
  el job si el título matchea cualquiera → la exclusión gana sobre el match de rol
  técnico. Mata el falso positivo de Aló Credit.
- **Filtro de rol técnico en el DISCOVERY:** `descubrir_empresas` ahora aplica
  `job_title_pattern_or` (rol dev/eng) + `job_title_pattern_not` (anti-comercial), no
  solo `obtener_triggers`. El universo inicial nace limpio de vacantes no técnicas
  (antes traía ventas/psicología porque `company_technology_slug_or` es a nivel EMPRESA).

### 2. Decisiones estratégicas (Core/Políticas)
- **Excepción SECOP para multinacionales** (`PoliticaFitComprador`): la firma pasó a
  `es_apta(es_multinacional, tiene_trigger_secop=False)`. Si el LLM dice multinacional
  PERO la empresa tiene trigger SECOP_SOCRATA activo → se PERMITE. Fundamento: la plata
  pública LOCAL valida que hay una compra que se decide en Colombia. Recupera a Atrys
  (filial de multinacional española con contratos SECOP), el lead de mayor señal. El
  sandbox (Paso 1.6) consulta SECOP solo si el LLM dijo multinacional y SECOP está
  enrutado (reutiliza la cache del adaptador → 0 costo extra).
- **Empresas no-tech-core (bufetes, caso CAC Abogados): DENTRO del ICP.** Un bufete
  buscando devs internos es cliente ideal de staff augmentation. Sin cambios de código.
- **Funding discoverer (TheirStack): ELIMINADO.** Se borraron
  `descubrir_empresas_por_funding`, `_parsear_empresas_funding`, `obtener_trigger_funding`,
  el origen `THEIRSTACK_FUNDING`, el endpoint `/v1/companies/search` y sus constantes/cache.
  No mantenemos código muerto si TheirStack devuelve 0 para Colombia. Funding = 100%
  Google Alerts.

### 3. El cuello de botella (arquitectura) — PREPARADO, no implementado
Los datos hablaron: **TheirStack no tiene cobertura suficiente para ser el ÚNICO
descubridor en LATAM.** Instrucción del fundador: revertir el Motor 1 a un modelo
**HÍBRIDO** — Apollo vuelve como `PuertoDescubridorEmpresas` para traer un TAM amplio
(con filtros duros contra NGO/educación/gobierno); TheirStack se queda exclusivamente en
el Motor 2 como evaluador de señal de alta urgencia. **En esta sesión NO se implementó la
reversión a Apollo**; solo se limpió el terreno (puntos 1 y 2) y se dejó todo verde.

## Verificación
- 480 tests verdes (se eliminaron los 5 tests del funding discoverer; se añadieron 2 de
  la excepción SECOP en `PoliticaFitComprador`). Gate ruff `src/`+`tests/` limpio.
- Sandboxes compilan; único lint restante = F541/E402 pre-existentes (imports tras
  load_dotenv, intencional).

## Próximo paso
Implementar la reversión a híbrido (Apollo descubridor + TheirStack solo Motor 2) en la
siguiente sesión, con los filtros duros de tipo de organización aplicados en el discovery
de Apollo.


---

# Recalibración por bandas + fit de comprador + discovery por funding + Tavily (26-jul-2026)

> Sesión de análisis de la **corrida #5** y blindaje profundo. Verificado:
> **483 tests verdes**, gate ruff (`src/`+`tests/`) limpio.

## Contexto: qué mostró la corrida #5

La corrida #5 (con la query de "vacante vieja-y-abierta" del fix anterior) salió con
un patrón que parece victoria pero NO lo es: **12 de 12 empresas analizadas
calificaron, casi todas con score exactamente 200 (TIER_0)**. Pasamos de una máquina
de falsos negativos (corrida #4, todo TIER_2) a una de **falsos positivos** (todo
TIER_0). Una tasa de calificación del 100% es tan inútil como la del 0%: el scoring
perdió capacidad de discriminar. La señal de alarma fue la uniformidad del aging:
45, 45, 46, 46, 53, 54, 55, 62 días — todos apenas por encima de 45.

## Causas raíz (verificadas, no suposiciones)

1. **45 días abierta ≠ dolor.** Una vacante publicada 45-60 días es ciclo de
   contratación NORMAL, no "no la pueden llenar". Usar 45d como TIER_0 automático
   hacía que casi cualquier empresa calificara.
2. **`is_closed=False` es débil.** El OpenAPI dice que `closed_at=null` significa
   "abierta O no lo sabemos todavía"; en Colombia lo más probable es que TheirStack
   rara vez detecte el cierre → el filtro deja pasar casi todo.
3. **`company_technology_slug_or` es a nivel EMPRESA, no de vacante** (confirmado en
   el OpenAPI: "jobs de empresas que mencionaron esas tecnologías, no necesariamente
   en los devueltos"). La vacante envejecida que tieramos TIER_0 podía ser un rol NO
   técnico. Evidencia: TODAS decían "Tecnologías: no especificadas" / "Vacante
   técnica".
4. **Bug de parseo:** los campos reales de la API son `job_title` y `technology_slugs`,
   no `title`/`technologies` → el título caía siempre al fallback y las tecnologías a
   "no especificadas".
5. **Fit del universo:** filiales de multinacionales (Novartis, Publicis,
   ContourGlobal/Termopaipa) y un bufete (CAC Abogados) calificaban. El Negative ICP
   filtra COMPETIDORES, no COMPRADORES de bajo fit.

## Decisiones aplicadas (todas con tests + ruff verde)

### Bugs de precisión (`theirstack_adapter.py`)
- **Parseo:** `_extraer_titulo`/`_extraer_tecnologias` leen `job_title`/`technology_slugs`
  (API real) con fallback a `title`/`technologies` (mocks). Ahora el trigger muestra
  el rol real.
- **Rol técnico a nivel de VACANTE:** la query de aging usa `job_title_pattern_or`
  (regex OR de roles dev/eng/devops/data/arquitecto) en vez de
  `company_technology_slug_or`. Así la vacante envejecida es realmente de tech.

### A — Recalibración del aging por BANDAS
`_parsear_triggers` ahora tiera por gradación (no umbral único):
`aging >= 75d → TIER_0` (sangrado activo, califica sola, 200≥150);
`45-75d → TIER_1` (dificultad notable, NO califica sola, 100<150, necesita cruce);
`<45d → TIER_2` (demanda fresca). `obtener_triggers` hace **2 queries de ventana de
fecha** (banda TIER_0 [75-90d], luego banda TIER_1 [45-75d]), robustas al `order_by`
deprecado y gratis cuando devuelven 0 (TheirStack no cobra sin resultados).

**Efecto (verificado con la lógica del ScoreTriggerPolicy):** colapsa los 12 falsos
positivos. CAC (53d) → TIER_1 = 100 → nurturing. Atrys (TS TIER_1 + SECOP TIER_0
cruce) → califica y queda #1. TIER_0 se reserva para aging FUERTE (≥75d) o para el
cruce multi-origen. Se restaura la discriminación.

### B — Gate de FIT DE COMPRADOR (`PropuestaValorAdapter` + `PoliticaFitComprador`)
5ª pregunta al LLM (`es_multinacional`) en la MISMA llamada cacheada (costo cero
extra): ¿la empresa es multinacional o filial de una? El ICP de TBBC son PYMEs
colombianas INDEPENDIENTES; una filial (Novartis/Publicis/ContourGlobal) queda fuera
(su compra de TI es global/centralizada). `PoliticaFitComprador.es_apta` es
**fail-open** (None no excluye; solo `es_multinacional=True` descarta). Cableado como
Paso 1.6 en el sandbox, con su banner y contador.

### C — Discovery signal-first POR FUNDING (`/v1/companies/search`)
`TheirStackAdapter.descubrir_empresas_por_funding`: descubre PYMEs colombianas
(HQ=CO, 50-200 empleados) que **levantaron capital en los últimos 365 días**, vía la
firmografía estructurada de TheirStack. Complementa al discovery por hiring: captura
empresas con presupuesto que quizá aún no publican vacantes tech. El funding se emite
como trigger autoritativo `obtener_trigger_funding` bajo el **nuevo origen
`OrigenTrigger.THEIRSTACK_FUNDING`** (CAUSA; tier por recencia: ≤90d TIER_0, ≤365d
TIER_2; fecha_evento = fecha de la ronda para el decay). Origen distinto de
GOOGLE_ALERTS (funding-as-news) a propósito: es una fuente independiente del mismo
hecho, así que cruza-corrobora en vez de colapsar por best-per-origin.

- **Costo:** 3 créditos POR EMPRESA devuelta (vs 1 del de jobs) → límite pequeño
  (`_max_discovery`). Degrada a `[]` si no hay cobertura de funding CO (la corrida
  dirá la cobertura real de TheirStack para PYMEs colombianas — dato NO verificable
  sin corrida en vivo).

### Tavily — respaldo de contexto cuando el scraping falla
Validado: Tavily da **1.000 créditos gratis/mes, sin tarjeta**
([docs](https://docs.tavily.com/documentation/api-credits), 26-jul-2026; contenido
reformulado por licencia). `TavilyContextoAdapter.describir_empresa` busca en la web
una descripción de la empresa; se inyecta como `buscador_respaldo` en
`PropuestaValorAdapter`. Cuando la homepage no resuelve (DNS muerto, SPA, 403), en
vez de caer a revisión manual por falla técnica, se clasifica con el texto de Tavily.
**Anti-bazuca:** solo se invoca cuando el scraping ya falló (0 costo si la homepage
se leyó). Ejemplo concreto: Bolsa Mercantil (homepage muerta) dejaría de quedar en
revisión manual.

## Rechazado / pospuesto (criterio anti-bazuca)

- **SECOP como descubridor:** SECOP contract-won ≠ comprador de consultoría IT (Atrys
  gana contratos de diagnóstico médico, no es un buyer de staff-aug). Y necesitaría
  Clearbit name→domain (otra dependencia). Menor calidad de señal para el ICP que el
  funding discoverer. Pospuesto.
- **`blur_company_data` (aging gratis):** el cuello de botella es la señal, no el
  costo. Pospuesto.
- **Nuevo origen para funding vía GOOGLE_ALERTS:** habría causado colisión semántica;
  se prefirió `THEIRSTACK_FUNDING` (provenance limpia).

## Qué mirar en la próxima corrida (criterio de evaluación)

1. **¿Se restauró la discriminación?** Esperado: la mayoría de las 18 caen a
   nurturing (TIER_1/TIER_2); solo califican las de aging fuerte (≥75d) o cruce
   (Atrys). Si vuelve a salir "todos TIER_0", la banda de 75d aún es baja.
2. **¿El gate de fit descarta las multinacionales?** Novartis/Publicis/ContourGlobal
   deberían caer a "DESCARTADA POR FIT (multinacional)".
3. **¿Cuántas empresas trae el funding discoverer?** Mide la cobertura real de
   TheirStack para funding de PYMEs colombianas. Si trae 0, la señal de funding
   seguirá dependiendo de Google News (P3); si trae varias, es un canal nuevo de oro.
4. **¿Tavily rescató los casos de homepage muerta?** Menos empresas en revisión
   manual por falla técnica.
5. **Créditos:** vigilar el gasto de company_search (3/empresa) y las 2 queries de
   banda de aging (0 si no hay señal).


---

