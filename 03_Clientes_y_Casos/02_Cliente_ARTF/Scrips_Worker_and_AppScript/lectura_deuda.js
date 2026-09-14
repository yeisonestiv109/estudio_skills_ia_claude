/**
 * LECTURA FIEL DE LA CIFRA DE DEUDA — Filtro 2 (12-sep-2026)
 * ============================================================================
 *
 * EL BUG QUE CIERRA (traza real tr_cd45365f7f). Lead con ingreso de $22M,
 * pregunta del porcentaje, responde "1200" (sumo el SALDO de sus creditos y lo
 * dividio por su sueldo). Qwen devolvio `deuda_cop = 12000000`: una escala que
 * el lead nunca escribio. El router saco 55%, "le quedan 9.900.000 libres", y
 * lo califico. En otras corridas el mismo "1200" salia como 12% o como $1.200:
 * el modelo "corrige" una cifra que le parece imposible, y la corrige hacia
 * algo que PASA el filtro.
 *
 * LA DIVISION DEL TRABAJO (la misma de todo el bot, aplicada a los numeros):
 *   · El LLM ENTIENDE el lenguaje: copia la cifra tal cual la escribio el lead
 *     (`deuda_literal`) y dice si el lead expreso una unidad
 *     (`deuda_unidad_dicha`: porcentaje / pesos / ninguna). "Me quedan",
 *     "pago", "palos", "lucas" son lenguaje: eso lo resuelve el.
 *   · Este modulo VERIFICA: que la cifra exista en el mensaje, que nadie la
 *     haya reescalado sin una palabra que lo justifique, y si es posible como
 *     cuota mensual. No interpreta lenguaje: compara numeros.
 *
 * Es la tecnica de extraccion anclada ("grounded extraction"): el modelo cita
 * y el codigo comprueba la cita contra la fuente, en vez de confiar en un
 * numero ya transformado. Nada aca decide si el lead califica: eso sigue en
 * `evaluarEndeudamiento`. Esto solo entrega un dato en el que se puede confiar,
 * o dice por que no.
 *
 * TODO lo que se decide queda en `diagnostico`, que el Worker vuelca a la
 * traza. Una discrepancia entre lo que dijo el LLM y lo que escribio el lead
 * se ve en el dashboard con nombre propio, sin reconstruirla a mano.
 */
import { UNIDAD_QUE_PIDE_LA_PREGUNTA } from './sop_v42_plantillas.js';

/**
 * Numero tolerante a como escribe un colombiano (y a como tipa el LLM).
 * Miles con punto o coma ("1.500.000", "1,500,000"), decimal latino ("42,5"),
 * `$` y `COP` alrededor. Lo que no es un numero es null: no se adivina.
 */
export function aNumero(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v !== 'string') return null;
  let t = v.trim().replace(/\s|\$|COP|%/gi, '');
  if (!t) return null;
  // Separadores de miles inequivocos: grupos de exactamente 3 digitos.
  if (/^-?\d{1,3}([.,]\d{3})+$/.test(t)) t = t.replace(/[.,]/g, '');
  // Decimal con coma al estilo latino: 42,5 -> 42.5
  else if (/^-?\d+,\d{1,2}$/.test(t)) t = t.replace(',', '.');
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

/** Todas las cifras escritas en un texto, ya normalizadas ("1.200" -> 1200). */
export function numerosDelTexto(texto) {
  return (String(texto ?? '').match(/\d+(?:[.,]\d+)*/g) || [])
    .map(aNumero)
    .filter((n) => n !== null);
}

/**
 * Una palabra de escala ("mil", "lucas", "millones", "palos") multiplica por
 * 1.000 como minimo. Por eso una cuota en pesos MIL veces menor que el ingreso
 * es la huella exacta de un "mil" que el lead se comio al hablar ("pago 1200"
 * por 1.200.000) -- o de un porcentaje mal hecho. No es un umbral de negocio:
 * no cambia quien califica, solo marca cuando hay que preguntar.
 */
