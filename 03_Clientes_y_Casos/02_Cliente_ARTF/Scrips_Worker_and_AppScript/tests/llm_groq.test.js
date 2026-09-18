/**
 * Pool de llaves de Groq y telemetría.
 *
 * CONTEXTO: las llamadas rebotaban con `output tokens per minute (OTPM):
 * Limit 1000` y el fallo era SILENCIOSO -- el bot seguía con solo deterministas,
 * ciego a crisis y objeciones.
 *
 * ⚠️ DOS HECHOS COMPROBADOS que estos tests protegen:
 *  1. Los límites de Groq son POR ORGANIZACIÓN (los errores citan
 *     `in organization 'org_...'`). Dos llaves de la misma cuenta comparten
 *     cupo: rotarlas no aporta nada.
 *  2. Los headers NO exponen el límite que frena. Publican TPM total (8000),
 *     pero el que rebota es OTPM (1000) y no tiene header. Por eso se cuentan
 *     los tokens de salida por nuestra cuenta.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';


import { pedirAGroq, llavesDeGroq, aliasDeLlave, leerCapacidad, leerLimiteDelError } from '../llm_groq.mjs';
import { clasificar, crearObservadorLLM } from '../worker_bot_setter_v42.js';

const headersFalsos = (extra = {}) => new Map(Object.entries({
  'x-ratelimit-limit-requests': '1000',
  'x-ratelimit-remaining-requests': '999',
  'x-ratelimit-reset-requests': '1m26.4s',
  'x-ratelimit-limit-tokens': '8000',
  'x-ratelimit-remaining-tokens': '7936',
  'x-ratelimit-reset-tokens': '480ms',
  ...extra,
}));

const respOk = (tokens = 60) => ({
  ok: true, status: 200, headers: headersFalsos(),
  json: async () => ({ choices: [{ message: { content: '{}' } }], usage: { completion_tokens: tokens } }),
});
const resp429 = () => ({
  ok: false, status: 429, headers: headersFalsos({ 'x-ratelimit-remaining-tokens': '0' }),
  text: async () => 'output tokens per minute (OTPM): Limit 1000, Requested 2048',
});
const resp401 = () => ({
  ok: false, status: 401, headers: headersFalsos(), text: async () => 'Invalid API Key',
});

describe('Pool de llaves de Groq', () => {
  test('lee el pool, y cae a la llave única si no hay pool', () => {
    assert.equal(llavesDeGroq({ GROQ_API_KEYS: 'a, b ,c' }).length, 3);
    assert.equal(llavesDeGroq({ GROQ_API_KEY: 'x' }).length, 1);
    assert.equal(llavesDeGroq({ GROQ_API_KEYS: '', GROQ_API_KEY: 'x' }).length, 1,
      'un pool vacío no puede dejar al bot sin LLM');
    assert.equal(llavesDeGroq({}).length, 0);
  });

  test('sin llaves no explota: devuelve el motivo', async () => {
    const r = await pedirAGroq({}, {});
    assert.equal(r.ok, false);
    assert.equal(r.detalle, 'sin_llaves');
  });

  test('con la principal sana, NO toca las de respaldo', async () => {
    // Es failover, no round-robin: siempre arranca por la principal para que
    // sea predecible qué llave atiende.
    let llamadas = 0;
    const fake = async () => { llamadas++; return respOk(); };
    const r = await pedirAGroq({ GROQ_API_KEYS: 'k1,k2,k3' }, {}, { fetchImpl: fake });
    assert.equal(r.ok, true);
    assert.equal(llamadas, 1);
    assert.equal(r.alias, 'principal');
  });

  test('ante un 429 salta a la siguiente llave y salva el turno', async () => {
    const usadas = [];
    const fake = async (_url, opts) => {
      usadas.push(opts.headers.Authorization);
      return usadas.length === 1 ? resp429() : respOk(120);
    };
    const r = await pedirAGroq({ GROQ_API_KEYS: 'k1,k2' }, {}, { fetchImpl: fake });
    assert.equal(r.ok, true, 'el lead tiene que quedar atendido');
    assert.equal(r.alias, 'respaldo_1');
    assert.equal(usadas.length, 2);
    assert.match(usadas[1], /k2/);
  });

  test('registra TODOS los intentos, no solo el que funcionó', () => {
    // Si solo se guardara el resultado final, un pool al borde del límite se
    // vería perfectamente sano en el dashboard.
    const fake = async () => resp429();
    return pedirAGroq({ GROQ_API_KEYS: 'k1,k2' }, {}, { fetchImpl: fake }).then((r) => {
      assert.equal(r.ok, false);
      assert.equal(r.intentos.length, 2, 'los dos 429 tienen que quedar registrados');
      assert.ok(r.intentos.every((i) => i.resultado === '429'));
    });
  });

  // CAMBIO DE REGLA A PROPOSITO (12-sep-2026). Antes un 401 cortaba el pool:
  // "gastar la siguiente llave en un 401 es tirar cupo". Eso vale para un error
  // del PEDIDO (400: cuerpo mal formado, ninguna llave lo arregla). Un 401/403
  // es un error de ESA llave: no consume cupo, y la siguiente es otra
  // credencial. Con el break, revocar una llave en la consola de Groq antes de
  // sacarla de GROQ_API_KEYS tumbaba el LLM entero con dos respaldos sanos.
  test('una llave invalida (401) salta a la siguiente: el error es de ESA llave', async () => {
    let llamadas = 0;
    const fake = async () => { llamadas++; return llamadas === 1 ? resp401() : respOk(); };
    const r = await pedirAGroq({ GROQ_API_KEYS: 'revocada,buena' }, {}, { fetchImpl: fake });
    assert.equal(r.ok, true, 'el lead queda atendido por el respaldo');
    assert.equal(r.alias, 'respaldo_1');
    assert.equal(r.intentos[0].resultado, 'llave_invalida', 'y queda a la vista que la principal esta muerta');
  });

  test('un 400 (el PEDIDO esta mal) sigue sin reintentarse: ninguna llave lo arregla', async () => {
    let llamadas = 0;
    const fake = async () => { llamadas++; return { ok: false, status: 400, headers: new Map(), text: async () => 'bad request' }; };
    const r = await pedirAGroq({ GROQ_API_KEYS: 'k1,k2' }, {}, { fetchImpl: fake });
    assert.equal(r.ok, false);
    assert.equal(llamadas, 1, 'gastar la siguiente llave en un pedido mal formado es tirar cupo');
  });

  test('si TODAS rebotan, falla limpio y sin lanzar', async () => {
    const fake = async () => resp429();
    const r = await pedirAGroq({ GROQ_API_KEYS: 'k1,k2,k3' }, {}, { fetchImpl: fake });
    assert.equal(r.ok, false);
    assert.equal(r.estado, 429);
    assert.equal(r.intentos.length, 3);
  });

  test('una excepción de red tampoco lanza', async () => {
    const fake = async () => { throw new Error('red caída'); };
    const r = await pedirAGroq({ GROQ_API_KEY: 'k' }, {}, { fetchImpl: fake });
    assert.equal(r.ok, false);
    assert.match(r.detalle, /red caída/);
  });

  test('los alias no exponen la llave', () => {
    assert.equal(aliasDeLlave(0), 'principal');
    assert.equal(aliasDeLlave(1), 'respaldo_1');
    for (const a of [0, 1, 2].map(aliasDeLlave)) {
      assert.ok(!/[A-Za-z0-9_-]{20,}/.test(a), 'un alias no puede parecerse a una llave');
    }
  });
});

describe('Capacidad publicada por Groq', () => {
  test('se leen los headers que sí existen', () => {
    const c = leerCapacidad(headersFalsos());
    assert.equal(c.limite_tokens, 8000);
    assert.equal(c.restantes_tokens, 7936);
    assert.equal(c.reset_tokens, '480ms');
    assert.equal(c.limite_requests, 1000);
  });

  test('el token de salida se cuenta por nuestra cuenta, porque Groq no lo publica', async () => {
    // ESTE es el punto. `x-ratelimit-remaining-tokens` diría 7936 (sano),
    // mientras el límite que rebota es OTPM=1000 y no tiene header. Sin este
    // conteo propio, el dashboard mostraría verde con la capacidad agotada.
    const fake = async () => respOk(421);
    const r = await pedirAGroq({ GROQ_API_KEY: 'k' }, {}, { fetchImpl: fake });
    assert.equal(r.tokensSalida, 421, 'sale de usage.completion_tokens, no de un header');
    assert.equal(r.capacidad.restantes_tokens, 7936);
    assert.ok(r.capacidad.restantes_tokens > r.tokensSalida * 2,
      'el header se ve sano aunque el OTPM esté al límite: por eso no basta');
  });

  test('cada intento trae tokens de entrada, huella de la llave y latencia', async () => {
    const fake = async () => ({
      ok: true, status: 200, headers: headersFalsos(),
      json: async () => ({ choices: [{ message: { content: '{}' } }], usage: { prompt_tokens: 5100, completion_tokens: 90 } }),
    });
    const r = await pedirAGroq({ GROQ_API_KEYS: 'gsk_secretoLargoXYZ9' }, {}, { fetchImpl: fake });
    assert.equal(r.tokensEntrada, 5100);
    assert.equal(r.intentos[0].tokensEntrada, 5100);
    assert.equal(r.intentos[0].huella, 'XYZ9', 'solo los ultimos 4');
    assert.ok(!JSON.stringify(r).includes('secretoLargo'), 'la llave jamas viaja en el resultado');
    assert.equal(typeof r.intentos[0].latenciaMs, 'number');
  });

  test('el limite que rebota se LEE del error: tipo, valor y organizacion', async () => {
    const msg = '{"error":{"message":"Rate limit reached for model `qwen/qwen3.8-27b` in organization `org_01kyebnn` service tier `on_demand` on input tokens per minute (ITPM): Limit 7000, Used 4100, Requested 5066. Please try again in 18.5s."}}';
    assert.deepEqual(leerLimiteDelError(msg), { tipo: 'ITPM', valor: 7000, usado: 4100, pedido: 5066, organizacion: 'org_01kyebnn' });
    assert.deepEqual(leerLimiteDelError('Invalid API Key'), { tipo: null, valor: null, usado: null, pedido: null, organizacion: null });
    const fake = async () => ({ ok: false, status: 429, headers: new Map(), text: async () => msg });
    const r = await pedirAGroq({ GROQ_API_KEY: 'k' }, {}, { fetchImpl: fake });
    assert.equal(r.intentos[0].limite.tipo, 'ITPM');
    assert.equal(r.intentos[0].limite.organizacion, 'org_01kyebnn');
  });

  test('headers ausentes no rompen nada', () => {
    const c = leerCapacidad(new Map());
    assert.equal(c.limite_tokens, null);
    assert.equal(c.reset_tokens, null);
  });
});

// ===========================================================================
// LAS 4 LLAMADAS AL LLM QUEDAN REGISTRADAS (12-sep-2026)
//
// Solo el clasificador escribia en llm_telemetria: adaptar objecion, responder
// pregunta y repregunta eran invisibles, y el 21% de 429 que se veia era un
// piso, no la tasa real. Tampoco quedaba en la traza QUE llave atendio.
// ===========================================================================
import { readFileSync } from 'node:fs';
import {
  atributosLlamadaLLM, adaptarObjecionConLLM, responderPreguntaConLLM, decidirRepregunta,
} from '../worker_bot_setter_v42.js';

describe('Observador de llamadas al LLM', () => {
  const src = readFileSync(new URL('../worker_bot_setter_v42.js', import.meta.url), 'utf8');

  test('toda llamada a pedirAGroq avisa al observador', () => {
    const llamadas = src.match(/await pedirAGroq\(/g) || [];
    const avisos = src.match(/notificarLLM\(obs, '[a-z_]+', r\)/g) || [];
    assert.ok(llamadas.length >= 4);
    assert.equal(avisos.length, llamadas.length, 'una llamada sin aviso vuelve a ser invisible');
  });

  test('los atributos cuentan la rotacion completa y la llave que atendio', () => {
    const r = {
      ok: true, alias: 'respaldo_1', huella: 'AB12', tokensEntrada: 5100, tokensSalida: 90,
      intentos: [
        { alias: 'principal', huella: 'ZZ99', resultado: '429', latenciaMs: 120, limite: { tipo: 'ITPM', valor: 7000, organizacion: 'org_a' } },
        { alias: 'respaldo_1', huella: 'AB12', resultado: 'ok', latenciaMs: 880 },
      ],
    };
    const a = atributosLlamadaLLM('clasificador', r);
    assert.equal(a['llm.funcion'], 'clasificador');
    assert.equal(a['llm.llave'], 'respaldo_1');
    assert.equal(a['llm.huella'], 'AB12');
    assert.equal(a['llm.intentos'], 'principal:429 > respaldo_1:ok');
    assert.equal(a['llm.rotacion'], true);
    assert.equal(a['llm.tokens_entrada'], 5100);
    assert.equal(a['llm.latencia_ms'], 1000);
    assert.equal(a['llm.limite_tipo'], 'ITPM');
    assert.equal(a['llm.organizacion_limitada'], 'org_a');
    assert.equal(a['llm.resultado'], 'ok');
  });

  async function conFetch(cuerpo, fn) {
    const original = globalThis.fetch;
    globalThis.fetch = async () => ({
      ok: true, status: 200, headers: new Map(),
      json: async () => ({ choices: [{ message: { content: cuerpo } }], usage: { prompt_tokens: 900, completion_tokens: 40 } }),
    });
    try { return await fn(); } finally { globalThis.fetch = original; }
  }

  test('las tres funciones de generacion reportan su nombre al observador', async () => {
    const vistos = [];
    const obs = (funcion, r) => vistos.push([funcion, r.tokensEntrada]);
    const env = { GROQ_API_KEY: 'k' };
    await conFetch('Buena pregunta.\n\n¿Agendamos?', () => adaptarObjecionConLLM(env, 'Buena pregunta.\n\n¿Agendamos?', 'ok', true, '', '', obs));
    await conFetch('Te cuento.', () => responderPreguntaConLLM(env, '¿cuanto cuesta?', 'cuanto cuesta', '', obs));
    await conFetch('{"accion":"mantener"}', () => decidirRepregunta(env, 'algo', '¿Cuanto ganas?', '', 'ok', false, obs));
    const nombres = vistos.map(([f]) => f);
    assert.ok(nombres.includes('adaptar_objecion'), nombres.join());
    assert.ok(nombres.includes('responder_pregunta'), nombres.join());
    assert.ok(nombres.includes('repregunta'), nombres.join());
    assert.ok(vistos.every(([, t]) => t === 900));
  });
});

describe('Tokens en cache (Fase 1: consumo diario)', () => {
  test('se leen de usage.prompt_tokens_details.cached_tokens y viajan al registro', async () => {
    const fake = async () => ({
      ok: true, status: 200, headers: new Map(),
      json: async () => ({ choices: [{ message: { content: '{}' } }],
        usage: { prompt_tokens: 5000, completion_tokens: 90, prompt_tokens_details: { cached_tokens: 4096 } } }),
    });
    const r = await pedirAGroq({ GROQ_API_KEY: 'k' }, {}, { fetchImpl: fake });
    assert.equal(r.tokensCacheados, 4096);
    assert.equal(r.intentos[0].tokensCacheados, 4096);
    assert.equal(atributosLlamadaLLM('clasificador', r)['llm.tokens_cacheados'], 4096);
    const src = readFileSync(new URL('../worker_bot_setter_v42.js', import.meta.url), 'utf8');
    assert.match(src, /p_tokens_cacheados: intento\.tokensCacheados \|\| 0,/);
  });

  test('sin el campo (qwen no tiene cache en Groq) vale 0, no undefined', async () => {
    const fake = async () => ({ ok: true, status: 200, headers: new Map(),
      json: async () => ({ choices: [{ message: { content: '{}' } }], usage: { prompt_tokens: 5000 } }) });
    const r = await pedirAGroq({ GROQ_API_KEY: 'k' }, {}, { fetchImpl: fake });
    assert.equal(r.tokensCacheados, 0);
  });
});

describe('ROTACION: un 4xx raro no puede dejar llaves sin usar (15-sep-2026)', () => {
  /**
   * Traza real: `principal:429 > respaldo_1:error` con `respaldo_2` SIN PROBAR,
   * y el lead a HANDOFF con una llave entera sin tocar.
   *
   * Antes habia un `break` ante cualquier 4xx que no fuera 429/401/403, con el
   * argumento de que "el pedido esta mal y ninguna llave lo arregla". Pero si el
   * pedido estuviera mal, la PRIMERA llave habria devuelto 400 tambien, no 429.
   * Un 4xx que aparece SOLO en una llave es de esa organizacion -- cuota diaria,
   * modelo no habilitado, cuenta suspendida -- y la siguiente puede atenderlo.
   */
  function fetchFalso(respuestas, vistas) {
    return async (url, opts) => {
      const llave = String(opts.headers.Authorization).replace('Bearer ', '');
      vistas.push(llave);
      const r = respuestas[llave] ?? { status: 500 };
      return {
        ok: r.status === 200,
        status: r.status,
        headers: new Map(),
        json: async () => ({ choices: [{ message: { content: '{}' } }], usage: {} }),
        text: async () => r.detalle ?? '',
      };
    };
  }

  test('⚠️ 429 y luego 400: se prueba la TERCERA llave', async () => {
    const vistas = [];
    const r = await pedirAGroq(
      { GROQ_API_KEYS: 'k1,k2,k3' }, { model: 'm', messages: [] },
      { fetchImpl: fetchFalso({ k1: { status: 429 }, k2: { status: 400, detalle: 'model not available for this organization' }, k3: { status: 200 } }, vistas) },
    );
    assert.equal(r.ok, true, 'la tercera llave atendio el turno');
    assert.deepEqual(vistas, ['k1', 'k2', 'k3'], 'se probaron LAS TRES');
  });

  test('si TODAS fallan tras el primer 429, se reporta en vez de fingir', async () => {
    const vistas = [];
    const r = await pedirAGroq(
      { GROQ_API_KEYS: 'k1,k2,k3' }, { model: 'm', messages: [] },
      { fetchImpl: fetchFalso({ k1: { status: 429 }, k2: { status: 400 }, k3: { status: 400 } }, vistas) },
    );
    assert.equal(r.ok, false);
    assert.equal(r.intentos.length, 3, 'los tres intentos quedan en la traza');
  });

  test('⚠️ pero un 400 en la PRIMERA llave sigue cortando: el pedido esta mal', () => {
    // La regla vieja no se deroga, se acota. Si el pedido estuviera bien, la
    // primera llave no habria devuelto 400. Gastar las otras dos ahi es tirar
    // cupo, que es exactamente lo que el test original protegia.
    assert.ok(true, 'cubierto por el test "un 400 (el PEDIDO esta mal) sigue sin reintentarse"');
  });
});

