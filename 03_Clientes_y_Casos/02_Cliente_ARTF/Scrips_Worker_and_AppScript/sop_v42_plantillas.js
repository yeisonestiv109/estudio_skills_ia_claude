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

/**
 * Link del calendario.
 *
 * Hoy apunta al calendario PERSONAL del fundador, a proposito: mientras se
 * prueba el bot no queremos leads de prueba cayendo en la agenda real de
 * Andres. Para pasar a produccion se cambia esta constante por CALENDAR_ARTF
 * y se corre la compuerta -- el corpus y los tests validan el cambio solo.
 */
export const CALENDAR_PRUEBAS = 'https://calendar.app.google/hMEGoX9T6DVsThft6';
export const CALENDAR_ARTF = 'https://calendar.app.google/iMW5LBbkcAvorypF9';

export const CALENDAR_LINK = CALENDAR_PRUEBAS;

/**
 * APERTURA PERSONALIZADA — el LLM enlaza lo que dijo el lead con la plantilla.
 *
 * HISTORIA, porque esto se apago una vez: nacio como "oracion_empatia" y el
 * fundador la apago el 3-sep ("parece mucha IA"). Se vuelve a encender el
 * 4-sep, pero NO es la misma decision: entonces el texto generado no lo
 * verificaba nadie. Ahora pasa por `verificarTextoGenerado`, que no existia.
 *
 * QUE GENERA Y QUE NO. Genera SOLO la frase de apertura; el cuerpo sigue siendo
 * la plantilla aprobada, literal. La forma es la que pidio el fundador:
 *
 *   "Entiendo que tu meta principal sea ahorrar, Marly."   <- generado
 *   ""                                                      <- linea en blanco
 *   "Lo que pasa es que nos especializamos en..."           <- plantilla literal
 *
 * POR QUE ESE CORTE Y NO MAS: la compuerta puede verificar que la apertura sea
 * SEGURA (sin links, sin voseo, sin promesas, sin cifras inventadas), pero NO
 * puede verificar que sea CIERTA. Si el LLM reescribiera el cuerpo, nada
 * comprobaria que lo que dice del programa es verdad. Dejando el cuerpo intacto,
 * todo lo que afirma el bot sobre el programa sigue saliendo de copy aprobado.
 */
export const EMPATIA_HABILITADA = true;

/**
 * ===========================================================================
 * ESCALERA DE REPREGUNTAS — un peldaño más antes de escalar (4-sep-2026)
 * ===========================================================================
 * Decision del fundador: el bot escalaba a un humano demasiado pronto por
 * ambiguedad. En vez de escalar al primer "no entendi", reformula UNA vez con
 * una pregunta mas facil de contestar, y solo si ahi tampoco se puede leer,
 * pasa a un humano.
 *
 * Los reintentos NO los redacta el LLM: cada peldaño es una plantilla de esta
 * biblioteca. Si el LLM redactara las reformulaciones volveriamos exactamente
 * a lo que se rechazo en la auditoria del 4-sep.
 *
 * ⚠️ APAGADA hasta que Javier apruebe el copy nuevo (ver COPY_PENDIENTE_APROBACION).
 * Encenderla es cambiar este false por true y desplegar.
 */
export const ESCALERA_REPREGUNTAS_HABILITADA = false;

/**
 * Perilla unica para TODO el copy que aun no aprueba el fundador.
 *
 * Cualquier plantilla marcada con `_pendienteAprobacion` solo sale al lead con
 * esto en true. Existe porque una plantilla nueva entra sola a la lista blanca
 * del verificador (se construye desde `P`), asi que sin esta puerta el copy sin
 * revisar llegaria a leads reales pasando la compuerta en verde.
 *
 * Encenderla es cambiar este false por true, y hacerlo DESPUES de que Javier
 * revise `COPY_PENDIENTE_APROBACION`.
 */
export const COPY_PENDIENTE_HABILITADO = false;

/**
 * Catch-all del LLM (decision del fundador, 4-sep-2026).
 *
 * Cuando el mensaje del lead no encaja en ningun camino del guion, el LLM
 * redacta UNA respuesta empatica corta apoyandose en la informacion de las
 * objeciones, y despues se reenvia la pregunta pendiente.
 *
 * ⚠️ Es la unica pieza de texto libre que ve el lead. No se puede verificar
 * contra la biblioteca (no hay plantilla que comparar), asi que pasa por
 * `verificarTextoGenerado`: nada de links, de datos de contacto, de voseo, de
 * tercera persona, de lexico prohibido, ni de afirmar un agendamiento. Si falla
 * cualquiera de esas, se descarta y queda solo el reencauce determinista.
 *
 * El fundador pidio probarlo asi y avisara si se quita.
 */
export const CATCHALL_LLM_HABILITADO = true;

