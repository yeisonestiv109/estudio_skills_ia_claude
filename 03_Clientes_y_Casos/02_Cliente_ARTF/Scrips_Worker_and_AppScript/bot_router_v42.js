/**
 * Router determinista del bot ARTF — SOP V4.2
 * ============================================================================
 * Este archivo NO habla con la red. Es logica pura: dado (estado del lead en
 * la base + clasificacion del mensaje), decide que plantilla se envia, a que
 * etapa pasa y que estado escribe. Se separo del Worker a proposito para poder
 * probarlo de verdad con `node --test` sin levantar nada.
 *
 * PRINCIPIO CENTRAL: el LLM nunca decide la ruta ni escribe el mensaje que ve
 * el lead. Solo entrega datos ya clasificados (un numero, una letra, un enum)
 * mas 1-2 frases de empatia. Todo lo de abajo -- filtros, umbrales, contadores
 * de objeciones, transiciones -- es codigo determinista.
 */

import {
  PLANTILLAS as P, OBJECIONES, OBJECIONES_HABILITADAS, OBJECIONES_PRE_PITCH,
  ETAPAS_PRE_PITCH, OBJ_6_EN_M1, ETAPAS_FILTRO_1, OBJECIONES_CON_PREGUNTA_PROPIA,
  UMBRALES, ESCALERA_REPREGUNTAS_HABILITADA, COPY_PENDIENTE_HABILITADO,
  CATCHALL_LLM_HABILITADO, objecionPermitidaEn, faseDeEtapa, OBJECION_ES_RESISTENCIA,
  HANDOFF_NO_RECUPERABLE, LIMPIAR_HANDOFF,
  render, partirEnBurbujas,
} from './sop_v42_plantillas.js';




// ═══════════════════════════════════════════════════════════════════════════
// AQUI VIVIA LA CAPA DE REGEX DE COMPRENSION. Se elimino el 12-sep-2026.
//
// Se habia dejado de usar el 6-sep (entender lenguaje es del LLM), pero las 12
// funciones seguian exportadas y con tests, como si estuvieran vivas. El costo
// no fue teorico: cuando el bot no reconocio un "70" suelto, la primera
// sospecha del fundador fue "hay un regex por ahi". No lo habia -- el mensaje
// ni siquiera llego al Worker (lo probo la telemetria) -- pero el codigo muerto
// hizo perder el tiempo buscando donde no era.
//
// Lo que se fue: parseIngresoCOP, detectarUrgencia, detectarSiNo,
// detectarHostilidad, detectarEndeudamientoPct, detectarDolorLetras,
// detectarAcompanante, detectarSinHorarios, detectarCompromiso,
// pareceRemanente, pareceIncertidumbre, pareceDolorFinanciero.
//
// Si alguna hiciera falta otra vez, esta en el historial de git. Pero la
// respuesta correcta casi siempre es una regla en el prompt, no un regex.
// ═══════════════════════════════════════════════════════════════════════════

// ---------------------------------------------------------------------------
// 2. Los 3 filtros del SOP V4.2
// ---------------------------------------------------------------------------
/** Filtro 1: ingreso >= $6M COP/mes (UMBRALES.INGRESO_MINIMO). */
export function evaluarIngreso(monto) {
  if (monto === null || monto === undefined) return 'ambiguo';
  return monto >= UMBRALES.INGRESO_MINIMO ? 'califica' : 'descalifica';
}

/**
 * Lo que le queda al lead cada mes despues de pagar deudas.
 *
 *   remanente = ingreso × (1 − deuda%)
 *
 * Es el criterio REAL del Filtro 2 desde el 4-sep-2026: al negocio no le
 * importa que deba poco, le importa que le QUEDE con que trabajar.
 * Devuelve null si falta cualquiera de los dos datos -- nunca 0, porque 0
 * significaria "no le queda nada" y eso descalificaria por falta de dato.
 */
export function calcularRemanente(ingreso, pct) {
  if (ingreso === null || ingreso === undefined || !(ingreso > 0)) return null;
  if (pct === null || pct === undefined) return null;
  return Math.round(ingreso * (1 - pct / 100));
}

/**
 * TOPE DE ENDEUDAMIENTO — el menor entre la escalera y el piso (11-sep-2026).
 *
 *   escalera: 50% en $7M, ±5 puntos por cada millon de diferencia.
 *   piso:     el % que deja exactamente UMBRALES.REMANENTE_MINIMO ($3M) libres.
 *
 * Gana el mas estricto. Ver el bloque del FILTRO 2 en sop_v42_plantillas.js
 * para la tabla completa y el porque.
 *
 * @returns {number|null} el tope en %, o null si no hay ingreso con que calcular.
 */
export function topeEndeudamiento(ingreso) {
  if (typeof ingreso !== 'number' || !Number.isFinite(ingreso) || ingreso <= 0) return null;
  const millones = ingreso / 1_000_000;
  const referencia = UMBRALES.INGRESO_REFERENCIA / 1_000_000;
  const escalera = UMBRALES.TOPE_EN_REFERENCIA_PCT + (millones - referencia) * UMBRALES.PUNTOS_POR_MILLON;
  // El % maximo que todavia deja el piso de remanente en el bolsillo.
  const piso = (1 - UMBRALES.REMANENTE_MINIMO / ingreso) * 100;
  // Nunca menos de 0 ni mas de 100: un tope fuera de ese rango no significa nada.
  return Math.max(0, Math.min(100, Math.min(escalera, piso)));
}

/**
 * Filtro 2 — 'ok' | 'verificar_calculo' | 'no_sabe'
 *
 * REGLA (11-sep-2026): la deuda mensual no puede pasar del tope que sale de
 * `topeEndeudamiento`, con un margen de tolerancia de
 * UMBRALES.MARGEN_TOLERANCIA_PCT puntos para los estimados "a ojo" del lead.
 *
 * Por encima NUNCA se descalifica de una: se verifica la cuenta primero. Un
 * endeudamiento imposible casi siempre es el saldo total en vez de la cuota,
 * o arriendo y servicios metidos como deuda. La decision final la toman
 * M2_VERIFICAR_CALCULO y M2_BORDERLINE.
 *
 * `remanenteDeclarado`: si el lead dio la cifra en plata, se usa esa para
 * derivar el %; pasar por el porcentaje redondeado mueve el resultado unos
 * miles de pesos justo en el limite.
 */
export function evaluarEndeudamiento(pct, ingreso, remanenteDeclarado = null) {
  const tope = topeEndeudamiento(ingreso);
  if (tope === null) return 'no_sabe';

  // Si hablo en plata, el % real sale de esa cifra y no del estimado.
  const pctReal = (typeof remanenteDeclarado === 'number' && Number.isFinite(remanenteDeclarado))
    ? (1 - remanenteDeclarado / ingreso) * 100
    : pct;
  if (pctReal === null || pctReal === undefined || !Number.isFinite(pctReal)) return 'no_sabe';

  return pctReal <= tope + UMBRALES.MARGEN_TOLERANCIA_PCT ? 'ok' : 'verificar_calculo';
}

// ---------------------------------------------------------------------------
// 3. ¿Debe el bot responder siquiera?
// ---------------------------------------------------------------------------
/**
 * Convivencia bot <-> Setter humano. Se evalua ANTES que cualquier otra cosa.
 *
 * Regla resuelta con base en el propio playbook V4.2 (no por criterio nuestro):
 * el SOP EXIGE que un lead descartado que se recalifica sea rescatado
 * automaticamente "sin humano y sin revelar que es IA" (RetornoLead). Por eso
 * 'descalificado' -- aunque es_terminal en la base -- NO se trata como puerta
 * cerrada: se deja pasar para poder rectificar. El resto de estados terminales
 * y todo lo que ya toco un humano si cierra la puerta.
 */
export function decidirSiResponder(estado) {
  if (!estado) return { responder: true, razon: 'lead_nuevo' };

  if (estado.handoff_razon) {
    // Excepcion puntual (5-sep-2026): `SIN_HORARIOS_ESPERANDO_FRANJA` pone el
    // handoff YA (el Setter se entera de inmediato, sin regresion), pero falta
    // UN turno para capturar la franja del lead y despedirse -- sin esto, la
    // pregunta de P.SIN_HORARIOS quedaba sin respuesta posible (bug real). No
    // reabre la conversacion: el propio case sale a HANDOFF sin condiciones, asi
    // que esta rama nunca se vuelve a tomar para el mismo lead.
    if (estado.etapa_bot === 'SIN_HORARIOS_ESPERANDO_FRANJA') {
      return { responder: true, razon: 'cerrando_franja_sin_horarios' };
    }
    // Auto-recuperacion (4-sep-2026): con un handoff recuperable el bot se deja
    // CLASIFICAR el mensaje, pero solo HABLA si el lead pidio continuar -- eso
    // lo decide `decidirTurno` con `recupera_handoff`. Sin esta puerta, un
    // "pero igual quiero seguir, me da 40%" se pierde en el vacio.
    if (HANDOFF_NO_RECUPERABLE.has(estado.handoff_razon)) {
      return { responder: false, razon: 'handoff_activo' };
    }
    return { responder: true, razon: 'handoff_recuperable' };
  }
  // Entregadas las preguntas pre-llamada, el bot no habla mas. (El blindaje
  // del show-up se retiro el 3-sep: no estaba en el SOP V4.2 y el % de
  // asistencia ya lo marca el Closer desde su dashboard.)
  if (['CIERRE_PRECALL', 'BLINDAJE_ENVIADO', 'BLINDAJE_CERRADO'].includes(estado.etapa_bot)) {
    // ANTI-BUCLE DEL "GRACIAS" (11-sep-2026). Con el embudo ya cerrado, un
    // "gracias" dejaba al lead en visto. Se le contesta UNA vez -- el propio
    // case pasa la etapa a BLINDAJE_CERRADO, asi que esta puerta no se vuelve
    // a abrir para el mismo lead y no hay forma de entrar en bucle.
    if (estado.etapa_bot === 'CIERRE_PRECALL') {
      return { responder: true, razon: 'cierre_por_gratitud' };
    }
    return { responder: false, razon: 'conversacion_cerrada' };
  }
  // Dominio del Setter/Closer: el bot no vuelve a hablar.
  const estadosDeHumano = ['agendado', 'no_show', 'show_up', 'oferta_presentada',
                           'reservo_oferta_valientes', 'seguimiento', 'ganado'];
  if (estadosDeHumano.includes(estado.estado_codigo)) {
    return { responder: false, razon: 'estado_de_humano' };
  }
  if (estado.estado_codigo === 'perdido' || estado.estado_codigo === 'nutricion') {
    return { responder: false, razon: 'estado_terminal' };
  }
  if (estado.estado_codigo === 'descalificado') {
    // Unica puerta abierta en terminal: RetornoLead.
    return { responder: true, razon: 'posible_retorno_lead' };
  }
  return { responder: true, razon: 'flujo_normal' };
}


// ---------------------------------------------------------------------------
// 3.b Retomar a un lead que vuelve
// ---------------------------------------------------------------------------

/**
 * ¿El mensaje es SOLO una palabra clave de disparo?
 *
 * Caso real de la primera prueba en vivo: el lead ya estaba en M1 esperando su
 * ingreso, volvio a mandar "PRUEBAV42", y el bot lo leyo como si fuera la
 * respuesta a "¿cuanto ganas?" -- no le encontro cifra y lo empujo por la rama
 * de ingreso ambiguo. Quemo un turno y lo saco del carril.
 *
 * Pasa igual con leads reales: el fundador reporta que muchos se caen a mitad
 * del guion y semanas despues vuelven comentando "CONTROL" otra vez.
 */
export function esSoloPalabraClave(texto) {
  const t = String(texto || '')
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')   // sin tildes
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return /^(control|claridad|radiografia|pruebav42|hola|test\s*javi|testjavi)$/.test(t);
}

/**
 * Las burbujas que el bot ya habia enviado en esa etapa, para reenviarlas.
 *
 * Se usa cuando el lead vuelve y repite la palabra clave: en vez de avanzar el
 * guion con basura, se le vuelve a poner delante la pregunta que quedo
 * pendiente. El SOP-05 de Javier respalda NO comentar la repeticion
 * ("veo que escribiste varios CONTROL" suena raro): solo se repregunta.
 */
export function preguntaPendiente(etapa, nombre) {
  const mapa = {
    // Solo la pregunta, no el saludo de apertura: reencarrilar no es reiniciar.
    M1_ENVIADO: [P.M1_PREGUNTA],
    M1_INGRESO_AMBIGUO: [P.M1_PEDIR_CIFRA],
    M1_RANGO_PREGUNTADO: [P.M1_PEDIR_RANGO_SIMPLE],
    M1_ACLARAR_REMANENTE: [P.M1_ACLARAR_REMANENTE],
    M2_ENVIADO: [P.M2_P1, P.M2_P2],
    M2_BORDERLINE: [P.M2_BORDERLINE],
    M2_NO_SABE: [P.M2_NO_SABE],
    M3_ENVIADO: [P.M3],
    M3_RECONDUCIR: [P.M3_RECONDUCIR],
    // De M4 y M5 se reenvia solo el remate, no la narrativa completa: el lead
    // ya la leyo, lo que necesita es volver a ver la pregunta.
    M4_ENVIADO: [P.M4_P2],
    M4_URGENCIA_REINTENTO: [P.M4_URGENCIA_REINTENTO],
    M5_ENVIADO: [P.M5_P2],
    M5_PITCH_REINTENTO: [P.M5_PITCH_REINTENTO],
    M7_ENVIADO: [P.M7],
    M7_ESPERANDO_VINCULO: [P.M6_CONFIRMAME],
    SIN_HORARIOS_ESPERANDO_FRANJA: [P.SIN_HORARIOS],
  };
  return (mapa[etapa] || []).map((x) => render(x, nombre));
}

