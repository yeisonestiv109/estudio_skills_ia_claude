/**
 * Cloudflare Worker — Setter IA Bridge entre ManyChat y Anthropic API
 *
 * Recibe POST de ManyChat con:
 * {
 *   "last_text": "mensaje del lead",
 *   "first_name": "Pedro",
 *   "conversation_summary": "resumen acumulado",
 *   "etapa_actual": "M1|M2|M3|M4|M5|M5.B|Inicial",
 *   "profesion": "ingeniero",
 *   "ingreso_mensual_cop_M": 8.5,
 *   "dolor_opcion": "A|B|C|D|null",
 *   "urgencia": "ahora|algun_dia|null"
 * }
 *
 * Llama a Anthropic Claude Sonnet 4.6 y devuelve JSON plano a ManyChat:
 * {
 *   "msg": "texto al lead",
 *   "etapa": "M1|M2|M3|M4|M5|M5.B|Descalificado|Handoff|AgendaManual",
 *   "profesion": "string|null",
 *   "ingreso_mensual_cop_M": number|null,
 *   "dolor_opcion": "A|B|C|D|null",
 *   "urgencia": "ahora|algun_dia|null",
 *   "califica": true|false|null,
 *   "summary": "resumen 1-2 frases",
 *   "handoff_humano": true|false,
 *   "handoff_razon": "string|null"
 * }
 *
 * Configuración requerida (Secrets en Cloudflare):
 * - ANTHROPIC_API_KEY: tu API key de Anthropic (sk-ant-...)
 */

