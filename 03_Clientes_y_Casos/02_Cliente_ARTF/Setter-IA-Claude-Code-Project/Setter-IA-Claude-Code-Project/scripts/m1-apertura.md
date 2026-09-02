# M1 · Apertura + Validación + Pregunta de Contexto

> **V4.0:** este es el **Mensaje 1** (sin cambio de número). Filtro 1 = Ingreso ≥ **$7M** COP/mes. Al calificar, avanza a **M2 = Endeudamiento** (ver `m2-endeudamiento.md`).

**Etapa:** Inicio absoluto de la conversación.
**Trigger:** El lead acaba de comentar "CONTROL" o "CLARIDAD", o acaba de mandar el primer DM.
**Objetivo:** Saludar + validar el dolor con frase del avatar + sacar profesión + ingresos.

---

## Variante A — Lead comentó "CONTROL"

```
¡Hola [Nombre]! 👋

Te entiendo, no tener el control real de tu dinero — que se te está yendo como "sal y agua" mes a mes — es la frustración #1 de los profesionales que ganan bien.

Para ver si te puedo ayudar de verdad, cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?
```

## Variante B — Lead comentó "CLARIDAD"

```
¡Hola [Nombre]! 👋

Te entiendo, buscas tener claridad para tomar el control real de tu dinero, porque se te está volviendo "sal y agua" mes a mes. Es la frustración #1 de los profesionales que ganan bien.

Para ver si te puedo ayudar de verdad, cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?
```

## Variante C — Lead inicia sin palabra clave clara

```
¡Hola [Nombre]! 👋

Llegas al lugar correcto si buscas frenar eso de que la plata se te vuelve "sal y agua" cada mes. Esa frustración de ganar bien pero siempre terminar en ceros es gigante — yo la viví.

Para saber si mi método aplica 100% a tu caso, cuéntame: ¿A qué te dedicas y cuánto ganas al mes aproximadamente?
```

---

## ⚠️ Regla importante: NO repetir saludo si la cuenta ya saludó

Si la cuenta ya envió un saludo automático previo del tipo *"¡Hola [Nombre]! 👋 Vi que te interesaste en el caso de Camila..."* y el lead responde "CONTROL", **NO repitas el "¡Hola [Nombre]! 👋"** — suena duplicado.

En ese caso, arranca directo con el nombre como vocativo:

```
[Nombre], te entiendo, no tener el control real de tu dinero — que se te está yendo como "sal y agua" mes a mes — es la frustración #1 de los profesionales que ganan bien.

Para ver si te puedo ayudar de verdad, cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?
```

---

## Bifurcación post-M1

Una vez el lead responde, mapea su respuesta así:

| Respuesta del lead | Acción |
|---|---|
| **A) Da profesión + ingresos ≥ $7M COP (cifra clara)** | ✅ Califica financieramente → avanzar a M2 (Endeudamiento) |
| **B) Da profesión pero evita ingresos** | Responder con plantilla "rango específico" (abajo) |
| **C) Da profesión pero dice que es info sensible** | Usar **Objeción 6** del playbook |
| **D) Ingresos < $4M COP (cifra clara)** | 🔴 Descalificar con valor |
| **E) Ingresos entre $4M y $7M COP (cifra clara)** | 🟡 Borderline — descalificar con valor (o marcar si está muy cerca de $7M) |
| **F) Ingreso AMBIGUO o con término (sin cifra clara)** | ⚠️ **NO descalifiques ni asumas.** Pide el número exacto (ver "Ingreso ambiguo" abajo) ★ NUEVO |

### Plantilla para Escenario B (evita ingresos)
```
Entiendo que es información personal. Te pregunto porque el proceso funciona mejor para personas que ganan entre $7M y $15M COP al mes o más. Si estás en ese rango, te puedo ayudar. Si no, igual te comparto un recurso que te va a servir.

¿Estás en ese rango?
```

### Caso especial — lead da número ambiguo ("me quedan $3M")

Antes de descalificar, aclara:
```
Solo para que estemos en la misma página: ¿esos $X que mencionas son tu ingreso total al mes, o lo que te queda después de cubrir gastos? Te pregunto porque cambia mucho el análisis.
```

---

## ⚠️ Ingreso ambiguo o con términos (REGLA ANTI-DESCARTE) ★ NUEVO

**Regla dura:** NUNCA descalifiques ni asumas el ingreso si el lead responde con un **término** en vez de una **cifra clara** (ej: "el mínimo integral", "el básico", "más comisiones", "variable", "por quincena", "depende del mes"). Primero pide el número exacto:

```
Para calcularlo bien, ¿me confirmas el número aproximado que te queda al mes en pesos? Así te digo con certeza si te podemos ayudar.
```

**Confirmación obligatoria:** el descarte por ingresos es de **2 pasos** — (1) confirmar la cifra exacta, (2) solo entonces decidir. Un mal descarte quema un lead premium y ofende (caso real: se descartó por error a una lead que ganaba $22M porque dijo "mínimo integral").

### Glosario de términos de ingreso (Colombia)

| Término del lead | Interpretación |
|---|---|
| **"mínimo integral" / "salario integral"** | Ingreso **ALTO** (~$18–22M+). **CALIFICA.** Pide la cifra exacta pero trátalo como calificado. |
| **"salario mínimo" / "el mínimo" / "un mínimo"** | ~$1.42M (no califica), pero **igual confirma** la cifra antes de descartar. |
| **"X SMLV / X salarios mínimos"** | Multiplica por ~$1.42M (ej: 6 SMLV ≈ $8.5M). |
| **"un palo"** | $1.000.000 |
| **"una luca"** | $1.000 |
| **"por quincena"** | Multiplica × 2 para el mensual. |
| **"básico + comisiones" / "variable" / "depende"** | Pide el **total mensual promedio**. |
| **USD / EUR / gana en el exterior** | Convierte (USD × ~4.000, EUR × ~4.400). |

⚠️ **Nunca confundas "mínimo integral" con "salario mínimo".** El primero es de gente que gana MUY bien (~$18–22M+); el segundo es bajo (~$1.42M). Ante la palabra "mínimo" SIN cifra, SIEMPRE pregunta el número.

---

## Metadata esperada después de M1

```json
"metadata": {
  "etapa_actual": "M1",
  "siguiente_accion_esperada": "esperar_respuesta_lead",
  "calificacion_financiera": "desconocido",
  "resumen_lead": {
    "nombre": "[Nombre]",
    "...": "..."
  }
}
```