// ===========================================================================
// EL PANEL TIENE QUE VER EL POOL, NO SOLO LAS LLAVES YA USADAS (18-sep-2026)
//
// El fundador puso 5 llaves y el panel seguia mostrando 3. No era que el panel
// fuera estatico: llm_telemetria solo aprendia de una llave cuando esa llave se
// usaba, y la rotacion es por FAILOVER -- respaldo_3 y respaldo_4 solo se tocan
// si las anteriores rebotan el mismo minuto. En un dia tranquilo no aparecian
// nunca, y el panel no podia distinguir "no existe" de "esta en reserva".
// ===========================================================================
describe('El Worker declara su pool completo en cada turno', () => {
  test('manda TODOS los alias, no solo el que atendio la llamada', async () => {
    const rpcs = [];
    const original = globalThis.fetch;
    globalThis.fetch = async (url, opts) => {
      const u = String(url);
      if (u.includes('/rest/v1/rpc/')) {
        rpcs.push({ fn: u.split('/rpc/')[1], body: JSON.parse(opts.body) });
        return { ok: true, status: 200, headers: new Map(), json: async () => ([]) };
      }
      return {
        ok: true, status: 200, headers: new Map(),
        json: async () => ({ choices: [{ message: { content: '{}' } }], usage: {} }),
      };
    };
    const env = {
      SUPABASE_URL: 'https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'k',
      GROQ_API_KEYS: 'a1,b2,c3,d4,e5',
    };
    const espera = [];
    try {
      await clasificar(env, { etapa_bot: 'M5_ENVIADO', estado_codigo: 'calificado' },
        'dale', { waitUntil: (p) => espera.push(p) }, '',
        crearObservadorLLM(env, { waitUntil: (p) => espera.push(p) }, null));
      await Promise.all(espera);
    } finally { globalThis.fetch = original; }

    const pool = rpcs.find((r) => r.fn === 'fn_registrar_pool_llm');
    assert.ok(pool, 'no se declaro el pool: las llaves en reserva serian invisibles');
    assert.deepEqual(pool.body.p_alias,
      ['principal', 'respaldo_1', 'respaldo_2', 'respaldo_3', 'respaldo_4'],
      'tienen que ir las 5, aunque solo una haya atendido');
    assert.equal(pool.body.p_proveedor, 'groq');
  });

  test('con una sola llave declara una sola, sin inventar respaldos', async () => {
    const rpcs = [];
    const original = globalThis.fetch;
    globalThis.fetch = async (url, opts) => {
      const u = String(url);
      if (u.includes('/rest/v1/rpc/')) {
        rpcs.push({ fn: u.split('/rpc/')[1], body: JSON.parse(opts.body) });
        return { ok: true, status: 200, headers: new Map(), json: async () => ([]) };
      }
      return {
        ok: true, status: 200, headers: new Map(),
        json: async () => ({ choices: [{ message: { content: '{}' } }], usage: {} }),
      };
    };
    const env = {
      SUPABASE_URL: 'https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'k',
      GROQ_API_KEY: 'solo-una',
    };
    const espera = [];
    try {
      await clasificar(env, { etapa_bot: 'M5_ENVIADO', estado_codigo: 'calificado' },
        'dale', { waitUntil: (p) => espera.push(p) }, '',
        crearObservadorLLM(env, { waitUntil: (p) => espera.push(p) }, null));
      await Promise.all(espera);
    } finally { globalThis.fetch = original; }
    const pool = rpcs.find((r) => r.fn === 'fn_registrar_pool_llm');
    assert.deepEqual(pool.body.p_alias, ['principal']);
  });
});

describe('El panel distingue una llave en reserva de una retirada', () => {
  const dash = readFileSync(new URL('../telemetria/index.html', import.meta.url), 'utf8');

  test('tiene un estado para la llave que ya no esta en el pool', () => {
    assert.match(dash, /retirada:\s*\{[^}]*Fuera del pool/,
      'sin esto una llave quitada de GROQ_API_KEYS se seguia viendo en verde');
    assert.match(dash, /fila\.en_pool === false/);
  });

  test('la capacidad se cuenta solo con las llaves vivas', () => {
    // "Cupos reales" es el numero con el que se decide si hay red suficiente.
    // Contar ahi una llave retirada es peor que no mostrarla: miente hacia
    // arriba justo en la metrica de capacidad.
    assert.match(dash, /const activas = reales\.filter\(\(f\) => f\.en_pool !== false\)/);
    assert.match(dash, /new Set\(activas\.map/);
  });
});
