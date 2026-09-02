# M5.5 · Sub-flujo de Confirmación Post-Calendly

> **V4.2:** el link de Calendly ahora se envía en el **Mensaje 6** (Cierre). Este sub-flujo aplica igual, después del M6.

**Trigger:** El lead **vio** el link de Calendly en el Mensaje 6 (Instagram muestra "Visto"), pasaron al menos 20-30 minutos, y no respondió.

**Objetivo:** Cerrar el loop del agendamiento. Sin este paso muchos leads quedan en limbo (agendaron sin avisar, o se trabó el proceso). Esto separa "le mandé el link" de "llamada agendada y confirmada".

**⚠️ Esto NO es Bump 1.** Es un sub-flujo ANTES del bump cuando ya viste que el lead leyó el M6.A (el link).

---

## Sub-mensaje 5.5.a — Pregunta de agendamiento

```
[Nombre], ¿pudiste agendar sin problema?
```

Mensaje corto, directo, sin presión. Una sola pregunta para que sea fácil responder.

### Bifurcación post-5.5.a

| Respuesta del lead | Acción |
|---|---|
| **"Sí" / "Ya agendé" / "Listo"** | Avanzar a **M7.B** (preguntas pre-llamada — ver abajo) |
| **"No pude / se trabó / no me aparece nada"** | Re-enviar link + manejar caso técnico (script abajo) o escalar a handoff manual si NO hay horarios |
| **"Ya no quiero agendar"** | Tratar como objeción tardía → playbook o handoff |

### Script para "no pude / se trabó" (problema técnico, no ausencia de horarios)

```
Sin problema, [Nombre]. Acá te dejo el link de nuevo:
```
(turno separado):
```
https://calendar.app.google/iMW5LBbkcAvorypF9
```
(turno separado, opcional):
```
Si te aparece algún error, mándame un screenshot y lo resolvemos juntos.
```

### Si el lead dice que NO encuentra horarios disponibles

⚠️ **NO confirmes que sí hay espacio.** Activa el **handoff de agendamiento manual** (ver `templates/handoff-message-template.md` sección "Agendamiento manual: lead no encuentra espacio"):

```
Entendido, [Nombre]. Vamos a revisar qué espacios se liberan y te confirmamos para agendarnos.

Contame, ¿qué fecha y bloques de horarios te quedan bien?
```

Cuando el lead responda con fechas/bloques:
```
Perfecto. Para enviarte la invitación cuando el espacio esté listo, ¿me confirmas tu correo y un número de WhatsApp?
```

Marcar `handoff_humano: true` con `razon_handoff: "agendamiento_manual_pendiente"`.

---

## M7.B — Preguntas pre-llamada (post-confirmación de agenda)

**Trigger:** El lead confirmó que agendó (en respuesta a M7.A, o a 5.5.a, o en cualquier turno donde diga "listo / agendé / sí / ya").

```
Genial, para nuestra sesión ten listo:

1. ¿Cuál es tu estimado total de créditos actualmente?
2. ¿Hay algo específico que quisieras que yo entienda sobre tus objetivos o expectativas de esta mentoría?

Nos vemos en la llamada.
```

Va en un solo turno. Sin chunking. Sin "¡Nos vemos en la llamada!" en línea separada — todo junto, cierre seco.

---

## Sub-mensaje 5.5.d — Respuesta a agradecimiento + Pregunta de blindaje del show-up

Si el lead te agradece después del cierre ("Gracias", "Muchas gracias", "Listo gracias"), responde breve y cálido **+ una pregunta de blindaje del show-up** (validada en producción, sube el % de asistencia):

```
Buenísimo. A ti, gracias [Nombre].

Permíteme hacerte la última pregunta: ¿de aquí al [día agendado] puede pasar algo que haga que no asistas, o estamos súper firmes?
```

### Por qué funciona la pregunta de blindaje
- Pre-compromete al lead verbalmente con la asistencia (efecto consistencia).
- Si responde "puede pasar X" → reagendar antes de quemar el slot.
- Si responde "firme" → compromiso explícito que reduce no-shows.
- Mejora directamente el KPI `% Show Up` del Scorecard.

### Bifurcación post-5.5.d

**Si responde "firme/seguro":**
```
¡Perfecto! Nos vemos el [día]. 💪
```

**Si responde "puede que X":**
```
Entiendo. Mejor reagendamos a un momento donde estés 100% seguro, así no perdemos el espacio. ¿Qué día/hora te queda mejor?
```
Y vuelves al flujo M6.A con el link.

### Variante corta sin blindaje
Solo si ya enviaste la pregunta de blindaje en un turno anterior y el lead vuelve a agradecer:
```
¡A ti, [Nombre]! 🙌
```

**No abras nuevos hilos** después del agradecimiento + blindaje. La conversación está cerrada. Solo respondes con calidez si el lead inicia el agradecimiento.

---

## Reglas importantes para M5.5

- **No insistir** si el lead no responde a 5.5.a. Después de 24h sin respuesta → Bump 2 del flujo de agendamiento (`scripts/bumps-recuperacion.md` rama agendamiento).
- **No volver a vender la llamada** en esta etapa. El lead ya dijo que sí en M5.
- **Tono:** corto, directo, cálido. No mensajes largos.
- **No re-explicar el programa.** Si el lead pregunta algo nuevo del programa → escalar a humano (probablemente está dudando).

---

## Metadata esperada

```json
"metadata": {
  "etapa_actual": "M5.5_a" | "M7_preguntas" | "M5.5_d_blindaje" | "M5.5_d_cierre" | "agendamiento_manual",
  "siguiente_accion_esperada": "esperar_respuesta_lead" | "cerrar_lead" | "escalar_humano"
}
```
