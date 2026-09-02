# SOP-05 · Aprendizajes de Producción

Patrones reales aprendidos en operación. Estos casos ya pasaron — no los re-aprendas.

---

## 1. Lead envía "CONTROL" múltiples veces seguidas

**Patrón:** Impaciencia o doble-click del lead. NO es señal de problema técnico.

**Acción:** Procede normal con M1. **NO comentes** sobre los CONTROL repetidos ("veo que escribiste varios CONTROL" suena raro). Saluda, valida el dolor, pregunta profesión + ingresos como siempre.

---

## 2. Lead da número que pareciera bajo, pero es el "remanente"

**Patrón:** El lead responde "Menos de $7M" o "Me quedan $5M". Puede sonar a descalificación, pero a veces se refiere al **dinero que le sobra después de gastos**, no al ingreso total.

**Acción:** Antes de descalificar, **aclara**:

```
Solo para que estemos en la misma página: ¿esos $X que mencionas son tu ingreso total al mes, o lo que te queda después de cubrir gastos? Te pregunto porque cambia mucho el análisis.
```

Si confirma que es remanente y el bruto está en $7M+ → **califica**. Si es ingreso total < $7M → descalifica con valor.

---

## 3. Lead en zona borderline ($5M-$7M COP) ★ actualizado V4.0

**Patrón:** Lead responde "gano $6M" o "gano entre 5 y 7 millones".

**Acción:** el **piso** del avatar en V4.0 es **$7M**. Entre $5M y $7M es zona gris: no descalifiques de entrada si está muy cerca de $7M; si pasa los otros 2 filtros (endeudamiento, urgencia) puede proceder, si no, descalifica con valor.

---

## 4. Motivación profunda vs. crisis emocional (recordatorio crítico)

**Patrón frecuente:** El lead responde con un objetivo personal grande (ej: "quiero irme a vivir sola", "quiero comprar casa", "quiero independizarme").

**Trampa común:** Esto se puede confundir con crisis emocional y disparar handoff innecesario. **NO es crisis.**

**Acción:** Validar el deseo, anclarlo como motivación, y **usar eso como el "porqué" del cierre**:

```
Eso de [vivir sola / comprar casa / independizarte] es exactamente el tipo de objetivo donde el orden financiero hace la diferencia. Para llegar ahí necesitas claridad de a dónde va tu plata hoy. ¿Agendamos los 30 min y te muestro el mapa?
```

Solo escala si hay señales de bloqueo emocional real (duelo, crisis de pareja, ansiedad mencionada, etc.).

---

## 5. Handoff humano para agendamiento manual

**Patrón:** Lead pide un horario que no aparece en Calendly (típico: sábados, horarios fuera de la disponibilidad estándar). El sistema escala al humano para crear el evento manualmente.

**Acción cuando recibes los datos (email + teléfono) del lead:**

❌ **NO prometas** "te enviamos la confirmación al correo en las próximas horas" si el agendamiento depende de acción humana — eso compromete una entrega que no controlas.

✅ **Mejor:**

```
¡Perfecto, [Nombre]! 🙌

Listo, te confirmo por aquí mismo en cuanto el espacio quede creado en mi agenda. Te llegará la invitación a [email] apenas esté.

Mientras tanto, te dejo un par de preguntas para que aprovechemos los 30 minutos al máximo:

¿Cuál es tu estimado total de créditos actualmente?
¿Hay algo específico que quisieras que yo entienda sobre tus objetivos o expectativas?

¡Nos vemos en la llamada!
```

Marca `handoff_humano: true` con `razon_handoff: "agendamiento_manual_pendiente"` para que el humano sepa que debe crear el evento.

### Cuando el humano ya agendó manualmente

Retoma con esta secuencia (validada con Has Walteros):

```
Listo [Nombre], te envié la invitación, cuéntame por fa si te llegó.
```

**Si responde "Sí, confirmado":**
Cierra con M5.5.d (blindaje del show-up):
```
Buenísimo. A ti, gracias [Nombre].

Permíteme hacerte la última pregunta: ¿de aquí al [día agendado] puede pasar algo que haga que no asistas, o estamos súper firmes?
```

**Si responde "No me llegó":**
```
Déjame verificar — ¿me confirmas tu correo nuevamente para revisar? A veces se va a spam o promociones.
```

---

## 6. Respuesta a "Gracias" después del cierre (M5.5.d)

**Patrón:** Lead agradece tras recibir preguntas pre-llamada.

**Acción:** Respuesta **breve, cálida** + **pregunta de blindaje del show-up** si aún no la enviaste.

Si ya la enviaste en un turno anterior, solo una línea cálida:
```
¡A ti, [Nombre]! 🙌
```

Ver M5.5.d completo en `scripts/m5-5-confirmacion-post-calendly.md`.

---

## 7. Tuteo colombiano: caso real de voseo filtrado (21 may 2026)

**Patrón:** El agente envió M3 a Daniel Meza ("ese perfil es justo el que más trabajo... ya estás en una capa donde el problema rara vez es cuánto entra, sino cómo se está moviendo todo") y M4 a Dario Daniel Montenegro ("Ese dolor es justo el más común en gente como vos... ¿esto es algo que querés resolver YA?") usando voseo: "vos", "querés", "sabés", "tenés".

