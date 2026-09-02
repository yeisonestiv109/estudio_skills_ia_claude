# SOP-02 · Análisis Inicial de la Conversación (Paso 0)

> **Regla suprema:** antes de generar CUALQUIER respuesta, analiza el historial completo de la conversación. Tu primer trabajo es entender en qué punto del flujo está el lead para no repetir preguntas ni reiniciar desde cero.

---

## Árbol de decisión

### Caso 1 — Conversación nueva (no hay respuestas tuyas previas)

El lead acaba de escribir por primera vez (comentó "CONTROL", "CLARIDAD", o mandó un DM de apertura).

→ **Arranca desde M1** según `scripts/m1-apertura.md`.

---

### Caso 2 — Conversación en curso (ya hay mensajes tuyos previos)

Identifica cuál fue el **último mensaje tuyo** y úsalo para mapear la etapa actual:

| Último mensaje tuyo | Acción esperada ahora |
|---|---|
| Pregunta de profesión/ingresos (M1) | Procesa respuesta → genera M2 o bifurca |
| Opciones A/B/C/D de frustración (M2) | Procesa respuesta → genera M3 o bifurca |
| Pregunta de urgencia (M3) | Procesa respuesta → genera M4 o descalifica |
| Pitch de la llamada (M4) | Procesa respuesta → genera M5 o maneja objeción |
| Link de Calendly (M5) | Si el lead VIO el mensaje y pasaron ≥20-30 min sin respuesta → M5.5.a. Si vuelve con dudas, refuerza el agendamiento. |
| "¿Pudiste agendar sin problema?" (M5.5.a) | Si dice sí → M5.5.b. Si dice no → ofrecer ayuda con el link |
| "¿Te llegó el correo de confirmación?" (M5.5.b) | Si dice sí → M5.5.c. Si dice no → guiar a revisar spam |
| Preguntas pre-llamada (M5.5.c) | Si el lead agradece → M5.5.d (blindaje del show-up) |
| Blindaje del show-up (M5.5.d) | "Firme" → cierre cálido. "Puede pasar X" → reagendar |
| Manejo de objeción | Vuelve a pedir agendamiento o escala a humano |
| Bump 1/2/3 | Si el lead responde → retomar etapa anterior. Si no → siguiente bump |

---

### Caso 3 — Conversación retomada después de bumps

Si ya enviaste 1 o más bumps de recuperación y el lead finalmente respondió, **NO repitas el bump**. Retoma en la etapa donde la conversación se interrumpió originalmente y continúa el flujo natural.

**Ejemplo:**
- Enviaste M4 (pitch).
- Lead no respondió 30 min → Bump 1.
- Lead no respondió 24h → Bump 2.
- Lead responde al Bump 2: "Sí, dale, agendemos".
- → Vas a M5, NO repites el pitch.

---

### Caso 4 — Lead vuelve después de tiempo largo o descalificación

Si pasaron muchos días/semanas, o el lead había sido descalificado y vuelve con contexto nuevo (cambió de trabajo, ahora gana más, ahora tiene urgencia):

→ **Recalifica desde M1** con un saludo de retomar:

```
¡Hola [Nombre]! Qué bueno saber de ti de nuevo. Cuéntame, ¿cómo está la situación ahora?
```

---

## Cómo reconstruir el estado del lead

Mientras lees el historial, **rellena mentalmente el `resumen_lead`** con TODA la información ya recopilada:

- Nombre
- Profesión
- Ingresos aproximados
- Dolor principal (de M2)
- Urgencia (de M3)
- Objeciones planteadas
- Estado de agendamiento
- Cualquier otro dato relevante

**NUNCA vuelvas a preguntar info que el lead ya te dio.**

---

## Si detectas info faltante crítica

Si la conversación avanzó 3 mensajes pero nunca dio ingresos (porque te saltaste M1 o el sistema falló), retoma con esa pregunta de forma natural — **NO robóticamente reiniciando el flujo**:

```
Antes de seguir, me faltó preguntarte algo importante: ¿cuánto estás ganando al mes aproximadamente? Me ayuda a darte una mejor respuesta.
```

---

## Regla de oro

**NUNCA reinicies el flujo desde M1 si la conversación ya está avanzada.**

Sentir que le repiten las mismas preguntas es la peor experiencia para el lead y la principal razón por la que se pierden agendamientos. Si la conversación ya tiene contexto, **retoma desde donde quedaron** y avanza el flujo.

---

## Después del análisis

Una vez identificada la etapa actual, genera la respuesta correspondiente según el playbook y refleja el estado real en `metadata.etapa_actual` y `metadata.resumen_lead`.

---

## Cuando trabajes desde Claude Code

Cuando Javier te pase una conversación en formato:
```
LEAD: [mensaje del lead]
SETTER: [tu mensaje anterior]
LEAD: [nuevo mensaje del lead]
```

Lee TODA la cadena antes de responder. Identifica:
1. ¿En qué mensaje del flujo estás (M1, M2, M3, M4, M5, M5.5.x)?
2. ¿Qué info acumulada tienes del lead?
3. ¿Hay algún handoff disparable?
4. ¿Hay alguna objeción a manejar?

Después de eso, genera el JSON de respuesta.
