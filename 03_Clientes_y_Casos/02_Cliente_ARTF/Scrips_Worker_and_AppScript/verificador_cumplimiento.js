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

import {
  PLANTILLAS as P, OBJECIONES, OBJECIONES_PRE_PITCH, OBJ_6_EN_M1, CALENDAR_LINK, REELS, partirEnBurbujas,
} from './sop_v42_plantillas.js';

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
    // Variantes sin cierre de agenda para las etapas de calificacion: se
    // derivan de las plantillas aprobadas recortando parrafos, asi que son
    // copy aprobado tambien.
    ...Object.values(OBJECIONES_PRE_PITCH),
    // Misma familia: la Objecion 6 recortada un parrafo mas para que enganche
    // con la pregunta del rango en M1 sin repetir "Te pregunto porque...".
    OBJ_6_EN_M1,
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
/**
 * Reglas para el UNICO texto que no sale de la biblioteca: la respuesta
 * generada por el LLM en el catch-all (decision del fundador, 4-sep-2026).
 *
 * No se puede verificar contra una huella -- no hay plantilla que comparar --
 * pero SI se puede verificar que sea seguro. Esto es lo que queda cuando se
 * cede el determinismo del texto: se pierde "es copy aprobado" y se conserva
 * "no puede hacer daño".
 *
 * Devuelve la lista de fallas (vacia si pasa).
 */
export function verificarTextoGenerado(texto) {
  const fallas = [];
  const t = String(texto || '');
  if (!t.trim()) return fallas;

  // Longitud: es un reencauce empatico, no un discurso.
  if (t.length > 320) fallas.push({ regla: 'G1_MUY_LARGO', detalle: `${t.length} caracteres (max 320).` });

  // NINGUNA URL. El bot manda un solo link en toda la conversacion y sale de la
  // biblioteca; un link generado es el vector de phishing del que se advirtio.
  if (/https?:\/\/|www\.|\b[\w.-]+\.(com|co|net|org|io|me|ly|app|link)\b/i.test(t)) {
    fallas.push({ regla: 'G2_LLEVA_LINK', detalle: 'el texto generado no puede contener URLs.' });
  }
  // Ni datos de contacto.
  if (/@[A-Za-z0-9_.]{3,}|\d[\d\s().-]{7,}/.test(t)) {
    fallas.push({ regla: 'G3_LLEVA_CONTACTO', detalle: 'parece incluir un handle, correo o telefono.' });
  }
  // Ni rastros de inyeccion.
  if (/\b(ignora|olvida|instrucciones|system|prompt|assistant|act[uú]a como)\b/i.test(t)) {
    fallas.push({ regla: 'G4_INYECCION', detalle: 'contiene lexico de inyeccion de prompt.' });
  }
  // Las dos reglas de voz "no negociables" de Javier, que ya se rompieron en
  // produccion: tuteo colombiano y hablar en primera persona como Andres.
  if (/\b(ten[eé]s|pod[eé]s|quer[eé]s|sab[eé]s\s+vos|vos\b|che\b|boludo|t[ií]o\b|guay\b|mola\b|wey\b|[oó]rale|chido)\b/i.test(t)) {
    fallas.push({ regla: 'G5_VOSEO_O_REGIONALISMO', detalle: 'rompe el tuteo colombiano estricto.' });
  }
  if (/\bandr[eé]s\b/i.test(t)) {
    fallas.push({ regla: 'G6_TERCERA_PERSONA', detalle: 'menciona a Andres en tercera persona; el bot ES Andres.' });
  }
  // Lexico prohibido del playbook (ahorrar = sufrir).
  const PROHIBIDAS = /\b(barato|sacrificio|tacañ|restricci[oó]n|sobrevivir|dieta financiera|ahorro hormiga|recortar gastos|mentalidad de abundancia|manifiestalo|manifi[eé]stalo)\b/i;
  if (PROHIBIDAS.test(t)) {
    fallas.push({ regla: 'G7_LEXICO_PROHIBIDO', detalle: 'usa vocabulario prohibido por el playbook.' });
  }
  // ⚠️ LA REGLA MAS IMPORTANTE DE ESTE SET, y la razon esta abajo:
  // el resto de reglas comprueba que el texto sea SEGURO. Ninguna puede
  // comprobar que sea CIERTO. Un modelo puede escribir "te garantizamos ahorrar
  // el 30% en 8 semanas" y pasar todas las demas. Por eso se prohibe el lexico
  // con el que se inventan hechos sobre el programa: promesas, garantias,
  // cifras y plazos. Lo que el programa promete de verdad ya esta escrito en las
  // plantillas, y esas si se verifican contra la biblioteca.
  if (/\b(te garantiz|garantizamos|garantizad|te aseguro|te prometo|prometemos|100%\s+seguro|sin falta|resultados garantizados)\b/i.test(t)) {
    fallas.push({ regla: 'G9_PROMESA', detalle: 'promete o garantiza un resultado.' });
  }
  if (/\b\d+\s*%|\b\d+\s*(semanas?|meses?|d[ií]as?|años?)\b/i.test(t)) {
    fallas.push({ regla: 'G10_CIFRA_INVENTADA', detalle: 'cita porcentajes o plazos: esos solo pueden salir de una plantilla aprobada.' });
  }

  // No puede prometer ni negar el agendamiento: eso lo decide la base.
  if (/\b(ya quedaste agendad|tu reunion esta confirmada|te confirmo la reunion)\b/i.test(t)) {
    fallas.push({ regla: 'G8_AFIRMA_AGENDA', detalle: 'afirma un agendamiento que solo la base puede confirmar.' });
  }
  return fallas;
}

/**
 * @param {object} contexto
 *   - nombre: para renderizar las plantillas al comparar huellas.
 *   - generado: string opcional. La burbuja que produjo el LLM en el catch-all;
 *     se exime de R8 (no hay huella que comparar) y se somete a
 *     `verificarTextoGenerado`. Todo lo demas sigue igual: el link, el precio y
 *     las otras reglas se le aplican como a cualquier burbuja.
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

    // R8 -- todo lo que ve el lead sale de la biblioteca (+ empatia opcional).
    // Excepcion unica y explicita: la burbuja generada por el LLM en el
    // catch-all, que no tiene huella contra la cual comparar y por eso pasa por
    // su propio set de reglas.
    const esLaGenerada = contexto.generado && msg.trim() === String(contexto.generado).trim();
    if (esLaGenerada) {
      for (const f of verificarTextoGenerado(msg)) {
        falla(f.regla, `${donde} (texto generado): ${f.detalle}`);
      }
    } else if (esCopyAprobado(msg, nombre)) {
      // HUECO QUE ESTO CIERRA (4-sep-2026): `esCopyAprobado` acepta
      // "prefijo generado\n\nplantilla aprobada" mirando solo lo que va DESPUES
      // de la linea en blanco. Eso hacia que el prefijo -- que lo escribe el LLM
      // y es lo unico que el lead lee sin aprobar -- pasara sin verificarse.
      // Ahora el cuerpo se valida contra la biblioteca Y el prefijo contra las
      // reglas del texto generado.
      const corte = msg.indexOf('\n\n');
      if (corte > -1 && !HUELLAS_APROBADAS.has(huella(msg, nombre))) {
        const prefijo = msg.slice(0, corte).trim();
        if (prefijo) {
          for (const f of verificarTextoGenerado(prefijo)) {
            falla(f.regla, `${donde} (apertura generada): ${f.detalle}`);
          }
        }
      }
    } else {
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