/** Elige la pregunta de retorno segun POR QUE se descarto al lead. */
export function plantillaRetorno(motivoPerdida) {
  const m = String(motivoPerdida || '').toLowerCase();
  if (m.includes('ingreso')) return P.RETORNO_INGRESO;
  if (m.includes('endeudamiento')) return P.RETORNO_ENDEUDAMIENTO;
  if (m.includes('urgencia')) return P.RETORNO_URGENCIA;
  return P.RETORNO_GENERICO;
}


// ---------------------------------------------------------------------------
// 4. Router principal
// ---------------------------------------------------------------------------
const HANDOFF = (razon, estado, extra = {}) => ({
  mensajes: [],
  etapaNueva: 'HANDOFF',
  estadoDestino: null,
  handoffRazon: razon,
  motivoPerdida: null,
  campos: {},
  permitirEmpatia: false,
  summary: `Handoff a humano: ${razon}`,
  ...extra,
});

/**
 * Filtro 2 completo -- extraida del case M2_ENVIADO/M2_NO_SABE (5-sep-2026)
 * para que la recuperacion de handoff pueda reusarla en vez de solo reenviar
 * la pregunta pendiente.
 *
 * `etapaEntrada` decide si un "no_sabe" manda el fallback (primera vez) o
 * escala en silencio (ya se penso, ver mas abajo por que la recuperacion
 * SIEMPRE entra aca como si fuera la segunda vez).
 */
function evaluarYResponderEndeudamiento(estado, c, nombre, etapaEntrada, textoLead) {
  const ingreso = estado?.salario_monto ?? c.ingreso_cop ?? null;
  let pct = c.endeudamiento_pct ?? null;
  // Si lo dijo en plata, esa cifra es la exacta: el % se deriva solo para
  // guardarlo, y la decision se toma sobre la plata.
  let remanenteDeclarado = null;

  if (pct === null && ingreso !== null && ingreso > 0) {
    if (c.deuda_cop != null) {
      pct = Math.round((c.deuda_cop / ingreso) * 100);
      remanenteDeclarado = ingreso - c.deuda_cop;
    } else if (c.remanente_cop != null) {
      const gastado = Math.max(0, ingreso - c.remanente_cop);
      pct = Math.round((gastado / ingreso) * 100);
      remanenteDeclarado = c.remanente_cop;
    }
  }

  const veredicto = evaluarEndeudamiento(pct, ingreso, remanenteDeclarado);

  // BUG REAL (5-sep-2026): el LLM confunde "no se/no estoy segura" (INCERTIDUMBRE)
  // con la Objecion 6 "es un dato sensible" (RETICENCIA) -- son intenciones
  // vecinas y el prompt no las distinguia. Resultado: el bot anteponia la
  // plantilla de "dato sensible" y repetia P.M2_P1/P.M2_P2 tal cual, en vez de
  // usar M2_NO_SABE que ya existe para este caso exacto. `pareceIncertidumbre`
  // es el mismo tipo de guarda determinista que ya usa `pareceDolorFinanciero`:
  // no le quita al LLM la decision en el caso general, solo la anula cuando el
  // texto es un "no se" inequivoco.
  // Antes habia aqui un `!pareceIncertidumbre(textoLead)` para que un "no se"
  // no se leyera como la Objecion 6. Se quito con el resto de la capa de regex
  // (6-sep-2026): distinguir "no tengo el dato" de "no te lo quiero dar" es
  // comprension pura, y ahora el LLM lo decide con el historial delante y con
  // la regla escrita en su prompt.
  if (veredicto === 'no_sabe' && (c.objecion_num || c.objecion_detectada)) {
    // Igual que en M1: "esa info es sensible" es la Objecion 6, no un
    // "no se". Preguntar por deudas la dispara con la misma frecuencia.
    return manejarObjecion(estado, c, nombre, 'Objecion al pedir el endeudamiento (M2).');
  }
  if (veredicto === 'no_sabe') {
    if (etapaEntrada === 'M2_NO_SABE') {
      // BUG REAL reportado en vivo (6-sep-2026, Marly): esto escalaba en
      // SILENCIO -- cero mensajes -- apenas la segunda respuesta seguia sin
      // traer un numero ("creo que si queda" no es una cifra). Para el lead
      // eso se ve identico a que el bot dejo de responder.
      //
      // Se cambia a reencauzar(), el mismo mecanismo que ya usa el caso
      // analogo de M2_BORDERLINE (linea de arriba, "sin datos para decidir"):
      // el LLM antepone una frase de contexto y se reenvia la pregunta
      // pendiente, con tope de 3 intentos (UMBRALES.AMBIGUEDAD_MISMA_DUDA)
      // antes de escalar de verdad. Sigue siendo la MISMA pregunta de fondo,
      // pero ya no llega en silencio.
      return reencauzar(estado, c, nombre, 'No logra estimar su endeudamiento tras insistir.');
    }
    // BUG REAL (auditoria del 6-sep-2026 sobre la conversacion de marlyy318):
    // aca caia TODO lo que no fuera una cifra, incluida una pregunta legitima.
    // La lead pregunto "los gastos que le paso a mi mama, ¿los incluyo?" y
    // recibio "dame un estimado" -- se le contesto al lado. El LLM SI habia
    // entendido la pregunta; este `return` la tiraba a la basura.
    //
    // Ahora, si el lead pregunto algo, se expone en `preguntaLibre` para que
    // el Worker la responda con el playbook delante y DESPUES insista con el
    // estimado. Si no pregunto nada (o el LLM no logra responder), el turno
    // queda exactamente como antes.
    // COLETILLA INNECESARIA (bug real, 11-sep-2026). Tras una aclaracion del
    // Setter humano, el lead contesto "ahh ok" y el bot le pego encima "Sin
    // presion, dame un estimado..." -- una frase escrita para vencer
    // RESISTENCIA, delante de alguien que no estaba resistiendo nada. Sobraba y
    // se notaba.
    //
    // Un acuse de recibo no es un "no se". Si el LLM entendio el turno y
    // redacto una respuesta a la medida de ESTA conversacion, esa vale mas que
    // la plantilla: manda lo que el modelo escribio y se queda esperando la
    // cifra, sin insistir de mas.
    const acuse = CATCHALL_LLM_HABILITADO && typeof c.respuesta_empatica === 'string'
      ? c.respuesta_empatica.trim()
      : '';
    if (acuse && !c.pregunta_libre) {
      return {
        mensajes: [acuse],
        etapaNueva: 'M2_NO_SABE', estadoDestino: 'contactado',
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: `Acusa recibo sin dar cifra. Se responde en contexto ("${acuse.slice(0, 60)}") sin la coletilla de insistencia.`,
      };
    }

    return {
      mensajes: [render(P.M2_NO_SABE, nombre)],
      etapaNueva: 'M2_NO_SABE', estadoDestino: 'contactado',
      handoffRazon: null, motivoPerdida: null, campos: {},
      permitirEmpatia: false,
      preguntaLibre: c.pregunta_libre || null,
      summary: c.pregunta_libre
        ? `Pregunta algo antes de dar la cifra ("${c.pregunta_libre}"). Se le responde y se insiste con el estimado.`
        : 'No sabe su endeudamiento. Se insiste suave con un estimado.',
    };
  }
  // DEUDA TOTAL EN VEZ DE CUOTA MENSUAL (11-sep-2026). Bug real: un lead dio
  // un monto enorme y el clasificador lo leyo como resistencia a dar el dato
  // (Objecion 6). No era resistencia: sumo el SALDO de sus creditos en vez de
  // lo que paga al mes. Si la cifra no cabe como cuota mensual -- es decir, si
  // se lleva su ingreso entero -- lo que falla es el enunciado, no el lead.
  // Se aclara ANTES de cualquier veredicto, para que no lo descarte ni lo trate
  // como si estuviera ocultando algo.
  if (c.deuda_cop != null && ingreso != null && ingreso > 0
      && c.deuda_cop >= ingreso && etapaEntrada !== 'M2_DEUDA_TOTAL') {
    return {
      mensajes: partirEnBurbujas(render(P.M2_DEUDA_TOTAL_VS_CUOTA, nombre)),
      etapaNueva: 'M2_DEUDA_TOTAL', estadoDestino: 'contactado',
      handoffRazon: null, motivoPerdida: null, campos: {},
      permitirEmpatia: false,
      summary: `Dio ${c.deuda_cop} de deuda contra un ingreso de ${ingreso}: es el saldo total, no la cuota. Se aclara antes de decidir.`,
    };
  }

  if (veredicto === 'verificar_calculo') {
    return {
      mensajes: [render(P.M2_VERIFICAR_CALCULO, nombre)],
      etapaNueva: 'M2_VERIFICAR_CALCULO', estadoDestino: 'contactado',
      handoffRazon: null, motivoPerdida: null,
      campos: { endeudamiento_pct: pct },
      permitirEmpatia: false,
      summary: `Deuda ${pct}% sobre un ingreso de ${ingreso}: le quedarian ${remanenteDeclarado ?? calcularRemanente(ingreso, pct)} libres (< ${UMBRALES.REMANENTE_MINIMO}). Se verifica el calculo antes de descartar.`,
    };
  }
  if (veredicto === 'borderline') {
    return {
      // El tipo de deuda solo no alcanza: la regla del fundador tambien
      // acepta al lead si RECTIFICA que le sobran >= REMANENTE_MINIMO. La
      // segunda burbuja es copy pendiente de aprobacion; sin ella el
      // borderline sigue funcionando si el lead suelta la cifra por su cuenta.
      mensajes: COPY_PENDIENTE_HABILITADO
        ? [render(P.M2_BORDERLINE, nombre), render(P.M2_PEDIR_SOBRANTE, nombre)]
        : [render(P.M2_BORDERLINE, nombre)],
      etapaNueva: 'M2_BORDERLINE', estadoDestino: 'contactado',
      handoffRazon: null, motivoPerdida: null,
      campos: { endeudamiento_pct: pct },
      permitirEmpatia: false,
      summary: `Remanente ${calcularRemanente(ingreso, pct)} < ${UMBRALES.REMANENTE_MINIMO} con deuda ${pct}% (>=${UMBRALES.ENDEUDAMIENTO_PARA_BORDERLINE}%). Puede ser deuda buena: se pregunta antes de descartar.`,
    };
  }
  if (veredicto === 'descalifica') {
    return {
      mensajes: partirEnBurbujas(render(P.DESC_ENDEUDAMIENTO, nombre)),
      etapaNueva: 'DESCALIFICADO', estadoDestino: 'descalificado',
      handoffRazon: null,
      motivoPerdida: 'Descalificado - Endeudamiento sobre su tope',
      campos: { endeudamiento_pct: pct, califica: false },
      permitirEmpatia: false,
      summary: `Filtro 2 no superado: remanente ${calcularRemanente(ingreso, pct)} < ${UMBRALES.REMANENTE_MINIMO} y la deuda (${pct}%) no lo explica.`,
    };
  }
  return {
    mensajes: [render(P.M3, nombre)],
    etapaNueva: 'M3_ENVIADO', estadoDestino: 'contactado',
    handoffRazon: null, motivoPerdida: null,
    campos: { endeudamiento_pct: pct },
    permitirEmpatia: true,
    summary: `Filtro 2 superado: le quedan ${calcularRemanente(ingreso, pct)} libres al mes (deuda ${pct}%). Se pregunta el dolor.`,
  };
}

/**
 * @param {object} estado         fila de fn_bot_get_estado (null si es el primer mensaje)
 * @param {object} clasificacion  salida del clasificador (LLM + deterministas)
 * @param {string} textoLead      mensaje crudo del lead
 * @returns plan del turno
 */
