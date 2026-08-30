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

**Sesiones 19/20-ago-2026 (resumen) — auditoría de duplicados + RLS +
frontend + Calendar + roles cerrados vía el artefacto "Planos ARTF"
(`https://claude.ai/code/artifact/e008fac2-e885-4b8a-9bcb-b7d6c46595a5`,
detalle sección por sección ahí, no reproducido aquí para no duplicar):**
- **19-ago (tercera continuación):** bug real de duplicación de leads (51+1
  pares) por la misma causa raíz del `.0` de Excel en `manychat_id` — fusión
  ejecutada y verificada en 0 duplicados. Fix estructural preventivo
  aplicado: `fn_normalizar_cliente()` / `trg_normalizar_cliente` (BEFORE
  INSERT OR UPDATE en `clientes`), normaliza `manychat_id` e `ig_handle`
  siempre, sin importar la vía de escritura. `ig_handle` backfillado
  completo (6.424 filas, 0 con "@").
- **20-ago, sección 07 (Seguridad/RLS) cerrada:** 11 funciones trigger con
  `EXECUTE` de `PUBLIC` corregidas de raíz (el `REVOKE` a roles específicos
  no bastaba, el grant real vivía en `PUBLIC`); `citext` movido a
  `extensions`; secrets de GitHub Actions configurados y CI verificado en
  verde con una corrida real.
- **20-ago, sección 08 (Frontend/Pipeline+Incidencias) cerrada:** 3 bugs
  reales corregidos corriendo la app en vivo con Playwright (login pegado
  por falta de `proxy.ts`, `/incidencias` vacío por permisos en
  `vw_embudo_diario`, grant de `anon` en la función nueva) — suite E2E
  permanente creada, disciplina de testing agregada a `AGENTS.md`/`CLAUDE.md`
  de ambos repos.
- **20-ago, sección 09 (Calendar) pausada por decisión explícita de
  Yeisiton:** código de integración ya completo; credenciales de Google
  Cloud (cuenta personal, Camino B) creadas; bloqueado en el share externo
  del calendario de Andrés (política de Workspace, requiere su Super Admin).
  Yeisiton pidió definir la arquitectura completa de Agenda antes de
  retomar el desbloqueo técnico.
- **20-ago, sección 10 (Roles) cerrada:** este proyecto corre bajo un
  **trueque** — Yeisiton+Gabyota (brazo tecnológico de su propia agencia
  emergente) profesionalizan la infraestructura de ARTF a cambio de
  mentoría comercial de Javier/Catalina. Admin de Yeisiton es temporal (se
  cede a Javier cuando el proyecto madure); rol Setter de Yeisiton y
  Gabyota es dogfooding deliberado, no su asignación permanente.
- **20-ago, sección 12 (Deuda técnica) — 3 de 5 patrones recurrentes
  cerrados de raíz en esta misma fecha:**
  1. Backfill de 263 `clientes.manychat_id` que quedaron con `.0` antes de
     que existiera el trigger normalizador (0 colisiones verificadas antes
     de tocar nada) + `CHECK` constraint (`clientes_manychat_id_solo_digitos`)
     para que sea estructuralmente imposible que se vuelva a colar por
     cualquier vía futura.
  2. Causa raíz real del grant `EXECUTE` a `anon` sobreviviendo un
     `CREATE OR REPLACE FUNCTION` (4 veces distintas: Fase 2, Fase 2b,
     18-ago, 20-ago): Supabase configura
     `ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT
     EXECUTE ON FUNCTIONS TO anon...` a nivel de proyecto, y `postgres` es
     el rol con el que se aplican las migraciones — corregido revocando ese
     mismo default para `anon` (una sola vez, para siempre hacia adelante).
  3. `fn_reunion_mueve_etapa`: en `INSERT` forzaba siempre `'agendado'` sin
     mirar `new.estado`, dejando leads mal parados cuando una reunión se
     insertaba directo en estado terminal (import histórico). Corregido
     reusando el mismo mapeo que ya existía para `UPDATE`.
  - Patrón restante (vistas sin `security_invoker`): ya cerrado desde antes
    vía el test de regresión existente, no requiere código nuevo. Patrón de
    Sheet-vs-Supabase en paralelo: no es un fix de código, es completar el
    corte del Sheet ya planeado — pendiente definir el criterio exacto de
    corte (sección 05).

**Sesión 19-ago-2026 (segunda) — `audit_18ago.py` corrido por primera vez,
15 incidencias marcadas en el panel real, políticas reafirmadas con
Yeisiton:**
- Se ejecutó `audit_18ago.py` (dejado a medio terminar por Antigravity el
  18-ago, nunca corrido) contra la base real y el export del Sheet del
  18-ago 6pm. Antes de confiar en sus resultados se encontraron y
  corrigieron 3 bugs propios del script: (1) seleccionaba
  `reuniones.cliente_id`, columna inexistente (400 de Postgres); (2)
  comparaba `str(manychat_id)` contra una lista con valores `None` crudos,
  generando falsos positivos de "ganado sin venta" para cualquier lead sin
  ManyChat ID — detectó como falso positivo a "Cesar Martínez", verificado
  con SQL directo que su venta sí estaba registrada ($4.968.000, cobrada);
  (3) una referencia rota (`cli_dict`/`mcid_dict`) tras el fix anterior.
  Ruff limpio tras los 3 fixes.
- **Resultado verificado de las 4 secciones:**
  1. Activity Log: Sheet 7.730 filas vs Supabase 14.010 — abierto,
     probablemente explicado por el bridge en vivo escribiendo directo desde
     el 18-ago, no investigado a fondo.
  2. 133 sin ManyChat ID: 100% (133/133) hacen match por nombre contra un
     cliente real ya existente en Supabase con manychat_id. **Decisión de
     Yeisiton: mantener NULL**, no backfillear (riesgo de falso match por
     nombre duplicado, reafirma la política del 15-ago).
  3. Financiero: único caso real pendiente sigue siendo "Juan Manuel" (mismo
     gap documentado desde el 13-ago, lead en estado `Ganado (Venta)` con 0
     filas en `ventas`, sin fecha de pago real).
  4. 15 conflictos "realizada" (Supabase) vs "No show"/"canceló" (Sheet,
     export 18-ago): **decisión de Yeisiton: marcarlos como incidencia, no
     resolver ahora.** Escrito `INCIDENTE_REVISION:` en `gestion_leads.notas`
     de los 15 leads correspondientes (matched por `manychat_id`, texto con
     sufijo `.0` en Supabase — mismo patrón de bug de float-de-Excel de
     sesiones anteriores), verificado con un SELECT posterior a
     `vw_scorecard_check` que las 15 aparecen bajo `requiere_revision_manual`.

**Sesión 19-ago-2026 — reconciliación completa Sheet-vs-Supabase, 1
vulnerabilidad financiera crítica encontrada y corregida, adopción de
tooling determinista (ruff/pytest/pre-commit/CI):**
- Reconciliación determinista (script propio `reconciliar_18ago.py`, NO
  análisis con LLM — comparación programática campo por campo, por decisión
  explícita de Yeisiton: "necesito algo determinista"). Corrigió 198 números
  de WhatsApp corruptos desde la migración original (bug del float de Excel
  dejando un `.0` de más al sanitizar), 14 leads históricos de la "Gaby
  vieja" (setter ya no activa) atribuidos por error a Andrew — hueco
  sistemático real, no puntual: el proceso nunca resincroniza cambios
  manuales de Setter/Closer hechos en el Sheet después de la captura inicial,
  y sigue existiendo hacia adelante mientras Sheet y bridge corran en
  paralelo. 9 closers restaurados, 23 estados corregidos (incluye un bug de
  diseño real documentado no corregido: `fn_reunion_mueve_etapa` solo
  reacciona a *cambios* de estado en `reuniones`, no a inserts masivos que ya
  nacen en `no_show`/`realizada`). 167 leads nuevos importados.
- **Vulnerabilidad financiera crítica encontrada y corregida:**
  `fn_registrar_venta` (crea ventas) era ejecutable con la llave pública
  `anon` — su propio código saltaba la validación de autorización cuando no
  hay JWT, exactamente la condición de `anon`. Cualquiera con la llave
  pública podía haber creado ventas falsas para cualquier lead. Encontrado
  vía `get_advisors` (linter oficial de Supabase, no la función de
  diagnóstico casera del agente). También se corrigieron 6 funciones sin
  `search_path` fijo y 2 vistas preexistentes sin `security_invoker`
  (`vw_scorecard_check_resumen`, `vw_ventas_neto` — esta última causaba que
  cualquier setter/closer viera discrepancias de ventas ajenas).
- **`vw_embudo_diario` (métricas de toda la empresa):** no se le puede poner
  `security_invoker=true` sin romperla en silencio para no-admins (es un
  agregado cruzando todos los closers/setters, no una fila por usuario). Se
  envolvió en `fn_embudo_diario()` (mismo patrón que `fn_registrar_venta`:
  chequeo de `fn_es_admin()` adentro), se quitó el SELECT directo a la vista
  para `authenticated`.
- Venta real registrada a mano con plan de pagos custom: Edwar Martos,
  $5.000.000 COP, términos acordados directamente por Andrés —
  `fn_registrar_venta` solo sabe repartir el saldo en cuotas iguales, no un
  plan custom.
- **Tooling determinista adoptado** (decisión de Yeisiton, fundamentada por
  el agente): `pyproject.toml` compartido (ruff + pytest) en la raíz del
  repo — NO aplicado a El Prospector (fuera de alcance). Lógica compartida de
  los scripts ARTF extraída a `artf_common.py` (antes duplicada en 3
  scripts — así se coló el bug del WhatsApp). 21 tests nuevos en
  `Tarea_1_Migrar_DB/tests/` (`test_artf_common.py` +
  `test_invariantes_schema.py` — verifica contra la base real que ninguna
  vista pierda `security_invoker` ni ninguna función SECURITY DEFINER gane
  acceso de `anon`, vía `fn_diagnostico_seguridad()`, solo accesible por
  `service_role`). Pre-commit hooks bloqueantes instalados y probados en
  ambos repos. GitHub Actions creados en los 2 repos (el de ARTF necesita 2
  secrets configurados a mano por Yeisiton en GitHub para correr los tests de
  invariantes de seguridad).
- **Política de migraciones versionadas desde esta fecha:** cada migración
  nueva contra Supabase se guarda también como `.sql` en
  `artf-pipeline-app/supabase/migrations/`. No se reconstruyó el historial
  anterior — empieza con `fn_embudo_diario_admin_gated`.
- Commits: `estudio_skills_ia_claude` `703f0ff` (rama
  `setup/base-conocimiento`), `artf-pipeline-app` `91d49d8` (rama `master`).

**Sesión 18-ago-2026 — bridge Cloudflare→Supabase confirmado en vivo, 3
fixes reales enviados a producción, revisión del reporte de Antigravity:**
- Antigravity usado por primera vez para el caso de uso acordado
  (clasificación de las 269 incidencias de `vw_scorecard_check`) — reporte
  verificado sin alucinaciones contra la base real.
