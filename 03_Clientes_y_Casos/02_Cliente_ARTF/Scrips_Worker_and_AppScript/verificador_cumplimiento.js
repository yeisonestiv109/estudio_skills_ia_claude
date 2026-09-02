/**
 * VERIFICADOR DE CUMPLIMIENTO — la compuerta del loop de desarrollo
 * ============================================================================
 * Loop engineering: este archivo es el `prepare.py` de este proyecto.
 *
 * Recibe los mensajes que el bot ESTA A PUNTO de enviarle al lead y decide
 * PASA / FALLA. Es determinista: cero LLM, cero criterio propio. Solo compara
 * contra reglas que salen de fuentes que NO escribio quien genera el codigo:
 *
 *   - El PDF del SOP Setter DM V4.2 (documento del cliente).
 *   - El proyecto original del Setter IA de Javier
 *     (Setter-IA-Claude-Code-Project), en particular
 *     `knowledge-base/04-voz-y-tono.md`, que declara sus dos reglas como
 *     "no negociables" porque SE ROMPIERON EN PRODUCCION y costaron leads.
 *   - La biblioteca de plantillas, que es copy aprobado por el cliente.
 *
 * POR QUE IMPORTA QUE SEA ASI: quien genera el codigo tambien escribe los
 * tests, y eso permite "hacer trampa al examen" debilitando el test hasta que
 * pase. Estas reglas no se pueden debilitar sin contradecir un documento del
 * cliente, que es justamente el terreno externo del loop.
 *
 * La regla R1 (link aislado) es la que habria atrapado sola el bug mas grave
 * que hemos tenido: mandabamos el link y dos mensajes mas en el mismo turno,
 * lo que en Instagram deja el link invalido ("Dynamic Link Not Found") y rompe
 * el agendamiento. No lo atraparon 52 tests ni el type-check.
 */

import { PLANTILLAS as P, OBJECIONES, CALENDAR_LINK, REELS, partirEnBurbujas } from './sop_v42_plantillas.js';

// ---------------------------------------------------------------------------
// Reglas de voz -- literales de knowledge-base/04-voz-y-tono.md (proyecto de Javier)
// ---------------------------------------------------------------------------

/**
 * Regla #2 "no negociable": tuteo colombiano estricto. Roto en produccion el
 * 21-may-2026 (M3 a Daniel Meza, M4 a Dario Montenegro).
 *
 * OJO con la tilde -- es lo unico que separa el tuteo del voseo en varias
 * formas, y confundirlo genera falsos positivos que vuelven inutil la
 * compuerta:
 *   "sabes"  = tuteo OK      vs  "sabés" = voseo
 *   "haces"  = tuteo OK      vs  "hacés" = voseo
 *   "andas"  = tuteo OK      vs  "andás" = voseo
 * En cambio "tenes/podes/queres/sentis/decis/venis" no son tuteo en ninguna
 * variante (el tuteo es tienes/puedes/quieres/sientes/dices/vienes), asi que
 * ahi se marcan con o sin tilde.
 */
const VOSEO = new RegExp(
  '\\b(' + [
    'vos', 'sos',                       // pronombre y verbo ser
    'sab[é]s', 'hac[é]s', 'and[á]s',    // solo con tilde: sin ella son tuteo valido
    'ten[eé]s', 'pod[eé]s', 'quer[eé]s', // nunca son tuteo
    'sent[ií]s', 'dec[ií]s', 'ven[ií]s',
  ].join('|') + ')\\b',
  'i',
);

/** Palabras que refuerzan "ahorrar = sufrir", justo lo contrario a la promesa del programa. */
const PALABRAS_PROHIBIDAS = [
  'barato', 'sacrificio', 'tacaño', 'tacano', 'restricción', 'restriccion',
  'sobrevivir', 'dieta financiera', 'ahorro hormiga', 'recortar gastos',
];

/** Lexico de otras regiones: rompe la identificacion con el avatar colombiano. */
const LEXICO_REGIONAL = /\b(che|boludo|tío|tia\b|guay|mola|chaval|wey|güey|órale|orale|chido|neta)\b/i;

