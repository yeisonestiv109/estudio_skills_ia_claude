# Paso a Paso · Sincronización al CRM (Apps Script + Worker)

Objetivo: que cada turno del bot escriba/actualice una fila en el CRM Google Sheet ("Leads Campaña 1 Reconexión Financiera") + escriba un evento en la pestaña "Activity Log" para auditoría.

Arquitectura: **ManyChat → Cloudflare Worker → Anthropic** (devuelve a ManyChat) **→ Apps Script → Google Sheet** (en background, no bloquea).

---

## Paso 1 — Agregar las 5 columnas nuevas al CRM

En la pestaña **CRM** del sheet, agregar 5 columnas a la derecha de la columna T (Notas):

| Columna | Header exacto | Tipo | Validación de datos |
|---|---|---|---|
| U | `Dolor` | Dropdown | A, B, C, D, AB, AC, AD, BC, BD, CD |
| V | `Urgencia` | Dropdown | ahora, algun_dia |
| W | `Handoff Razón` | Text libre | — |
| X | `Califica` | Dropdown | Sí, No |
| Y | `ManyChat ID` | Text / Number | — |

**Tip rápido:** click en columna U → escribir el header → Datos → Validación de datos → Lista de elementos → pegar las opciones.

---

## Paso 2 — Crear la pestaña "Activity Log"

1. Click en el `+` abajo a la izquierda para agregar una pestaña nueva.
2. Renombrar a **`Activity Log`** (exactamente así, con espacio).
3. En la fila 1, pegar este header (selecciona A1 y pega):

```
Timestamp	IG Handle	Nombre	Evento	Etapa Actual	Etapa Anterior	Profesión	Ingreso (M COP)	Dolor	Urgencia	Califica	Handoff	Handoff Razón	Último msg lead	Último msg bot	Summary
```

4. Formatea la fila 1: bold + relleno gris claro + freeze row 1 (Ver → Inmovilizar → 1 fila).

---

## Paso 3 — Crear el Apps Script

1. En el sheet → menú **Extensiones → Apps Script**.
2. Se abre el editor de Apps Script en una pestaña nueva.
3. Borra el código por defecto (`function myFunction() {}`).
4. Abre el archivo local `apps-script-crm-bridge.gs` y copia TODO el contenido.
5. Pégalo en el editor de Apps Script.
6. Click en el ícono de disquete (Guardar) — proyecto sin título → ponle nombre **`Setter IA CRM Bridge`**.

### Test inicial dentro del editor

Antes de publicar, prueba que el script funciona desde el editor:

1. En el dropdown de funciones (arriba), selecciona **`testInsertNewLead`**.
2. Click en **Ejecutar**.
3. La primera vez te pedirá permisos:
   - "Revisar permisos" → tu cuenta de Google
   - Click en "Avanzado" → "Ir a Setter IA CRM Bridge (no seguro)"
   - "Permitir"
4. Ve al sheet, pestaña CRM. Debe aparecer una nueva fila con IG Handle = `@test_lead_javit`, Nombre = `TestLead`.
5. Ve a la pestaña Activity Log. Debe aparecer una fila con el evento `lead_nuevo`.

Si esto funciona, el script está OK. **Borra la fila de prueba del CRM** (manual) antes de seguir.

---

## Paso 4 — Desplegar como Web App

1. En el editor de Apps Script, click en **Implementar** (botón azul arriba derecha) → **Nueva implementación**.
2. ⚙️ Tipo de implementación → selecciona **Aplicación web**.
3. Configuración:
   - **Descripción:** `Setter IA CRM Bridge v1`
   - **Ejecutar como:** `Yo (luisjavier.suarezmeza@gmail.com)`
   - **Quién tiene acceso:** `Cualquier persona` ⚠️ (esto es necesario para que el Worker pueda llamarla sin auth)
4. Click **Implementar**.
5. Te muestra una URL tipo: `https://script.google.com/macros/s/AKfycb.../exec`
6. **Copia esa URL completa.** La vas a necesitar en el siguiente paso.

⚠️ Cada vez que cambies el código y quieras publicar, debes hacer "Nueva implementación" o "Gestionar implementaciones → Editar → Nueva versión".

---

## Paso 5 — Agregar la URL como Secret en Cloudflare

