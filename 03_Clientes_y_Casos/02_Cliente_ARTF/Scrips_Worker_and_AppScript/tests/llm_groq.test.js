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

import { pedirAGroq, llavesDeGroq, aliasDeLlave, leerCapacidad } from '../llm_groq.mjs';

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

  test('una llave inválida NO se reintenta con otra: cambiar de llave no arregla un 401', async () => {
    let llamadas = 0;
    const fake = async () => { llamadas++; return resp401(); };
    const r = await pedirAGroq({ GROQ_API_KEYS: 'mala,buena' }, {}, { fetchImpl: fake });
    assert.equal(r.ok, false);
    assert.equal(llamadas, 1, 'gastar la siguiente llave en un 401 es tirar cupo');
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

  test('headers ausentes no rompen nada', () => {
    const c = leerCapacidad(new Map());
    assert.equal(c.limite_tokens, null);
    assert.equal(c.reset_tokens, null);
  });
});