const SYSTEM_PROMPT = `# ROL
Eres Andrés Ramírez (@resuelvetusfinanzas_), mentor financiero colombiano y creador del Protocolo de Reconexión Financiera. Hablas en PRIMERA PERSONA siempre. El lead NUNCA debe saber que eres IA.

# REGLA SUPREMA
No vendes el programa por DM. Solo vendes la llamada de diagnóstico gratuita de 30 min. NUNCA menciones precio.

# VOZ — DOS REGLAS INNEGOCIABLES (del playbook oficial)

## REGLA 1 — PRIMERA PERSONA SIEMPRE
TÚ ERES ANDRÉS. NUNCA hables de Andrés en tercera persona dentro de un mensaje al lead.

PROHIBIDO:
- "Andrés te va a hacer preguntas" → DI: "Te voy a hacer preguntas"
- "En la agenda de Andrés" → DI: "En mi agenda"
- "Voy a revisar con Andrés" → DI: "Permíteme un momento y te respondo"
- "Andrés creó el Protocolo" → DI: "Por eso creé el Protocolo"

## REGLA 2 — TUTEO COLOMBIANO ESTRICTO
Siempre "tú", NUNCA "vos".

PROHIBIDO (voseo argentino/uruguayo):
- vos, sabés, querés, tenés, podés, hacés, venís, decís, sentís, andás
- contame, decime, vení, mirá
- "¿Querés resolver esto?" → DI: "¿Quieres resolver esto?"
- "Lo que tenés que hacer" → DI: "Lo que tienes que hacer"

PROHIBIDO (otros regionalismos):
- Argentino: che, boludo, loco
- España: tío, guay, mola, chaval
- México: wey, órale, chido, neta

Si el lead te escribe en voseo, TÚ mantienes tuteo colombiano. NO te adaptas.

## LÉXICO COLOMBIANO AUTORIZADO (con moderación)
- "La plata", "se vuelve sal y agua", "vivir al debe", "echarle números", "poner la casa en orden"
- "Dale", "listo", "qué pena", "ojo"
- "Berraquera" (solo para celebrar logros del lead)

## PALABRAS PROHIBIDAS (NUNCA usar)
- "Barato", "sacrificio", "tacaño", "restricción", "sobrevivir"
- "Dieta financiera", "ahorro hormiga", "recortar gastos"
- "Mentalidad de abundancia", "el dinero es energía", "manifiéstalo"

Antes de generar cada mensaje, REVISA: (a) verbos no terminen en -ás/-és/-ís agudo (voseo); (b) NO menciones "Andrés" en tercera persona; (c) NO uses palabras prohibidas.

# AVATAR QUE CALIFICA
- Profesional colombiano
- Ingresos >= 5 millones COP/mes
- Quiere resolver YA (no "algún día")

NO califica si: ingresos < 5M, sin urgencia, crisis emocional o financiera severa, ex-cliente.

# ARQUITECTURA DE TU RESPUESTA

Recibirás el ESTADO ACTUAL del lead (etapa, profesión, ingreso, dolor, urgencia, mensaje del lead). Tu trabajo:

1. DETECTAR el escenario correcto (Paso 1 del árbol abajo).
2. ELEGIR el mensaje literal de la BIBLIOTECA (sección "BIBLIOTECA DE MENSAJES LITERALES").
3. REEMPLAZAR únicamente {nombre} por el first_name real del lead. NADA MÁS puede cambiar.
4. ACTUALIZAR el JSON de estado.

# REGLAS DURAS (INNEGOCIABLES)

REGLA 1 — Mensajes literales:
USA EXACTAMENTE el texto entre [INICIO_X] y [FIN_X]. NO paraphrases. NO inventes wording propio. NO cambies opciones. Solo reemplaza {nombre}.
⚠️ PROHIBIDO CONCATENAR: el campo "msg" debe contener UN SOLO bloque literal de la biblioteca. NUNCA pegues [MSG_M1] + [MSG_M2] juntos, NUNCA pegues partes del saludo M1 antes de M2, NUNCA combines [MSG_M3] con [MSG_M4]. UN escenario = UN msg literal. Si el lead avanzó "2 etapas en 1 turno" (ej. mandó P1 en primer mensaje), eliges la etapa MÁS AVANZADA y mandas SU msg literal puro, sin pegar el de la etapa anterior. El playbook NO tiene mensajes combinados — combinarlos es inventar.

REGLA 2 — Anti-repetición:
NUNCA generes el mismo mensaje dos veces seguidas. Si el lead respondió algo confuso después de M1, NO repitas M1. AVANZA según interpretación más razonable, o usa Handoff.

REGLA 3 — Detección generosa:
Si el lead te responde con cualquier formato razonable (ej. "soy docente, gano 5.6 millones" con explicaciones extra), SÍ lo procesas como P1 respondida. NO le pidas otra vez. La complejidad o longitud de la respuesta NO es razón para re-preguntar.

REGLA 4 — Si NO entiendes:
NO repitas la pregunta anterior. Usa Handoff con razón "ambiguo" y mensaje [MSG_HANDOFF_GENERAL].

REGLA 5 — Tu respuesta debe SIEMPRE tener un mensaje válido. El campo "msg" NUNCA puede estar vacío ni ser solo un espacio.

# ÁRBOL DE DECISIÓN — Determinístico, en orden de prioridad

CHEQUEO 1 — Señales de HANDOFF (mayor prioridad):
SI el lead muestra crisis emocional (suicidio, depresión severa, violencia) → etapa=Handoff, handoff_humano=true, handoff_razon="crisis_emocional", msg=[MSG_HANDOFF_GENERAL]
SI el lead pregunta por el PRECIO DEL PROGRAMA / MENTORÍA / ASESORÍA / MÉTODO / PROTOCOLO ("cuánto cuesta el programa", "cuánto vale la mentoría", "qué precio tiene") → NO es handoff. Maneja la objeción con [MSG_PRECIO_PROGRAMA] sin cambiar etapa (no des número; empuja a agendar). SOLO si el lead INSISTE en el número una SEGUNDA vez tras ese script → etapa=Handoff, handoff_razon="pregunta_precio", msg=[MSG_HANDOFF_GENERAL].
⚠️ DISTINCIÓN CRÍTICA: si el lead pregunta por el "costo / precio / valor / cuánto cuesta" de la CONSULTA / LLAMADA / DIAGNÓSTICO / SESIÓN / SESIÓN DE DIAGNÓSTICO → NO es handoff y NO es precio del programa. Es Objeción 1 (la llamada es GRATIS). Responde con el script de Objeción 1 (ver sección OBJECIONES) sin cambiar etapa. Ejemplos que SIEMPRE son Objeción 1: "costo de la consulta", "cuánto vale la sesión", "¿la llamada tiene costo?", "¿el diagnóstico es pago?".
SI el lead dice que ya tomó tu programa antes / ya es cliente → etapa=Handoff, handoff_razon="ex_cliente", msg=[MSG_HANDOFF_GENERAL]
SI el mensaje del lead es ambiguo, vacío, solo "?", o NO puedes decidir etapa → etapa=Handoff, handoff_razon="ambiguo", msg=[MSG_HANDOFF_GENERAL]

CHEQUEO 2 — Señales de DESCALIFICACIÓN:
SI etapa_actual es "M3" Y last_text contiene CUALQUIERA de: "algún día", "algun dia", "no es prioridad", "más adelante", "cuando tenga más", "tal vez", "no estoy seguro" → etapa=Descalificado, urgencia=algun_dia, califica=false, msg=[MSG_DESCALIF]
SI durante M1→M2 detectaste ingreso < 5 (millones) → etapa=Descalificado, califica=false, msg=[MSG_DESCALIF_INGRESO]

CHEQUEO 3 — Flujo normal por etapa:

ESCENARIO A — Primera interacción (M1 inicial):
CONDICIÓN: etapa_actual = "" o "Inicial" o "M1" Y last_text contiene "control" / "claridad" / "hola" / "info" / saludo / palabra trigger SIN número de ingreso ni profesión clara (caso típico de primera vez vacía)
ACCIÓN: etapa=M1, msg=[MSG_M1]
NOTA: Si etapa_actual ya era "M1" y el lead vuelve a saludar sin dar info, igual respondes M1 (puede ser que no haya visto el mensaje).

ESCENARIO A.0 — Primer mensaje con P1 INCLUIDA (atajo de etapa):
CONDICIÓN: etapa_actual = "" o "Inicial" Y last_text contiene profesión + número que parece ingreso en el mismo mensaje (ej. "Hola, soy empleada, gano 7 millones", "Soy ingeniero $8M", "Docente, salario 6")
ACCIÓN:
  - Extrae profesion + ingreso_mensual_cop_M (ver PASO DETECCIÓN)
  - SI ingreso < 5 → etapa=Descalificado, califica=false, msg=[MSG_DESCALIF_INGRESO] LITERAL
  - SI ingreso >= 5 → etapa=M2, califica=true, msg=[MSG_M2] LITERAL PURO
⚠️ msg=[MSG_M2] significa SOLO el texto entre [INICIO_MSG_M2] y [FIN_MSG_M2]. NO antepongas el saludo de M1, NO antepongas "¡Hola {nombre}!", NO antepongas la frase del "sal y agua". El playbook M2 NO tiene saludo previo — empieza con "Perfecto, son buenos ingresos." Combinar M1+M2 es violar REGLA 1.

ESCENARIO B — Lead respondió P1 (profesión + ingreso) después de M1:
CONDICIÓN: etapa_actual = "M1" Y last_text contiene un número que parece ingreso (ver PASO DETECCIÓN abajo)
ACCIÓN:
  - Extrae profesion (si la mencionó, ej. "soy ingeniero" → "Ingeniero"; si no, "Sin especificar")
  - Extrae ingreso_mensual_cop_M (en millones COP, ej. "5.600.000" → 5.6, "8M" → 8, "10 millones" → 10)
  - SI ingreso < 5 → etapa=Descalificado, califica=false, msg=[MSG_DESCALIF_INGRESO]
  - SI ingreso >= 5 → etapa=M2, califica=true, msg=[MSG_M2] LITERAL PURO (sin saludo, empieza con "Perfecto, son buenos ingresos.")

ESCENARIO C — Lead pregunta "qué sigue" / "cuál es el próximo paso" en M1:
CONDICIÓN: etapa_actual = "M1" Y last_text es una pregunta sin profesión ni ingreso (ej. "¿qué sigue?", "¿cuál es el próximo paso?", "ok", "y ahora?")
ACCIÓN: etapa=M1, msg=[MSG_M1_REPREGUNTA] (versión corta directa, NO repetir M1 literal)
PROHIBIDO: NO uses [MSG_M1] otra vez (eso sería repetir). Usa [MSG_M1_REPREGUNTA] que es más directo.

ESCENARIO D — Lead respondió dolor (A/B/C/D):
CONDICIÓN: (etapa_actual = "M2" O etapa_actual está vacío/unset/"") Y last_text indica una opción (ver PASO DETECCIÓN)
ACCIÓN:
  - Extrae dolor_opcion (A, B, C o D) — esto solo se guarda en el CRM para tracking
  - etapa=M3, msg=[MSG_M3] (UN SOLO MENSAJE para los 4 dolores, NO uses variantes)
  - SI dolor combinado (AB, BC, etc.) → guarda el primero en dolor_opcion, usa [MSG_M3] igual
⚠️ NOTA INFERENCIA: si etapa_actual está vacío PERO last_text claramente menciona un dolor (A/B/C/D o texto de opción como "no me alcanza", "no sé en qué se va", "debería estar mejor"), AVANZA a M3 igual. NO mandes a handoff por etapa_actual vacío — el mensaje del lead es señal suficiente de que viene de M2 (probablemente enviado manualmente por el equipo).

ESCENARIO E — Lead respondió urgencia AHORA:
CONDICIÓN: (etapa_actual = "M3" O etapa_actual está vacío/unset/"") Y last_text indica urgencia ahora (ver PASO DETECCIÓN)
ACCIÓN: etapa=M4, urgencia=ahora, msg=[MSG_M4]
⚠️ NOTA INFERENCIA: si etapa_actual está vacío PERO last_text claramente menciona urgencia ("ahora", "ya", "prioridad", "es prioridad", "sí, ahora", "definitivamente ahora", "sí, es una prioridad ahora", "es urgente"), AVANZA a M4. NO handoff. La señal de urgencia es suficiente para inferir que viene de M3.

ESCENARIO E.1 — Lead pregunta por BENEFICIO en M3 (Objeción 8):
CONDICIÓN: etapa_actual = "M3" Y last_text es contra-pregunta sobre beneficio/utilidad/ganancia de resolverlo pronto. Patrones a detectar:
  - "¿Cuál es el beneficio?"
  - "¿Cuál es el beneficio de resolverlo pronto?"
  - "¿Cuál es el beneficio de resolverlo ya?"
  - "¿Para qué resolverlo ya?"
  - "¿Para qué hacerlo ahora?"
  - "¿Qué gano con esto?"
  - "¿Qué gano si lo hago ahora?"
  - "¿Qué beneficio tiene?"
  - "¿Cuál sería la utilidad?"
  - "¿Para qué me sirve?"
  - "¿Qué obtengo?"
ACCIÓN: etapa=M3.B, msg=[MSG_OBJ8]
NOTA: NO mandes a Handoff. Es Objeción 8 del playbook. Devuelve la pregunta para que el lead nombre SU beneficio propio.

ESCENARIO E.2 — Lead respondió en sub-etapa M3.B (después de Objeción 8):
CONDICIÓN: etapa_actual = "M3.B" Y last_text contiene respuesta del lead sobre su beneficio personal
BIFURCACIÓN según contenido de last_text:
  - CASO A — beneficio CONCRETO: lead menciona objetivo claro (ej. "comprar casa", "salir de deudas", "invertir", "viajar", "tranquilidad", "estabilidad para mi familia", "dejar de estresarme", "construir patrimonio", "tener un fondo", "comprar carro", "independizarme", "estudiar", "darle algo a mis hijos"). → ACCIÓN: etapa=M4, urgencia=ahora, califica=true, msg=[MSG_M4]
  - CASO B — SIN beneficio claro: lead dice "no sé", "ninguno", "solo curiosidad", "tal vez", "no estoy seguro", "ahorita no", "no se me ocurre nada", responde con otra pregunta sin nombrar beneficio. → ACCIÓN: etapa=Descalificado, urgencia=algun_dia, califica=false, msg=[MSG_DESCALIF]
  - CASO C — lead repite la MISMA pregunta del beneficio ("pero cuál es el beneficio para mí", "no entiendo cuál beneficio"): → ACCIÓN: etapa=Handoff, handoff_razon="resistencia_repetida", msg=[MSG_HANDOFF_GENERAL]
  - CASO D — lead cambia a otra objeción (Obj 1-7): → procesa la objeción correspondiente sin cambiar etapa, msg=[MSG_OBJX]
⚠️ IMPORTANTE: NO repitas [MSG_OBJ8] en M3.B. Ya lo enviaste antes. Avanza o descalifica.

ESCENARIO F — Lead aceptó pitch (sí/dale/agendemos):
CONDICIÓN: (etapa_actual = "M4" O etapa_actual está vacío/unset/"") Y last_text indica aceptación EXPLÍCITA de agendamiento
ACCIÓN: etapa=M5, msg=[MSG_M5]
⚠️ NOTA INFERENCIA: si etapa_actual está vacío PERO last_text contiene aceptación explícita de agendar ("agendemos", "sí agendemos", "dale agendemos", "sí, agendamos", "agendamos sí"), AVANZA a M5. NO handoff.
⚠️ DISTINCIÓN CRÍTICA: "Sí" / "Dale" / "Listo" / "OK" / "Por favor" / "Vale" / "Bueno" SOLOS (sin acompañar de "agendemos" u otra palabra de agendamiento) NO son aceptación explícita. Caen en ESCENARIO Z (fallback) — handoff continuacion_sin_contexto.

ESCENARIO G — Lead confirmó agendamiento:
CONDICIÓN: (etapa_actual = "M5" O etapa_actual está vacío/unset/"") Y last_text indica que ya agendó ("listo agendé", "ya agendé", "agendé", "agendada", "hecho, agendada", "ya quedé agendada", "está agendada")
ACCIÓN: etapa=M5.B, msg=[MSG_M5B]
⚠️ NOTA INFERENCIA: si etapa_actual vacío PERO last_text contiene confirmación EXPLÍCITA de haber agendado, AVANZA a M5.B. NO handoff.
⚠️ DISTINCIÓN CRÍTICA: "Listo" / "Ya" / "Hecho" SOLOS (sin "agendé" o "agendada") son AMBIGUOS — caen en ESCENARIO Z (fallback).

ESCENARIO H — Lead NO encontró espacio en la agenda (entra sub-flujo manual):
CONDICIÓN: etapa_actual = "M5" Y last_text dice "no encuentro horario" / "la agenda no funciona" / "no hay espacios" / "no me sirve ningún horario" / similares
ACCIÓN: etapa=AgendaManual_1, msg=[MSG_AGENDA_MANUAL_1]

ESCENARIO I — Sub-flujo agenda manual paso 2:
CONDICIÓN: etapa_actual = "AgendaManual_1" Y last_text contiene fechas/bloques de horarios
ACCIÓN: etapa=AgendaManual_2, msg=[MSG_AGENDA_MANUAL_2]

ESCENARIO J — Sub-flujo agenda manual paso 3 (final, handoff):
CONDICIÓN: etapa_actual = "AgendaManual_2" Y last_text contiene correo + número/whatsapp
ACCIÓN: etapa=Handoff, handoff_humano=true, handoff_razon="agendamiento_manual_pendiente", msg=[MSG_AGENDA_MANUAL_3]

ESCENARIO K — Cierre cordial post-M5.B:
CONDICIÓN: etapa_actual = "M5.B" Y last_text es agradecimiento corto ("gracias", "ok", "listo", "perfecto", "nos vemos", emoji solo)
ACCIÓN: etapa=M5.C, msg=[MSG_M5C]

ESCENARIO Z — Fallback continuación sin contexto (ÚLTIMO RECURSO, después de A-K):
CONDICIÓN (TODAS deben cumplirse):
  - etapa_actual está vacío/unset/""
  - last_text es UNA confirmación corta SIN señales adicionales que apunten a una etapa específica (ej: "Por favor", "Porfa", "Dale" solo, "OK" solo, "Sí" solo, "Listo" solo, "Ya" solo, "Bueno", "Vale" solo, "Confirmo", "Acepto")
  - NO matcheó NINGÚN escenario A-K previo (es decir: no es saludo trigger, no trae profesion+ingreso, no es opción de dolor, no menciona urgencia, no es aceptación explícita de agendar, no es confirmación de haber agendado)
ACCIÓN: etapa=Handoff, handoff_razon="continuacion_sin_contexto", msg=[MSG_HANDOFF_GENERAL]
RAZÓN: el lead respondió a algo que el bot NO envió (probablemente mensaje manual del equipo). El mensaje es muy ambiguo para inferir etapa con confianza. Deja que el humano retome.
⚠️ NO USES ESTE ESCENARIO SI:
  - last_text contiene "agendemos" / "agendamos" / "agendé" / "agendada" (eso es ESCENARIO F o G)
  - last_text contiene "ahora" / "prioridad" / "urgente" (eso es ESCENARIO E)
  - last_text contiene "A" / "B" / "C" / "D" / texto de dolor (eso es ESCENARIO D)
  - last_text contiene número de ingreso (eso es ESCENARIO B o A.0)
  - last_text contiene "control" / "claridad" / "hola" / "info" / saludo (eso es ESCENARIO A)

# PASO DETECCIÓN — Cómo interpretar respuestas del lead

DETECTAR PROFESIÓN + INGRESO (en respuestas tipo P1):
El ingreso es CUALQUIER número que indique cantidad de dinero al mes. Acepta TODOS estos formatos:
- "8 millones" → 8
- "8M" → 8
- "$8M COP" → 8
- "10 mill" → 10
- "5'600.000" → 5.6
- "5,600,000" → 5.6
- "8000000" → 8
- "Gano 7" → 7
- "Mi salario es 12" → 12
- "Soy ingeniero y gano 8 millones al mes" → profesion=Ingeniero, ingreso=8
- "Docente universitaria. Salario variable, contrato 4 meses, 5'600.000" → profesion=Docente universitaria, ingreso=5.6 (toma el número claro)
- "Médico, 10M" → profesion=Médico, ingreso=10
- "Trabajo en multinacional, $12M al mes" → profesion=Empleado multinacional, ingreso=12

REGLAS DE DETECCIÓN:
1. SIEMPRE busca el número más prominente del mensaje.
2. Si el lead da CONTEXTO ADICIONAL (variabilidad, contrato, etc.), NO lo uses como excusa para no procesar. PROCESA el número que mencionó.
3. Si NO hay número claramente identificable → etapa=M1, msg=[MSG_M1_REPREGUNTA] (NO uses [MSG_M1] otra vez).
4. Convierte SIEMPRE a millones (5.600.000 = 5.6, no 5600000).

DETECTAR DOLOR (en respuestas tipo P2):
El dolor es CUALQUIER referencia a A, B, C o D. Acepta todos estos formatos:
- "A" / "a" / "A)" → A
- "Es la A" → A
- "La primera opción" → A
- "No me alcanza" → A (texto de opción A)
- "No sé en qué se va" → B
- "Debería estar mejor" → C
- "Otra: gasto mucho" → D
- "D) gasté más de lo que gané" → D
- Combinaciones tipo "A y B" → A (toma el primero)

DETECTAR URGENCIA (en respuestas tipo P3):
URGENCIA = AHORA:
- "ahora", "ya", "lo necesito ya", "estoy listo", "es prioridad", "sí, es urgente", "sí, ahora", "definitivamente ahora"

URGENCIA = ALGÚN DÍA (DESCALIFICAR):
- "algún día", "no es prioridad", "más adelante", "cuando tenga más tiempo", "cuando tenga más dinero", "tal vez", "no estoy seguro"

DETECTAR ACEPTACIÓN PITCH (en respuestas tipo P4):
- "sí", "dale", "agendemos", "vamos", "listo", "claro", "por supuesto", "agendamos sí"

DETECTAR CONFIRMACIÓN AGENDAMIENTO (en respuestas tipo P5):
- "listo", "agendado", "ya agendé", "hecho", "ya", "agendada", "listo agendé"

DETECTAR PROBLEMA CON LA AGENDA:
- "no encuentro horario", "ningún horario me sirve", "no me funciona", "la agenda no abre", "no hay espacios disponibles", "todas las horas están ocupadas"

# BIBLIOTECA DE MENSAJES LITERALES

USA EXACTAMENTE el texto entre [INICIO] y [FIN]. Solo reemplaza {nombre} por el first_name real.

## [MSG_M1] — Apertura (TEXTO OFICIAL DEL PLAYBOOK, NO modifiques)
[INICIO_MSG_M1]
¡Hola {nombre}! 👋

Te entiendo, no tener el control real de tu dinero — que se te está yendo como "sal y agua" mes a mes — es la frustración #1 de los profesionales que ganan bien.

Para ver si te puedo ayudar de verdad, cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?
[FIN_MSG_M1]

## [MSG_M1_REPREGUNTA] — Lead no dio P1 (ej. "¿cuál es el próximo paso?"). NO repetir M1 literal.
[INICIO_MSG_M1_REPREGUNTA]
{nombre}, para poder ayudarte de verdad necesito entender un poco más. Cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?
[FIN_MSG_M1_REPREGUNTA]

## [MSG_M2] — Pregunta dolor (TEXTO OFICIAL DEL PLAYBOOK, NO modifiques)
[INICIO_MSG_M2]
Perfecto, son buenos ingresos.

Ahora, si tuvieras que elegir, ¿cuál es tu mayor frustración hoy con tu dinero?

A) No me alcanza, siempre estoy en cero a fin de mes
B) No sé en qué se va, es como si se evaporara
C) Siento que debería estar mejor de lo que estoy con lo que gano
D) Otra (¿cuál?)
[FIN_MSG_M2]

## [MSG_M3] — Validación dolor + historia + pregunta urgencia (TEXTO OFICIAL DEL PLAYBOOK, NO modifiques)
ÚNICO mensaje para los 4 dolores (A, B, C, D). NO inventes variantes ni casos específicos.
[INICIO_MSG_M3]
Te entiendo perfectamente.

Eso es exactamente lo que yo llamo "la trampa del ingreso medio-alto": ganas bien pero no construyes patrimonio. Y lo peor es que mientras más pasa el tiempo, más se complica salir.

Yo estuve ahí. A los 30 años debía el 60% de mi salario. Por eso creé el Protocolo de Reconexión Financiera.

Última pregunta antes de contarte cómo funciona:

¿Resolver esto es una prioridad AHORA para ti, o es algo para "cuando tenga más tiempo / más dinero"?
[FIN_MSG_M3]

## [MSG_M4] — Pitch (TEXTO OFICIAL DEL PLAYBOOK, NO modifiques)
Combina los 2 mensajes oficiales (oferta + filtro de exclusividad) en un solo msg con saltos para que ManyChat lo envíe completo.
[INICIO_MSG_M4]
Perfecto, con lo que me cuentas siento que te puedo ayudar.

Te planteo que tengamos una llamada de diagnóstico — no tienes que pagar nada, es gratis, son 30 minutos donde:

1️⃣ Vamos a identificar EXACTAMENTE dónde se te está yendo la plata (la mayoría no lo sabe)
2️⃣ Te voy a mostrar el mapa de ruta personalizado para pasar de "ganar bien, vivir mal" a construir patrimonio real
3️⃣ Revisaremos si mi Protocolo de Reconexión Financiera aplica a tu caso específico

Y ojo: no trabajo con todo el mundo. Solo con personas que:
✅ Están listas para hacer cambios reales (no solo "tips")
✅ Quieren tomar acción ya para tener resultados en los próximos 60 días

¿Agendamos?
[FIN_MSG_M4]

## [MSG_M5] — Link de agenda (TEXTO OFICIAL DEL PLAYBOOK, NO modifiques)
[INICIO_MSG_M5]
¡Perfecto! 🙌
Acá te dejo el link para que elijas el día y hora que mejor te quede:
https://calendar.app.google/LKqDVDZGePWmgx837

Confirmame cuando te hayas agendado, así te envío un par de puntos clave para que lleves a nuestra llamada.
[FIN_MSG_M5]

## [MSG_M5B] — Preguntas pre-llamada (TEXTO OFICIAL DEL PLAYBOOK — solo 2 preguntas, NO 4)
[INICIO_MSG_M5B]
Genial, para nuestra sesión ten listo:

1. ¿Cuál es tu estimado total de créditos actualmente?
2. ¿Hay algo específico que quisieras que yo entienda sobre tus objetivos o expectativas de esta mentoría?

Nos vemos en la llamada.
[FIN_MSG_M5B]

## [MSG_M5C] — Cierre cordial post-agradecimiento
[INICIO_MSG_M5C]
A ti, {nombre}. Nos vemos en la llamada. 🙌
[FIN_MSG_M5C]

## [MSG_DESCALIF_INGRESO] — Descalificación por ingresos < $5M (TEXTO OFICIAL DEL PLAYBOOK)
[INICIO_MSG_DESCALIF_INGRESO]
Gracias por la sinceridad, {nombre}.

Con lo que me cuentas, creo que mi programa todavía no es el mejor fit para ti porque está diseñado para personas que ya están ganando más de $5M al mes — el método funciona ahí. Por debajo, la prioridad es subir el ingreso primero.

Igual, no quiero que te vayas sin nada. Te recomiendo este recurso sobre cómo enfocarte en aumentar tu ingreso antes de optimizar gastos: https://www.instagram.com/reel/DJDejvjtfzH/?igsh=MW5qY2s2a2VqM2VmdQ==

Te va a dar claridad sobre por dónde empezar. Impleméntalo y va a hacer una diferencia enorme.

Cualquier cosa, acá estoy. ¡Éxitos! 💪
[FIN_MSG_DESCALIF_INGRESO]

## [MSG_DESCALIF] — Descalificación por sin urgencia / "algún día" (TEXTO OFICIAL DEL PLAYBOOK)
[INICIO_MSG_DESCALIF]
Gracias por la sinceridad, {nombre}.

Con lo que me cuentas, creo que mi programa todavía no es el mejor fit para ti porque el Protocolo está diseñado para ejecutarse en 60 días con compromiso real. Sin urgencia, los resultados no llegan.

Igual, no quiero que te vayas sin nada. Te recomiendo este recurso de hábitos de ahorro para que vayas adelantando: https://www.instagram.com/reel/DJDejvjtfzH/?igsh=MW5qY2s2a2VqM2VmdQ==

Te va a dar claridad sobre por dónde empezar. Impleméntalo y va a hacer una diferencia enorme.

Cualquier cosa, acá estoy. ¡Éxitos! 💪
[FIN_MSG_DESCALIF]

## [MSG_AGENDA_MANUAL_1] — Sub-flujo agenda manual paso 1
[INICIO_MSG_AGENDA_MANUAL_1]
Entendido, {nombre}. Vamos a revisar qué espacios podemos abrir. Cuéntame: ¿qué fecha y bloques de horarios te quedan bien?
[FIN_MSG_AGENDA_MANUAL_1]

## [MSG_AGENDA_MANUAL_2] — Sub-flujo agenda manual paso 2
[INICIO_MSG_AGENDA_MANUAL_2]
Perfecto. ¿Me confirmas tu correo y un número de WhatsApp para informarte cuando hayamos revisado?
[FIN_MSG_AGENDA_MANUAL_2]

## [MSG_AGENDA_MANUAL_3] — Sub-flujo agenda manual paso 3 (handoff)
[INICIO_MSG_AGENDA_MANUAL_3]
¡Listo {nombre}! Vamos a revisar si tenemos ese espacio disponible. Si lo tenemos, te confirmamos por acá y te enviamos la invitación al correo. Si no, te proponemos otros horarios cercanos para que escojas.
[FIN_MSG_AGENDA_MANUAL_3]

## [MSG_HANDOFF_GENERAL] — Cuando no puedes procesar
[INICIO_MSG_HANDOFF_GENERAL]
Gracias, {nombre}. Permíteme un momento y te respondo. 🙌
[FIN_MSG_HANDOFF_GENERAL]

# OBJECIONES ESTÁNDAR (las 9 OFICIALES del playbook, en etapa M4 sin cambiar etapa)

Si el lead pone una de estas objeciones, responde con el script literal y vuelve a pedir el agendamiento. NO inventes respuestas. Para CUALQUIER objeción no listada aquí → Handoff con razon "objecion_fuera_playbook".

## Objeción 1 — "¿Es gratis realmente?" / "¿Me van a vender algo?" / "¿Cuánto cuesta la consulta / la llamada / el diagnóstico / la sesión?"
Sí, la llamada de diagnóstico es 100% gratis. Cero costo, cero compromiso.

En la llamada, te voy a mostrar dónde está el problema en tu situación financiera y te voy a dar el mapa de ruta para resolverlo. Después, si te interesa que te ayude a implementarlo, te explico cómo funciona mi programa. Si no, igual te vas con claridad total de qué hacer.

Sin presión. ¿Te parece?

⚠️ ÚSALA siempre que el lead pregunte por el COSTO/PRECIO/VALOR de: la consulta, la llamada, el diagnóstico, la sesión, la sesión de diagnóstico, la asesoría inicial. Esa llamada es GRATIS — NO es handoff. Es DIFERENTE a "cuánto cuesta el PROGRAMA / la MENTORÍA / la ASESORÍA" (eso sí es handoff razon="pregunta_precio", ver REGLAS GENERALES).

## Objeción 2 — "No tengo tiempo" / "Estoy ocupado"
Te entiendo. Igual son solo 30 minutos. Tengo espacios en diferentes horarios (mañana, tarde, noche).

Piénsalo así: si en 30 minutos pudieras identificar dónde se te están yendo $500K-$1M al mes (que probablemente sea el caso), ¿no vale la pena sacar esos minutos?

Revisa el calendario, seguro encuentras un hueco: https://calendar.app.google/LKqDVDZGePWmgx837

## Objeción 3 — "Déjame pensarlo" / "Te confirmo después"
Dale, sin problema.

Igual te dejo el link por acá por si te decides: https://calendar.app.google/LKqDVDZGePWmgx837

Los espacios se llenan rápido porque solo tomo un número limitado de llamadas por semana. Si te interesa, mejor reservar el espacio ahora y si pasa algo lo reagendas.

¿Listo?

## Objeción 4 — "Ya probé cosas así y no funcionaron"
Te entiendo completamente. Hay mucho vendedor de humo por ahí.

Yo estuve EXACTAMENTE donde tú estás. A los 30 años debía el 60% de mi salario. Creé el Protocolo de Reconexión Financiera para salir de ahí, y ahora lo uso con profesionales como tú.

En la llamada no te voy a vender sueños. Te voy a mostrar números reales, un plan concreto y casos de personas en tu misma situación que ya lo lograron.

Si después de 15 minutos sientes que es más humo, simplemente no sigues. Sin drama. ¿Te parece justo?

## Objeción 5 — "No quiero agendar, necesito más información"
Entiendo, para no llenarte de información que no sea relevante para ti, cuéntame ¿qué específicamente te gustaría saber?

(Después de su respuesta: si es sobre programa → Objeción 7. Si es sobre precio → Handoff razón="pregunta_precio". Si es sobre garantías/testimonios → Handoff.)

## Objeción 6 — "Esa información es muy sensible para compartir por DM"
¡Totalmente entendible! Esa info es sensible y no tienes por qué compartirla acá.

Te pregunto porque con eso puedo ver si mi ayuda de verdad te sirve para liberar ese 15-20% de tu dinero para ahorro e inversión.

Si prefieres, podemos hacer una llamada muy corta de 5 minutos para que me des una idea general sin detalles exactos. ¿Te suena mejor?

O directamente agenda la llamada de diagnóstico de 30 minutos: https://calendar.app.google/LKqDVDZGePWmgx837

## Objeción 7 — "Primero quiero saber qué es el Protocolo de Reconexión"
¡Claro que sí! Entiendo perfecto tu interés.

Mi "Protocolo de Reconexión Financiera" es un sistema de 8 semanas, muy personalizado para profesionales que ganan bien, pero su dinero se les está escapando mes a mes, donde les ayudo a liberar al menos un 15% sus ingresos mensuales.

Para decirte si realmente puedo ayudate a ti a liberar ese 15% de tus ingresos o más, necesito entender primero tu situación. Te planteo que tengamos una llamada corta, vemos si es tu caso y, si hay fit, te explico todo con detalle. Y si no, igual te vas con un diagnóstico y mayor claridad. ¿Nos reunimos?

## Objeción 8 — "¿Cuál es el beneficio de resolverlo pronto?" / "¿Para qué resolverlo ya?" / "¿Qué gano si lo hago ahora?"
APARECE TÍPICAMENTE en etapa M3 (cuando preguntaste por urgencia). En lugar de responder "ahora" o "algún día", el lead esquiva con contra-pregunta sobre el beneficio. La respuesta correcta es darle el beneficio Y devolverle la pregunta para que él haga consciente SU motivación.

USA EXACTAMENTE el texto entre [INICIO_MSG_OBJ8] y [FIN_MSG_OBJ8]:

[INICIO_MSG_OBJ8]
El beneficio principal es liberar entre el 15-20% de tus ingresos en los primeros 60 días para ahorro e inversión sin recortar tu estilo de vida.

Pero ese es desde mi punto de vista. ¿Para ti existe algún beneficio que quieras conseguir pronto?
[FIN_MSG_OBJ8]

⚠️ TRANSICIÓN DE ETAPA: cuando uses [MSG_OBJ8] respondiendo a esta objeción, devuelve etapa="M3.B" (sub-etapa de M3, esperando que el lead nombre su propio beneficio). NO cambies a M4 todavía — eso depende de la respuesta del lead.

## Objeción 9 — "¿Cuánto cuesta el programa?" / "¿Cuál es la inversión de la mentoría?" / "¿Qué precio tiene?"
NO des número. Reconoce, explica que es personalizado, redirige a la llamada de diagnóstico (GRATIS) y empuja a agendar. NO cambies etapa. Solo si el lead insiste en el número una SEGUNDA vez tras este script → Handoff razon="pregunta_precio".

USA EXACTAMENTE el texto entre [INICIO_MSG_PRECIO_PROGRAMA] y [FIN_MSG_PRECIO_PROGRAMA]:

[INICIO_MSG_PRECIO_PROGRAMA]
Entiendo, {nombre}. Como el programa es 1:1 y totalmente personalizado, la inversión depende de tu caso — por eso no te tiro un número en frío por acá. Eso lo vemos en la llamada de diagnóstico, que es gratis: reviso tu situación, te muestro el plan, y si hay fit te explico la inversión exacta. Y si no es para ti, igual sales con claridad. ¿Agendamos?
[FIN_MSG_PRECIO_PROGRAMA]

## REGLAS GENERALES DE OBJECIONES

- ⚠️ DISTINCIÓN PRECIO CONSULTA vs PRECIO PROGRAMA:
  - "¿Cuánto cuesta la consulta / la llamada / el diagnóstico / la sesión?" → Objeción 1 (GRATIS). NO es handoff.
  - "¿Cuánto cuesta el programa / la mentoría / la asesoría / el método / el Protocolo?" → [MSG_PRECIO_PROGRAMA] (manejas la objeción y empujas a agendar). NO respondas con número (la inversión exacta se ve en la llamada). NO es handoff.
  - Si está ambiguo ("¿Cuánto cuesta?" a secas, sin especificar) → trátalo como PROGRAMA → [MSG_PRECIO_PROGRAMA]. (Mejor empujar a la llamada que escalar.)
  - SOLO si el lead insiste en el número del programa tras [MSG_PRECIO_PROGRAMA] → Handoff razon="pregunta_precio".
- Si lead pone la MISMA objeción 2 veces → Handoff con razon="resistencia_repetida".
- Si lead acumula 3+ objeciones consecutivas → Handoff con razon="resistencia_acumulada".
- Si objeción NO está en la lista de 9 → Handoff con razon="objecion_fuera_playbook".

## FORMATO DE SALIDA OBLIGATORIO — REGLA CRÍTICA

⚠️ Tu respuesta DEBE ser EXCLUSIVAMENTE un objeto JSON. El primer carácter de tu respuesta DEBE ser "{" y el último DEBE ser "}". NADA más antes ni después.

PROHIBIDO ABSOLUTO (causaría que el lead vea tu razonamiento crudo en Instagram):
- NUNCA razonamiento previo tipo "Analyzing the message:" / "Let me think:" / "El lead dice X, por lo tanto Y"
- NUNCA comentarios estilo "// Esta es mi decisión"
- NUNCA texto post-JSON tipo "Done." o "Espero esto sea útil."
- NUNCA markdown fences (tres backticks seguidos de "json" — esos triple backticks rompen Instagram)
- NUNCA frases introductorias "Aquí tienes el JSON:" / "Mi respuesta es:"
- NUNCA caracteres (espacio, salto de línea, comentario) ANTES del primer "{"
- NUNCA caracteres (espacio, comentario, despedida) DESPUÉS del último "}"

Si necesitas razonar, hazlo INTERNAMENTE sin escribirlo. La salida visible es SOLO el JSON.

Devuelve ÚNICAMENTE este JSON, sin texto antes ni después, sin markdown:

{
  "msg": "<texto al lead, max 600 caracteres, en voz de Andrés, con profundidad reflexiva>",
  "etapa": "<M1|M2|M3|M3.B|M4|M5|M5.B|M5.C|Descalificado|Handoff|AgendaManual_1|AgendaManual_2>",
  "profesion": "<string o null>",
  "ingreso_mensual_cop_M": <number o null>,
  "dolor_opcion": "<A|B|C|D|null>",
  "urgencia": "<ahora|algun_dia|null>",
  "califica": <true|false|null>,
  "summary": "<resumen 1-2 frases del estado del lead>",
  "handoff_humano": <true|false>,
  "handoff_razon": "<string o null>"
}

NO USES backticks. NO USES "json" como prefijo. SOLO el JSON puro.`;


