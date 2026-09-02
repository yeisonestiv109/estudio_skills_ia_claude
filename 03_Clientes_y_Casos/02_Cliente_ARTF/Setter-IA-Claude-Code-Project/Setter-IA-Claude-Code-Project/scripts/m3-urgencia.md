# M4 · Empatía + Pregunta de Urgencia

> **⚠️ V4.2 — RENUMERADO:** este script (Urgencia) ahora es el **Mensaje 4**. Si el lead responde "¿por qué es importante resolverlo ahora?", maneja con **Objeción 9** (ver `objection-handling/`).

**Etapa:** Lead calificó por ingreso (M1), endeudamiento (M2) y nombró su dolor (M3).
**Objetivo:** Filtrar por urgencia (Filtro 3). Solo califica si quiere resolver YA, no "algún día".

---

## Script base

```
Te entiendo perfectamente.

Eso es exactamente lo que yo llamo "la trampa del ingreso medio-alto": ganas bien pero no construyes patrimonio. Y lo peor es que mientras más pasa el tiempo, más se complica salir.

Yo estuve ahí. A los 30 años debía el 60% de mi salario. Por eso creé el Protocolo de Reconexión Financiera.

Última pregunta antes de contarte cómo funciona: ¿Resolver esto es una prioridad AHORA para ti, o es algo para "cuando tenga más tiempo / más dinero"?
```

---

## Variantes opcionales según el dolor del lead

### Si el lead eligió B en M3 ("no sé en qué se va")

```
Te entiendo perfectamente. Esa sensación de que la plata se evapora es justo lo que yo llamo "fugas invisibles" — son gastos pequeños que sumados se llevan el 20-30% de tu ingreso sin que te enteres.

Yo estuve ahí. A los 30 años debía el 60% de mi salario. Por eso creé el Protocolo de Reconexión Financiera.

Última pregunta antes de contarte cómo funciona: ¿Resolver esto es una prioridad AHORA para ti, o es algo para "cuando tenga más tiempo / más dinero"?
```

### Si el lead mencionó pareja

```
Te entiendo. Las finanzas en pareja son uno de los temas más complicados — y de los que más matrimonios desgastan.

Yo estuve ahí. A los 30 años debía el 60% de mi salario. Hoy ayudo a parejas como Javier y Catalina, que pasaron de gastar $12M sin rumbo a liberar $2M mensuales juntos.

Última pregunta antes de contarte cómo funciona: ¿Resolver esto es una prioridad AHORA para ti (y tu pareja), o es algo para "cuando tengamos más tiempo / más dinero"?
```

---

## Bifurcación post-M4

| Respuesta | Acción |
|---|---|
| **"Es prioridad ahora" / "Lo quiero resolver ya"** | ✅ Califica por urgencia → avanzar a M5 |
| **"Es para más adelante" / "Cuando tenga tiempo"** | 🔴 Descalificar con valor |
| **"Sí pero no sé si tengo plata para invertir"** | Esto NO es objeción al programa todavía (no le has pitcheado precio). Es duda existencial. Avanza a M5 y la objeción aparecerá si aparece. |
| **Motivación profunda revelada** ("para comprar casa", "para irme a vivir solo") | ✅ Calificada por urgencia + ancla en M5 |

---

## ⚠️ Cuidado con el filtro de urgencia

NO confundas urgencia emocional con crisis emocional.

- "Necesito resolverlo YA porque estoy ahogado" → urgencia válida, avanza.
- "Necesito resolverlo YA porque mi pareja me dejó por la plata" → crisis emocional, escala a humano.

Ver `knowledge-base/03-avatar-cliente-ideal.md` sección "Motivación profunda ≠ Crisis emocional".

---

## Metadata esperada después de M4

```json
"metadata": {
  "etapa_actual": "M4",
  "calificacion_urgencia": "alta" | "media" | "baja",
  "resumen_lead": {
    "urgencia": "alta" | "media" | "baja"
  }
}
```
