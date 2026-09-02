# M2 · Validación de Endeudamiento ★ NUEVO V4.0

> **V4.0 — Mensaje 2.** Se ejecuta después de M1 (ingreso ≥ $7M) y antes de M3 (Dolor).

**Etapa:** Lead calificó por ingreso en M1 (≥ $7M).
**Objetivo:** Validar que el nivel de endeudamiento permite trabajar el método. Si está por encima de su tope según ingreso, el programa NO es el primer paso — primero necesita bajar deuda.

---

## Script base

```
Ok, [Nombre]. Para asegurar que mi método te aplique perfecto y puedas ver resultados rápidos, necesito validar algo clave: ¿sabes aproximadamente cuál es tu nivel de endeudamiento hoy? 🤔

Para calcularlo suma todo lo que pagas al mes en créditos, tarjetas, préstamos o deudas con alguien. El arriendo, servicios y mercado NO CUENTAN — esos son gastos fijos.

Con ese número haces esto: total de deudas ÷ ingresos del mes × 100

Ejemplo: $1.500.000 en deudas ÷ $7.000.000 de ingresos × 100 = 21%

¿Cuánto te da a ti? 😊
```

## Por qué funciona
- Le das una fórmula clara con un ejemplo concreto → reduce la fricción de responder.
- Posiciona la pregunta como un cuidado hacia el lead ("para que veas resultados rápidos").
- Filtra leads que necesitan otra ayuda antes (estrategia de salida de deudas).

---

## Filtro 2 — Tope de endeudamiento SEGÚN INGRESO

El tope NO es fijo, depende del ingreso:

| Ingreso mensual | Tope de endeudamiento |
|---|---|
| Cerca de $7M | ≤ 50% |
| Más de $9M | hasta 60% |

Racional: a mayor ingreso, mayor excedente absoluto, así que se tolera un % de deuda más alto.

## Bifurcación post-M2

| Respuesta del lead | Acción |
|---|---|
| **Dentro de su tope** (≤50% si ~$7M; ≤60% si >$9M) | ✅ Continuar a **M3 (Dolor)** |
| **Apenas por encima del tope** (hasta ~10 puntos) | 🟡 Borderline — preguntar tipo de deuda: *"Entiendo. ¿Qué tipo de deudas son? (créditos de consumo, hipoteca, tarjetas). Si la mayoría es deuda buena (vivienda) el escenario cambia."* |
| **Muy por encima de su tope** | 🔴 Descalificar con valor (Script 2 de `descalificacion-con-valor.md`) |
| **No sabe / "no estoy seguro"** | Insistir suave: *"Sin presión, dame un estimado. ¿Te queda plata después de pagar deudas o todo se va en eso?"* |

---

## Metadata esperada después de M2

```json
"metadata": {
  "etapa_actual": "M2",
  "endeudamiento_pct": 0,
  "siguiente_accion_esperada": "esperar_respuesta_lead"
}
```