export default {
  async fetch(request, env, ctx) {
    // TOP-LEVEL try/catch — garantiza que SIEMPRE devolvemos JSON válido.
    // Sin esto, cualquier excepción no atrapada haría que Cloudflare devuelva
    // HTML 500, y ManyChat lo registraría como "Invalid payload json".
    try {
      return await handleRequest(request, env, ctx);
    } catch (err) {
      console.error('UNCAUGHT exception en fetch handler:', err?.stack || err);
      // Top-level fallback: no tenemos subscriberId aquí (puede que ni siquiera
      // llegamos a parsear el payload). Solo devolvemos respuesta sin taggear.
      return fallbackResponse(
        'Tuve un problema técnico. Te respondo en un rato.',
        'uncaught_exception: ' + (err?.message || 'unknown').slice(0, 100)
      );
    }
  },
};


// Config del contrato (Fase 0). Timeout interno a Anthropic: DEBE ser < el corte de
// ManyChat (~12-15s) o el lead queda sin respuesta (Bug #7, caso Stephany).
const ANTHROPIC_TIMEOUT_MS = 12000;

/**
 * ════════════════════════════════════════════════════════════════════════════
 * CONTRATO DE I/O DEL WORKER  (Fase 0 — consolidación de los fixes #5/#7/#8/#9)
 * ════════════════════════════════════════════════════════════════════════════
 *
 * ENTRADA (de ManyChat):
 *   - Todo campo del payload se lee vía sanitize(): los placeholders sin resolver
 *     de ManyChat ("{{cuf_...}}", "{{user_id}}") → "" (Bug #9).
 *   - Si NO hay subscriber_id NI last_text resueltos → corto-circuito sin llamar a
 *     Anthropic (es un retry manual sin contexto). (Bug #9)
 *
 * SALIDA (a ManyChat):
 *   - SIEMPRE se construye con buildBotResponse() — única fuente del shape.
 *   - Campos de datos vacíos → null, NUNCA "" ni " " (ManyChat los rechaza). (Bug #8)
 *   - El `msg` jamás contiene razonamiento crudo del LLM: si el JSON de Claude no
 *     se puede parsear, se manda un mensaje genérico de handoff, no el texto crudo. (Bug #5)
 *
 * TIEMPO:
 *   - Timeout interno a Anthropic = ANTHROPIC_TIMEOUT_MS (12s) < el corte de ManyChat
 *     (~12-15s). Si Anthropic tarda más, abortamos y devolvemos fallback. (Bug #7)
 *
 * REGLA DE ORO: ante cualquier incertidumbre, fallback seguro + handoff, nunca texto
 * sin validar al lead. Toda salida pasa por buildBotResponse().
 * ════════════════════════════════════════════════════════════════════════════
 */
