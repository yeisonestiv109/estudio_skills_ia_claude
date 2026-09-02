# SOP de Recuperación — Bumps cuando el lead deja de responder

> **V4.2 — nota de numeración:** el flujo ahora tiene 7 mensajes. "Bumps Generales" cubre silencios en las etapas de calificación (M1 a M4). "Bumps de Agendamiento" cubre silencios después del **Pitch (M5)** y del **envío del link (M6)**. Donde este archivo diga "M5/M6" en el contexto de agendamiento, léelo como **M5 (pitch) / M6 (link)**. (La Asistencia solo/acompañado es M7, DESPUÉS del link.)

El sistema externo (no tú) controla el timing. Tu trabajo es generar el mensaje correcto cuando el sistema te indique qué bump enviar.

> 🚫 **PROHIBIDO — wording legacy a NO usar nunca:**
> No envíes mensajes tipo *"¿Te llegó mi último mensaje? A veces Instagram los oculta"* ni variantes. Ese wording fue retirado el 2026-05-23. Los únicos bumps válidos son los de este archivo, palabra por palabra.

**⚠️ Importante:** existen **dos ramas de bumps** según en qué etapa quedó silencioso el lead:

1. **Bumps Generales** — para silencios en las etapas de calificación (M1 a M4, antes de aceptar agendar).
2. **Bumps de Agendamiento** — para silencios después del Pitch (M5) o del envío del link (M6): ya aceptó agendar pero no agendó / no respondió al link.

---

# RAMA 1 — BUMPS GENERALES (M1 / M2 / M3 silenciosos)

Aplica cuando el lead respondió en alguna etapa de la calificación y luego se quedó callado **antes** de aceptar agendar.

## Bump 1 — 30 minutos después

```
Hola [Nombre], quedé pendiente de tu respuesta para entender un poco mejor tu contexto y ver si realmente te puedo ayudar.
```

**Tono:** empático, sin presión, deja claro que esperas su respuesta para personalizar.

## Bump 2 — 24 horas después

```
[Nombre], no quiero ser un mensaje más que te estorba en el chat. 😊

¿Seguimos hablando o prefieres que no te escriba más?
```

**Tono:** humano, opción de salida limpia. Convierte ghosters en respuestas reales (sí/no).

## Bump 3 — 72 horas después (ÚLTIMO intento)

```
[Nombre], me alegra que hayas llegado hasta aquí, aunque no hayamos podido hablar. 😊 Te dejo este video que a mucha gente le ha servido un montón: https://www.instagram.com/reel/DX73ACPNvRV/?igsh=MXQ3anYycWUzNXBoMA==

Si algo resuena contigo, ya sabes dónde encontrarme. ¡Éxitos!
```

**Link fijo:** `https://www.instagram.com/reel/DX73ACPNvRV/?igsh=MXQ3anYycWUzNXBoMA==` (reel de cierre estándar, no se cambia por dolor).

**Después del Bump 3:** marca el lead como `estado: nurture_largo_plazo` y deja de enviar bumps.

---

# RAMA 2 — BUMPS DE AGENDAMIENTO (M5/M6 silenciosos)

Aplica cuando el lead aceptó agendar en M5 ("¿Agendamos?" → "Sí") o recibió el link de Calendly en M6 pero **NO se agendó / no respondió**.

## Bump 1 — 30 minutos después

```
[Nombre], ¿quedó alguna duda antes de agendar?

¿Se fue la señal? 😄
```

**Tono:** ligero, humor suave, invita a responder sin presión.

**⚠️ Diferenciar de M5.5.a:** Si el lead **vio el link** (Instagram muestra "Visto") y solo no respondió → usar `M5.5.a` ("¿Pudiste agendar sin problema?") en lugar de este Bump 1. Este Bump 1 es para cuando el lead NO vio el link aún o cuando ya fallaron M5.5.a y M5.5.b.

## Bump 2 — 24 horas después

