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

// ---------------------------------------------------------------------------
// 1. Glosario de ingreso colombiano (★ NUEVO V4.1)
// ---------------------------------------------------------------------------
/**
 * Convierte una expresion de ingreso en pesos colombianos al mes.
 *
 * Esta funcion existe por un caso real: se descarto a una lead que ganaba
 * $22M porque respondio "gano el minimo integral" y el bot leyo "minimo".
 * Por eso "integral" se evalua ANTES que "minimo", y ante cualquier duda
 * devuelve ambiguo:true -- que en el router NUNCA descalifica, solo pide la
 * cifra exacta (regla de descarte en 2 pasos del playbook).
 *
 * @returns {{monto: number|null, ambiguo: boolean, glosario: string|null, aproximado: boolean}}
 */
export function parseIngresoCOP(textoRaw) {
  const texto = String(textoRaw || '').toLowerCase().trim();
  if (!texto) return { monto: null, ambiguo: true, glosario: null, aproximado: false };

  const amb = (glosario) => ({ monto: null, ambiguo: true, glosario, aproximado: false });

  // ⚠️ VARIAS FUENTES DE INGRESO -> este parser SE ABSTIENE.
  //
  // QA del 4-sep-2026, y costo una descalificacion injusta: la lead escribio
  // "en mi trabajo son mas o menos 4 millones, de mi negocio familiar son 3
  // millones, y de un local donde soy socia recibo casi 4 millones" (11M). Este
  // parser agarraba la PRIMERA cifra -- 4M -- y como los deterministas GANAN
  // sobre el LLM, tapaba la suma correcta del modelo. La descalifico, y la lead
  // tuvo que reclamar ("pero eso suma mas de 7m, porque me descartas").
  //
  // Sumar aca seria adivinar: no se sabe si las cifras se suman (varias
  // fuentes), se restan (ingreso menos gastos) o son alternativas ("entre 4 y 6
  // millones"). Eso es comprension de lenguaje, y es trabajo del LLM. Aca se
  // aplica la misma regla que ya salvo al detector de endeudamiento:
  // ABSTENERSE ES MEJOR QUE ADIVINAR.
  if (cuentaCifrasDeDinero(texto) > 1) return amb('varias_fuentes');

  // (a) "integral" SIEMPRE primero. "minimo integral"/"salario integral" es un
  //     ingreso ALTO (~$18-22M+), jamas el salario minimo. No se asume la
  //     cifra: se pide, que es lo que manda el playbook. Lo importante es que
  //     este camino NUNCA puede terminar en descalificacion.
  if (/\bintegral\b/.test(texto)) return amb('salario_integral');

  // (b) Terminos que por definicion no traen cifra -> pedir el numero.
  if (/\b(comisi[oó]n|comisiones|variable|depende|var[ií]a|no\s+s[eé]|nose|depende\s+del\s+mes)\b/.test(texto)
      && !/\d/.test(texto)) {
    return amb('ingreso_variable');
  }

  const porQuincena = /\b(quincen|cada\s*15|por\s*15\s*d[ií]as)/.test(texto);
  const multQuincena = porQuincena ? 2 : 1;

  // (c) "X SMLV" / "X salarios minimos" / "X minimos"
  const smlv = texto.match(/(\d+(?:[.,]\d+)?)\s*(?:smlv|smmlv|salarios?\s*m[ií]nimos?|m[ií]nimos)\b/);
  if (smlv) {
    const n = parseFloat(smlv[1].replace(',', '.'));
    return { monto: Math.round(n * UMBRALES.SMLV_2026 * multQuincena), ambiguo: false, glosario: 'smlv', aproximado: true };
  }

  // (d) "el minimo" / "salario minimo" a secas (ya descartamos "integral")
  if (/\b(salario\s*m[ií]nimo|el\s*m[ií]nimo|m[ií]nimo\b)/.test(texto) && !/\d/.test(texto)) {
    return { monto: UMBRALES.SMLV_2026 * multQuincena, ambiguo: false, glosario: 'salario_minimo', aproximado: true };
  }

  // (e) "un palo" = $1M ; "X palos" = X millones
  const palos = texto.match(/(\d+(?:[.,]\d+)?|un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*palos?\b/);
  if (palos) {
    const palabras = { un: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7, ocho: 8, nueve: 9, diez: 10 };
    const n = palabras[palos[1]] ?? parseFloat(palos[1].replace(',', '.'));
    if (Number.isFinite(n)) {
      return { monto: Math.round(n * 1_000_000 * multQuincena), ambiguo: false, glosario: 'palos', aproximado: false };
    }
  }

  // (f) Moneda extranjera -> se convierte, marcado como aproximado.
  const usd = texto.match(/(?:us\$?|usd|d[oó]lares?)\s*(\d[\d.,]*)|(\d[\d.,]*)\s*(?:us\$?|usd|d[oó]lares?)/);
  if (usd) {
    const n = normalizarNumero(usd[1] || usd[2]);
    if (n) return { monto: Math.round(n * 4000 * multQuincena), ambiguo: false, glosario: 'usd', aproximado: true };
  }
  const eur = texto.match(/(?:eur|euros?|€)\s*(\d[\d.,]*)|(\d[\d.,]*)\s*(?:eur|euros?|€)/);
  if (eur) {
    const n = normalizarNumero(eur[1] || eur[2]);
    if (n) return { monto: Math.round(n * 4400 * multQuincena), ambiguo: false, glosario: 'eur', aproximado: true };
  }

  // (g) "X millones (y medio)" / "X millon" / "XM"
  const millones = texto.match(/(\d+(?:[.,]\d+)?)\s*(?:millones?|mill[oó]n|mill\b|m\b|'?millones)/);
  if (millones) {
    let n = parseFloat(millones[1].replace(',', '.'));
    if (/y\s*medio/.test(texto)) n += 0.5;
    if (Number.isFinite(n)) {
      return { monto: Math.round(n * 1_000_000 * multQuincena), ambiguo: false, glosario: 'millones', aproximado: false };
    }
  }

  // (h) Cifra escrita completa: 12.000.000 / 12'500.000 / 12,000,000 / 12500000
  const crudo = texto.match(/\d[\d.,'\s]{2,}\d|\d{4,}/);
  if (crudo) {
    const n = normalizarNumero(crudo[0]);
    if (n && n >= 1000) {
      return { monto: Math.round(n * multQuincena), ambiguo: false, glosario: 'cifra', aproximado: false };
    }
  }

  // (i) Numero suelto sin unidad: "gano 12". En Colombia casi siempre son
  //     millones, pero a partir de ~50 deja de ser obvio y entre 100 y 999
  //     puede ser "800 mil". Solo se asume millones en el rango seguro.
  const suelto = texto.match(/(?:^|\s)(\d{1,3})(?:\s|$)/);
  if (suelto) {
    const n = parseInt(suelto[1], 10);
    if (n >= 1 && n <= 50) {
      return { monto: n * 1_000_000 * multQuincena, ambiguo: false, glosario: 'numero_suelto_millones', aproximado: true };
    }
    return amb('numero_sin_unidad');
  }

  return amb('sin_cifra');
}

/**
 * Cuantas cifras de dinero DISTINTAS menciona el texto.
 *
 * Sirve para saber cuando el parser determinista tiene que callarse y dejarle
 * la interpretacion al LLM. No intenta sumar ni entender: solo contar.
 */
export function cuentaCifrasDeDinero(textoRaw) {
  const t = String(textoRaw || '').toLowerCase();
  if (!t.trim()) return 0;
  // Un rango ("entre 4 y 6 millones") es UNA sola idea de ingreso, no dos
  // fuentes: se neutraliza antes de contar para no abstenerse de mas.
  const sinRangos = t.replace(/\b(entre|de)\s+\d[\d.,]*\s*(?:y|a|-)\s*\d/g, ' RANGO ');
  const conUnidad = sinRangos.match(/\d[\d.,]*\s*(?:millones?|mill[oó]n|mill\b|m\b|palos?|lucas?|mil\b|k\b)/g) || [];
  const escritas = sinRangos.match(/\d[\d.,']{5,}/g) || [];
  return conUnidad.length + escritas.length;
}

function normalizarNumero(s) {
  if (!s) return null;
  const limpio = String(s).replace(/[\s.'’,]/g, '');
  const n = parseInt(limpio, 10);
  return Number.isFinite(n) ? n : null;
}

// ---------------------------------------------------------------------------
// 2. Los 3 filtros del SOP V4.2
// ---------------------------------------------------------------------------
/** Filtro 1: ingreso >= $7M COP/mes. */
export function evaluarIngreso(monto) {
  if (monto === null || monto === undefined) return 'ambiguo';
  return monto >= UMBRALES.INGRESO_MINIMO ? 'califica' : 'descalifica';
}

/**
 * Filtro 2 — el tope depende del ingreso (V4.0/V4.2):
 * gana ~$7M -> tope 50% ; gana >$9M -> tope 60%.
 */
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
 * Filtro 2 — 'ok' | 'borderline' | 'descalifica' | 'no_sabe'
 *
 * La regla del fundador (4-sep-2026):
 *   remanente >= 2.5M                    -> ok
 *   remanente <  2.5M  y deuda >= 50%    -> borderline: puede ser deuda BUENA
 *                                           (hipoteca), se pregunta antes de
 *                                           descartar
 *   remanente <  2.5M  y deuda <  50%    -> descalifica (le sobra poco y no es
 *                                           por las deudas: el ingreso no da)
 *
 * ⚠️ NOTA MATEMATICA, comprobada sobre todo el espacio 6M-30M: la ultima rama
 * es INALCANZABLE para quien paso el Filtro 1. Con ingreso >= 6M y deuda < 50%,
 * el remanente siempre supera 2.5M. Se deja escrita igual porque deja de ser
 * inalcanzable si el fundador baja el ingreso minimo por debajo de 5M, y porque
 * el ingreso puede llegar por otras vias (una cifra escrita a mano por el
 * Setter en el dashboard, por ejemplo). Hay un test que fija ambas cosas.
 */
export function evaluarEndeudamiento(pct, ingreso) {
  if (pct === null || pct === undefined) return 'no_sabe';
  const remanente = calcularRemanente(ingreso, pct);
  // Sin ingreso no se puede calcular remanente: no se adivina ni se descarta.
  if (remanente === null) return 'no_sabe';
  if (remanente >= UMBRALES.REMANENTE_MINIMO) return 'ok';
  return pct >= UMBRALES.ENDEUDAMIENTO_PARA_BORDERLINE ? 'borderline' : 'descalifica';
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

/** Si/no simple, para la respuesta a la pregunta de retorno. */
export function detectarSiNo(texto) {
  const t = String(texto || '').toLowerCase();
  if (/\b(no|nada|igual|lo\s*mismo|todav[ií]a\s*no|a[uú]n\s*no|sigue\s*igual)\b/.test(t)) return false;
  if (/\b(s[ií]|claro|ya|mejor[oó]|subi[oó]|baj[oó]|cambi[oó]|ahora\s*s[ií]|por\s*supuesto|dale)\b/.test(t)) return true;
  return null;
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
  if (c.crisis) return HANDOFF('crisis_emocional', estado, { estadoDestino: 'nutricion' });
  if (c.hostil) return HANDOFF('contenido_hostil', estado);
  if (c.ex_cliente) return HANDOFF('ex_cliente', estado);

  // --- Handoff recuperable: el bot solo vuelve a hablar si el lead lo pide ---
  if (estado?.handoff_razon) {
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
    return {
      mensajes: preguntaPendiente(retomaEn, nombre),
      etapaNueva: retomaEn, estadoDestino: null,
      handoffRazon: LIMPIAR_HANDOFF, motivoPerdida: null, campos: {},
      // Aca la apertura personalizada vale oro: el lead viene de un roce.
      permitirEmpatia: true,
      summary: `El lead pide continuar tras el handoff (${estado.handoff_razon}). Se recupera y se retoma en ${retomaEn}.`,
    };
  }

  // --- Lead nuevo: se envia el Mensaje 1 ---
  if (!etapa) {
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

    // Primera vez que vuelve: se le pregunta por el motivo EXACTO del descarte.
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
          // Ya se pidio la cifra una vez y sigue sin darla -> humano, jamas descarte.
          return HANDOFF('ambiguo', estado, {
            campos: { profesion: c.profesion ?? null },
            summary: 'Ingreso sigue ambiguo tras pedir la cifra. Handoff en vez de descartar (regla V4.1).',
          });
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
        if (etapa !== 'M1_ACLARAR_REMANENTE' && pareceRemanente(textoLead)) {
          return {
            mensajes: [render(P.M1_ACLARAR_REMANENTE, nombre)],
            etapaNueva: 'M1_ACLARAR_REMANENTE', estadoDestino: 'contactado',
            handoffRazon: null, motivoPerdida: null,
            campos: { profesion: c.profesion ?? null },
            permitirEmpatia: false,
            summary: `Ingreso ${ing} bajo el umbral PERO el texto sugiere que es remanente, no ingreso total. Se aclara antes de descalificar.`,
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
    case 'M2_NO_SABE': {
      const ingreso = estado?.salario_monto ?? c.ingreso_cop ?? null;
      let pct = c.endeudamiento_pct ?? null;
      
      if (pct === null && ingreso !== null && ingreso > 0) {
        if (c.deuda_cop != null) {
          pct = Math.round((c.deuda_cop / ingreso) * 100);
        } else if (c.remanente_cop != null) {
          const gastado = Math.max(0, ingreso - c.remanente_cop);
          pct = Math.round((gastado / ingreso) * 100);
        }
      }
      
      const veredicto = evaluarEndeudamiento(pct, ingreso);

      if (veredicto === 'no_sabe' && (c.objecion_num || c.objecion_detectada)) {
        // Igual que en M1: "esa info es sensible" es la Objecion 6, no un
        // "no se". Preguntar por deudas la dispara con la misma frecuencia.
        return manejarObjecion(estado, c, nombre, 'Objecion al pedir el endeudamiento (M2).');
      }
      if (veredicto === 'no_sabe') {
        if (etapa === 'M2_NO_SABE') {
          return HANDOFF('ambiguo', estado, {
            summary: 'No logra estimar su endeudamiento tras insistir. Handoff.',
          });
        }
        return {
          mensajes: [render(P.M2_NO_SABE, nombre)],
          etapaNueva: 'M2_NO_SABE', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'No sabe su endeudamiento. Se insiste suave con un estimado.',
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
        return HANDOFF('ambiguo', estado, {
          summary: 'Borderline sin datos para decidir (ni tipo de deuda ni sobrante). Humano, jamas descarte a ciegas.',
        });
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
      const dFinanciero = c.dolor_financiero
        || pareceDolorFinanciero(c.dolor_detalle)
        || pareceDolorFinanciero(textoLead);
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
        summary: 'Dolor D no financiero. Se reconduce.',
      };
    }

    // =====================================================================
    case 'M3_RECONDUCIR': {
      if (c.dolor_financiero || c.acepta || pareceDolorFinanciero(textoLead)) {
        return {
          mensajes: [render(P.M4_P1, nombre), render(P.M4_P2, nombre)],
          etapaNueva: 'M4_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'Reconduccion exitosa: el dolor si esta conectado con el dinero.',
        };
      }
      // No hay script del SOP para "no es fit por dolor". No se inventa copy:
      // decide un humano.
      return HANDOFF('ambiguo', estado, {
        summary: 'Dolor no financiero confirmado. Sin script del SOP para este cierre -> humano.',
      });
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
      if (!c.urgencia && (c.acepta || estado?.ultima_objecion_codigo === '9')
          && detectarAceptacion(textoLead)) {
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
      return HANDOFF('ambiguo', estado, { summary: 'No se pudo leer la urgencia con confianza.' });
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
      return HANDOFF('ambiguo', estado, { summary: 'Respuesta al pitch no clasificable.' });
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
      if (c.pide_link) {
        return {
          mensajes: [render(P.M6_CONFIRMAME, nombre), P.M6_LINK],
          etapaNueva: 'M6_ENVIADO', estadoDestino: null,
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false, // REGLA CRITICA DEL LINK
          summary: 'Pide el link otra vez. Se reenvia la plantilla aprobada, aislada.',
        };
      }
      if (c.sin_horarios) {
        return {
          mensajes: [render(P.SIN_HORARIOS, nombre)],
          etapaNueva: 'HANDOFF', estadoDestino: null,
          handoffRazon: 'agendamiento_manual_pendiente',
          motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'No encuentra horarios. Se le pide la franja y se escala para agendar a mano.',
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
        return {
          mensajes: [render(P.SIN_HORARIOS, nombre)],
          etapaNueva: 'HANDOFF', estadoDestino: null,
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
        return {
          mensajes: [render(P.SIN_HORARIOS, nombre)],
          etapaNueva: 'HANDOFF', estadoDestino: null,
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
    case 'CIERRE_PRECALL':
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
export function reencauzar(estado, c, nombre, contexto = '') {
  const etapaActual = estado?.etapa_bot || null;
  const pendientes = preguntaPendiente(etapaActual, nombre);

  if (!pendientes.length) {
    return HANDOFF('ambiguo', estado, {
      summary: `${contexto} Sin pregunta pendiente en ${etapaActual}: no hay a donde reencauzar.`,
    });
  }

  const generada = CATCHALL_LLM_HABILITADO && typeof c?.respuesta_empatica === 'string'
    ? c.respuesta_empatica.trim()
    : '';

  return {
    mensajes: generada ? [generada, ...pendientes] : pendientes,
    // No avanza el guion: reencauzar no es progresar.
    etapaNueva: etapaActual, estadoDestino: null,
    handoffRazon: null, motivoPerdida: null, campos: {},
    permitirEmpatia: false,
    // El Worker lo usa para eximir esta burbuja de la lista blanca y para
    // dejarlo anotado en el activity_log como texto generado.
    textoGenerado: generada || null,
    summary: generada
      ? `${contexto} Reencauce con respuesta generada + la pregunta pendiente.`
      : `${contexto} Reencauce determinista: se reenvia la pregunta pendiente.`,
  };
}

export function manejarObjecion(estado, c, nombre, contexto = '') {
  // "Si la objecion NO esta en la lista de 9 -> handoff objecion_fuera_playbook"
  if (!c.objecion_num || !OBJECIONES[c.objecion_num]) {
    return HANDOFF('objecion_fuera_playbook', estado, {
      summary: `${contexto} Objecion fuera del playbook.`,
    });
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

  // Precio insistido tiene razon propia: es mas util para el Setter que el
  // generico. Como la 7 ya no acumula, la señal es que la REPITA -- si volvio a
  // preguntar el precio despues de que se lo explicamos, la respuesta no le sirvio.
  if (num === '7' && repiteLaMisma) {
    return HANDOFF('pregunta_precio', estado, {
      campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
      summary: `${contexto} Vuelve a preguntar el precio del programa despues de la respuesta.`,
    });
  }

  // Repetir la MISMA objecion.
  //  - Si es resistencia: aplica el tope del fundador (aguanta N rondas).
  //  - Si es curiosidad: repetirla significa que nuestra respuesta no le sirvio,
  //    y ahi no hay tope que aguantar -- insistir con la misma plantilla que ya
  //    no funciono seria repetirse. Va a un humano.
  if (repiteLaMisma && (!esResistencia || consecutivas >= UMBRALES.RESISTENCIA_MISMA_OBJECION)) {
    return HANDOFF('resistencia_repetida', estado, {
      campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
      summary: esResistencia
        ? `${contexto} Repite la objecion ${num} (${consecutivas} veces).`
        : `${contexto} Vuelve a preguntar lo mismo (objecion ${num}): la respuesta del playbook no le sirvio.`,
    });
  }

  // Tope de resistencia acumulada. Ahora cuenta SOLO resistencia.
  if (consecutivas >= UMBRALES.RESISTENCIA_ACUMULADA) {
    return HANDOFF('resistencia_acumulada', estado, {
      campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
      summary: `${contexto} ${consecutivas} objeciones de resistencia consecutivas.`,
    });
  }

  // MATRIZ DE FASES (fundador, 4-sep-2026). Una objecion fuera de la fase donde
  // el Setter humano la ve de verdad casi siempre significa que el clasificador
  // leyo mal, no que el lead objete eso: "no tengo tiempo" en M1, cuando todavia
  // no se le ha propuesto ninguna llamada, no es la Objecion 2. Contestarle con
  // la plantilla seria responder a algo que nadie dijo. Se reencauza.
  //
  // ⚠️ VA DESPUES DE LAS REGLAS DE ESCALAMIENTO, y no es un detalle de orden:
  // puesta antes, un lead que insiste con una objecion fuera de fase se
  // reencauzaba indefinidamente y NUNCA llegaba a un humano. Lo encontro el test
  // "la resistencia repetida gana sobre la matriz".
  const etapaDelLead = estado?.etapa_bot || null;
  if (!objecionPermitidaEn(c.objecion_num, etapaDelLead)) {
    return reencauzar(estado, c, nombre,
      `${contexto} Objecion ${num} fuera de su fase (el lead esta en ${faseDeEtapa(etapaDelLead) || 'sin etapa'}).`);
  }

  // Perilla de alcance de la v1: el bot solo contesta las objeciones
  // habilitadas; el resto las ve un humano. Va DESPUES de las reglas de
  // escalamiento a proposito, para que el Setter reciba siempre la razon mas
  // informativa (resistencia repetida/acumulada gana sobre "no habilitada").
  if (!OBJECIONES_HABILITADAS.has(Number(c.objecion_num))) {
    return HANDOFF('objecion_no_habilitada', estado, {
      campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
      summary: `${contexto} Objecion ${num} reconocida pero no habilitada en esta version: la atiende un humano.`,
    });
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

  const mensajes = esObjecion6EnM1
    ? [render(plantilla, nombre), render(P.M1_PEDIR_RANGO, nombre)]
    : esPrePitch
      ? (traePreguntaPropia
        ? [render(plantilla, nombre)]
        : [render(plantilla, nombre), ...preguntaPendiente(etapaActual, nombre)])
      : partirEnBurbujas(render(plantilla, nombre));

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
    permitirEmpatia: !mensajes.some((m) => /https?:\/\//.test(m)),
    summary: esObjecion6EnM1
      ? `${contexto} Objecion 6 en ${etapaActual}: se le quita la presion de la profesion y la cifra exacta, y se le pregunta solo por el rango $7M-$15M.`
      : esPrePitch
        ? `${contexto} Objecion ${num} respondida SIN cierre de agenda (el lead aun se esta calificando) y se reenvia la pregunta pendiente.`
        : `${contexto} Se responde con la Objecion ${num}.`,
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

/** "solo" vs "acompañado" en la pregunta M7. */
export function detectarAcompanante(texto) {
  const t = String(texto || '').toLowerCase();
  // "voy solo" gana sobre cualquier mencion de persona: "voy solo, mi esposa
  // trabaja" es un NO, y si se evaluara primero el "esposa" se leeria al reves.
  if (/\b(sol[oa]|yo\s*sol[oa]|nadie\s*m[aá]s|solamente\s*yo|no,?\s*sol[oa]|voy\s*sol[oa])\b/.test(t)) return false;

  // La forma con "con..." era la unica que se detectaba, y el QA mostro que la
  // gente contesta nombrando a la persona sin preposicion: "va mi esposa",
  // "estaria mi socio", "mi pareja tambien".
  const PERSONA = '(esposa|esposo|pareja|novi[ao]|mam[aá]|pap[aá]|socia?|hermana?|hij[ao]|marido|mujer|familia|c[oó]nyuge)';
  if (new RegExp(`\\b(con\\s*(mi|alguien|un[ao])|${PERSONA}|acompañad|vamos\\s*(los\\s*)?dos|s[ií],?\\s*con)`).test(t)) return true;
  return null;
}

/** Urgencia: mecanico en la mayoria de casos. */
export function detectarUrgencia(texto) {
  const t = String(texto || '').toLowerCase();
  if (/\b(por\s*qu[eé]|porqu[eé])\b.*\b(ahora|ya|urgen|importante)\b/.test(t)
      || /\b(por\s*qu[eé]|porqu[eé])\s*(es\s*)?(tan\s*)?(importante|urgente)/.test(t)) {
    return 'pregunta_por_que';
  }
  if (/\b(ahora|ya|prioridad|urgente|lo\s*antes\s*posible|cuanto\s*antes|s[ií]\s*es\s*urgente|inmediato)\b/.test(t)) {
    return 'ahora';
  }
  if (/\b(m[aá]s\s*adelante|despu[eé]s|alg[uú]n\s*d[ií]a|cuando\s*tenga|no\s*es\s*urgente|el\s*otro\s*a[ñn]o|luego)\b/.test(t)) {
    return 'algun_dia';
  }
  return null;
}

/**
 * Dolor A/B/C/D.
 *
 * Ampliado con lenguaje real del corpus: en las conversaciones modelo el lead
 * no responde "B" a secas, responde "B sin duda. Siento que me llega la plata
 * y a los 15 dias ya no se en que se fue". La version anterior solo reconocia
 * la letra aislada y mandaba ese turno al LLM sin necesidad.
 *
 * OJO con la "a": en español es preposicion ("a mi me pasa que..."), asi que
 * solo se acepta aislada o seguida de puntuacion. La b/c/d no son palabras, asi
 * que ahi si se acepta la letra al inicio seguida de texto.
 */
export function detectarDolorLetras(texto) {
  const t = String(texto || '').trim().toLowerCase();
  if (!t) return [];

  // Se trabaja por tokens: "la B y la C" tiene palabras entre las letras, asi
  // que una regex de "letra separador letra" se pierde la segunda.
  const tokens = t.replace(/[()]/g, ' ').split(/[\s,.;:/+&]+/).filter(Boolean);
  const letras = new Set();

  // "todas" / "todas las anteriores" / "me pasan todas" (fundador, 4-sep-2026).
  // Cuenta como A+B+C+D. La consecuencia importante es que arrastra A, B y C,
  // asi que el lead califica emocionalmente y el detalle de la D se ignora --
  // que es exactamente la excepcion que pidio el fundador: a quien le pasan
  // todas no hay que preguntarle "¿cual es esa otra?".
  if (/\btodas?\b|\btodo\s+lo\s+anterior\b|\blas\s+cuatro\b/.test(t)) {
    for (const c of ['a', 'b', 'c', 'd']) letras.add(c);
  }

  // Letras pegadas: "AB", "BCD". ManyChat ya dispara con esas combinaciones.
  for (const tok of tokens) {
    if (/^[abcd]{2,4}$/.test(tok)) for (const c of tok) letras.add(c);
  }

  // b/c/d aisladas cuentan siempre: no son palabras en español.
  for (const tok of tokens) if (/^[bcd]$/.test(tok)) letras.add(tok);

  // La "a" es preposicion ("a mi me pasa que..."), asi que solo cuenta si es
  // el mensaje entero o si ya hay otra letra de respuesta ("a y b").
  const hayA = tokens.includes('a');
  if (hayA && (tokens.length === 1 || letras.size > 0)) letras.add('a');

  if (letras.size === 0) {
    const una = detectarDolorLetra(texto);
    if (una) letras.add(una.toLowerCase());
  }
  return [...letras].map((x) => x.toUpperCase()).sort();
}

/**
 * ¿El texto libre de la opcion D habla de dinero?
 *
 * QA en vivo (4-sep-2026): la lead escribio "D, me siento preocupada por la
 * cantidad de deudas que tengo" y el LLM devolvio `dolor_financiero: false`, asi
 * que el bot la saco por M3_RECONDUCIR -- le dijo "puede que no seamos el mejor
 * fit" a alguien cuyo dolor es LITERALMENTE deudas.
 *
 * Se arreglo en los dos lados. El prompt ahora lo dice explicito, pero eso solo
 * no basta: el LLM ya habia fallado con un caso obvio. Este detector es la red
 * determinista, y GANA sobre el LLM -- si el texto menciona dinero, es dolor
 * financiero y no hay nada que interpretar.
 */
export function pareceDolorFinanciero(texto) {
  const t = String(texto || '').toLowerCase();
  if (!t.trim()) return false;
  return RAICES_DE_DINERO.test(t);
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
  if (/\b(no|pero|aunque)\b/.test(t.slice(0, 20))) return false;

  const AFIRMA = /\b(dale|listo|s[ií]|dele|dal[eé]|dalee|dsl|dsp|de\s*una|dale\s*pues|agendemos|agendamos|me\s*sirve|dale\s*ah[ií]|perfecto|obvio|por\s*supuesto|hag[aá]moslo|vamos)\b/;
  if (AFIRMA.test(t)) return true;

  // "claro" suelto SI es aceptacion ("claro", "claro que si"); pegado a un verbo
  // de entender, NO ("quiero tener mas claro", "para dejarlo claro").
  return /\bclaro\b/.test(t) && !/\b(m[aá]s|tener|dejar|ver|saber|entender|quede|queda)\s+(lo\s+)?claro/.test(t);
}

/**
 * ¿La cifra que dio el lead suena a "lo que me queda" y no a su ingreso total?
 *
 * Aprendizaje de produccion del equipo de Javier (SOP-05 #2): descalificar a
 * alguien que dijo "me quedan $5M" sin aclarar es perder un lead que puede
 * estar ganando $12M brutos. Solo dispara la aclaracion cuando el texto trae
 * una marca explicita de remanente -- no en cualquier ingreso bajo, para no
 * agregarle friccion al lead que de verdad no califica.
 */
export function pareceRemanente(texto) {
  const t = String(texto || '').toLowerCase();
  return /\b(me\s*qued|queda[nr]?\b|me\s*sobra|sobran|libre[s]?\b|despu[eé]s\s*de\s*(gastos|pagar)|neto|limpio|disponible|para\s*gastar|menos\s*de)\b/.test(t);
}

/** Agradecimiento tras el cierre -> dispara el blindaje del show-up. */
export function detectarAgradecimiento(texto) {
  const t = String(texto || '').toLowerCase();
  return /\b(gracias|grac|mil\s*gracias|te\s*agradezco|muy\s*amable|excelente|perfecto|listo)\b/.test(t)
      || /^\s*(🙏|👍|🙌|💪|😊)+\s*$/u.test(String(texto || '').trim());
}

/** Respuesta a la pregunta de blindaje: 'firme' | 'dudoso' | null. */
export function detectarCompromiso(texto) {
  const t = String(texto || '').toLowerCase();
  if (/\b(puede\s*(que|pasar)|tal\s*vez|quiz[aá]s?|no\s*estoy\s*segur|depende|capaz|probablemente\s*no|creo\s*que\s*no|no\s*podr[ií]a)\b/.test(t)) {
    return 'dudoso';
  }
  if (/\b(firme|firmes|s[ií]\s*firme|segur[oa]|100|ah[ií]\s*estar[eé]|claro\s*que\s*s[ií]|por\s*supuesto|confirmad|ah[ií]\s*nos\s*vemos|nada\s*(me\s*)?lo\s*impide|todo\s*bien)\b/.test(t)) {
    return 'firme';
  }
  return null;
}

/**
 * El lead dice que no encuentra horarios disponibles.
 *
 * SOP-05 #5 del proyecto de Javier: "NO confirmes que si hay espacio" --
 * hay que escalar para agendar a mano. Es senal de calendario sin cupos, un
 * dato que al Setter le sirve tanto como el lead mismo.
 */
export function detectarSinHorarios(texto) {
  const t = String(texto || '').toLowerCase();
  return /\b(no\s*(me\s*)?(aparece|hay|encuentro|veo|sale|deja|carga|figura)|sin\s*(cupos?|espacios?|horarios?)|no\s*(hay|tengo|queda)\s*(espacio|cupo|horario|nada)|no\s*me\s*(cuadra|cuadran|sirve|sirven|queda|quedan)|est[aá]\s*(lleno|bloqueado)|no\s*me\s*deja\s*agendar|no\s*pude\s*agendar)\b/.test(t);
}

/** Hostilidad -- red deterministas basica, el LLM afina. */
export function detectarHostilidad(texto) {
  const t = String(texto || '').toLowerCase();
  return /\b(hp\b|hijueputa|gonorrea|estafa|estafador|ladr[oó]n|rat[aeo]s?\b|malparid|est[uú]pid|imb[eé]cil|idiota|vete\s*a|no\s*jodas|d[eé]jame\s*en\s*paz|no\s*me\s*escrib)/.test(t);
}

/** Porcentaje de endeudamiento escrito directo ("35%", "el 35"). */
export function detectarEndeudamientoPct(texto) {
  const t = String(texto || '').toLowerCase();
  const conPct = t.match(/(\d{1,3}(?:[.,]\d+)?)\s*%/);
  if (conPct) {
    const n = parseFloat(conPct[1].replace(',', '.'));
    if (n >= 0 && n <= 100) return n;
  }
  if (/\b(no\s*s[eé]|ni\s*idea|no\s*estoy\s*segur|no\s*tengo\s*idea|no\s*lo\s*s[eé])\b/.test(t)) return null;

  // El lead contesto con PLATA, no con un porcentaje ("pago 2 millones al mes",
  // "me quedan 500 mil"). Sin este freno, el fallback de "numero suelto" de
  // abajo agarra el 2 y lo reporta como 2% -- y 2% es un endeudamiento
  // EXCELENTE, asi que el lead pasaba el Filtro 2 con un dato inventado. No es
  // que escalara a un humano: es peor, calificaba en silencio.
  //
  // Cuando hay marca de plata se devuelve null a proposito: el LLM extrae
  // `deuda_cop`/`remanente_cop` y el router los convierte a % contra el
  // ingreso ya conocido (caso M2_ENVIADO). Aqui adivinar es peor que abstenerse.
  if (MARCA_DE_PLATA.test(t)) return null;

  const suelto = t.match(/(?:^|\s)(\d{1,3}(?:[.,]\d+)?)(?:\s|$)/);
  if (suelto) {
    const n = parseFloat(suelto[1].replace(',', '.'));
    if (n >= 0 && n <= 100) return n;
  }
  return null;
}

/**
 * Vocabulario de plata colombiano, el mismo que entiende `parseIngresoCOP`.
 * Se mantiene junto al detector de porcentaje porque su unico trabajo es
 * distinguir "30" (porcentaje) de "30 millones" (monto).
 */
const MARCA_DE_PLATA =
  /(\bmillones?\b|\bmill[oó]n\b|\bmill\b|\bpalos?\b|\blucas?\b|\bmil\b|\bk\b|\bcop\b|\bpesos?\b|\bsmlv\b|\bsmmlv\b|salarios?\s*m[ií]nimos?|\$|\bd[oó]lares?\b|\busd\b|\beuros?\b|\bmensuales?\b\s*en\s*deuda)/;
