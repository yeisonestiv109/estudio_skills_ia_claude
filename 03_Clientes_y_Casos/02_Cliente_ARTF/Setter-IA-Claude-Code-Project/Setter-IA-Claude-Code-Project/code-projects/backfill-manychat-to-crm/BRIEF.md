# Backfill — Migrar leads históricos de ManyChat al CRM Sheet

> **Para Claude Code:** este documento contiene todo el contexto necesario para construir el script de migración. Léelo completo antes de proponer el primer plan.

---

## 1. Objetivo

Sincronizar **todos los suscriptores de ManyChat** que aún no están en el Google Sheet del CRM, inferir su etapa actual del setter, y dejar el CRM como la única fuente de verdad del estado de cada lead.

**Estado actual:**
- ManyChat: **~900+ suscriptores** (la cifra exacta hay que confirmarla via API)
- Google Sheet (pestaña CRM): **245 filas**
- Diferencia: **~655 leads sin registrar**

**Causa raíz del gap:** durante varias semanas el flow de ManyChat tenía triggers deshabilitados / mensajes que no caían en ningún trigger / opt-ins de primer mensaje → el External Request al Worker nunca se disparó → el bridge al Sheet nunca corrió. Por eso hay leads que existen en ManyChat pero no en el CRM. (Ver `project_manychat_optin_behavior.md` en memoria si tienes acceso, o el flow de ManyChat para entender por qué.)

**Resultado esperado al terminar:**
1. Todos los suscriptores de ManyChat tienen una fila en el CRM con su info básica.
2. Cada lead tiene una **etapa inferida** lo más precisa posible a partir de su historial de mensajes y custom fields.
3. Todos los eventos relevantes quedan en `Activity Log` para auditoría.
4. El equipo puede filtrar el CRM por estado y empezar a procesar manualmente los leads pendientes.

---

## 2. Contexto del negocio (TL;DR)

**Resuelve Tus Finanzas (RTF)** es un negocio de mentoría financiera premium operado por:
- **Andrés Ramírez** — visionario, experto, cara pública (cuenta IG: `@resuelvetusfinanzas_`)
- **Catalina Rúa** — estratega comercial
- **Javier Suárez** — ops + IA (tú eres su Integrador IA)

El producto: programa de mentoría 1:1 de 8 semanas, $1.500 USD ticket promedio, target = profesionales colombianos $5M-$10M COP/mes con frustración financiera.

**El "Setter IA Javit"** es un chatbot que vive en ManyChat → Cloudflare Worker → Anthropic Claude → Apps Script → Google Sheets. Su trabajo es calificar leads que entran por DM/comentarios en Instagram y agendar llamadas con Andrés.

Stack actual:
```
IG comment / DM
   ↓
ManyChat (flow con triggers de keyword + IA)
   ↓
Cloudflare Worker (https://setter-ia-bridge.luisjavier-suarezmeza.workers.dev/)
   ↓
   ├─→ Anthropic Claude (genera respuesta + decide etapa)
   ├─→ Apps Script Web App (escribe al CRM)
   └─→ ManyChat API (aplica tags al contacto)
```

Cuando funciona bien, cada turno del usuario actualiza el CRM con la etapa, datos calificadores (profesión, salario, dolor, urgencia) y un activity log.

**Etapas del setter:** Inicial → M1 → M2 → M3 → M4 → M5 → M5.B → M5.C. Plus ramas: Descalificado, AgendaManual_1/2, Handoff, JavitOff.

---

## 3. Estado actual del CRM y de los sistemas

### 3.1 Google Sheet — CRM
- **Sheet ID:** `1iYLMAYV0XtN74ALBCmJkszUOpoINIt5tEs2CKGMvaf0`
- **Pestaña principal:** `CRM`
- **Pestaña de auditoría:** `Activity Log`

### 3.2 Estructura del CRM (columnas 1-indexed)

