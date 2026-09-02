/**
 * Biblioteca de plantillas — SOP Setter DM en Instagram V4.2 (1-sep-2026)
 * ============================================================================
 * TEXTO LITERAL del playbook. Esto NO se parafrasea, no se "mejora" y no lo
 * genera el LLM: es copy probado en produccion y optimizado para conversion.
 * El LLM del bot nuevo solo clasifica/extrae y aporta 1-2 frases de empatia
 * que se anteponen a estas plantillas -- nunca las reemplaza.
 *
 * Cambios de V4.2 que se reflejan aca:
 *  - Se ELIMINA Datacredito de la precalificacion (el flujo pasa de 8 a 7
 *    mensajes y de 4 a 3 filtros).
 *  - Se reordena el cierre: M6 = cierre + link, M7 = pregunta de asistencia
 *    (antes era al reves).
 *  - Tope de endeudamiento condicional al ingreso (<=50% si gana ~$7M,
 *    hasta 60% si gana >$9M).
 *  - Regla anti-descarte por ingreso ambiguo + glosario colombiano (V4.1).
 *  - RetornoLead: si un lead descartado se recalifica, se rectifica solo.
 *
 * Marcado explicito: las entradas con `_extensionOperativa: true` NO salen del
 * playbook -- son minimos operativos que el bot necesita para no dejar al lead
 * sin respuesta en un punto donde el SOP le habla al Setter humano ("espera a
 * que agende") en vez de darle un script. Estan aisladas a proposito para que
 * el fundador las revise y las apruebe o reemplace por copy oficial.
 */

export const CALENDAR_LINK = 'https://calendar.app.google/iMW5LBbkcAvorypF9';

export const REELS = {
  ingresos_bajos: 'https://www.instagram.com/reel/DJDejvjtfzH/',
  salir_de_deudas: 'https://www.instagram.com/reel/DMmAfHqt3a7/',
  tarjetas_credito: 'https://www.instagram.com/p/DIZ3HNwMLky/',
  nurture: 'https://www.instagram.com/reel/DX73ACPNvRV/',
};

/** Umbrales de los 3 filtros del SOP V4.2. */
export const UMBRALES = {
  INGRESO_MINIMO: 7_000_000,
  INGRESO_BORDERLINE_BAJO: 4_000_000,
  // Tope de endeudamiento condicional al ingreso (V4.0/V4.2)
  INGRESO_TOPE_ALTO: 9_000_000,
  ENDEUDAMIENTO_TOPE_BASE: 50,
  ENDEUDAMIENTO_TOPE_ALTO: 60,
  // "apenas por encima de su tope (hasta ~10 puntos)" -> borderline
  ENDEUDAMIENTO_MARGEN_BORDERLINE: 10,
  SMLV_2026: 1_420_000,
};

const P = {};

// ---------------------------------------------------------------------------
// MENSAJE 1 — Apertura + Validacion + Pregunta de Contexto
// ---------------------------------------------------------------------------
P.M1_CONTROL = `¡Hola {nombre}! 👋 Te entiendo, no tener el control real de tu dinero, que se te está yendo como "sal y agua" mes a mes, es la frustración #1 de los profesionales que ganan bien.

Para ver si te puedo ayudar de verdad, cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?`;

P.M1_CLARIDAD = `¡Hola {nombre}! 👋 Te entiendo, buscas tener claridad para tomar el control real de tu dinero, porque se te está volviendo "sal y agua" mes a mes. Es la frustración #1 de los profesionales que ganan bien.

Para ver si te puedo ayudar de verdad, cuéntame: ¿A qué te dedicas y cuánto estás ganando al mes aproximadamente?`;

P.M1_GENERAL = `¡Hola {nombre}! 👋 Llegas al lugar correcto si buscas frenar eso de que la plata se te vuelve "sal y agua" cada mes. Esa frustración de ganar bien pero siempre terminar en ceros es gigante, yo la viví.

Para saber si mi método aplica 100% a tu caso, cuéntame: ¿A qué te dedicas y cuánto ganas al mes aproximadamente?`;

