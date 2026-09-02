# M7 · Confirmación de Asistencia (solo o acompañado) ★ NUEVO V4.0

> **V4.2 — Mensaje 7.** Se ejecuta después de M6 (Cierre + link Calendly ya enviado). El link YA se envió en M6; aquí solo confirmamos si el lead asistirá solo o acompañado antes de que separe su espacio.

**Etapa:** Lead recibió el link de Calendly en M6.
**Objetivo:** Saber si el lead asistirá solo o acompañado una vez enviado el link. Involucrar a la pareja/decisor aumenta la tasa de cierre.

---

## Script base

```
Excelente [Nombre], antes de que separes tu espacio te hago una última pregunta 😊
¿A esta sesión de diagnóstico asistirás solo tú o consideras importante que participe alguien más?

Te lo pregunto porque hay personas que prefieren tener presente a alguien con quien suelen hablar sus temas financieros.
```

---

## Bifurcación post-M7

| Respuesta del lead | Acción |
|---|---|
| **A) "Sí, voy con alguien"** | *"Perfecto [Nombre], entonces cuando vayas a agendar asegúrate de que esa persona también pueda estar ese día ¿Lo pueden cuadrar?"* → esperar a que agende → **preguntas pre-llamada** |
| **B) "Solo/a"** | Perfecto, esperar a que agende → cuando confirme el agendamiento → **preguntas pre-llamada** |
| **C) No responde** | Activar SOP de Recuperación (`bumps-recuperacion.md`) |

---

## Metadata esperada después de M7

```json
"metadata": {
  "etapa_actual": "M7",
  "asiste_acompanado": "si|no|desconocido",
  "siguiente_accion_esperada": "esperar_respuesta_lead"
}
```