| Col | Letra | Campo | Notas |
|---|---|---|---|
| 1 | A | # | Auto-incremental |
| 2 | B | Nombre | Full name (first + last) |
| 3 | C | IG Handle | Sin `@`, lowercase, trim |
| 4 | D | Setter | Vacío en backfill; lo asigna humano luego |
| 5 | E | Fuente | "ig_comment", "ig_dm", "manual_backfill", etc. |
| 6 | F | Profesión | Opcional |
| 7 | G | Salario | COP millones (number) |
| 8 | H | Fecha Contacto | First seen (date+time) |
| 9 | I | Fecha Atendido | First message del bot (date+time) |
| 10 | J | **Estado** | Dropdown — ver `ESTADOS_VALIDOS` abajo |
| 11 | K | Fecha Agendamiento | |
| 12 | L | Fecha Llamada Programada | |
| 13 | M | WhatsApp | Manual |
| 14 | N | Correo | Manual |
| 15 | O | Fecha Llamada Realizada | |
| 16 | P | Fecha Pago | |
| 17 | Q | Revenue COP | |
| 18 | R | Upfront Cash COP | |
| 19 | S | Recurring Mensual | |
| 20 | T | Notas | |
| 21 | U | Dolor (A/B/C/D) | |
| 22 | V | Urgencia | "ahora" / "algun_dia" / "" |
| 23 | W | Handoff Razón | "javit_off", "agendamiento_manual_pendiente", etc. |
| 24 | X | Califica (Sí/No) | |
| 25 | Y | **ManyChat ID** | subscriber_id numérico (clave única) |

**Formato de fechas:** `yyyy-MM-dd HH:mm`, timezone `America/Bogota`.

### 3.3 ESTADOS_VALIDOS (dropdown en col J)

```js
const ESTADOS_VALIDOS = [
  'Lead Nuevo - Sin Atender',
  'M1 Enviado - Esperando P1',
  'P1 Respondida - Esperando M2',
  'M2 Enviado - Esperando dolor',
  'M2 D - Clarificación enviada',
  'M3 Enviado - Esperando urgencia',
  'M3 Enviado - Esperando respuesta',
  'M4 Enviado - Esperando agendar',
  'M4 Enviado - Esperando respuesta',
  'M4 Pitch + Objeción 5 manejada',
  'M4 Pitch personalizado',
  'M5 Enviado - Esperando Calendly',
  'Aceptó llamada - Pendiente datos',
  'Agendada - Sin datos',
  'Agendada - Confirmada',
  'Agendada - Manual sábado 30 10:30 AM',
  'Descalificado - Ingresos bajos',
  'Descalificado - Sin urgencia',
  'Handoff - Agendamiento manual',
  'Handoff - Pregunta precio',
  'Handoff - Crisis emocional',
  'Handoff - Ex cliente',
  'Handoff - Otro',
  'Ghosteo - Bump 1 enviado'
];
```

Si tu mapeo no calza con ninguno → usa `'Lead Nuevo - Sin Atender'` como fallback (más conservador).

---

## 4. Endpoints, autenticación y secretos

### 4.1 ManyChat API

- **Base:** `https://api.manychat.com/`
- **Auth:** header `Authorization: Bearer <token>`
- **Token (compartido por Javi para este uso):** `4978175:7140953bc232c3f4971776cce810a6a4`
- **Page ID:** `4978175` (el prefijo del token antes del `:`)

**Endpoints relevantes:**

| Endpoint | Método | Propósito |
|---|---|---|
| `/fb/page/getInfo` | GET | Verificar token + cuenta IG conectada |
| `/fb/subscriber/findByName` | GET | Buscar suscriptor por nombre (limitado) |
| `/fb/subscriber/findBySystemField` | GET | Buscar por `system_field` (email/phone) |
| `/fb/subscriber/findByCustomField` | GET | Buscar por custom field |
| `/fb/subscriber/getInfo` | GET | Detalle completo de un suscriptor por ID |
| `/fb/subscriber/getInfoByUserRef` | GET | Detalle por user_ref |
| `/fb/page/getTags` | GET | Lista todas las tags de la página |
| `/fb/page/getCustomFields` | GET | Lista todos los custom fields |

