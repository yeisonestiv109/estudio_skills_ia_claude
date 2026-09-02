# Template · Formato JSON de Output (OBLIGATORIO)

> El Agente Setter IA SIEMPRE responde en este formato JSON. Nunca rompas la estructura.

---

## Estructura completa

```json
{
  "mensaje_para_lead": "string O array de 2-3 strings. Si la respuesta es corta (<80 palabras), usa string único. Si es larga, usa array donde cada elemento es un mensaje separado que se enviará en secuencia. Mantén saltos de línea con \\n.",
  "metadata": {
    "etapa_actual": "M1 | M2 | M3 | M4 | M5 | M5.5_a | M5.5_b | M5.5_c | M5.5_d_blindaje | M5.5_d_cierre | objecion | bump1 | bump2 | bump3 | descalificacion | handoff",
    "siguiente_accion_esperada": "esperar_respuesta_lead | esperar_calendly_agendado | escalar_humano | cerrar_lead",
    "calificacion_financiera": "calificado | borderline | descalificado | desconocido",
    "calificacion_dolor": "calificado | descalificado | desconocido",
    "calificacion_urgencia": "calificado | descalificado | desconocido",
    "handoff_humano": false,
    "razon_handoff": null,
    "resumen_lead": {
      "nombre": "string o null",
      "profesion": "string o null",
      "ingreso_aproximado_cop": "string o null",
      "dolor_principal": "string o null",
      "urgencia": "alta | media | baja | desconocida",
      "objeciones_planteadas": [],
      "notas": "Resumen corto de lo más relevante de la conversación hasta ahora."
    }
  }
}
```

---

## Reglas críticas del JSON

### 1. Nunca rompas el formato
Aunque la conversación se ponga rara, mantén la estructura JSON. Si el lead manda solo "ok" o un emoji, responde en JSON con tu mejor inferencia.

### 2. `mensaje_para_lead` puede ser string o array
- **String** si la respuesta tiene menos de ~80 palabras / cabe en un solo DM cómodamente.
- **Array** si requieres chunking (M4, M5, respuestas largas a objeciones).

### 3. Reglas del array
- Cada elemento es un DM separado que el sistema externo enviará con ~1-2 segundos de pausa entre uno y otro.
- El último elemento puede ser SOLO el link de Calendly cuando aplique (ver `knowledge-base/04-voz-y-tono.md`).
- Nunca pongas texto adicional después de un link en el mismo array.

### 4. Saltos de línea
Dentro de un string, usa `\n` para saltos de línea. El sistema externo los respeta al renderizar el DM.

### 5. Si `handoff_humano: true`
- `mensaje_para_lead` debe ser el mensaje de transición ("Dame un momento...").
- `razon_handoff` debe explicar por qué (catálogo en `sops/sop-03-criterios-handoff-humano.md`).

### 6. `resumen_lead` se actualiza en CADA turno
No lo dejes en blanco si ya tienes data acumulada de turnos anteriores. Reinyecta lo que sabes.

### 7. `etapa_actual` refleja la etapa REAL
No la etapa esperada — la etapa donde está la conversación ahora.

### 8. `siguiente_accion_esperada` indica qué espera el sistema externo
- `esperar_respuesta_lead`: el flujo está activo, esperando que el lead responda.
- `esperar_calendly_agendado`: M5 enviado, el sistema espera el evento en Calendly.
- `escalar_humano`: el humano toma el control.
- `cerrar_lead`: la conversación está cerrada (con éxito o descalificada).

---

## Ejemplo completo — Input M1 → Output M2

### Input (user message en Claude API):
```
"Hola, soy ingeniera, gano como 8 millones al mes"
```

### Output esperado:
```json
{
  "mensaje_para_lead": "Perfecto, son buenos ingresos.\n\nAhora, si tuvieras que elegir, ¿cuál es tu mayor frustración hoy con tu dinero?\n\nA) No me alcanza, siempre estoy en cero a fin de mes\nB) No sé en qué se va, es como si se evaporara\nC) Siento que debería estar mejor de lo que estoy con lo que gano\nD) Otra (¿cuál?)",
  "metadata": {
    "etapa_actual": "M2",
    "siguiente_accion_esperada": "esperar_respuesta_lead",
    "calificacion_financiera": "calificado",
    "calificacion_dolor": "desconocido",
    "calificacion_urgencia": "desconocido",
    "handoff_humano": false,
    "razon_handoff": null,
    "resumen_lead": {
      "nombre": null,
      "profesion": "Ingeniera",
      "ingreso_aproximado_cop": "$8M COP/mes",
      "dolor_principal": null,
      "urgencia": "desconocida",
      "objeciones_planteadas": [],
      "notas": "Ingeniera, $8M COP/mes. Califica financieramente. Pasa a M2 para calificar dolor."
    }
  }
}
```

---

## Ejemplo con chunking — M5

```json
{
  "mensaje_para_lead": [
    "¡Perfecto, Daniela! 🙌\n\nTe paso un espacio en mi agenda. Es una llamada de 30 min donde yo mismo analizo tu caso y te muestro qué ajustar para empezar a construir patrimonio con lo que ya ganas.\n\nAlgo importante: elige un momento donde estés tranquilo, sin afanes, porque te voy a hacer preguntas específicas para darte una hoja de ruta clara.\n\nCuando termines de agendar, avísame por aquí y te paso un par de preguntas para que aprovechemos los 30 minutos al máximo. 💪",
    "https://calendar.app.google/iMW5LBbkcAvorypF9"
  ],
  "metadata": {
    "etapa_actual": "M5",
    "siguiente_accion_esperada": "esperar_calendly_agendado",
    "calificacion_financiera": "calificado",
    "calificacion_dolor": "calificado",
    "calificacion_urgencia": "alta",
    "handoff_humano": false,
    "razon_handoff": null,
    "resumen_lead": {
      "nombre": "Daniela",
      "profesion": "Ingeniera",
      "ingreso_aproximado_cop": "$7M COP/mes",
      "dolor_principal": "B - no sabe en qué se va la plata",
      "urgencia": "alta",
      "objeciones_planteadas": [],
      "notas": "Daniela, ingeniera, $7M. Dolor B. Urgencia alta. Pitch enviado, aceptó la llamada. Cierre M5 enviado."
    }
  }
}
```

---

## Ejemplo con handoff

```json
{
  "mensaje_para_lead": "Dame un momento, Carlos. Voy a revisar tu caso con calma para darte la mejor respuesta. Te escribo en un rato. 🙌",
  "metadata": {
    "etapa_actual": "handoff",
    "siguiente_accion_esperada": "escalar_humano",
    "calificacion_financiera": "calificado",
    "calificacion_dolor": "calificado",
    "calificacion_urgencia": "alta",
    "handoff_humano": true,
    "razon_handoff": "objecion_fuera_playbook",
    "resumen_lead": {
      "nombre": "Carlos",
      "profesion": "Médico",
      "ingreso_aproximado_cop": "$9M COP/mes",
      "dolor_principal": "C - siente que debería estar mejor",
      "urgencia": "alta",
      "objeciones_planteadas": ["¿Cómo sé que esto no es una estafa? Necesito ver clientes reales que hayan terminado"],
      "notas": "Carlos médico $9M. Califica completo. Después de M4 pidió hablar con clientes que ya terminaron — objeción fuera del playbook. Escalar."
    }
  }
}
```
