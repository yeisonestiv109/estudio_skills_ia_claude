# Guía de despliegue — Bot conversacional ARTF (SOP V4.2)

**Fecha:** 1-sep-2026 · **Estado:** listo para la prueba con cuentas de prueba.

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
| Tests | `Scrips_Worker_and_AppScript/tests/` | 52 tests, `node --test` |
| Migraciones | `artf-pipeline-app/supabase/migrations/20260901*` | Campos nuevos + `fn_bot_get_estado` + `fn_bot_procesar_turno` |

**Ya aplicado en la base** (las 3 migraciones corrieron y están verificadas).

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
  -d '{"manychat_subscriber_id":"999888777","last_text":"CONTROL","first_name":"Prueba","fuente":"comentario"}'
```

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
`HANDOFF_OBJECION_FUERA_PLAYBOOK`, `HANDOFF_AMBIGUO`, `HANDOFF_EX_CLIENTE`,
`HANDOFF_ERROR_TECNICO`.

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
- **Headers:** `Content-Type: application/json`
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

> **Por qué 3 mensajes separados:** el SOP exige que el link del calendario vaya
> **aislado en su propia burbuja** (Instagram lo rompe si le pegas texto justo
> después). En el turno del cierre el Worker manda: `msg` = link,
> `msg2` = "Confirmame cuando te hayas agendado…", `msg3` = la pregunta de si
> asiste solo o acompañado.

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
| 6 | `dale, agendemos` | Llegan 3 mensajes: link solo, "confirmame", y la pregunta de acompañante. `calendario_enviado_at` se llena. **El estado NO pasa a `agendado`** |
| 7 | `voy solo` | Acuse corto. `asiste_acompanado=false` |
| 8 | `ya agendé` | Llegan las 2 preguntas pre-llamada. `etapa_bot=CIERRE_PRECALL` |

### Caminos que también hay que probar (con la segunda cuenta)

| Escribe | Debe pasar |
|---|---|
| `gano el mínimo integral` (en M1) | **NO descalifica.** Pide la cifra exacta |
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

## 9. Decisiones que tomé y conviene que confirmes

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
