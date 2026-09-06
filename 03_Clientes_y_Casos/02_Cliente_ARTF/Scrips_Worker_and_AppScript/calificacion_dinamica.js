/**
 * CALIFICACION DINAMICA — Filtros 1 y 2 derivados del criterio del Setter experto
 * ============================================================================
 *
 * QUE ES ESTO Y POR QUE VIVE EN SU PROPIO ARCHIVO
 *
 * Los umbrales de calificacion (ingreso minimo, remanente minimo) venian de
 * `UMBRALES` en `sop_v42_plantillas.js`, elegidos a mano. Este modulo los
 * reemplaza por una frontera DERIVADA de 50 casos que el experto etiqueto uno
 * por uno, y esta deliberadamente aislado:
 *
 *   · No importa NADA del Worker ni del router. Es una funcion pura.
 *   · No tiene efectos: no escribe en la base, no llama al LLM, no registra.
 *   · Se apaga con una sola linea (`MODELO.activo = false`) y el llamador cae
 *     a la regla anterior sin tocar este archivo.
 *   · Se borra entero sin romper nada mas que su propio test.
 *
 * Actualizarlo es cambiar `MODELO.umbrales` y volver a correr su test: el
 * dataset etiquetado es el fixture, asi que un umbral movido fuera de la banda
 * admisible sale en rojo diciendo exactamente que caso rompio.
 *
 * ----------------------------------------------------------------------------
 * COMO SE DERIVO (6-sep-2026)
 *
 * 50 perfiles sinteticos de leads colombianos (semilla 20260906: 15 rechazos
 * obvios, 15 aprobaciones obvias, 20 borderline en 4 formas), etiquetados por
 * el experto en el artefacto "Frontera de Decision" sin ver nunca el veredicto
 * del codigo -- verlo habria medido su acuerdo con el codigo, no su criterio.
 *
 * Busqueda exhaustiva sobre todos los cortes posibles de las dos variables:
 *
 *   salario >= S  AND  remanente >= R      ->  0 errores en 50 casos
 *     S admisible: $3.600.000 .. $5.750.000
 *     R admisible: $1.970.000 .. $2.520.000
 *
 * Ninguna variable sola separa las clases (las tres solapan). La conjuncion si,
 * y perfectamente. No hizo falta un arbol, ni pesos, ni probabilidades: el
 * criterio del experto ES un AND de dos umbrales.
 *
 * ----------------------------------------------------------------------------
 * TRES COSAS QUE LOS DATOS DIJERON, Y QUE IMPORTAN MAS QUE LOS NUMEROS
 *
 * 1. EL PISO DE INGRESO ESTABA MUY ALTO. Estaba en $6.000.000, fuera de la
 *    banda admisible ($3,6M-$5,75M). Los dos unicos casos donde el experto
 *    APROBO y el codigo RECHAZABA son exactamente eso: #17 ($5,75M al 51%,
 *    le quedan $2,82M) y #46 ($5,9M al 48%, le quedan $3,07M). Dos leads que
 *    calificaban y el codigo botaba.
 *
 * 2. EL PORCENTAJE DE DEUDA NO APORTA NADA POR SI SOLO. De los 13 casos con
 *    deuda >= 70%, el experto aprobo 5 y rechazo 8 -- y la conjuncion explica
 *    los 13 sin mirar el porcentaje ni una vez. Aprobo a quien debe el 90% y
 *    gana $26,5M (le quedan $2,65M) y rechazo a quien debe el 74% y gana $7,4M
 *    (le quedan $1,92M). El porcentaje solo importa por el remanente que
 *    produce. `ENDEUDAMIENTO_PARA_BORDERLINE: 50` no estaba calificando nada.
 *
 * 3. CERO ETIQUETAS "DUDA" EN 50 CASOS. El experto nunca escalo: para el, la
 *    calificacion por cifras siempre es decidible.
 *
 *    ⚠️ OJO CON ESTA TERCERA, QUE ES LA QUE SE PUEDE MALINTERPRETAR: NO
 *    significa que M2_BORDERLINE sobre. Esa etapa pregunta que TIPO de deuda
 *    es (hipoteca vs. consumo), y el artefacto nunca le mostro al experto el
 *    tipo de deuda -- no tenia como expresar "aca yo preguntaria". Lo unico
 *    que prueba el cero es que la frontera sobre (salario, remanente) es
 *    NITIDA, no que la repregunta cualitativa sobre. Este modulo por eso no
 *    devuelve 'borderline': esa decision se queda donde esta.
 *
 * ----------------------------------------------------------------------------
 * LIMITES HONESTOS DE ESTE MODELO
 *
 * · 50 casos, un solo etiquetador, datos sinteticos. Alcanza para una frontera
 *   de dos variables; NO alcanza para meter profesion (24 valores, ~2 casos por
 *   categoria) ni para nada probabilistico.
 * · El piso de remanente queda al filo de su banda: el caso #37 lo pasa por
 *   $20.000. Ver la nota en `umbrales`.
 * · Es un modelo de la cabeza del experto, no del resultado comercial. Dice a
 *   quien HABRIA calificado, no con quien se cierran ventas. Eso solo lo dira
 *   comparar contra `gestion_lead` cuando haya volumen.
 */

/**
 * @typedef {Object} EntradaCalificacion
 * @property {number|null} ingresoCop      ingreso mensual en COP
 * @property {number|null} remanenteCop    lo que le queda tras las deudas, en COP
 * @property {number|null} [endeudamientoPct] solo informativo: no entra en la decision
 *
 * @typedef {Object} Veredicto
 * @property {'aprobar'|'rechazar'|'no_sabe'} veredicto
 * @property {string} razon                 por que, en una linea, para el summary
 * @property {number|null} holguraIngreso   pesos por encima (o debajo) del piso
 * @property {number|null} holguraRemanente idem para el remanente
 * @property {boolean} alFilo               true si alguna holgura es < MARGEN_ESTRECHO
 * @property {string} modelo                version del modelo que decidio
 */