export function decidirTurno(estado, clasificacion = {}, textoLead = '') {
  const c = clasificacion || {};
  const nombre = estado?.nombre || c.nombre || '';
  const etapa = estado?.etapa_bot || null;

  // --- Prioridad maxima, se evalua siempre y por encima de la etapa ---
  //
  // SIN LLM NO SE ADIVINA (6-sep-2026, regla de Gaby). Antes, si Groq fallaba,
  // el turno seguia "solo con deterministas" -- y esos deterministas eran los
  // que leian "si, ahora tengo mas claro que NO quiero" como una aceptacion y
  // le mandaban el link del calendario. Prefiere que lo atienda una persona
  // antes que un regex ciego adivinando.
  //
  // Va ANTES que el lead nuevo y que la etapa: si no se pudo entender el
  // mensaje, no hay decision que tomar sobre el.
  if (c.llm_fallo && etapa) {
    return HANDOFF('error_tecnico', estado, {
      summary: 'El LLM no respondio (sin cupo o caido). No se adivina lo que dijo el lead: lo atiende una persona.',
    });
  }
  if (c.crisis) return HANDOFF('crisis_emocional', estado, { estadoDestino: 'nutricion' });
  if (c.hostil) return HANDOFF('contenido_hostil', estado);
  if (c.ex_cliente) return HANDOFF('ex_cliente', estado);

  // --- Handoff recuperable: el bot solo vuelve a hablar si el lead lo pide ---
  // Excepcion puntual (5-sep-2026), MISMO caso que la de `decidirSiResponder`:
  // en SIN_HORARIOS_ESPERANDO_FRANJA hay que dejar que decidirTurno llegue a su
  // propio case (que cierra la conversacion) en vez de caer aca y quedarse mudo
  // -- sin esto, el gate general de arriba se comia el turno antes de que el
  // nuevo case pudiera correr, y el lead quedaba en visto igual que antes.
  if (estado?.handoff_razon && etapa !== 'SIN_HORARIOS_ESPERANDO_FRANJA') {
    if (c.recupera_handoff !== true) {
      // El lead escribio pero no pidio continuar. Se registra y se calla: el
      // handoff sigue en pie y el Setter conserva el turno.
      return {
        mensajes: [], etapaNueva: null, estadoDestino: null,
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: `Handoff activo (${estado.handoff_razon}) y el mensaje no pide continuar. Solo se registra.`,
      };
    }
    // Pide continuar: se limpia el handoff y se retoma donde el DATO dice que
    // iba, no donde quedo la etapa (que es 'HANDOFF' y no dice nada).
    const retomaEn = etapaParaRetomar(estado);

    // GENERALIZADO (5-sep-2026): en vez de solo reenviar la pregunta pendiente
    // (que puede ser la MISMA que ya se mando antes de escalar -- prohibido),
    // se REPROCESA el mensaje de vuelta como si el lead ya estuviera en
    // `retomaEn`, corriendo la logica REAL de esa etapa en vez de duplicarla
    // aca. BUG REAL que esto corrige: tras la Objecion 9 en M4, "pero si
    // agendemos" llegaba con el lead ya en HANDOFF (por una confusion previa)
    // y el codigo viejo solo reenviaba la pregunta de urgencia -- ignorando la
    // "bifurcacion oficial post-Objecion 9" que YA existe en el case
    // M4_ENVIADO (aceptar ahi manda el pitch real de M5, no la pregunta de
    // vuelta). Con el replay, esa logica corre sola, sin repetirla aca.
    //
    // Excepcion: M2. Llegar a un handoff desde M2 implica que YA se pregunto
    // al menos una vez (es la unica forma de llegar aca desde ahi); tratar la
    // recuperacion como "primer intento" reenviaria P.M2_NO_SABE de nuevo. Se
    // fuerza a 'M2_NO_SABE' para que, si sigue sin resolver, escale en
    // silencio en vez de repetir (ver evaluarYResponderEndeudamiento).
    const etapaParaReprocesar = retomaEn === 'M2_ENVIADO' ? 'M2_NO_SABE' : retomaEn;
    const estadoRetomado = { ...estado, etapa_bot: etapaParaReprocesar, handoff_razon: null };
    const resultado = decidirTurno(estadoRetomado, c, textoLead);

    if (resultado.etapaNueva === 'HANDOFF') {
      // Sigue sin resolver (o es una escalada nueva de otro tipo, ej. objecion
      // no habilitada): se queda escalado, sin mandarle al lead nada que ya vio.
      return resultado;
    }
    // Se resolvio de verdad: ahora si se limpia el handoff, no se deja la
    // razon vieja pegada mientras la conversacion ya sigue.
    return {
      ...resultado,
      handoffRazon: LIMPIAR_HANDOFF,
      summary: `El lead pide continuar tras el handoff (${estado.handoff_razon}). Se recupera y se retoma en ${etapaParaReprocesar}. ${resultado.summary}`,
    };
  }

  // --- Lead nuevo: se envia el Mensaje 1 ---
  if (!etapa) {
    // ⚠️ "SIN ETAPA" NO SIEMPRE ES "NUEVO" (12-sep-2026). Visto en produccion:
    // un lead con 2 turnos de historial y hablando de sus deudas recibio otra
    // vez el saludo de apertura, porque su `etapa_bot` estaba en null.
    //
    // Pasa siempre que la fila existe pero la etapa nunca se fijo: turnos
    // registrados en modo log-only, un lead creado por otro sistema, o los dos
    // bots conviviendo. Reenviarle el Mensaje 1 lo devuelve al principio del
    // embudo y le hace repetir lo que ya contesto.
    //
    // La etapa no es la unica fuente de verdad: los DATOS del lead tambien lo
    // son, y `etapaParaRetomar` ya sabe deducir el punto exacto a partir del
    // primer filtro que le falte. Solo se saluda a quien de verdad no ha dicho
    // nada todavia.
    const yaDijoAlgo = Boolean(estado && (estado.salario_monto
      || estado.endeudamiento_pct !== null && estado.endeudamiento_pct !== undefined
      || estado.dolor || estado.urgencia));
    if (yaDijoAlgo) {
      const retomaEn = etapaParaRetomar(estado);
      const r = decidirTurno({ ...estado, etapa_bot: retomaEn }, c, textoLead);
      return { ...r, summary: `Lead con datos pero sin etapa: se retoma en ${retomaEn} en vez de saludarlo de nuevo. ${r.summary}` };
    }

    const variante = detectarVarianteM1(textoLead);
    return {
      mensajes: [render(P[variante], nombre)],
      etapaNueva: 'M1_ENVIADO',
      estadoDestino: 'contactado',
      handoffRazon: null,
      motivoPerdida: null,
      campos: {},
      permitirEmpatia: false, // M1 ya trae su propia validacion emocional
      summary: `Apertura enviada (${variante}).`,
    };
  }

  // --- Lead DESCALIFICADO que vuelve a escribir ---
  // Caso real reportado por el fundador: "leads que ya he descalificado vuelven
  // y llegan". Antes el bot no les respondia NADA salvo que soltaran una cifra
  // que los recalificara. Ahora, como si guardamos POR QUE se descarto, se le
  // pregunta exactamente por eso.
  if (estado?.estado_codigo === 'descalificado') {
    const ing = c.ingreso_cop ?? null;

    // RetornoLead del propio SOP V4.1: si de entrada suelta una cifra que ya
    // califica, se rectifica de inmediato, sin humano y sin revelar que es IA.
    if (ing !== null && evaluarIngreso(ing) === 'califica') {
      return {
        mensajes: [render(P.RETORNO_LEAD, nombre), render(P.M2_P1, nombre), render(P.M2_P2, nombre)],
        etapaNueva: 'M2_ENVIADO',
        estadoDestino: 'contactado',
        handoffRazon: null,
        motivoPerdida: null,
        campos: { salario_monto: ing, ingreso_confirmado: true, califica: null },
        permitirEmpatia: false,
        summary: `RetornoLead: se recalifica con ingreso ${ing}. Se retoma en M2.`,
      };
    }

    // Ya le preguntamos si su situacion cambio; ahora se procesa la respuesta.
    if (etapa === 'RETORNO_PREGUNTA') {
      if (c.retoma === true) {
        const m = String(estado?.motivo_perdida || '').toLowerCase();
        if (m.includes('endeudamiento')) {
          return {
            mensajes: [render(P.M2_P1, nombre), render(P.M2_P2, nombre)],
            etapaNueva: 'M2_ENVIADO', estadoDestino: 'contactado',
            handoffRazon: null, motivoPerdida: null, campos: {},
            permitirEmpatia: false,
            summary: 'Retorna y dice que bajo la deuda. Se revalida el Filtro 2.',
          };
        }
        if (m.includes('urgencia')) {
          return {
            mensajes: [render(P.M4_P1, nombre), render(P.M4_P2, nombre)],
            etapaNueva: 'M4_ENVIADO', estadoDestino: 'contactado',
            handoffRazon: null, motivoPerdida: null, campos: {},
            permitirEmpatia: false,
            summary: 'Retorna y dice que ahora si es prioridad. Se revalida el Filtro 3.',
          };
        }
        // Ingreso, o motivo desconocido: se pide la cifra (nunca se asume).
        return {
          mensajes: [render(P.M1_PEDIR_CIFRA, nombre)],
          etapaNueva: 'M1_INGRESO_AMBIGUO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { ingreso_confirmado: false },
          permitirEmpatia: false,
          summary: 'Retorna y dice que mejoro el ingreso. Se pide la cifra para revalidar el Filtro 1.',
        };
      }
      if (c.retoma === false) {
        return {
          mensajes: [render(P.RETORNO_SIN_CAMBIO, nombre)],
          etapaNueva: 'DESCALIFICADO', estadoDestino: null,
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'Retorna pero su situacion no cambio. Se cierra sin insistir.',
        };
      }
      return {
        mensajes: [], etapaNueva: null, estadoDestino: null, handoffRazon: null,
        motivoPerdida: null, campos: {}, permitirEmpatia: false,
        summary: 'Respuesta a la pregunta de retorno no clasificable. Solo se registra.',
      };
    }

    // ⚠️ RESURRECCION FANTASMA (bug real, 11-sep-2026). Un lead recien
    // descalificado por endeudamiento dijo "gracias" y el bot le contesto
    // "¡Hola de nuevo! ... ¿Lograste bajar esa carga?" -- lo trato como un lead
    // viejo que volvia rehabilitado, treinta segundos despues de descartarlo.
    //
    // Un "gracias" u "ok" ahi no es un retorno: es una reaccion al cierre. El
    // saludo de retorno solo tiene sentido cuando de verdad paso tiempo, asi
    // que si el lead sigue activo HOY se cierra con calidez y no se reabre el
    // embudo. `dias_sin_actividad` lo da la propia RPC del estado.
    if ((estado?.dias_sin_actividad ?? 0) < 1) {
      return {
        mensajes: partirEnBurbujas(render(P.CIERRE_POST_DESCALIFICACION, nombre)),
        etapaNueva: 'DESCALIFICADO', estadoDestino: null,
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: 'Reacciona al cierre el mismo dia en que se le descalifico. Se cierra con calidez, NO se le trata como lead que vuelve.',
      };
    }

    // Primera vez que vuelve DE VERDAD (paso al menos un dia): se le pregunta
    // por el motivo EXACTO del descarte.
    return {
      mensajes: [render(plantillaRetorno(estado?.motivo_perdida), nombre)],
      etapaNueva: 'RETORNO_PREGUNTA', estadoDestino: null,
      handoffRazon: null, motivoPerdida: null, campos: {},
      permitirEmpatia: false,
      summary: `Lead descalificado (${estado?.motivo_perdida || 'motivo no registrado'}) vuelve a escribir. Se le pregunta si su situacion cambio.`,
    };
  }

  // --- Repitio la palabra clave a mitad del guion ---
  // No avanza el flujo: se le vuelve a poner delante la pregunta pendiente.
  // El SOP-05 de Javier es explicito en NO comentar la repeticion.
  if (esSoloPalabraClave(textoLead)) {
    const pendientes = preguntaPendiente(etapa, nombre);
    return {
      mensajes: pendientes,
      etapaNueva: null, estadoDestino: null, handoffRazon: null,
      motivoPerdida: null, campos: {}, permitirEmpatia: false,
      summary: pendientes.length
        ? `Repitio la palabra clave estando en ${etapa}. Se reenvia la pregunta pendiente sin avanzar.`
        : `Repitio la palabra clave estando en ${etapa}. Sin pregunta pendiente que reenviar.`,
    };
  }

  switch (etapa) {
    // =====================================================================
    // =====================================================================
    // Se le pregunto "¿estas en el rango de $7M a $15M o mas?". Es una pregunta
    // de SI/NO: un "Si" ahi CONFIRMA el Filtro 1. Antes caia como ambiguo y
    // terminaba escalando a un humano un lead que ya habia dicho que califica.
    case 'M1_RANGO_PREGUNTADO': {
      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion al preguntar por el rango de ingreso.');
      }
      // Si de paso soltó una cifra, esa manda sobre el si/no.
      const ingRango = c.ingreso_cop ?? null;
      if (ingRango !== null) {
        if (evaluarIngreso(ingRango) === 'califica') {
          return {
            mensajes: [render(P.M2_P1, nombre), render(P.M2_P2, nombre)],
            etapaNueva: 'M2_ENVIADO', estadoDestino: 'contactado',
            handoffRazon: null, motivoPerdida: null,
            campos: { salario_monto: ingRango, ingreso_confirmado: true },
            permitirEmpatia: false,
            summary: `Filtro 1 superado con cifra ${ingRango} al preguntar el rango.`,
          };
        }
        return {
          mensajes: partirEnBurbujas(render(P.DESC_INGRESO, nombre)),
          etapaNueva: 'DESCALIFICADO', estadoDestino: 'descalificado',
          handoffRazon: null,
          motivoPerdida: `Descalificado - Ingreso bajo (< $${UMBRALES.INGRESO_MINIMO / 1e6}M)`,
          campos: { salario_monto: ingRango, ingreso_confirmado: true, califica: false },
          permitirEmpatia: false,
          summary: `Filtro 1 no superado: dio ${ingRango} al preguntar el rango.`,
        };
      }
      if (c.confirma_rango === true) {
        // Confirma estar en el rango: se registra el PISO del rango que el
        // propio lead acepto. No es una cifra inventada -- sale del texto que
        // se le pregunto (INGRESO_ASUMIDO_POR_RANGO va atado a M1_PEDIR_RANGO,
        // con un test que lo exige). Se marca `ingreso_confirmado: false`
        // porque el lead nunca dijo un numero: no cambia el flujo, pero deja el
        // dashboard honesto sobre de donde salio la cifra.
        return {
          mensajes: [render(P.M2_P1, nombre), render(P.M2_P2, nombre)],
          etapaNueva: 'M2_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { salario_monto: UMBRALES.INGRESO_ASUMIDO_POR_RANGO, ingreso_confirmado: false },
          permitirEmpatia: false,
          summary: `Confirma estar en el rango. Filtro 1 superado; se asume el piso del rango (${UMBRALES.INGRESO_ASUMIDO_POR_RANGO}) sin confirmar.`,
        };
      }
      if (c.confirma_rango === false) {
        // DECISION COMERCIAL del fundador (4-sep-2026): el copy sigue
        // preguntando por el rango de $7M aunque el Filtro 1 este en $6M, y un
        // "No" descalifica directo. Se asume a proposito la perdida de los
        // leads en la banda $6M-$7M que contestan que no: se prefiere eso a
        // gastar un turno mas pidiendo la cifra.
        //
        // Por eso el motivo NO cita el umbral (seria mentira: este lead puede
        // ganar $6.5M): dice lo que de verdad paso, que es que dijo no al rango.
        return {
          mensajes: partirEnBurbujas(render(P.DESC_INGRESO, nombre)),
          etapaNueva: 'DESCALIFICADO', estadoDestino: 'descalificado',
          handoffRazon: null,
          motivoPerdida: 'Descalificado - Ingreso bajo (fuera del rango del playbook)',
          campos: { ingreso_confirmado: true, califica: false },
          permitirEmpatia: false,
          summary: 'Dice que NO esta en el rango del playbook. Filtro 1 no superado (decision comercial: no se le pide la cifra).',
        };
      }
      // Ni cifra ni si/no claro: se pide el numero, nunca se descarta.
      return {
        mensajes: [render(P.M1_PEDIR_CIFRA, nombre)],
        etapaNueva: 'M1_INGRESO_AMBIGUO', estadoDestino: 'contactado',
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: 'Respuesta al rango no clasificable. Se pide la cifra exacta (nunca se descarta sobre ambiguo).',
      };
    }

    case 'M1_ENVIADO':
    case 'M1_INGRESO_AMBIGUO':
    case 'M1_ACLARAR_REMANENTE': {
      const ing = c.ingreso_cop ?? null;
      const veredicto = evaluarIngreso(ing);

      if (veredicto === 'ambiguo') {
        // OBJECION antes que ambiguedad. Caso real de la prueba: la lead
        // respondio "es un dato delicado para compartir por aqui" -- eso es la
        // Objecion 6 del SOP, no un ingreso ambiguo. El bot le pidio el rango y
        // la conversacion se atasco.
        if (c.objecion_num || c.objecion_detectada) {
          return manejarObjecion(estado, c, nombre, 'Objecion al pedir el ingreso (M1).');
        }

        // Regla de oro V4.1: NUNCA descalificar sobre un ingreso ambiguo.
        if (etapa === 'M1_INGRESO_AMBIGUO') {
          // Antes escalaba aca, con este argumento: "tampoco reencauzar,
          // repetiria P.M1_PEDIR_CIFRA, la misma pregunta que ya se hizo".
          // Era valido cuando reencauzar SOLO sabia reenviar la plantilla.
          // Desde la auditoria B (6-sep-2026) antepone una respuesta razonada
          // con el playbook, asi que ya no es repetirse: el lead que no da la
          // cifra casi siempre esta preguntando algo ("¿antes o despues de
          // impuestos?", "¿cuento lo de mi negocio?") y eso tiene respuesta.
          // La regla de oro V4.1 sigue intacta: no se descarta sobre un
          // ingreso ambiguo, jamas.
          return reencauzar(estado, c, nombre,
            'Sigue sin dar una cifra de ingreso clara tras pedirsela.');
        }

        // Cual de las dos preguntas toca, segun el SOP:
        //  - Escenario E: dijo un TERMINO ambiguo ("minimo integral", "variable")
        //    -> se le pide el numero.
        //  - Escenario B: no menciono ingreso en absoluto -> se le pregunta si
        //    esta en el rango. Esa pregunta es de SI/NO, y por eso lleva su
        //    propia etapa: un "Si" ahi es una respuesta valida, no ambiguedad.
        // `varias_fuentes` entra aca: si el LLM tampoco logro sumar, lo util es
        // pedirle el TOTAL, no ofrecerle el rango -- ya dio cifras, lo que falta
        // es la suma.
        const terminoAmbiguo = ['salario_integral', 'ingreso_variable', 'numero_sin_unidad', 'varias_fuentes']
          .includes(c.ingreso_glosario);
        if (terminoAmbiguo) {
          return {
            mensajes: [render(P.M1_PEDIR_CIFRA, nombre)],
            etapaNueva: 'M1_INGRESO_AMBIGUO', estadoDestino: 'contactado',
            handoffRazon: null, motivoPerdida: null,
            campos: { profesion: c.profesion ?? null, ingreso_confirmado: false },
            permitirEmpatia: false,
            summary: `Ingreso ambiguo (${c.ingreso_glosario}). Se pide la cifra exacta.`,
          };
        }
        // Variante SIMPLE: no hubo objecion, al lead simplemente se le paso decir
        // la cifra. La defensiva ("te pregunto porque...") solo se usa cuando hay
        // una objecion de privacidad que desactivar (ver manejarObjecion).
        return {
          mensajes: [render(P.M1_PEDIR_RANGO_SIMPLE, nombre)],
          etapaNueva: 'M1_RANGO_PREGUNTADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { profesion: c.profesion ?? null, ingreso_confirmado: false },
          permitirEmpatia: false,
          summary: 'No dio ninguna cifra y no objeto. Se pregunta el rango sin ponerse a la defensiva.',
        };
      }

      if (veredicto === 'descalifica') {
        // Aprendizaje de produccion (SOP-05 #2 del proyecto de Javier): el lead
        // que dice "me quedan $5M" o "menos de $7M" a veces habla del dinero
        // que le SOBRA despues de gastos, no de su ingreso total. Descalificar
        // ahi quema un lead bueno. Se aclara UNA vez antes de decidir.
        if (etapa !== 'M1_ACLARAR_REMANENTE' && c.cifra_es_remanente === true) {
          return {
            mensajes: [render(P.M1_ACLARAR_REMANENTE, nombre)],
            etapaNueva: 'M1_ACLARAR_REMANENTE', estadoDestino: 'contactado',
            handoffRazon: null, motivoPerdida: null,
            campos: { profesion: c.profesion ?? null },
            permitirEmpatia: false,
            summary: `Ingreso ${ing} bajo el umbral PERO el texto sugiere que es remanente, no ingreso total. Se aclara antes de descalificar.`,
          };
        }
        // RESCATE POR INGRESOS VARIABLES (7-sep-2026). Antes de cerrarle la
        // puerta a quien no llega con el fijo, se le pregunta si ademas recibe
        // comisiones, bonos o extras. Es la misma logica del rescate por
        // remanente de arriba: una pregunta barata contra un lead quemado.
        // Solo se hace UNA vez (si ya venimos de M1_INGRESO_AMBIGUO, no se
        // repite) y solo con la perilla de copy pendiente encendida.
        if (COPY_PENDIENTE_HABILITADO && etapa !== 'M1_INGRESO_AMBIGUO'
            && etapa !== 'M1_ACLARAR_REMANENTE') {
          return {
            mensajes: [render(P.M1_PREGUNTAR_VARIABLES, nombre)],
            etapaNueva: 'M1_INGRESO_AMBIGUO', estadoDestino: 'contactado',
            handoffRazon: null, motivoPerdida: null,
            campos: { profesion: c.profesion ?? null },
            permitirEmpatia: false,
            summary: `Ingreso fijo ${ing} bajo el umbral. Se pregunta por comisiones/bonos antes de descalificar.`,
          };
        }
        return {
          mensajes: partirEnBurbujas(render(P.DESC_INGRESO, nombre)),
          etapaNueva: 'DESCALIFICADO',
          estadoDestino: 'descalificado',
          handoffRazon: null,
          motivoPerdida: `Descalificado - Ingreso bajo (< $${UMBRALES.INGRESO_MINIMO / 1e6}M)`,
          campos: { profesion: c.profesion ?? null, salario_monto: ing, ingreso_confirmado: true, califica: false },
          permitirEmpatia: false,
          summary: `Filtro 1 no superado: ingreso ${ing} < $7M. Descalificacion con valor.`,
        };
      }

      return {
        mensajes: [render(P.M2_P1, nombre), render(P.M2_P2, nombre)],
        etapaNueva: 'M2_ENVIADO',
        estadoDestino: 'contactado',
        handoffRazon: null, motivoPerdida: null,
        campos: { profesion: c.profesion ?? null, salario_monto: ing, ingreso_confirmado: true },
        permitirEmpatia: true,
        summary: `Filtro 1 superado: ingreso ${ing}. Se pregunta endeudamiento.`,
      };
    }

    // =====================================================================
    case 'M2_ENVIADO':
    case 'M2_NO_SABE':
    // Ya se le aclaro que la cuenta va con la CUOTA mensual, no con el saldo
    // total: este turno trae la cifra corregida y se evalua igual que M2.
    case 'M2_DEUDA_TOTAL':
      return evaluarYResponderEndeudamiento(estado, c, nombre, etapa, textoLead);

    // =====================================================================
    // VERIFICACION DEL CALCULO (7-sep-2026). El lead reporto un endeudamiento
    // por encima del tope de su ingreso y se le pregunto si la cuenta esta
    // bien hecha. Este turno es su respuesta.
    //
    // Tres salidas:
    //   1. Corrige a una cifra dentro del tope -> sigue el embudo (M3).
    //   2. Rectifica en plata y le sobra suficiente -> sigue el embudo.
    //   3. Ratifica la cifra alta -> M2_BORDERLINE, que es la ULTIMA salida:
    //      si la mayoria es deuda buena (vivienda/hipoteca) todavia pasa.
    //      Descalificar aca seria botar a alguien con hipoteca, que el
    //      playbook trata distinto a proposito.
    case 'M2_VERIFICAR_CALCULO': {
      const pctCorregido = c.endeudamiento_pct ?? null;
      const ingresoConocido = estado?.salario_monto ?? c.ingreso_cop ?? null;
      const sobrante = c.remanente_cop ?? null;
      // BUG CORREGIDO (11-sep-2026): si el lead corregia diciendo lo que PAGA al
      // mes ("pago 3 millones"), el prompt de esta etapa le pide al LLM ponerlo
      // en `deuda_cop`, pero aqui no se leia: el bot concluia "no dio nada" y
      // volvia a preguntar lo mismo. Ahora esa cifra cuenta.
      const cuotaCorregida = (c.deuda_cop != null && ingresoConocido > 0) ? c.deuda_cop : null;
      const pctFinal = pctCorregido
        ?? (cuotaCorregida !== null ? Math.round((cuotaCorregida / ingresoConocido) * 100) : null);
      const remanenteCorregido = (pctCorregido === null && cuotaCorregida !== null)
        ? ingresoConocido - cuotaCorregida
        : calcularRemanente(ingresoConocido, pctCorregido);

      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion al verificar el calculo del endeudamiento (M2).');
      }

      // Rectifico en plata: esa cifra manda sobre cualquier porcentaje estimado.
      if (sobrante !== null && sobrante >= UMBRALES.REMANENTE_MINIMO) {
        return {
          mensajes: [render(P.M3, nombre)],
          etapaNueva: 'M3_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { remanente_cop: sobrante },
          permitirEmpatia: true,
          summary: `Verificacion del calculo: rectifica que le sobran ${sobrante} al mes. Filtro 2 superado.`,
        };
      }

      // Corrigio la cuenta (en % o en cuota) y ahora si le quedan los $2.5M.
      if (remanenteCorregido !== null
          && evaluarEndeudamiento(pctFinal, ingresoConocido, remanenteCorregido) === 'ok') {
        return {
          mensajes: [render(P.M3, nombre)],
          etapaNueva: 'M3_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { endeudamiento_pct: pctFinal },
          permitirEmpatia: true,
          summary: `Verificacion del calculo: corrige a ${pctFinal}% y le quedan ${remanenteCorregido} libres. Filtro 2 superado.`,
        };
      }

      // No dio NADA con que decidir (ni cifra corregida ni sobrante). Misma
      // regla de oro del resto del embudo: no se descarta sobre un vacio.
      if (pctFinal === null && sobrante === null) {
        return reencauzar(estado, c, nombre,
          'Verificacion del calculo sin datos: no corrigio la cifra ni dijo cuanto le sobra.');
      }

      // Ratifica la cifra alta. Queda UNA salida: que la mayoria sea deuda
      // buena. Es exactamente el borderline de siempre.
      return {
        mensajes: COPY_PENDIENTE_HABILITADO
          ? [render(P.M2_BORDERLINE, nombre), render(P.M2_PEDIR_SOBRANTE, nombre)]
          : [render(P.M2_BORDERLINE, nombre)],
        etapaNueva: 'M2_BORDERLINE', estadoDestino: 'contactado',
        handoffRazon: null, motivoPerdida: null,
        campos: pctFinal !== null ? { endeudamiento_pct: pctFinal } : {},
        permitirEmpatia: false,
        summary: `Verificacion del calculo: ratifica ${pctFinal ?? 'la cifra'}%, le siguen quedando menos de ${UMBRALES.REMANENTE_MINIMO} libres. Puede ser deuda buena: se pregunta antes de descartar.`,
      };
    }

    // =====================================================================
    case 'M2_BORDERLINE': {
      // Dos salidas a favor, cualquiera basta (regla del fundador, 4-sep-2026):
      //   1. la mayoria es deuda BUENA (vivienda/hipoteca), o
      //   2. RECTIFICA que le sobra >= REMANENTE_MINIMO al mes.
      // La segunda existe porque el % declarado en M2 suele ser un estimado
      // grueso; si al preguntarle en plata resulta que si le queda, el estimado
      // estaba mal, no el lead.
      const sobrante = c.remanente_cop ?? null;
      const leSobraSuficiente = sobrante !== null && sobrante >= UMBRALES.REMANENTE_MINIMO;

      if (c.deuda_mayoritariamente_buena || leSobraSuficiente) {
        return {
          mensajes: [render(P.M3, nombre)],
          etapaNueva: 'M3_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          // Si rectifico en plata, esa cifra manda sobre el % estimado.
          campos: leSobraSuficiente ? { remanente_cop: sobrante } : {},
          permitirEmpatia: true,
          summary: c.deuda_mayoritariamente_buena
            ? 'Borderline resuelto a favor: la mayoria es deuda buena (vivienda).'
            : `Borderline resuelto a favor: rectifica que le sobran ${sobrante} al mes.`,
        };
      }

      // Regla de oro heredada del Filtro 1: no se descarta sobre un vacio. Si no
      // dijo ni que tipo de deuda es ni cuanto le sobra, se le vuelve a
      // preguntar antes de cerrarle la puerta.
      if (c.deuda_mayoritariamente_buena === undefined && sobrante === null
          && !c.objecion_num && !c.objecion_detectada) {
        // Reencauzar (5-sep-2026): el comentario de esta regla siempre dijo
        // "se le vuelve a preguntar antes de cerrarle la puerta", pero el
        // codigo escalaba en silencio sin volver a preguntar nada. Ahora si
        // cumple lo que promete, con contexto del LLM y tope de 3 intentos.
        return reencauzar(estado, c, nombre,
          'Borderline sin datos para decidir (ni tipo de deuda ni sobrante).');
      }

      return {
        mensajes: partirEnBurbujas(render(P.DESC_ENDEUDAMIENTO, nombre)),
        etapaNueva: 'DESCALIFICADO', estadoDestino: 'descalificado',
        handoffRazon: null,
        motivoPerdida: 'Descalificado - Endeudamiento sobre su tope',
        campos: { califica: false, ...(sobrante !== null ? { remanente_cop: sobrante } : {}) },
        permitirEmpatia: false,
        summary: sobrante !== null
          ? `Borderline resuelto en contra: deuda de consumo y solo le sobran ${sobrante} (< ${UMBRALES.REMANENTE_MINIMO}).`
          : 'Borderline resuelto en contra: deuda de consumo/tarjetas.',
      };
    }

    // =====================================================================
    case 'M3_ENVIADO': {
      // H4: el lead puede elegir VARIOS dolores ("C y B"). Se guardan todos,
      // con el mismo formato que ya usa el dashboard ("B,C").
      const letras = Array.isArray(c.dolores) && c.dolores.length
        ? c.dolores.map((x) => String(x).toUpperCase())
        : ((c.dolor || '').toUpperCase() ? [(c.dolor || '').toUpperCase()] : []);
      const dolor = serializarDolor(letras, c.dolor_detalle || '');

      if (letras.length === 0 && (c.objecion_num || c.objecion_detectada)) {
        return manejarObjecion(estado, c, nombre, 'Objecion al preguntar por el dolor (M3).');
      }
      // Califica emocionalmente si eligio CUALQUIERA de los dolores del avatar.
      //
      // Para la D, el detector determinista GANA sobre el LLM: si el texto libre
      // menciona deudas, pagos, tarjetas o falta de plata, es dolor financiero y
      // punto. El LLM ya fallo con "me siento preocupada por la cantidad de
      // deudas que tengo" y mando a reconducir a una lead perfecta (QA 4-sep).
      const esAvatar = letras.some((l) => ['A', 'B', 'C'].includes(l));
      // El respaldo por regex (`pareceDolorFinanciero`) se quito el 6-sep-2026.
      // Existia porque el LLM habia fallado una vez con "me siento preocupada
      // por la cantidad de deudas que tengo"; ese caso ahora esta escrito como
      // regla en el prompt, que es donde se puede leer y corregir.
      const dFinanciero = c.dolor_financiero === true;
      if (esAvatar || (letras.includes('D') && dFinanciero)) {
        return {
          mensajes: [render(P.M4_P1, nombre), render(P.M4_P2, nombre)],
          etapaNueva: 'M4_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { dolor: dolor || null },
          // M4 ya arranca con "Te entiendo perfectamente" -> no se le antepone empatia.
          permitirEmpatia: false,
          summary: `Dolor ${dolor} (califica emocionalmente). Se pregunta urgencia.`,
        };
      }
      // BUG REAL (auditoria del 6-sep-2026, conversacion de marlyy318): el
      // playbook ofrece "D) Otra (¿cuál?)" -- pregunta el "¿cuál?" el mismo --
      // pero NO habia ninguna rama que lo preguntara. La lead contesto "d" y
      // recibio M3_RECONDUCIR, que le insinua que no es buen fit ("puede que
      // no seamos el mejor fit") por no haber dicho algo que nadie le pidio
      // dos veces. Elegir D sin detalle no es un lead fuera del avatar: es un
      // lead que todavia no ha contado su caso.
      //
      // Se resuelve con el LLM y no con otra plantilla a proposito: la
      // pregunta ya existe en el copy aprobado (P.M3), asi que redactarla no
      // inventa nada. `preguntaLibreReemplaza` = el LLM escribe el turno
      // entero; si falla, sale M3_RECONDUCIR igual que antes.
      const dSinDetalle = letras.includes('D') && !c.dolor_detalle;

      // Es EL caso que reporto el QA del 4-sep: el lead da un contexto rico
      // ("quiero ahorrar", "me preocupa mi futuro") y recibe una plantilla que
      // no lo menciona. Aca la apertura personalizada es lo que evita que suene
      // a robot; el cuerpo sigue siendo la plantilla aprobada.
      return {
        mensajes: [render(P.M3_RECONDUCIR, nombre)],
        etapaNueva: 'M3_RECONDUCIR', estadoDestino: 'contactado',
        handoffRazon: null, motivoPerdida: null,
        campos: { dolor: dolor || null },
        permitirEmpatia: true,
        preguntaLibre: dSinDetalle
          ? 'El lead eligio la opcion "D) Otra" de la lista de frustraciones con el dinero, pero no dijo cual es esa otra frustracion. Preguntale con calidez cual es, dandole pie a que la cuente con sus palabras. NO insinues que no es buen fit ni lo descalifiques: todavia no te ha contado su caso.'
          : (c.pregunta_libre || null),
        preguntaLibreReemplaza: dSinDetalle,
        summary: 'Dolor D no financiero. Se reconduce.',
      };
    }

    // =====================================================================
    case 'M3_RECONDUCIR': {
      if (c.dolor_financiero === true || c.acepta) {
        return {
          mensajes: [render(P.M4_P1, nombre), render(P.M4_P2, nombre)],
          etapaNueva: 'M4_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'Reconduccion exitosa: el dolor si esta conectado con el dinero.',
        };
      }
      // BUG REAL reportado en Instagram (6-sep-2026): esta rama trataba
      // "no se pudo clasificar nada" exactamente igual que "se confirmo que
      // NO es financiero" -- el lead quedaba mudo (HANDOFF silencioso) ante
      // CUALQUIER respuesta que el LLM no lograra leer, no solo ante una
      // confirmacion real. Solo escala directo (sin script, decision de
      // negocio real) cuando el LLM SI logro determinar que no es financiero.
      // Si simplemente no se entendio el mensaje, se reencauza como en el
      // resto del bot -- misma regla del 5-sep, ahora tambien aca.
      if (c.dolor_financiero === false) {
        // Antes: "sin script del SOP para este cierre -> humano". El playbook
        // SI tiene con que responder esto (que es el programa, para quien es,
        // que se ve en la llamada); lo que faltaba era darselo al LLM. Se le
        // pide cerrar con honestidad en vez de escalar: si de verdad no hay
        // fit, decirlo bien dicho es mejor servicio que dejarlo esperando a
        // que aparezca un humano.
        return reencauzar(estado, c, nombre,
          'Dolor no financiero confirmado: se responde con el playbook en vez de escalar.',
          'El lead confirma que su frustracion principal NO tiene que ver con el dinero. Reconocelo con respeto y explicale en una o dos frases para quien es esto, apoyandote en el playbook, y cierra preguntandole si aun asi siente que su dinero le limita decisiones. No lo descalifiques ni le prometas nada que el playbook no diga.',
          true);
      }
      return reencauzar(estado, c, nombre, 'No se entendio si la frustracion esta conectada con el dinero.');
    }

    // =====================================================================
    // Segundo (y ultimo) peldaño de la urgencia. Se lee igual que M4_ENVIADO,
    // pero de aca ya no hay reformulacion: o se entiende, o va a un humano.
    case 'M4_URGENCIA_REINTENTO':
    case 'M4_ENVIADO': {
      if (!c.urgencia && (c.objecion_num || c.objecion_detectada)) {
        return manejarObjecion(estado, c, nombre, 'Objecion al preguntar por la urgencia (M4).');
      }
      // Bifurcacion oficial post-Objecion 9 del SOP: "Tiene sentido, agendemos"
      // -> se avanza al cierre. Aceptar agendar ES mostrar urgencia, asi que se
      // trata como tal y el lead pasa por el pitch antes del link.
      // Antes esto exigia ADEMAS un `detectarAceptacion(textoLead)` por regex.
      // Se quito (6-sep-2026): `acepta` ya lo decide el LLM, y el regex era
      // justo el que leia "si, ahora tengo mas claro que NO quiero" como una
      // aceptacion.
      if (!c.urgencia && c.acepta === true) {
        return {
          mensajes: [render(P.M5_P1, nombre), render(P.M5_P2, nombre)],
          etapaNueva: 'M5_ENVIADO', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { urgencia_raw: 'ahora', califica: true },
          permitirEmpatia: false,
          summary: 'Acepta agendar tras la Objecion 9. Se trata como urgencia "ahora" y se envia el pitch.',
        };
      }
      if (c.urgencia === 'pregunta_por_que') {
        return manejarObjecion(estado, { ...c, objecion_num: 9, objecion_conocida: true }, nombre,
          'Objecion 9 (por que ahora) en el filtro de urgencia.');
      }
      if (c.urgencia === 'algun_dia') {
        return {
          mensajes: partirEnBurbujas(render(P.DESC_URGENCIA, nombre)),
          etapaNueva: 'DESCALIFICADO', estadoDestino: 'descalificado',
          handoffRazon: null,
          motivoPerdida: 'Descalificado - Sin urgencia',
          campos: { urgencia_raw: 'algun_dia', califica: false },
          permitirEmpatia: false,
          summary: 'Filtro 3 no superado: sin urgencia real.',
        };
      }
      if (c.urgencia === 'ahora') {
        // Los 3 filtros superados = lead CALIFICADO. Este es el momento en que
        // el bot escribe 'calificado' en la base (nunca 'agendado': ese lo
        // escribe solo la sincronizacion de Google Calendar).
        return {
          mensajes: [render(P.M5_P1, nombre), render(P.M5_P2, nombre)],
          etapaNueva: 'M5_ENVIADO', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { urgencia_raw: 'ahora', califica: true },
          permitirEmpatia: false, // el pitch entra directo, sin preambulo
          summary: 'Filtro 3 superado. Lead CALIFICADO (3/3 filtros). Se envia el pitch.',
        };
      }
      // Peldaño 2 del Filtro 3. Antes se escalaba al PRIMER "no entendi", que es
      // lo que el fundador señalo como escalamiento prematuro. La reformulacion
      // cambia el marco temporal en vez de repetir la misma pregunta.
      // `etapa !== ...` cierra el bucle: la etapa de reintento cae en este mismo
      // case, asi que sin esta guarda volveria a ofrecerse el reintento para
      // siempre y el lead nunca llegaria a un humano.
      if (ESCALERA_REPREGUNTAS_HABILITADA && etapa !== 'M4_URGENCIA_REINTENTO') {
        return {
          mensajes: [render(P.M4_URGENCIA_REINTENTO, nombre)],
          etapaNueva: 'M4_URGENCIA_REINTENTO', estadoDestino: null,
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'No se pudo leer la urgencia. Se reformula una vez antes de escalar.',
        };
      }
      // El peldaño terminal dejo de escalar (6-sep-2026): su contrato era "no
      // ofrece otro peldaño", y se mantiene -- no se le da otra plantilla de
      // reintento. Lo que si se le da es una respuesta razonada al mensaje que
      // no se entendio, que no es un peldaño mas del guion.
      if (etapa === 'M4_URGENCIA_REINTENTO') {
        return reencauzar(estado, c, nombre,
          'No se pudo leer la urgencia ni tras la reformulacion.',
          'Ya se le pregunto dos veces si resolver esto es prioridad ahora y su respuesta sigue sin entenderse. Responde a lo que acaba de decir con el playbook y ayudale a aterrizar si es para ahora o para mas adelante. Sin presionarlo.');
      }
      // Reencauzar (5-sep-2026): antes escalaba en silencio ante CUALQUIER
      // respuesta no clasificable -- exactamente el caso real reportado
      // ("cual es la diferencia si lo hago ahora o despues?" mal leido, luego
      // "como asi?" sin respuesta). Ahora el LLM contesta con contexto y
      // reencauza, hasta 3 veces insistiendo en la misma duda.
      return reencauzar(estado, c, nombre, 'No se pudo leer la urgencia con confianza.');
    }

    // =====================================================================
    // Segundo (y ultimo) peldaño tras el pitch. Misma regla que M4.
    case 'M5_PITCH_REINTENTO':
    case 'M5_ENVIADO': {
      // OBJECION ANTES QUE ACEPTACION -- la misma regla que ya existe en M1 y
      // M2, y que aca faltaba. El QA del 4-sep lo pago: "esperame, antes me
      // gustaria tener mas claro de que trata el protocolo" es la objecion 8, y
      // se leyo como aceptacion. Le mando el link a quien dijo "esperame".
      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion tras el pitch.');
      }
      if (c.acepta) {
        // ORDEN DEL CIERRE (fundador, 4-sep-2026): M5 -> M6 (link) -> M7
        // (acompañante) -> M8. La pregunta del acompañante ya NO va en este
        // turno, y la razon salio del QA: iba junto al link, asi que un "emm
        // si" del lead era ambiguo -- podia contestar al acompañante o al
        // "¿ya agendaste?". El LLM lo leyo como agendamiento confirmado y salto
        // hasta el cierre. Separando los turnos, esa ambiguedad no existe.
        //
        // ⚠️ EL LINK ES LA ULTIMA BURBUJA Y VA SOLO. Bug confirmado en
        // produccion: si va texto despues, Instagram los concatena y deja el
        // link invalido ("Dynamic Link Not Found").
        return {
          mensajes: [
            render(P.M6_SALUDO, nombre),
            render(P.M6_CONFIRMAME, nombre),
            P.M6_LINK,                     // SIEMPRE la ultima, y sola
          ],
          etapaNueva: 'M6_ENVIADO',
          estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { calendario_enviado: true },
          permitirEmpatia: false, // REGLA CRITICA DEL LINK
          summary: 'Acepta agendar. Se envia el link aislado; la pregunta del acompañante va en el turno siguiente (M7).',
        };
      }
      // Peldaño 2 tras el pitch, misma razon que M4. La reformulacion le da
      // salida honesta ("si no es el momento, me lo dices"): un "no" claro es
      // una respuesta valida y deja de ser un lead atascado.
      // Misma guarda anti-bucle que en M4.
      if (ESCALERA_REPREGUNTAS_HABILITADA && etapa !== 'M5_PITCH_REINTENTO') {
        return {
          mensajes: [render(P.M5_PITCH_REINTENTO, nombre)],
          etapaNueva: 'M5_PITCH_REINTENTO', estadoDestino: null,
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'Respuesta al pitch no clasificable. Se reformula una vez antes de escalar.',
        };
      }
      // Peldaño terminal: mismo criterio que M4_URGENCIA_REINTENTO, ver ese
      // comentario. Ya no escala: no ofrece otro peldaño, pero si responde.
      if (etapa === 'M5_PITCH_REINTENTO') {
        return reencauzar(estado, c, nombre,
          'Respuesta al pitch no clasificable ni tras la reformulacion.',
          'Ya se le hizo el pitch de la llamada y se le repregunto directo, y su respuesta sigue sin entenderse. Responde a lo que acaba de decir con el playbook. Si lo que tiene es una duda sobre la llamada, resuelvela.');
      }
      // Reencauzar (5-sep-2026): mismo criterio que en M4 -- ver ese comentario.
      return reencauzar(estado, c, nombre, 'Respuesta al pitch no clasificable.');
    }

    // =====================================================================
    // Turno siguiente al link: aca SI se puede mandar texto, porque el link
    // ya salio solo en su propio turno.
    // El link ya salio. Aca se espera a que el lead diga que agendo.
    case 'M6_ENVIADO': {
      // "¿donde me agendo?" / "no me llego el link". El LLM SEÑALA que lo pide;
      // el link lo reenvia el router desde la plantilla aprobada, aislado y de
      // ultimo. El LLM nunca teclea una URL -- un link generado seria a la vez
      // una violacion de la regla del link y un vector de suplantacion.
      // ⚠️ `sin_horarios` SE EVALUA ANTES QUE `pide_link`, y el orden es el
      // arreglo (11-sep-2026). "No veo espacios disponibles" activa los DOS
      // campos: el lead esta hablando del calendario, asi que el clasificador
      // marca `pide_link`, y ademas dice que no hay cupos. Con `pide_link`
      // primero, el bot le REENVIABA el link que el lead acababa de decir que
      // no le sirve -- y se quedaba en M6_ENVIADO, asi que cuando el lead
      // contestaba con su horario ("los viernes por la tarde") el turno caia
      // en la rama equivocada y le respondia "confirmame cuando te agendes".
      // Sin cupos NO se reenvia el link: se pide la franja y se escala.
      if (c.sin_horarios) {
        // No se salta directo a HANDOFF: P.SIN_HORARIOS hace una pregunta, y un
        // HANDOFF no recuperable en el mismo turno dejaba la respuesta del lead
        // en silencio total (bug real 5-sep-2026). El handoff ya queda puesto
        // (el Setter se entera YA); falta un turno para capturar la franja y
        // despedirse bien -- ver el case SIN_HORARIOS_ESPERANDO_FRANJA.
        return {
          mensajes: [render(P.SIN_HORARIOS, nombre)],
          etapaNueva: 'SIN_HORARIOS_ESPERANDO_FRANJA', estadoDestino: null,
          handoffRazon: 'agendamiento_manual_pendiente',
          motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'No encuentra horarios. Se le pide la franja y se escala para agendar a mano.',
        };
      }
      if (c.pide_link) {
        return {
          mensajes: [render(P.M6_CONFIRMAME, nombre), P.M6_LINK],
          etapaNueva: 'M6_ENVIADO', estadoDestino: null,
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false, // REGLA CRITICA DEL LINK
          summary: 'Pide el link otra vez. Se reenvia la plantilla aprobada, aislada.',
        };
      }
      if (c.confirmo_agendo) {
        // Confirmo que agendo -> AHORA si la pregunta del acompañante.
        return {
          mensajes: [render(P.M7, nombre)],
          etapaNueva: 'M7_ENVIADO', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: true,
          summary: 'Confirma que agendo. Se pregunta si asistira solo o acompañado (M7).',
        };
      }
      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion despues de enviar el link.');
      }
      // Ni confirma ni objeta: se le recuerda que confirme, SIN reenviar el link
      // (ya lo tiene) y sin avanzar.
      return {
        mensajes: [render(P.M6_CONFIRMAME, nombre)],
        etapaNueva: 'M6_ENVIADO', estadoDestino: null,
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: true,
        summary: 'Sigue en M6 esperando que confirme el agendamiento.',
      };
    }

    // =====================================================================
    // ORDEN NUEVO (4-sep-2026): a M7 solo se llega DESPUES de que el lead
    // confirmo que agendo. Aca se pregunta el acompañante, y su respuesta cierra
    // con M8. Antes esta pregunta viajaba junto al link y por eso un "emm si"
    // era ambiguo: el LLM lo leyo como "ya agende" y salto hasta el cierre.
    case 'M7_ENVIADO': {
      if (c.sin_horarios) {
        // No se salta directo a HANDOFF: P.SIN_HORARIOS hace una pregunta, y un
        // HANDOFF no recuperable en el mismo turno dejaba la respuesta del lead
        // en silencio total (bug real 5-sep-2026). El handoff ya queda puesto
        // (el Setter se entera YA); falta un turno para capturar la franja y
        // despedirse bien -- ver el case SIN_HORARIOS_ESPERANDO_FRANJA.
        return {
          mensajes: [render(P.SIN_HORARIOS, nombre)],
          etapaNueva: 'SIN_HORARIOS_ESPERANDO_FRANJA', estadoDestino: null,
          handoffRazon: 'agendamiento_manual_pendiente',
          motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'No encuentra horarios. Se le pide la franja y se escala para agendar a mano.',
        };
      }
      // Vuelve a pedir el link estando ya en M7: se reenvia aislado, sin avanzar.
      if (c.pide_link) {
        return {
          mensajes: [P.M6_LINK],
          etapaNueva: 'M7_ENVIADO', estadoDestino: null,
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false, // REGLA CRITICA DEL LINK
          summary: 'Pide el link de nuevo en M7. Se reenvia solo, sin texto despues.',
        };
      }

      // La respuesta al acompañante CIERRA la conversacion con M8.
      if (c.acompanado === true || c.acompanado === false) {
        const acompanado = c.acompanado === true;
        return {
          mensajes: acompanado
            ? [render(P.M7_ACOMPANADO, nombre), render(P.CIERRE_PRECALL, nombre)]
            : [render(P.M7_SOLO_ACK, nombre), render(P.CIERRE_PRECALL, nombre)],
          etapaNueva: 'CIERRE_PRECALL', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { asiste_acompanado: acompanado },
          // ⚠️ El estado NO avanza a `agendado`: eso lo escribe unicamente la
          // sync de Google Calendar, y hay guarda dura en la base.
          permitirEmpatia: true,
          summary: acompanado
            ? 'Asistira acompañado. Se le pide cuadrar y se cierra con las preguntas pre-llamada (M8).'
            : 'Asistira solo. Se cierra con las preguntas pre-llamada (M8).',
        };
      }

      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion tras confirmar el agendamiento.');
      }

      // No se entendio si va solo o acompañado: se repregunta una vez, no se
      // adivina. Adivinar aca fue justo lo que rompio el QA.
      return {
        mensajes: [render(P.M7, nombre)],
        etapaNueva: 'M7_ENVIADO', estadoDestino: null,
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: true,
        summary: 'No se entendio la respuesta del acompañante. Se repregunta sin avanzar.',
      };
    }

    // =====================================================================
    // Ya dijo que agendo y se le acuso recibo; falta que el Setter vincule la
    // reunion. El bot espera en SILENCIO -- solo reacciona a lo que de verdad
    // necesita accion: que no encuentre horarios, o una objecion tardia.
    case 'M7_ESPERANDO_VINCULO': {
      if (c.sin_horarios) {
        // Mismo arreglo que en M6/M7: no saltar directo a HANDOFF (ver comentario
        // arriba y el case SIN_HORARIOS_ESPERANDO_FRANJA).
        return {
          mensajes: [render(P.SIN_HORARIOS, nombre)],
          etapaNueva: 'SIN_HORARIOS_ESPERANDO_FRANJA', estadoDestino: null,
          handoffRazon: 'agendamiento_manual_pendiente',
          motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'Dijo que agendo pero no encuentra horarios. Se escala para agendar a mano.',
        };
      }
      if (estado?.tiene_reunion) {
        return {
          mensajes: [render(P.CIERRE_PRECALL, nombre)],
          etapaNueva: 'CIERRE_PRECALL', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'El Setter ya vinculo la reunion. Se envian las preguntas pre-llamada.',
        };
      }
      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion tardia, esperando el vinculo de la reunion.');
      }
      return {
        mensajes: [], etapaNueva: null, estadoDestino: null,
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: 'Esperando que el Setter vincule la reunion. Solo se registra.',
      };
    }

    // =====================================================================
    // UN SOLO TURNO: captura la franja que el lead acaba de dar en respuesta a
    // P.SIN_HORARIOS y se despide bien, en vez de dejarlo en silencio (bug real
    // 5-sep-2026 -- ver los 3 sitios que entran aca). El handoff ya estaba
    // puesto desde el turno anterior (el Setter se entero YA); esto solo cierra
    // la conversacion con el lead. `decidirSiResponder` tiene una excepcion
    // puntual para esta etapa: sin ella, el handoff ya activo silenciaria este
    // turno antes de llegar aca.
    //
    // Guarda anti-bucle: siempre sale a HANDOFF sin importar que responda el
    // lead -- no hay forma de quedarse dando vueltas en esta etapa.
    case 'SIN_HORARIOS_ESPERANDO_FRANJA': {
      const franja = String(textoLead || '').trim().slice(0, 200);
      const generada = CATCHALL_LLM_HABILITADO && typeof c?.respuesta_empatica === 'string'
        ? c.respuesta_empatica.trim()
        : '';
      const cierre = generada || render(P.SIN_HORARIOS_CIERRE, nombre);
      return {
        mensajes: [cierre],
        etapaNueva: 'HANDOFF', estadoDestino: null,
        // ⚠️ `null` A PROPOSITO, no es un descuido. CASO MARLY (7-sep-2026):
        // el handoff YA se creo en M6/M7 cuando el lead dijo que no encontraba
        // horarios (esa fue la Alerta 1). Repetir la razon aca disparaba una
        // SEGUNDA alerta en Google Chat por el mismo caso, media hora despues,
        // y le llegaba al Setter como si fuera un lead nuevo.
        //
        // Devolver null NO pierde el handoff: `fn_bot_procesar_turno` asigna
        // `handoff_razon = coalesce(nullif(btrim(p_handoff_razon),''), handoff_razon)`,
        // asi que null CONSERVA el valor que ya estaba. El lead queda igual de
        // escalado, en HANDOFF, y el Setter recibe UNA alerta, no dos.
        //
        // De paso deja de reaplicarse el tag HANDOFF_AGENDAMIENTO_MANUAL_PENDIENTE
        // en ManyChat, que era ruido del mismo origen.
        handoffRazon: null,
        motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        // El Worker usa esto para eximir la burbuja de la lista blanca y para
        // dejar constancia de que fue texto generado (mismo contrato que reencauzar()).
        textoGenerado: generada || null,
        summary: `Franja informada por el lead: "${franja}". Se le confirmo el cierre `
          + `(${generada ? 'generado por el LLM' : 'plantilla estandar'}) y queda en HANDOFF definitivo. `
          + 'No se re-notifica: la alerta salio cuando dijo que no encontraba horarios.',
      };
    }

    // =====================================================================
    // Embudo cerrado y el lead escribe algo corto de despedida. NO es un lead
    // que vuelve: es la reaccion al cierre. Se le reconoce y se cierra de
    // verdad -- nada de saludarlo de nuevo ni de sacarle otra pregunta.
    case 'CIERRE_PRECALL': {
      if (detectarAgradecimiento(textoLead) && !c.objecion_num && !c.crisis && !c.hostil) {
        return {
          mensajes: [render(P.CIERRE_AGRADECIMIENTO, nombre)],
          etapaNueva: 'BLINDAJE_CERRADO', estadoDestino: null,
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'Agradece con el embudo ya cerrado. Se despide y se cierra la conversacion para siempre.',
        };
      }
      return {
        mensajes: [], etapaNueva: null, estadoDestino: null,
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: 'Escribe con el embudo cerrado y no es una despedida. Solo se registra.',
      };
    }

    case 'BLINDAJE_ENVIADO':   // legado: etapas de leads anteriores al 3-sep
    case 'BLINDAJE_CERRADO':
    case 'RETORNO_PREGUNTA':
    case 'DESCALIFICADO':
    case 'HANDOFF':
    default:
      return {
        mensajes: [], etapaNueva: null, estadoDestino: null,
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: `Sin accion automatica para la etapa ${etapa}. Solo se registra.`,
      };
  }
}

