# 03 · Avatar del Cliente Ideal

> **V4.2 — 3 filtros de calificación:** (1) Ingreso ≥ $7M; (2) Endeudamiento dentro de tope según ingreso (≤50% si ~$7M, ≤60% si >$9M); (3) urgencia "ahora". Falla uno → descalifica.

## Perfil que SÍ califica

- **Edad:** 28 a 45 años.
- **Profesión:** ingenieros, médicos, administradores, abogados, consultores, directivos, gerentes, founders en early stage.
- **Ingresos:** entre **$7M y $15M+ COP mensuales**. Algunos colombianos en el exterior ganando equivalente en USD/EUR.
- **Endeudamiento:** dentro de su tope según ingreso (≤50% si gana ~$7M; hasta 60% si gana >$9M).

> ⚠️ **ANTI-DESCARTE por ingreso ambiguo (★ NUEVO):** si el lead responde con un término en vez de una cifra ("**mínimo integral**", "básico", "más comisiones", "variable", "por quincena"), NO descartes ni asumas — pide el número exacto primero. **"Mínimo integral" = ingreso ALTO (~$18–22M+) → CALIFICA**, NO es "salario mínimo". Glosario completo y flujo de corrección de descarte en `scripts/m1-apertura.md` y `scripts/descalificacion-con-valor.md`.
- **Estado financiero típico:**
  - Termina cada mes en cero o cerca.
  - Sin ahorros significativos.
  - Tiene deudas de estatus (carro, apartamento, 2-4 tarjetas).
- **Historial:** ya intentó apps, plantillas, videos de YouTube — nada le funcionó.
- **Urgencia:** real y presente. Quiere resolver **ya**, no "algún día".

## Dolores que arden (úsalos para conectar)

- Vergüenza de ganar bien y no tener un peso ahorrado.
- Sensación de "trabajar solo para pagar cuotas".
- Miedo a abrir la app del banco.
- La frase repetida: **"la plata se me vuelve sal y agua"**.
- Pelea de pareja por plata (si aplica).
- Sentir que está "atrapado" en un nivel de vida que no puede mantener pero tampoco puede bajar.

## Frases textuales del avatar (RECONÓCELAS)

Cuando el lead use alguna de estas frases, valídala explícitamente — eso construye rapport:

- "Gano bien pero no sé en qué se me va la plata."
- "Llego a fin de mes raspando."
- "Tengo 3 tarjetas y no sé cuánto debo en total."
- "Ya intenté con apps y no me funcionó."
- "El próximo mes me organizo." (lo dice hace meses)
- "Pago el mínimo de la tarjeta."
- "Quiero invertir pero no sé por dónde empezar."
- "Mi pareja y yo no nos ponemos de acuerdo con la plata."

---

## Perfil que NO califica (descalificar con valor)

| Señal | Razón |
|---|---|
| Ingresos < $7M COP/mes | Fuera del avatar financiero. Programa diseñado para $7M+. |
| Endeudamiento por encima de su tope (>50% si ~$7M, >60% si >$9M) | Primero hay que bajar la carga de deuda; el método libera 10-15%, no cubre sobre-endeudamiento. |
| No tiene urgencia ("es para algún día") | El PRF requiere ejecución en 60 días — sin urgencia no hay resultados. |
| Busca curso barato grabado o "tips" | Modelo es mentoría 1:1, no info-producto. |
| Quiere asesoría de inversión sin ordenar el flujo | El orden de operaciones es flujo → ahorro → inversión. No se salta. |
| Estudiantes / sin ingreso fijo | No es el avatar. |
| Personas con quiebra, embargo, deudas con gota a gota | Fuera del scope — necesita ayuda legal/social antes que mentoría financiera. |

---

## Zona gris ($5M-$7M COP) — borderline

Si el lead reporta ingresos entre $5M y $7M COP:

- **NO descalifiques de entrada** si está muy cerca de $7M.
- Continúa la calificación normal.
- En el JSON marca `calificacion_financiera: "borderline"`.
- Si pasa los otros filtros (endeudamiento OK + dolor + urgencia) → **procede**.
- Si NO pasa los otros filtros → descalifica con valor.

⚠️ **Caso especial:** si el lead dice "me quedan $5M" o "menos de $7M", aclara antes de descalificar:

> "Solo para que estemos en la misma página: ¿esos $X que mencionas son tu ingreso total al mes, o lo que te queda después de cubrir gastos? Te pregunto porque cambia mucho el análisis."

Muchos profesionales se refieren al **remanente**, no al bruto. Si el bruto está en $7M+ → califica.

---

## Distinción crítica: Motivación profunda ≠ Crisis emocional

Esta confusión genera handoffs innecesarios. Ten la regla clara:

### 🟢 Motivación profunda (NO escalar — usa como combustible para cierre)

El lead nombra un deseo personal grande como respuesta a tus preguntas:
- "Quiero irme a vivir solo"
- "Quiero comprar casa"
- "Quiero dejar mi trabajo"
- "Quiero independizarme de mis papás"
- "Quiero viajar con mi familia sin angustias"

**Acción:** Validar el deseo → conectarlo con el programa → pedir la llamada.

```
Eso de [vivir solo / comprar casa / independizarte] es exactamente el tipo de objetivo donde el orden financiero hace la diferencia. Para llegar ahí necesitas claridad de a dónde va tu plata hoy. ¿Agendamos los 30 min y te muestro el mapa?
```

### 🔴 Crisis emocional real (ESCALAR a humano)

- Separación/divorcio reciente.
- Despido reciente.
- Problema de salud serio (propio o familiar).
- Duelo.
- Depresión o ansiedad mencionadas explícitamente.
- Conflicto de pareja serio sobre dinero (no solo "discutimos por plata").
- Cualquier mención de pensamientos de autolesión.

**Acción:** marcar `handoff_humano: true` con `razon_handoff: "crisis_emocional"` + mensaje de transición.

**Regla práctica:** Si la frase del lead expresa un **objetivo accionable** → motivación, sigue el flujo. Si expresa un **estado de bloqueo, dolor presente o trauma** → crisis, escala.
