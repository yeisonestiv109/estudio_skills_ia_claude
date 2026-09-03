# Guía de despliegue — Bot conversacional ARTF (SOP V4.2)

**Fecha:** 2-sep-2026 · **Estado:** listo para desplegar y probar.
**Compuerta del proyecto:** `./verificar.sh` — 143 tests, 4 de 5 en verde
(la 5ª es justamente el smoke del Worker, que se corre al terminar el paso 2).

Esta guía cubre el despliegue del **Worker nuevo** y la configuración del
**ManyChat de prueba**. Todo corre en paralelo a producción: lo único
compartido es la base de datos de Supabase (decisión explícita del fundador).

---

## 0. Qué se construyó (resumen)

| Pieza | Archivo | Qué hace |
|---|---|---|
| Plantillas del SOP | `Scrips_Worker_and_AppScript/sop_v42_plantillas.js` | Texto literal V4.2 (M1-M7, 9 objeciones, 3 descalificaciones, bumps) |
| Router determinista | `Scrips_Worker_and_AppScript/bot_router_v42.js` | Filtros, glosario de ingreso, objeciones, transiciones. Sin red: 100% testeable |
| Worker | `Scrips_Worker_and_AppScript/worker_bot_setter_v42.js` | Webhook, idempotencia, LLM, Supabase, tags |
| Verificador | `Scrips_Worker_and_AppScript/verificador_cumplimiento.js` | La compuerta: reprueba cualquier mensaje que viole el playbook (link, voz, copy no aprobado) |
| Simulador | `Scrips_Worker_and_AppScript/simulador.js` | Reproduce conversaciones completas sin red. `node ver-conversacion.mjs` |
| Corpus | `Scrips_Worker_and_AppScript/tests/corpus/` | 4 conversaciones con frases literales de leads reales |
| Tests | `Scrips_Worker_and_AppScript/tests/` | 143 tests, `node --test` |
| Migraciones | `artf-pipeline-app/supabase/migrations/20260901*` | Campos nuevos + `fn_bot_get_estado` + `fn_bot_procesar_turno` |

**Ya aplicado en la base** (las 4 migraciones corrieron y están verificadas).

> Antes de desplegar, si quieres ver cómo conversa el bot sin tocar nada:
> `cd Scrips_Worker_and_AppScript && node ver-conversacion.mjs`

---

## 1. Antes de empezar — ten a mano

- [ ] Cuenta de **Instagram de prueba** ya conectada a una cuenta de **ManyChat** (puede ser un espacio/página nueva; NO uses el ManyChat de producción).
- [ ] **2 cuentas de Instagram personales** para escribirle al bot como si fueras el lead.
- [ ] `SUPABASE_SERVICE_ROLE_KEY` del proyecto `lrdtjsxtaadpgrzkchlw` (Supabase → Settings → API).
- [ ] `GROQ_API_KEY` (la misma que ya usa el Worker de captura pasiva sirve).
- [ ] Token de la API de ManyChat **de la cuenta de prueba** (ManyChat → Settings → API).

---

## 2. Desplegar el Worker en Cloudflare

### Opción A — con wrangler (recomendada, son 3 archivos)

```bash
cd estudio_skills_ia_claude/03_Clientes_y_Casos/02_Cliente_ARTF/Scrips_Worker_and_AppScript
npx wrangler login
npx wrangler deploy
```

Esto crea el Worker `artf-bot-setter-v42` y te devuelve su URL
(`https://artf-bot-setter-v42.<tu-subdominio>.workers.dev`). **Guarda esa URL**, la necesitas en el paso 4.

> El Worker está partido en 3 archivos (`worker_bot_setter_v42.js` importa
> `bot_router_v42.js` y `sop_v42_plantillas.js`). Wrangler los empaqueta solo.
> Por eso **no** se puede copiar y pegar en el editor del dashboard como el
> Worker viejo: usa wrangler.

### Cargar los secrets