/**
 * ¿En que etapa retomar a un lead cuyo `etapa_bot` no sirve de guia?
 *
 * Pasa al recuperar un handoff: la etapa quedo en 'HANDOFF', que no dice donde
 * iba. Se deduce de los DATOS que ya tiene, que es la fuente mas confiable:
 * el primer filtro que le falte es donde se retoma.
 */
export function etapaParaRetomar(estado) {
  if (!estado?.salario_monto) return 'M1_ENVIADO';
  if (estado.endeudamiento_pct === null || estado.endeudamiento_pct === undefined) return 'M2_ENVIADO';
  if (!estado.dolor) return 'M3_ENVIADO';
  if (!estado.urgencia) return 'M4_ENVIADO';
  return 'M5_ENVIADO';
}

// ---------------------------------------------------------------------------
// 5. Objeciones + reglas de escalamiento
// ---------------------------------------------------------------------------
/**
 * CATCH-ALL — que hacer cuando el mensaje del lead no encaja en ningun camino.
 *
 * Dos capas, en este orden:
 *  1. Si el LLM produjo una respuesta empatica y sobrevivio al saneo del
 *     Worker, se antepone. Es texto GENERADO: el verificador lo somete a
 *     `verificarTextoGenerado` en vez de a la lista blanca.
 *  2. Siempre se reenvia la pregunta pendiente de la etapa, para devolver la
 *     conversacion al carril. Esta capa es determinista y no depende del LLM.
 *
 * Si la etapa no tiene pregunta pendiente que reenviar, no hay a donde
 * reencauzar: eso si va a un humano.
 */