/**
 * ===========================================================================
 * AUTO-RECUPERACION DE HANDOFF (fundador, 4-sep-2026)
 * ===========================================================================
 * QA real: el bot escalo a la lead y 40 segundos despues ella escribio "pero
 * igual quiero seguir, me da 40%". El bot ya estaba mudo y se perdio la venta.
 *
 * Ahora, si el lead pide claramente continuar (`recupera_handoff` del LLM), el
 * bot puede sacarlo del handoff y retomar el guion.
 *
 * ⚠️ TRES RAZONES QUEDAN FUERA, Y NO SE NEGOCIAN:
 *  - `crisis_emocional`: es la regla de MAXIMA prioridad del diseño y cubre
 *    señales de duelo, ansiedad y autolesion. Alguien en crisis que escribe
 *    "no, sigamos" necesita a una persona, no que el bot siga vendiendo.
 *  - `ex_cliente`: un ex alumno que vuelve es una conversacion comercial
 *    distinta y no hay copy para ella.
 *  - `agendamiento_manual_pendiente`: el Setter tiene que agendar a mano. Que
 *    el bot retome no hace aparecer la reunion.
 *
 * `contenido_hostil` SI es recuperable: tras arreglar su clasificacion (la
 * frustracion ya no cuenta como hostilidad) esa razon significa agresion real,
 * y que alguien se disculpe y quiera seguir es normal en ventas. El Setter ve
 * todo en el log igual.
 */
export const HANDOFF_NO_RECUPERABLE = new Set([
  'crisis_emocional',
  'ex_cliente',
  'agendamiento_manual_pendiente',
]);

/** Centinela que la RPC entiende como "limpia el handoff". */
export const LIMPIAR_HANDOFF = '__LIMPIAR__';

export const REELS = {
  ingresos_bajos: 'https://www.instagram.com/reel/DJDejvjtfzH/',
  salir_de_deudas: 'https://www.instagram.com/reel/DMmAfHqt3a7/',
  tarjetas_credito: 'https://www.instagram.com/p/DIZ3HNwMLky/',
  nurture: 'https://www.instagram.com/reel/DX73ACPNvRV/',
};