**⚠️ Limitación importante:** la API de ManyChat **NO tiene un endpoint público para listar todos los suscriptores paginados**. Para obtener la lista completa hay que usar uno de estos workarounds (de mejor a peor):

1. **Tag-based pagination:** crear una tag temporal en ManyChat ("backfill_done") y procesar suscriptores en batches que tengan/no tengan esa tag. Para esto se necesita la UI o un cron.
2. **Export desde la UI:** ManyChat tiene "Audience → Export CSV" que descarga todos los suscriptores con sus custom fields y tags. Esta es probablemente **la ruta más rápida**: exportar CSV una vez, leerlo desde el script, y procesarlo. Pedirle a Javi/Andrés que hagan el export.
3. **Iterar por subscriber_id incremental:** los IDs de ManyChat son numéricos secuenciales (ej. `1587113915`, `1853985680`). En teoría se podría iterar por rango, pero `getInfo` requiere un ID exacto, no soporta range queries.

**👉 Recomendación:** empezar con el **CSV export** (paso 2). El primer paso del proyecto debería ser pedirle al usuario que haga el export en ManyChat UI y suba el archivo al repo.

### 4.2 Apps Script Web App (CRM bridge)

- **URL:** la del Secret `APPS_SCRIPT_URL` en Cloudflare Worker (Javi te la pasa, formato `https://script.google.com/macros/s/.../exec`)
- **Método:** POST
- **Content-Type:** `application/json`

**Payload esperado (mínimo para insertar lead nuevo):**

```json
{
  "ig_username": "javi.suarez.m",
  "first_name": "Javier",
  "last_name": "Suárez",
  "full_name": "Javier Suárez",
  "manychat_subscriber_id": "1853985680",
  "fuente": "manual_backfill",
  "evento": "backfill_inicial",
  "etapa_actual": "Inicial",
  "etapa_anterior": "Inicial",
  "profesion": null,
  "ingreso_mensual_cop_M": null,
  "dolor_opcion": null,
  "urgencia": null,
  "califica": null,
  "handoff_humano": false,
  "handoff_razon": "",
  "ultimo_mensaje_lead": "",
  "ultimo_mensaje_bot": "",
  "summary": "Backfill desde ManyChat — etapa inferida automáticamente."
}
```

**Comportamiento del Apps Script:**
1. Busca el lead por `ig_username` o `manychat_subscriber_id` (cualquiera de los dos).
2. Si existe → actualiza solo campos no manuales (no toca WhatsApp/Correo/Revenue/etc.).
3. Si no existe → inserta nueva fila al final.
4. Siempre escribe una fila en `Activity Log` para trazabilidad.

**Response esperado:**
```json
{"ok": true, "action": "inserted", "row": 246, "estado": "Lead Nuevo - Sin Atender"}
```

### 4.3 Cloudflare Worker (referencia, NO se usa en backfill)

- **URL:** `https://setter-ia-bridge.luisjavier-suarezmeza.workers.dev/`
- **No lo invokes desde el backfill** — el Worker está pensado para tráfico en vivo de ManyChat (cada turno del usuario). Para backfill, pega directo al Apps Script.

---

## 5. Lógica de mapeo de etapas (inferencia)

Cada lead histórico de ManyChat tiene:
- **Custom fields:** posiblemente `etapa_actual`, `ingreso_mensual_cop_M`, `dolor_opcion`, `urgencia`, `califica`, `handoff_humano`, `handoff_razon`, `conversation_summary`, `fecha_ultimo_mensaje_setter`, `last_text`.
- **Tags:** `EXISTENTE_CONVERSACION`, `CONVERSACION_ACTIVA`, `REQUIERE_RESPUESTA_HUMANA`, `ATENDIDO_BOT`, `HANDOFF_ANDRES`, `M5_LINK_ENVIADO`, `DESCALIFICADO_INGRESO`, `ERROR_BOT`.