- `worker_bridge_supabase_NUEVO_paralelo.js` (el worker "no desplegado
  aún" de la nota del 15-ago) ya desplegado y escribiendo en vivo a
  Supabase — sigue en modo paralelo/sombra, el Sheet sigue siendo la fuente
  oficial mientras se valida.
- Bug real encontrado y corregido: `gestion_leads.palabra_clave_ad` nunca
  se llenaba (ni el Worker ni `fn_sync_bot_turn` la calculaban) — no era una
  regresión nueva, ya estaba roto en el Sheet. Fix: nueva función
  `fn_derivar_palabra_clave()`, backfill de ~5.200 leads existentes,
  `fn_sync_bot_turn` ahora la deriva automáticamente hacia adelante.
- Gap estructural real y activo encontrado: no existía ningún mecanismo
  para que un setter humano reclamara un lead — todo lead nuevo entra con
  `setter_id = Andrew` (el bot) por diseño, nada lo reasignaba después, y por
  RLS eso significaba que ningún lead capturado por el bridge en vivo sería
  visible jamás para un setter real. Fix: RPC `fn_reclamar_lead(uuid)`
  (SECURITY DEFINER, bloquea robarle el lead a otro setter humano), botón
  "Tomar este lead" en el Pipeline, extensión del trigger de auditoría a
  reasignaciones de `setter_id`.
- Bug de seguridad propio cometido y corregido en la misma sesión:
  `fn_reclamar_lead` quedó con grant `EXECUTE` a `anon` por default de
  Postgres al crearla — revocado, mismo patrón de disciplina que Fase 2b.
- Mecanismo de "reconocer" incidencias en vez de ocultarlas para siempre:
  nueva tabla `incidencias_reconocidas` — panel bajó de 269 → 127
  incidencias reales tras reconocer 142 filas de deuda histórica de la
  migración.

**Sesión 17-ago-2026 (continuación) — Fase 2b: página pública de
agendamiento (corrige el modelo de reserva de la Fase 2) + instalación de
Playwright + adopción de Antigravity CLI como herramienta complementaria:**
- **Corrección de modelo tras probar la Fase 2 en vivo:** Yeisiton revisó la
  Agenda de la Fase 2 (setter reserva directo por el lead) y corrigió la
  premisa — el flujo real es que **el lead se agenda solo con un link único**
  contra los espacios reales del closer (como hoy con Google, pero dentro de
  la app), y el setter solo agenda manualmente como respaldo. Esto también
  resuelve de raíz el 96% de `clientes.correo` vacío: ahora el lead lo
  escribe él mismo al agendarse, así que el evento de Calendar por fin
  invita por correo real — decisión que también hizo correo obligatorio en
  el flujo de respaldo del setter (antes era opcional).
- **Construido:** tabla `enlaces_agenda` (token único por lead), página
  pública `/agendar/[token]` sin login (Server Component + server action con
  cliente `service_role`, nunca expuesto al navegador), botón "Generar link
  de agenda" en el Pipeline, y la extensión del flujo de respaldo del
  setter con correo obligatorio. Tres RPCs de la Fase 2
  (`fn_reservar_espacio`, `fn_marcar_incidente_calendar`,
  `fn_registrar_evento_calendar`) se relajaron para aceptar llamadas sin JWT
  de usuario (mismo patrón que ya usaba `fn_columnas_por_rol` para el
  Worker/Bridge), y se agregó `fn_actualizar_contacto_lead` nueva.
- **Hallazgo de seguridad crítico durante la construcción (Task 2):** la
  relajación de las RPCs para aceptar `service_role` sin querer también dejó
  la puerta abierta a `anon` — `fn_reservar_espacio` tenía un grant
  explícito a `anon` desde que se creó en la Fase 2 (nunca revocado, un
  `CREATE OR REPLACE FUNCTION` no resetea grants), lo que habría permitido
  que cualquiera con la llave pública `anon` llamara la función directo vía
  PostgREST, saltándose por completo la validación del token de la página
  pública. Corregido y reverificado con `has_function_privilege()` sobre las
  4 funciones y las 4 credenciales (anon/public/authenticated/service_role).
- **Segundo hallazgo real durante la construcción (Task 6):** la ruta
  pública devolvía mensajes crudos de Postgres a un visitante sin
  autenticar (podían incluir el uuid interno de un lead) — corregido a
  mensajes genéricos, salvo el único caso útil de traducir
  ("ese espacio ya no está disponible").
- **Revisión final de todo el branch (con el modelo más capaz):** encontró 3
  hallazgos Importantes reales — (1) el middleware bloqueaba a staff
  autenticado de abrir sus propios links generados (un solo flag booleano
  compartido para dos propósitos distintos), (2) `fn_actualizar_contacto_lead`
  no tenía ningún chequeo de ownership (cualquier setter podía sobreescribir
  el correo de cualquier lead), (3) un supuesto hueco de doble-reserva entre
  el flujo público y el manual — este último se **investigó y se refutó con
  una prueba real en vivo**: el índice único `uq_reunion_activa_por_lead`
  (ya existente desde la Fase 2) ya impide exactamente ese escenario, probado
  reservando dos veces el mismo lead y confirmando el rollback limpio. Los
  otros dos sí eran reales y se corrigieron.
- **Verificado de punta a punta con navegador real** (Playwright, instalado
  esta sesión): closer crea un espacio real → setter genera el link desde
  el bot del Pipeline → una sesión sin cookies abre el link → llena
  correo/WhatsApp → confirma → reabrir el mismo link muestra "ya no
  disponible" → la base confirma que el correo quedó guardado. Mergeado y
  pusheado a `master` (16 commits).
- **Adopción de Antigravity CLI** (herramienta de Google, `agy`, ya
  instalada y probada en esta máquina — modelos Gemini 3.1 Pro entre otros)
  como complemento, no reemplazo: 3 casos de uso acordados (auditoría masiva
  de artefactos históricos grandes, clasificación de las 268 incidencias
  WARN como insumo de diseño, segunda opinión independiente en migraciones
  sensibles). El análisis de audios/reuniones sigue siendo por NotebookLM,
  no por Antigravity. Decisión + guía de prompting oficial de Gemini 3.1 Pro
  guardadas en memoria persistente para futuras sesiones.
- **Pendiente para Yeisiton:** revisar 8 filas reales de `disponibilidad_closer`
  encontradas durante la verificación (probablemente su propia exploración
  del servidor local que quedó corriendo) — no se tocaron, quedan para que
  él decida si son válidas o se limpian.

**Sesión 16/17-ago-2026 — Fase 2: Agenda de closers construida, revisada y
mergeada a `master` (`artf-pipeline-app`), incluye un hallazgo crítico
corregido antes de producción:**
- **Pedido de Yeisiton:** seguir con el Formulario Dashboard, ahora la
  Agenda (espacios de disponibilidad de los closers + reserva por el
  setter + evento real de Google Calendar). Se siguió el proceso completo:
  brainstorming (arquitectónico) → spec escrito y commiteado
  (`docs/superpowers/specs/2026-08-16-agenda-closers-design.md`) → plan de
  11 tareas (`docs/superpowers/plans/2026-08-16-agenda-closers.md`) →
  ejecución con `subagent-driven-development` en un worktree aislado
  (`agenda-closers`, ya eliminado tras el merge).
- **Decisiones de diseño clave, todas verificadas antes de asumirlas:** la
  API de Google Calendar NO expone la configuración de "Appointment
  Schedules" (confirmado por búsqueda directa, no hay `eventType` para
  eso) — por eso Supabase (`disponibilidad_closer`, tabla nueva) es la
  fuente de verdad de los espacios, no Calendar. El 96% de `clientes.correo`
  está vacío (6.228/6.468, verificado con `execute_sql`) porque hoy el
  lead escribe su correo en el momento en la página pública de Google, que
  nunca se sincroniza al CRM — por eso el evento nuevo se crea sin
  invitado, y la app solo muestra el link de Meet para reenviar por
  Instagram/WhatsApp. Toda la agenda real corre hoy sobre la cuenta única
  de Andrés (confirmado por Yeisiton), así que se descartó Domain-Wide
  Delegation por closer — basta una cuenta de servicio con el calendario
  de Andrés compartido (prerequisito externo, sección 7 del spec, aún
  pendiente).
- **Construido:** tabla `disponibilidad_closer` + RLS; RPCs transaccionales
  `fn_reservar_espacio` (compare-and-swap atómico) y `fn_cancelar_reunion`
  (con trigger de reapertura del espacio si su hora no pasó); cliente de
  Google Calendar (`googleapis`, cuenta de servicio); el primer *server
  action* de la app (`src/app/agenda/actions.ts` — necesario porque
  necesita un secreto que nunca debe llegar al navegador); UI completa por
  rol (Closer: "Mi disponibilidad"; Setter: "Espacios abiertos"; Admin:
  "Cobertura"). Si la creación del evento de Calendar falla, la reserva en
  Supabase queda firme y se marca `INCIDENTE_REVISION:` para revisión
  manual — no se pierde el cupo de un lead ya calificado por una falla
  transitoria de Google.
- **Bugs reales encontrados y corregidos durante la construcción** (todos
  con evidencia real contra el proyecto Supabase `lrdtjsxtaadpgrzkchlw`,
  ninguno adivinado): colisión de nombres de columna en
  `fn_reservar_espacio` (`RETURNS TABLE` generaba parámetros OUT que
  chocaban con columnas homónimas, error 42702); el script de verificación
  necesitó un *fixture* QA reutilizable en vez de un lead nuevo por corrida
  porque `activity_log` es append-only con FK RESTRICT hacia
  `gestion_leads`/`clientes` (cualquier lead tocado queda permanentemente
  imborrable).
- **Hallazgo crítico de la revisión final de todo el branch (con el modelo
  más capaz), que ninguna revisión por-tarea podía detectar:** el mecanismo
  `INCIDENTE_REVISION:` escribía solo en `reuniones.notas`, pero la vista
  real de Incidencias (`vw_scorecard_check`) SOLO revisa
  `gestion_leads.notas` con match de prefijo — es decir, **el 100% de las
  reservas de producción de hoy (mientras el prerequisito de Google siga
  pendiente) habrían quedado con un incidente invisible, sin aparecer en
  ningún lado de la app.** Corregido para escribir también (como prefijo
  real) en `gestion_leads.notas`. Segundo hallazgo crítico: `fn_reservar_espacio`
  nunca asignaba `gestion_leads.closer_id` (solo `reuniones.closer_id`),
  lo que dejaba en blanco la columna "Closer" del Pipeline y le quitaba al
  closer la visibilidad RLS sobre su propia reunión — corregido.
- **Hallazgo de seguridad encontrado en la re-revisión del fix anterior,
  confirmado con Yeisiton antes de tocarlo:** dos funciones
  (`fn_marcar_incidente_calendar`, `fn_registrar_evento_calendar`) no
  tenían ningún control de autenticación y `EXECUTE` estaba otorgado
  incluso a `anon` (rol sin sesión) — cualquiera con la llave pública
  anon podía sobreescribir `gestion_leads.notas` de cualquier lead
  adivinando un `reunion_id`. Corregido exigiendo rol operativo
  (setter/closer/admin autenticado) y revocando el `EXECUTE` de `anon`.
- **Todo verificado de forma independiente contra la base real** (no solo
  confiando en los reportes de los subagentes) y con
  `scripts/verify-agenda.mjs` (11 aserciones, incluida una nueva que
  ejercita el incidente vía RLS con la cuenta real del setter, no solo con
  `service_role`). Mergeado a `master` y pusheado a `origin/master`
  (commits `f55f8d5..4e22ef9`).
- **Pendiente, fuera de alcance de IA:** (1) prerequisito externo — Andrés
  debe compartir su calendario de Google con la cuenta de servicio (spec
  §7); hasta entonces todo evento real de Calendar caerá en el fallback
  `INCIDENTE_REVISION:` (que ahora SÍ es visible en `/incidencias`). (2)
  Prueba manual de clic-por-clic en `/agenda` — no hay Playwright instalado
  en este repo (decisión explícita de Yeisiton en la Fase 1 de no instalar
  herramientas fuera de su entorno), así que solo la capa de datos/RPC
  quedó verificada de forma automatizada.

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

**Sesiones 22 a 27-ago-2026 (resumen) — Dashboards por rol + Super Botones
ManyChat + investigación Feature 2 (extracción LLM):**
- **22-ago:** Dashboard dedicado del Setter (`SetterPipelineBoard`, 5 estados
  propios) — Yeisiton (setter+admin) hace dogfooding deliberado del rol.
- **24-ago:** Módulo Closer (`CloserPipelineBoard`, 7 estados propios).
- **26-ago:** "Enviar Calendario" y "Vincular Reserva" como Super Botones —
  disparan flows reales de ManyChat (`/fb/sending/sendFlow`,
  `/fb/subscriber/removeTagByName`) desde Server Actions con contrato de
  resiliencia fijo: el `UPDATE`/RPC de Supabase manda siempre primero, un
  fallo de ManyChat nunca revierte la escritura ya hecha, la UI muestra
  toasts honestos (no éxito falso) vía discriminated unions.