```bash
npx wrangler secret put SUPABASE_URL
# pega: https://lrdtjsxtaadpgrzkchlw.supabase.co

npx wrangler secret put SUPABASE_SERVICE_ROLE_KEY
# pega la service_role key

npx wrangler secret put GROQ_API_KEY
npx wrangler secret put MANYCHAT_API_TOKEN

# OBLIGATORIO -- sin esto el Worker se niega a arrancar (responde 500).
# Genera uno largo y aleatorio, por ejemplo con:
#   openssl rand -hex 32
npx wrangler secret put WEBHOOK_SECRET

# Opcional pero MUY recomendado para esta prueba:
npx wrangler secret put MANYCHAT_IDS_PRUEBA
# pega los 2 subscriber_id de prueba separados por coma, ej: 123456,789012
```

`MANYCHAT_IDS_PRUEBA` hace que esos leads se guarden con el nombre
prefijado **`[PRUEBA]`**. Sirve para dos cosas: los distingues de un vistazo en
el dashboard, y al final los borras filtrando por ese prefijo.

### Probar que responde (sin ManyChat todavía)

```bash
curl -X POST https://TU-WORKER.workers.dev \
  -H "Content-Type: application/json" \
  -H "X-Bot-Secret: EL-SECRETO-QUE-PUSISTE" \
  -d '{"manychat_subscriber_id":"999888777","last_text":"CONTROL","first_name":"Prueba","fuente":"comentario"}'
```

Y comprueba que **sin** el header te rechaza (debe dar `401`, no una respuesta del bot):

```bash
curl -i -X POST https://TU-WORKER.workers.dev \
  -H "Content-Type: application/json" \
  -d '{"manychat_subscriber_id":"999888777","last_text":"CONTROL"}'
# HTTP/2 401 ... {"ok":false,"responder":false,"error":"no_autorizado"}
```

> **Por qué esto importa:** la URL de un Worker no es un secreto (queda en la
> config de ManyChat, en logs, en tu historial de terminal). Sin el header,
> cualquiera que la conozca podría escribir en la base de datos **real** con el
> `manychat_id` de un lead ajeno: cambiarle el salario, avanzarlo en el embudo,
> descalificarlo, o quemarte los créditos del LLM.

Debe responder algo así:

```json
{"ok":true,"responder":true,"msg":"¡Hola Prueba! 👋 Te entiendo, no tener el control real...","msg2":"","msg3":"","handoff":false,"etapa":"M1_ENVIADO","estado":"contactado"}
```

> Ese `curl` **crea un lead real** en la base con manychat_id `999888777`.
> Bórralo después (ver paso 7) o úsalo como tu tercera cuenta de prueba.

---

## 3. Preparar los tags en ManyChat

En el ManyChat de prueba, crea estos tags (Settings → Tags). El Worker los
aplica solo, pero deben existir:

`ATENDIDO_BOT`, `HANDOFF_ANDRES`, `DESCALIFICADO`, `CALENDARIO_ENVIADO`,
`ERROR_TECNICO_BOT`, y los de razón específica:
`HANDOFF_CRISIS_EMOCIONAL`, `HANDOFF_CONTENIDO_HOSTIL`, `HANDOFF_PREGUNTA_PRECIO`,
`HANDOFF_RESISTENCIA_REPETIDA`, `HANDOFF_RESISTENCIA_ACUMULADA`,
`HANDOFF_OBJECION_FUERA_PLAYBOOK`, `HANDOFF_OBJECION_NO_HABILITADA`,
`HANDOFF_AMBIGUO`, `HANDOFF_EX_CLIENTE`, `HANDOFF_ERROR_TECNICO`.

> **Atajo:** si prefieres no crearlos a mano, ManyChat crea el tag solo la
> primera vez que la API lo aplica. Crear al menos `ATENDIDO_BOT` y
> `HANDOFF_ANDRES` a mano te sirve para dejar armados los filtros de la bandeja
> desde el dia 1.

---

## 4. Armar el Flow de ManyChat

**Diferencia clave con el bot viejo: ManyChat es un tubo abierto.** No hay kill
switch, no hay condiciones que bloqueen turnos, no hay custom fields de memoria.
Manda TODO al Worker y envía lo que el Worker le diga.

### 4.1 Triggers

Un solo Flow, con los triggers que quieras probar (comentario en Reel con
`CONTROL` / `CLARIDAD`, DM nuevo, etc.). **Importante:** agrega también el
trigger de **cualquier mensaje entrante** (Default Reply / "User replies"), para
que los mensajes 2, 3, 4… también lleguen al Worker. Sin eso el bot solo
contestaría el primer mensaje — que fue exactamente lo que rompió al bot viejo.