const FACTOR_DE_ESCALA_MINIMO = 1000;

const UNIDADES = ['porcentaje', 'pesos', 'ninguna'];

const LETRA = /\p{L}/u;

/**
 * @param {object} c        clasificacion ya validada del LLM
 * @param {string} textoLead lo que escribio el lead en este turno
 * @param {string} etapa    etapa en la que se hizo la pregunta
 * @param {number|null} ingreso
 * @returns {{
 *   endeudamiento_pct: number|null, deuda_cop: number|null, remanente_cop: number|null,
 *   plausibilidad: 'plausible'|'imposible'|'ambigua'|'sin_cifra',
 *   diagnostico: Record<string, string|number|null>,
 * }}
 */
export function leerDeuda(c = {}, textoLead = '', etapa = null, ingreso = null) {
  const llm = {
    pct: c?.endeudamiento_pct ?? null,
    deuda: c?.deuda_cop ?? null,
    rem: c?.remanente_cop ?? null,
  };
  const citaDelLLM = typeof c?.deuda_literal === 'string' && c.deuda_literal.trim()
    ? c.deuda_literal.trim() : null;
  // Si el modelo no copio la cifra pero el mensaje no tiene NI UNA letra
  // ("1200", "70%", "1.500.000"), no hay lenguaje que interpretar: el mensaje
  // mismo es la cita. Asi el caso real se ataja aunque el LLM ignore el campo.
  const mensaje = String(textoLead ?? '').trim();
  const mensajeEsLaCita = !citaDelLLM && mensaje && !LETRA.test(mensaje) && numerosDelTexto(mensaje).length > 0;
  const literal = citaDelLLM || (mensajeEsLaCita ? mensaje : null);
  const unidadDicha = UNIDADES.includes(c?.deuda_unidad_dicha) ? c.deuda_unidad_dicha : null;
  const unidadEsperada = UNIDAD_QUE_PIDE_LA_PREGUNTA[etapa] || 'abierta';

  let final = { ...llm };
  let anclaje;
  let unidadLeida = null;

  if (!literal) {
    // Clasificacion sin cita (etapas que no la piden, o el modelo no la lleno):
    // se usa lo que dijo el LLM, y los chequeos de posibilidad corren igual.
    anclaje = 'sin_literal';
  } else {
    // RANGOS DE DEUDA (14-sep-2026). Un literal puede traer DOS cifras porque el
    // lead contesto con un rango: "entre 7 y 15", "del 20 al 30%".
    //
    // Anclar en la PRIMERA hundia la deuda a su piso, que es justo al reves de
    // la prudencia que pide el negocio: con el ingreso se toma el piso y con la
    // deuda el techo, porque ambos eligen el escenario MENOS favorable para el
    // lead. Caso real: "Entre 7 y 15" entraba como 7% y el lead pasaba el filtro
    // con la MITAD de su deuda.
    //
    // Y hacia algo peor que equivocarse: el LLM extraia bien el 15, el ancla lo
    // bajaba a 7 y la traza lo registraba como `llm_cambio_la_cifra` -- culpaba
    // al modelo del error de quien lo estaba leyendo.
    //
    // Con UNA sola cifra el maximo es esa misma cifra, asi que ningun caso que
    // ya funcionaba cambia de comportamiento.
    const cifrasDelLiteral = numerosDelTexto(literal);
    const v = cifrasDelLiteral.length ? Math.max(...cifrasDelLiteral) : null;
    if (v === null) {
      // "setenta", "la mitad": no hay digitos que comprobar. Convertir palabras
      // en numeros es lenguaje, y eso es del LLM.
      anclaje = 'en_palabras';
    } else if (!numerosDelTexto(textoLead).includes(v)) {
      // El modelo cito una cifra que el lead no escribio. No se usa NINGUNA:
      // decidir un filtro sobre un numero inventado es peor que volver a pedirlo.
      anclaje = 'literal_no_esta_en_el_mensaje';
      final = { pct: null, deuda: null, rem: null };
    } else {
      anclaje = mensajeEsLaCita ? 'mensaje_sin_palabras' : 'ok';
      const conPalabra = LETRA.test(literal);
      const conPorcentaje = literal.includes('%');

      if (conPorcentaje || unidadDicha === 'porcentaje') unidadLeida = 'porcentaje';
      // Un numero <= 100 sin palabra que lo acompañe no es plata en ningun
      // contexto: nadie paga $70 de cuota. Es un porcentaje.
      else if (v <= 100 && !conPalabra) unidadLeida = 'porcentaje';
      else if (unidadDicha === 'pesos') unidadLeida = 'pesos';
      // Pelado: manda la unidad que pidio la pregunta.
      else unidadLeida = unidadEsperada === 'porcentaje' ? 'porcentaje' : 'pesos';

      if (unidadLeida === 'porcentaje') {
        final = { pct: v, deuda: null, rem: null };
      } else {
        const campo = llm.rem !== null && llm.deuda === null ? 'rem' : 'deuda';
        const x = llm[campo];
        // Solo una palabra escrita por el lead autoriza a escalar la cifra, y
        // una escala nunca achica. Todo lo demas vuelve a lo que el lead escribio.
        const valor = conPalabra && x !== null && x >= v ? x : v;
        final = { pct: null, deuda: campo === 'deuda' ? valor : null, rem: campo === 'rem' ? valor : null };
      }
    }
  }

  const llmDijoAlgo = llm.pct !== null || llm.deuda !== null || llm.rem !== null;
  const cambio = llmDijoAlgo && (llm.pct !== final.pct || llm.deuda !== final.deuda || llm.rem !== final.rem)
    && (anclaje === 'ok' || anclaje === 'mensaje_sin_palabras');

  // ¿Es posible como dato del Filtro 2?
  let plausibilidad = 'plausible';
  let motivo = null;
  if (final.pct === null && final.deuda === null && final.rem === null) {
    plausibilidad = 'sin_cifra';
  } else if (final.pct !== null && final.pct >= 100) {
    // Pagar en cuotas todo el sueldo o mas, cada mes, no es una cuota: es el
    // saldo total dividido por el ingreso, o una cuenta mal hecha.
    plausibilidad = 'imposible';
    motivo = 'porcentaje_mayor_o_igual_a_100';
  } else if (final.deuda !== null && ingreso > 0 && final.deuda >= ingreso) {
    plausibilidad = 'imposible';
    motivo = 'cuota_mayor_o_igual_al_ingreso';
  } else if (final.deuda !== null && ingreso > 0 && final.deuda * FACTOR_DE_ESCALA_MINIMO < ingreso) {
    plausibilidad = 'ambigua';
    motivo = 'cuota_mil_veces_menor_al_ingreso';
  }

  return {
    endeudamiento_pct: final.pct,
    deuda_cop: final.deuda,
    remanente_cop: final.rem,
    plausibilidad,
    diagnostico: {
      'deuda.literal': literal,
      'deuda.unidad_dicha': unidadDicha,
      'deuda.unidad_esperada': unidadEsperada,
      'deuda.unidad_leida': unidadLeida,
      'deuda.anclaje': anclaje,
      'deuda.llm_pct': llm.pct,
      'deuda.llm_deuda_cop': llm.deuda,
      'deuda.llm_remanente_cop': llm.rem,
      'deuda.discrepancia': cambio ? 'llm_cambio_la_cifra' : null,
      'deuda.pct_final': final.pct,
      'deuda.cop_final': final.deuda,
      'deuda.remanente_final': final.rem,
      'deuda.plausibilidad': plausibilidad,
      'deuda.motivo': motivo,
    },
  };
}