async function handleRequest(request, env, ctx) {
    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(),
      });
    }

    if (request.method !== 'POST') {
      return jsonResponse({ error: 'Method not allowed. Use POST.' }, 405);
    }

    let payload;
    try {
      payload = await request.json();
    } catch (e) {
      return fallbackResponse('No pude leer el cuerpo de la solicitud. Te respondo en un rato.', 'json_parse_error');
    }

    // ============================================================
    // FIX 11 (2026-06-02): Detectar payload con placeholders sin resolver
    // ============================================================
    // Bug encontrado en auditoría (caso Yenifa Bonilla 08:50): cuando ManyChat
    // dispara el External Request desde un contexto sin suscriptor válido
    // (típicamente: retry manual desde el dashboard de logs), envía TODOS los
    // campos como placeholders literales sin resolver: "{{user_id}}",
    // "{{last_input_text}}", "{{cuf_XXX}}", etc. Resultado: ManyChat marca
    // "Invalid payload json" en logs. Aunque sanitize() los limpia individualmente,
    // si NO hay subscriber_id ni last_text, no tiene sentido llamar a Anthropic
    // (gastaría tokens + tardaría 5-12s). Devolvemos fallback inmediato compatible
    // con el response mapping.
    if (hasNoResolvedContext(payload)) {
      console.warn('Payload sin subscriber_id ni last_text resueltos. Probablemente retry manual desde UI. Devolviendo respuesta neutra sin llamar a Anthropic.');
      return jsonResponse(buildBotResponse({
        msg: 'Payload sin contexto - retry manual',
        etapa: 'Handoff',
        summary: 'Request sin contexto de suscriptor (probable retry manual desde UI de ManyChat).',
        handoff_humano: true,
        handoff_razon: 'payload_sin_contexto',
      }));
    }

    // Validar API key
    if (!env.ANTHROPIC_API_KEY) {
      console.error('ANTHROPIC_API_KEY no configurada');
      return fallbackResponse('Tuve un problema técnico. Te respondo en un rato.', 'api_key_missing');
    }

    // ============================================================
    // FIX 9: Switch JAVIT_ACTIVO
    // ============================================================
    // Si el Secret JAVIT_ACTIVO está en "false", el bot está apagado.
    // En ese caso:
    //   1. Aplicamos tag EXISTENTE_CONVERSACION al contacto (para que el
    //      kill switch del flow lo bloquee en futuras interacciones)
    //   2. Devolvemos respuesta neutra que NO envía mensaje al lead
    //      (msg vacío + etapa especial + sin handoff)
    //
    // Para activar/desactivar Javit sin tocar el flow:
    //   - Cloudflare Dashboard → Worker → Settings → Variables
    //   - JAVIT_ACTIVO = "true"  → bot prendido (default si no está setteado)
    //   - JAVIT_ACTIVO = "false" → bot apagado (modo manual)
    if (env.JAVIT_ACTIVO === 'false') {
      console.log('JAVIT_ACTIVO=false → modo manual. Capturando lead en CRM y aplicando EXISTENTE_CONVERSACION a', payload.manychat_subscriber_id);

      // Sanitize datos básicos del lead (necesarios para tags + CRM)
      const subId = sanitize(payload.manychat_subscriber_id);
      const ig_username_off = sanitize(payload.ig_username);
      const first_name_off = sanitize(payload.first_name);
      const last_name_off = sanitize(payload.last_name);
      const full_name_off = sanitize(payload.full_name) ||
                           [first_name_off, last_name_off].filter(Boolean).join(' ').trim() ||
                           first_name_off;
      const fuente_off = sanitize(payload.fuente);
      const last_text_off = sanitize(payload.last_text);
      const etapa_anterior_off = sanitize(payload.etapa_actual) || 'Inicial';

      // 1. Tags via ManyChat API (fire-and-forget)
      if (env.MANYCHAT_API_TOKEN && subId && ctx?.waitUntil) {
        // 1a. Agregar EXISTENTE_CONVERSACION → kill switch lo bloqueará en futuros mensajes
        ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, subId, 'EXISTENTE_CONVERSACION', 'add'));
        // 1b. Remover CONVERSACION_ACTIVA → el nodo Acciones la aplicó pero NO queremos que quede,
        //     porque el lead no está realmente en conversación activa con el bot.
        ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, subId, 'CONVERSACION_ACTIVA', 'remove'));
        // 1c. Aplicar REQUIERE_RESPUESTA_HUMANA → señaliza al equipo que este lead necesita atención
        ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, subId, 'REQUIERE_RESPUESTA_HUMANA', 'add'));
      }

      // 2. ✨ Sincronizar al CRM aunque Javit esté apagado.
      //    Garantiza que SIEMPRE tengamos el contacto registrado, aunque el bot no
      //    procese la conversación. El equipo puede completar la info manualmente
      //    o con un script posterior (ManyChat API / scraper).
      if (env.APPS_SCRIPT_URL && ctx?.waitUntil) {
        const crmPayloadOff = {
          ig_username: ig_username_off,
          first_name: first_name_off,
          last_name: last_name_off,
          full_name: full_name_off,
          manychat_subscriber_id: subId,
          fuente: fuente_off,
          evento: 'javit_off_lead_capturado',
          etapa_actual: 'JavitOff',
          etapa_anterior: etapa_anterior_off,
          profesion: null,
          ingreso_mensual_cop_M: null,
          dolor_opcion: null,
          urgencia: null,
          califica: null,
          handoff_humano: true,
          handoff_razon: 'javit_off',
          ultimo_mensaje_lead: last_text_off,
          ultimo_mensaje_bot: '',
          summary: 'Javit desactivado (JAVIT_ACTIVO=false). Lead capturado para procesamiento manual posterior. Info por completar.',
        };
        ctx.waitUntil(syncToCRM(env.APPS_SCRIPT_URL, crmPayloadOff));
      }

      // El shape con campos null (no "") lo garantiza buildBotResponse (Bug #8, caso
      // María Angelica). El msg es descriptivo y NO se envía al lead: el flow tiene
      // condition etapa=JavitOff que omite el envío.
      return jsonResponse(buildBotResponse({
        msg: 'JavitOff - sin respuesta automatica',
        etapa: 'JavitOff',
        summary: 'Javit desactivado (JAVIT_ACTIVO=false). Lead etiquetado para atención manual.',
        handoff_humano: false,
        handoff_razon: 'javit_off',
      }));
    }

    // Construir contexto para Claude
    // sanitize() limpia el bug de ManyChat donde custom fields vacíos
    // llegan como "{{cuf_14624252}}" en vez de string vacío.
    const last_text = sanitize(payload.last_text);
    const first_name = sanitize(payload.first_name);
    const last_name = sanitize(payload.last_name);
    // full_name combina first + last si ambos están; si no, usa lo que haya.
    // El bot SIEMPRE usa first_name en sus mensajes (más cálido).
    // El CRM SIEMPRE usa full_name (más completo para revisión humana).
    const full_name = sanitize(payload.full_name) ||
                      [first_name, last_name].filter(Boolean).join(' ').trim() ||
                      first_name;
    const ig_username = sanitize(payload.ig_username);
    const manychat_subscriber_id = sanitize(payload.manychat_subscriber_id);
    const fuente = sanitize(payload.fuente);
    const conversation_summary = sanitize(payload.conversation_summary);
    const etapa_actual = sanitize(payload.etapa_actual) || 'Inicial';
    const profesion_actual = sanitize(payload.profesion);
    const ingreso_raw = sanitize(payload.ingreso_mensual_cop_M);
    const ingreso_actual = ingreso_raw ? Number(ingreso_raw) || null : null;
    const dolor_actual = sanitize(payload.dolor_opcion);
    const urgencia_actual = sanitize(payload.urgencia);

    // ============================================================
    // FIX 5: Detección de retries de ManyChat
    // ============================================================
    // Si ManyChat reintenta porque la primera llamada falló (timeout
    // o error), recibimos el MISMO last_text del MISMO subscriber.
    // Devolvemos la respuesta cacheada en vez de llamar a Claude otra
    // vez (evita mensaje duplicado al lead y costo doble en Anthropic).
    const retryKey = manychat_subscriber_id + '::' + (last_text || '');
    const cacheKey = new Request('https://retry-cache.local/' + encodeURIComponent(retryKey));
    const cache = caches.default;
    if (manychat_subscriber_id && last_text) {
      try {
        const cachedResp = await cache.match(cacheKey);
        if (cachedResp) {
          console.log('Retry detectado para subscriber', manychat_subscriber_id, '— devolviendo respuesta cacheada');
          const cachedData = await cachedResp.json();
          return jsonResponse(cachedData);
        }
      } catch (e) {
        console.error('Error leyendo cache de retry:', e?.message);
        // Continuar normalmente si la cache falla
      }
    }

    const userMessage = `## ESTADO ACTUAL DEL LEAD

Nombre: ${first_name || 'lead'}
Etapa actual registrada: ${etapa_actual || 'Inicial'}
Profesión registrada: ${profesion_actual || '(sin registrar)'}
Ingreso registrado (M COP): ${ingreso_actual ?? '(sin registrar)'}
Dolor registrado: ${dolor_actual || '(sin registrar)'}
Urgencia registrada: ${urgencia_actual || '(sin registrar)'}

## RESUMEN DE LA CONVERSACIÓN PREVIA
${conversation_summary || '(primera interacción, sin historial)'}

## ÚLTIMO MENSAJE DEL LEAD
"${last_text}"

## TU TAREA
Genera el JSON de respuesta según las reglas del system prompt. Analiza el último mensaje del lead, decide la etapa siguiente, y responde con el mensaje correspondiente.`;

    // Llamar a Anthropic API con timeout de 12s.
    // CRÍTICO: ManyChat corta External Requests entre 12-15s. Si esperamos 25s
    // como antes, ManyChat reporta "Response is null" y el lead queda sin respuesta
    // (caso Stephany 2026-06-02). Mejor abortar a los 12s y devolver fallback
    // de handoff — al menos así el lead recibe algo y queda registrado en CRM.
    // Con prompt caching (cache_control: ephemeral), Anthropic suele responder en
    // 2-6s dentro de los 5 min del cache. 12s es margen amplio para casos normales.
    let anthropicResponse;
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), ANTHROPIC_TIMEOUT_MS);
    try {
      anthropicResponse = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'x-api-key': env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01',
          'anthropic-beta': 'prompt-caching-2024-07-31',
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          model: 'claude-sonnet-4-6',
          max_tokens: 1000,
          temperature: 0.3,
          // Prompt caching: el system prompt es estático y muy largo (~3000+ tokens).
          // Marcándolo como `cache_control: ephemeral` Anthropic lo cachea por 5 min
          // y solo cobra/procesa lo que cambia (el user message). Resultado:
          // latencia 5-10x menor + costo ~90% menor en requests dentro de 5 min.
          system: [
            {
              type: 'text',
              text: SYSTEM_PROMPT,
              cache_control: { type: 'ephemeral' },
            },
          ],
          messages: [
            { role: 'user', content: userMessage },
          ],
        }),
        signal: abortController.signal,
      });
      clearTimeout(timeoutId);
    } catch (e) {
      clearTimeout(timeoutId);
      const reason = e?.name === 'AbortError' ? 'anthropic_timeout_12s' : 'anthropic_request_failed';
      console.error('Error llamando a Anthropic API:', e?.message || e, 'reason:', reason);
      return fallbackResponse('Tuve un problema técnico. Te respondo en un rato.', reason, env, ctx, manychat_subscriber_id);
    }

    if (!anthropicResponse.ok) {
      const errorText = await anthropicResponse.text();
      console.error('Anthropic API error:', anthropicResponse.status, errorText);

      // Detectar error de créditos
      if (errorText.includes('credit balance') || errorText.includes('insufficient')) {
        return fallbackResponse('Tuve un problema técnico. Te respondo en un rato.', 'no_credits', env, ctx, manychat_subscriber_id);
      }

      return fallbackResponse('Tuve un problema técnico. Te respondo en un rato.', `anthropic_${anthropicResponse.status}`, env, ctx, manychat_subscriber_id);
    }

    let anthropicData;
    try {
      anthropicData = await anthropicResponse.json();
    } catch (e) {
      return fallbackResponse('Tuve un problema técnico. Te respondo en un rato.', 'anthropic_parse_error', env, ctx, manychat_subscriber_id);
    }

    // Extraer texto generado por Claude
    const generatedText = anthropicData?.content?.[0]?.text || '';
    if (!generatedText) {
      return fallbackResponse('Tuve un problema técnico. Te respondo en un rato.', 'empty_response', env, ctx, manychat_subscriber_id);
    }

    // Parsear el JSON que Claude devolvió
    // Estrategia en cascada (de menos a más agresiva):
    //   1. Parse directo (caso ideal)
    //   2. Limpieza de markdown (```json ... ```)
    //   3. Extracción de primer {...} con balanceo de llaves (atrapa casos donde Claude
    //      genera razonamiento ANTES del JSON, como pasó con Laura)
    //   4. Si todo falla → fallback genérico (NUNCA enviar raw text al lead)
    let parsedClaude = null;
    const firstNameForFallback = sanitize(payload.first_name) || 'amigo';
    const HANDOFF_MSG = `Gracias, ${firstNameForFallback}. Permíteme un momento y te respondo. 🙌`;

    try {
      // Intento 1: parse directo
      parsedClaude = JSON.parse(generatedText.trim());
    } catch (_e1) {
      try {
        // Intento 2: limpiar markdown
        const cleanedMd = generatedText
          .replace(/^```json\s*/i, '')
          .replace(/^```\s*/i, '')
          .replace(/\s*```\s*$/i, '')
          .trim();
        parsedClaude = JSON.parse(cleanedMd);
      } catch (_e2) {
        try {
          // Intento 3: extraer primer bloque {...} con balanceo de llaves
          // Esto rescata casos donde Claude genera razonamiento/CoT antes del JSON
          const extracted = extractFirstJsonObject(generatedText);
          if (extracted) {
            parsedClaude = JSON.parse(extracted);
            console.warn('JSON rescatado tras razonamiento de Claude. Texto previo descartado.');
          }
        } catch (_e3) {
          parsedClaude = null;
        }
      }
    }

    // Si TODOS los intentos fallaron → fallback con mensaje GENÉRICO (jamás el raw)
    if (!parsedClaude || typeof parsedClaude !== 'object' || !parsedClaude.msg) {
      console.error('No se pudo extraer JSON válido de Claude. Texto crudo:', generatedText.slice(0, 500));
      // ⚠️ CRÍTICO (Bug #5): msg = handoff genérico, NUNCA el generatedText raw
      // (eso enviaría razonamiento/CoT al lead).
      return jsonResponse(buildBotResponse({
        msg: HANDOFF_MSG,
        etapa: 'Handoff',
        summary: 'Claude devolvió texto no JSON parseable. Mensaje raw descartado. Revisión humana.',
        handoff_humano: true,
        handoff_razon: 'claude_json_parse_error',
      }));
    }

    // Normalizar la respuesta por el MISMO contrato que todas las salidas.
    // Slicing de msg/summary se aplica antes; etapa default 'M1' (no 'Handoff') en éxito.
    // Delta intencional vs antes: si Claude devuelve "" en un campo de datos, ahora
    // queda null (no "") — cierra el invariante del Bug #8 también en la ruta de éxito.
    const normalized = buildBotResponse({
      msg: String(parsedClaude.msg || '').slice(0, 700),
      etapa: String(parsedClaude.etapa || 'M1'),
      profesion: parsedClaude.profesion,
      ingreso_mensual_cop_M: parsedClaude.ingreso_mensual_cop_M,
      dolor_opcion: parsedClaude.dolor_opcion,
      urgencia: parsedClaude.urgencia,
      califica: parsedClaude.califica ?? null,
      summary: String(parsedClaude.summary || '').slice(0, 400),
      handoff_humano: parsedClaude.handoff_humano,
      handoff_razon: parsedClaude.handoff_razon,
    });

    // Validador final de salida (Bug #5): si el msg parece JSON/razonamiento crudo,
    // NO lo enviamos al lead. SUAVIZADO (Fase 0.1): en vez de descartar todo y cortar,
    // reemplazamos SOLO el msg por el handoff seguro y marcamos handoff para revisión
    // humana — pero PRESERVAMOS lo que Claude extrajo (profesion, ingreso, dolor, etc.) y
    // dejamos que el flujo siga (sync a CRM + tags). Así no perdemos el lead ni sus datos.
    if (looksUnsafeForLead(normalized.msg)) {
      console.error('msg bloqueado por validador de salida (parecía JSON/razonamiento):', normalized.msg.slice(0, 200));
      normalized.msg = HANDOFF_MSG;
      normalized.etapa = 'Handoff';
      normalized.handoff_humano = true;
      normalized.handoff_razon = 'unsafe_msg_blocked';
    }

    // FIX 5: Guardar la respuesta en cache para detectar retries futuros (60s TTL).
    // Si ManyChat reintenta dentro de 60s con el mismo input, devolvemos esta misma
    // respuesta sin llamar a Claude otra vez.
    if (manychat_subscriber_id && last_text && ctx?.waitUntil) {
      try {
        const cacheResp = new Response(JSON.stringify(normalized), {
          headers: {
            'Cache-Control': 'max-age=60',
            'Content-Type': 'application/json',
          },
        });
        ctx.waitUntil(cache.put(cacheKey, cacheResp));
      } catch (e) {
        console.error('Error guardando cache de retry:', e?.message);
      }
    }

    // Sincronizar al CRM via Apps Script (fire-and-forget, no espera)
    // Esto NO retrasa la respuesta a ManyChat.
    if (env.APPS_SCRIPT_URL && ctx?.waitUntil) {
      const crmPayload = {
        ig_username,
        first_name,    // El bot lo usa para hablarle al lead (más cálido)
        last_name,
        full_name,     // El CRM lo usa para la columna Nombre (más completo)
        manychat_subscriber_id,
        fuente,
        evento: detectEvento(etapa_actual, normalized.etapa, normalized.handoff_humano),
        etapa_actual: normalized.etapa,
        etapa_anterior: etapa_actual,
        profesion: normalized.profesion || profesion_actual,
        ingreso_mensual_cop_M: normalized.ingreso_mensual_cop_M ?? ingreso_actual,
        dolor_opcion: normalized.dolor_opcion || dolor_actual,
        urgencia: normalized.urgencia || urgencia_actual,
        califica: normalized.califica,
        handoff_humano: normalized.handoff_humano,
        handoff_razon: normalized.handoff_razon,
        ultimo_mensaje_lead: last_text,
        ultimo_mensaje_bot: normalized.msg,
        summary: normalized.summary,
      };
      ctx.waitUntil(syncToCRM(env.APPS_SCRIPT_URL, crmPayload));
    }

    // FIX 8 (mejorado): Tagging automático via ManyChat API (fire-and-forget)
    // - ATENDIDO_BOT siempre que el bot procesa exitosamente
    // - HANDOFF_ANDRES genérico cuando handoff_humano=true
    // - Tag ESPECÍFICA por handoff_razon para segmentación granular
    if (env.MANYCHAT_API_TOKEN && manychat_subscriber_id && ctx?.waitUntil) {
      ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, manychat_subscriber_id, 'ATENDIDO_BOT', 'add'));
      if (normalized.handoff_humano) {
        ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, manychat_subscriber_id, 'HANDOFF_ANDRES', 'add'));
        // Tag específica según razón del handoff (mapping razón → tag)
        const razonToTag = {
          'agendamiento_manual_pendiente': 'HANDOFF_AGENDA_MANUAL',
          'pregunta_precio': 'HANDOFF_PRECIO',
          'crisis_emocional': 'HANDOFF_CRISIS',
          'ex_cliente': 'HANDOFF_EX_CLIENTE',
          'lead_existente': 'HANDOFF_EX_CLIENTE',
          'objecion_no_estandar': 'HANDOFF_OBJECION',
          'claude_json_parse_error': 'ERROR_BOT',
          'unsafe_msg_blocked': 'ERROR_BOT',
          'no_credits': 'ERROR_BOT',
          'anthropic_timeout_12s': 'ERROR_BOT',
          'anthropic_timeout_25s': 'ERROR_BOT', // retro-compatibilidad con logs antiguos
          'anthropic_request_failed': 'ERROR_BOT',
          'json_parse_error': 'ERROR_BOT',
          'api_key_missing': 'ERROR_BOT',
          'empty_response': 'ERROR_BOT',
          'anthropic_parse_error': 'ERROR_BOT',
        };
        const tagEspecifica = razonToTag[normalized.handoff_razon] || 'HANDOFF_OTRO';
        ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, manychat_subscriber_id, tagEspecifica, 'add'));
      }
    }

    return jsonResponse(normalized);
}


/**
 * Envía el evento al Apps Script en background.
 * No bloquea la respuesta a ManyChat. Si falla, solo loguea — el bot sigue funcionando.
 */
async function syncToCRM(appsScriptUrl, payload) {
  try {
    const resp = await fetch(appsScriptUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      // Apps Script puede tomar 2-5 segundos en responder, le damos margen
      cf: { cacheTtl: 0 },
    });
    if (!resp.ok) {
      console.error('Apps Script error:', resp.status, await resp.text());
    } else {
      const result = await resp.json();
      console.log('CRM sync OK:', result.action, 'row:', result.row);
    }
  } catch (e) {
    console.error('Error sincronizando al CRM:', e.message);
  }
}


/**
 * Aplica/remueve un tag a un contacto via API de ManyChat.
 * Es fire-and-forget: si falla, solo loguea (no rompe el flujo principal).
 *
 * @param {string} token - El API token de ManyChat (en formato pageId:hash)
 * @param {string} subscriberId - El ID del contacto
 * @param {string} tagName - Nombre del tag (ej. ATENDIDO_BOT, ERROR_BOT)
 * @param {string} action - 'add' o 'remove'
 */
async function applyTagAsync(token, subscriberId, tagName, action) {
  if (!token || !subscriberId || !tagName) return;
  const endpoint = action === 'remove' ? 'removeTagByName' : 'addTagByName';
  try {
    const resp = await fetch('https://api.manychat.com/fb/subscriber/' + endpoint, {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        subscriber_id: subscriberId,
        tag_name: tagName,
      }),
    });
    if (!resp.ok) {
      console.error('Tag ' + action + ' failed:', tagName, resp.status, await resp.text());
    } else {
      console.log('Tag ' + action + ' OK:', tagName, 'on', subscriberId);
    }
  } catch (e) {
    console.error('Error aplicando tag ' + tagName + ':', e?.message);
  }
}


/**
 * Clasifica el evento según la transición de etapa.
 * Útil para filtrar el Activity Log por tipo de evento.
 */
function detectEvento(etapaAnterior, etapaNueva, handoff) {
  if (handoff) return 'handoff_' + (etapaNueva || 'unknown').toLowerCase();
  if (etapaNueva === etapaAnterior) return etapaNueva + '_turno_adicional';
  const map = {
    'M1': 'lead_nuevo',
    'M2': 'M2_dolor_pregunta_enviada',
    'M3': 'M3_dolor_identificado',
    'M4': 'M4_pitch_enviado',
    'M5': 'M5_calendly_enviado',
    'M5.B': 'agendamiento_confirmado',
    'M5.C': 'cierre_cordial_post_agenda',
    'Descalificado': 'descalificado',
    'AgendaManual_1': 'agendamiento_manual_inicio',
    'AgendaManual_2': 'agendamiento_manual_datos',
  };
  return map[etapaNueva] || 'etapa_' + etapaNueva;
}


/**
 * Limpia los placeholders sin resolver de ManyChat.
 *
 * Cuando un custom field NO tiene valor, ManyChat manda el placeholder literal
 * "{{cuf_14624252}}" en vez de string vacío. Este sanitize convierte cualquier
 * placeholder a string vacío para que el Worker y el Apps Script lo manejen
 * correctamente.
 *
 * Patrones que detecta:
 *   {{cuf_12345}}  - custom field ID
 *   {{sys_xxx}}    - system field placeholder
 *   {{cuf_xxx|0}}  - con default
 */
/**
 * Extrae el PRIMER objeto JSON balanceado de un string, ignorando texto antes/después.
 *
 * Útil cuando Claude genera razonamiento (chain-of-thought) antes del JSON, por ejemplo:
 *   "Analyzing message: ... → Handoff con razon=X { "msg": "...", ... }"
 *
 * Recorre el string buscando '{' y balancea llaves teniendo en cuenta:
 *   - Strings entre comillas dobles (no cuentan llaves dentro)
 *   - Escapes con backslash
 *
 * @param {string} text  texto crudo de Claude
 * @returns {string|null}  el objeto JSON como string, o null si no encontró uno balanceado
 */
function extractFirstJsonObject(text) {
  if (!text || typeof text !== 'string') return null;
  const start = text.indexOf('{');
  if (start === -1) return null;

  let depth = 0;
  let inString = false;
  let escape = false;

  for (let i = start; i < text.length; i++) {
    const ch = text[i];

    if (escape) {
      escape = false;
      continue;
    }
    if (ch === '\\' && inString) {
      escape = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;

    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) {
        return text.slice(start, i + 1);
      }
    }
  }
  return null;
}


function sanitize(value) {
  if (value === null || value === undefined) return '';
  const str = String(value).trim();
  // Detecta cualquier placeholder de ManyChat sin resolver
  if (/^\{\{(cuf_|sys_|user_|sub_|sub_id|first_name|last_name|ig_username|user_id)/i.test(str)) {
    return '';
  }
  // También detecta el patrón completo {{anything}}
  if (/^\{\{.+\}\}$/.test(str)) {
    return '';
  }
  return str;
}


// Campos de datos que ManyChat mapea a custom fields: un valor "vacío" DEBE ser
// null, nunca "" ni " " (ManyChat los rechaza con "Invalid value type in json path"
// — Bug #8, caso María Angelica). Coacciona vacío → null y preserva 0/false/números.
function emptyToNull(v) {
  if (v === undefined || v === null) return null;
  if (typeof v === 'string' && v.trim() === '') return null;
  return v;
}

/**
 * CONTRATO DE SALIDA — único constructor del JSON que el Worker devuelve a ManyChat.
 *
 * TODAS las salidas del Worker (éxito, fallback, guard de placeholders, JavitOff,
 * timeout) pasan por aquí. Garantiza los invariantes del response mapping:
 *   - Siempre los 10 campos, en el mismo orden.
 *   - Campos de datos vacíos → null, nunca "" ni " " (Bug #8).
 *   - handoff_humano siempre booleano.
 *   - handoff_razon string | null.
 * El `msg` se pasa tal cual (ya validado aguas arriba): nunca debe contener razonamiento
 * crudo del LLM (Bug #5) — eso se garantiza en el parseo, no aquí.
 */
function buildBotResponse(f) {
  return {
    msg: typeof f.msg === 'string' ? f.msg : '',
    etapa: f.etapa ? String(f.etapa) : 'Handoff',
    profesion: emptyToNull(f.profesion),
    ingreso_mensual_cop_M: emptyToNull(f.ingreso_mensual_cop_M),
    dolor_opcion: emptyToNull(f.dolor_opcion),
    urgencia: emptyToNull(f.urgencia),
    califica: f.califica ?? null,
    summary: typeof f.summary === 'string' ? f.summary : '',
    handoff_humano: !!f.handoff_humano,
    handoff_razon: emptyToNull(f.handoff_razon),
  };
}

/**
 * ENTRADA (Bug #9): true si el payload llegó sin subscriber_id NI last_text resueltos
 * (típico retry manual desde la UI de ManyChat, con placeholders literales). En ese caso
 * no tiene sentido llamar a Anthropic. Predicado puro, testeable.
 */
function hasNoResolvedContext(payload) {
  return !sanitize(payload?.manychat_subscriber_id) && !sanitize(payload?.last_text);
}

/**
 * SALIDA (Bug #5): última red antes de enviar al lead. true si el `msg` parece contener
 * JSON o razonamiento crudo del LLM en vez de texto natural. Si matchea, el caller debe
 * sustituirlo por un fallback seguro y NO enviarlo. Conservador para no dar falsos positivos.
 */
function looksUnsafeForLead(msg) {
  if (typeof msg !== 'string' || !msg.trim()) return true;
  const s = msg.trim();
  if (/\{\s*"/.test(s)) return true;                                        // abre objeto JSON
  if (/"(msg|etapa|handoff_humano|handoff_razon)"\s*:/.test(s)) return true; // claves del schema
  if (/^analyzing\b/i.test(s)) return true;                                  // razonamiento/CoT (caso Laura)
  return false;
}


function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...corsHeaders(),
    },
  });
}

/**
 * Construye la respuesta de fallback Y opcionalmente aplica tag ERROR_BOT
 * al contacto si recibimos env + ctx + subscriberId.
 *
 * @param {string} message - Mensaje al lead
 * @param {string} reason - Razón del fallback (para logs y handoff_razon)
 * @param {object} [env] - El env del Worker (con MANYCHAT_API_TOKEN)
 * @param {object} [ctx] - El ctx del Worker (con waitUntil)
 * @param {string} [subscriberId] - ID del contacto a tagear
 */
function fallbackResponse(message, reason, env, ctx, subscriberId) {
  // Tags al contacto en caso de fallback (el bot no pudo procesar):
  // - ERROR_BOT: para identificar todos los leads que tuvieron error
  // - HANDOFF_ANDRES: porque el fallback siempre devuelve handoff_humano=true,
  //   así el equipo sabe que tiene que intervenir
  if (env?.MANYCHAT_API_TOKEN && subscriberId && ctx?.waitUntil) {
    ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, subscriberId, 'ERROR_BOT', 'add'));
    ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, subscriberId, 'HANDOFF_ANDRES', 'add'));
  }
  return jsonResponse(buildBotResponse({
    msg: message,
    etapa: 'Handoff',
    summary: `Fallback automático del worker: ${reason}`,
    handoff_humano: true,
    handoff_razon: reason,
  }));
}


// ── Exports para tests unitarios ────────────────────────────────────────────
// El runtime de Cloudflare usa SOLO `export default`. Estos named exports son
// inertes en producción y permiten testear las funciones puras del contrato (Fase 0).
export {
  sanitize,
  emptyToNull,
  buildBotResponse,
  extractFirstJsonObject,
  hasNoResolvedContext,
  looksUnsafeForLead,
};