export function reencauzar(estado, c, nombre, contexto = '', situacionParaLLM = null, reemplazaPlantilla = false) {
  const etapaActual = estado?.etapa_bot || null;
  const pendientes = preguntaPendiente(etapaActual, nombre);

  // EL TOPE, con su significado nuevo (6-sep-2026, auditoria B): ya no cuenta
  // "el lead insiste", cuenta "el LLM no responde". Un lead confuso NUNCA
  // escala -- se le razona la respuesta las veces que haga falta. Lo que si
  // escala es quedarse sin LLM: la It. 23 probo en vivo que con Groq caido el
  // bot repite el mismo mensaje indefinidamente, sordo a todo. Ver
  // UMBRALES.LLM_SIN_RESPUESTA_SEGUIDAS.
  const fallosLLM = c?.llm_fallo ? (estado?.ambiguedad_consecutiva || 0) + 1 : 0;
  if (c?.llm_fallo && fallosLLM >= UMBRALES.LLM_SIN_RESPUESTA_SEGUIDAS) {
    return HANDOFF('ambiguo', estado, {
      campos: { ambiguedad_consecutiva: 0 },
      summary: `${contexto} El LLM lleva ${fallosLLM} turnos seguidos sin responder (Groq caido o sin cupo): no hay con que razonar, entra un humano.`,
    });
  }

  // Sin pregunta pendiente no hay carril al que volver NI mensaje determinista
  // que enviar. Se deja escalar a proposito: devolver `mensajes: []` esperando
  // que el LLM rellene el turno es exactamente como se producen los silencios
  // (It. 20 y It. 23). Son etapas post-embudo (ej. CIERRE_PRECALL), donde que
  // el Setter vea el mensaje es lo correcto.
  if (!pendientes.length) {
    return HANDOFF('ambiguo', estado, {
      campos: { ambiguedad_consecutiva: 0 },
      summary: `${contexto} Sin pregunta pendiente en ${etapaActual}: no hay a donde reencauzar.`,
    });
  }

  // `respuesta_empatica` (catch-all) vs. respuesta ANCLADA al playbook: cuando
  // el router trae una instruccion explicita (`situacionParaLLM`) gana la
  // anclada, y no es preferencia estetica. Caso real visto en la verificacion
  // del 6-sep-2026, con el dolor no financiero: el catch-all cerro con "¿Te
  // gustaria que hablemos de...?" y JUSTO DEBAJO salio la plantilla, que
  // pregunta otra cosa. Dos preguntas seguidas, con tonos distintos. El
  // catch-all no sabe que hay una burbuja detras ni tiene el playbook; la
  // llamada anclada sabe las dos cosas.
  const generada = !situacionParaLLM && CATCHALL_LLM_HABILITADO && typeof c?.respuesta_empatica === 'string'
    ? c.respuesta_empatica.trim()
    : '';

  // Lo que hay que resolverle al lead, para que el Worker lo redacte con el
  // playbook delante. Si el LLM enuncio una pregunta concreta se usa esa; si
  // no, se le pide razonar sobre el mensaje tal cual llego. Nunca se queda sin
  // razonamiento: eso es lo que pidio Gaby ("que haya un razonamiento frente a
  // todo mensaje"). `respuesta_empatica` sigue como respaldo, porque viene de
  // la MISMA llamada que ya se hizo y no cuesta un turno mas de Groq.
  // Prioridad: lo que el lead PREGUNTO gana sobre la instruccion del router.
  // Si el lead hizo una pregunta concreta, responderle eso es lo urgente.
  const aResolver = c?.pregunta_libre
    || situacionParaLLM
    || 'El lead escribio algo que el guion no tiene mapeado y no se pudo clasificar en ningun campo. Responde a lo que dijo apoyandote en el playbook, sin inventar, y sin repetir la pregunta que va justo despues.';

  return {
    mensajes: generada ? [generada, ...pendientes] : pendientes,
    // BUG REAL (marlyy318, 6-sep-2026): la pregunta pendiente se reenviaba
    // TEXTUAL. La lead recibio dos veces, con 54 segundos de diferencia,
    // "Última pregunta antes de contarte cómo funciona: ¿Resolver esto es una
    // prioridad AHORA...?" -- palabra por palabra. Medido despues en la base:
    // 84 turnos repetidos textualmente en 22 leads. Y viola una regla dura que
    // ya estaba escrita ("nunca el mismo mensaje dos veces"), que nadie
    // vigilaba porque la compuerta mira cada turno AISLADO, sin memoria.
    //
    // Se marca cual burbuja es un REENVIO para que el Worker deje al LLM
    // reformularla. Es un indice, no el texto: el router no redacta.
    reenvioPendienteIdx: generada ? 1 : 0,
    // No avanza el guion: reencauzar no es progresar.
    etapaNueva: etapaActual, estadoDestino: null,
    handoffRazon: null, motivoPerdida: null,
    campos: { ambiguedad_consecutiva: fallosLLM },
    permitirEmpatia: false,
    // El Worker lo usa para eximir esta burbuja de la lista blanca y para
    // dejarlo anotado en el activity_log como texto generado.
    textoGenerado: generada || null,
    // Solo se pide redaccion nueva si el catch-all no trajo ya una respuesta:
    // dos textos generados encima de la pregunta pendiente satura el DM.
    preguntaLibre: generada ? null : aResolver,
    // Cuando la plantilla determinista CONTRADICE lo que se le pide al LLM
    // (ej. el cierre del dolor no financiero, que insinua "no eres buen fit"),
    // la respuesta anclada la reemplaza en vez de anteponerse. La plantilla
    // sigue siendo el fallback si el LLM no responde.
    preguntaLibreReemplaza: reemplazaPlantilla && !generada,
    summary: generada
      ? `${contexto} Reencauce con respuesta generada + la pregunta pendiente.`
      : `${contexto} Reencauce: se razona la respuesta con el playbook y se reenvia la pregunta pendiente.`,
  };
}

