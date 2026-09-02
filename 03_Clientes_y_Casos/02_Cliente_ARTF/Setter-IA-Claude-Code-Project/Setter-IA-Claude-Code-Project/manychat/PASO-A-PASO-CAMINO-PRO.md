# Camino Pro — Implementación completa Setter IA con Cloudflare Worker

> **Arquitectura:** ManyChat (estado) → External Request → Cloudflare Worker → Anthropic API → JSON limpio → ManyChat (parsea con Response Mapping) → mensaje al lead.

> **Tiempo estimado:** 1.5h - 2h

---

## Roadmap

```
PASO 1  → Crear cuenta Cloudflare
PASO 2  → Crear Worker nuevo
PASO 3  → Pegar el código del worker
PASO 4  → Configurar Secret ANTHROPIC_API_KEY
PASO 5  → Deploy y obtener URL pública
PASO 6  → Test del worker con curl/Postman
PASO 7  → Actualizar Custom Fields en ManyChat
PASO 8  → Eliminar acción "Acciones de Claude" del flow
PASO 9  → Crear External Request al worker
PASO 10 → Configurar Response Mapping (JSON path)
PASO 11 → Actualizar Conditions del flow (usar etapa_actual)
PASO 12 → Test end-to-end
```

---

## PASO 1 — Cuenta Cloudflare

1. Ir a https://dash.cloudflare.com/sign-up.
2. Crear cuenta gratis con email + contraseña.
3. En el menú izquierdo: **Workers & Pages**.
4. Si pide subdominio inicial, configurarlo (ej: `javier-bitbang`). Esto define la URL base del worker: `<worker-name>.<subdominio>.workers.dev`.

## PASO 2 — Crear Worker nuevo

1. En Workers & Pages → **Create application** → **Create Worker**.
2. Nombre del worker: `setter-ia-bridge` (o similar).
3. Clic en **Deploy** para crear el worker básico.
4. Una vez creado, clic en **Edit Code** para abrir el editor online.

## PASO 3 — Pegar el código del worker

1. En el editor online, **borrar TODO el código por defecto** (el "Hello World" que viene).
2. Copiar TODO el contenido del archivo `cloudflare-worker.js` (en `/manychat/`).
3. Pegar en el editor.
4. Clic en **Save and Deploy** (arriba derecha).

## PASO 4 — Configurar Secret ANTHROPIC_API_KEY

> ⚠️ NUNCA hardcodees la API key en el código. Va como Secret de Cloudflare.

1. En el panel del worker → **Settings** → **Variables and Secrets**.
2. Clic en **+ Add variable** → seleccionar tipo **Secret** (no Plain text).
3. Variable name: `ANTHROPIC_API_KEY`
4. Value: tu API key de Anthropic (la misma que tienes en ManyChat para la integración nativa). Empieza con `sk-ant-...`.
5. Clic en **Save and Deploy**.

**Si NO tienes API key:**
- Ve a https://console.anthropic.com/settings/keys → **Create Key**.
- Cópiala (solo se muestra UNA vez).
- Asegúrate que tu cuenta tenga créditos (≥$5 USD).

## PASO 5 — Obtener URL pública del worker

En el panel del worker, busca el dominio asignado. Será algo como:
```
https://setter-ia-bridge.javier-bitbang.workers.dev
```

**Cópiala** — la vas a usar en ManyChat.

## PASO 6 — Test del worker (CRÍTICO antes de seguir)

Antes de tocar ManyChat, prueba el worker desde tu terminal:

```bash
curl -X POST https://setter-ia-bridge.javier-bitbang.workers.dev \
  -H "Content-Type: application/json" \
  -d '{
    "last_text": "Control",
    "first_name": "Javier",
    "conversation_summary": "",
    "etapa_actual": "Inicial",
    "profesion": "",
    "ingreso_mensual_cop_M": null,
    "dolor_opcion": "",
    "urgencia": ""
  }'
```

**Respuesta esperada (JSON):**
```json
{
  "msg": "Javier, te entiendo, no tener el control real de tu dinero es la frustración #1 de los profesionales que ganan bien. Para ver si te puedo ayudar, cuéntame: ¿a qué te dedicas y cuánto ganas al mes?",
  "etapa": "M1",
  "profesion": null,
  "ingreso_mensual_cop_M": null,
  "dolor_opcion": null,
  "urgencia": null,
  "califica": null,
  "summary": "Primer contacto, esperando profesión e ingreso",
  "handoff_humano": false,
  "handoff_razon": null
}
```