/** Regla #1 "no negociable": TU ERES Andres. Nunca hablar de el en tercera persona. */
const TERCERA_PERSONA = /\bandr[eé]s\b/i;

/** Nunca revelar que es IA (rompe la percepcion del canal). */
const REVELA_IA = /\b(soy\s+(un\s+)?(bot|robot|ia\b|inteligencia artificial|asistente virtual)|como\s+(una\s+)?ia\b|modelo de lenguaje|soy\s+una\s+m[aá]quina|automatizad[oa])\b/i;

/** El precio solo se dice en la llamada, nunca en DM. */
const MENCIONA_PRECIO = /(\$\s?\d|\d+\s?(usd|d[oó]lares|millones\s+de\s+pesos\s+el\s+programa))/i;

// ---------------------------------------------------------------------------
// Biblioteca de copy aprobado
// ---------------------------------------------------------------------------

/** Normaliza para comparar: sin nombre, sin dobles espacios, minusculas. */
function huella(texto, nombre = '') {
  let t = String(texto || '');
  if (nombre) {
    const primero = nombre.trim().split(/\s+/)[0];
    if (primero) t = t.split(primero).join('');
  }
  return t
    .replace(/\{nombre\}/g, '')
    .replace(/\s+/g, ' ')
    .replace(/\s([,.!?])/g, '$1')
    .trim()
    .toLowerCase();
}

/**
 * Todas las plantillas aprobadas, normalizadas. Se calcula una sola vez.
 *
 * Incluye tanto la plantilla completa como sus burbujas partidas: las que
 * traen un link se envian como [texto, link] (ver `partirEnBurbujas`), asi que
 * el texto-sin-link tambien es copy aprobado. Sin esto la compuerta reprobaria
 * su propio mecanismo de aislamiento del link.
 */
const HUELLAS_APROBADAS = (() => {
  const fuentes = [
    ...Object.values(P),
    ...Object.values(OBJECIONES),
    CALENDAR_LINK,
    ...Object.values(REELS),
  ].filter((v) => typeof v === 'string' && v.trim());

  const set = new Set();
  for (const texto of fuentes) {
    set.add(huella(texto));
    for (const burbuja of partirEnBurbujas(texto)) set.add(huella(burbuja));
  }
  return set;
})();

/**
 * ¿Este mensaje sale de la biblioteca de copy aprobado?
 *
 * Contempla que el Worker puede anteponer 1-2 frases de empatia separadas por
 * una linea en blanco. Se prueba el mensaje completo y, si no matchea, lo que
 * viene despues de la primera linea en blanco.
 */
function esCopyAprobado(mensaje, nombre) {
  const candidatos = [mensaje];
  const corte = mensaje.indexOf('\n\n');
  if (corte > -1) candidatos.push(mensaje.slice(corte + 2));
  return candidatos.some((c) => HUELLAS_APROBADAS.has(huella(c, nombre)));
}

// ---------------------------------------------------------------------------
// El verificador
// ---------------------------------------------------------------------------

/**
 * @param {string[]} mensajes  las burbujas que se van a enviar, en orden
 * @param {object}   contexto  { nombre } del lead
 * @returns {{pasa: boolean, fallas: Array<{regla: string, detalle: string}>}}
 */
