# Guía Paso a Paso — ManyChat Pro (Opción A: JSON path nativo)

> **Esta es la ruta oficial de implementación.** Tienes ManyChat Pro, así que usaremos JSON path nativo (sin middleware externo). Sigue cada paso EN ORDEN.

---

## ⚙️ Pre-flight check

Antes de empezar, verifica que tu cuenta de ManyChat:
- ✅ Está conectada a Instagram (cuenta `@andresresuelvetusfinanzas`).
- ✅ Tiene Pro activo (Settings → Billing).
- ✅ La integración con Claude API está activa (Settings → Apps & Integrations → "Claude").

---

## PASO 1 — Crear Custom Fields (15 min)

**Settings → Custom Fields → User Fields → New Field**

Crea estos **15 campos** uno por uno:

| # | Nombre | Tipo | Default | Notas |
|---|---|---|---|---|
| 1 | `etapa_actual` | Text | `M1` | Última etapa del lead |
| 2 | `profesion` | Text | (vacío) | Profesión extraída del lead |
| 3 | `ingreso_mensual_cop_M` | Number | `0` | Millones COP, ej: 8.5 |
| 4 | `dolor_opcion` | Text | (vacío) | A, B, C, o D |
| 5 | `urgencia` | Text | `desconocida` | ahora / algun_dia / desconocida |
| 6 | `califica` | Boolean | `false` | true = pasó filtro avatar |
| 7 | `handoff_humano` | Boolean | `false` | true = notificar a Andrés |
| 8 | `razon_handoff` | Text | (vacío) | Por qué se escaló |
| 9 | `caso_exito_usado` | Text | (vacío) | Carlos / Sandra / ninguno |
| 10 | `claude_response_json` | Text | (vacío) | Respuesta cruda de Claude |
| 11 | `mensaje_lead_0` | Text | (vacío) | Primera burbuja |
| 12 | `mensaje_lead_1` | Text | (vacío) | Segunda burbuja |
| 13 | `mensaje_lead_2` | Text | (vacío) | Tercera burbuja |
| 14 | `fecha_ultimo_mensaje_setter` | DateTime | (vacío) | Para timing de bumps |
| 15 | `agendamiento_fecha` | Text | (vacío) | Si agenda manual |

---

## PASO 2 — Crear Tags (5 min)

**Settings → Tags → New Tag**

Crea estos **8 tags**:
- `CALIFICA`
- `M4_PITCH_ENVIADO`
- `M5_LINK_ENVIADO`
- `AGENDADO`
- `HANDOFF_ANDRES`
- `NURTURE_LARGO_PLAZO`
- `DESCALIFICADO_INGRESO`
- `DESCALIFICADO_TIMING`

---

## PASO 3 — Configurar la acción Claude (10 min)

**En la ventana "Editar Acciones de Claude" que ya tienes abierta:**