/** Escenario B: dio profesion pero evadio el ingreso. */
P.M1_PEDIR_RANGO = `Te pregunto porque el proceso funciona mejor para personas que ganan entre $7M y $15M COP o más al mes. ¿Estás en ese rango?`;

/** Escenario E (★ V4.1): ingreso ambiguo, sin cifra clara. NUNCA descalificar aca. */
P.M1_PEDIR_CIFRA = `Para calcularlo bien, ¿me confirmas el número aproximado que te queda al mes en pesos? Así te digo con certeza si te podemos ayudar.`;

// ---------------------------------------------------------------------------
// MENSAJE 2 — Empatia + Validacion de Endeudamiento
// ---------------------------------------------------------------------------
P.M2 = `Ok, {nombre}. Para asegurar que mi método te aplique perfecto y puedas ver resultados rápidos, necesito validar algo clave: ¿Sabes aproximadamente cuál es tu nivel de endeudamiento hoy? 🤔

Para calcularlo suma todo lo que pagas al mes en créditos, tarjetas, préstamos o deudas con alguien. El arriendo, servicios y mercado NO CUENTAN — esos son gastos fijos.

Con ese número haces esto: total de deudas ÷ ingresos del mes × 100
Ejemplo: $1.500.000 en deudas ÷ $7.000.000 de ingresos × 100 = 21%

¿Cuánto te da a ti? 😊`;

P.M2_BORDERLINE = `Entiendo. ¿Qué tipo de deudas son? (créditos de consumo, hipoteca, tarjetas). Si la mayoría es deuda buena (vivienda) el escenario cambia.`;

P.M2_NO_SABE = `Sin presión, dame un estimado. ¿Te queda plata después de pagar deudas o todo se va en eso?`;

// ---------------------------------------------------------------------------
// MENSAJE 3 — Validacion de Dolor
// ---------------------------------------------------------------------------
P.M3 = `Perfecto, {nombre}.

Ahora, si tuvieras que elegir, ¿cuál es tu mayor frustración hoy con tu dinero?

A) No me alcanza, siempre estoy en cero a fin de mes
B) No sé en qué se va, es como si se evaporara
C) Siento que debería estar mejor de lo que estoy con lo que gano
D) Otra (¿cuál?)`;

P.M3_RECONDUCIR = `Entiendo. Lo que pasa es que nos especializamos en ayudar a profesionales a construir patrimonio. Si tu tema principal es otro, puede que no seamos el mejor fit. ¿O tu frustración está conectada con que sientes que tu dinero no te alcanza para tomar decisiones más libres?`;

// ---------------------------------------------------------------------------
// MENSAJE 4 — Empatia + Urgencia (ultimo filtro antes del pitch)
// ---------------------------------------------------------------------------
P.M4 = `Te entiendo perfectamente.

Eso es exactamente lo que yo llamo "la trampa del ingreso medio-alto": ganas bien pero no construyes patrimonio. Y lo peor es que mientras más pasa el tiempo, más se complica salir.

Yo estuve ahí. A los 30 años debía el 60% de mi salario. Por eso creé el Protocolo de Reconexión Financiera.

Última pregunta antes de contarte cómo funciona: ¿Resolver esto es una prioridad AHORA para ti, o es algo para "cuando tenga más tiempo / más dinero"?`;

// ---------------------------------------------------------------------------
// MENSAJE 5 — Pitch de la llamada (EL MOMENTO CRITICO)
// ---------------------------------------------------------------------------
P.M5 = `Perfecto, con lo que me cuentas, siento que te puedo ayudar.

Te planteo que tengamos una llamada de diagnóstico, no tienes que pagar nada, es gratis, son 30 minutos donde:

1️⃣ Vamos a identificar EXACTAMENTE dónde se te está yendo la plata (la mayoría no lo sabe)
2️⃣ Te voy a mostrar el mapa de ruta personalizado para pasar de "ganar bien, vivir mal" a construir patrimonio real
3️⃣ Revisaremos si mi Protocolo de Reconexión Financiera aplica a tu caso específico.

Y ojo: no trabajo con todo el mundo. Solo con personas que:
✅ Están listas para hacer cambios reales en su vida (no solo "tips")
✅ Quieren tomar acción ya para tener resultados en los próximos 60 días, no "algún día".

¿Agendamos?`;

