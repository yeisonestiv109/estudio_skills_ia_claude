# ManyChat — Implementación del Setter IA

Esta carpeta contiene **todos los artefactos necesarios para portar el Setter IA del proyecto Claude Code a ManyChat**, donde correrá 24/7 sin intervención manual.

## Archivos

| Archivo | Qué tiene | Cuándo usarlo |
|---|---|---|
| `system-prompt-condensado.md` | El system prompt completo que va en "Mensaje del sistema" de la acción Claude Request. | Configurando la acción "Acciones de Claude: Request" |
| `custom-fields.md` | Lista de 20+ custom fields y tags a crear. | Antes de armar cualquier flujo, en Settings → Custom Fields |
| `flujo-completo.md` | Mapa visual del flujo principal + sub-flujos (bumps, handoff, M5.5.a, sync). | Diseñando los flujos en el Flow Builder |
| `parser-json.md` | Cómo parsear el JSON de respuesta de Claude (opción nativa vs webhook). | Después de cada acción Claude Request |

## Orden de implementación (Fase 1 — MVP)

### Paso 1 — Crear custom fields (15 min)
Settings → Custom Fields → crea los campos listados en `custom-fields.md`. **Mínimo necesario para MVP:**
- `etapa_actual` (Text, default `M1`)
- `profesion` (Text)
- `ingreso_mensual_cop_M` (Number)
- `dolor_opcion` (Text)
- `urgencia` (Text)
- `califica` (Boolean)
- `handoff_humano` (Boolean)
- `claude_response_json` (Text)
- `fecha_ultimo_mensaje_setter` (DateTime)
- 3 campos auxiliares para `mensaje_lead_0/1/2`

### Paso 2 — Crear tags (5 min)
Settings → Tags → crea: `CALIFICA`, `M4_PITCH_ENVIADO`, `M5_LINK_ENVIADO`, `AGENDADO`, `HANDOFF_ANDRES`, `NURTURE_LARGO_PLAZO`, `DESCALIFICADO_INGRESO`, `DESCALIFICADO_TIMING`.

### Paso 3 — Configurar acción Claude (10 min)
Crea un flujo de prueba con un solo nodo "Acciones de Claude: Request":
- **Modelo:** Claude Sonnet 4.6
- **Mensaje del sistema:** Pega TODO el contenido del bloque en `system-prompt-condensado.md`
- **Último mensaje del usuario:** `{{Last User Message}}`
- **Guardar resultado en:** `claude_response_json`
- **Tokens máximos:** `2048`
- **Temperatura:** `0`

### Paso 4 — Construir el parser (15 min)
Después de la acción Claude, usa **Set Custom Field** con JSON path (ver `parser-json.md`):
- `mensaje_lead_0` ← `$.mensaje_para_lead[0]`
- `mensaje_lead_1` ← `$.mensaje_para_lead[1]`
- `mensaje_lead_2` ← `$.mensaje_para_lead[2]`
- `etapa_actual` ← `$.etapa_nueva`
- (resto de campos según mapping)

### Paso 5 — Enviar mensajes al lead (5 min)
Después del parser:
- Send Message `{{mensaje_lead_0}}` (si no está vacío)
- Delay 2 segundos
- Send Message `{{mensaje_lead_1}}` (si no está vacío)
- Delay 2 segundos
- Send Message `{{mensaje_lead_2}}` (si no está vacío)
- Set Custom Field `fecha_ultimo_mensaje_setter` ← `{{system.timestamp}}`

### Paso 6 — Trigger inicial (10 min)
Settings → Growth Tools → Instagram → Configurar:
- **Trigger:** comentario "CONTROL" en cualquier reel de la cuenta
- **Action:** Iniciar flujo "Setter IA Principal"

### Paso 7 — Test con un lead real (importante)
Comenta "CONTROL" en uno de tus propios reels desde una cuenta de prueba. Verifica:
- ✅ M0 saludo automático llega.
- ✅ Después de escribir CONTROL, Claude responde con M1.
- ✅ Custom fields se actualizan.
- ✅ Si dices "Soy médico, gano 8 millones", Claude pasa a M2.

### Paso 8 — Agregar bumps (Fase 2 después del MVP)
Usar "Smart Delay" condicional según `etapa_actual` y `fecha_ultimo_mensaje_setter`. Ver `flujo-completo.md` sub-flujo BUMPS.

### Paso 9 — Notificación handoff (Fase 2)
Cuando `handoff_humano == true`:
- Add tag `HANDOFF_ANDRES`
- Send email notification a javier.suarez@thebitbang.company
- Pausar flow para ese lead

### Paso 10 — Google Sheets sync (Fase 3)
External Request a Google Sheets API cuando cambia `etapa_actual`. Reemplaza el `sop-04-registro-google-sheets.md` manual.

---

## Diferencias clave entre Claude Code y ManyChat

| Aspecto | Claude Code (proyecto actual) | ManyChat |
|---|---|---|
| Quién opera | Yo (Claude) manualmente cada turno | Bot 24/7 |
| Memoria del lead | El historial completo del chat de IG | Custom fields persistentes |
| Costo | Mi tiempo de operación | ~$0.05-0.15 USD/lead |
| Velocidad | 30 seg/respuesta | 2-5 seg/respuesta |
| Bumps | Manuales en rondas | Automáticos con Smart Delay |
| Handoff | Yo te aviso en este chat | Email + tag automático |
| Errores | SOP-06 para clicks | Imposibles (ManyChat siempre escribe al chat correcto) |
| Escala | Limitada por mi disponibilidad | Ilimitada |

---

## Mantenimiento del system prompt

Cuando se actualice el SOP del Setter IA:
1. Editar primero los archivos en `/scripts/`, `/sops/`, `/knowledge-base/`.
2. Actualizar `system-prompt-condensado.md` con los cambios relevantes.
3. Copiar el bloque actualizado en la acción "Claude Request" de ManyChat.
4. Probar con un lead de prueba antes de dejar live.

---

## Próximos pasos sugeridos

1. ✅ Crear todos los artefactos (este archivo y los 4 hermanos) — **HECHO**.
2. ⏳ Implementar en ManyChat la Fase 1 (Pasos 1-7) — pendiente.
3. ⏳ Test con lead real.
4. ⏳ Activar Fase 2 (bumps + handoff).
5. ⏳ Fase 3 (Google Sheets sync + dashboards).

Si todo funciona en Fase 1, tienes el Setter IA corriendo solo. Tú y Andrés se enfocan SOLO en cerrar las llamadas agendadas.