### 4.2 Acción 1 — External Request

- **Method:** POST
- **URL:** la URL de tu Worker
- **Headers:** (los dos, el segundo es obligatorio)
  - `Content-Type: application/json`
  - `X-Bot-Secret: <el mismo valor que pusiste en WEBHOOK_SECRET>`
- **Body (JSON):**

```json
{
  "manychat_subscriber_id": "{{user_id}}",
  "last_text": "{{last_input_text}}",
  "first_name": "{{first_name}}",
  "last_name": "{{last_name}}",
  "ig_username": "{{ig_username}}",
  "fuente": "comentario"
}
```

### 4.3 Response Mapping

**Esto es lo que hay que hacer distinto al bot viejo.** El bot viejo mapeaba la
respuesta a custom fields (`conversation_summary`) y los **sobrescribía** cada
turno — esa fue la causa raíz de que perdiera la memoria.

**Aquí NO se mapea nada a custom fields.** Solo se usa la respuesta inline:

- `$.msg`   → texto del primer mensaje
- `$.msg2`  → texto del segundo (puede venir vacío)
- `$.msg3`  → texto del tercero (puede venir vacío)
- `$.responder` → booleano, si es `false` no se envía nada

### 4.4 Acciones de envío (en este orden)

1. **Condition:** `{{response.responder}}` es `true` → si no, terminar el Flow sin enviar nada.
2. **Send Message:** `{{response.msg}}`
3. **Condition:** `{{response.msg2}}` no está vacío → **Send Message:** `{{response.msg2}}`
4. **Condition:** `{{response.msg3}}` no está vacío → **Send Message:** `{{response.msg3}}`

> Hoy el bot envía **máximo 2 burbujas** por turno, así que `msg3` siempre llega
> vacío. Configúralo igual: es una condición más y evita que un mensaje se
> pierda en silencio si más adelante alguna rama envía 3.

> **Por qué 3 mensajes separados:** el SOP exige que el link del calendario vaya
> **aislado en su propia burbuja** (Instagram lo rompe si le pegas texto justo
> después). En el turno del cierre el Worker manda: `msg` = link,
> `msg2` = "Confirmame cuando te hayas agendado…", `msg3` = la pregunta de si
> asiste solo o acompañado.

---

## 4.5 Qué hace y qué NO hace el bot en esta v1

Para que sepas qué esperar en la prueba y no lo leas como un fallo:

| El bot lo hace solo | Te lo pasa a ti (handoff + tag) |
|---|---|
| Los 7 mensajes del guion (M1→M7) | Objeciones **4 a 9** (`objecion_no_habilitada`) |
| Los 3 filtros + glosario de ingreso | Cualquier objeción fuera de las 9 |
| Descalificación con valor (3 scripts) | Crisis emocional, hostilidad, ex-cliente |
| Objeciones **1, 2 y 3** | Ingreso que sigue ambiguo tras pedirlo |
| RetornoLead (descartado que se recalifica) | Misma objeción 2 veces / 3 seguidas |
| Blindaje del show-up | Fallo técnico de la base |

**Ampliar objeciones después = agregar el número al Set `OBJECIONES_HABILITADAS`** en `sop_v42_plantillas.js`. El copy y el ruteo de las 9 ya están construidos y probados.

**Lo que NO existe todavía:** los bumps de recuperación (30min/24h/72h). Necesitan un Cron Trigger de Cloudflare y quedan para después de esta prueba. Si un lead deja de responder, el bot simplemente no insiste.

---

## 5. Guion de prueba (haz esto con las 2 cuentas)

Prueba estos caminos. Después de cada uno revisa el lead en el dashboard
(`/` pipeline) y en Supabase (`gestion_leads.etapa_bot`, `estado_id`).