// ---------------------------------------------------------------------------
// MENSAJE 6 — Cierre del agendamiento (★ reordenado en V4.2)
// ---------------------------------------------------------------------------
// ⚠️ REGLA CRITICA DEL LINK -- bug CONFIRMADO EN PRODUCCION por el equipo de
// Javier (ver Setter-IA-Claude-Code-Project/knowledge-base/04-voz-y-tono.md y
// scripts/m5-cierre-agendamiento.md):
//
//   "cuando un link de Calendly se envia y luego viene otro texto en chunks
//    rapidos, Instagram puede concatenar el link con el texto siguiente y
//    dejar el link INVALIDO ('Dynamic Link Not Found'). Esto rompe el
//    agendamiento."
//
// Reglas duras que salen de ahi:
//   1. Todo el contexto que acompaña al link va ANTES del link.
//   2. El link es SIEMPRE el ULTIMO elemento del turno.
//   3. NUNCA se manda texto despues del link en el MISMO turno.
//
// Por eso el turno del link son exactamente 2 burbujas (saludo, link) y el
// "Confirmame..." + M7 se van al turno SIGUIENTE. Su propio documento
// recomienda justo esto: "prioriza dividir en 2 turnos".
P.M6_SALUDO = `¡Perfecto! 🙌
Acá te dejo el link para que elijas el día y hora que mejor te quede:`;

/** Va SOLO en su burbuja, y es lo ultimo del turno. Nada despues. */
P.M6_LINK = CALENDAR_LINK;

P.M6_CONFIRMAME = `Confirmame cuando te hayas agendado, así te envío un par de puntos clave para que lleves a nuestra llamada.`;

// ---------------------------------------------------------------------------
// MENSAJE 7 — Confirmar asistencia (★ NUEVO V4.0, reordenado en V4.2)
// ---------------------------------------------------------------------------
P.M7 = `Excelente {nombre}, antes de que separes tu espacio te hago una última pregunta 😊

¿A esta sesión de diagnóstico asistirás solo tú o consideras importante que participe alguien más?

Te lo pregunto porque hay personas que prefieren tener presente a alguien con quien suelen hablar sus temas financieros.`;

P.M7_ACOMPANADO = `Perfecto {nombre}, entonces cuando vayas a agendar asegúrate de que esa persona también pueda estar ese día ¿Lo pueden cuadrar?`;

/**
 * Acuse cuando el lead dice que asiste solo.
 *
 * El SOP aca le habla al Setter humano ("Perfecto, esperar a que agende") en
 * vez de dar un script, asi que este texto no es copy literal del playbook.
 * Aprobado por el fundador (1-sep-2026) y escrito siguiendo la voz del
 * proyecto de Javier: linea corta y calida, sin abrir hilos nuevos y sin
 * volver a vender ("el lead ya dijo que si en M5").
 */
P.M7_SOLO_ACK = `¡Listo, {nombre}! 🙌 Quedo pendiente de tu confirmación cuando separes tu espacio.`;

/** Cuando confirma que agendo -> preguntas pre-llamada. */
P.CIERRE_PRECALL = `Genial, para nuestra sesión ten listo:

1. ¿Cuál es tu estimado total de créditos actualmente?
2. ¿Hay algo específico que quisieras que yo entienda sobre tus objetivos o expectativas de esta mentoría?

Nos vemos en la llamada.`;