### Reglas de inferencia (en orden — primera que matchee, gana):

1. **Si `etapa_actual` custom field está seteado** → úsalo tal cual (es lo que dejó el bot en su último turno).

2. **Si tag `M5_LINK_ENVIADO`** → `etapa_actual = "M5"` → estado CRM = `'M5 Enviado - Esperando Calendly'`.

3. **Si tag `DESCALIFICADO_INGRESO`** → `etapa_actual = "Descalificado"`, `califica = false` → estado CRM = `'Descalificado - Ingresos bajos'`.

4. **Si tag `HANDOFF_ANDRES` Y tag `HANDOFF_AGENDA_MANUAL`** → `handoff_humano = true`, `handoff_razon = "agendamiento_manual_pendiente"` → estado CRM = `'Handoff - Agendamiento manual'`.

5. **Si tag `HANDOFF_ANDRES`** (sin razón específica) → `handoff_humano = true`, `handoff_razon = "manual"` → estado CRM = `'Handoff - Otro'`.

6. **Si tag `ATENDIDO_BOT`** (pero sin las anteriores) → bot habló al menos una vez pero no llegó a M5 → `etapa_actual = "M1"` (conservador) → estado CRM = `'M1 Enviado - Esperando P1'`.

7. **Si tag `REQUIERE_RESPUESTA_HUMANA` Y tag `EXISTENTE_CONVERSACION`** → el bot lo capturó en modo JAVIT_OFF → `etapa_actual = "JavitOff"` → estado CRM = `'Lead Nuevo - Sin Atender'`.

8. **Si tag `ERROR_BOT`** → fallback técnico → `handoff_humano = true`, `handoff_razon = "error_bot"` → estado CRM = `'Handoff - Otro'`.

9. **Si NINGUNA tag aplicable y NINGÚN custom field con datos** → lead nunca atendido → `etapa_actual = "Inicial"` → estado CRM = `'Lead Nuevo - Sin Atender'`.

### Campos a copiar 1-a-1 desde ManyChat custom fields → CRM:

| ManyChat custom field | CRM column |
|---|---|
| `profesion` | F (Profesión) |
| `ingreso_mensual_cop_M` | G (Salario) |
| `dolor_opcion` | U (Dolor) |
| `urgencia` | V (Urgencia) |
| `handoff_razon` | W (Handoff Razón) |
| `califica` | X (Califica) |
| `subscriber_id` | Y (ManyChat ID) |

### Fuente (col E):
- Si tiene tag/contexto de comentario en Reel → `"ig_comment"`
- Si tiene contexto de DM directo → `"ig_dm"`
- Si no se puede determinar → `"manual_backfill"`

---

## 6. Plan de implementación recomendado

### Fase 0 — Setup (30 min)
1. Crear proyecto Node.js / Python (la que prefieras — sugiero **Node.js** para coherencia con el Worker que ya es JS).
2. `.env` con: `MANYCHAT_TOKEN`, `APPS_SCRIPT_URL`, `SHEET_ID`.
3. Estructura sugerida:
   ```
   /backfill-manychat-to-crm
   ├── BRIEF.md (este archivo)
   ├── package.json
   ├── .env (no commitear)
   ├── .env.example
   ├── inputs/
   │   └── manychat-export-YYYY-MM-DD.csv  (lo sube Javi)
   ├── outputs/
   │   ├── 01-parsed-subscribers.json
   │   ├── 02-mapped-payloads.json
   │   ├── 03-already-in-crm.json
   │   ├── 04-to-insert.json
   │   ├── 05-insert-results.json
   │   └── 06-summary-report.md
   └── src/
       ├── 01-parse-csv.js          # CSV → JSON estructurado
       ├── 02-fetch-current-crm.js  # GET filas existentes del Sheet
       ├── 03-map-stages.js         # Aplica reglas de mapeo
       ├── 04-diff.js               # Decide insert vs skip
       ├── 05-push-to-crm.js        # POST al Apps Script con rate limit
       └── 06-report.js             # Resumen final
   ```

