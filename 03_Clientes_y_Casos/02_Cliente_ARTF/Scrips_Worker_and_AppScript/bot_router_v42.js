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

import { PLANTILLAS as P, OBJECIONES, UMBRALES, render } from './sop_v42_plantillas.js';

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
export function topeEndeudamiento(ingreso) {
  return (ingreso ?? 0) > UMBRALES.INGRESO_TOPE_ALTO
    ? UMBRALES.ENDEUDAMIENTO_TOPE_ALTO
    : UMBRALES.ENDEUDAMIENTO_TOPE_BASE;
}

/** 'ok' | 'borderline' (hasta ~10 puntos sobre el tope) | 'descalifica' */
export function evaluarEndeudamiento(pct, ingreso) {
  if (pct === null || pct === undefined) return 'no_sabe';
  const tope = topeEndeudamiento(ingreso);
  if (pct <= tope) return 'ok';
  if (pct <= tope + UMBRALES.ENDEUDAMIENTO_MARGEN_BORDERLINE) return 'borderline';
  return 'descalifica';
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
    return { responder: false, razon: 'handoff_activo' };
  }
  if (estado.etapa_bot === 'CIERRE_PRECALL') {
    return { responder: false, razon: 'cierre_ya_entregado' };
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

  // --- Lead descalificado que vuelve: unica ruta viva es RetornoLead ---
  if (estado?.estado_codigo === 'descalificado') {
    const ing = c.ingreso_cop ?? null;
    if (ing !== null && evaluarIngreso(ing) === 'califica') {
      return {
        mensajes: [render(P.RETORNO_LEAD, nombre), render(P.M2, nombre)],
        etapaNueva: 'M2_ENVIADO',
        estadoDestino: 'contactado',
        handoffRazon: null,
        motivoPerdida: null,
        campos: { salario_monto: ing, ingreso_confirmado: true, califica: null },
        permitirEmpatia: false,
        summary: `RetornoLead: se recalifica con ingreso ${ing}. Se retoma en M2.`,
      };
    }
    return {
      mensajes: [], etapaNueva: null, estadoDestino: null, handoffRazon: null,
      motivoPerdida: null, campos: {}, permitirEmpatia: false,
      summary: 'Mensaje de lead descalificado sin recalificacion. Solo se registra.',
    };
  }

  switch (etapa) {
    // =====================================================================
    case 'M1_ENVIADO':
    case 'M1_INGRESO_AMBIGUO': {
      const ing = c.ingreso_cop ?? null;
      const veredicto = evaluarIngreso(ing);

      if (veredicto === 'ambiguo') {
        // Regla de oro V4.1: NUNCA descalificar sobre un ingreso ambiguo.
        if (etapa === 'M1_INGRESO_AMBIGUO') {
          // Ya se pidio la cifra una vez y sigue sin darla -> humano, jamas descarte.
          return HANDOFF('ambiguo', estado, {
            campos: { profesion: c.profesion ?? null },
            summary: 'Ingreso sigue ambiguo tras pedir la cifra. Handoff en vez de descartar (regla V4.1).',
          });
        }
        const plantilla = c.profesion ? P.M1_PEDIR_CIFRA : P.M1_PEDIR_RANGO;
        return {
          mensajes: [render(plantilla, nombre)],
          etapaNueva: 'M1_INGRESO_AMBIGUO',
          estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { profesion: c.profesion ?? null, ingreso_confirmado: false },
          permitirEmpatia: false,
          summary: `Ingreso ambiguo (${c.ingreso_glosario || 'sin cifra'}). Se pide la cifra exacta.`,
        };
      }

      if (veredicto === 'descalifica') {
        return {
          mensajes: [render(P.DESC_INGRESO, nombre)],
          etapaNueva: 'DESCALIFICADO',
          estadoDestino: 'descalificado',
          handoffRazon: null,
          motivoPerdida: 'Descalificado - Ingreso bajo (< $7M)',
          campos: { profesion: c.profesion ?? null, salario_monto: ing, ingreso_confirmado: true, califica: false },
          permitirEmpatia: false,
          summary: `Filtro 1 no superado: ingreso ${ing} < $7M. Descalificacion con valor.`,
        };
      }

      return {
        mensajes: [render(P.M2, nombre)],
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
      const pct = c.endeudamiento_pct ?? null;
      const veredicto = evaluarEndeudamiento(pct, ingreso);

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
          mensajes: [render(P.M2_BORDERLINE, nombre)],
          etapaNueva: 'M2_BORDERLINE', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { endeudamiento_pct: pct },
          permitirEmpatia: false,
          summary: `Endeudamiento ${pct}% apenas sobre el tope (${topeEndeudamiento(ingreso)}%). Se pregunta el tipo de deuda.`,
        };
      }
      if (veredicto === 'descalifica') {
        return {
          mensajes: [render(P.DESC_ENDEUDAMIENTO, nombre)],
          etapaNueva: 'DESCALIFICADO', estadoDestino: 'descalificado',
          handoffRazon: null,
          motivoPerdida: 'Descalificado - Endeudamiento sobre su tope',
          campos: { endeudamiento_pct: pct, califica: false },
          permitirEmpatia: false,
          summary: `Filtro 2 no superado: ${pct}% > tope ${topeEndeudamiento(ingreso)}%.`,
        };
      }
      return {
        mensajes: [render(P.M3, nombre)],
        etapaNueva: 'M3_ENVIADO', estadoDestino: 'contactado',
        handoffRazon: null, motivoPerdida: null,
        campos: { endeudamiento_pct: pct },
        permitirEmpatia: true,
        summary: `Filtro 2 superado: ${pct}% <= tope ${topeEndeudamiento(ingreso)}%. Se pregunta el dolor.`,
      };
    }

    // =====================================================================
    case 'M2_BORDERLINE': {
      const ingreso = estado?.salario_monto ?? null;
      if (c.deuda_mayoritariamente_buena) {
        return {
          mensajes: [render(P.M3, nombre)],
          etapaNueva: 'M3_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: true,
          summary: 'Borderline resuelto a favor: la mayoria es deuda buena (vivienda).',
        };
      }
      return {
        mensajes: [render(P.DESC_ENDEUDAMIENTO, nombre)],
        etapaNueva: 'DESCALIFICADO', estadoDestino: 'descalificado',
        handoffRazon: null,
        motivoPerdida: 'Descalificado - Endeudamiento sobre su tope',
        campos: { califica: false },
        permitirEmpatia: false,
        summary: `Borderline resuelto en contra (tope ${topeEndeudamiento(ingreso)}%): deuda de consumo/tarjetas.`,
      };
    }

    // =====================================================================
    case 'M3_ENVIADO': {
      const dolor = (c.dolor || '').toUpperCase();
      const esAvatar = ['A', 'B', 'C'].includes(dolor);
      if (esAvatar || (dolor === 'D' && c.dolor_financiero)) {
        return {
          mensajes: [render(P.M4, nombre)],
          etapaNueva: 'M4_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { dolor: dolor || null },
          // M4 ya arranca con "Te entiendo perfectamente" -> no se le antepone empatia.
          permitirEmpatia: false,
          summary: `Dolor ${dolor} (califica emocionalmente). Se pregunta urgencia.`,
        };
      }
      return {
        mensajes: [render(P.M3_RECONDUCIR, nombre)],
        etapaNueva: 'M3_RECONDUCIR', estadoDestino: 'contactado',
        handoffRazon: null, motivoPerdida: null,
        campos: { dolor: dolor || null },
        permitirEmpatia: false,
        summary: 'Dolor D no financiero. Se reconduce.',
      };
    }

    // =====================================================================
    case 'M3_RECONDUCIR': {
      if (c.dolor_financiero || c.acepta) {
        return {
          mensajes: [render(P.M4, nombre)],
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
    case 'M4_ENVIADO': {
      if (c.urgencia === 'pregunta_por_que') {
        return manejarObjecion(estado, { ...c, objecion_num: 9, objecion_conocida: true }, nombre,
          'Objecion 9 (por que ahora) en el filtro de urgencia.');
      }
      if (c.urgencia === 'algun_dia') {
        return {
          mensajes: [render(P.DESC_URGENCIA, nombre)],
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
          mensajes: [render(P.M5, nombre)],
          etapaNueva: 'M5_ENVIADO', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { urgencia_raw: 'ahora', califica: true },
          permitirEmpatia: false, // el pitch entra directo, sin preambulo
          summary: 'Filtro 3 superado. Lead CALIFICADO (3/3 filtros). Se envia el pitch.',
        };
      }
      return HANDOFF('ambiguo', estado, { summary: 'No se pudo leer la urgencia con confianza.' });
    }

    // =====================================================================
    case 'M5_ENVIADO': {
      if (c.acepta) {
        // M6 (link) + M7 (asistencia) en el mismo turno, en burbujas separadas:
        // asi lo ordena el flujo V4.2 y M7 dice "antes de que separes tu
        // espacio". El link queda aislado en su propia burbuja -- nada de texto
        // pegado despues en la MISMA burbuja (Instagram lo rompe).
        return {
          mensajes: [
            render(P.M6_LINK, nombre),
            render(P.M6_CONFIRMAME, nombre),
            render(P.M7, nombre),
          ],
          etapaNueva: 'M7_ENVIADO',
          estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { calendario_enviado: true },
          permitirEmpatia: false, // REGLA CRITICA DEL LINK
          summary: 'Acepta agendar. Se envia link (M6) + pregunta de asistencia (M7).',
        };
      }
      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion tras el pitch.');
      }
      return HANDOFF('ambiguo', estado, { summary: 'Respuesta al pitch no clasificable.' });
    }

    // =====================================================================
    case 'M6_ENVIADO': // por compatibilidad si algun turno quedo en M6
    case 'M7_ENVIADO': {
      if (c.confirmo_agendo) {
        return {
          mensajes: [render(P.CIERRE_PRECALL, nombre)],
          etapaNueva: 'CIERRE_PRECALL', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'El lead dice que agendo. Se envian las preguntas pre-llamada. OJO: el estado "agendado" lo confirma la sync de Google Calendar, no esto.',
        };
      }
      if (c.acompanado === true) {
        return {
          mensajes: [render(P.M7_ACOMPANADO, nombre)],
          etapaNueva: 'M7_ENVIADO', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { asiste_acompanado: true },
          permitirEmpatia: false,
          summary: 'Asistira acompañado. Se le pide cuadrar con esa persona.',
        };
      }
      if (c.acompanado === false) {
        return {
          mensajes: [render(P.M7_SOLO_ACK, nombre)],
          etapaNueva: 'M7_ENVIADO', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { asiste_acompanado: false },
          permitirEmpatia: false,
          summary: 'Asistira solo. Se espera a que agende (acuse operativo, no del SOP).',
        };
      }
      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion despues de enviar el link.');
      }
      return {
        mensajes: [], etapaNueva: null, estadoDestino: null,
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: 'Mensaje tras el link sin señal clara. Solo se registra, se espera el agendamiento.',
      };
    }

    // =====================================================================
    case 'CIERRE_PRECALL':
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

// ---------------------------------------------------------------------------
// 5. Objeciones + reglas de escalamiento
// ---------------------------------------------------------------------------
export function manejarObjecion(estado, c, nombre, contexto = '') {
  // "Si la objecion NO esta en la lista de 9 -> handoff objecion_fuera_playbook"
  if (!c.objecion_num || !OBJECIONES[c.objecion_num]) {
    return HANDOFF('objecion_fuera_playbook', estado, {
      summary: `${contexto} Objecion fuera del playbook.`,
    });
  }

  const num = String(c.objecion_num);
  const anterior = estado?.ultima_objecion_codigo || null;
  const consecutivas = (estado?.objeciones_consecutivas || 0) + 1;

  // Precio insistido 2 veces tiene razon propia (mas util para el Setter que
  // el generico "resistencia_repetida").
  if (num === '7' && anterior === '7') {
    return HANDOFF('pregunta_precio', estado, {
      campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
      summary: `${contexto} Insiste en el precio del programa por 2a vez.`,
    });
  }
  // "Si el lead pone la MISMA objecion 2 veces -> resistencia_repetida"
  if (anterior && anterior === num) {
    return HANDOFF('resistencia_repetida', estado, {
      campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
      summary: `${contexto} Repite la objecion ${num}.`,
    });
  }
  // "Si acumula 3+ objeciones consecutivas -> resistencia_acumulada"
  if (consecutivas >= 3) {
    return HANDOFF('resistencia_acumulada', estado, {
      campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
      summary: `${contexto} ${consecutivas} objeciones consecutivas.`,
    });
  }

  return {
    mensajes: [render(OBJECIONES[c.objecion_num], nombre)],
    // Se queda en la misma etapa: tras manejar la objecion se vuelve a pedir
    // el agendamiento, no se avanza el guion.
    etapaNueva: estado?.etapa_bot || null,
    estadoDestino: null,
    handoffRazon: null, motivoPerdida: null,
    campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
    permitirEmpatia: false,
    summary: `${contexto} Se responde con la Objecion ${num}.`,
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
  return /\b(ya\s*(me\s*)?(agend|reserv|separ)|list[oa]\s*(ya)?\s*(agend|qued)|qued[eé]\s*(agendad|separad)|agend[eé]|reserv[eé]|ya\s*qued[eé])/.test(t);
}

/** "solo" vs "acompañado" en la pregunta M7. */
export function detectarAcompanante(texto) {
  const t = String(texto || '').toLowerCase();
  if (/\b(con\s*(mi|alguien|mi\s*(esposa|esposo|pareja|novi[ao]|mam|pap))|acompañad|vamos\s*(los\s*)?dos|s[ií],?\s*con)/.test(t)) return true;
  if (/\b(sol[oa]|yo\s*sol[oa]|nadie\s*m[aá]s|solamente\s*yo|no,?\s*sol[oa]|voy\s*sol[oa])\b/.test(t)) return false;
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

/** Dolor A/B/C/D cuando responde con la letra sola. */
export function detectarDolorLetra(texto) {
  const t = String(texto || '').trim().toLowerCase();
  const m = t.match(/^\(?([abcd])\)?[\s.,)]*$/);
  return m ? m[1].toUpperCase() : null;
}

/** Aceptacion del pitch ("dale", "si", "agendemos"). */
export function detectarAceptacion(texto) {
  const t = String(texto || '').toLowerCase();
  return /\b(dale|listo|s[ií]|claro|dele|dal[eé]|dalee|dalé|dsl|dsp|dele|de\s*una|dale\s*pues|agendemos|agendamos|me\s*sirve|dale\s*ah[ií]|perfecto|obvio|por\s*supuesto|hag[aá]moslo|vamos)\b/.test(t)
      && !/\b(no|pero|aunque)\b/.test(t.slice(0, 12));
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
  const suelto = t.match(/(?:^|\s)(\d{1,3}(?:[.,]\d+)?)(?:\s|$)/);
  if (suelto) {
    const n = parseFloat(suelto[1].replace(',', '.'));
    if (n >= 0 && n <= 100) return n;
  }
  return null;
}