export const MODELO = {
  version: 'frontera-experto-2026-09-06',

  /**
   * Interruptor. En false, `calificar()` devuelve 'no_sabe' con razon
   * 'modelo_apagado' y el llamador debe caer a la regla anterior. Es el camino
   * de vuelta sin tocar codigo: una linea, un deploy.
   */
  activo: true,

  umbrales: {
    /**
     * PISO DE INGRESO: $4.500.000.
     * Banda admisible $3,60M-$5,75M; se toma el punto medio (max-margen), que
     * es el valor mas lejano de los dos casos que lo rodean: el rechazado mas
     * rico con remanente suficiente ($3,40M) y el aprobado mas pobre ($5,75M).
     * Baja desde los $6.000.000 que habia, que estaban FUERA de la banda.
     */
    INGRESO_MINIMO: 4_500_000,

    /**
     * PISO DE REMANENTE: $2.500.000 — se CONSERVA el valor que ya existia.
     * Banda admisible $1,97M-$2,52M: el valor de siempre cae dentro, o sea que
     * el dato lo confirma. Pero cae casi en el borde superior, y el caso #37
     * ($8,4M al 70%, le quedan $2.520.000) lo pasa por $20.000.
     * Si se quiere el punto de maximo margen en vez del valor historico, es
     * $2.200.000; con ese valor el acuerdo sigue siendo 50/50. Se dejo el
     * historico por ser el numero que el negocio ya conoce.
     */
    REMANENTE_MINIMO: 2_500_000,

    /** Por debajo de esto se marca `alFilo`. No cambia el veredicto: solo lo señala. */
    MARGEN_ESTRECHO: 300_000,
  },

  /** De donde salio, para poder auditarlo o rehacerlo. */
  procedencia: {
    dataset: 'tests/fixtures/etiquetado_calificacion_20260906.json',
    semilla: 20260906,
    casos: 50,
    etiquetador: 'Setter experto (Gaby)',
    aciertos: '50/50',
    reemplaza: { INGRESO_MINIMO: 6_000_000, REMANENTE_MINIMO: 2_500_000, ENDEUDAMIENTO_PARA_BORDERLINE: 50 },
  },
};

const esNum = (v) => typeof v === 'number' && Number.isFinite(v);

/**
 * Decide los filtros 1 y 2 (ingreso y capacidad de pago) sobre las cifras ya
 * extraidas. NO extrae, NO redacta, NO decide etapa: solo el veredicto.
 *
 * Nunca adivina: sin ingreso o sin remanente devuelve 'no_sabe', que es lo que
 * el router ya sabe manejar (se le pregunta al lead).
 *
 * @param {EntradaCalificacion} entrada
 * @returns {Veredicto}
 */
export function calificar(entrada) {
  const base = { holguraIngreso: null, holguraRemanente: null, alFilo: false, modelo: MODELO.version };

  if (!MODELO.activo) {
    return { ...base, veredicto: 'no_sabe', razon: 'El modelo dinamico esta apagado.' };
  }

  const ingreso = entrada && entrada.ingresoCop;
  const remanente = entrada && entrada.remanenteCop;

  if (!esNum(ingreso) || ingreso <= 0) {
    return { ...base, veredicto: 'no_sabe', razon: 'Sin ingreso no se califica: hay que preguntarlo.' };
  }
  if (!esNum(remanente)) {
    return { ...base, veredicto: 'no_sabe', razon: 'Sin remanente no se califica: hay que preguntar el endeudamiento.' };
  }

  const { INGRESO_MINIMO, REMANENTE_MINIMO, MARGEN_ESTRECHO } = MODELO.umbrales;
  const holguraIngreso = ingreso - INGRESO_MINIMO;
  const holguraRemanente = remanente - REMANENTE_MINIMO;
  const alFilo = Math.min(Math.abs(holguraIngreso), Math.abs(holguraRemanente)) < MARGEN_ESTRECHO;
  const comun = { holguraIngreso, holguraRemanente, alFilo, modelo: MODELO.version };

  // La frontera. Es un AND, y ese AND es literalmente el criterio del experto:
  // gana lo suficiente Y le queda lo suficiente. Ni el porcentaje de deuda ni
  // la profesion entran -- los datos dijeron que no aportan.
  if (holguraIngreso < 0) {
    return { ...comun, veredicto: 'rechazar', razon: `Gana ${cop(ingreso)}, por debajo del piso de ${cop(INGRESO_MINIMO)}.` };
  }
  if (holguraRemanente < 0) {
    return { ...comun, veredicto: 'rechazar', razon: `Le quedan ${cop(remanente)} libres, por debajo del piso de ${cop(REMANENTE_MINIMO)}.` };
  }
  return { ...comun, veredicto: 'aprobar', razon: `Gana ${cop(ingreso)} y le quedan ${cop(remanente)} libres.` };
}

/**
 * El remanente a partir del porcentaje, que es como llega del lead. Se expone
 * aparte porque el router ya hace esta cuenta y conviene que sea LA MISMA.
 * @returns {number|null} null si no se puede calcular (no se adivina)
 */
export function remanenteDesdePct(ingresoCop, endeudamientoPct) {
  if (!esNum(ingresoCop) || ingresoCop <= 0) return null;
  if (!esNum(endeudamientoPct) || endeudamientoPct < 0 || endeudamientoPct > 100) return null;
  return Math.round(ingresoCop * (1 - endeudamientoPct / 100));
}

function cop(n) {
  return '$' + Math.round(n).toLocaleString('es-CO');
}