// ---------------------------------------------------------------------------
// BLINDAJE DEL SHOW-UP (M5.5.d) — aprobado por el fundador 1-sep-2026
// ---------------------------------------------------------------------------
// Copy LITERAL del proyecto de Javier
// (Setter-IA-Claude-Code-Project/scripts/m5-5-confirmacion-post-calendly.md).
// Validado en produccion: pre-compromete al lead con la asistencia (efecto
// consistencia) y ataca directo el KPI "% Show Up > 70%" del Scorecard.
// Se dispara cuando el lead agradece DESPUES de confirmar que agendo.
P.BLINDAJE_SHOWUP = `Buenísimo. A ti, gracias {nombre}.

Permíteme hacerte la última pregunta: ¿de aquí al día de la sesión puede pasar algo que haga que no asistas, o estamos súper firmes?`;

/** Responde "firme/seguro" -> se cierra la conversacion. */
P.BLINDAJE_FIRME = `¡Perfecto! Nos vemos entonces. 💪`;

/**
 * Responde "puede que pase X" -> mejor reagendar antes de quemar el slot.
 * Ojo: este mensaje NO lleva el link pegado. Si hay que reenviarlo, va en su
 * propia burbuja al final (misma regla critica del link).
 */
P.BLINDAJE_REAGENDAR = `Entiendo. Mejor reagendamos a un momento donde estés 100% seguro, así no perdemos el espacio.`;

// ---------------------------------------------------------------------------
// ACLARACION DE INGRESO REMANENTE — aprendizaje de produccion (SOP-05 #2)
// ---------------------------------------------------------------------------
// Patron real: el lead responde "me quedan $5M" o "menos de $7M" refiriendose
// al dinero que le SOBRA despues de gastos, no a su ingreso total. Descalificar
// ahi es perder un lead bueno. Copy literal del proyecto de Javier.
P.M1_ACLARAR_REMANENTE = `Solo para que estemos en la misma página: ¿esos que mencionas son tu ingreso total al mes, o lo que te queda después de cubrir gastos? Te pregunto porque cambia mucho el análisis.`;

// ---------------------------------------------------------------------------
// RETORNO LEAD (★ NUEVO V4.1) — descartado que se recalifica
// ---------------------------------------------------------------------------
// "rectifica de inmediato, sin humano y sin revelar que es IA"
P.RETORNO_LEAD = `¡Uy, tienes toda la razón, {nombre}! Con ese ingreso sí estás justo en el perfil. Retomemos entonces 🙌`;

// ---------------------------------------------------------------------------
// PLAYBOOK DE OBJECIONES (9)
// ---------------------------------------------------------------------------
P.OBJ_1 = `Sí, la llamada de diagnóstico es 100% gratis. Cero costo, cero compromiso.

En la llamada, te voy a mostrar dónde está el problema en tu situación financiera y te voy a dar el mapa de ruta para resolverlo. Después de eso, si te interesa que te ayude a implementarlo, te explico cómo funciona mi programa. Si no, igual te vas con claridad total de qué hacer.

Sin presión. ¿Te parece?`;

P.OBJ_2 = `Te entiendo. Igual son solo 30 minutos. Tengo espacios en diferentes horarios (mañana, tarde, noche).

Piénsalo así: si en 30 minutos pudieras identificar dónde se te están yendo $500K-$1M al mes (que probablemente sea el caso), ¿no vale la pena sacar esos minutos?

Revisa el calendario, seguro encuentras un hueco:
${CALENDAR_LINK}`;

P.OBJ_3 = `Dale, sin problema.

Igual te dejo el link por acá por si te decides:
${CALENDAR_LINK}

Los espacios se llenan rápido porque solo tomo un número limitado de llamadas por semana. Si te interesa, mejor reservar el espacio ahora y si pasa algo lo reagendas.

¿Listo?`;

P.OBJ_4 = `Te entiendo completamente. Hay mucho vendedor de humo por ahí.

Yo estuve EXACTAMENTE donde tú estás. A los 30 años debía el 60% de mi salario. Creé el Protocolo de Reconexión Financiera para salir de ahí, y ahora lo uso con profesionales como tú.

En la llamada no te voy a vender sueños. Te voy a mostrar números reales, un plan concreto y casos de personas en tu misma situación que ya lo lograron.

Si después de 15 minutos sientes que es más humo, simplemente no sigues. Sin drama. ¿Te parece justo?`;