| Campo | Valor |
|---|---|
| **Modelo** | Claude Sonnet 4.6 ✅ (ya está) |
| **Mensaje del sistema** | Pegar TODO el bloque del archivo `system-prompt-condensado.md` (entre las líneas ``` ``` ```) |
| **Último mensaje del usuario** | Seleccionar `{{Last User Message}}` (o el equivalente en tu cuenta — el dropdown te muestra opciones) |
| **Guardar resultado en** | Custom Field: `claude_response_json` |
| **Opciones Avanzadas → Tokens máximos** | 🚨 Cambiar de **200 → 2048** |
| **Temperatura** | 0 ✅ (ya está) |

**Clic en "Guardar".**

---

## PASO 4 — Construir el parser con JSON path (15 min)

Después de la acción Claude, agrega 11 **"Set Custom Field"** seguidos:

### Bloque 4.1 — Extraer mensajes (3 nodos)

| Custom Field | Valor (JSON path) |
|---|---|
| `mensaje_lead_0` | `{{claude_response_json[0].mensaje_para_lead[0]}}` |
| `mensaje_lead_1` | `{{claude_response_json[0].mensaje_para_lead[1]}}` |
| `mensaje_lead_2` | `{{claude_response_json[0].mensaje_para_lead[2]}}` |

> **Nota:** La sintaxis exacta de JSON path en ManyChat puede ser ligeramente distinta. Si `{{claude_response_json[0]...}}` no funciona, prueba `{{claude_response_json.mensaje_para_lead[0]}}` o `{{cuf_claude_response_json.mensaje_para_lead[0]}}`. ManyChat suele autocompletar cuando tipeas `{{`.

### Bloque 4.2 — Extraer metadata (8 nodos)

| Custom Field | Valor |
|---|---|
| `etapa_actual` | `{{claude_response_json.etapa_nueva}}` |
| `califica` | `{{claude_response_json.califica}}` |
| `profesion` | `{{claude_response_json.metadata.profesion}}` |
| `ingreso_mensual_cop_M` | `{{claude_response_json.metadata.ingreso_mensual_cop_M}}` |
| `dolor_opcion` | `{{claude_response_json.metadata.dolor_opcion}}` |
| `urgencia` | `{{claude_response_json.metadata.urgencia}}` |
| `handoff_humano` | `{{claude_response_json.metadata.handoff_humano}}` |
| `caso_exito_usado` | `{{claude_response_json.metadata.caso_exito_usado}}` |
| `razon_handoff` | `{{claude_response_json.metadata.razon_handoff}}` |

---

## PASO 5 — Enviar los mensajes al lead (5 min)

Después del parser, agrega:

### 5.1 — Condition: ¿Es handoff?
- **If** `handoff_humano` is `true` → ir a sub-flow **HANDOFF** (Paso 9)
- **Else** → continuar a 5.2

### 5.2 — Send Message 1
- **Action: Send Message**
- **Text:** `{{mensaje_lead_0}}`
- **Condition:** Solo enviar si `{{mensaje_lead_0}}` is not empty

### 5.3 — Delay 2 segundos
- **Action: Delay → 2 seconds**

### 5.4 — Send Message 2 (con typing indicator)
- **Action: Send Message**
- **Text:** `{{mensaje_lead_1}}`
- **Condition:** Solo enviar si `{{mensaje_lead_1}}` is not empty

### 5.5 — Delay 2 segundos

### 5.6 — Send Message 3
- **Action: Send Message**
- **Text:** `{{mensaje_lead_2}}`
- **Condition:** Solo enviar si `{{mensaje_lead_2}}` is not empty

### 5.7 — Set timestamp
- **Action: Set Custom Field**
- **Field:** `fecha_ultimo_mensaje_setter`
- **Value:** `{{system.current_datetime}}` (o equivalente en tu cuenta)

---

## PASO 6 — Loop de espera de respuesta (10 min)

Después de los Send Message:

### 6.1 — User Input Node
- **Action: Wait for user reply**
- **Save reply to:** `{{Last User Message}}` (variable de sistema)

### 6.2 — Volver al nodo Claude
- **Conexión:** Output del User Input → Input del nodo Claude del Paso 3

**Esto crea el loop:** el lead responde → Claude procesa → ManyChat envía → espera respuesta → Claude procesa → loop.

### 6.3 — Salidas del loop
El loop se ROMPE cuando:
- `etapa_actual == "M5"` → ir a sub-flow **POST-M5 (esperar agendamiento)**
- `etapa_actual == "Descalificado"` → ir a sub-flow **DESCALIFICADO** (Stop flow)
- `etapa_actual == "Handoff"` → ir a sub-flow **HANDOFF**

---

## PASO 7 — Trigger inicial: comentario "CONTROL" (10 min)

**Growth Tools → Instagram → Comment Reply Growth Tool**

| Campo | Valor |
|---|---|
| **Trigger** | When user comments on any post / specific post |
| **Keyword(s)** | `CONTROL` (también: `control`, `Control`) |
| **Public reply** | (opcional, ej: "Te escribo por DM 📩") |
| **Send a private message to commenter** | ✅ Activar |
| **Initial DM (M0)** | `¡Hola! {{first_name}} 👋 Vi que te interesaste en el caso de Camila y en tomar el control de tu dinero. Escríbeme la palabra CONTROL para empezar.` |
| **After lead replies "CONTROL"** | Iniciar flow → **Setter IA Principal** (el que armaste en Pasos 3-6) |

---

## PASO 8 — Test con cuenta de prueba (10 min)

1. Desde una cuenta IG personal (NO la de Andrés), comenta "CONTROL" en cualquier reel de `@andresresuelvetusfinanzas`.
2. Verifica que:
   - ✅ Recibes el M0 automático.
   - ✅ Al escribir "CONTROL" en el DM, Claude responde con M1.
   - ✅ Si dices "Soy médico, gano 8 millones", Claude pasa a M2 con las opciones.
   - ✅ Custom field `etapa_actual` cambia de M1 → M2.
   - ✅ Si dices "B", Claude pasa a M3 con caso adaptado.
   - ✅ Si dices "Prioridad ahora", Claude pasa a M4 PITCH.
   - ✅ Si dices "Sí, agendemos", Claude pasa a M5 con el link de Calendly aislado.

Si algo falla → revisa `claude_response_json` para ver qué devolvió Claude.

---

## PASO 9 — Sub-flow HANDOFF (Fase 2)

**Cuando `handoff_humano == true`:**

1. **Add tag** `HANDOFF_ANDRES`
2. **External Request** → Email notification a `javier.suarez@thebitbang.company`:
   - Subject: `🚨 Setter IA — Handoff: {{first_name}}`
   - Body: 
     ```
     Lead requiere atención humana.
     
     Nombre: {{first_name}} {{last_name}}
     IG: @{{ig_username}}
     Etapa: {{etapa_actual}}
     Razón: {{razon_handoff}}
     Profesión: {{profesion}}
     Ingreso (M COP): {{ingreso_mensual_cop_M}}
     Dolor: {{dolor_opcion}}
     Urgencia: {{urgencia}}
     
     Link al DM: https://www.instagram.com/direct/t/{{thread_id}}/
     ```
3. **Stop flow** (no más respuestas automáticas para este lead hasta que se desactive el tag).

---

## PASO 10 — Sub-flows de Bumps (Fase 2)

Estos NO necesitan a Claude (son texto fijo). Usa **Smart Delay** con condiciones.

### Bump 1 General — 30 min sin respuesta
**Trigger:** Time elapsed since `fecha_ultimo_mensaje_setter` > 30 min  
**Condition:** `etapa_actual` ∈ {M1, M2, M3}  
**Action:** Send Message:
```
Hola {{first_name}}, quedé pendiente de tu respuesta para entender un poco mejor tu contexto y ver si realmente te puedo ayudar.
```

### Bump 1 Agendamiento — 30 min sin respuesta
**Trigger:** Time elapsed since `fecha_ultimo_mensaje_setter` > 30 min  
**Condition:** `etapa_actual` ∈ {M4, M5}  
**Action:** Send Message:
```
{{first_name}}, ¿quedó alguna duda antes de agendar?

¿Se fue la señal? 😄
```

### Bump 2 — 24h sin respuesta
**Trigger:** Time elapsed since `fecha_ultimo_mensaje_setter` > 24h  
**Action:** Send Message según etapa (texto exacto en `scripts/bumps-recuperacion.md`).

### Bump 3 — 72h (ÚLTIMO)
**Trigger:** Time elapsed > 72h  
**Action:**
```
{{first_name}}, me alegra que hayas llegado hasta aquí, aunque no hayamos podido hablar. 😊 Te dejo este video que a mucha gente le ha servido un montón: https://www.instagram.com/reel/DX73ACPNvRV/?igsh=MXQ3anYycWUzNXBoMA==

Si algo resuena contigo, ya sabes dónde encontrarme. ¡Éxitos!
```
**Add tag** `NURTURE_LARGO_PLAZO`. **Stop bump sequence.**

---

## Checklist final antes de ir LIVE

- [ ] Los 15 custom fields creados
- [ ] Los 8 tags creados
- [ ] System prompt pegado en acción Claude
- [ ] Tokens máximos en 2048
- [ ] Parser de 11 nodos Set Custom Field
- [ ] Send Message × 3 con delays
- [ ] Loop de espera funcionando
- [ ] Trigger "CONTROL" en Growth Tools activo
- [ ] Test con cuenta personal pasó M1 → M7 sin errores (V4.2)
- [ ] Sub-flow HANDOFF configurado y probado
- [ ] (Fase 2) Bumps automáticos configurados
- [ ] (Fase 3) Google Sheets sync funcionando

---

## Si algo se rompe

**Problema:** Claude responde texto en lugar de JSON.  
**Solución:** Verificar que el system prompt tenga la sección "FORMATO DE SALIDA OBLIGATORIO" con el JSON template. Si persiste, agregar al final del system prompt: `"IMPORTANTE: tu respuesta DEBE ser solo JSON puro, sin markdown ni texto adicional."`

**Problema:** JSON path no extrae los valores.  
**Solución:** Verificar la sintaxis exacta de ManyChat. Probar en orden: `{{claude_response_json.etapa_nueva}}`, `{{cuf_claude_response_json.etapa_nueva}}`, `{{$.etapa_nueva}}`. Si ninguno funciona, usar External Request a un Cloudflare Worker (código en `parser-json.md`).

**Problema:** El lead recibe el mismo mensaje 2 veces.  
**Solución:** Revisar que el loop tenga "Wait for user reply" — si no, el flujo no se pausa.

**Problema:** Los `mensaje_lead_1` y `mensaje_lead_2` envían mensajes vacíos.  
**Solución:** Agregar Condition "is not empty" antes de cada Send Message.

---

## Métricas a vigilar la primera semana

- **% de M1 → M2** (debería ser >40% si los ads atraen al avatar correcto)
- **% de M2 → M3** (debería ser >80% si M2 está bien escrito)
- **% de M3 → M4** (calidad de urgencia)
- **% de M4 → M5** (calidad del PITCH)
- **% de M5 → Agendado en Calendly** (calidad del link/timing)
- **% de Handoffs** (debería ser <10%; si >20% el SOP necesita refinarse)
- **Costo por lead procesado** (objetivo: <$0.20 USD)

---

**Tiempo total estimado: 1-1.5 horas para Fase 1 MVP funcionando.**