| # | Escribe esto | Debe pasar |
|---|---|---|
| 1 | `CONTROL` | Llega M1. `etapa_bot=M1_ENVIADO`, estado `contactado` |
| 2 | `soy ingeniera y gano 12 millones` | Llega M2 (endeudamiento). Guarda profesión y salario |
| 3 | `como el 30%` | Llega M3 (dolor A/B/C/D) |
| 4 | `B` | Llega M4 (urgencia) |
| 5 | `es prioridad ahora` | Llega M5 (pitch). **Estado pasa a `calificado`** |
| 6 | `dale, agendemos` | Llegan **exactamente 2 mensajes**: el saludo y **el link SOLO, de último**. `calendario_enviado_at` se llena. **El estado NO pasa a `agendado`**. `etapa_bot=M6_ENVIADO` |
| 7 | (cualquier cosa, ej. `listo`) | Recién ahora llegan la pregunta de acompañante y el "Confirmame…". `etapa_bot=M7_ENVIADO` |
| 8 | `voy solo` | Acuse corto. `asiste_acompanado=false` |
| 9 | `ya agendé` | Llegan las 2 preguntas pre-llamada. `etapa_bot=CIERRE_PRECALL` |
| 10 | `muchas gracias!` | Llega la **pregunta de blindaje del show-up**. `etapa_bot=BLINDAJE_ENVIADO` |
| 11 | `ahí estaré firme` | Cierre corto. `etapa_bot=BLINDAJE_CERRADO` — el bot ya no responde más |

> **⚠️ Verificación crítica en el paso 6:** mira el chat de Instagram y confirma que **el link quedó como último mensaje, solo, y que es clickeable**. Si le llega texto pegado después, Instagram lo rompe (*"Dynamic Link Not Found"*) y se cae el agendamiento. Esto es un bug confirmado en producción por el equipo de Javier, y es la razón por la que el "Confirmame…" y la pregunta de acompañante se envían hasta el turno siguiente.

### Caminos que también hay que probar (con la segunda cuenta)

| Escribe | Debe pasar |
|---|---|
| `gano el mínimo integral` (en M1) | **NO descalifica.** Pide la cifra exacta |
| `me quedan como 5 millones libres` | **NO descalifica.** Pregunta si es ingreso total o lo que le queda (aprendizaje de producción de Javier) |
| `gano 2 millones` | Descalifica con valor (script de ingresos), motivo de pérdida registrado |
| `¿cuánto cuesta el programa?` (tras el pitch) | Responde la Objeción 7 |
| Repetir `¿cuánto cuesta?` | Handoff `pregunta_precio` + tag. **El bot deja de responder** |
| Tras descalificar por ingreso: `pero yo gano 22 millones` | **RetornoLead**: rectifica y retoma en M2 |

---

## 6. Verificar en la base mientras pruebas

```sql
select c.nombre, gl.etapa_bot, e.codigo as estado, gl.califica,
       c.salario_monto, gl.endeudamiento_pct, gl.dolor, gl.urgencia,
       gl.handoff_razon, gl.calendario_enviado_at, gl.total_interacciones
from gestion_leads gl
join clientes c on c.id = gl.cliente_id
join estados_lead e on e.id = gl.estado_id
where c.nombre like '[PRUEBA]%'
order by gl.updated_at desc;
```

Y la conversación completa (memoria append-only):

```sql
select al.created_at, al.ultimo_msg_lead, al.ultimo_msg_bot, al.summary, al.payload
from activity_log al
join clientes c on c.id = al.cliente_id
where c.nombre like '[PRUEBA]%'
order by al.created_at;
```

---

## 7. Limpiar los datos de prueba al terminar

**Ojo:** `activity_log` es append-only (un trigger bloquea el `DELETE`), y tiene
FK `RESTRICT` hacia `clientes`/`gestion_leads`. Por eso **no se puede borrar un
lead que ya tuvo actividad** — es un problema ya conocido en este proyecto.

Las 2 opciones reales:

**A) Marcarlos como terminales** (recomendado, es lo que hacen los tests e2e):

```sql
update gestion_leads gl
   set estado_id = (select id from estados_lead where codigo='descalificado')
  from clientes c
 where c.id = gl.cliente_id and c.nombre like '[PRUEBA]%';
```

**B) Borrado real** (solo si de verdad hace falta): hay que borrar en orden
`activity_log` → `gestion_leads` → `clientes`, y el `DELETE` sobre
`activity_log` requiere desactivar temporalmente `trg_log_inmutable`. Es una
operación destructiva sobre la base compartida: **no la hagas sin avisar.**