### Fase 1 — Conseguir el dataset (Javi hace export)
1. Pídele a Javi (en chat) que vaya a ManyChat → **Audience → Export → CSV**.
2. Pídele que seleccione TODOS los campos: nombre, IG handle, subscriber ID, tags, todos los custom fields, opt-in date, last interaction.
3. Que suba el CSV a `inputs/manychat-export-YYYY-MM-DD.csv`.

### Fase 2 — Parse y normalización (script 01)
- Leer el CSV con `papaparse` (Node) o `pandas` (Python).
- Normalizar IG handles (lowercase, sin `@`).
- Parsear tags (vienen como string CSV interno, ej. `"tag1,tag2,tag3"`).
- Parsear custom fields (un CF por columna en el CSV).
- Output: `outputs/01-parsed-subscribers.json` (array de objetos uno por suscriptor).

### Fase 3 — Snapshot del CRM actual (script 02)
- GET al Apps Script para listar IG handles + ManyChat IDs ya en el Sheet. Si el endpoint actual no expone esto, **agregar un GET handler nuevo al `apps-script-crm-bridge.gs`** que devuelva `[{ig_handle, manychat_id, row}]`.
- Output: `outputs/03-already-in-crm.json`.

> **Alternativa rápida:** descargar el CRM como CSV manualmente desde el Sheet y leerlo directo. Menos elegante pero evita tocar el Apps Script.

### Fase 4 — Mapeo de etapas (script 03)
- Aplicar las reglas de la sección 5 a cada suscriptor del CSV.
- Output: `outputs/02-mapped-payloads.json` — cada entry tiene el payload exacto que se le mandará al Apps Script.

### Fase 5 — Diff (script 04)
- Filtrar fuera los que ya están en el CRM (matchean por `ig_username` O `manychat_subscriber_id`).
- Output: `outputs/04-to-insert.json` (~655 entries esperados).

### Fase 6 — Insert al CRM (script 05)
- POST batch al Apps Script. **Rate limit obligatorio:** Apps Script tiene quota de ~20-30 req/min de mi experiencia previa. Hazlo a **1 request cada 2 segundos** para evitar throttle.
- Reintentar con backoff exponencial en 429 / 500.
- Loggear cada response. Si falla, dejarlo en `outputs/05-insert-results.json` con `status: "failed"`.
- **Idempotencia:** el Apps Script ya hace upsert por IG handle / ManyChat ID, así que reintentar la misma fila NO duplica.

### Fase 7 — Reporte final (script 06)
- Output: `outputs/06-summary-report.md` con:
  - Total subscribers en ManyChat (del CSV)
  - Ya en CRM antes del backfill
  - Insertados nuevos
  - Fallidos (con razón)
  - Distribución por estado final (cuántos quedaron en cada bucket del dropdown)

---

## 7. Gotchas y consideraciones

1. **Sanitización de placeholders ManyChat:** si algún field en el CSV viene con valor literal `{{cuf_XXX}}` o `{{user_id}}`, tratarlo como `null`/vacío. El Apps Script ya tiene `sanitizePayload()` que limpia esto, pero es bueno hacerlo upstream también.

2. **IG handle vacío:** algunos suscriptores de ManyChat no tienen IG handle (vienen por WhatsApp, web widget, etc.). En ese caso, usar `manychat_subscriber_id` como key única.

3. **`fecha_ultimo_mensaje_setter`:** si el CSV trae este campo con fecha pasada, usarlo en columna H (Fecha Contacto) para tener un histograma temporal correcto. Si está vacío, usar el `opt-in date` del suscriptor.

4. **Charset:** el CSV de ManyChat viene en UTF-8 con BOM. Configurar parser para manejarlo o el primer header sale con `﻿` al frente.

5. **Tags vienen como string CSV interno:** ej. `'CONVERSACION_ACTIVA,REQUIERE_RESPUESTA_HUMANA'`. Splitea por `,` y trimea cada uno.

