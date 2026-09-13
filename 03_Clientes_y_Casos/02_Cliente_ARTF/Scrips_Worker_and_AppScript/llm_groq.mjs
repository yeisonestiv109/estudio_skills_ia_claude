/**
 * Cliente de Groq con pool de llaves y telemetria.
 * ============================================================================
 * Modulo AISLADO: no sabe nada del router ni del playbook. Solo llama a Groq,
 * sobrevive a los 429 y reporta capacidad.
 *
 * POR QUE EXISTE (5-sep-2026): las llamadas rebotaban con
 * `output tokens per minute (OTPM): Limit 1000` y el fallo era SILENCIOSO --
 * el bot seguia con solo deterministas, ciego a crisis y objeciones.
 *
 * ⚠️ DOS COSAS QUE HAY QUE SABER ANTES DE TOCAR ESTO:
 *
 * 1. LOS LIMITES DE GROQ SON POR ORGANIZACION, NO POR LLAVE. Se comprobo en los
 *    mensajes de error, que citan `in organization 'org_...'`. Dos llaves de la
 *    MISMA cuenta comparten cupo y rotarlas no sirve de nada. El pool solo
 *    aporta si las llaves son de organizaciones distintas.
 *
 * 2. LOS HEADERS NO EXPONEN EL LIMITE QUE NOS FRENA. Groq publica
 *    `x-ratelimit-*-tokens` (TPM total: 8000) pero el que rebota es OTPM
 *    (salida por minuto: 1000) y NO tiene header. Por eso aca se cuentan los
 *    tokens de salida por nuestra cuenta: es la unica medida fiable.
 */

/** Lee el pool: `GROQ_API_KEYS` (coma) y, si no, la `GROQ_API_KEY` de siempre. */
export function llavesDeGroq(env) {
  const pool = String(env?.GROQ_API_KEYS || '')
    .split(',').map((s) => s.trim()).filter(Boolean);
  if (pool.length) return pool;
  const unica = String(env?.GROQ_API_KEY || '').trim();
  return unica ? [unica] : [];
}

/** Alias legible para la telemetria. NUNCA se guarda la llave. */
export const aliasDeLlave = (i) => (i === 0 ? 'principal' : `respaldo_${i}`);

