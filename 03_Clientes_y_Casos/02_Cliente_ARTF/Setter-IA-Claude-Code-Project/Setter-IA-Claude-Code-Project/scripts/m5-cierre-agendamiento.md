# M6 · Cierre del Agendamiento

> **⚠️ V4.2 — RENUMERADO:** este script (Cierre + link) ahora es el **Mensaje 6**. Va **directo después de M5 (Pitch aceptado)** y ANTES de **M7 Asistencia** (`m7-asistencia.md`). El "Sí, agendemos" ocurre en **M5 Pitch**, aquí M6 envía el link, y luego M7 pregunta la asistencia.

**Etapa:** Lead aceptó agendar en M5 (Pitch, "sí, agendemos").
**Objetivo:** Entregar el link de Calendly. Tras enviarlo → **M7 Asistencia**. Cuando el lead confirme que agendó → entregar las preguntas pre-llamada.

---

## ⚠️ REGLAS CRÍTICAS (no negociables)

1. **Chunking obligatorio en 2 mensajes.** Texto + link aislado al final.
2. **El link de Calendly es SIEMPRE el último elemento del array.**
3. **NUNCA envíes texto después del link en el mismo turno.** (Rompe el link en Instagram.)
4. **Tutéo colombiano + primera persona siempre.**

Ver `knowledge-base/04-voz-y-tono.md` sección "LINK DE CALENDLY SIEMPRE AISLADO".

---

## Mensaje 6.A — Saludo + link

**Mensaje 1 — saludo + instrucción + CTA de confirmación:**
```
¡Perfecto! 🙌
Acá te dejo el link para que elijas el día y hora que mejor te quede:
```

**Mensaje 2 — SOLO el link:**
```
https://calendar.app.google/iMW5LBbkcAvorypF9
```

**Mensaje 3 — cierre con CTA de confirmación (DESPUÉS del link, NO en el mismo turno):**
> ⚠️ Este mensaje va en un turno separado para no contaminar el link.

```
Confirmame cuando te hayas agendado, así te envío un par de puntos clave para que lleves a nuestra llamada.
```

### Forma alternativa en una sola tanda (cuando el sistema externo soporta chunks múltiples):

El array puede ir así, siempre con el link aislado:

```json
"mensaje_para_lead": [
  "¡Perfecto! 🙌\nAcá te dejo el link para que elijas el día y hora que mejor te quede:",
  "https://calendar.app.google/iMW5LBbkcAvorypF9",
  "Confirmame cuando te hayas agendado, así te envío un par de puntos clave para que lleves a nuestra llamada."
]
```

⚠️ **Si el cliente IG ha mostrado en producción que romper el link es problema cuando viene texto después en el MISMO turno, prioriza dividir en 2 turnos:**
- Turno 1: array `[saludo, link]`
- Turno 2: `"Confirmame cuando te hayas agendado..."`

---

## Mensaje 7.B — Confirmación + preguntas pre-llamada

> **Nota de orden (V4.2):** aunque este bloque vive en el script de Cierre, conceptualmente es la etapa **M7.B** y ocurre al FINAL, después de que el lead pasó por **M7 Asistencia** y confirmó su agendamiento. Se dispara con la confirmación de agenda, no inmediatamente después de enviar el link.

**Trigger:** El lead respondió confirmando que agendó ("ya agendé", "listo", "sí", "agendado", etc.).

```
Genial, para nuestra sesión ten listo:

1. ¿Cuál es tu estimado total de créditos actualmente?
2. ¿Hay algo específico que quisieras que yo entienda sobre tus objetivos o expectativas de esta mentoría?

Nos vemos en la llamada.
```

Este mensaje va completo en un solo turno (no requiere chunking — es corto y no contiene links).

---

## Output JSON correcto

### Para M6.A (saludo + link)
```json
{
  "mensaje_para_lead": [
    "¡Perfecto! 🙌\nAcá te dejo el link para que elijas el día y hora que mejor te quede:",
    "https://calendar.app.google/iMW5LBbkcAvorypF9"
  ],
  "metadata": {
    "etapa_actual": "M6",
    "siguiente_accion_esperada": "esperar_calendly_agendado"
  }
}
```