---

## 8. Lo que queda pendiente (fuera del alcance de esta prueba)

1. **SOP de Recuperación (bumps 30min/24h/72h).** Las plantillas están escritas
   (`P.BUMP_*`) pero el disparo por tiempo necesita un **Cron Trigger** de
   Cloudflare, no un webhook. Se hace después de validar el flujo base.
2. **Conectar el calendario real.** El estado `agendado` sigue llegando solo por
   la sincronización de Google Calendar que ya existe. Nada que cambiar en el bot.
3. **Empatía dinámica.** Está implementada y activa solo en 2 puntos (M2 y M3).
   Deliberadamente NO se antepone al pitch ni al link.

---

## 9. Decisiones — ✅ TODAS CERRADAS (1-sep-2026)

1. **`calificado` se marca al pasar los 3 filtros** (urgencia="ahora", antes del pitch). Confirmado. El envío del link se mide aparte en `calendario_enviado_at`. Encaja con el Scorecard de Javier, que ya trata `% Calificación` y `% Conversión a Agenda` como KPIs separados.
2. **Cuando el lead dice que asiste solo**, el bot responde un acuse corto y cálido: *"¡Listo, {nombre}! 🙌 Quedo pendiente de tu confirmación cuando separes tu espacio."* Aprobado.
3. **Se incorpora la pregunta de blindaje del show-up** (M5.5.d, copy literal del proyecto de Javier, validado en producción). Ataca el KPI `% Show Up > 70%`.
4. **Las inconsistencias del PDF V4.2 quedan solo documentadas** (sección 10). El código implementa el orden correcto; que las corrijan ellos en su documento.

### Texto histórico de cuando estaban abiertas

1. **Cuándo se marca `calificado`.** Lo puse cuando pasa los **3 filtros**
   (urgencia = "ahora", justo antes del pitch), no cuando se manda el link.
   Razón: es la definición de "calificado" del propio SOP, y así puedes medir
   aparte "cuántos calificaron" vs "cuántos recibieron el link"
   (`calendario_enviado_at`). Si lo prefieres atado al envío del link, es un
   cambio de una línea.
2. **Leads en estado terminal.** El bot NO responde a `perdido`, `nutricion`, ni
   a nada que ya sea del Setter/Closer (`agendado`, `show_up`, etc.): solo
   registra el mensaje. **Excepción:** `descalificado` sí lo escucha, porque el
   propio SOP V4.2 exige el RetornoLead automático.
3. **`M7_SOLO_ACK` es copy inventado.** Cuando el lead dice que asiste solo, el
   SOP le habla al Setter humano ("espera a que agende") en vez de darle un
   script. Un bot no puede quedarse mudo, así que puse un acuse mínimo, marcado
   en el código como `_extensionOperativa`. **Reemplázalo por copy oficial.**

## 10. Inconsistencias que encontré en el PDF de la V4.2

La renumeración de V4.2 (link pasó a M6, asistencia a M7) dejó referencias
viejas sin actualizar. No rompen nada porque implementé el flujo correcto, pero
conviene arreglarlas en el documento:

- **Bifurcación de Mensaje 5, Escenario A:** dice "Continuar al Mensaje 6
  (Asistencia)". En V4.2 el Mensaje 6 es el cierre + link; la asistencia es el 7.
- **Bifurcación post-Objeción 9, Escenario A:** dice "→ Mensaje 7 (cierre + link)".
  El cierre + link ahora es el Mensaje 6.
- **SOP de Recuperación:** el bloque titulado "Si el lead deja de responder en el
  Mensaje 7 (agendamiento)" se refiere al agendamiento, que ahora es el Mensaje 6.
- **Criterios de calificación (pág. 1):** dice "los 3 filtros" y lista 3, pero el
  texto de descalificación de la pág. 17 sigue mencionando el tope de "60% si
  gana >$9M" junto a un "> 60%" en el título del Script 2 — quedó consistente,
  solo vale la pena unificar el redondeo del margen borderline (usé 10 puntos
  sobre el tope, que es lo que dice "hasta ~10 puntos").
