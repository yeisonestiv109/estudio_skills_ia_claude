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
  ETAPAS_PRE_PITCH, UMBRALES, render, partirEnBurbujas,
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
    M1_RANGO_PREGUNTADO: [P.M1_PEDIR_RANGO],
    M1_ACLARAR_REMANENTE: [P.M1_ACLARAR_REMANENTE],
    M2_ENVIADO: [P.M2_P1, P.M2_P2],
    M2_BORDERLINE: [P.M2_BORDERLINE],
    M2_NO_SABE: [P.M2_NO_SABE],
    M3_ENVIADO: [P.M3],
    M3_RECONDUCIR: [P.M3_RECONDUCIR],
    // De M4 y M5 se reenvia solo el remate, no la narrativa completa: el lead
    // ya la leyo, lo que necesita es volver a ver la pregunta.
    M4_ENVIADO: [P.M4_P2],
    M5_ENVIADO: [P.M5_P2],
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
          motivoPerdida: 'Descalificado - Ingreso bajo (< $7M)',
          campos: { salario_monto: ingRango, ingreso_confirmado: true, califica: false },
          permitirEmpatia: false,
          summary: `Filtro 1 no superado: dio ${ingRango} al preguntar el rango.`,
        };
      }
      if (c.confirma_rango === true) {
        // Confirma estar en el rango: se registra el PISO del rango que acepto
        // ($7M), que es lo minimo verificado. No se inventa una cifra mayor.
        return {
          mensajes: [render(P.M2_P1, nombre), render(P.M2_P2, nombre)],
          etapaNueva: 'M2_ENVIADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { salario_monto: UMBRALES.INGRESO_MINIMO, ingreso_confirmado: true },
          permitirEmpatia: false,
          summary: `Confirma estar en el rango $7M-$15M. Filtro 1 superado; se registra el piso (${UMBRALES.INGRESO_MINIMO}) como minimo verificado.`,
        };
      }
      if (c.confirma_rango === false) {
        return {
          mensajes: partirEnBurbujas(render(P.DESC_INGRESO, nombre)),
          etapaNueva: 'DESCALIFICADO', estadoDestino: 'descalificado',
          handoffRazon: null,
          motivoPerdida: 'Descalificado - Ingreso bajo (< $7M)',
          campos: { ingreso_confirmado: true, califica: false },
          permitirEmpatia: false,
          summary: 'Dice que NO esta en el rango $7M-$15M. Filtro 1 no superado.',
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
        const terminoAmbiguo = ['salario_integral', 'ingreso_variable', 'numero_sin_unidad']
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
        return {
          mensajes: [render(P.M1_PEDIR_RANGO, nombre)],
          etapaNueva: 'M1_RANGO_PREGUNTADO', estadoDestino: 'contactado',
          handoffRazon: null, motivoPerdida: null,
          campos: { profesion: c.profesion ?? null, ingreso_confirmado: false },
          permitirEmpatia: false,
          summary: 'No dio ninguna cifra. Se pregunta si esta en el rango $7M-$15M.',
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
          motivoPerdida: 'Descalificado - Ingreso bajo (< $7M)',
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
      const pct = c.endeudamiento_pct ?? null;
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
          mensajes: partirEnBurbujas(render(P.DESC_ENDEUDAMIENTO, nombre)),
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
        mensajes: partirEnBurbujas(render(P.DESC_ENDEUDAMIENTO, nombre)),
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
      const esAvatar = letras.some((l) => ['A', 'B', 'C'].includes(l));
      if (esAvatar || (letras.includes('D') && c.dolor_financiero)) {
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
      return HANDOFF('ambiguo', estado, { summary: 'No se pudo leer la urgencia con confianza.' });
    }

    // =====================================================================
    case 'M5_ENVIADO': {
      if (c.acepta) {
        // ⚠️ EXACTAMENTE 2 burbujas, y el LINK ES LA ULTIMA. Nada despues.
        // Bug confirmado en produccion por el equipo de Javier: si va texto
        // despues del link en el mismo turno, Instagram los concatena y deja
        // el link invalido ("Dynamic Link Not Found") -- se rompe el
        // agendamiento, que es lo unico que este bot existe para lograr.
        // El "Confirmame..." y M7 (asistencia) se envian en el TURNO SIGUIENTE.
        return {
          mensajes: [
            render(P.M7, nombre),          // "antes de que separes tu espacio..."
            render(P.M6_SALUDO, nombre),
            render(P.M6_CONFIRMAME, nombre),
            P.M6_LINK,                     // SIEMPRE la ultima, y sola
          ],
          etapaNueva: 'M7_ENVIADO',
          estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null,
          campos: { calendario_enviado: true },
          permitirEmpatia: false, // REGLA CRITICA DEL LINK
          summary: 'Acepta agendar. Se envian asistencia (M7) + link aislado al final.',
        };
      }
      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion tras el pitch.');
      }
      return HANDOFF('ambiguo', estado, { summary: 'Respuesta al pitch no clasificable.' });
    }

    // =====================================================================
    // Turno siguiente al link: aca SI se puede mandar texto, porque el link
    // ya salio solo en su propio turno.
    case 'M6_ENVIADO': {
      if (c.confirmo_agendo) {
        return {
          mensajes: [render(P.CIERRE_PRECALL, nombre)],
          etapaNueva: 'CIERRE_PRECALL', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'Confirma agendamiento apenas recibe el link. Se envian las preguntas pre-llamada. OJO: "agendado" lo confirma la sync de Calendar, no esto.',
        };
      }
      if (c.objecion_num || c.objecion_detectada) {
        return manejarObjecion(estado, c, nombre, 'Objecion despues de enviar el link.');
      }
      return {
        mensajes: [render(P.M7, nombre), render(P.M6_CONFIRMAME, nombre)],
        etapaNueva: 'M7_ENVIADO', estadoDestino: 'calificado',
        handoffRazon: null, motivoPerdida: null, campos: {},
        permitirEmpatia: false,
        summary: 'Se envia la pregunta de asistencia (M7) + el CTA de confirmacion, ya sin link en el turno.',
      };
    }

    // =====================================================================
    case 'M7_ENVIADO': {
      // El lead dice que no encuentra horarios: se le pregunta la franja Y se
      // escala al Setter en el mismo turno (SOP-05 #5 del proyecto de Javier).
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
        // El bot NO decide si agendo: lo decide la base. El Setter es quien
        // vincula la reunion desde el dashboard.
        if (estado?.tiene_reunion) {
          return {
            mensajes: [render(P.CIERRE_PRECALL, nombre)],
            etapaNueva: 'CIERRE_PRECALL', estadoDestino: 'calificado',
            handoffRazon: null, motivoPerdida: null, campos: {},
            permitirEmpatia: false,
            summary: 'Confirma agendamiento Y la reunion ya esta vinculada. Se envian las preguntas pre-llamada.',
          };
        }
        // Dice que agendo pero la base todavia no lo respalda: acuse UNA vez y
        // a esperar en silencio. Sin este cambio de etapa, cada "listo",
        // "gracias" o "ya quedo" recibia el mismo "¡Perfecto! 🙌" otra vez, y
        // repetir la misma linea tres veces seguidas se ve robotico justo en el
        // momento mas delicado de la conversacion.
        return {
          mensajes: [render(P.ACUSE_SIN_REUNION, nombre)],
          etapaNueva: 'M7_ESPERANDO_VINCULO', estadoDestino: 'calificado',
          handoffRazon: null, motivoPerdida: null, campos: {},
          permitirEmpatia: false,
          summary: 'Dice que agendo pero NO hay reunion vinculada. Acuse corto; no se confirma nada que la base no respalde.',
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
          summary: 'Asistira solo. Se espera a que agende.',
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
  const esPrePitch = ETAPAS_PRE_PITCH.has(etapaActual) && Number(c.objecion_num) !== 9;

  const plantilla = esPrePitch
    ? (OBJECIONES_PRE_PITCH[num] || OBJECIONES[c.objecion_num])
    : OBJECIONES[c.objecion_num];

  const mensajes = esPrePitch
    ? [render(plantilla, nombre), ...preguntaPendiente(etapaActual, nombre)]
    : partirEnBurbujas(render(plantilla, nombre));

  return {
    mensajes,
    // Se queda en la misma etapa: tras manejar la objecion se retoma donde
    // estaba, no se avanza el guion.
    etapaNueva: etapaActual,
    estadoDestino: null,
    handoffRazon: null, motivoPerdida: null,
    campos: { ultima_objecion_codigo: num, objeciones_consecutivas: consecutivas },
    permitirEmpatia: false,
    summary: esPrePitch
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
  return /\b(dale|listo|s[ií]|claro|dele|dal[eé]|dalee|dalé|dsl|dsp|dele|de\s*una|dale\s*pues|agendemos|agendamos|me\s*sirve|dale\s*ah[ií]|perfecto|obvio|por\s*supuesto|hag[aá]moslo|vamos)\b/.test(t)
      && !/\b(no|pero|aunque)\b/.test(t.slice(0, 12));
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
  const suelto = t.match(/(?:^|\s)(\d{1,3}(?:[.,]\d+)?)(?:\s|$)/);
  if (suelto) {
    const n = parseFloat(suelto[1].replace(',', '.'));
    if (n >= 0 && n <= 100) return n;
  }
  return null;
}