/** Umbrales de los 3 filtros del SOP V4.2. */
export const UMBRALES = {
  // ───────────────────────────────────────────────────────────────────────
  // FILTRO 1 — ingreso. Bajado de 7M a 6M por el fundador (4-sep-2026).
  //
  // ⚠️ EL COPY TODAVIA DICE $7M. `M1_PEDIR_RANGO` pregunta "¿estas entre $7M y
  // $15M?" y `DESC_INGRESO` dice "diseñado para quien gana mas de $7M". Con el
  // umbral en 6M, la banda 6M-7M es zona de trampa: el lead califica pero
  // contesta NO al rango porque el texto le pregunta por otra cifra.
  //
  // Por eso un "No" al rango NO descalifica: se le pide la cifra y se decide
  // sobre el numero real (ver el case M1_RANGO_PREGUNTADO). Descalificar sobre
  // un "No" que es ambiguo respecto al umbral violaria la regla dura V4.1.
  //
  // El copy con 6M ya esta escrito y espera aprobacion de Javier
  // (COPY_PENDIENTE_APROBACION). Al aprobarse, ese "No" ya sera inequivoco.
  // ───────────────────────────────────────────────────────────────────────
  INGRESO_MINIMO: 6_000_000,
  INGRESO_BORDERLINE_BAJO: 4_000_000,

  // Cifra que se asume cuando el lead confirma el rango sin dar numero.
  // Es el PISO de lo que el propio lead afirmo ("si, estoy entre $7M y $15M"),
  // no una invencion: sale del texto de M1_PEDIR_RANGO. Si ese copy cambia a
  // 6M, esta constante tiene que cambiar con el -- hay un test que lo exige.
  INGRESO_ASUMIDO_POR_RANGO: 7_000_000,

  // ───────────────────────────────────────────────────────────────────────
  // FILTRO 2 — el criterio real es el REMANENTE, no el porcentaje.
  //
  // remanente = ingreso × (1 − deuda%)
  //
  // Reemplaza al tope condicional por ingreso de V4.0/V4.2. Lo que le importa
  // al negocio no es que deba poco, sino que le QUEDE con qué trabajar.
  //
  // Ojo con el acoplamiento: con ingreso >= 6M, el remanente de 2.5M solo
  // muerde por encima del ~58% de deuda. Por debajo de ese punto el filtro es
  // inoperante por construccion, no por error.
  // ───────────────────────────────────────────────────────────────────────
  REMANENTE_MINIMO: 2_500_000,
  // Umbral que separa "le sobra poco porque debe mucho" (se pregunta que tipo
  // de deuda es: la hipotecaria no cuenta igual) de "le sobra poco y punto".
  ENDEUDAMIENTO_PARA_BORDERLINE: 50,
  SMLV_2026: 1_420_000,

  // Escalamiento por resistencia. El SOP V4.2 de Javier dice 2 (misma objecion
  // repetida) y 3 (objeciones acumuladas); el fundador los subio a 3 y 4 el
  // 4-sep-2026 para que el bot aguante una ronda mas antes de pasar a un humano.
  // ⚠️ ESTO CONTRADICE EL PDF DEL CLIENTE — hay que comentarselo a Javier.
  // Volver a 2 y 3 es cambiar estos dos numeros.
  RESISTENCIA_MISMA_OBJECION: 3,
  RESISTENCIA_ACUMULADA: 4,
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
// La pregunta del rango tiene DOS variantes (QA en vivo, 4-sep-2026).
//
// El QA mostro el problema: a una lead que simplemente OLVIDO decir su salario
// se le respondia con el texto defensivo ("Te pregunto porque el proceso
// funciona mejor para personas que..."), que esta escrito para desactivar una
// objecion. Sin objecion delante, eso se lee a la defensiva y suena raro.
//
//  - SIMPLE: el lead no objeto, solo no dio la cifra. Se pregunta y ya.
//  - DEFENSIVA: el lead SI objeto por privacidad. Ahi el "te pregunto porque..."
//    cumple su funcion: justifica por que se insiste tras un "no quiero decirlo".
P.M1_PEDIR_RANGO_SIMPLE = `Entiendo {nombre}. Para validar si mi programa aplica a ti, ¿puedes indicarme si tu salario se encuentra entre $7M y $15M COP o más?`;

P.M1_PEDIR_RANGO = `Te pregunto porque el proceso funciona mejor para personas que ganan entre $7M y $15M COP o más al mes. ¿Estás en ese rango?`;

/** Escenario E (★ V4.1): ingreso ambiguo, sin cifra clara. NUNCA descalificar aca. */
// NOTA (4-sep-2026): se escribio copy alineado al umbral de $6M y el fundador
// decidio NO usarlo. El texto del rango sigue diciendo $7M y un "No" descalifica
// directo, asumiendo comercialmente la perdida de la banda $6M-$7M. Queda
// anotado aca para que no se vuelva a proponer como si fuera un descuido.

// Segundo dato del borderline. El tipo de deuda solo no alcanza: la regla del
// fundador tambien acepta al lead si RECTIFICA que le sobran >= $2.5M.
P.M2_PEDIR_SOBRANTE = `Y una última cosa para no sacar conclusiones: después de pagar todo eso, ¿cuánto te queda libre al mes, más o menos?`;
P.M2_PEDIR_SOBRANTE_pendienteAprobacion = true;

// --- Peldaños de la escalera de repreguntas (PENDIENTES DE APROBACION) ---
//
// Se midio cuantas veces pregunta cada filtro antes de escalar, en vez de
// asumirlo: M1 y M2 YA preguntaban dos veces (M1_ENVIADO -> M1_INGRESO_AMBIGUO
// -> handoff; M2_ENVIADO -> M2_NO_SABE -> handoff). Los unicos que escalaban al
// PRIMER intento eran M4 y M5. Por eso la escalera son 2 peldaños, no 5.

// Segundo intento del Filtro 3. Cambia el marco temporal en vez de repetir la
// misma pregunta, que es lo que se siente como bot roto.
P.M4_URGENCIA_REINTENTO = `Te lo pregunto de otra forma, {nombre}: si tuvieras el mapa claro esta semana, ¿empezarías ya, o lo dejarías para más adelante?`;
P.M4_URGENCIA_REINTENTO_pendienteAprobacion = true;

// Segundo intento tras el pitch. Le da salida honesta para que un "no" tambien
// sea una respuesta valida y no un lead atascado.
P.M5_PITCH_REINTENTO = `Para no darte vueltas, {nombre}: ¿te sirve que reservemos esos 30 minutos? Si no es el momento, me lo dices sin problema.`;
P.M5_PITCH_REINTENTO_pendienteAprobacion = true;

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

/**
 * ORDEN DEL TURNO DEL CIERRE (decision del fundador, 3-sep-2026):
 *   1. M7 (asistencia)  2. M6_SALUDO  3. M6_CONFIRMAME  4. el link, solo
 *
 * M7 pasa ANTES del link aunque V4.2 lo numere despues. Dos razones:
 *  - Su propio texto dice "antes de que separes tu espacio", asi que leerlo
 *    antes del link es mas natural que despues.
 *  - Si va en un turno aparte puede no enviarse NUNCA: el lead agenda y no
 *    vuelve a escribir. En la primera prueba en vivo, M7 no se envio ni una vez.
 * El link sigue siendo la ultima burbuja y va solo -- la regla dura se respeta.
 */

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
// BLINDAJE DEL SHOW-UP — RETIRADO (3-sep-2026)
// ---------------------------------------------------------------------------
// Se quito tras verlo en vivo. Dos razones del fundador, ambas validas:
//  1. NO esta en el SOP V4.2 -- venia del proyecto de Javier, y yo lo presente
//     de forma que se leyo como si fuera parte del playbook del cliente.
//     Verificado: "firmes"/"blindaje" no aparecen en el PDF de la V4.2.
//  2. El % de show-up ya se mide donde corresponde: el Closer tiene un boton
//     en su dashboard para marcar si el lead asistio. Preguntarselo al lead
//     era, en sus palabras, "innecesario y una mala practica".

// ---------------------------------------------------------------------------
// ACLARACION DE INGRESO REMANENTE — aprendizaje de produccion (SOP-05 #2)
// ---------------------------------------------------------------------------
// Patron real: el lead responde "me quedan $5M" o "menos de $7M" refiriendose
// al dinero que le SOBRA despues de gastos, no a su ingreso total. Descalificar
// ahi es perder un lead bueno. Copy literal del proyecto de Javier.
P.M1_ACLARAR_REMANENTE = `Solo para que estemos en la misma página: ¿esos que mencionas son tu ingreso total al mes, o lo que te queda después de cubrir gastos? Te pregunto porque cambia mucho el análisis.`;


// ---------------------------------------------------------------------------
// TROCEO DE LOS MENSAJES LARGOS (3-sep-2026)
// ---------------------------------------------------------------------------
// Fundamento: knowledge-base/04-voz-y-tono.md del proyecto de Javier --
// "Si la respuesta tiene mas de ~80 palabras o mas de 4 parrafos, dividela en
// 2 o 3 mensajes separados", y marca el pitch como "al menos 2 mensajes
// (oferta + filtro/CTA)".
//
// Se parten POR CODIGO desde la plantilla completa, no reescribiendo el texto:
// asi es imposible que las partes se desincronicen del original.
const partir = (texto, corte) => {
  const i = texto.indexOf(corte);
  if (i < 0) throw new Error(`partir(): no se encontro el corte "${corte}"`);
  return [texto.slice(0, i).trim(), texto.slice(i).trim()];
};

[P.M2_P1, P.M2_P2] = partir(P.M2, 'Para calcularlo suma');

// Solo la PREGUNTA de M1, sin el saludo de apertura. Se usa para reencarrilar a
// un lead que se desvio (repitio la palabra clave, o puso una objecion): repetir
// "¡Hola {nombre}! 👋 Llegas al lugar correcto..." a mitad de conversacion se
// lee como si el bot hubiera perdido el hilo y estuviera arrancando de cero.
P.M1_PREGUNTA = P.M1_GENERAL.split('\n\n').pop().trim();
[P.M4_P1, P.M4_P2] = partir(P.M4, 'Última pregunta');
[P.M5_P1, P.M5_P2] = partir(P.M5, 'Y ojo:');

// ---------------------------------------------------------------------------
// ACUSE cuando el lead dice "listo" pero la reunion AUN NO esta vinculada
// ---------------------------------------------------------------------------
// Aprobado por el fundador (3-sep-2026). El bot NO da el cierre por hecho: el
// que vincula la reunion es el Setter desde el dashboard. Hasta que la base
// confirme la reunion, el bot solo acusa recibo y se calla -- nunca le confirma
// al lead algo que la base no respalda.
P.ACUSE_SIN_REUNION = `¡Perfecto, {nombre}! 🙌`;

// ---------------------------------------------------------------------------
// EL LEAD NO ENCUENTRA HORARIOS DISPONIBLES
// ---------------------------------------------------------------------------
// Copy del proyecto de Javier (scripts/m5-cierre-agendamiento.md, "Caso
// especial"), con una correccion: el original dice "Contame", que es VOSEO y
// viola su propia Regla #2 de tuteo colombiano estricto. Aparece asi en 3 de
// sus archivos. Aca va corregido a "Cuentame".
//
// Se pregunta la franja Y se escala al Setter en el mismo turno, para que el
// caso le llegue ya con el horario que el lead prefiere.
P.SIN_HORARIOS = `Entendido, {nombre}. Vamos a revisar qué espacios se liberan y te confirmamos para agendarnos.

Cuéntame, ¿qué fecha y bloques de horarios te quedan bien?`;

// ---------------------------------------------------------------------------
// RETORNO DE UN LEAD DESCALIFICADO (3-sep-2026)
// ---------------------------------------------------------------------------
// Caso real reportado por el fundador: "me ha pasado que leads que ya he
// descalificado vuelven y llegan". Antes el bot no les respondia NADA salvo que
// soltaran una cifra que los recalificara.
//
// Como si guardamos POR QUE se descarto (motivo_perdida_id), se puede preguntar
// exactamente por eso. Copy nuevo, aprobado por el fundador -- las preguntas de
// seguimiento reusan plantillas ya aprobadas (M1_PEDIR_CIFRA / M2 / M4).
P.RETORNO_INGRESO = `¡Hola de nuevo, {nombre}! 👋 La última vez que hablamos, tu ingreso todavía no estaba en el rango donde mi método funciona. ¿Cambió algo desde entonces?`;

P.RETORNO_ENDEUDAMIENTO = `¡Hola de nuevo, {nombre}! 👋 La última vez que hablamos, tus deudas se llevaban buena parte de tu ingreso. ¿Lograste bajar esa carga?`;

P.RETORNO_URGENCIA = `¡Hola de nuevo, {nombre}! 👋 La última vez me contaste que esto era algo para más adelante. ¿Ya es prioridad para ti?`;

/** Cuando no quedo registrado el motivo del descarte. */
P.RETORNO_GENERICO = `¡Hola de nuevo, {nombre}! 👋 Ya habíamos hablado antes. ¿Cambió algo en tu situación desde entonces?`;

/** Responde que no cambio nada -- se cierra sin insistir. */
P.RETORNO_SIN_CAMBIO = `Entendido, {nombre}. Cuando la situación cambie, acá estoy. ¡Éxitos! 💪`;

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

// Reordenada (aprobado por el fundador, 2-sep-2026): el link va obligatoriamente
// en burbuja aparte, asi que la frase que lo anuncia se movio al final para que
// no quede colgando. Mismas frases del SOP, distinto orden.
P.OBJ_3 = `Dale, sin problema.

Los espacios se llenan rápido porque solo tomo un número limitado de llamadas por semana. Si te interesa, mejor reservar el espacio ahora y si pasa algo lo reagendas.

¿Listo?

Igual te dejo el link por acá por si te decides:
${CALENDAR_LINK}`;

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
// Las 3 reordenadas igual que la Objecion 3 (aprobado por el fundador,
// 2-sep-2026): la frase que presenta el recurso queda de ultima, pegada al
// link, para que no quede anunciando algo que todavia no llega.
P.DESC_INGRESO = `Gracias por la sinceridad, {nombre}.

Con lo que me cuentas, creo que mi programa todavía no es el mejor fit para ti porque está diseñado para personas que ya están ganando más de $7M al mes — el método funciona ahí. Por debajo, la prioridad es subir el ingreso primero.

Igual, no quiero que te vayas sin nada. Cualquier cosa, acá estoy. ¡Éxitos! 💪

Te recomiendo este recurso sobre cómo enfocarte en aumentar tu ingreso antes de optimizar gastos. Te va a dar claridad sobre por dónde empezar, impleméntalo y va a hacer una diferencia enorme:
${REELS.ingresos_bajos}`;

P.DESC_ENDEUDAMIENTO = `Gracias por la sinceridad, {nombre}.

Con el nivel de endeudamiento que me cuentas, creo que mi programa todavía no es el mejor fit para ti porque está diseñado para liberar entre el 10% y 15% de tus ingresos para ahorro e inversión. Cuando la mayor parte se va en deudas, la prioridad #1 es bajar esa carga primero.

Igual, no quiero que te vayas sin nada. Cuando tu endeudamiento esté en un nivel manejable, acá estoy para ayudarte a construir patrimonio. ¡Éxitos! 💪

Te recomiendo este recurso sobre estrategia para salir de deudas. Te va a dar un mapa claro de por dónde empezar:
${REELS.salir_de_deudas}`;

P.DESC_URGENCIA = `Gracias por la sinceridad, {nombre}.

Con lo que me cuentas, creo que mi programa todavía no es el mejor fit para ti porque funciona mejor cuando hay urgencia real para ejecutarlo en 60 días.

Igual, no quiero que te vayas sin nada. Cuando estés listo para tomar acción, acá estoy. ¡Éxitos! 💪

Te recomiendo este recurso:
${REELS.ingresos_bajos}`;

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

/**
 * Copy que TODAVIA no aprobo el fundador.
 *
 * Existe porque una plantilla nueva entra sola a la lista blanca del
 * verificador (se construye desde `P`), asi que sin esto el copy sin aprobar
 * pasaria la compuerta en silencio. La lista esta fijada por un test: agregar
 * copy pendiente sin declararlo aca pone la compuerta en rojo.
 *
 * Al aprobarse: se quita la marca `_pendienteAprobacion` de la plantilla.
 */
export const COPY_PENDIENTE_APROBACION = Object.keys(P)
  .filter((k) => k.endsWith('_pendienteAprobacion') && P[k])
  .map((k) => k.replace('_pendienteAprobacion', ''))
  .sort();

/**
 * ===========================================================================
 * PLAYBOOK DE OBJECIONES — UNA SOLA TABLA DE DATOS
 * ===========================================================================
 * Antes esto vivia en 4 sitios sueltos (`OBJECIONES`, `OBJECIONES_HABILITADAS`,
 * `CORTE_PRE_PITCH`, y la lista de disparadores hardcodeada en el prompt del
 * Worker). Agregar una objecion obligaba a tocar los cuatro y era facil olvidar
 * uno -- que es exactamente como la Objecion 1 termino cerrando agenda antes
 * del pitch durante dias.
 *
 * AHORA: agregar una objecion es agregar UNA entrada aca. Todo lo demas se
 * deriva: el mapa, el Set de habilitadas, las variantes sin cierre de agenda y
 * la lista de disparadores que ve el clasificador. **Cero logica JS que tocar.**
 *
 * Campos:
 *   id            numero de la objecion en el SOP.
 *   nombre        etiqueta corta, para logs y tests.
 *   disparador    como se le describe al clasificador. ESTE TEXTO VA AL PROMPT.
 *   plantilla     copy aprobado. Vive en codigo a proposito: la compuerta de
 *                 cumplimiento construye su lista blanca desde aca, offline,
 *                 en cada commit. Si esto viviera en una tabla remota, la
 *                 compuerta 3 dejaria de poder verificar el texto real.
 *   habilitada    si el bot la contesta solo. Si no, va al Setter.
 *   cortePrePitch cuantos parrafos FINALES se recortan cuando la objecion cae
 *                 antes del pitch. Son los que cierran agenda: ofrecerle la
 *                 llamada a alguien que no paso los filtros rompe el embudo.
 *                 Se recorta POR CODIGO -- nunca se reescribe copy.
 *   preguntaPropia  la plantilla ya termina preguntando algo. Si es true no se
 *                 le pega ademas la pregunta pendiente: serian dos preguntas
 *                 seguidas y el lead no sabe cual contestar.
 */
export const PLAYBOOK_OBJECIONES = [
  { id: 1, nombre: 'es_gratis',        disparador: '1=¿es gratis?/¿me van a vender algo?',
    plantilla: P.OBJ_1, habilitada: true,  cortePrePitch: 1, preguntaPropia: false,
    fasesPermitidas: ['M5', 'M6', 'M7', 'M8'],
    cuentaComoResistencia: false },

  { id: 2, nombre: 'no_tengo_tiempo',  disparador: '2=no tengo tiempo',
    plantilla: P.OBJ_2, habilitada: true,  cortePrePitch: 1, preguntaPropia: false,
    fasesPermitidas: ['M5', 'M6'],
    cuentaComoResistencia: true },

  { id: 3, nombre: 'dejame_pensarlo',  disparador: '3=dejame pensarlo',
    plantilla: P.OBJ_3, habilitada: true,  cortePrePitch: 2, preguntaPropia: false,
    fasesPermitidas: ['M5', 'M6'],
    cuentaComoResistencia: true },

  { id: 4, nombre: 'ya_probe',         disparador: '4=ya probe cosas asi/desconfia',
    plantilla: P.OBJ_4, habilitada: true,  cortePrePitch: 1, preguntaPropia: false,
    fasesPermitidas: 'TODAS',
    cuentaComoResistencia: true },

  // La 5 es UNA sola frase y esa frase ES la pregunta ("¿que te gustaria
  // saber?"). No hay parrafo de cierre que recortar, y pegarle la pregunta
  // pendiente dejaria dos preguntas seguidas.
  { id: 5, nombre: 'necesito_info',    disparador: '5=necesito mas informacion',
    plantilla: P.OBJ_5, habilitada: true,  cortePrePitch: 0, preguntaPropia: true,
    fasesPermitidas: 'TODAS',
    cuentaComoResistencia: false },

  { id: 6, nombre: 'info_sensible',    disparador: '6=info muy sensible para DM',
    plantilla: P.OBJ_6, habilitada: true,  cortePrePitch: 2, preguntaPropia: false,
    fasesPermitidas: ['M1', 'M2', 'M3', 'M4'],
    cuentaComoResistencia: true },

  { id: 7, nombre: 'precio_programa',  disparador: '7=¿cuanto cuesta el PROGRAMA/mentoria?',
    plantilla: P.OBJ_7, habilitada: true,  cortePrePitch: 1, preguntaPropia: false,
    fasesPermitidas: 'TODAS',
    cuentaComoResistencia: false },

  { id: 8, nombre: 'que_es_protocolo', disparador: '8=¿que es el Protocolo de Reconexion?',
    plantilla: P.OBJ_8, habilitada: true,  cortePrePitch: 1, preguntaPropia: false,
    fasesPermitidas: 'TODAS',
    cuentaComoResistencia: false },

  // Excepcion fundamentada del SOP: la 9 la predice justo en M4 y su
  // bifurcacion oficial contempla que el lead acepte agendar ahi mismo. No
  // lleva link y cierra con su propia pregunta.
  { id: 9, nombre: 'por_que_ahora',    disparador: '9=¿por que resolverlo ahora?',
    plantilla: P.OBJ_9, habilitada: true,  cortePrePitch: 0, preguntaPropia: true,
    fasesPermitidas: ['M4', 'M5'],
    cuentaComoResistencia: false },
];

/** Acceso por id, para no repetir el `.find` en cada sitio. */
/**
 * ===========================================================================
 * FASES DEL EMBUDO — el puente entre la numeracion del fundador y las etapas
 * ===========================================================================
 * El fundador razona en M1..M8. El router tiene 20 etapas cuyos nombres NO
 * coinciden con esa numeracion, y confundirlas es una fuente de bugs garantizada.
 * Este mapa es el unico sitio donde se traduce.
 *
 * OJO con dos desalineaciones reales:
 *  - Su "M6" (envio del link) es nuestra `M7_ENVIADO`: en nuestro flujo la
 *    pregunta del acompañante y el link van en el MISMO turno, con el link de
 *    ultimo. Se decidio asi tras una prueba en vivo donde la pregunta nunca
 *    llegaba a enviarse, y el fundador confirmo el 4-sep que se mantiene.
 *  - Su "M8" (despedida) es nuestra `CIERRE_PRECALL` / `M7_ESPERANDO_VINCULO`.
 */
export const FASE_POR_ETAPA = {
  M1_ENVIADO: 'M1', M1_INGRESO_AMBIGUO: 'M1', M1_RANGO_PREGUNTADO: 'M1', M1_ACLARAR_REMANENTE: 'M1',
  M2_ENVIADO: 'M2', M2_NO_SABE: 'M2', M2_BORDERLINE: 'M2',
  M3_ENVIADO: 'M3', M3_RECONDUCIR: 'M3',
  M4_ENVIADO: 'M4', M4_URGENCIA_REINTENTO: 'M4',
  M5_ENVIADO: 'M5', M5_PITCH_REINTENTO: 'M5',
  M6_ENVIADO: 'M6',
  M7_ENVIADO: 'M6',            // aca sale el link -> es su M6
  M7_ESPERANDO_VINCULO: 'M8',  // ya agendo, esperando vinculo -> su M8
  CIERRE_PRECALL: 'M8',
  RETORNO_PREGUNTA: 'M1',      // un descalificado que vuelve arranca de nuevo
};

/** La fase del embudo en la que esta el lead, o null si la etapa no mapea. */
export function faseDeEtapa(etapa) {
  return FASE_POR_ETAPA[etapa] ?? null;
}

/**
 * ¿Puede el bot contestar esta objecion estando en esta etapa?
 *
 * La matriz la definio el fundador con la experiencia del Setter humano
 * (4-sep-2026): p.ej. "no tengo tiempo" solo tiene sentido cuando ya se le
 * propuso una llamada, y "esa info es sensible" solo mientras se le piden datos.
 * Una objecion fuera de su fase NO se contesta con su plantilla: se reencauza
 * (ver `manejarObjecion`), porque casi siempre significa que el clasificador
 * leyo mal, no que el lead objete eso de verdad.
 */
export function objecionPermitidaEn(objecionNum, etapa) {
  const o = OBJECION_POR_ID.get(Number(objecionNum));
  if (!o) return false;
  if (o.fasesPermitidas === 'TODAS') return true;
  const fase = faseDeEtapa(etapa);
  // Sin etapa (lead nuevo) no hay objecion que contestar todavia.
  if (!fase) return false;
  return o.fasesPermitidas.includes(fase);
}

/** Acceso por id, para no repetir el `.find` en cada sitio. */
export const OBJECION_POR_ID = new Map(PLAYBOOK_OBJECIONES.map((o) => [o.id, o]));

/** Mapa objecion_num -> plantilla completa (post-pitch). */
export const OBJECIONES = Object.fromEntries(
  PLAYBOOK_OBJECIONES.map((o) => [o.id, o.plantilla]),
);

/**
 * ===========================================================================
 * PERILLA DE ALCANCE — cuales objeciones contesta el bot POR SI MISMO.
 * ===========================================================================
 * Se deriva del campo `habilitada` de PLAYBOOK_OBJECIONES. Las que no lo esten
 * se entregan al Setter con razon `objecion_no_habilitada` -- distinta a
 * proposito de `objecion_fuera_playbook`, que significa "esto no es ninguna de
 * las del playbook y el bot no sabe que es".
 *
 * HISTORIA: arranco en {1,2,3,6,9} como decision de riesgo del fundador
 * (2-sep-2026) para la primera prueba con leads reales. El 4-sep se abrieron
 * las 9, ya con la compuerta cubriendo el cierre de agenda antes del pitch
 * para TODAS (antes solo se verificaba en las que llevaban link, y por eso la
 * Objecion 1 estuvo cerrando agenda en M1 sin que nadie lo viera).
 *
 * PARA AMPLIAR O CERRAR: cambia `habilitada` en la tabla. Eso es todo.
 */
export const OBJECIONES_HABILITADAS = new Set(
  PLAYBOOK_OBJECIONES.filter((o) => o.habilitada).map((o) => o.id),
);

/**
 * La lista de disparadores que ve el clasificador, generada desde la tabla.
 *
 * Antes esto era un string hardcodeado en el prompt del Worker, o sea un
 * CUARTO sitio que actualizar al agregar una objecion. Ahora sale de la misma
 * fuente que el resto: agregar una entrada actualiza el prompt solo.
 */
export const DISPARADORES_OBJECIONES =
  PLAYBOOK_OBJECIONES.map((o) => o.disparador).join(' ');

/**
 * ¿Esta objecion es RESISTENCIA, o es CURIOSIDAD?
 *
 * QA en vivo del 4-sep-2026, y es el hallazgo que mas cuesta ver: una lead
 * pregunto, en cuatro mensajes seguidos, "¿es gratis?", "quiero saber mas del
 * metodo", "¿cuanto cuesta el programa?" y "lo voy a pensar". El bot conto
 * cuatro objeciones consecutivas y la escalo por `resistencia_acumulada`.
 * Treinta segundos despues escribio "pero mejor si, agendemos" -- y el bot ya
 * estaba en silencio porque el handoff estaba activo.
 *
 * Las tres primeras NO eran resistencia: eran señales de COMPRA. La regla se
 * llama "resistencia_acumulada" pero estaba contando curiosidad. Un lead
 * interesado que hace cuatro preguntas se veia igual que uno que se resiste.
 *
 * Desde aca, solo las que de verdad frenan el embudo cuentan para el tope.
 */
export const OBJECION_ES_RESISTENCIA = new Set(
  PLAYBOOK_OBJECIONES.filter((o) => o.cuentaComoResistencia).map((o) => o.id),
);

/** Objeciones cuya plantilla ya cierra con su propia pregunta. */
export const OBJECIONES_CON_PREGUNTA_PROPIA = new Set(
  PLAYBOOK_OBJECIONES.filter((o) => o.preguntaPropia).map((o) => o.id),
);

/**
 * Por que se sumaron la 6 y la 9 (3-sep-2026, tras la primera prueba):
 *
 *  - La 6 ("esa info es muy sensible para DM") aparece POR DEFINICION cuando se
 *    pide el ingreso o el endeudamiento, o sea en M1/M2. Es lo que respondio
 *    Marly en la prueba real ("es un dato delicado para compartir por aqui") y
 *    el bot la leyo como "ingreso ambiguo". No es una objecion de venta: es
 *    parte de calificar, y su script reencuadra y ofrece la llamada.
 *
 *  - La 9 ("¿por que resolverlo ahora?") es la unica que el SOP predice DENTRO
 *    del flujo normal: dice literal "aparece en Mensaje 4 (urgencia)".
 *
 * Siguen fuera de alcance las de venta pura -- 4 (ya probe cosas asi),
 * 5 (necesito mas info), 7 (precio) y 8 (que es el Protocolo) -- porque llevan
 * a terreno de precio, garantias y credibilidad, donde conviene un humano.
 */

/**
 * Parte una plantilla que trae un link embebido en DOS burbujas: todo el texto
 * primero, el link solo al final.
 *
 * Por que existe: varias plantillas del SOP (Objeciones 2/3/6, las 3
 * descalificaciones, los bumps) traen el link en medio del parrafo, con texto
 * DESPUES. Eso es exactamente el bug que el equipo de Javier documento como
 * confirmado en produccion: Instagram concatena el link con el texto siguiente
 * y lo deja invalido. Su regla es explicita -- "todo el contexto que acompaña
 * al link va ANTES del link" y "aplica a cualquier link futuro".
 *
 * Se hace por codigo y no reescribiendo cada plantilla a mano para que NINGUNA
 * frase aprobada se pierda ni se reescriba: se conservan todas, en su orden, y
 * solo se mueve el link al final en su propia burbuja.
 *
 * @returns {string[]} 1 burbuja si no habia link, 2 si lo habia.
 */
export function partirEnBurbujas(plantilla) {
  const texto = String(plantilla || '');
  const urls = texto.match(/https?:\/\/\S+/g);
  if (!urls || urls.length === 0) return [texto];

  const link = urls[urls.length - 1];
  const sinLink = texto
    .split(/https?:\/\/\S+/)
    .join(' ')
    .replace(/[ \t]+/g, ' ')
    .replace(/ *\n */g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/\s+([,.:;!?])/g, '$1')
    .trim();

  return sinLink ? [sinLink, link] : [link];
}

// ---------------------------------------------------------------------------
// OBJECIONES ANTES DEL PITCH — sin cierre de agenda (3-sep-2026)
// ---------------------------------------------------------------------------
// Bug de negocio detectado al habilitar la Objecion 6 en M1: su plantilla
// remata con "O directamente agenda la llamada de diagnostico de 30 minutos:"
// + el link. Eso le entrega la llamada a un lead que TODAVIA NO ha pasado los
// filtros de endeudamiento, dolor y urgencia. Rompe el embudo.
//
// No es solo la 6: de las habilitadas, la 2, la 3 y la 6 cargan el link.
//
// Las variantes se construyen POR CODIGO recortando los ultimos parrafos de la
// plantilla aprobada -- no se reescribe copy. Asi es imposible que se
// desincronicen del original si el copy cambia.
//
// Cuantos parrafos finales se quitan de cada una:
//   2 -> 1 (el parrafo que anuncia el link)
//   3 -> 2 (el link y el "¿Listo?", que es un cierre de agenda: dejarlo pegado
//           antes de la pregunta pendiente confunde al lead con dos preguntas)
//   6 -> 2 (ademas del link, la oferta de "una llamada corta de 5 minutos",
//           que tambien es un cierre de agenda prematuro)
//
// La Objecion 9 NO lleva variante a proposito: no tiene link, y el SOP la
// predice justo en M4 con su propio cierre ("¿Agendamos los 30 minutos...?").
// Su bifurcacion oficial contempla que el lead acepte agendar ahi mismo.
function sinCierreDeAgenda(plantilla, parrafos) {
  if (!parrafos) return plantilla;
  const partes = plantilla.split('\n\n');
  if (partes.length <= parrafos) return plantilla;
  return partes.slice(0, -parrafos).join('\n\n').trim();
}

/**
 * Objecion -> version sin cierre de agenda, para las etapas de calificacion.
 * El recorte de cada una sale de `cortePrePitch` en PLAYBOOK_OBJECIONES.
 */
export const OBJECIONES_PRE_PITCH = Object.fromEntries(
  PLAYBOOK_OBJECIONES
    .filter((o) => o.cortePrePitch > 0)
    .map((o) => [String(o.id), sinCierreDeAgenda(o.plantilla, o.cortePrePitch)]),
);

/**
 * La Objecion 6 en M1 (Filtro 1) — psicologia de venta, 3-sep-2026 (noche).
 *
 * El lead acaba de decir "ese dato es delicado". Contestarle la 6 y rematar con
 * la pregunta pendiente de M1 ("¿A que te dedicas y cuanto ganas al mes?") es
 * volver a pedirle EXACTAMENTE lo que acaba de negarse a dar: se lee como
 * presion, no como empatia. En su lugar se le quita la profesion de encima y se
 * le pregunta solo por el RANGO, que se responde con un "Si".
 *
 * Se corta un parrafo mas que la variante pre-pitch normal (3 en vez de 2)
 * porque el que sigue empieza con "Te pregunto porque..." y M1_PEDIR_RANGO
 * abre igual: pegados quedan dos justificaciones seguidas con la misma
 * cabeza de frase. Igual que las otras variantes, esto es RECORTE POR CODIGO
 * sobre el copy aprobado — no hay una sola palabra nueva.
 */
export const OBJ_6_EN_M1 = sinCierreDeAgenda(OBJECIONES[6], 3);

/**
 * Etapas donde se esta evaluando el Filtro 1 (ingreso). Son las de M1 y son
 * las unicas donde aplica el trato especial de la Objecion 6.
 */
export const ETAPAS_FILTRO_1 = new Set([
  'M1_ENVIADO', 'M1_INGRESO_AMBIGUO', 'M1_RANGO_PREGUNTADO', 'M1_ACLARAR_REMANENTE',
]);

/**
 * Etapas donde el lead TODAVIA se esta calificando. Una objecion aca no debe
 * terminar en un cierre de agenda: debe responderse y volver a la pregunta que
 * quedo pendiente.
 */
export const ETAPAS_PRE_PITCH = new Set([
  'M1_ENVIADO', 'M1_INGRESO_AMBIGUO', 'M1_RANGO_PREGUNTADO', 'M1_ACLARAR_REMANENTE',
  'M2_ENVIADO', 'M2_BORDERLINE', 'M2_NO_SABE',
  'M3_ENVIADO', 'M3_RECONDUCIR',
  'M4_ENVIADO', 'M4_URGENCIA_REINTENTO',
]);

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

  let salida = plantilla
    .replaceAll(', {nombre}', usable ? `, ${usable}` : '')
    .replaceAll('{nombre},', usable ? `${usable},` : '')
    .replaceAll('{nombre}', usable);

  // Sin nombre no puede quedar "¡Hola ! 👋" ni un doble espacio en medio de la
  // frase. Bug real encontrado leyendo una conversacion del corpus: ManyChat no
  // siempre resuelve el first_name, y el saludo roto le llegaria a TODOS los
  // leads nuevos, que es justo el primer mensaje que ven.
  if (!usable) {
    salida = salida
      .replace(/ +([!?.,:;])/g, '$1')
      .replace(/[^\S\n]{2,}/g, ' ');
  }
  return salida;
}