- **27-ago:** "Devolver a Nuevo" (red de seguridad para un "Enviar
  Calendario" hecho por error) — mismo contrato de resiliencia, quita el tag
  `PENDIENTE_AGENDA` para apagar los Smart Delays. Verificado con
  Playwright + SQL directo, commit `1222ff7`, pusheado a `origin/master`
  con confirmación explícita.
- **27-ago — Investigación Feature 2 (extracción LLM antes de "Enviar
  Calendario"): BLOQUEADA, no se escribió código.** Petición original:
  usar un LLM para extraer profesión/salario/dolor de la conversación del
  lead antes de mandarle el calendario. Tres hallazgos cambiaron el
  diseño:
  1. **ManyChat no tiene endpoint para leer historial de conversación**
     (confirmado por investigación web, limitación documentada de la
     plataforma) — descarta llamarla en vivo desde el Server Action.
  2. **`activity_log` tampoco sirve hoy como fuente — causa raíz
     encontrada en el código real, no solo en los datos.** `fn_sync_bot_turn`
     sí tiene el parámetro `p_ultimo_msg_bot` (la tabla está diseñada para
     guardar ambos lados), pero al auditar `activity_log` completa (no solo
     el lead de prueba): de 1.050 turnos escritos en vivo por `worker_ia`,
     **0 tienen `ultimo_msg_bot` con contenido**, y `ultimo_msg_lead` solo
     en la mitad. Se leyó el Worker real que escribe esos turnos —
     `estudio_skills_ia_claude/03_Clientes_y_Casos/02_Cliente_ARTF/
     Scrips_Worker_and_AppScript/worker_bridge_supabase_NUEVO_paralelo.js`,
     desplegado como `setter-bridge-supabase` — y el `rpcPayload` que arma
     (líneas 120-130) **nunca incluye `p_ultimo_msg_bot`, ni tiene de dónde
     sacarlo**: es deliberado, no un bug — el bot conversacional está
     apagado (`JAVIT_ACTIVO=false`, ya documentado en la sesión 19-ago de
     este mismo archivo), este Worker solo hace "captura pasiva" del
     último mensaje del LEAD (`last_text` → `p_ultimo_msg_lead`); no existe
     ninguna respuesta de bot que reenviar porque hoy nadie (ni un bot
     propio ni Claude) le contesta al lead desde este pipeline — la
     conversación real ocurre dentro del flow nativo de ManyChat, fuera de
     cualquier código que controlemos. El único contenido real de
     conversación que existe en `activity_log` (5.259 `ultimo_msg_lead` /
     667 `ultimo_msg_bot`, origen `importacion`) viene del import histórico
     único del Sheet (`migrate_activity_log.py`, sección 19-ago arriba), no
     del pipeline en vivo. Verificado también contra el lead de prueba real
     de Yeisiton (IG personal, manychat_id `845096996`): solo 5 filas desde
     el 18-ago, ninguna con texto real (un `"Control"` suelto) —
     consistente con que esa cuenta solo tuvo conversaciones al azar, no
     siguiendo el playbook.
  3. **Modelo:** se descartó `openai/gpt-oss-120b` en Groq — bug
     documentado y sin resolver donde ignora `json_schema`/`strict:true`
     (foro oficial de Groq + issue abierto en `langchain-ai/langchain`).
     Recomendado en su lugar `qwen/qwen3.6-27b` en Groq (sí soporta
     `json_schema` estricto de forma confiable).
  - **Decisión de Yeisiton:** arreglar primero la tubería del bot antes de
    construir Feature 2, en otra sesión. **No es un fix de código simple**
    (el Worker no tiene de dónde sacar el mensaje del bot porque no hay
    bot conversacional corriendo hoy) — la pregunta arquitectónica real a
    resolver primero es si el flow nativo de ManyChat puede exponer el
    texto de su propia respuesta como variable hacia una acción "External
    Request" (investigar en la plataforma de ManyChat, no en este repo);
    solo si eso es posible tiene sentido extender
    `worker_bridge_supabase_NUEVO_paralelo.js` + `fn_sync_bot_turn` para
    capturarlo. Alcance de campos a extraer se mantiene en el pedido
    original (profesión, salario_mensual, dolor_principal) — NO se expande
    a endeudamiento %/Datacrédito del playbook V4.0
    (`03_Clientes_y_Casos/02_Cliente_ARTF/SOP Setter DM en Instagram
    V4.0.pdf`) por ahora.

## Próximos pasos — Inbound AI SDR

- [x] ~~Feature 2 (extracción LLM en "Enviar Calendario"): bloqueada~~ —
      desbloqueada e implementada 27-ago-2026 (Modal de Revisión IA,
      commit `65aad35`). Ver sesión "Feature 2 destrabada" arriba.
- [ ] **Aplicar en ManyChat: agregar la Solicitud externa hacia
      `setter-bridge-supabase` también en "Acciones #5"** del Flow único
      (rama del kill switch para leads existentes) — cambio de
      configuración en el dashboard de ManyChat, no de código, el fundador
      ya tiene acceso admin. Sin esto, `activity_log` sigue con 1 solo turno
      por lead y el Modal de Revisión IA abrirá vacío casi siempre. Ver
      sesión 27-ago-2026 (continuación) arriba para el detalle completo del
      Flow real (captura del fundador) y por qué este es el mecanismo.
- [ ] **Confirmar push de `artf-pipeline-app` a `origin/master`**
      (commit `65aad35`, Modal de Revisión IA + creación manual de leads
      con profesión/salario).

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

**Habeas Data (Ley 1581) — YA NO ES TEÓRICO.** El código ahora procesa y ha enviado correos a PII real (nombres y direcciones de decisores reales del piloto de M3/M4). El compliance real requiere asesoría legal con abogado real antes de cualquier envío a escala. Ver `outbound-prospector-app/docs/validacion/validacion-fuentes.md` §7 (ruta corregida 21-ago-2026: el repo se extrajo el 20-ago, ya no vive en `02_Lineas_de_Producto/`). **Este bloqueo se activa formalmente ahora que existe envío real, no solo diseño.**

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

## 🧠 Sesión 21-ago-2026 — Auditoría y corrección de la arquitectura de memoria

**Fecha:** 2026-08-21
**Módulo:** entorno
**Tipo:** decision
**Conclusión:** Se auditó el sistema de memoria completo (Skills de Kiro, MCP,
NotebookLM, jerarquía de verdad) y se ejecutaron las correcciones autorizadas por
el fundador: (1) rutas muertas corregidas en `handoff-cierre-sesion`,
`sincronizador-spec`, `AGENTS.md`, `contexto-proyecto.md`, `estrategia-memoria.md`,
`directrices_globales.md`, `03_protocolos_comunicacion.md`, `mvp-prospector-limpio.md`
y las citas internas de `outbound-prospector-app/docs/tecnico/` — todas apuntaban a
`02_Lineas_de_Producto/Outbound_Prospector/` (extraído el 20-ago); (2) MCP `memory`
retirado de `mcp.json` (grafo nunca alimentado, `{}` vacío, solapado con Graphify +
memoria de Claude — mismo criterio que el retiro del `decision_ledger` de Sheets del
24-jul); `memory-preload` reescrita como aviso de retiro, `cerrar-decision` ya no la
referencia; (3) duplicado eliminado de la librería NotebookLM
(`artf-arquitectura-actual-y-rol-1`); (4) Bug #4 de `notebooklm-mcp` diagnosticado
con causa raíz exacta (lista de frases de carga en español incompleta + heurística
de elipsis solo detectaba `...` ASCII, no `…` Unicode) y parcheado localmente en el
caché de `npx` — parche no verificado en vivo aún, requiere reinicio de la sesión de
Claude Code para que el proceso MCP recargue el archivo; (5) jerarquía de verdad de
`estrategia-memoria.md` extendida con un 6º nivel explícito para la memoria de
Claude Code; (6) `guia_configuracion_memoria_ia.md` marcada como plantilla genérica
histórica, no estructura vigente; (7) Outbound Prospector confirmado en pausa —
directriz inyectada en `contexto-proyecto.md` y en memoria de Claude: al reanudar,
Paso 1 es configurar su notebook de NotebookLM antes de tocar código.
**Fuentes:** verificación en vivo (`list_notebooks`, `get_health`, `ask_question`
×4, lectura directa de `.kiro/skills/*`, `.kiro/settings/mcp.json`), sesión de
auditoría de memoria 2026-08-21. Detalle completo →
`04_Segundo_Cerebro/guia_arquitectura_memoria.md`.
**Estado:** validado (ejecutado con autorización explícita del fundador). Pendiente
de confirmación por el fundador: eliminar `02_Lineas_de_Producto/Outbound_Prospector/`
(solo caché `__pycache__`/`.pytest_cache`/`.ruff_cache`, bloqueado por el
clasificador de seguridad de Claude Code, no ejecutado).

---

## 🧠 Sesión 21-ago-2026 (continuación) — verificación en vivo de la migración de cierre de deuda técnica (sección 12), pendiente desde el 20-ago

**Fecha:** 2026-08-21
**Módulo:** ARTF / Base de datos (`lrdtjsxtaadpgrzkchlw`)
**Tipo:** verificación
**Conclusión:** Los 3 puntos de la migración `20260821024645_cierre_deuda_tecnica_seccion_12_manychat_grants_reunion`
(aplicada el 20/21-ago, verificación en vivo bloqueada entonces por el clasificador
de auto-mode) se confirmaron correctos contra la base real, sin necesidad de tocar
nada — solo lectura:
1. **Backfill `manychat_id` + CHECK constraint:** `0` filas con sufijo `.0` sobre
   6.664 clientes con `manychat_id`; `clientes_manychat_id_solo_digitos` existe en
   `pg_constraint`.
2. **Grant `EXECUTE` a `anon` revocado a nivel de `ALTER DEFAULT PRIVILEGES` para el
   rol `postgres`** (el rol real que corre las migraciones): confirmado vía
   `pg_default_acl` — el ACL por defecto de `postgres` en `public` para funciones ya
   no incluye `anon` (`{postgres=X/postgres,authenticated=X/postgres,service_role=X/postgres}`).
   Corrida `fn_diagnostico_seguridad()`: `funciones_security_definer_con_anon: []`,
   `funciones_trigger_con_authenticated: []` — sin huecos nuevos. La única entrada en
   `vistas_sin_security_invoker` (`vw_embudo_diario`) es la excepción de diseño ya
   documentada y decidida el 19-ago (envuelta en `fn_embudo_diario_o_vacio()`), no un
   hallazgo nuevo.
3. **`fn_reunion_mueve_etapa` corregido:** `pg_get_functiondef` confirma que ahora
   resuelve `v_codigo` desde `new.estado` también en `INSERT` (antes forzaba
   `'agendado'` sin mirar el estado real) — coincide exacto con el fix descrito en la
   sesión del 20-ago.
**Fuentes:** `execute_sql` en vivo contra `lrdtjsxtaadpgrzkchlw` (4 queries de solo
lectura: conteo+constraint, `pg_default_acl`, `fn_diagnostico_seguridad()`,
`pg_get_functiondef`), `list_migrations` (confirma la migración aplicada).
**Estado:** cerrado. Sección 12 (Deuda técnica) queda 100% verificada, no solo
aplicada. Próximo paso en la ronda de arquitectura "Planos ARTF": sección 13.

---

## 🧠 Sesión 22-ago-2026 — 5 correcciones UX/rendimiento reales, encontradas probando `master` en navegador

**Fecha:** 2026-08-22
**Módulo:** ARTF / `artf-pipeline-app` (commit `8933e5e`, sobre `master`)
**Tipo:** corrección de bugs reales (no visibles en `type-check`/`lint`)
**Conclusión:** El fundador probó `master` (commit `3146272`) en el navegador real y
reportó 5 problemas de uso; los 5 se corrigieron, verificaron en vivo y quedaron
pusheados a `origin/master`:
1. **Token de `/agendar/[token]` de un solo uso (bug real):** `canjearTokenAgenda`
   marcaba `usado_en` en el primer GET -- un lead que abría el link en el celular y
   luego en el computador se encontraba con "link no disponible" sin haber
   agendado nada. Corregido a lectura pura: solo invalida si `expira_en` venció o
   si ya existe una fila real en `reuniones` (`agendada/confirmada/realizada`) para
   ese lead -- la reserva ya completada, no un flag de "abierto una vez". Migración
   `20260823021619_...` documenta el cambio de significado de `usado_en` (histórico,
   sin uso en la validación). Verificado en vivo: mismo token abierto 3 veces vía
   curl, las 3 con 307 real hacia Google.
2. **Pipeline cargaba 6.163+ leads de `nuevo` en memoria, congelaba el navegador:**
   `getPipelineLeads()` paginaba con `.range()` hasta traer TODO `vw_pipeline`. Un
   límite global habría dejado a `calificado`/`agendado` (2/152 filas reales) sin
   nada si `nuevo` acaparaba las primeras posiciones -- se cambió a un cap de 300
   leads más recientes POR ESTADO, en N consultas paralelas (una por
   `estados_lead.activo`), más rápido en reloj de pared que la paginación
   secuencial anterior.
3. **"Generar Enlace" pedía 2 clics:** `GenerarEnlaceModal` tenía un modal
   intermedio con checkbox "¿es reagendamiento?". Rediseñado a botón de acción
   directa -- 1 clic genera el token, copia al portapapeles y muestra toast. El TTL
   (24h/48h) ahora lo decide quien monta el componente vía prop `ttlHoras`, no una
   interacción del usuario.
4. **"Agendado" se podía devolver a "Nuevo" por error:** se quitó el botón "Volver
   a Nuevo" del tablero del Setter (`SETTER_BOTONES.agendado`) -- candado de UI,
   igual que el resto de restricciones de rol de este proyecto; `estado_transiciones`
   en la base sigue permitiendo `agendado→nuevo` a propósito (no se tocó).
5. **Percepción de "flicker" en el redirect:** investigado con medición real
   (`curl -w`) -- `/agendar/[token]` YA emitía un 307 HTTP genuino desde el Server
   Component (~400-500ms en dev con Turbopack, sin recompilar sería más rápido aún
   en producción), no una navegación cliente con HTML intermedio visible. No hizo
   falta ningún cambio de código; la percepción es explicable por overhead de dev
   más la carga de la propia landing de Google, fuera de control de este repo.
**Fuentes:** `execute_sql`/`apply_migration` en vivo contra `lrdtjsxtaadpgrzkchlw`
(token real con `reuniones.estado='agendada'` para confirmar el caso "ya
completó la reserva", inserción/borrado de un `enlaces_agenda` desechable para
medir timing), `curl -w` contra el dev server real, `npx playwright test` (suite
existente + una prueba temporal contra la cuenta fixture `setter.qa@artf.test`
para los fixes 3/4, borrada tras confirmar -- ver commit `8933e5e`).
**Estado:** cerrado y pusheado a `origin/master`. Los 3 bugs de test-selector
encontrados armando la prueba temporal (clic interceptado por el botón "Copiar"
anidado, overlay `z-40` de otro modal, `has-text("Nuevo")` ambiguo con "+ Nuevo
lead") eran de la prueba, no de la app -- documentado por si se reintroduce un
test similar más adelante.

---

## 🧠 Sesión 22-ago-2026 (continuación) — drawer del Setter 100% automático, limpieza de código muerto, 3 leads QA permanentes

**Fecha:** 2026-08-22
**Módulo:** ARTF / `artf-pipeline-app` (commit `5b17dd5`, sobre `master`)
**Tipo:** refactor operativo + auditoría proactiva + fixtures de QA
**Conclusión:** El fundador pidió una reestructuración del drawer del Setter para
que la fecha/hora de la llamada y la transición a "Agendado" dejen de ser
manuales -- responsabilidad exclusiva del Puente de Google Calendar -- más una
auditoría proactiva del código y 3 leads de prueba permanentes.
1. **Drawer simplificado por estado:** `Calificado` perdió su formulario
   (Nombre/WhatsApp/Correo/fechas) y el botón manual "Agendar" -- ahora solo
   muestra Identificación + "Esperando reserva en Google Calendar" (mensaje
   pasivo). `Agendado` perdió los `datetime-local` y los inputs de
   WhatsApp/Correo -- ahora son badges de solo lectura (WhatsApp/Correo desde
   `clientes`, fecha desde `reuniones.fecha_programada` vía
   `vw_pipeline.proxima_llamada`, NO `reunion_fecha_agendamiento` que es un
   campo distinto -- verificado contra `pg_get_viewdef`). `SETTER_BOTONES` se
   eliminó por completo de `estados.ts` -- sin consumidor real tras quitar los
   2 botones que le quedaban.
2. **⚠️ Caveat real encontrado, no corregido (fuera del alcance pedido):** "Datos
   sincronizados por Google" es el rótulo correcto para la fecha de la
   llamada, pero NO para WhatsApp/Correo -- `src/lib/google/sync.ts`
   (`procesarEvento`) usa el correo/teléfono parseados de la descripción del
   evento SOLO para hacer MATCH contra un cliente existente, nunca los
   escribe de vuelta en `clientes.whatsapp_e164`/`correo`. El badge muestra
   lo que ya hubiera en `clientes` antes del booking, no necesariamente lo
   último que el lead escribió en el Appointment Schedule de Google. Si se
   quiere que el badge refleje literalmente el dato de la reserva, hace falta
   un cambio aparte en `sync.ts` (decisión de arquitectura, no ejecutada sin
   confirmación).
3. **Auditoría proactiva:** cero `useEffect`/`any` en todo el frontend (nada
   que corregir ahí). Eliminado código 100% muerto del flujo de formulario
   propio pre-pivote (`AgendarForm.tsx`, `actions.ts`, y los exports
   huérfanos `getLeadParaAgendar`/`getEspaciosAbiertosPublico` en
   `agendar-publico.ts`) -- confirmado sin importador real desde
   `/agendar/[token]/page.tsx` (la ruta vigente desde el pivote a Google
   Calendar nativo). Corregido `BotonCopiar` en `SetterPipelineBoard.tsx`:
   `navigator.clipboard.writeText()` no estaba `await`ado ni con `.catch()`
   -- una promesa rechazada (permiso denegado) quedaba sin manejar mientras
   el toast decía "copiado" de todas formas.
4. **3 leads QA permanentes creados** (vía `fn_crear_lead_manual`, dueños de
   QA Setter): `TEST-Lead QA 1 (Nuevo)`, `TEST-Lead QA 2 (Multi-Tab)`,
   `TEST-Lead QA 3 (Bridge Sync)`, los 3 en estado `nuevo`. **Contradice
   directamente [[feedback_activity_log_blocks_test_data_purge]]** (decisión
   ya tomada esta misma sesión: reutilizar cuentas QA fixture, no crear más
   leads `TEST-` porque quedan indeletables para siempre en cuanto tocan
   cualquier flujo real) -- se le presentó la contradicción al fundador vía
   `AskUserQuestion` y confirmó explícitamente crearlos igual, aceptando que
   queden permanentes. Documentado para que quede claro que no fue un olvido
   de la restricción, sino una decisión consciente tomada con el trade-off
   sobre la mesa.
**Fuentes:** lectura completa de `SetterPipelineBoard.tsx`/`estados.ts`/
`sync.ts`/`agenda.ts`/`AgendaBoard.tsx`, `pg_get_viewdef('vw_pipeline')` en
vivo, `grep` de `useEffect`/`: any`/importadores de los archivos eliminados,
`fn_crear_lead_manual` vía `execute_sql` (rol `authenticated` + JWT claims de
QA Setter), 2 pruebas Playwright temporales contra `setter.qa@artf.test`
(Calificado sin formulario; Agendado con badges reales usando una reunión de
prueba insertada y borrada solo para la verificación), `type-check`/`lint`/
suite E2E existente -- todas en verde.
**Estado:** cerrado y pusheado a `origin/master`. Los 3 leads QA quedan
disponibles para pruebas en vivo del fundador, todos en `nuevo`.

---

## 🧠 Sesión 22-ago-2026 (continuación) — enriquecimiento de contacto desde Google Calendar, sin fusión frágil de nombre

**Fecha:** 2026-08-22
**Módulo:** ARTF / `artf-pipeline-app` (commit `9d5f86c`, sobre `master`)
**Tipo:** feature aprobada + decisión de diseño
**Conclusión:** El fundador aprobó explícitamente el caveat señalado en la sesión
anterior (WhatsApp/Correo del badge de Agendado no se actualizaban desde el
booking real) y pidió además resolver el cruce de nombre Instagram vs. Calendar
sin un simple `==` frágil.
1. **`sync.ts` ahora enriquece `clientes.correo`/`whatsapp_e164`** al matchear un
   booking real -- el campo usado como llave de match nunca se pisa (ya es
   igual por definición); el otro campo se llena si estaba vacío o se
   actualiza si cambió, con un `console.warn` cuando pisa un valor existente
   (auditable, nunca silencioso).
2. **Nombre: decisión de diseño explícita, NO fuzzy-matching.** Se descartó
   cualquier heurística de similitud (Levenshtein, umbral, etc.) porque es
   exactamente el tipo de comparación frágil que el fundador pidió evitar --
   un apodo/emoji de IG puede diferir arbitrariamente del nombre real
   tecleado en Calendar sin dejar de ser la misma persona (el match real ya
   lo resuelve correo/teléfono, nunca el nombre). Se guardan AMBOS como
   hechos independientes en vez de fusionar: nueva columna
   `reuniones.nombre_google` (booking-scoped, no se concilia contra
   `clientes.nombre`), expuesta en `vw_pipeline` como `reunion_nombre_google`
   y mostrada en el drawer de Agendado como "Nombre en Calendar" solo cuando
   difiere de verdad del nombre de Instagram (comparación normalizada
   puramente de UI, nunca de integridad de datos -- el peor caso de un falso
   negativo es una línea de más, no una corrupción).
**Fuentes:** migración `reuniones_nombre_google_y_vw_pipeline` aplicada en vivo,
`type-check`/`lint`/suite E2E existente en verde, smoke test real de
`/api/cron/sync-calendar` (200 OK, `procesados:0` -- sin eventos nuevos, pero
confirma que el código nuevo no rompe el endpoint real).
**Estado:** cerrado y pusheado a `origin/master`. Pendiente: el fundador probará
en vivo con los 3 leads QA de la sesión anterior.

---

## 🧠 Sesión 23-ago-2026 — auditoría E2E real con cuenta de staff (Yuli), 403 diagnosticado, badges duplicados de Agenda corregidos

**Fecha:** 2026-08-23
**Módulo:** ARTF / `artf-pipeline-app` (commit `ef99ffd`, sobre `master`)
**Tipo:** diagnóstico + corrección real, verificado con Playwright contra la
cuenta real de Yuli (`gaby318jaramillo@gmail.com`, rol setter) -- credenciales
pasadas por variable de entorno en la corrida, nunca escritas a ningún archivo
commiteado (regla de `AGENTS.md`).
1. **403 en `fn_reclamar_lead`: NO era un problema de permisos.**
   `has_function_privilege` confirmó que `authenticated` YA podía ejecutar la
   función. La causa real: los 3 leads QA (creados la sesión anterior) tenían
   `setter_id` = QA Setter -- cuando Yuli (setter real, distinto usuario)
   intentaba reclamarlos, la función correctamente bloqueaba con "ya fue
   reclamado por otro setter" (42501/403 real, no un bug). Se reseteó
   `setter_id = null` en los 3 leads QA. Además, confirmado que la
   arquitectura que el fundador proponía ("generar enlace = reclamar +
   mover a Calificado automáticamente") YA estaba implementada desde la
   sesión anterior (`SetterPipelineBoard.tsx`, `onAntesDeGenerar`/
   `onGenerado`) -- no hizo falta ningún cambio de código, solo el reset de
   datos. Verificado en vivo con Yuli: RPC 2xx, toast, lead pasa a
   Calificado con `setter_id` = Yuli.
2. **Badges duplicados en `/agenda` (hallazgo real, encontrado con datos en
   vivo):** 186 reuniones `realizada` + 26 `no_show` (todas de antes del
   puente de Google Calendar) nunca tuvieron `google_event_id` -- el badge
   "Pendiente" solo miraba esa columna, mostrándose junto al badge de
   estado ya resuelto. Corregido en `AgendaBoard.tsx` (Pendiente solo si
   `estado === 'agendada'`) y en `agenda.ts` (`getReunionesProximas` ya no
   trae las 276 reuniones no-canceladas sin filtro/límite ordenadas por
   fecha ascendente -- ahora solo `estado IN (agendada, confirmada)`,
   excluyendo también `reprogramada` a propósito por estar superada).
3. **Redirección de `/agendar/[token]` re-verificada:** 307 real,
   300-450ms, multi-apertura confirmada con la cuenta real de Yuli
   (incluida navegación en pestañas nuevas simulando incógnito).
4. **Pendiente de decisión (NO ejecutado, solo diagnosticado):** el
   fundador señaló que el link generado "se ve extraño" para compartir --
   confirmado que el token es un UUID completo de 36 caracteres
   (`gen_random_uuid()` por defecto en `enlaces_agenda.token`). Acortarlo a
   un slug corto tipo base62 es una opción real pero implica cambiar el
   default de la columna y la generación -- no se ejecutó sin confirmación
   explícita, queda como recomendación pendiente de aprobar.
**Fuentes:** `has_function_privilege`/`pg_get_functiondef` en vivo, reset de
`setter_id` vía SQL, 3 pruebas Playwright temporales contra la cuenta real de
Yuli (flujo completo Nuevo→Generar enlace→Calificado→TTL multi-apertura;
badges de Agendado con una reserva simulada por SQL fiel a `procesarEvento()`
de `sync.ts`; `/agenda` sin duplicados), las 3 borradas tras confirmar (una
quedó momentáneamente sin borrar por error propio, corregido antes de
cualquier commit -- nunca contenía credenciales literales, solo
`process.env`), `type-check`/`lint`/suite E2E oficial en verde.
**Estado:** cerrado y pusheado a `origin/master`. `TEST-Lead QA 1` queda en
`Agendado` como evidencia visual del flujo completo funcionando (badges
reales incluidos); `TEST-Lead QA 2`/`QA 3` quedan limpios en `nuevo` para que
el fundador corra su propia prueba de punta a punta.

---

## 🧠 Sesión 23-ago-2026 (continuación) — pivote a link directo de Google (sin token propio), riesgo real de baneo de Instagram

**Fecha:** 2026-08-23
**Módulo:** ARTF / `artf-pipeline-app` (commit `dbbd37b`, sobre `master`)
**Tipo:** pivote arquitectónico aprobado, decisión de negocio explícita
**Conclusión:** El fundador reportó que el link generado (`/agendar/[token]`,
nuestro dominio + UUID de 36 caracteres) se veía como spam/phishing al
compartirlo por DM de Instagram -- riesgo real de baneo de la cuenta de
Instagram del negocio. Decisión: `GenerarEnlaceModal` ya no crea ningún token
propio -- copia directo `NEXT_PUBLIC_GOOGLE_APPOINTMENT_URL`
(`calendar.app.google/...`, el mismo dominio corto y confiable de Google que
ya usaba el redirect del lado del servidor).
- Se agregó `NEXT_PUBLIC_GOOGLE_APPOINTMENT_URL` a `.env.local` (mismo valor
  que `GOOGLE_APPOINTMENT_SCHEDULE_URL`) -- **pendiente agregarla también a
  las variables de entorno de producción**, el fundador debe hacerlo (no
  soy yo quien administra ese panel).
- `sync.ts` NO necesitó cambios: el match real de un booking siempre fue por
  correo/teléfono que el lead escribe en el propio formulario de Google, no
  por el token -- se confirmó explícitamente que sigue intacto.
- **Decisión consultada y confirmada por el fundador vía `AskUserQuestion`:**
  `/agendar/[token]`, `agendar-publico.ts` y la tabla `enlaces_agenda`
  (con su TTL y el bloqueo de reapertura tras completar la reserva) quedan
  funcionales pero sin ningún botón que las use desde este flujo -- NO se
  borraron, por si más adelante hace falta un link con TTL para otro canal
  (ej. email).
- **403 en `fn_reclamar_lead` de la sesión anterior: causa raíz confirmada.**
  No era un problema de permisos (`has_function_privilege` ya daba `true`
  para `authenticated`) -- eran los leads QA con `setter_id` de otra cuenta
  (mío, de crearlos) bloqueando correctamente a Yuli. Los 4 leads de prueba
  (`TEST-Lead QA 1/2/3` + `TEST-Yeisiton Bridge Verify`) quedaron en `nuevo`
  con `setter_id = NULL`.
**Fuentes:** lectura de `.env.local` (valor público, no sensible -- es el
link de reserva que se comparte con leads), edición de `GenerarEnlaceModal.tsx`
(quitado el INSERT a `enlaces_agenda` y el prop `leadId`/`ttlHoras` sin uso),
prueba Playwright temporal contra la cuenta fixture QA Setter confirmando que
el portapapeles recibe la URL exacta de Google y que ya no se inserta en
`enlaces_agenda`, `type-check`/`lint`/suite E2E oficial en verde.
**Estado:** cerrado y pusheado a `origin/master`. Pendiente del fundador:
agregar la variable de entorno en producción antes del próximo deploy.

---

## 🧠 Sesión 23-ago-2026 (continuación) — Candado de Validación de Reservas: vinculación manual determinística, cierra la brecha de datos investigada

**Fecha:** 2026-08-23/24
**Módulo:** ARTF / `artf-pipeline-app` (commit `ce4e6e4`, sobre `master`)
**Tipo:** pivote de arquitectura aprobado, implementación completa
**Conclusión:** Respuesta directa a la brecha investigada la sesión anterior
([[artf_formulario_dashboard_status]]-adjacente, ver informe de investigación):
casi ningún lead de Instagram tiene correo/teléfono antes de agendar, así que
el match automático de `sync.ts` fallaba para la mayoría de bookings reales.
El fundador diseñó "el Candado": en vez de adivinar (prohibido
explícitamente -- ni ventanas de tiempo, ni similitud de nombre), la
reunión que no matchea se guarda "flotante" y el Setter la reconoce y
vincula a mano al mover Calificado -> Agendado (el mismo empujón obligatorio
que ya se usaba para "Generar Enlace" -- "dos pájaros de un tiro").
1. **Esquema:** `reuniones.gestion_lead_id` pasa a nullable (una reserva
   flotante no tiene lead todavía); nuevas columnas
   `correo_google`/`telefono_google` (datos crudos del booking, solo
   relevantes mientras sigue flotante).
2. **RLS:** `pol_re_select` se reescribió para exponer reuniones sin dueño
   a cualquier setter/closer/admin -- un sandbox test confirmó que la
   política vieja las escondía por completo (el `EXISTS` contra
   `gestion_leads` nunca matchea `NULL`), lo habría dejado el modal vacío
   en producción si no se hubiera probado antes.
3. **`fn_vincular_reserva_flotante`** (RPC transaccional, todo o nada): liga
   la reserva, actualiza `clientes.correo`/`whatsapp_e164` con los datos
   reales de Google, avanza el lead a `agendado`. Exige `calificado` y
   ownership (setter dueño o admin).
4. **Bug real encontrado en desarrollo, antes de tocar frontend:** la
   función declaraba `v_estado_agendado_id` como `uuid` --
   `estados_lead.id`/`gestion_leads.estado_id` son `integer`. Atrapado por
   el sandbox test (`SET LOCAL ROLE` + `SAVEPOINT`/`ROLLBACK`,
   `"invalid input syntax for type uuid: '4'"`), corregido en una segunda
   migración antes de escribir una sola línea de frontend.
5. **`VincularReservaModal.tsx`:** reemplaza el mensaje pasivo de
   Calificado -- lista corta de reservas sin vincular (Nombre/Correo/
   WhatsApp/Fecha reales de Google), selección en 2 pasos (elegir +
   confirmar, no 1 clic como "Generar Enlace" -- vincular la reserva
   equivocada mezcla la identidad de 2 leads reales y no hay deshacer).
**Nota de entorno:** el plugin `chrome-devtools-mcp` recién instalado no
tiene binario de Chrome disponible en este sandbox Linux (WSL sin GUI) --
la verificación real se hizo con Playwright (Chromium embebido, ya probado
toda la sesión), no con chrome-devtools. Vale la pena confirmarlo en un
entorno con Chrome real antes de asumir que chrome-devtools funciona acá.
**Fuentes:** investigación previa de la sesión (playbook del bot, esquema
real vía `information_schema`/`pg_policies`/`pg_trigger`/
`pg_get_functiondef`), sandbox SQL con `SAVEPOINT`/`ROLLBACK` (happy path +
guard de ownership + el bug de tipos), prueba Playwright temporal contra
`setter.qa@artf.test` cubriendo el flujo completo end-to-end, `type-check`/
`lint`/suite E2E oficial en verde.
**Estado:** cerrado y pusheado a `origin/master`. `TEST-Lead QA 1` queda en
`Agendado` con datos reales de la vinculación (prueba visual); `TEST-Lead QA
2` queda en `Calificado` con 1 reserva flotante sin vincular
("Andres Multi Tab") lista para que el fundador pruebe el modal él mismo.

---


## 🧠 Sesión 24-ago-2026 — hipótesis de crash de teléfono descartada, cron real encontrado ausente, auditoría de Pipeline

**Fecha:** 2026-08-24
**Módulo:** ARTF / `artf-pipeline-app` (commits `2ade053`, `96d3048`, sobre `master`)
**Tipo:** investigación + corrección real, 3 issues pedidos
**Conclusión:** El fundador confirmó en vivo que el Candado de Validación de
Reservas de la sesión anterior YA funciona -- probó él mismo con su cuenta
real y con QA Setter (evidencia: `TEST-Lead QA 1`/`QA 2` y
`TEST-Yeisiton Bridge Verify` aparecieron movidos por la sesión anterior sin
que yo los tocara). Pidió 3 correcciones más:
1. **Hipótesis de "crash por teléfono" descartada con evidencia, no
   aceptada de entrada** (pedido explícito: "no la tomes como la fuente de
   la verdad"). Verificado en vivo con `node -e` directo contra
   `parsePhoneNumberFromString`: nunca lanza excepción para ningún input.
   **Causa real, mucho más simple: no existía `vercel.json`** -- cero cron
   configurado disparando `/api/cron/sync-calendar` en producción, pese a
   que la ruta ya estaba escrita esperando exactamente eso. La reserva del
   fundador estaba sentada sin sincronizar hasta que alguien la disparara a
   mano -- confirmado corriendo el sync manualmente: apareció de inmediato,
   incluida una reserva real con teléfono no parseable
   (`telefono_google=null`, sin ningún error). Agregado `vercel.json` con
   cron cada 15 min -- **pendiente confirmar el plan de Vercel real** (Hobby
   limita cron a 1 vez/día, lo cual seguiría dejando el mismo problema
   percibido aunque ya no sea un bug).
2. **Corrección real aparte, sí necesaria:** cuando el teléfono no se podía
   normalizar a E.164, se guardaba `null` en la reserva flotante -- se
   perdía el dato sin que hubiera ningún error. Ahora se guarda el texto
   crudo como respaldo.
3. **Paginación:** `PipelineBoard.tsx` (Closer/Admin, 8 columnas
   simultáneas) podía renderizar hasta 2400 tarjetas de golpe con "Todos" --
   `SetterPipelineBoard.tsx` hasta 300 (confirmado en vivo: 473 leads
   reales en "Nuevo" para una sola cuenta). Ambos ahora cargan de a 100 con
   "Cargar más".
4. **Búsqueda insensible a tildes** (hallazgo real de la auditoría, no
   pedido explícitamente): "maria" no encontraba a "María" -- volumen alto
   real dado el ICP colombiano. Nueva función compartida `@/lib/texto.ts`.
5. **Bug real encontrado proactivamente, no reportado por el fundador:**
   `PipelineBoard.tsx` todavía tenía su PROPIA implementación vieja de
   "Generar link de agenda" (`/agendar/[token]`, el link con riesgo de
   baneo de Instagram eliminado el 23-ago en `GenerarEnlaceModal.tsx`) --
   nunca se actualizó porque vive en un componente distinto. Un Admin/Closer
   que lo usara desde el tablero compartido seguía generando el link
   sospechoso. Corregido reusando el mismo componente.
**Fuentes:** `node -e` directo contra libphonenumber-js, lectura completa de
`PipelineBoard.tsx` (no se había vuelto a leer desde antes del rediseño de
Agenda), consulta real a `google_calendar_sync_state` (última sync:
23-ago 16:54 UTC) y corrida manual del cron confirmando la hipótesis
correcta, prueba Playwright temporal contra QA Setter con datos reales
(lead con tilde, 473 leads reales activando "Cargar más", reserva flotante
sintética con teléfono no parseable), `type-check`/`lint`/suite E2E oficial
en verde.
**Estado:** cerrado y pusheado a `origin/master`. Los 4 leads QA quedan
limpios en `nuevo`/sin dueño. Pendiente del fundador: confirmar plan de
Vercel para saber si el cron de 15 min realmente aplica.

---

## 🧠 Sesión 24-ago-2026 (continuación) — Módulo Closer diseñado e implementado, RLS de `reuniones` desincronizada con `gestion_leads.closer_id`

**Fecha:** 2026-08-24
**Módulo:** ARTF / `artf-pipeline-app` (commit `4fc3038` sobre `master`, más el
fix de RLS de este bloque)
**Tipo:** diseño + implementación de feature nueva + bug real encontrado
probándola en vivo

**Módulo Closer:** el fundador propuso 5 piezas (campos nuevos en
clientes/leads para precio/anticipo/plan de pagos jsonb, peajes obligatorios
para Seguimiento y Perdido, Modal de Cierre con Oferta de Valientes,
reagendamiento). Evaluación crítica antes de programar: los campos nuevos
duplicaban infraestructura ya existente (`ventas`/`pagos_cuotas`/
`fn_registrar_venta`, que ya calcula cuotas, redondeo, forma de pago y tasa
de cambio) -- se implementó solo lo que faltaba (`es_oferta_valientes` +
parámetro nuevo en `fn_registrar_venta`) en vez de un jsonb paralelo. El
resto se construyó tal cual: `CloserPipelineBoard.tsx` dedicado (7 estados),
`fn_mover_a_seguimiento`/`fn_marcar_perdido` como peajes reales (no solo
UI), catálogo `motivos_perdida`, "Reagendar" reusando `GenerarEnlaceModal`
sin crear reuniones a mano.

**Bug real encontrado en la misma sesión, probando el cierre de venta en
vivo:** `fn_registrar_venta` recibía `p_comision_closer_pct`/
`p_comision_setter_pct` en `null` en AMBOS tableros (Closer y el compartido)
-- esas columnas son `NOT NULL DEFAULT 0`, pero Postgres solo aplica el
default cuando el valor se OMITE, nunca cuando se manda `null` explícito.
Todo intento real de "Registrar venta" fallaba con 400 desde antes de esta
sesión -- el botón de cierre llevaba tiempo roto en producción sin que nadie
lo notara (invisible en `type-check`/`lint`). Corregido a `0` en los dos
tableros.

**Fix de hidratación (Next.js), pedido aparte el mismo día:**
`SetterPipelineBoard.tsx` (filtro "Nuevo" 24h/168h) y `PipelineBoard.tsx`
(badge de reunión vencida) llamaban `Date.now()` en el cuerpo del render --
servidor y cliente lo calculan en instantes distintos, un lote de leads en
el borde cambiaba de lado entre el HTML del servidor y el primer render del
cliente. Se descartó el enfoque `useEffect`/`isMounted` propuesto (habría
causado el parpadeo que se quería evitar) -- se calcula una sola vez en el
Server Component (`getAhoraMs()` en `pipeline.ts`, usando `io()` de
`next/cache`, la forma oficial de esta versión de Next.js) y baja como prop.

**Segundo bug real, encontrado por el fundador probando el Módulo Closer:**
reportó que `TEST-Lead QA 1` "no respondía" al intentar marcar Show
Up/Seguimiento, con la hipótesis de que el sistema bloqueaba a propósito
reuniones futuras (la suya estaba agendada para el 26-ago). **Hipótesis
descartada con evidencia:** no existe ninguna validación de fecha en
`fn_motor_etapas`, `fn_registrar_venta`, `fn_mover_a_seguimiento`,
`fn_marcar_perdido`, ni en los `CHECK` de `reuniones`. **Causa real, más
seria:** la política `pol_re_update` sobre `reuniones` (creada el
22-ago-2026 junto con el resto del rediseño Setter) exigía
`reuniones.closer_id = auth.uid()` -- pero el Closer se asigna a un lead
escribiendo SOLO `gestion_leads.closer_id` (`PipelineBoard.tsx
asignarCloser()`), nunca `reuniones.closer_id`. Un UPDATE bloqueado por RLS
no lanza error (PostgREST no reporta 0 filas afectadas como fallo) -- el
botón "no hacía nada", ni error ni éxito. Verificado en vivo: **de 58
reuniones activas con lead vinculado, 10 tenían closer asignado en
`gestion_leads` pero `reuniones.closer_id` null** -- no fue un caso aislado
de un solo lead de prueba. Fix: la rama de Closer de `pol_re_update` ahora
también resuelve la pertenencia vía `gestion_leads.closer_id`, igual que ya
hacía la rama de Setter (inconsistencia que quedó desde el 22-ago). Ver
`supabase/migrations/20260824210000_fix_pol_re_update_reconoce_closer_via_gestion_lead.sql`.
Se agregó test permanente `e2e/closer-reuniones-rls.spec.ts` (con reset de
fixture vía service role en `beforeEach`, para que sea repetible) --
convención de "bug de clase nueva = test permanente, no solo corrección
puntual".

**Fuentes:** lectura de `pg_proc`/`pg_constraint`/`pg_policy` en vivo antes
de tocar nada (se descartó la hipótesis del fundador con evidencia, no se
aceptó de entrada), conteo real de reuniones desincronizadas, Playwright
contra QA Closer confirmando el fix, `type-check`/`lint`/suite E2E oficial
en verde.

**Estado:** Módulo Closer y fix de hidratación pusheados (`4fc3038`). Fix de
RLS aplicado directo a la base (migración pendiente de commit/push en la
próxima vuelta de esta sesión). `TEST-Lead QA 1` quedó con su reunión movida
al pasado (hoy en la mañana) para que el fundador pruebe el flujo completo
sin el bloqueo de fecha futura que él mismo ya no tiene, porque nunca
existió.

---

## 🧠 Sesión 25-ago-2026 — Wizard del Drawer del Closer, bloqueo real de reuniones futuras, limpieza de "nutrición"

**Fecha:** 2026-08-25
**Módulo:** ARTF / `artf-pipeline-app` (sobre `master`, continuación directa
de la sesión anterior)
**Tipo:** refinamiento UX (feature) + limpieza de estado fantasma, clasificado
como tarea Bounded (brainstorming skill) -- diseño aprobado en chat antes de
tocar código

**Bloqueo de reuniones futuras:** pedido explícito del fundador -- un Closer
no debería poder marcar Show Up/No Show de una reunión que aún no ocurrió.
Implementado en `CloserPipelineBoard.tsx` (`reunionEsFutura()`): si
`proxima_llamada` es posterior al `ahoraMs` que baja del Server Component
(mismo patrón del fix de hidratación de la sesión anterior -- se le agregó
esa prop al tablero del Closer, que no la tenía), los botones se ocultan y
se muestra el mensaje real ("La reunión es el [fecha] — aún no ha
ocurrido"). El caso de reprogramación que el fundador dejó a criterio propio
no necesitó código nuevo: `proxima_llamada` siempre refleja la reunión
ACTIVA del lead (`uq_reunion_activa_por_lead`), así que tras un
reagendamiento real el chequeo ya mira la fecha nueva sola.

**Wizard del Drawer:** el fundador reportó fricción real -- marcar Show Up
movía la tarjeta a otra columna y obligaba a cerrar el drawer, buscarla y
reabrirla para registrar el cierre ("chasing cards"). Ahora el drawer es un
flujo de 3 pasos (asistencia -> resultado -> detalle, estado local
`wizardStep`) que no se cierra entre Show Up y el cierre final. Un lead que
ya está en Show Up/Oferta al abrir el drawer entra directo en el paso 2 (no
repite la pregunta de asistencia). Ajuste sobre la propuesta original,
explicado y aprobado antes de programar: solo el paso 3 (detalle) difiere la
escritura real a un botón de Confirmar -- el paso 1 (Show Up) sigue
escribiendo de inmediato, porque `show_up` ya es un estado real e
independiente en el motor de etapas (un Closer puede marcar asistencia y
decidir el cierre horas después, comportamiento de negocio que ya existía).
Los formularios de Perdido/Seguimiento se extrajeron de sus modales
(`PerdidoForm`/`SeguimientoForm` en los mismos archivos, sin overlay propio)
para reusar la misma lógica de validación/RPC tanto en el wizard como en los
modales flotantes que siguen usando las pestañas No Show/Seguimiento y
`PipelineBoard.tsx` -- cero lógica de negocio duplicada. Botones "Atrás" en
los pasos 2 y 3 (paso 2 solo si el wizard arrancó en el paso 1).

**Limpieza de "nutrición":** el fundador notó (correctamente) que era un
estado fantasma. Verificado antes de tocar nada: existía activo en la base,
con transiciones reales funcionando, pero **0 leads lo habían usado jamás**
y no hay ningún sistema de nutrición/drip real detrás. Se desactivó sin
borrar la fila de `estados_lead` (`activo=false` + se borraron las 11 filas
de `estado_transiciones` que lo referenciaban) -- reversible sin fricción si
se retoma más adelante. Se sacó de `estados.ts`
(tipo/ESTADOS/TRANSICIONES/COLUMNAS), del botón "Enviar a Nutrición" del
Drawer y de `MOTIVO_LABEL` en `PipelineBoard.tsx`.

**Fuentes:** lectura completa de `estados_lead`/`estado_transiciones` antes
de decidir el mecanismo de baja, Playwright contra QA Closer confirmando
bloqueo por fecha futura (sin escritura en la base cuando está bloqueado,
verificado) + reentrada directa en paso 2 + Atrás + cierre completo del
wizard con venta registrada, `type-check`/`lint`/suite E2E oficial en verde.

**Estado:** implementado y verificado en vivo. Pendiente en esta misma
sesión: commit + push a `origin/master` (con aprobación previa del
fundador, patrón ya establecido) y aviso para que pruebe el flujo en el
navegador.

---

## 🧠 Sesión 25-ago-2026 (continuación) — Acciones rápidas en reunión futura, leads QA4/QA5, auditoría real: reunión huérfana al cancelar antes de la llamada

**Fecha:** 2026-08-25
**Módulo:** ARTF / `artf-pipeline-app` (sobre `master`, misma sesión que el
Wizard del Drawer)
**Tipo:** feature (acciones rápidas) + datos QA + auditoría de casos borde
con hallazgo real corregido a nivel de RPC

**Acciones rápidas en reunión futura:** el fundador pidió que un Closer no
quede atado de manos si el lead escribe a cancelar/reagendar antes de que
la reunión ocurra. Se agregaron 2 botones dentro del mismo contenedor de
aviso ("La reunión es el... aún no ha ocurrido"):
1. **"Cancelar reunión antes de la llamada"** -- salta directo al paso 3
   del wizard (Perdido) con el motivo "Canceló antes de la llamada"
   preseleccionado (catálogo `motivos_perdida`, no texto libre). Su "Atrás"
   vuelve al paso 1, no a un paso "resultado" que nunca se mostró (estado
   nuevo `origenDetalle`).
2. **"Reagendar cita"** -- reusa `GenerarEnlaceModal` como los demás
   puntos de reagendamiento del Módulo Closer.

**Hallazgo real de la auditoría (el más importante de este bloque):**
`uq_reunion_activa_por_lead` es un índice único PARCIAL sobre
`estado IN ('agendada','confirmada')` -- verificado en `pg_indexes` antes de
tocar nada. Los 2 caminos previos hacia "Perdido" (No Show, o desde Show
Up/Oferta) nunca chocaban con esto porque la reunión ya estaba fuera de ese
par de estados cuando `fn_marcar_perdido` podía llamarse. Pero el nuevo
botón "Cancelar reunión antes de la llamada" introduce el PRIMER camino
real hacia Perdido con la reunión todavía 'agendada' -- sin fix, esa
reunión quedaba huérfana en ese estado para siempre, bloqueando cualquier
reagendamiento futuro real de ese lead (sync.ts no podría insertar la
reunión nueva sin violar el único). Corregido a nivel de RPC, no solo en la
UI: `fn_marcar_perdido` ahora cancela cualquier reunión que siga
'agendada'/'confirmada' del lead antes de marcarlo Perdido -- protege la
invariante sin importar desde dónde se llame en el futuro. Migración:
`20260825150000_fn_marcar_perdido_cancela_reunion_activa.sql`. Mismo
razonamiento aplicado a "Reagendar cita": a diferencia de los reagendamientos
existentes (donde la reunión vieja ya estaba fuera del índice parcial antes
del botón existir), acá la reunión SIGUE activa -- se marca 'reprogramada'
(no 'cancelada' -- la cita se mueve, no se cae) vía `onAntesDeGenerar` de
`GenerarEnlaceModal`, antes de copiar el link, para que un error ahí
cancele todo el flujo en vez de mentir "copiado".

**Efecto colateral encontrado y corregido:** probar el flujo de "Cancelar"
dejó `TEST-Lead QA 1` en `perdido`, y el test permanente
`closer-reuniones-rls.spec.ts` intentaba resetearlo directo a `agendado` --
transición que `perdido` no permite (`TRANSICIONES.perdido = ["contactado"]`).
Su propio `UPDATE` de reseteo no revisaba el error, así que fallaba en
silencio y el síntoma real aparecía minutos después como un timeout de
locator sin relación aparente. Se endureció ese `beforeEach` para lanzar un
error claro apuntando a la causa real si esto vuelve a pasar.

**Leads QA4/QA5:** creados con reunión en el pasado (`TEST-Lead QA 4`,
hoy en la mañana; `TEST-Lead QA 5`, ayer) para que el fundador pueda probar
el wizard completo sin el bloqueo de fecha futura, sin gastar QA1/QA2/QA3
(ya usados como prueba de otros flujos).

**Fuentes:** lectura de `pg_indexes`/`pg_get_functiondef` antes de decidir
el mecanismo del fix (no se asumió, se verificó que era un índice parcial y
exactamente qué estados cubre), Playwright contra QA Closer confirmando
tanto el motivo preseleccionado como que `fn_marcar_perdido` efectivamente
cancela la reunión huérfana (verificado consultando la base después del
click, no solo el toast de éxito), `type-check`/`lint`/suite E2E oficial en
verde.

**Estado:** implementado y verificado en vivo. `TEST-Lead QA 1` quedó de
nuevo en `agendado` con reunión futura (27-ago) para que el fundador pruebe
los 2 botones nuevos él mismo. El fundador pidió explícitamente "commiteado"
(no push) esta vez -- push queda pendiente de una confirmación aparte,
siguiendo el patrón ya establecido de no pushear sin pedirlo cada vez.

---

## 🧠 Sesión 26-ago-2026 — Integración ManyChat (Setter): Enviar Calendario, Vincular con notificación, fix real de reunión huérfana

**Fecha:** 2026-08-26
**Módulo:** ARTF / `artf-pipeline-app` (sobre `master`, brainstorming
arquitectónico completo: exploración -> preguntas -> spec -> plan ->
ejecución, ver `docs/superpowers/specs/2026-08-26-manychat-integracion-setter-design.md`
y `docs/superpowers/plans/2026-08-26-manychat-integracion-setter.md`)
**Tipo:** integración nueva (primera vez que este repo habla con ManyChat)
+ bug real encontrado y reproducido en vivo antes de programar nada

**Regla de negocio confirmada:** cero correo/WhatsApp/IG handle pedidos en
la conversación de Instagram -- el lead los escribe recién al agendar en
Google Calendar.

**Enviar Calendario:** nuevo botón principal en el tab "Nuevo" del Setter
(reemplaza el copiar-y-pegar manual como camino principal; "Generar
enlace" queda de respaldo si ManyChat falla o el lead no tiene
`manychat_id`). Dispara un Flow YA CONFIGURADO en ManyChat vía
`POST /fb/sending/sendFlow` (verificado contra documentación real de
ManyChat, no asumido) -- se prefirió sobre armar el mensaje a mano
(`sendContent`) porque Meta exige un `message_tag` válido para mensajes
fuera de la ventana de 24h y ninguno de los tags documentados encaja limpio
con este caso; el Flow ya vive configurado en ManyChat con eso resuelto.

**Vincular como "Super Botón":** al vincular una reserva flotante manualmente,
ahora también notifica a ManyChat (quita el tag `PENDIENTE_AGENDA` vía
`removeTagByName`, dispara un segundo Flow de confirmación) -- pero
**Supabase manda**: si el RPC de vinculación falla, no se toca ManyChat; si
tiene éxito, un fallo de ManyChat (timeout, ventana de 24h, lo que sea)
NUNCA revierte la vinculación ya confirmada -- el toast lo dice honesto
("Vinculado con éxito. (Nota: No se pudo actualizar ManyChat)").

**Bug real encontrado y reproducido en vivo antes de programar** (no solo
leído en código): `fn_vincular_reserva_flotante` escribía
`clientes.whatsapp_e164 = coalesce(telefono_google, whatsapp_e164)` sin
validar contra el CHECK real de la tabla (`^\+[1-9][0-9]{7,14}$`).
`sync.ts` preserva a propósito el texto crudo del teléfono cuando no logra
normalizarlo a E.164 (ej. "3011234567 (este es el de mi mamá)") -- ese
texto real revienta la transacción completa con
`violates check constraint clientes_whatsapp_e164_check`, dejando al
Setter sin poder vincular jamás ese lead. No es un caso raro -- es
exactamente el tipo de dato que un lead real escribe en un formulario.
Corregido: si el teléfono crudo no pasa el regex, no se sobreescribe
`whatsapp_e164` (nunca se bloquea la vinculación por esto).

**Mejora de UX pedida explícitamente:** `VincularReservaModal` mostraba
TODAS las reservas flotantes sin filtrar ("buscar en un pajar"). Ahora
tiene filtro de fecha (Hoy / Esta semana -- default -- / Todos) y buscador
de texto libre.

**Decisión técnica evaluada, no asumida:** Server Action de Next.js
(`'use server'`) en vez de una Edge Function de Supabase -- este repo tiene
CERO edge functions hoy, y el patrón ya establecido
(`src/app/api/cron/sync-calendar/route.ts`) ya prueba que un secreto
server-side + Next.js alcanza sin infraestructura nueva.

**Fuentes:** lectura completa de `sync.ts` (mecanismo de "cita huérfana"),
verificación en vivo contra documentación real de ManyChat (`sendFlow`,
`removeTagByName`, autenticación Bearer, restricción real de ventana de
24h) vía WebSearch/WebFetch -- no se asumió ningún endpoint de memoria,
reproducción en vivo del bug de `whatsapp_e164` contra la base ANTES de
escribir el fix (rollback limpio confirmado, sin corrupción), 3 leads de
prueba creados (`TEST-Setter QA 1/2/3`), test permanente agregado
(`e2e/vincular-reserva-telefono-crudo.spec.ts`, con reset de fixture vía
service role), `type-check`/`lint`/suite E2E oficial en verde.

**Estado:** implementado, commiteado, pendiente de confirmación de push a
`origin/master`. El fundador gestiona `MANYCHAT_API_TOKEN` en su propio
`.env.local`/Vercel -- no es parte de este commit.

---

## 🧠 Sesión 27-ago-2026 — Auditoría: por qué el Pipeline del Setter solo mostraba 739 de 7.065 leads reales

**Fecha:** 2026-08-27
**Módulo:** ARTF / `artf-pipeline-app` (sobre `master`)
**Tipo:** auditoría de bug real (diagnóstico primero, código después, ambos
pedidos explícitos en turnos separados) + refactor del data layer del Setter

**Reporte inicial (Yuli, vía el fundador):** el Pipeline del Setter mostraba
"56 de 739 leads" cuando la base real tiene 7.065 (6.346 solo en "nuevo").
Leads viejos que reengancharon no aparecían, o aparecían con la fecha de su
primer contacto de hace meses.

**Diagnóstico (verificado en vivo antes de proponer nada):**
1. `getPipelineLeads()` trae los leads de `vw_pipeline` ordenando por
   `estado_desde` antes de cortar a 300 por estado (`CAP_POR_ESTADO`, del
   22-ago). `fn_sync_bot_turn` (leída completa) confirma que un lead que
   reengancha mientras sigue en "nuevo" solo actualiza `fecha_atendido` --
   nunca `estado_id`/`estado_desde` ni `fecha_contacto`. Un lead que
   escribió hace 6 meses y reengancha hoy queda ordenado como si tuviera 6
   meses de antigüedad, enterrado fuera del cap de 300.
2. El mismo defecto estaba duplicado client-side: `pasaRango` (filtro
   "Últimas 24h") y el `sort()` de `visible` en `SetterPipelineBoard.tsx`
   también usaban `fecha_contacto`/`estado_desde`.
3. El buscador de texto solo filtraba el array ya recortado a 300 -- un
   lead fuera de esa ventana era invisible para la búsqueda aunque
   existiera en la base.
4. Hallazgo colateral, no el bug reportado: RLS (`pol_gl_select`) sí deja
   ver a cualquier Setter los leads del bot o sin dueño -- correcto según
   la regla de negocio ("se asigna al enviar el calendario"). 53 de 6.346
   leads "nuevo" pertenecen a otros setters reales, pero todos con
   `origen_escritura='importacion'` -- artefacto de la migración vieja de
   la base, no un bug de la app actual.

**Fix:** `horas_sin_actividad` (ya expuesto en `vw_pipeline`, ya usado en
la insignia "Xh" de cada tarjeta) SÍ se recalcula en cada turno del bot
(confirmado: `fn_sync_bot_turn` inserta en `activity_log` sin excepción) --
se convirtió en la clave de orden y de filtro en 3 lugares (cap del
servidor, `pasaRango`, sort de `visible`). Buscador global nuevo
(`fn_buscar_leads_pipeline`, RPC sin `security definer` -- RLS se aplica
igual que un select directo) que ignora el cap por completo, con
`unaccent` (extensión nueva) para paridad exacta con
`normalizarParaComparar` del cliente. "Cargar más" pasó de revelar más de
un array ya recortado a pedir una página real nueva al servidor
(`getPipelineLeadsPagina`) cuando se agota lo cargado. Nuevo conteo real
por estado (`getConteosRealesPorEstado`, `count:"exact", head:true`, sin
traer filas) para que el header del Setter muestre el total real, no el
del array recortado.

**Desviación real del plan escrito, encontrada implementando:** el diseño
original sincronizaba el estado local `leads` con el prop `initialLeads`
vía un `useEffect`. El linter (`react-hooks/set-state-in-effect`, la regla
del compilador de React) lo marcó como el antipatrón "derivar estado de un
prop dentro de un efecto" -- se resolvió con el patrón que React
recomienda para esto (ajustar el estado durante el render cuando el prop
cambia de referencia, sin efecto), no ignorando el error.

**Fuentes:** conteo real por estado contra la base antes de proponer nada
(6.346/423/151/96/23/16/6/4), lectura completa de `fn_sync_bot_turn` (no
solo grep) para confirmar exactamente qué campos toca y cuáles no en un
reengagement, verificación de extensiones disponibles (`unaccent`) antes
de asumir que existía, reproducción en vivo del fixture del bug (lead con
`fecha_contacto` de hace 6 meses + `activity_log` de hace 0 horas) y
confirmación en navegador real de que aparece en "Nuevo/Todos" y en el
buscador global, comparación en vivo de página 1 vs. offset=300 sin
duplicados, `type-check`/`lint`/suite E2E oficial en verde.

**Estado:** implementado, commiteado. Pendiente de confirmación de push a
`origin/master`. El fixture de prueba (`TEST-Reenganche QA`) no se pudo
borrar -- `activity_log` es append-only (mismo diseño protector que
`ventas`) -- se dejó en estado terminal `descalificado`, renombrado para
dejar rastro de por qué existe.

---

## 🧠 Sesión 27-ago-2026 (continuación) — Feature 2 destrabada: arquitectura real de ManyChat encontrada, Modal de Revisión IA implementado y commiteado

**Fecha:** 2026-08-27
**Módulo:** ARTF / `artf-pipeline-app` (commit `65aad35` sobre `master`, sin
push todavía) + hallazgo de arquitectura en `estudio_skills_ia_claude`
**Tipo:** investigación de plataforma (corrige la sesión anterior) + spec +
implementación completa, con luz verde explícita del fundador en cada paso

**Corrección real sobre la investigación de la sesión anterior (misma
27-ago):** se había concluido que ManyChat no puede exponer ningún mensaje
fuera de un Flow automatizado. Al leer completo el Worker viejo
(`worker_cloudflare.md`, 1300 líneas -- antes solo resumido) se encontró que
**"Javit" no era captura pasiva: era un bot conversacional completo con
Claude Sonnet 4.6 que ejecutaba TODO el Playbook V4.0** (M1→M5.C),
extrayendo profesión/ingreso/dolor_opcion/urgencia en cada turno vía
`conversation_summary` acumulado -- apagado (`JAVIT_ACTIVO=false`), no
borrado. El fundador aportó una captura real del Flow de ManyChat (un solo
Flow, 7 reglas de trigger ya amplias -- incluye 2 de reconocimiento de
intención con IA de ManyChat sobre "dinero/finanzas/frustraciones" y
"quiere avanzar") con un nodo filtro **"Kill switch-leads existentes"**:
si el contacto ya tiene el tag `EXISTENTE_CONVERSACION`, la rama verde
("Acciones #5") solo pone/quita tags y NUNCA llama a ningún worker; solo la
rama roja (leads nuevos, primera vez) llama a `setter-ia-bridge` +
`setter-bridge-supabase`. Esto explica con evidencia real (no solo el patrón
de la base) por qué el 100% de los 518 leads reales con texto en
`activity_log` tiene exactamente 1 turno -- no es límite de la plataforma,
es una condición de este Flow específico.

**Idea del fundador, validada con fuentes oficiales antes de aceptarla:**
agregar la misma "Solicitud externa" hacia `setter-bridge-supabase` TAMBIÉN
en "Acciones #5" -- reusa las 7 reglas de trigger ya existentes (varias ya
cubren las respuestas reales de profesión/salario/dolor/urgencia) sin tocar
el kill switch de Javit (da igual, sigue apagado). Confirmado contra la
documentación oficial de ManyChat que el patrón "Default Reply + External
Request + Last Text Input" es exactamente esto. **Pendiente: este es un
cambio de CONFIGURACIÓN dentro de ManyChat (agregar 1 acción en el Flow ya
existente) -- el fundador ya tiene acceso admin, pero no se aplicó todavía
en esta sesión.** Hasta que se aplique, `activity_log` seguirá teniendo solo
1 turno por lead casi siempre, así que el Modal de Revisión IA (ver abajo)
va a abrir "vacío" para la mayoría de leads por ahora -- comportamiento
esperado, no un bug del LLM.

**Decisión de diseño explícita del fundador: cero botones manuales de IA
-- extracción "Just In Time".** Al pulsar "Enviar Calendario" (no un botón
aparte), en background se concatenan los `activity_log.ultimo_msg_lead` del
lead y se le piden a Groq. Se abre un Modal de Revisión con el formulario ya
pre-rellenado (o vacío con aviso explícito si no hay nada) -- el Setter
revisa/edita y confirma con un solo clic que guarda y envía.

**Verificado antes de programar (mismo código, no supuesto), 2 correcciones
reales al alcance pedido:**
1. **"Añadir nuevo lead" y el flujo sin `manychat_id`ya estaban 100%
   construidos** (`NuevoLeadModal.tsx` con botón visible + RPC real
   `fn_crear_lead_manual`; "Enviar Calendario" ya se deshabilita sin
   `manychat_id` con `GenerarEnlaceModal` como respaldo que ya mueve a
   Calificado). Solo faltaban los campos profesión/salario en el modal y en
   la RPC -- se evitó reconstruir algo que ya existía.
2. **`fn_vincular_reserva_flotante` no hace match automático por
   teléfono/correo -- es 100% manual** (el Setter elige de una lista). El
   pedido de "identidad por teléfono para leads sin manychat_id" no
   aplicaba: el camino ya es genérico para cualquier lead, con o sin
   manychat_id.
3. **Corrección de modelo:** se descartó `openai/gpt-oss-120b` (pedido
   inicialmente) a favor de `qwen/qwen3.8-27b` -- reverificado en esta
   sesión (no de memoria): los docs oficiales de Groq ya listan a
   `gpt-oss-120b` como soportado en modo estricto, pero el hilo de la
   comunidad y el issue de `langchain-ai/langchain#34155` siguen activos
   con el mismo bug reportado recientemente. Se usa además
   `response_format: json_object` (modo básico, no el `json_schema`
   estricto problemático) + limpieza defensiva de fences markdown antes de
   `JSON.parse`, pedida explícitamente por el fundador.
4. **Corrección de formato de dato:** el schema de extracción pide
   `dolor_opcion` (A-D) + `dolor_detalle` en vez de un resumen de texto
   libre -- `gestion_leads.dolor` tiene un formato de almacenamiento
   acordado (`parseDolor`/`serializeDolor` en `estados.ts`, "A,C,D|detalle")
   que un texto libre habría roto silenciosamente la próxima vez que el
   Setter abriera "Agendado".

**Implementado y verificado en vivo, commit `65aad35`:**
- `supabase/migrations/20260827180000_fn_crear_lead_manual_agrega_profesion_salario.sql`
  -- `fn_crear_lead_manual` extendida con 4 parámetros nuevos al final de la
  firma. **Bug propio encontrado y corregido en la misma sesión:** `CREATE OR
  REPLACE` con parámetros nuevos crea un SEGUNDO overload en vez de
  reemplazar (Postgres solo reemplaza con firma idéntica) -- se detectó
  verificando `pg_get_function_arguments` después de aplicar, no se asumió
  que el reemplazo fue limpio, y se corrigió con un `DROP FUNCTION` del
  overload viejo de 7 parámetros.
- `src/lib/ai/extraerDatosLead.ts` (nuevo, Server Action) -- lee
  `activity_log.ultimo_msg_lead` ordenado, corta sin llamar a Groq si no hay
  texto (determinístico), nunca lanza.
- `src/components/ModalRevisionIA.tsx` (nuevo) -- aviso "✨ Datos sugeridos
  por IA" o "No se detectaron datos, llena manualmente" (exigencia de
  transparencia del fundador).
- `src/components/SetterPipelineBoard.tsx` -- "Enviar Calendario" se parte
  en 2 momentos: clic reclama el lead + dispara la extracción (botón
  "Analizando chat…"); confirmar dentro del modal guarda
  profesión/salario/dolor + mueve a Calificado + llama a ManyChat
  best-effort (mismo contrato de siempre: Supabase manda, un fallo de
  ManyChat nunca revierte lo ya guardado). "Reenviar" (caso raro, edge case)
  se dejó intacto sin pasar por el modal, a propósito, para no tocar un
  camino que no se pidió cambiar.
- `src/components/CloserPipelineBoard.tsx` -- agrega profesión/salario al
  panel de "Datos" (antes solo mostraba dolor) para que el Closer vea la
  info completa antes de su llamada, pedido explícito del fundador.
- `src/components/NuevoLeadModal.tsx` -- inputs de profesión/salario.
- `CURRENCIES`/`PERIODICIDADES` (antes duplicados solo en
  `SetterPipelineBoard.tsx`) movidos a `estados.ts`, compartidos entre los 3
  componentes.
- Test permanente `e2e/modal-revision-ia-enviar-calendario.spec.ts` --
  fixture nuevo `TEST-Setter QA 4 (Modal Revision IA)` con `manychat_id`
  inventado a propósito (mismo criterio que el resto de fixtures QA: nunca
  un suscriptor real) y CERO filas en `activity_log`, para que
  `extraerDatosLead` corte de forma determinística sin depender de una
  llamada real a Groq -- prueba justo el contrato de resiliencia (Supabase
  manda, ManyChat best-effort) con una consulta directa a la base después
  del toast, no solo el mensaje de éxito.

**Fuentes:** lectura completa de `worker_cloudflare.md` (1300 líneas, no
solo resumen de memoria), captura real del Flow de ManyChat aportada por el
fundador, documentación oficial de Groq (`console.groq.com/docs/structured-outputs`)
+ comunidad/issue de GitHub reverificados en esta sesión (no de memoria),
lectura del código real de `enviarCalendario`/`guardarAgendado`/
`fn_vincular_reserva_flotante`/`fn_crear_lead_manual` antes de programar
(2 reducciones de alcance reales, no asumidas), `pg_get_function_arguments`
después de la migración (encontró el bug del overload), `type-check`/`lint`
(pre-commit hooks) y suite E2E completa (5/5) en verde.

**Estado:** implementado y commiteado (`65aad35`), pendiente de confirmación
de push a `origin/master`. **Pendiente real, fuera de este repo:** aplicar
el cambio de Flow en el dashboard de ManyChat (agregar la Solicitud externa
a "Acciones #5") -- sin eso, el Modal de Revisión IA seguirá abriendo vacío
para la mayoría de leads nuevos, comportamiento esperado documentado arriba,
no un bug.

---

**Sesión 28-ago-2026 — Deuda Técnica "Thick Client" saldada, Pruebas E2E estabilizadas y Push final (Agent Antigravity):**
- **Deuda Técnica "Thick Client" en Componentes React:** Identificamos y corregimos llamadas `.update()` a base de datos que residían directamente en el frontend.
  - El `SetterPipelineBoard.tsx`, `CloserPipelineBoard.tsx` y `PipelineBoard.tsx` (Admin) fueron refactorizados completamente. Todas sus mutaciones (como re-agendar, avanzar estado o actualizar perfiles de leads) ahora están encapsuladas y aisladas en **Next.js Server Actions** transaccionales en `src/lib/data/pipeline-actions.ts`.
  - Esta migración no solo mejora la seguridad para que RLS pueda auditar con confianza las solicitudes desde el servidor, sino que impone un patrón sólido ("use server") para las futuras ampliaciones.
- **Fixture Collisions en Playwright E2E:** Al intentar verificar los tableros concurrentemente en 6 hilos, los tests se rompían intermitentemente ("flakiness") debido al uso compartido del fixture "TEST-Setter QA 4" entre varios archivos. Se refactorizó el script de pruebas para crear fixtures *aislados* dinámicamente con `test.beforeEach()` e `insert`, y limpiar su rastro en `test.afterEach()`.
- **Estatus:** Completado y pusheado a `master` (`3007032`). Toda la arquitectura React Client / Server Action queda robusta para soportar el diseño pendiente del flujo final del Closer y el Dashboard de Métricas Administrativas.

---

## 🧠 Sesión 28-29-ago-2026 — 5 bugs/UX del Setter + captura total de la conversación + validación de agenda con Groq

**Módulo:** ARTF / `artf-pipeline-app` (sin commitear todavía) + Worker Cloudflare + `fn_sync_bot_turn.sql` (`estudio_skills_ia_claude`)

**Bloque 1 (28-ago, 5 puntos pedidos por el fundador) -- diagnóstico primero, no todo era bug real:**
- **Rendimiento de navegación:** no era fuga de canales Realtime (verificado: 1 solo WebSocket, estable). Causa real, verificada con `EXPLAIN ANALYZE`: `horas_sin_actividad` era una subconsulta correlacionada -- Postgres evaluaba 6.470 filas de "nuevo" antes de poder ordenar y cortar a 300 (600ms). Fix: `ultima_actividad_at`/`total_interacciones` desnormalizadas a columnas reales en `gestion_leads` (trigger sobre `activity_log`), índice compuesto real, `ANALYZE` -- **90ms verificado, 6.6x**.
  - **Bug propio serio encontrado corriendo la suite E2E completa después del fix** (no antes): el trigger nuevo chocaba con `fn_columnas_por_rol` (control de qué columnas puede tocar cada rol) -- CUALQUIER acción de un Setter/Closer que cambiara `estado_id` (Show Up, Vincular, Desvincular, guardar Agendado) fallaba en cascada, en silencio. Corregido agregando las 2 columnas a `v_comunes`, mismo tratamiento que `version`/`updated_at`.
- **Desvincular no limpiaba correo/teléfono inyectados por la reserva equivocada:** confirmado -- `fn_vincular_reserva_flotante` siempre sobreescribe. `fn_desvincular_reserva` ahora limpia solo si coinciden exacto con lo que esa reserva específica escribió (nunca un borrado ciego).
- **"Modal perdido":** no estaba perdido -- Calificado nunca tuvo formulario para VER esos datos de nuevo. Se extrajo `CamposCualitativosForm` (antes duplicado en Agendado) y se agregó a Calificado también.
- **Visualización + Safe Close + formato:** tarjetas muestran profesión/salario cuando existen; `window.confirm()` bloquea cierre del drawer con cambios sin guardar (verificado en vivo); salario con separador de miles (`8.000.000`).
- **Mensaje de agradecimiento ya no automático al vincular:** separado en `confirmarRespuestaLeadYNotificar()`, botón manual "Confirmar respuesta del lead" en Agendado.
- Verificado: `type-check`/`lint` verde, **8/8 E2E verde** (incluye 1 test nuevo + 2 ajustados por el cambio de formato).

**Bloque 2 (29-ago) -- captura total de la conversación + validación de agenda con Groq:**
- **Hallazgo crítico ANTES de tocar ManyChat:** `fn_sync_bot_turn` calculaba `else 'nuevo'` para cualquier llamada sin `p_etapa_bot` -- exactamente el caso del worker pasivo nuevo (nunca lo manda). Y `'agendado'->'nuevo'` SÍ es una transición legal en `estado_transiciones` (existe para "Devolver a Nuevo"). **Abrir la puerta de ManyChat sin este fix habría devuelto a "nuevo" cualquier lead ya agendado en cuanto mandara un mensaje más** ("gracias", lo que sea) -- en silencio, sin que nadie lo pidiera. Corregido: sin señal de etapa, el destino es quedarse donde está. Verificado con `BEGIN/ROLLBACK` contra un lead agendado real (`manychat_id 611122479`) antes y después del fix. Sincronizado en `Tarea_1_Migrar_DB/fn_sync_bot_turn.sql` (bug #6 documentado en su cabecera).
- **Instrucción de Flow para ManyChat (pendiente de que el fundador la aplique):** agregar la misma "Solicitud externa" hacia `setter-bridge-supabase` también en "Acciones #5" (rama verde del "Kill switch-leads existentes") -- sin tocar los 7 triggers ya existentes ni el kill switch de Javit.
- **Validación de agenda con Groq, en el Worker (`worker_bridge_supabase_NUEVO_paralelo.js`):** cuando `fn_sync_bot_turn` devuelve `out_estado_codigo='agendado'`, se clasifica el mensaje del lead con `qwen/qwen3.8-27b` (Groq, `response_format: json_object`). **Se descartó el booleano confirmó/problema de la propuesta original** -- "agendado" en la base ya es un hecho verificado contra Calendar, no algo que el LLM deba re-confirmar; la pregunta real es si el mensaje pide reagendar/cancelar. 3 categorías: `confirmacion` (dispara el flow de agradecimiento + tag `RESPUESTA_AGENDA_PROCESADA`), `reagendar_o_cancelar` (tag `REQUIERE_ATENCION_AGENDA` + `RESPUESTA_AGENDA_PROCESADA`, sin agradecimiento), `otro` (mismo tratamiento que reagendar). Groq null (timeout/fallo) no toca nada -- el Smart Delay de 30 min lo cubre.
- **Fallback de 30 min (diseño entregado, pendiente de aplicar en ManyChat):** Smart Delay de 30 min después de "Enviar Calendario", seguido de una condición "¿tiene el tag `RESPUESTA_AGENDA_PROCESADA`?" -- si no, dispara el flow de agradecimiento + pone el tag, para que nunca se duplique.
- Verificado con `node --check` (sintaxis) -- no se pudo correr en vivo (el Worker corre en Cloudflare, no hay despliegue automatizado desde este repo, el fundador debe redesplegar a mano).

**Pendiente real, fuera de código:** aplicar el cambio de Flow en ManyChat (Acciones #5 + Smart Delay), configurar `GROQ_API_KEY`/`MANYCHAT_FLOW_NS_CONFIRMACION` como secrets del Worker en Cloudflare, redesplegar el Worker.

### PRÓXIMOS PASOS EXACTOS (para quien retome esta sesión)

**Aclaración importante para no confundirse:** el código del Worker (`worker_bridge_supabase_NUEVO_paralelo.js`) está actualizado SOLO en este repo (`estudio_skills_ia_claude`) -- **el Worker que corre de verdad en Cloudflare todavía tiene la versión VIEJA**, sin la clasificación de Groq ni el fix de captura ampliada. Nadie lo desplegó todavía -- esta sesión no tiene acceso a la API/CLI de Cloudflare, así que este es un paso 100% manual pendiente, no algo que ya esté hecho.

1. **Redesplegar el Worker a Cloudflare** -- copiar el contenido actualizado de `worker_bridge_supabase_NUEVO_paralelo.js` al editor de `setter-bridge-supabase` en el dashboard de Cloudflare (o vía `wrangler` si se adopta esa herramienta más adelante) y publicar.
2. **Agregar 2 secrets nuevos** en Cloudflare Dashboard → `setter-bridge-supabase` → Settings → Variables: `GROQ_API_KEY` y `MANYCHAT_FLOW_NS_CONFIRMACION` (mismo valor de flow_ns que ya usa `artf-pipeline-app` para esa misma variable -- revisar su `.env.local`/Vercel).
3. **Configurar el Flow de ManyChat -- 2 cambios, ambos manuales en el dashboard de ManyChat:**
   - En "Kill switch-leads existentes" → rama verde "Acciones #5": agregar una Solicitud externa hacia `setter-bridge-supabase` (misma URL que ya usa la rama roja "Acciones").
   - En el Flow de "Enviar Calendario" (`MANYCHAT_FLOW_NS_CALENDARIO`), después del mensaje con el link: Smart Delay de 30 min → Condición "¿tiene la etiqueta `RESPUESTA_AGENDA_PROCESADA`?" → si no, disparar el flow de agradecimiento (`MANYCHAT_FLOW_NS_CONFIRMACION`) + poner esa etiqueta.
4. **Probar en vivo con un lead de prueba real** antes de asumir que el flujo completo funciona en producción (mismo criterio de disciplina de todo este proyecto) -- confirmar que un mensaje de un lead nuevo YA agendado no lo regresa a "nuevo" (el fix de `fn_sync_bot_turn` ya está verificado con `ROLLBACK`, pero vale la pena verlo funcionar de punta a punta con tráfico real una vez desplegado).
5. **Commitear/pushear `artf-pipeline-app`** con los fixes de esta sesión (ver bloque de arriba) -- confirmar si ya se hizo revisando `git log` al abrir la sesión nueva.
6. **Iniciar el diseño del flujo Closer/Admin** -- próxima iniciativa grande, todavía sin discutir en ninguna sesión, sin spec ni plan escrito. Empezar con brainstorming/arquitectura antes de tocar código, mismo criterio ya establecido para todo este proyecto.

**Cómo inicializar la sesión nueva:** pedirle a Claude que lea este archivo (`01_Gobernanza_EOS/02_backlog_y_rocas.md`, ya lo hace por defecto según `estudio_skills_ia_claude/CLAUDE.md`) y las memorias `artf_manychat_flow_kill_switch_arquitectura` + `artf_feature2_llm_extraction_blocked` + `artf_formulario_dashboard_status` antes de asumir el estado del proyecto.

## 🧠 Sesión 30-ago-2026 — Alerta de recursos de Supabase: diagnóstico + 2 fixes reales

**Disparador:** Supabase mostró "Your project is currently exhausting multiple resources" en el dashboard. Investigado a fondo con el MCP de Supabase (advisors, `pg_stat_statements`, `EXPLAIN ANALYZE` impersonando roles reales con `set_config('request.jwt.claims', ...)`, logs) antes de tocar nada — mismo criterio de este proyecto de no adivinar.

**Descartado primero (evidencia, no suposición):**
- No es disco: la base completa pesa 114 MB.
- No son conexiones: solo ~22 abiertas, lejos de cualquier límite.
- No es un incendio activo: los checkpoints de Postgres del día se ven sanos (sin `canceling statement`, sin OOM). `pg_stat_statements` **nunca se ha reseteado desde que se creó el proyecto (2026-08-09, 21 días acumulados)** -- las cifras de millones de buffers en las queries más caras son costo histórico acumulado (migraciones, imports, pruebas), no necesariamente la causa de la alerta de HOY. Importante tenerlo en cuenta la próxima vez que se lea `pg_stat_statements`: revisar `pg_stat_statements_info.stats_reset` primero, o los números llevan a conclusiones exageradas.

**Fix 1 -- índice de cobertura en `gestion_leads(cliente_id)` (aplicado, bajo riesgo):**
`pol_cli_select` (RLS de `clientes`) hace un `EXISTS` correlacionado contra `gestion_leads` por cada fila -- duplica el join que `vw_pipeline` ya hace. Verificado con `EXPLAIN (analyze, buffers)` impersonando un Setter real (`set_config('request.jwt.claims', ...)` con el `auth_user_id` de `QA Setter`) antes/después: el índice viejo `ix_gl_cliente` no cubría `setter_id`/`closer_id`/`califica`, forzando un heap fetch extra en ese `EXISTS`. Reemplazado por `ix_gl_cliente_covering` (`INCLUDE (setter_id, closer_id, califica)`) -- el plan pasó de `Index Scan` a `Index Only Scan`. Ganancia real (~8%), no transformadora -- el lever grande sigue siendo paginar/filtrar la pestaña "Ver Todos" (ya señalado en el handoff de Gaby del Closer, aplica igual al Setter/`PipelineBoard.tsx`), tarea de UX pendiente, no bugfix de una línea.

**Fix 2 -- bug real reproducido: `fn_calificar_lead_con_datos` explota con periodicidad inválida:**
Encontrado por accidente investigando 2 conexiones `idle in transaction (aborted)` de PostgREST. `fn_calificar_lead_con_datos` (creada 28-ago por Gaby) castea `p_salario_periodicidad::public.periodicidad` (enum: solo `mensual`/`quincenal`/`anual`). `ModalRevisionIA.tsx:42` inicializaba el `<select>` directo con la sugerencia de Groq **sin validar contra esos 3 valores** -- si el modelo devuelve otra cosa y el Setter confirma sin tocar el dropdown, la RPC lanza `invalid input value for enum` y aborta la transacción. Reproducido limpio con `BEGIN/ROLLBACK` (no se pudo confirmar por logs -- ni `postgres_logs` ni `edge_logs` capturaron el evento, la única evidencia fue `pg_stat_activity` + reproducción manual). Fix: normalizar a `"mensual"` si la sugerencia no está en `PERIODICIDADES` antes de usarla como estado inicial. `type-check` limpio. **Commiteado local (`1ef5ec9`), NO pusheado todavía.**

**Corrección post-sesión: la "posible colisión con Gaby" fue una falsa alarma.** Se le preguntó directamente y confirmó que no ha tocado `fn_calificar_lead_con_datos`/`ModalRevisionIA.tsx` ni tiene contexto de Groq/periodicidad (está en Closer). Evidencia forense del lead `TEST-RPC-debug-1788105627400` (`updated_at`/`updated_by`) muestra que su última escritura real fue a las 16:02 UTC, mucho antes de que empezara a probar (23:2x) -- la "version cambiando entre mis propias transacciones con ROLLBACK" fue casi con certeza un artefacto de la propia secuencia de pruebas vía MCP (el pooler de conexión no garantiza que un string multi-statement con `set local role` quede en una sola sesión atómica), no una sesión externa concurrente. `origin/gaby` apareciendo al mismo tiempo fue coincidencia de timing. **Commit `1ef5ec9` pusheado a `origin/master` sin más demora.** Lección para la próxima vez: verificar `updated_at`/`updated_by` (evidencia dura) antes de anotar "colisión con otra persona" como hecho, y preguntar antes de escribirlo en la bitácora como conclusión.

**Pendiente real de esta sesión:**
1. Confirmar con Gaby si ya arregló `fn_calificar_lead_con_datos`/`ModalRevisionIA.tsx` en su rama -- evitar 2 fixes duplicados/conflictivos del mismo bug.
2. Una vez confirmado, pushear `1ef5ec9` (o descartarlo si el de ella ya lo cubre).
3. Nota de seguridad aparte (no bloqueante): la key del service account de Google (`GOOGLE_SERVICE_ACCOUNT_KEY_BASE64`) quedó impresa en texto plano en la salida de una terminal durante una exploración de código esta semana -- `.env.local` está bien gitignoreado (nunca se commiteó), pero vale la pena rotarla en algún momento por higiene, ya se imprimió más de una vez en desarrollo.
4. Todavía sigue pendiente el plan grande de esta sesión: cerrar el flujo del Setter (Worker + Flow de ManyChat, para la noche), luego métricas del Admin. Ver la sección anterior "PRÓXIMOS PASOS EXACTOS" del 28-29-ago, que sigue vigente.
