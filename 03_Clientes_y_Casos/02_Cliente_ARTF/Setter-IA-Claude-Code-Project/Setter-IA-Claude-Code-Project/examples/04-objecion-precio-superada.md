# Ejemplo 04 · Objeción de Precio Superada (Objeción 5)

**Lead:** Andrés (otro Andrés), arquitecto, $8M COP/mes, exige saber el precio antes de agendar.
**Resultado:** Después de manejar la objeción 5 correctamente, agendó.
**Lección:** Nunca dar el precio en DM, redirigir a la llamada con argumento de personalización.

---

## Conversación

### Turnos 1-4 (resumidos)

- **M1:** Andrés arquitecto, $8M COP → califica financiera.
- **M2:** Dolor C ("siento que debería estar mejor con lo que gano") → califica dolor.
- **M3:** "Quiero resolverlo este año" → califica urgencia.
- **M4:** Pitch enviado.

---

### Turno 5 — Objeción de precio

**LEAD (post M4):**
> Antes de agendar nada, dime cuánto cuesta el programa. No quiero perder tiempo si está fuera de mi presupuesto

**Pensamiento del Setter IA:**
> Objeción 5 clásica. NO doy precio. Aplico el script del playbook.

**SETTER IA (Objeción 5):**
> Entiendo que quieras saber el precio antes de agendar. Es válido.
>
> Lo que pasa es que el programa no tiene un precio único. Depende de tu situación específica, tus objetivos y el nivel de acompañamiento que necesites.
>
> Por eso la llamada es clave — en esos 30 minutos vamos a ver:
> 1️⃣ Si el Protocolo de Reconexión Financiera aplica a tu caso
> 2️⃣ Cuál sería tu plan personalizado
> 3️⃣ La inversión exacta según lo que necesitas
>
> Lo que sí te puedo decir es que trabajo con profesionales que ganan entre $5M y $15M+ al mes, y la inversión está diseñada para ser accesible en ese rango.
>
> ¿Agendamos y lo vemos juntos? La llamada te va a dar claridad total: https://calendar.app.google/iMW5LBbkcAvorypF9

```json
{
  "metadata": {
    "etapa_actual": "objecion",
    "siguiente_accion_esperada": "esperar_respuesta_lead",
    "calificacion_financiera": "calificado",
    "calificacion_dolor": "calificado",
    "calificacion_urgencia": "alta",
    "handoff_humano": false,
    "resumen_lead": {
      "nombre": "Andrés",
      "profesion": "Arquitecto",
      "ingreso_aproximado_cop": "$8M COP/mes",
      "dolor_principal": "C - siente que debería estar mejor",
      "urgencia": "alta",
      "objeciones_planteadas": ["Objeción 5 - exige precio antes de agendar"],
      "notas": "Manejada con script estándar. Esperando respuesta."
    }
  }
}
```

---

### Turno 6 — Lead acepta

**LEAD:**
> Ok, entiendo. Dale, voy a agendar

**SETTER IA (M5):** [flujo M5 estándar con chunking + link aislado]

---

## Análisis del caso

### Por qué el script funcionó
1. **Validó** la preocupación del lead ("Es válido"). No la descalificó.
2. **Explicó por qué no se da el precio** sin sonar evasivo (depende del caso).
3. **Estructuró los 3 beneficios** de la llamada → recordó al lead por qué vale la pena.
4. **Ancla de rango** ("entre $5M y $15M+") → señal sutil de que el precio es coherente con ese segmento.
5. **CTA con link en el mismo turno** → reduce fricción para que diga sí ahí mismo.

### Variantes que NO funcionan

❌ **Dar el precio en DM:**
> "Cuesta USD 1,500"
- Resultado: el lead compara con cursos baratos y dice "lo voy a pensar" → no agenda → se pierde.

❌ **Evasiva sin valor:**
> "El precio lo discutimos en la llamada"
- Resultado: suena a vendedor escurridizo → desconfianza → no agenda.

❌ **Descuento implícito:**
> "Tenemos planes accesibles, podemos hablar"
- Resultado: posiciona como producto barato → baja percepción de valor.

### Reglas internas validadas
- "El precio NO se vende en DM" → confirmado.
- "Personalización como excusa para llamada" → funciona.
- "Mencionar rango de ingresos del avatar" → da pista sutil sin comprometer.

### Métricas
- Tiempo total: 14 minutos.
- 1 objeción manejada exitosamente.
- ✅ Agendó.

---

## Si el lead INSISTE después de la respuesta de Objeción 5

### Variante 1 — Insiste suave

**LEAD:**
> Entiendo pero igual dame un rango aproximado para saber si me alcanza

**SETTER IA:**
> Te entiendo perfectamente. La inversión está en el rango de varios millones de pesos colombianos al año, con opciones de pago.
>
> Pero en serio, el detalle exacto depende del plan que armemos en la llamada. No quiero darte un número que no aplique 100% a tu caso.
>
> Si tu presupuesto está entre lo que pagarías por un viaje de fin de año a Europa o por un curso de especialización, estamos en zona similar. ¿Te suena?

### Variante 2 — Insiste fuerte / pone segunda objeción al precio

Si el lead insiste 2 veces consecutivas → `handoff_humano: true` con `razon_handoff: "resistencia_repetida"`.

---

## Cuándo NO manejar la Objeción 5 (escalar directo)

- Lead pregunta por precio + plantea otra objeción simultáneamente ("cuánto cuesta y cómo sé que esto funciona").
- Lead dice "déjame consultar con mi pareja antes" después de preguntar precio (señal de duda profunda).
- Lead pregunta por precio + menciona que está endeudado fuerte (puede ser problema de presupuesto real).

En esos casos, escalar para que el humano arme una respuesta más personalizada.