1. Ve a [dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages → `setter-ia-bridge`.
2. Settings → Variables and Secrets.
3. **Add → Secret**:
   - Name: `APPS_SCRIPT_URL`
   - Value: pega la URL que copiaste del paso 4.
4. Save.

---

## Paso 6 — Actualizar el código del Worker

El archivo `cloudflare-worker.js` ya tiene los cambios. Necesitas redeployarlo:

1. En Cloudflare dashboard → tu worker → **Edit code**.
2. Selecciona todo (Cmd+A) → borra.
3. Abre el archivo local `cloudflare-worker.js` y copia todo.
4. Pega en el editor de Cloudflare.
5. **Save and deploy**.

---

## Paso 7 — Actualizar el Body del External Request en ManyChat

El Worker ahora necesita 3 campos más para sincronizar al CRM:
- `ig_username` (el usuario de Instagram del lead)
- `manychat_subscriber_id` (ID interno de ManyChat)
- `fuente` (de dónde llegó el lead — por ahora opcional)

1. En ManyChat → flow "Setter IA v2.0" → nodo "Acciones" → click en el External Request.
2. Tab **Cuerpo**. El JSON actual tiene 8 campos. Necesitas agregar 3 más:

```json
{
  "last_text": "{{Last Text Input}}",
  "first_name": "{{first_name}}",
  "ig_username": "{{ig_username}}",
  "manychat_subscriber_id": "{{user_id}}",
  "fuente": "{{fuente}}",
  "conversation_summary": "{{conversation_summary}}",
  "etapa_actual": "{{etapa_actual}}",
  "profesion": "{{profesion}}",
  "ingreso_mensual_cop_M": "{{ingreso_mensual_cop_M}}",
  "dolor_opcion": "{{dolor_opcion}}",
  "urgencia": "{{urgencia}}"
}
```

⚠️ **Pills a insertar** (no como texto literal, sino seleccionándolas del selector de variables):
- `{{ig_username}}` → System Field: `IG Username` (o `Instagram Username`)
- `{{user_id}}` → System Field: `User ID` (es el manychat_subscriber_id)
- `{{fuente}}` → Custom Field nuevo, tipo Text — créalo si no existe. Por ahora puede quedar vacío.

3. Click **Probar Solicitud** para validar que el JSON es válido (Vista previa en verde).
4. **Guardar**.
5. Vuelve al canvas → click **Actualizar** arriba para publicar el flow.

---

## Paso 8 — Prueba end-to-end

1. Limpia los custom fields y tags del contacto Javier Suárez en ManyChat.
2. Manda "TestJavi" o "Control" en Instagram DM desde tu cuenta personal.
3. Verifica:
   - Bot responde el M1 normal (latencia debe ser similar a antes, ~3-5s).
   - En el sheet pestaña **CRM** → aparece nueva fila al final con tu info.
   - En la pestaña **Activity Log** → aparece evento `lead_nuevo`.
4. Continúa la conversación (responde profesión, A/B, etc.).
5. Verifica que la fila del CRM se va actualizando con cada turno (Fecha Atendido cambia, Estado avanza, etc.).
6. Verifica que cada turno agrega una nueva fila al Activity Log.

---

## Troubleshooting

### El CRM no se actualiza pero el bot responde normal

- Revisa los logs del Worker en Cloudflare (pestaña Logs en tiempo real).
- Busca líneas tipo `Error sincronizando al CRM:` o `Apps Script error:`.
- Verifica que el Secret `APPS_SCRIPT_URL` esté bien configurado (sin espacios, URL completa con `/exec` al final).

### El Apps Script da error 401/403

- Probablemente desplegaste con "Solo yo" en vez de "Cualquier persona". Vuelve al editor → Implementar → Gestionar implementaciones → editar → Nueva versión → cambiar a "Cualquier persona".

### El Apps Script da error de columnas

- Verifica que creaste las 5 columnas U-Y con los headers exactos.
- Si no las creaste todavía, el script falla al buscar por ManyChat ID. Crea primero las columnas.

### El bot responde lento después del cambio

- No debería. La llamada al Apps Script es asíncrona (`ctx.waitUntil`). Si notas latencia, revisa que el Worker tenga la firma `async fetch(request, env, ctx)` con `ctx`.

---

## Lo que ya queda automatizado en el CRM

Después de esto, cada lead que entre al bot tendrá automáticamente:

✅ Nueva fila en CRM con: Nombre, IG Handle, Setter=Javit, Fuente, Profesión, Salario, Fecha Contacto, Fecha Atendido, Estado (con etapa actual), Dolor, Urgencia, Califica, Handoff Razón, ManyChat ID, Notas.

✅ Activity Log con timestamp de cada turno: mensaje del lead, mensaje del bot, transición de etapa.

✅ Estado del CRM siempre fresco (cada turno actualiza Fecha Atendido + Estado).

## Lo que queda manual (no lo toca el bot)

- WhatsApp (M), Correo (N) → Andrés/Catalina llenan post-handoff
- Fecha Llamada Realizada (O), Fecha Pago (P) → post-llamada
- Revenue (Q), Upfront (R), Recurring (S) → post-venta
- Fecha Llamada Programada (L) → idealmente desde Calendly webhook (fase futura)

---

## Historial de cambios

- **2026-05-26:** Documento creado. Setter default = "Javit". 5 columnas U-Y agregadas. Activity Log secundario para auditoría completa.