const numero = (v) => {
  // ⚠️ `Number(null)` es 0, no NaN. Sin este guard, un header AUSENTE se
  // guardaba como 0 -- y en el dashboard "0 restantes" se lee como capacidad
  // agotada. Una falsa alarma por un header que simplemente no vino.
  if (v === null || v === undefined || String(v).trim() === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

/** Saca la capacidad publicada por Groq de los headers. */
export function leerCapacidad(headers) {
  const h = (k) => headers?.get?.(k) ?? null;
  return {
    limite_requests: numero(h('x-ratelimit-limit-requests')),
    restantes_requests: numero(h('x-ratelimit-remaining-requests')),
    reset_requests: h('x-ratelimit-reset-requests'),
    limite_tokens: numero(h('x-ratelimit-limit-tokens')),
    restantes_tokens: numero(h('x-ratelimit-remaining-tokens')),
    reset_tokens: h('x-ratelimit-reset-tokens'),
  };
}

/**
 * Lee del mensaje de error QUE limite rebota, su valor y la organizacion.
 *
 * Groq no publica en headers el limite que nos frena (ni OTPM ni ITPM), pero
 * lo escribe en el 429: "in organization `org_...` ... on input tokens per
 * minute (ITPM): Limit 7000, Used 4100, Requested 5066". Leerlo de ahi hace que
 * la telemetria se entere sola si el limite cambia, y que dos alias de la
 * MISMA organizacion (un solo cupo) se vean sin revisar el texto a mano.
 */
export function leerLimiteDelError(detalle) {
  const t = String(detalle ?? '');
  const org = t.match(/organization `([^`]+)`/);
  const lim = t.match(/\((\w+)\):\s*Limit\s+(\d+)(?:,\s*Used\s+(\d+))?(?:,\s*Requested\s+(\d+))?/);
  return {
    tipo: lim ? lim[1].toUpperCase() : null,
    valor: lim ? Number(lim[2]) : null,
    usado: lim?.[3] ? Number(lim[3]) : null,
    pedido: lim?.[4] ? Number(lim[4]) : null,
    organizacion: org ? org[1] : null,
  };
}

/** Ultimos 4 caracteres: suficiente para saber de que cuenta es, inutil para usarla. */
const huellaDe = (llave) => String(llave || '').slice(-4);

/**
 * Llama a Groq recorriendo el pool si hace falta.
 *
 * Es FAILOVER, no round-robin: siempre arranca por la principal y solo pasa a
 * la siguiente si la actual devuelve 429, 5xx o 401/403. Round-robin repartiria
 * carga pero haria impredecible que llave atiende a quien, y con llaves de
 * distinta capacidad eso es peor, no mejor.
 *
 * 401/403 (12-sep-2026): antes cortaban el pool. Pero son errores de ESA
 * llave (revocada, mal pegada), no del pedido: no consumen cupo y la siguiente
 * es otra credencial. Con el corte, revocar una llave en la consola antes de
 * sacarla de GROQ_API_KEYS dejaba al bot sin LLM con dos respaldos sanos. Un
 * 400 si sigue cortando: es el cuerpo el que esta mal y ninguna llave lo arregla.
 *
 * @returns {Promise<{ok, datos?, intentos, alias?, tokensSalida, capacidad?, estado?, detalle?}>}
 */
export async function pedirAGroq(env, cuerpo, { timeoutMs = 8000, fetchImpl = fetch } = {}) {
  const llaves = llavesDeGroq(env);
  if (!llaves.length) return { ok: false, intentos: [], tokensSalida: 0, detalle: 'sin_llaves' };

  const intentos = [];

  for (let i = 0; i < llaves.length; i++) {
    const alias = aliasDeLlave(i);
    const huella = huellaDe(llaves[i]);
    const t0 = Date.now();
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const resp = await fetchImpl('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: { Authorization: `Bearer ${llaves[i]}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(cuerpo),
        signal: ctrl.signal,
      });
      const capacidad = leerCapacidad(resp.headers);

      if (resp.ok) {
        const datos = await resp.json();
        const tokensSalida = datos?.usage?.completion_tokens ?? 0;
        const tokensEntrada = datos?.usage?.prompt_tokens ?? 0;
        // Solo los modelos con cache de prompt lo reportan (en Groq, gpt-oss-*).
        const tokensCacheados = datos?.usage?.prompt_tokens_details?.cached_tokens ?? 0;
        intentos.push({ alias, huella, resultado: 'ok', tokensSalida, tokensEntrada, tokensCacheados, capacidad, latenciaMs: Date.now() - t0 });
        return { ok: true, datos, intentos, alias, huella, tokensSalida, tokensEntrada, tokensCacheados, capacidad };
      }

      const detalle = (await resp.text()).slice(0, 300);
      const llaveInvalida = resp.status === 401 || resp.status === 403;
      const reintentable = resp.status === 429 || resp.status >= 500 || llaveInvalida;
      intentos.push({
        alias, huella,
        resultado: resp.status === 429 ? '429' : llaveInvalida ? 'llave_invalida' : 'error',
        estado: resp.status, detalle, capacidad, tokensSalida: 0, tokensEntrada: 0,
        limite: leerLimiteDelError(detalle), latenciaMs: Date.now() - t0,
      });
      if (!reintentable) break;      // 400: el pedido esta mal, ninguna llave lo arregla
      console.warn(`[groq] ${alias} devolvio ${resp.status}; se prueba la siguiente llave.`);
    } catch (e) {
      intentos.push({
        alias, huella, resultado: 'error', detalle: String(e?.message || e).slice(0, 200),
        tokensSalida: 0, tokensEntrada: 0, latenciaMs: Date.now() - t0,
      });
    } finally { clearTimeout(t); }
  }

  const ultimo = intentos[intentos.length - 1] || {};
  return {
    ok: false, intentos, tokensSalida: 0, tokensEntrada: 0, tokensCacheados: 0,
    estado: ultimo.estado, detalle: ultimo.detalle, capacidad: ultimo.capacidad,
  };
}