P.OBJ_5 = `Entiendo, para no llenarte de información que no sea relevante para ti, cuéntame: ¿qué específicamente te gustaría saber?`;

P.OBJ_6 = `¡Totalmente entendible! Esa info es sensible y no tienes por qué compartirla acá.

Te pregunto porque con eso puedo ver si mi ayuda de verdad te sirve para liberar ese 10-15% de tu dinero para ahorro e inversión.

Si prefieres, podemos hacer una llamada muy corta de 5 minutos para que me des una idea general sin detalles exactos. ¿Te suena mejor?

O directamente agenda la llamada de diagnóstico de 30 minutos:
${CALENDAR_LINK}`;

P.OBJ_7 = `Entiendo que quieras saber el precio antes de agendar. Es válido.

Lo que pasa es que el programa no tiene un precio único. Depende de tu situación específica, tus objetivos y el nivel de acompañamiento que necesites.

Por eso la llamada es clave, en esos 30 minutos vamos a ver:
1️⃣ Si el Protocolo de Reconexión Financiera aplica a tu caso
2️⃣ Cuál sería tu plan personalizado
3️⃣ La inversión exacta según lo que necesitas

Lo que sí te puedo decir es que trabajo con profesionales que ganan entre $7M y $15M+ al mes, y la inversión está diseñada para que sea accesible en ese rango.

¿Te suena que agendemos y en esos 30 minutos lo vemos juntos?`;

P.OBJ_8 = `¡Claro que sí! Entiendo perfecto tu interés.

Mi "Protocolo de Reconexión Financiera" es un sistema de 8 semanas, muy personalizado para profesionales que ganan bien, pero su dinero se les está escapando mes a mes, donde les ayudo a liberar al menos un 15% de sus ingresos mensuales.

Para decirte si realmente puedo ayudarte a ti a liberar ese 15% o más de tus ingresos, necesito entender primero tu situación.

Te planteo que tengamos una llamada corta, vemos si es tu caso y, si hay fit, te explico todo con detalle. Y si no, igual te vas con un diagnóstico y mayor claridad. ¿Nos reunimos?`;

P.OBJ_9 = `Buena pregunta.

Lo más caro NO es la plata que se te está yendo (que son entre $500K y $1.5M al mes). Es el tiempo que pasa sin que esa plata trabaje para ti.

Cada año que sigues "ganando bien y viviendo mal" son $6M-$18M que pudieron estar invertidos. A 10 años, con interés compuesto, son más de $40M que se te escapan.

Y la trampa empeora con el tiempo, porque los hábitos se cementan.

¿Agendamos los 30 minutos y vemos exactamente cuánto te está costando cada mes?`;

// ---------------------------------------------------------------------------
// DESCALIFICACION CON VALOR
// ---------------------------------------------------------------------------
P.DESC_INGRESO = `Gracias por la sinceridad, {nombre}.

Con lo que me cuentas, creo que mi programa todavía no es el mejor fit para ti porque está diseñado para personas que ya están ganando más de $7M al mes — el método funciona ahí. Por debajo, la prioridad es subir el ingreso primero.

Igual, no quiero que te vayas sin nada. Te recomiendo este recurso sobre cómo enfocarte en aumentar tu ingreso antes de optimizar gastos:
${REELS.ingresos_bajos}

Te va a dar claridad sobre por dónde empezar. Impleméntalo y va a hacer una diferencia enorme.

Cualquier cosa, acá estoy. ¡Éxitos! 💪`;

P.DESC_ENDEUDAMIENTO = `Gracias por la sinceridad, {nombre}.

Con el nivel de endeudamiento que me cuentas, creo que mi programa todavía no es el mejor fit para ti porque está diseñado para liberar entre el 10% y 15% de tus ingresos para ahorro e inversión. Cuando la mayor parte se va en deudas, la prioridad #1 es bajar esa carga primero.

Igual, no quiero que te vayas sin nada. Te recomiendo este recurso sobre estrategia para salir de deudas:
${REELS.salir_de_deudas}

Te va a dar un mapa claro de por dónde empezar. Cuando tu endeudamiento esté en un nivel manejable, acá estoy para ayudarte a construir patrimonio.

¡Éxitos! 💪`;