**Mensaje 1 — recordatorio + dolor + escasez:**
```
¡Hola [Nombre]! ¿Algún inconveniente?

Ayer hablamos de esa plata que se va como "sal y agua", ¿verdad?

Mira, me quedan pocos cupos esta semana para que revisemos tu caso y veas cómo liberamos ese 15% de tu ingreso.

Te dejo el link de nuevo:
```

**Mensaje 2 — SOLO el link aislado:**
```
https://calendar.app.google/iMW5LBbkcAvorypF9
```

**Mensaje 3 — salida limpia (opcional, turno separado):**
```
Si ya no te interesa, sin problema, me avisas. ¡Un abrazo! 😊
```

**Tono:** retoma el dolor original, escasez real (cupos limitados — máximo 25 clientes simultáneos), opción de salida.

⚠️ **Regla del link aislado aplica:** texto antes, link aislado al final, sin texto después del link en el mismo turno. Si quieres incluir el "Si ya no te interesa..." final, va en un turno separado después.

## Bump 3 — 72 horas después (ÚLTIMO intento)

```
[Nombre], último mensaje, lo prometo. 😄

Te dejo este video antes de irme, creo que te va a servir:
https://www.instagram.com/reel/DX73ACPNvRV/?igsh=MXQ3anYycWUzNXBoMA==

Si en algún momento quieres retomar, aquí estoy. ¡Éxitos! 💪
```

**Después del Bump 3:** marca el lead como `estado: nurture_largo_plazo` y deja de enviar bumps.

---

## Excepciones — NO mandes bumps si:

- El lead pidió "déjame pensarlo" y dijo que escribiría él/ella primero.
- El lead se descalificó solo (ej: "no tengo plata para pagar nada", "es para algún día").
- El lead pasó a `handoff_humano: true` en algún turno anterior.
- Es fin de semana después de las 8pm (espera al lunes).
- El lead está en handoff de agendamiento manual esperando que el humano confirme el slot — ahí el bump le corresponde al humano, no al setter.

---

## Tabla de decisión rápida

| Situación | Acción |
|---|---|
| Lead respondió M1 → silencio 30 min | Bump 1 General |
| Lead respondió M2 → silencio 30 min | Bump 1 General |
| Lead respondió M3 → silencio 30 min | Bump 1 General |
| Lead aceptó "Sí, agendemos" en M5 → silencio 30 min sin link enviado | (Caso raro — primero enviar M6.A) |
| Lead vio el link M6 → silencio 20-30 min | **M5.5.a** (no Bump) |
| Lead no vio el link M6 → silencio 30 min | Bump 1 de Agendamiento |
| Lead silencio 24h en cualquier etapa | Bump 2 (General o Agendamiento según etapa) |
| Lead silencio 72h en cualquier etapa | Bump 3 (General o Agendamiento según etapa) |
| Bump 3 ya enviado → silencio continuo | `estado: nurture_largo_plazo`, no más bumps |

---

## Metadata esperada en bumps

```json
"metadata": {
  "etapa_actual": "bump1_general" | "bump2_general" | "bump3_general" | "bump1_agendamiento" | "bump2_agendamiento" | "bump3_agendamiento",
  "siguiente_accion_esperada": "esperar_respuesta_lead",
  "resumen_lead": {
    "notas": "Bump X enviado. Última etapa activa antes del silencio: [M2/M3/M4/M5]"
  }
}
```

---

## Historial de cambios

- **2026-05-22:** Reescritura completa siguiendo nuevas instrucciones de Javier. Separación en 2 ramas (Generales vs Agendamiento), wordings actualizados, mapeo de reels movido a `templates/reels-por-dolor.md`.
- **2026-05-23:** Agregado warning explícito contra wording legacy ("¿Te llegó mi último mensaje? A veces Instagram los oculta") que el Setter IA improvisó por error en R10/R11. Bump 3 General actualizado con link fijo del reel de cierre (https://www.instagram.com/reel/DX73ACPNvRV/...) en lugar de mapeo variable por dolor. Wording final cambiado a "¡Éxitos!" (sin "Muchos" ni 👋).
