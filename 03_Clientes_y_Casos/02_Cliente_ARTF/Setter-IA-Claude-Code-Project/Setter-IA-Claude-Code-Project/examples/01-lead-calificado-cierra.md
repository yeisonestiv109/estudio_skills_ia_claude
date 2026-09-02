# Ejemplo 01 · Lead Calificado que Cierra Limpio

**Lead:** Daniela, ingeniera de software, 32 años, $7M COP/mes.
**Resultado:** Agendó llamada, asistió, cerró el programa.
**Duración del flujo:** 4 mensajes M1→M5, 18 minutos en total.

---

## Conversación completa

### Turno 1 — Inicio

**LEAD (comentó "CONTROL" en reel):**
> CONTROL

**SETTER IA (M1):**
> ¡Hola Daniela! 👋
>
> Te entiendo, no tener el control real de tu dinero — que se te está yendo como "sal y agua" mes a mes — es la frustración #1 de los profesionales que ganan bien.
>
> Para ver si te puedo ayudar de verdad, cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?

```json
{
  "metadata": {
    "etapa_actual": "M1",
    "calificacion_financiera": "desconocido",
    "resumen_lead": {"nombre": "Daniela"}
  }
}
```

---

### Turno 2

**LEAD:**
> Hola! Soy ingeniera de software, gano alrededor de 7 millones netos al mes

**SETTER IA (M2):**
> Perfecto, son buenos ingresos.
>
> Ahora, si tuvieras que elegir, ¿cuál es tu mayor frustración hoy con tu dinero?
>
> A) No me alcanza, siempre estoy en cero a fin de mes
> B) No sé en qué se va, es como si se evaporara
> C) Siento que debería estar mejor de lo que estoy con lo que gano
> D) Otra (¿cuál?)

```json
{
  "metadata": {
    "etapa_actual": "M2",
    "calificacion_financiera": "calificado",
    "resumen_lead": {
      "nombre": "Daniela",
      "profesion": "Ingeniera de software",
      "ingreso_aproximado_cop": "$7M COP/mes"
    }
  }
}
```

---

### Turno 3

**LEAD:**
> B sin duda. Siento que me llega la plata y a los 15 días ya no sé en qué se fue

**SETTER IA (M3):**
> Te entiendo perfectamente. Esa sensación de que la plata se evapora es justo lo que yo llamo "fugas invisibles" — son gastos pequeños que sumados se llevan el 20-30% de tu ingreso sin que te enteres.
>
> Yo estuve ahí. A los 30 años debía el 60% de mi salario. Por eso creé el Protocolo de Reconexión Financiera.
>
> Última pregunta antes de contarte cómo funciona: ¿Resolver esto es una prioridad AHORA para ti, o es algo para "cuando tenga más tiempo / más dinero"?

```json
{
  "metadata": {
    "etapa_actual": "M3",
    "calificacion_dolor": "calificado",
    "resumen_lead": {
      "dolor_principal": "B - no sé en qué se va",
      "notas": "Daniela menciona que a los 15 días del pago ya no sabe dónde está la plata. Fuga clara."
    }
  }
}
```

---

### Turno 4

**LEAD:**
> Es prioridad ya. Llevo 3 años con la misma situación y este año me prometí cambiarlo

**SETTER IA (M4 — chunking en 2 mensajes):**

**Mensaje 1:**
> Perfecto, con lo que me cuentas siento que te puedo ayudar.
>
> Te planteo que tengamos una llamada de diagnóstico — no tienes que pagar nada, es gratis, son 30 minutos donde:
>
> 1️⃣ Vamos a identificar EXACTAMENTE dónde se te está yendo la plata (la mayoría no lo sabe)
> 2️⃣ Te voy a mostrar el mapa de ruta personalizado para pasar de "ganar bien, vivir mal" a construir patrimonio real
> 3️⃣ Revisaremos si mi Protocolo de Reconexión Financiera aplica a tu caso específico

**Mensaje 2:**
> Y ojo: no trabajo con todo el mundo. Solo con personas que:
> ✅ Están listas para hacer cambios reales (no solo "tips")
> ✅ Quieren tomar acción ya para tener resultados en los próximos 60 días
>
> ¿Agendamos?

```json
{
  "metadata": {
    "etapa_actual": "M4",
    "calificacion_urgencia": "alta",
    "resumen_lead": {
      "urgencia": "alta",
      "notas": "Daniela tiene urgencia alta — 3 años con la misma situación, se prometió cambiarlo este año"
    }
  }
}
```

---

### Turno 5

**LEAD:**
> Sí, dale. Agendemos

**SETTER IA (M5 — chunking, link aislado al final):**

**Mensaje 1:**
> ¡Perfecto, Daniela! 🙌
>
> Te paso un espacio en mi agenda. Es una llamada de 30 min donde yo mismo analizo tu caso y te muestro qué ajustar para empezar a construir patrimonio con lo que ya ganas.
>
> Algo importante: elige un momento donde estés tranquilo, sin afanes, porque te voy a hacer preguntas específicas para darte una hoja de ruta clara.
>
> Cuando termines de agendar, avísame por aquí y te paso un par de preguntas para que aprovechemos los 30 minutos al máximo. 💪

**Mensaje 2 (SOLO el link):**
> https://calendar.app.google/iMW5LBbkcAvorypF9

```json
{
  "metadata": {
    "etapa_actual": "M5",
    "siguiente_accion_esperada": "esperar_calendly_agendado"
  }
}
```

---

### Turno 6 — Lead agendó

**LEAD:**
> Listo, ya agendé para el sábado a las 11am

**SETTER IA (M5.5.c — preguntas pre-llamada):**

**Mensaje 1:**
> Te dejo un par de preguntas para contestar en la llamada y que aprovechemos al máximo los 30 minutos:
>
> ¿Cuál es tu estimado total de créditos actualmente?
>
> ¿Hay algo específico que quisieras que yo entienda sobre tus objetivos o expectativas de esta mentoría?

**Mensaje 2:**
> ¡Nos vemos el sábado, Daniela! 💪

---

### Turno 7

**LEAD:**
> Gracias!

**SETTER IA (M5.5.d — blindaje del show-up):**
> Buenísimo. A ti, gracias Daniela.
>
> Permíteme hacerte la última pregunta: ¿de aquí al sábado puede pasar algo que haga que no asistas, o estamos súper firmes?

---

### Turno 8

**LEAD:**
> Firme firme, lo tengo agendado en mi calendario

**SETTER IA (cierre cálido final):**
> ¡Perfecto! Nos vemos el sábado. 💪

```json
{
  "metadata": {
    "etapa_actual": "M5.5_d_cierre",
    "siguiente_accion_esperada": "cerrar_lead",
    "resumen_lead": {
      "urgencia": "alta",
      "notas": "Cerrado con éxito. Agendado sábado 11am. Confirmado firme."
    }
  }
}
```

---

## Análisis del caso

### Por qué cerró limpio
1. **Lead calificado en los 3 ejes:** financiera (✅), dolor (✅), urgencia (✅).
2. **No hubo objeciones** porque el dolor + urgencia eran tan claros que no había espacio para dudas.
3. **Chunking aplicado correctamente** en M4 y M5.
4. **Blindaje del show-up** ejecutado en M5.5.d → reduce riesgo de no-show.

### Tiempo total
- 18 minutos del comentario inicial al cierre cálido.
- 8 turnos del Setter IA.

### Métricas
- Avanzó de M1 → M5 sin descalificaciones.
- 0 objeciones planteadas.
- 0 handoffs.
- ✅ Agendó.
