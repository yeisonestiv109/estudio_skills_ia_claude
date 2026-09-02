# Parser del JSON de Claude en ManyChat

Después de la acción "Claude Request", Claude devuelve un JSON. ManyChat necesita parsearlo para extraer los mensajes y actualizar custom fields.

## Opción A — JSON Path nativo de ManyChat (más simple)

En ManyChat, después de la acción Claude:

1. **Action → Set Custom Field**
2. Usa **JSON path** sobre `{{claude_response_json}}`:

| Campo a actualizar | JSON Path |
|---|---|
| `etapa_actual` | `$.etapa_nueva` |
| `califica` | `$.califica` |
| `profesion` | `$.metadata.profesion` |
| `ingreso_mensual_cop_M` | `$.metadata.ingreso_mensual_cop_M` |
| `dolor_opcion` | `$.metadata.dolor_opcion` |
| `urgencia` | `$.metadata.urgencia` |
| `handoff_humano` | `$.metadata.handoff_humano` |
| `caso_exito_usado` | `$.metadata.caso_exito_usado` |
| `razon_handoff` | `$.metadata.razon_handoff` |
| `mensaje_lead_0` | `$.mensaje_para_lead[0]` |
| `mensaje_lead_1` | `$.mensaje_para_lead[1]` |
| `mensaje_lead_2` | `$.mensaje_para_lead[2]` |

3. **Send Message** con `{{mensaje_lead_0}}`, luego delay 2s, luego `{{mensaje_lead_1}}`, etc.

## Opción B — External Request webhook (más robusto)

Si tu plan de ManyChat lo permite, mejor crea un endpoint propio (Google Apps Script, Cloudflare Worker, etc.) que:

1. Reciba el `claude_response_json` crudo
2. Lo parsee
3. Devuelva los campos individuales
4. Maneje errores (JSON mal formado, etc.)

Ejemplo Cloudflare Worker (JS):

```javascript
export default {
  async fetch(request) {
    const { claude_response_json } = await request.json();
    
    let parsed;
    try {
      // Claude a veces envuelve en markdown ```json ... ``` — limpiar primero
      const cleaned = claude_response_json
        .replace(/^```json\n?/, '')
        .replace(/\n?```$/, '')
        .trim();
      parsed = JSON.parse(cleaned);
    } catch (e) {
      return new Response(JSON.stringify({
        error: "JSON malformado",
        fallback: {
          mensaje_lead_0: "Disculpa, tuve un problema técnico. Andrés te responde en un momento.",
          handoff_humano: true,
          razon_handoff: "JSON parse error en Claude response"
        }
      }), { headers: { "Content-Type": "application/json" }});
    }
    
    return new Response(JSON.stringify({
      mensaje_lead_0: parsed.mensaje_para_lead[0] || "",
      mensaje_lead_1: parsed.mensaje_para_lead[1] || "",
      mensaje_lead_2: parsed.mensaje_para_lead[2] || "",
      etapa_nueva: parsed.etapa_nueva,
      califica: parsed.califica,
      profesion: parsed.metadata?.profesion || "",
      ingreso_mensual_cop_M: parsed.metadata?.ingreso_mensual_cop_M || 0,
      dolor_opcion: parsed.metadata?.dolor_opcion || "",
      urgencia: parsed.metadata?.urgencia || "desconocida",
      handoff_humano: parsed.metadata?.handoff_humano || false,
      caso_exito_usado: parsed.metadata?.caso_exito_usado || "ninguno",
      razon_handoff: parsed.metadata?.razon_handoff || ""
    }), { headers: { "Content-Type": "application/json" }});
  }
};
```

## Fallback si Claude devuelve algo inesperado

Si el JSON viene mal formado o vacío:
1. **No envíes nada al lead** (mejor silencio que mensaje raro).
2. **Add tag HANDOFF_ANDRES** + notificación.
3. **Log el `claude_response_json` crudo** para debug en Google Sheets.

## Recomendación de configuración de Claude para evitar errores de JSON

En el system prompt agregar:
> "Si por cualquier razón no puedes generar el JSON estricto, devuelve únicamente: `{\"mensaje_para_lead\":[\"\"],\"etapa_nueva\":\"Handoff\",\"metadata\":{\"handoff_humano\":true,\"razon_handoff\":\"Setter no pudo procesar\"}}`. NO devuelvas explicación, NO uses markdown, SOLO JSON puro."

Y configurar en la acción de Claude:
- **Response format**: si ManyChat soporta "JSON mode" en la API de Anthropic, activarlo. Si no, parsear con limpieza de markdown como muestra el worker.