P.DESC_URGENCIA = `Gracias por la sinceridad, {nombre}.

Con lo que me cuentas, creo que mi programa todavía no es el mejor fit para ti porque funciona mejor cuando hay urgencia real para ejecutarlo en 60 días.

Igual, no quiero que te vayas sin nada. Te recomiendo este recurso:
${REELS.ingresos_bajos}

Cuando estés listo para tomar acción, acá estoy. ¡Éxitos! 💪`;

// ---------------------------------------------------------------------------
// SOP DE RECUPERACION (bumps) — se disparan por tiempo, no por webhook.
// Se dejan definidos aca para la Fase 2 (cron). Ver guia de despliegue.
// ---------------------------------------------------------------------------
P.BUMP_1_CONVERSACION = `Hola {nombre}, quedé pendiente de tu respuesta para entender un poco mejor tu contexto y ver si realmente te puedo ayudar. 😊`;

P.BUMP_2_CONVERSACION = `{nombre}, no quiero ser un mensaje más que te estorba en el chat. 😊 ¿Seguimos hablando o prefieres que no te escriba más?`;

P.BUMP_3_CONVERSACION = `{nombre}, me alegra que hayas llegado hasta aquí, aunque no hayamos podido hablar. 😊 Te dejo este video que a mucha gente le ha servido un montón:
${REELS.nurture}

Si algo resuena contigo, ya sabes dónde encontrarme. ¡Éxitos!`;

P.BUMP_1_AGENDA = `{nombre}, ¿quedó alguna duda antes de agendar? 😄 ¿Se fue la señal?`;

P.BUMP_2_AGENDA = `¡Hola {nombre}! ¿Algún inconveniente? Ayer hablamos de esa plata que se va como 'sal y agua', ¿verdad? Mira, me quedan pocos cupos esta semana para que revisemos tu caso y veas cómo liberamos ese 15% de tu ingreso. Te dejo el link de nuevo:
${CALENDAR_LINK}

Si ya no te interesa, sin problema, me avisas. ¡Un abrazo! 😊`;

P.BUMP_3_AGENDA = `{nombre}, último mensaje, lo prometo. 😄 Te dejo este video antes de irme, creo que te va a servir:
${REELS.nurture}

Si en algún momento quieres retomar, aquí estoy. ¡Éxitos! 💪`;

// ---------------------------------------------------------------------------
// FALLBACK operativo (no del SOP) — si la escritura en Supabase falla.
// ---------------------------------------------------------------------------
P.FALLBACK_ERROR = `Dame un momento, {nombre}, ya te respondo por acá 😊`;
P.FALLBACK_ERROR_esExtension = true;

export const PLANTILLAS = P;

/** Mapa objecion_num -> plantilla. */
export const OBJECIONES = {
  1: P.OBJ_1, 2: P.OBJ_2, 3: P.OBJ_3, 4: P.OBJ_4, 5: P.OBJ_5,
  6: P.OBJ_6, 7: P.OBJ_7, 8: P.OBJ_8, 9: P.OBJ_9,
};

/**
 * Interpolacion simple. Solo {nombre} -- a proposito: cuanto menos dinamico
 * sea el copy, menos formas hay de romperlo.
 * Si no hay nombre usable cae a un saludo neutro en vez de dejar "{nombre}"
 * o un "Hola undefined" visible para el lead.
 */
export function render(plantilla, nombre) {
  if (!plantilla) return '';
  const limpio = (nombre || '').trim().split(/\s+/)[0] || '';
  // Evita nombres basura tipo "Lead 12345" que genera la propia base.
  const usable = /^lead$/i.test(limpio) || /^\d+$/.test(limpio) ? '' : limpio;
  return plantilla
    .replaceAll(', {nombre}', usable ? `, ${usable}` : '')
    .replaceAll('{nombre},', usable ? `${usable},` : '')
    .replaceAll('{nombre}', usable);
}