export function manejarObjecion(estado, c, nombre, contexto = '') {
  // POLITICA DE ESCALAMIENTO (6-sep-2026, decision de Gaby tras la auditoria B):
  // "la unica objecion que debe escalarse a un setter es cuando el lead llega a
  // la fase final y no encuentra espacios en el calendar; en las anteriores
  // etapas si se puede manejar con el playbook". Antes, una objecion que no
  // fuera una de las 9 iba directo a un humano -- pero el bot tiene el playbook
  // completo y puede responderla, o decir con honestidad que eso se ve en la
  // llamada. Se reencauza en vez de escalar.
  if (!c.objecion_num || !OBJECIONES[c.objecion_num]) {
    return reencauzar(estado, c, nombre,
      `${contexto} Objecion que no es ninguna de las 9 del playbook: se razona la respuesta.`);
  }

  const num = String(c.objecion_num);
  const anterior = estado?.ultima_objecion_codigo || null;
  const repiteLaMisma = Boolean(anterior) && anterior === num;

  // CURIOSIDAD vs RESISTENCIA (QA 4-sep-2026). Solo lo que de verdad frena el
  // embudo suma al tope. Preguntar "¿es gratis?", "¿cuanto cuesta?" o "quiero
  // saber mas" son señales de COMPRA: contarlas como resistencia escalo a una
  // lead que 30 segundos despues escribio "mejor si, agendemos".
  const esResistencia = OBJECION_ES_RESISTENCIA.has(Number(c.objecion_num));
  const consecutivas = esResistencia
    ? (estado?.objeciones_consecutivas || 0) + 1
    : (estado?.objeciones_consecutivas || 0);

  // ─────────────────────────────────────────────────────────────────────────
  // LOS TRES TOPES DE ESCALAMIENTO POR OBJECION SE RETIRARON (6-sep-2026).
  //
  // Eran: repetir la objecion 7 (`pregunta_precio`), repetir cualquier objecion
  // (`resistencia_repetida`) y acumular 4 de resistencia (`resistencia_acumulada`).
  // Los tres compartian el mismo supuesto: "la plantilla ya no le sirvio, que
  // entre un humano". Ese supuesto era cierto cuando la unica respuesta posible
  // era la MISMA plantilla literal -- repetirla no aportaba nada.
  //
  // Dejo de serlo con la auditoria B: ahora el LLM puede reformular la objecion
  // con el contexto de la conversacion (ADAPTAR_OBJECIONES_CON_LLM) y responder
  // con el playbook completo delante (RESPONDER_PREGUNTAS_CON_LLM). Insistir ya
  // no es repetirse: es responder distinto. Y un lead que pregunta el precio dos
  // veces es un lead interesado, no uno que haya que sacar del embudo.
  //
  // El CONTADOR se mantiene: alimenta el dashboard y deja la señal para el
  // Setter en el summary. Lo que se retiro es el HANDOFF, no la medicion.
  //
  // Lo que sigue escalando: seguridad (crisis/hostil/ex-cliente), no encontrar
  // horarios en el calendario, y que el LLM lleve N turnos caido.
  const insiste = repiteLaMisma
    ? ` El lead REPITE la objecion ${num} (${consecutivas} seguidas): la respuesta anterior no le sirvio, hay que responderle distinto.`
    : '';

  // MATRIZ DE FASES (fundador, 4-sep-2026). Una objecion fuera de la fase donde
  // el Setter humano la ve de verdad casi siempre significa que el clasificador
  // leyo mal, no que el lead objete eso: "no tengo tiempo" en M1, cuando todavia
  // no se le ha propuesto ninguna llamada, no es la Objecion 2. Contestarle con
  // la plantilla seria responder a algo que nadie dijo. Se reencauza.
  //
  // El orden respecto a los topes dejo de importar el 6-sep-2026: los topes de
  // objecion se retiraron (ver arriba), asi que ya no hay nada que pueda
  // "ganarle" a la matriz. El comentario historico decia que ponerla antes
  // dejaba a un lead reencauzando para siempre sin llegar a un humano -- hoy
  // eso es justamente el comportamiento buscado, con la red del LLM caido.
  const etapaDelLead = estado?.etapa_bot || null;
  if (!objecionPermitidaEn(c.objecion_num, etapaDelLead)) {
    return reencauzar(estado, c, nombre,
      `${contexto} Objecion ${num} fuera de su fase (el lead esta en ${faseDeEtapa(etapaDelLead) || 'sin etapa'}).`);
  }

  // Perilla de alcance: si una objecion se apaga, su plantilla no sale. Antes
  // eso mandaba el turno a un humano; desde el 6-sep-2026 se reencauza, que es
  // la misma politica que el resto. Apagar una objecion ahora significa "no
  // uses ESA plantilla", no "no atiendas a este lead". Hoy las 9 estan
  // habilitadas, asi que esta rama practicamente no se pisa.
  if (!OBJECIONES_HABILITADAS.has(Number(c.objecion_num))) {
    return reencauzar(estado, c, nombre,
      `${contexto} Objecion ${num} reconocida pero con la plantilla apagada: se razona la respuesta con el playbook.`);
  }

  // ANTES DEL PITCH la objecion no puede terminar en un cierre de agenda: el
  // lead todavia no ha pasado los filtros de endeudamiento, dolor y urgencia.
  // Se usa la variante sin link y se REENVIA la pregunta que quedo pendiente,
  // para volver al carril de la calificacion.
  //
  // La Objecion 9 es la excepcion, y esta fundamentada: el SOP la predice justo
  // en M4 y su bifurcacion oficial contempla que el lead acepte agendar ahi
  // mismo. Ademas no lleva link, y cierra con su propia pregunta -- pegarle la
  // de urgencia dejaria dos preguntas seguidas.
  const etapaActual = estado?.etapa_bot || null;
  const esPrePitch = ETAPAS_PRE_PITCH.has(etapaActual);

  // Hay plantillas que ya terminan preguntando algo (la 5 pregunta "¿que te
  // gustaria saber?"; la 9 cierra con "¿Agendamos los 30 minutos?"). A esas NO
  // se les pega ademas la pregunta pendiente: serian dos preguntas seguidas y
  // el lead no sabe cual contestar. Sale de la tabla, no de un `!== 9` a mano.
  const traePreguntaPropia = OBJECIONES_CON_PREGUNTA_PROPIA.has(Number(c.objecion_num));

  // CASO ESPECIAL: la Objecion 6 mientras se evalua el Filtro 1.
  //
  // "Ese dato es delicado" + la pregunta pendiente de M1 = "te entiendo, pero
  // dime a que te dedicas y cuanto ganas". Es pedirle otra vez lo mismo que
  // acaba de negarse a dar, y se lee como presion. Regla de negocio: en M1 se
  // le PERDONA la profesion y la cifra exacta, y se le pregunta solo por el
  // rango -- que se contesta con un "Si".
  //
  // Por eso tambien avanza a M1_RANGO_PREGUNTADO: sin eso el bot haria la
  // pregunta del rango pero seguiria escuchando en M1_ENVIADO, donde un "Si"
  // pelado no es una respuesta valida de ingreso y volveria a atascarse.
  // Es la unica objecion que mueve de etapa, y mueve a la etapa que le
  // corresponde a la pregunta que acaba de hacer.
  const esObjecion6EnM1 = esPrePitch
    && Number(c.objecion_num) === 6
    && ETAPAS_FILTRO_1.has(etapaActual);

  const plantilla = esObjecion6EnM1
    ? OBJ_6_EN_M1
    : esPrePitch
      ? (OBJECIONES_PRE_PITCH[num] || OBJECIONES[c.objecion_num])
      : OBJECIONES[c.objecion_num];

  // La segunda burbuja de este caso es un REENVIO: la pregunta de la etapa ya
  // se le hizo al lead cuando entro en ella. Reenviarla textual fue el bug de
  // marlyy318 (ver `reenvioPendienteIdx` en reencauzar). La de la Objecion 6
  // en M1 NO cuenta: P.M1_PEDIR_RANGO es una pregunta NUEVA, no un reenvio.
  const reenviaPendiente = !esObjecion6EnM1 && esPrePitch && !traePreguntaPropia;

  const mensajes = esObjecion6EnM1
    ? [render(plantilla, nombre), render(P.M1_PEDIR_RANGO, nombre)]
    : esPrePitch
      ? (traePreguntaPropia
        ? [render(plantilla, nombre)]
        : [render(plantilla, nombre), ...preguntaPendiente(etapaActual, nombre)])
      : partirEnBurbujas(render(plantilla, nombre));

  const llevaLink = mensajes.some((m) => /https?:\/\//.test(m));
  return {
    mensajes,
    // Se queda en la misma etapa: tras manejar la objecion se retoma donde
    // estaba, no se avanza el guion. La unica excepcion es la 6 en M1, que
    // pasa a esperar la respuesta del rango (ver arriba).
    etapaNueva: esObjecion6EnM1 ? 'M1_RANGO_PREGUNTADO' : etapaActual,
    estadoDestino: null,
    handoffRazon: null, motivoPerdida: null,
    campos: esObjecion6EnM1
      // No se toca `profesion`: el lead no la dio y aqui se decidio no pedirla.
      ? { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas, ingreso_confirmado: false }
      : { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
    // La apertura personalizada se permite SOLO si el turno no lleva link.
    // Con link, la primera burbuja es texto y la ultima es la URL sola; meterle
    // un prefijo generado al texto es seguro, pero se prefiere no tocar el turno
    // mas fragil del embudo -- es el que ya se rompio una vez en produccion.
    permitirEmpatia: !llevaLink,
    // Adaptacion de objeciones con LLM (6-sep-2026, ver ADAPTAR_OBJECIONES_CON_LLM):
    // el Worker puede reescribir el FRASEO de esta burbuja especifica (nunca
    // inventa cifras nuevas, verificado aparte). Mismo criterio que la apertura:
    // nunca con link en el turno. El router solo EXPONE el texto aprobado
    // original -- decidir si se adapta y como es responsabilidad del Worker.
    objecionPlantillaOriginal: llevaLink ? null : render(plantilla, nombre),
    reenvioPendienteIdx: reenviaPendiente ? 1 : null,
    summary: (esObjecion6EnM1
      ? `${contexto} Objecion 6 en ${etapaActual}: se le quita la presion de la profesion y la cifra exacta, y se le pregunta solo por el rango $7M-$15M.`
      : esPrePitch
        ? `${contexto} Objecion ${num} respondida SIN cierre de agenda (el lead aun se esta calificando) y se reenvia la pregunta pendiente.`
        : `${contexto} Se responde con la Objecion ${num}.`) + insiste,
  };
}

// ---------------------------------------------------------------------------
// 6. Helpers deterministas de deteccion (sin LLM)
// ---------------------------------------------------------------------------
export function detectarVarianteM1(texto) {
  const t = String(texto || '').toLowerCase();
  if (/\bcontrol\b/.test(t)) return 'M1_CONTROL';
  if (/\bclaridad\b/.test(t)) return 'M1_CLARIDAD';
  return 'M1_GENERAL';
}

/** Confirmaciones de agendamiento -- suficientemente mecanico para no gastar LLM. */
export function detectarConfirmacionAgenda(texto) {
  const t = String(texto || '').toLowerCase();
  // Ojo con las conjugaciones: la primera version solo cubria "quede/quedé" y
  // se le escapaba "ya quedo agendado", que es como lo dice mucha gente.
  return /\b(ya\s*(me\s*)?(agend|reserv|separ)|list[oa]\s*(ya)?\s*(agend|qued)|qued[eéoó]\s*(agendad|separad|list)|(?:agend|reserv)[eé](?![a-záéíóúñ])|agendad[oa]|ya\s*qued[eéoó])/.test(t);
}





/**
 * Vocabulario de dinero, en RAICES.
 *
 * ⚠️ TRAMPA QUE YA COSTO DOS VECES: `\b` NO cierra entre dos letras. Escribir
 * `\bahorr\b` no casa "ahorrar" ni "ahorro" -- no casa NADA. La primera version
 * de este detector tenia cuatro raices asi (`ahorr`, `invers`, `financier`,
 * `econom`) y todas estaban muertas desde el dia uno: por eso una lead que
 * escribio "d. quiero ahorrar" salio por M3_RECONDUCIR. Las raices llevan `\b`
 * SOLO al inicio; el final queda abierto a proposito.
 *
 * Incluye lo que pidio el fundador el 4-sep: ahorro/ahorrar, inversion,
 * patrimonio y futuro tambien son dolor financiero valido. Querer construir NO
 * es un dolor distinto al de no poder construir: es el mismo lead.
 */
const RAICES_DE_DINERO = new RegExp(
  '(' + [
    // deuda y pagos
    '\\bdeud', '\\bdeb[oe]\\b', '\\bpag[oaá]', '\\bcuota', '\\btarjeta',
    '\\bcr[eé]dito', '\\bpr[eé]stamo', '\\bintere', '\\bmora\\b', '\\bcobr',
    // dinero
    // 'peso' en singular es el corporal ("bajar de peso"); el dinero va en
    // plural o como millones. Falso positivo real detectado al probar.
    '\\bplata\\b', '\\bdiner', '\\bpesos\\b', '\\bmillon', '\\bsalari', '\\bsueld', '\\bingres',
    '\\bquincena', '\\bnomina', '\\bn[oó]mina',
    // construir (lo que pidio el fundador)
    '\\bahorr', '\\binvers', '\\binvertir', '\\bpatrimoni', '\\bfuturo\\b',
    '\\brentab', '\\blibertad financiera', '\\bjubilac', '\\bpension',
    // marcos generales
    '\\bfinanci', '\\becon[oó]mic', '\\bgast', '\\bpresupuest',
    // frases
    'no me alcanza', 'no me rinde', 'fin de mes', 'sal y agua', 'vivir mal',
  ].join('|') + ')',
  'i',
);

/**
 * Serializa el dolor con EL MISMO formato que ya usa el dashboard
 * (`serializeDolor` en src/lib/data/estados.ts): letras ordenadas unidas por
 * coma, y si incluye D se le pega "|detalle". Asi el dato que escribe el bot y
 * el que escribe un Setter a mano son indistinguibles.
 */
export function serializarDolor(letras, detalle = '') {
  const ls = [...new Set(letras || [])].filter(Boolean).sort();
  if (ls.length === 0) return null;
  const base = ls.join(',');
  return ls.includes('D') && String(detalle).trim() ? `${base}|${String(detalle).trim()}` : base;
}

export function detectarDolorLetra(texto) {
  const t = String(texto || '').trim().toLowerCase();
  if (!t) return null;

  // 1. La letra sola: "B", "(c)", "d."
  const sola = t.match(/^\(?([abcd])\)?[\s.,:)]*$/);
  if (sola) return sola[1].toUpperCase();

  // 2. b/c/d al inicio seguidas de texto: "B sin duda...", "c) porque..."
  const inicio = t.match(/^\(?([bcd])\)?[\s.,:)]/);
  if (inicio) return inicio[1].toUpperCase();

  // 3. "a" al inicio SOLO con puntuacion, para no confundirla con la preposicion
  const inicioA = t.match(/^\(?a\)?[.,:)]/);
  if (inicioA) return 'A';

  // 4. Marcada explicitamente: "la B", "opcion C", "elijo la d"
  const marcada = t.match(/\b(?:la|el|opci[oó]n|respuesta|elijo|ser[ií]a)\s+\(?([abcd])\)?\b/);
  if (marcada) return marcada[1].toUpperCase();

  return null;
}