6. **No dispares el Worker:** los inserts van DIRECTO al Apps Script. NO pasen por `https://setter-ia-bridge.luisjavier-suarezmeza.workers.dev/` porque eso gastaría tokens de Anthropic sin necesidad.

7. **JAVIT_ACTIVO no afecta al backfill:** el backfill solo escribe al Sheet, no toca el bot.

8. **Dry-run primero:** antes de correr el script 05 real, hacer un dry-run que solo loggee lo que MANDARÍA sin postear. Que Javi revise 10 entries random antes de soltar los 655 al CRM.

9. **Backup del CRM:** antes de empezar la fase 6, descargar una copia del Sheet (Archivo → Descargar → xlsx) como backup. Si algo sale mal, podemos restaurar.

10. **Idempotencia / re-runs:** el script debe ser seguro de correr 2 veces. El Apps Script hace upsert, así que la 2da corrida no duplica filas. Pero el `Activity Log` SÍ acumula filas — eso es deseable.

---

## 8. Criterios de éxito

- [ ] CSV parseado sin errores (`outputs/01-parsed-subscribers.json` tiene N entries iguales al N de líneas del CSV).
- [ ] Snapshot del CRM correcto (245 entries en `outputs/03-already-in-crm.json`).
- [ ] Diff genera ~655 entries en `outputs/04-to-insert.json` (margen ±50).
- [ ] Después del push, el Sheet tiene ~900 filas en CRM (suma de previas + insertadas).
- [ ] `Activity Log` tiene ~655 entries nuevas con `evento = "backfill_inicial"`.
- [ ] Reporte final muestra distribución por estado (la mayoría será `Lead Nuevo - Sin Atender`, pero esperamos un % considerable de `M1 Enviado - Esperando P1`, `Descalificado - *`, `Handoff - *`).
- [ ] Javi puede abrir el Sheet, filtrar por `Lead Nuevo - Sin Atender`, y empezar a procesarlos manualmente.

---

## 9. Lo que NO está en alcance

- No sincronizar mensajes individuales del histórico (solo metadata del lead).
- No modificar el flow de ManyChat ni el Worker.
- No mandar mensajes nuevos a los leads desde el backfill.
- No agregar campos nuevos al Sheet (solo poblar los existentes).
- No fix-ear el Worker para el tema de opt-in / Welcome Flow / triggers de comentarios — eso es trabajo separado.

---

## 10. Pregúntale a Javi antes de empezar

Si algo de esto no está claro o falta info, pregúntale a Javi en chat **antes** de codear. En particular:

1. ¿Puedes hacer el export CSV de ManyChat hoy? ¿O necesitas que te muestre cómo?
2. ¿Me confirmas la `APPS_SCRIPT_URL` actual? (es Secret, no está en este doc)
3. ¿La fuente (col E) la quieres como `"manual_backfill"` para todos los registrados, o prefieres que intentemos distinguir `ig_comment` vs `ig_dm` cuando se pueda?
4. ¿Hay leads del CSV que SABEMOS que están descalificados o ya cerrados como venta y quieres marcarlos manualmente antes de la migración? (lista de excepciones)
5. ¿Quieres que el backfill también dispare la tag `BACKFILL_DONE` en ManyChat para no procesarlos 2 veces si re-corres? (opcional)

---

## 11. Resumen ejecutivo (1 párrafo)

Hay 900+ leads en ManyChat y solo 245 en el CRM. Vamos a exportar el CSV completo desde ManyChat, parsearlo en Node.js, inferir la etapa de cada lead a partir de sus tags y custom fields aplicando reglas deterministas, hacer diff contra el CRM actual, y postear al Apps Script bridge un payload por lead nuevo respetando rate limit. Resultado: CRM completo, equipo puede empezar a procesar la cola atrasada. Tiempo estimado: 4-6 horas de desarrollo + 30-60 min de ejecución.