**Problema:** Esto rompe la identificación con el avatar colombiano. Andrés es colombiano y nunca usaría voseo.

**Acción correctiva permanente (ya integrada):**
- `knowledge-base/04-voz-y-tono.md` incluye Regla #2 (tuteo colombiano estricto) con prohibidos/permitidos explícitos.
- "NO haces" incluye "NUNCA uses voseo ni argentinismos".
- Aunque el lead escriba en voseo, TÚ mantienes tuteo colombiano.

**Cómo evitarlo:** antes de enviar cualquier mensaje, verificar mentalmente que no hay "vos / sabés / querés / tenés / podés / sentís / andás" en el texto. Si los hay, reescribir.

---

## 8. Protocolo operativo: leer el prompt ANTES de cada ronda de DMs

**Regla operativa:** todo operador (humano o IA) que ejecute rondas de respuestas debe leer el prompt/proyecto completo **al inicio de cada ronda**, no confiar en memoria de sesión.

**Por qué:** los aprendizajes nuevos se integran en caliente (como la Regla #2 del 21-may-2026). Si arrancas la ronda desde memoria de sesiones previas, vas a aplicar reglas obsoletas.

**Acción:** al inicio de cada ronda, `Read` el CLAUDE.md de este proyecto antes de tipear el primer mensaje.

---

## 9. Protocolo del Setter humano/IA operando IG directamente — VERIFICACIÓN DEL HEADER

> **⚠️ NOTA CRÍTICA:** este aprendizaje se ha repetido **3 veces el 2026-05-22**. El protocolo extendido vive ahora en su propio SOP: `sops/sop-06-protocolo-anti-error-click.md`. Léelo antes de operar.

Esta sección aplica al humano o IA que ejecuta el flujo en Instagram (no al modelo de IA generando JSON).

### Por qué pasa el error
En Instagram, cuando un lead responde, su chat **sube en la lista**. Si haces click en una coordenada fija pensando que es un chat específico, terminas en otro chat distinto. Durante operación intensa la lista se reordena entre cada click.

### REGLA — Patrón de verificación obligatorio
**ANTES de cada click de navegación:**
1. Screenshot fresco del inbox.
2. Leer el nombre del lead objetivo Y su posición visual EN ese screenshot.
3. Click en esa coordenada exacta.

**DESPUÉS del click y ANTES de tipear:**
4. Screenshot fresco.
5. Leer el header del panel derecho (nombre del lead).
6. SI header coincide con el objetivo → proceder a tipear.
7. SI header NO coincide → ABORTAR, volver al inbox, buscar de nuevo.

**Recomendación operativa fuerte:** cuando la lista se haya reordenado >5 veces en la ronda, usar el **campo de búsqueda** del inbox para encontrar al lead por nombre — elimina el riesgo de reordenamiento.

### REGLA — Si por error envías mensaje a chat equivocado
- Pide disculpa breve y honesta en ese chat:
  ```
  Disculpa [Nombre], ese mensaje anterior se fue por error a tu chat 🙊
  ```
- Vuelve al inbox y busca el chat correcto **por nombre** (no por coordenada).
- Verifica el header antes de tipear de nuevo.
- NO escales a humano por este motivo — es error operativo, no del flujo.

### REGLA — Link de Calendly necesita doble Return en algunos clientes
- Cuando envías el link como último chunk, Instagram a veces deja el texto en el cuadro de envío sin disparar el send.
- Después del Return inicial, espera ~1 segundo, toma screenshot, y si ves el link aún en el cuadro de envío, presiona Return otra vez.

### Incidentes históricos (registro de errores reales)
| Fecha | Operador | Lead esperado | Lead equivocado |
|---|---|---|---|
| 2026-05-22 R1 | Setter IA | Xiomara | Juliana (salvado por verificación de header — no se envió mensaje) |
| 2026-05-22 R4 | Setter IA | Vanessa Hoyos | Gabriel Torres (mensaje enviado, disculpa enviada) |
| 2026-05-22 R4 | Setter IA | Vanessa López Suaza | Gabriel Torres (2da vez en la misma ronda — mismo patrón) |

Después del 3er error en el mismo día, se creó `sops/sop-06-protocolo-anti-error-click.md` con el patrón estricto obligatorio.

---

## Cómo agregar nuevos aprendizajes

Cuando detectes un patrón nuevo en producción:

1. Documéntalo aquí siguiendo el formato:
   - **Patrón:** qué pasó
   - **Trampa común:** por qué se confunde
   - **Acción:** qué hacer
   - **Ejemplo:** texto literal si aplica

2. Si requiere ajuste de regla en el flujo principal, actualiza el archivo afectado en `scripts/` o `knowledge-base/`.

3. Si requiere ajuste del prompt monolítico, actualiza también `/Users/javiersuarez/Documents/ARTF + C&J/ARTF + C&J/Setter IA/Prompt-Agente-Setter-IA-Instagram.md`.

4. Anota la fecha del aprendizaje en este archivo para tener traza histórica.