/** Aceptacion del pitch ("dale", "si", "agendemos"). */
export function detectarAceptacion(texto) {
  const t = String(texto || '').toLowerCase();
  if (!t.trim()) return false;

  // FRENOS que el QA del 4-sep dejo caros. El lead escribio "esperame, antes me
  // gustaria tener mas claro de que trata el protocolo" y esto devolvio TRUE:
  //   1. "claro" casaba dentro de "mas claro" -- que es pedir informacion, no
  //      aceptar. Ahora "claro" solo cuenta si no viene de "tener/mas/dejar/ver
  //      /saber claro".
  //   2. El freno de negacion solo miraba los primeros 12 caracteres, asi que
  //      "esperame, antes..." se le escapaba. Ahora mira el mensaje completo y
  //      cubre tambien "espera", "antes" y "primero", que son aplazamientos.
  if (/\b(espera|esperame|esper[aá]|antes|primero|todav[ií]a\s+no|aun\s+no|a[uú]n\s+no)\b/.test(t)) return false;

  const AFIRMA = /\b(dale|listo|s[ií]|dele|dal[eé]|dalee|dsl|dsp|de\s*una|dale\s*pues|agendemos|agendamos|me\s*sirve|dale\s*ah[ií]|perfecto|obvio|por\s*supuesto|hag[aá]moslo|vamos)\b/;

  // "no"/"aunque" al inicio SIEMPRE frenan. "pero" NO, si el mensaje trae una
  // afirmacion clara -- BUG REAL (5-sep-2026): "pero si agendemos" (tras la
  // Objecion 9) se leia como rechazo por la sola palabra "pero", cuando el
  // lead esta aceptando pese a la duda, no rechazando.
  if (/\b(no|aunque)\b/.test(t.slice(0, 20))) return false;
  if (/\bpero\b/.test(t.slice(0, 20)) && !AFIRMA.test(t)) return false;

  if (AFIRMA.test(t)) return true;

  // "claro" suelto SI es aceptacion ("claro", "claro que si"); pegado a un verbo
  // de entender, NO ("quiero tener mas claro", "para dejarlo claro").
  return /\bclaro\b/.test(t) && !/\b(m[aá]s|tener|dejar|ver|saber|entender|quede|queda)\s+(lo\s+)?claro/.test(t);
}



/** Agradecimiento tras el cierre -> dispara el blindaje del show-up. */
export function detectarAgradecimiento(texto) {
  const t = String(texto || '').toLowerCase();
  return /\b(gracias|grac|mil\s*gracias|te\s*agradezco|muy\s*amable|excelente|perfecto|listo)\b/.test(t)
      || /^\s*(🙏|👍|🙌|💪|😊)+\s*$/u.test(String(texto || '').trim());
}





/**
 * Vocabulario de plata colombiano, el mismo que entiende `parseIngresoCOP`.
 * Se mantiene junto al detector de porcentaje porque su unico trabajo es
 * distinguir "30" (porcentaje) de "30 millones" (monto).
 */
const MARCA_DE_PLATA =
  /(\bmillones?\b|\bmill[oó]n\b|\bmill\b|\bpalos?\b|\blucas?\b|\bmil\b|\bk\b|\bcop\b|\bpesos?\b|\bsmlv\b|\bsmmlv\b|salarios?\s*m[ií]nimos?|\$|\bd[oó]lares?\b|\busd\b|\beuros?\b|\bmensuales?\b\s*en\s*deuda)/;