**Test 2 — Turno 2 (validar lógica de etapa):**

```bash
curl -X POST https://setter-ia-bridge.javier-bitbang.workers.dev \
  -H "Content-Type: application/json" \
  -d '{
    "last_text": "Soy ingeniero y gano 8 millones",
    "first_name": "Javier",
    "conversation_summary": "Primer contacto, esperando profesión e ingreso",
    "etapa_actual": "M1",
    "profesion": "",
    "ingreso_mensual_cop_M": null,
    "dolor_opcion": "",
    "urgencia": ""
  }'
```

**Respuesta esperada:** etapa = "M2", profesion = "ingeniero", ingreso_mensual_cop_M = 8.

**Si los 2 tests pasan**, el worker funciona perfecto. Avanza al Paso 7.

**Si fallan**: revisar logs en Cloudflare (panel del worker → **Logs** → **Real-time**).

## PASO 7 — Actualizar Custom Fields en ManyChat

Vas a necesitar estos custom fields (algunos ya los tienes):

| Campo | Tipo | Notas |
|---|---|---|
| `etapa_actual` | Text | Ya existe ✅ |
| `profesion` | Text | Crear si no existe |
| `ingreso_mensual_cop_M` | Number | Crear si no existe |
| `dolor_opcion` | Text | Crear si no existe |
| `urgencia` | Text | Crear si no existe |
| `califica` | Boolean | Crear si no existe |
| `claude_msg` | Text | **NUEVO** — el mensaje al lead |
| `conversation_summary` | Text | **NUEVO** — resumen acumulado |
| `handoff_humano` | Boolean | Ya existe ✅ |
| `handoff_razon` | Text | Crear si no existe |
| `fecha_ultimo_mensaje_setter` | DateTime | Ya existe ✅ |

> Puedes ELIMINAR `historial_conversacion` y `claude_response_json` — ya no se usan en el Camino Pro.

## PASO 8 — Eliminar acción "Acciones de Claude" del flow

1. Abre el flow "Setter IA v1.0" en ManyChat.
2. Edita el nodo "Acciones" principal.
3. **Borra la acción "Acciones de Claude — Request"**.
4. **Borra también la acción "Establecer historial_conversacion"** (ya no la necesitamos).
5. Mantén:
   - Establecer `fecha_ultimo_mensaje_setter`
   - Añadir etiqueta `CONVERSACION_ACTIVA`

> ⚠️ NO toques las Conditions todavía. Las actualizaremos en el Paso 11.

## PASO 9 — Crear External Request al worker

1. En el nodo "Acciones", clic en **+ Acción**.
2. **Busca "Solicitud Externa" / "External Request" / "Realizar Solicitud"** (puede estar en Dev Tools o categoría similar).
3. Configura:
   - **Method:** POST
   - **URL:** la URL de tu worker (del Paso 5)
   - **Body type:** JSON
   - **Body:**
     ```json
     {
       "last_text": "[pill: Última entrada de texto]",
       "first_name": "[pill: Nombre]",
       "conversation_summary": "[pill: conversation_summary]",
       "etapa_actual": "[pill: etapa_actual]",
       "profesion": "[pill: profesion]",
       "ingreso_mensual_cop_M": [pill: ingreso_mensual_cop_M],
       "dolor_opcion": "[pill: dolor_opcion]",
       "urgencia": "[pill: urgencia]"
     }
     ```
     (Reemplaza `[pill: X]` por las pills reales usando el botón `{}`.)
4. **Headers** (si ManyChat lo permite):
   - Content-Type: `application/json`

5. Mueve esta acción al **TOP del nodo Acciones** (antes de "Establecer fecha_ultimo_mensaje_setter").

## PASO 10 — Configurar Response Mapping

> Aquí está la magia del Camino Pro.

En la misma configuración del External Request, busca pestaña **"Response Mapping"** / **"Mapeo de respuesta"** / **"Map Response"**.

Configura cada campo con su JSON Path:

