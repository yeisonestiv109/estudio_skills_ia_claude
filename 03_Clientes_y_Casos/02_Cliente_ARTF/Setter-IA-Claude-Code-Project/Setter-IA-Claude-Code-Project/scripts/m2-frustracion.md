# M3 · Validación de Dolor + Pregunta de Frustración

> **⚠️ V4.2 — RENUMERADO:** este script (Dolor) ahora es el **Mensaje 3**. En V4.2 el orden es: M1 Ingreso → **M2 Endeudamiento** (`m2-endeudamiento.md`) → **M3 Dolor (este)** → M4 Urgencia → M5 Pitch → M6 Cierre + link → M7 Asistencia.

**Etapa:** Lead ya calificó por ingreso (M1) y endeudamiento (M2).
**Objetivo:** Identificar el dolor específico → segmentar el caso de éxito a citar más adelante.

---

## Script base

```
Perfecto, son buenos ingresos.

Ahora, si tuvieras que elegir, ¿cuál es tu mayor frustración hoy con tu dinero?

A) No me alcanza, siempre estoy en cero a fin de mes
B) No sé en qué se va, es como si se evaporara
C) Siento que debería estar mejor de lo que estoy con lo que gano
D) Otra (¿cuál?)
```

---

## Variante si el lead está en borderline ($5M-$7M)

No empieces con "son buenos ingresos" porque suena forzado. Usa:

```
Listo, entendido.

Ahora cuéntame: si tuvieras que elegir, ¿cuál es tu mayor frustración hoy con tu dinero?

A) No me alcanza, siempre estoy en cero a fin de mes
B) No sé en qué se va, es como si se evaporara
C) Siento que debería estar mejor de lo que estoy con lo que gano
D) Otra (¿cuál?)
```

---

## Bifurcación post-M3

| Respuesta | Acción |
|---|---|
| **A** ("no me alcanza") | ✅ Califica → avanzar a M4. Caso a citar después: Carlos. |
| **B** ("no sé en qué se va") | ✅ Califica → avanzar a M4. Caso a citar: Sandra Milena. |
| **C** ("debería estar mejor") | ✅ Califica → avanzar a M4. Caso a citar: cualquiera del avatar. |
| **D** con dolor relacionado (deudas, pareja, hijos, futuro) | ✅ Profundiza una vuelta más → M4. |
| **D** con dolor NO financiero (ej: "no me gusta mi trabajo") | 🟡 Reconducir (script abajo). |

### Plantilla para reconducir Escenario D no-financiero

```
Entiendo. Lo que pasa es que nos especializamos específicamente en ayudar a profesionales a construir patrimonio y salir del ciclo de "ganar bien, vivir mal". Si tu tema principal es otro, puede que no seamos el mejor fit.

¿O tu frustración está conectada con que sientes que tu dinero no te alcanza para tomar decisiones más libres?
```

- Si reconecta → M4.
- Si no → descalificar con valor.

---

## ⚠️ Si el lead te da una motivación profunda como respuesta D

Si dice algo como "quiero comprar casa", "quiero irme a vivir solo", "quiero independizarme":
- **NO escales**. Eso es motivación, no crisis.
- Valida + ancla como combustible:

```
Eso de [comprar casa / vivir solo / independizarte] es exactamente el tipo de objetivo donde el orden financiero hace la diferencia. ¿Y hoy sientes que tu plata te alcanza para llegar ahí, o se te va antes de que te des cuenta?
```

Si responde algo que califica el dolor → M4. Si reconfirma la motivación grande → M5 directo (puedes saltarte el filtro de urgencia porque la motivación ES la urgencia).

---

## Metadata esperada después de M3

```json
"metadata": {
  "etapa_actual": "M3",
  "calificacion_dolor": "calificado" | "desconocido" | "descalificado",
  "resumen_lead": {
    "dolor_principal": "[A/B/C/D + descripción]"
  }
}
```