Luego, en el siguiente turno (o si el cliente soporta chunking extendido en el mismo array):
```json
{
  "mensaje_para_lead": "Confirmame cuando te hayas agendado, así te envío un par de puntos clave para que lleves a nuestra llamada.",
  "metadata": {
    "etapa_actual": "M6_followup",
    "siguiente_accion_esperada": "esperar_confirmacion_lead"
  }
}
```

### Para M7.B (preguntas pre-llamada, post-confirmación)
```json
{
  "mensaje_para_lead": "Genial, para nuestra sesión ten listo:\n\n1. ¿Cuál es tu estimado total de créditos actualmente?\n2. ¿Hay algo específico que quisieras que yo entienda sobre tus objetivos o expectativas de esta mentoría?\n\nNos vemos en la llamada.",
  "metadata": {
    "etapa_actual": "M7_preguntas",
    "siguiente_accion_esperada": "cerrar_lead"
  }
}
```

---

## ❌ Output INCORRECTO (rompe el link)

```json
"mensaje_para_lead": [
  "¡Perfecto!",
  "https://calendar.app.google/iMW5LBbkcAvorypF9",
  "Cuando termines, avísame."  ← ESTO PEGA AL LINK Y LO ROMPE
]
```

---

## Si el link salió roto en un turno previo

NO te disculpes. Re-envía el link aislado:

```json
"mensaje_para_lead": [
  "Te lo dejo acá para que sea más fácil:",
  "https://calendar.app.google/iMW5LBbkcAvorypF9"
]
```

O solo el link si ya hay confianza:
```json
"mensaje_para_lead": "https://calendar.app.google/iMW5LBbkcAvorypF9"
```

---

## ⚠️ Caso especial: lead dice que NO encuentra agenda disponible

Si el lead responde algo como:
- "No me aparece nada disponible"
- "No hay horarios libres"
- "Calendly está bloqueado"
- "No me deja agendar"

**NO confirmes que sí hay espacio.** Sigue el protocolo de **handoff de agendamiento manual** definido en:
- `templates/handoff-message-template.md` (sección "Agendamiento manual: lead no encuentra espacio")
- `sops/sop-05-aprendizajes-produccion.md` (Aprendizaje #5)

Resumen del protocolo:
1. Avísale que vamos a revisar qué espacios se liberan y le confirmaremos.
2. Pide fecha y bloques de horarios que le queden bien.
3. Después de tener fechas/horarios, pide email y celular.
4. Marca `handoff_humano: true` con `razon_handoff: "agendamiento_manual_pendiente"`.

Script base:
```
Entendido, [Nombre]. Vamos a revisar qué espacios se liberan y te confirmamos para agendarnos.

Contame, ¿qué fecha y bloques de horarios te quedan bien?
```

Y cuando el lead responda con fechas/bloques:
```
Perfecto. Para enviarte la invitación cuando el espacio esté listo, ¿me confirmas tu correo y un número de WhatsApp?
```

---

## Siguiente paso

Después de enviar M6.A (link), sigue **M7 Asistencia** (`m7-asistencia.md`) y luego el sistema externo espera que el lead agende:
- Si pasaron 20-30 min con "Visto" pero sin respuesta → **M5.5.a** (`scripts/m5-5-confirmacion-post-calendly.md`).
- Si pasaron 30 min sin "Visto" o sin respuesta → **Bump 1 de agendamiento** (`scripts/bumps-recuperacion.md` rama agendamiento).
- Si el lead confirma "ya agendé" → enviar **M7.B** (preguntas pre-llamada).

---

## Variable a actualizar antes de producción

Link oficial Calendly actual: **`https://calendar.app.google/iMW5LBbkcAvorypF9`**

Cuando Andrés cambie su Calendly, actualizar en TODOS los archivos del proyecto con:
```bash
find . -type f -name "*.md" -exec sed -i '' 's|iMW5LBbkcAvorypF9|NUEVO_LINK_AQUI|g' {} +
```