| JSON Path | Custom Field destino |
|---|---|
| `$.msg` | `claude_msg` |
| `$.etapa` | `etapa_actual` |
| `$.profesion` | `profesion` |
| `$.ingreso_mensual_cop_M` | `ingreso_mensual_cop_M` |
| `$.dolor_opcion` | `dolor_opcion` |
| `$.urgencia` | `urgencia` |
| `$.califica` | `califica` |
| `$.summary` | `conversation_summary` |
| `$.handoff_humano` | `handoff_humano` |
| `$.handoff_razon` | `handoff_razon` |

**Guarda.**

## PASO 11 — Actualizar Conditions del flow

Ahora las Conditions YA NO buscan frases en `claude_response_json` — usan el campo `etapa_actual` directamente.

Reemplaza las 4 condiciones del nodo "Condición" por:

| # | Condición | Si SÍ |
|---|---|---|
| 1 | `etapa_actual` = `M5` | Enviar `{{claude_msg}}` + tag M5_LINK_ENVIADO |
| 2 | `etapa_actual` = `Descalificado` | Enviar `{{claude_msg}}` + tag DESCALIFICADO_INGRESO + remover CONVERSACION_ACTIVA |
| 3 | `handoff_humano` = `true` AND `handoff_razon` = `agendamiento_manual_pendiente` | Enviar `{{claude_msg}}` + tag HANDOFF_ANDRES + tag HANDOFF_AGENDA_MANUAL + remover CONVERSACION_ACTIVA |
| 4 | `handoff_humano` = `true` | Enviar `{{claude_msg}}` + tag HANDOFF_ANDRES + remover CONVERSACION_ACTIVA |
| — | No coincide (caso NORMAL: M1, M2, M3, M4, M5.B, AgendaManual_1, AgendaManual_2) | Solo enviar `{{claude_msg}}` |

> **CAMBIOS CLAVE:**
> - Las Send Messages ahora usan `{{claude_msg}}` (el mensaje al lead, limpio) en lugar de `{{claude_response_json}}`.
> - El enrutamiento se basa en `etapa_actual` y `handoff_humano`, no en detección por contenido.
> - Mucho más limpio, robusto y rápido.

## PASO 12 — Test end-to-end

1. **Limpia el contacto Javier** en ManyChat:
   - `etapa_actual` → vacío
   - `claude_msg`, `profesion`, `ingreso_mensual_cop_M`, `dolor_opcion`, `urgencia`, `conversation_summary` → vacíos
   - `califica`, `handoff_humano` → false
   - Quitar tag `CONVERSACION_ACTIVA`

2. Desde Javier escribe "Control".
3. **Verifica:**
   - Bot responde M1 ✅
   - `etapa_actual` se actualizó a "M1" ✅
   - `conversation_summary` se actualizó ✅

4. Escribe "Soy ingeniero y gano 8 millones".
5. **Verifica:**
   - Bot responde M2 (las 4 opciones) ✅ ← TEST CRÍTICO
   - `etapa_actual` se actualizó a "M2" ✅
   - `profesion` = "ingeniero", `ingreso_mensual_cop_M` = 8 ✅

6. Continúa hasta M5.

## ¿Y si algo sale mal?

**Worker no responde:** revisar Logs en Cloudflare (Real-time logs).
**JSON malformado:** el worker tiene fallback que envía mensaje cortés + handoff.
**Response Mapping no mapea:** verificar que los nombres de custom fields coinciden EXACTAMENTE con los del JSON path.
**ManyChat no encuentra External Request:** buscar en categorías "Dev Tools" o "Automatización Avanzada". Si tu plan no incluye External Request, hay que upgradear.

---

## Ventajas del Camino Pro vs nativo

| Aspecto | Nativo | Camino Pro |
|---|---|---|
| Bucle M1 | ❌ Frecuente (Claude se pierde) | ✅ Imposible (etapa es campo) |
| Detección por contenido | ❌ Frágil | ✅ Determinístico |
| Tokens de respuesta | 2500 (limitado) | Controlado en worker |
| Modelo Claude | Fijo por ManyChat | ✅ Elegible en worker |
| Manejo de errores | Silencioso | ✅ Fallback explícito |
| Cambios de prompt | Editar en ManyChat | ✅ Editar en código, deploy |
| Logging | No | ✅ Logs en Cloudflare |
| Tool use (Fase 2) | No | ✅ Listo para agregar |
| Memoria persistente (Fase 3) | No | ✅ Listo para Supabase |
