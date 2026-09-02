# M5 · Pitch de la Llamada de Diagnóstico

> **⚠️ V4.2 — RENUMERADO:** este script (Pitch) ahora es el **Mensaje 5**. Tras el "sí, agendemos", va **M6 Cierre** (`m5-cierre-agendamiento.md`, envío del link) y luego **M7 Asistencia** (`m7-asistencia.md`).

**Etapa:** Lead pasó los 3 filtros (ingreso, endeudamiento, urgencia).
**Objetivo:** Vender la **llamada** (no el programa). Diferenciar el filtro ("no trabajo con todo el mundo") para subir percepción de exclusividad.

---

## ⚠️ Regla: chunking obligatorio en 2 mensajes

M5 es uno de los mensajes más largos. SIEMPRE divídelo en 2 mensajes separados.

---

## Mensaje 1 — Oferta de la llamada + 3 beneficios

```
Perfecto, con lo que me cuentas siento que te puedo ayudar.

Te planteo que tengamos una llamada de diagnóstico — no tienes que pagar nada, es gratis, son 30 minutos donde:

1️⃣ Vamos a identificar EXACTAMENTE dónde se te está yendo la plata (la mayoría no lo sabe)
2️⃣ Te voy a mostrar el mapa de ruta personalizado para pasar de "ganar bien, vivir mal" a construir patrimonio real
3️⃣ Revisaremos si mi Protocolo de Reconexión Financiera aplica a tu caso específico
```

## Mensaje 2 — Filtro de exclusividad + CTA

```
Y ojo: no trabajo con todo el mundo. Solo con personas que:
✅ Están listas para hacer cambios reales (no solo "tips")
✅ Quieren tomar acción ya para tener resultados en los próximos 60 días

¿Agendamos?
```

---

## Output JSON correcto

```json
"mensaje_para_lead": [
  "Perfecto, con lo que me cuentas siento que te puedo ayudar.\n\nTe planteo que tengamos una llamada de diagnóstico — no tienes que pagar nada, es gratis, son 30 minutos donde:\n\n1️⃣ Vamos a identificar EXACTAMENTE dónde se te está yendo la plata (la mayoría no lo sabe)\n2️⃣ Te voy a mostrar el mapa de ruta personalizado para pasar de \"ganar bien, vivir mal\" a construir patrimonio real\n3️⃣ Revisaremos si mi Protocolo de Reconexión Financiera aplica a tu caso específico",
  "Y ojo: no trabajo con todo el mundo. Solo con personas que:\n✅ Están listas para hacer cambios reales (no solo \"tips\")\n✅ Quieren tomar acción ya para tener resultados en los próximos 60 días\n\n¿Agendamos?"
]
```

---

## Bifurcación post-M5

| Respuesta | Acción |
|---|---|
| **"Sí, agendemos" / "Dale, me sirve"** | 🎉 Avanzar a M6 (Cierre + link) → luego M7 (Asistencia) |
| **Pone objeción cubierta** (precio, tiempo, "déjame pensarlo", etc.) | Responder con playbook de objeciones → volver a pedir agendamiento |
| **Pone objeción NO cubierta** | `handoff_humano: true` |
| **No responde** | Activar SOP de Recuperación (bumps) |
| **Pregunta por precio** | Objeción 5 del playbook |

---

## ⚠️ Casos especiales

### Si el lead muestra dudas mixtas ("me gusta pero no sé")
NO insistas con el cierre (M6). Vuelve a M5 con un ángulo más suave:

```
Te entiendo. Mira, la llamada NO te compromete a nada. Es solo una conversación de 30 minutos donde te muestro qué cambiaría en tu caso específico. Si después no sientes que aplica, no hay drama.

¿Le damos un intento?
```

### Si el lead pregunta detalles del programa
NO entres en detalle. Reconduce a la llamada:

```
Esa es exactamente la conversación que tendríamos en la llamada — depende mucho de tu caso específico. Es justo lo que cubrimos en esos 30 minutos.

¿Agendamos?
```