export function verificarMensajes(mensajes, contexto = {}) {
  const fallas = [];
  const nombre = contexto.nombre || '';
  const lista = Array.isArray(mensajes) ? mensajes : [];
  const falla = (regla, detalle) => fallas.push({ regla, detalle });

  // --- R1: CUALQUIER link va SOLO y de ULTIMO ------------------------------
  // Bug confirmado en produccion (proyecto de Javier): si va texto despues del
  // link en el mismo turno, Instagram los concatena y el link queda invalido
  // ("Dynamic Link Not Found"). Su regla es explicita en que esto "aplica a
  // cualquier link futuro", no solo al del calendario -- por eso se chequea
  // cualquier URL, incluidos los reels de las descalificaciones y los bumps.
  const URL_RE = /https?:\/\/\S+/;
  const indicesConLink = lista
    .map((m, i) => (URL_RE.test(String(m)) ? i : -1))
    .filter((i) => i > -1);

  if (indicesConLink.length > 1) {
    falla('R1_LINK_AISLADO', `Hay links en ${indicesConLink.length} burbujas; solo puede ir uno, y de ultimo.`);
  }
  for (const i of indicesConLink) {
    if (i !== lista.length - 1) {
      falla('R1_LINK_AISLADO',
        `El link va en la burbuja ${i + 1} de ${lista.length}: hay texto DESPUES del link en el mismo turno. Instagram lo rompe.`);
    }
    const soloLink = String(lista[i]).trim();
    if (!/^https?:\/\/\S+$/.test(soloLink)) {
      falla('R1_LINK_AISLADO',
        `La burbuja del link lleva texto pegado. Debe contener UNICAMENTE el link.`);
    }
  }

  // --- Reglas por mensaje --------------------------------------------------
  lista.forEach((msgRaw, i) => {
    const msg = String(msgRaw || '');
    const donde = `burbuja ${i + 1}/${lista.length}`;
    if (!msg.trim()) {
      falla('R0_VACIO', `${donde}: mensaje vacio.`);
      return;
    }

    // R2 -- tuteo colombiano (regla #1 no negociable de ellos)
    const voseo = msg.match(VOSEO);
    if (voseo) falla('R2_VOSEO', `${donde}: "${voseo[0]}" es voseo. Andres habla tuteo colombiano.`);

    // R3 -- palabras prohibidas
    const bajo = msg.toLowerCase();
    for (const palabra of PALABRAS_PROHIBIDAS) {
      if (bajo.includes(palabra)) {
        falla('R3_PALABRA_PROHIBIDA', `${donde}: contiene "${palabra}".`);
      }
    }

    // R4 -- lexico de otras regiones
    const regional = msg.match(LEXICO_REGIONAL);
    if (regional) falla('R4_LEXICO_REGIONAL', `${donde}: "${regional[0]}" no es lexico colombiano.`);

    // R5 -- primera persona (regla #2 no negociable de ellos)
    if (TERCERA_PERSONA.test(msg)) {
      falla('R5_TERCERA_PERSONA',
        `${donde}: menciona "Andres". El bot ES Andres y habla en primera persona.`);
    }

    // R6 -- nunca revelar que es IA
    if (REVELA_IA.test(msg)) {
      falla('R6_REVELA_IA', `${donde}: revela que es una IA.`);
    }

    // R7 -- el precio solo en la llamada. Se excluyen las burbujas de copy
    // aprobado, porque varias plantillas del SOP citan cifras a proposito
    // (los "$500K-$1M" de la Objecion 2, el "$7M y $15M+" de la 7, etc.).
    if (!esCopyAprobado(msg, nombre) && MENCIONA_PRECIO.test(msg)) {
      falla('R7_MENCIONA_PRECIO', `${donde}: menciona cifras fuera del copy aprobado.`);
    }

    // R8 -- todo lo que ve el lead sale de la biblioteca (+ empatia opcional)
    if (!esCopyAprobado(msg, nombre)) {
      falla('R8_COPY_NO_APROBADO',
        `${donde}: el texto no corresponde a ninguna plantilla aprobada. Empieza con: "${msg.slice(0, 70)}..."`);
    }
  });

  return { pasa: fallas.length === 0, fallas };
}

/** Formatea las fallas para un log legible de un vistazo. */
export function formatearFallas(resultado) {
  if (resultado.pasa) return 'PASA';
  return resultado.fallas.map((f) => `  [${f.regla}] ${f.detalle}`).join('\n');
}

export const REGLAS_VOZ = { VOSEO, PALABRAS_PROHIBIDAS, LEXICO_REGIONAL, TERCERA_PERSONA, REVELA_IA };
export { esCopyAprobado, huella };
