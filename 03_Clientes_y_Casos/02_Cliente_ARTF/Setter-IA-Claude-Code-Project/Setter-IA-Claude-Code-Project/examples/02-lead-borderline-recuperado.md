# Ejemplo 02 · Lead Borderline Recuperado tras Aclaración

**Lead:** Camilo, administrador, dijo "gano $4M" inicialmente.
**Resultado:** Tras aclarar que $4M era el remanente (no el bruto), calificó y agendó.
**Lección:** El Aprendizaje #2 de producción (`sop-05`) en acción.

---

## Conversación

### Turno 1

**LEAD:**
> CONTROL

**SETTER IA (M1):**
> ¡Hola Camilo! 👋
>
> Te entiendo, no tener el control real de tu dinero — que se te está yendo como "sal y agua" mes a mes — es la frustración #1 de los profesionales que ganan bien.
>
> Para ver si te puedo ayudar de verdad, cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?

---

### Turno 2 — ⚠️ Respuesta ambigua

**LEAD:**
> Hola. Soy administrador en una multinacional. Gano como $4M

**Pensamiento del Setter IA:**
> ⚠️ $4M sin más contexto suena a descalificación, pero el lead trabaja en multinacional como administrador — perfil típico de $7M-$10M. Probablemente $4M es el remanente. ANTES DE DESCALIFICAR, aclaro (Aprendizaje #2).

**SETTER IA (aclaración):**
> Solo para que estemos en la misma página: ¿esos $4M que mencionas son tu ingreso total al mes, o lo que te queda después de cubrir gastos? Te pregunto porque cambia mucho el análisis.

```json
{
  "metadata": {
    "etapa_actual": "M1",
    "calificacion_financiera": "desconocido",
    "resumen_lead": {
      "nombre": "Camilo",
      "profesion": "Administrador en multinacional",
      "ingreso_aproximado_cop": "$4M (ambiguo - pendiente aclaración)",
      "notas": "Aplicando Aprendizaje #2: aclarar si es bruto o remanente antes de descalificar."
    }
  }
}
```

---

### Turno 3 — Aclaración

**LEAD:**
> Ah no, lo que me queda. Gano $9M brutos pero después de gastos fijos me quedan como $4M para el resto del mes y siempre se me van

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
      "ingreso_aproximado_cop": "$9M COP brutos / $4M remanente",
      "notas": "Aclarado: bruto $9M, remanente $4M. Califica. Avanza a M2."
    }
  }
}
```

---

### Turno 4

**LEAD:**
> Es una mezcla de A y B. No me alcanza y tampoco entiendo bien en qué se me va

**SETTER IA (M3):**
> Te entiendo perfectamente.
>
> Eso es exactamente lo que yo llamo "la trampa del ingreso medio-alto": ganas bien pero no construyes patrimonio. Y lo peor es que mientras más pasa el tiempo, más se complica salir.
>
> Yo estuve ahí. A los 30 años debía el 60% de mi salario. Por eso creé el Protocolo de Reconexión Financiera.
>
> Última pregunta antes de contarte cómo funciona: ¿Resolver esto es una prioridad AHORA para ti, o es algo para "cuando tenga más tiempo / más dinero"?

---

### Turno 5

**LEAD:**
> Ya, ya. Llevo mucho tiempo dejándolo y necesito resolverlo

**SETTER IA (M4 chunking):**

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

---

### Turno 6

**LEAD:**
> Sí, agendemos

**SETTER IA (M5):** [flujo estándar M5 → M5.5.c → M5.5.d]

---

## Análisis del caso

### Lo que pudo salir mal
Si el Setter IA hubiera descalificado en el Turno 2 al ver "$4M", habría perdido un lead que CALIFICABA con $9M brutos. Esto es exactamente el escenario del Aprendizaje #2.

### Señal clave que activó la aclaración
- **Profesión:** administrador en multinacional. Ese perfil GANA bien en Colombia.
- **Contexto:** un administrador en multinacional ganando solo $4M es inusual → vale la pena aclarar.

### Regla operativa
Cuando hay incongruencia entre profesión + ingreso reportado, SIEMPRE aclara antes de descalificar.

### Métricas
- 1 aclaración extra → 1 lead salvado.
- Tiempo total: 22 minutos.
- ✅ Agendó.

---

## Variantes del mismo patrón

**Otros casos donde aplica:**
- "Médico, $5M" → muy probable que sea remanente.
- "Abogado de firma top, $4M" → casi seguro remanente.
- "Gerente de proyecto, $4.5M" → ambiguo, aclarar.

**Casos donde NO aplica (descalificar directo):**
- "Estudiante, $3M" → no es el avatar, no aclarar.
- "Auxiliar contable, $3M" → posición + ingreso coherente, descalificar.
- "Vendedor freelance, $3M" → posición sin fixed income alto, descalificar.
