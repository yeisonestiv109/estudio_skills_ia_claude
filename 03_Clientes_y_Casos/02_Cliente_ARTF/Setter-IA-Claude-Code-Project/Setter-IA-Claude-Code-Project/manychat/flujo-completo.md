# Flujo Completo del Setter IA en ManyChat

Mapa visual de los flujos a construir y cómo se conectan.

```
┌─────────────────────────────────────────────────┐
│  TRIGGER: Comentario "CONTROL" en reel de IG    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  M0 — Saludo automático (texto fijo, no Claude) │
│  "¡Hola! [Nombre] 👋 Vi que te interesaste en   │
│  el caso de Camila y en tomar el control de tu  │
│  dinero. Escríbeme la palabra CONTROL para      │
│  empezar."                                       │
└──────────────────────┬──────────────────────────┘
                       │
                       │ Lead responde "CONTROL"
                       ▼
┌─────────────────────────────────────────────────┐
│  Set etapa_actual = M1                          │
│  Set fecha_ultimo_mensaje_setter = now()        │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  ★ NODO CLAUDE ★                                │
│  Action: Claude Request                          │
│  System prompt: ver system-prompt-condensado.md │
│  User message: {{Last User Message}}            │
│  Save to: claude_response_json                  │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  PARSER (External Request o JS de ManyChat)     │
│  Extrae del JSON:                               │
│  - mensaje_para_lead[] (array de strings)       │
│  - etapa_nueva                                  │
│  - califica                                     │
│  - metadata.*                                   │
│  Actualiza custom fields según mapping.         │
└──────────────────────┬──────────────────────────┘
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
   ┌──────────────────┐  ┌─────────────────────┐
   │ handoff_humano   │  │ Resto del flujo     │
   │ == true ?        │  │ normal              │
   └────────┬─────────┘  └─────────┬───────────┘
            │ SÍ                   │ NO
            ▼                      │
   ┌──────────────────┐            │
   │ Add tag HANDOFF  │            │
   │ Notify Andrés    │            │
   │ (email/WhatsApp) │            │
   │ Stop flow        │            │
   └──────────────────┘            │
                                   │
                                   ▼
                       ┌─────────────────────┐
                       │ Send mensaje_para_  │
                       │ lead[0] (con typing │
                       │ indicator)          │
                       │ Delay 2s            │
                       │ Send [1]            │
                       │ Delay 2s            │
                       │ Send [2] etc.       │
                       └──────────┬──────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │ Set fecha_ultimo_   │
                       │ mensaje_setter = now│
                       └──────────┬──────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │ Switch por          │
                       │ etapa_nueva:        │
                       └─────────┬───────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
    etapa: M2-M5, M7         etapa: M6                etapa: Descalificado
    Wait for lead reply  →    Add tag M6_LINK_ENVIADO  Add tag DESCALIFICADO
    Loop a nodo Claude        (link enviado)           Stop flow
    (M7 = pregunta            Luego M7 (asistencia)
     asistencia post-link)    Wait for lead reply
                              Si "agendada":
                                Add tag AGENDADO
                                Loop a Claude (M7.B)
                              Si silencio 30min:
                                Trigger Bump 1 Agend
```

---

## Sub-flujo: BUMPS automáticos

```
┌─────────────────────────────────────────────────┐
│  TRIGGER: 30min sin respuesta tras último       │
│  mensaje del setter (basado en                  │
│  fecha_ultimo_mensaje_setter)                   │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  ¿etapa_actual == M5_PITCH o M6?                │
└──────────────────────┬──────────────────────────┘
                       │
              ┌────────┴────────┐
              │                 │
              ▼ SÍ              ▼ NO
   ┌──────────────────────┐ ┌─────────────────────────┐
   │ Bump 1 AGENDAMIENTO   │ │ Bump 1 GENERAL          │
   │ "[Nombre], ¿quedó    │ │ "Hola [Nombre], quedé   │
   │ alguna duda antes de │ │ pendiente de tu         │
   │ agendar? ¿Se fue la  │ │ respuesta para entender │
   │ señal? 😄"           │ │ un poco mejor tu        │
   └──────────┬───────────┘ │ contexto y ver si       │
              │             │ realmente te puedo      │
              │             │ ayudar."                │
              │             └────────┬────────────────┘
              │                      │
              └──────────┬───────────┘
                         │
                         ▼
              Wait 24h sin respuesta
                         │
                         ▼
              ┌─────────────────────────────────┐
              │ Bump 2                          │
              │ (texto exacto SOP, ver          │
              │ scripts/bumps-recuperacion.md)  │
              └────────────┬────────────────────┘
                           │
                           ▼
                Wait 72h sin respuesta
                           │
                           ▼
              ┌─────────────────────────────────┐
              │ Bump 3 (ÚLTIMO)                 │
              │ + Add tag NURTURE_LARGO_PLAZO   │
              │ + Stop bump sequence            │
              └─────────────────────────────────┘
```

---

## Sub-flujo: HANDOFF

```
TRIGGER: handoff_humano == true
       │
       ▼
1. Add tag HANDOFF_ANDRES
2. Set razon_handoff = (de claude_response_json.metadata.razon_handoff)
3. Send notification:
   - Email a: javier.suarez@thebitbang.company
   - Subject: "🚨 Setter IA — Handoff: {{nombre_lead}} ({{razon_handoff}})"
   - Body: Snapshot completo del lead
4. Pausa el flow automático para este lead
5. Sigue notificando cada vez que el lead responda hasta que Javier desactive el tag
```

---

## Sub-flujo: M5.5.a (vio el link, no agendó)

```
TRIGGER: M6_LINK_ENVIADO y "Visto" (cuando Instagram marca leído)
       │
       ▼
Wait 20-30 min
       │
       ▼
Si NO respondió ni AGENDADO:
  Send: "[Nombre], ¿pudiste agendar sin problema? Si tuviste algún inconveniente, dime y vemos cómo resolverlo 🙌"
       │
       ▼
Wait 24h
       │
       ▼
Si silencio → Bump 2 Agendamiento (con reenvío del link)
```

---

## Sub-flujo: SYNC con Google Sheets

```
TRIGGER: Cualquier cambio en etapa_actual
       │
       ▼
Action: External Request → Google Sheets API
Append row con:
  - timestamp
  - nombre_lead
  - ig_username
  - profesion
  - ingreso_mensual_cop_M
  - dolor_opcion
  - urgencia
  - califica
  - etapa_actual
  - objeciones_planteadas
  - handoff_humano
  - caso_exito_usado
```

---

## Estimación de costos

Por lead que pasa por todo el funnel M1→M7 (V4.2):
- ~4 llamadas a Claude (M1, M2, M3, M4)
- ~2000 tokens system + 500 tokens output por llamada = ~2500 tokens/llamada
- 4 × 2500 = 10,000 tokens por lead completo
- Sonnet 4.6: ~$0.03 USD/MTok input + $0.15 USD/MTok output
- **Costo por lead que pasa todo el funnel: ~$0.05-0.10 USD**

Con bumps y objeciones puede subir a $0.15 USD/lead. **Muy bajo comparado con el ticket de $1500 USD.**
