/**
 * Modelo del clasificador configurable + prompt ordenado para la cache (13-sep-2026).
 *
 * Contexto: Groq free limita qwen/qwen3.8-27b a 200K tokens/dia por organizacion
 * y no ofrece cache de prompt para qwen. openai/gpt-oss-120b si la ofrece, y
 * "los tokens en cache no cuentan para los limites" (docs oficiales). Para que
 * la cache sirva, la parte FIJA del prompt tiene que ir primero: hoy el estado y
 * la conversacion van arriba y rompen el prefijo.
 *
 * Reglas que estos tests protegen:
 *   1. Con qwen (default) el cuerpo que se manda a Groq es IDENTICO al de antes,
 *      byte a byte (fixtures capturados antes del cambio).
 *
 *      ⚠️ FIXTURES RECAPTURADOS EL 14-SEP-2026 (+1438 chars en los tres, solo en
 *      `system`). NO se ablando el test: entro una regla de negocio nueva -- los
 *      RANGOS DE DEUDA se leen por el techo y no por el piso -- y esa regla va
 *      en el prompt, asi que el prompt de qwen tenia que cambiar. Lo que el test
 *      sigue protegiendo es lo de siempre: que el orden 'cache' de gpt-oss no
 *      altere ni un caracter del prompt de qwen. Si estos fixtures se vuelven a
 *      tocar sin una regla nueva detras, el cambio esta mal.
 *   2. El cambio de modelo es una variable, solo del clasificador, y solo acepta
 *      modelos con perfil.
 *   3. Con gpt-oss la parte fija va primero y es identica entre turnos distintos.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  clasificar, PERFILES_MODELO, modeloClasificador, MODELO_POR_DEFECTO,
} from '../worker_bot_setter_v42.js';

const CASOS = [
  ['m2_con_historial', { etapa_bot: 'M2_ENVIADO', estado_codigo: 'contactado', salario_monto: 8000000 }, '62%', 'LEAD: soy medico\nTU: ¿Cuanto ganas?'],
  ['m5_sin_historial', { etapa_bot: 'M5_ENVIADO', estado_codigo: 'calificado' }, 'Si', ''],
  ['cierre', { etapa_bot: 'CIERRE_PRECALL', estado_codigo: 'calificado' }, 'gracias', 'LEAD: listo\nTU: nos vemos'],
];

async function cuerpoEnviado(env, estado, texto, hist) {
  const original = globalThis.fetch;
  let cuerpo;
  globalThis.fetch = async (url, opts) => {
    cuerpo = JSON.parse(opts.body);
    return { ok: true, status: 200, headers: new Map(), json: async () => ({ choices: [{ message: { content: '{}' } }], usage: {} }) };
  };
  try { await clasificar(env, estado, texto, null, hist); } finally { globalThis.fetch = original; }
  return cuerpo;
}

describe('Con qwen (default) nada cambia', () => {
  for (const [nombre, estado, texto, hist] of CASOS) {
    test(`el cuerpo enviado es identico al de antes: ${nombre}`, async () => {
      const esperado = JSON.parse(readFileSync(new URL(`./fixtures/prompts/${nombre}.json`, import.meta.url), 'utf8'));
      // PROMPT_POR_ETAPA='false' = la perilla de reversa. Que los fixtures de
      // ANTES del enrutado sigan cuadrando byte a byte es lo que prueba que
      // apagarla devuelve el prompt de siempre, no uno parecido.
      const c = await cuerpoEnviado({ GROQ_API_KEY: 'k', PROMPT_POR_ETAPA: 'false' }, estado, texto, hist);
      assert.equal(c.model, esperado.model);
      assert.equal(c.max_tokens, esperado.max_tokens);
      assert.equal(c.temperature, esperado.temperature);
      assert.deepEqual(c.response_format, esperado.response_format);
      assert.equal(c.messages[0].content, esperado.system, 'el system prompt de qwen no puede cambiar ni un caracter');
      assert.equal(c.messages[1].content, esperado.user);
    });
  }
});

describe('El modelo del clasificador es configuracion, no codigo', () => {
  test('default qwen; LLM_MODELO_CLASIFICADOR elige otro con perfil', () => {
    assert.equal(MODELO_POR_DEFECTO, 'qwen/qwen3.8-27b');
    assert.equal(modeloClasificador({}), MODELO_POR_DEFECTO);
    assert.equal(modeloClasificador({ LLM_MODELO_CLASIFICADOR: 'openai/gpt-oss-120b' }), 'openai/gpt-oss-120b');
  });

  test('un modelo sin perfil no se usa: se cae al default (nunca un modelo a ciegas)', () => {
    assert.equal(modeloClasificador({ LLM_MODELO_CLASIFICADOR: 'openai/gpt-oss-20b-inventado' }), MODELO_POR_DEFECTO);
  });

  test('cada perfil declara como se pide la salida', () => {
    for (const [modelo, perfil] of Object.entries(PERFILES_MODELO)) {
      assert.ok(perfil.parametros, `${modelo} sin parametros`);
      assert.ok(['clasico', 'cache'].includes(perfil.orden), `${modelo} sin orden de prompt`);
    }
  });
});

describe('Con gpt-oss-120b: parte fija primero para aprovechar la cache', () => {
  const env = { GROQ_API_KEY: 'k', LLM_MODELO_CLASIFICADOR: 'openai/gpt-oss-120b' };

  test('pide el modelo con sus parametros de razonamiento', async () => {
    const c = await cuerpoEnviado(env, CASOS[0][1], CASOS[0][2], CASOS[0][3]);
    assert.equal(c.model, 'openai/gpt-oss-120b');
    assert.equal(c.reasoning_effort, PERFILES_MODELO['openai/gpt-oss-120b'].parametros.reasoning_effort);
    assert.equal(c.max_tokens, undefined, 'gpt-oss usa max_completion_tokens: el razonamiento cuenta contra el');
    assert.ok(c.max_completion_tokens > 600);
    assert.deepEqual(c.response_format, { type: 'json_object' });
  });

  test('el prefijo fijo es identico entre turnos de la MISMA etapa', async () => {
    // ⚠️ CAMBIO DELIBERADO (18-sep-2026). Antes se exigia un prefijo unico para
    // TODAS las etapas. Con las reglas enrutadas eso ya no es cierto ni deseable:
    // cada etapa manda solo sus reglas, asi que hay un prefijo cacheable POR
    // ETAPA en vez de uno solo. La cache de Groq sigue sirviendo -- reutiliza el
    // prefijo entre turnos de la misma etapa, que es como avanzan los leads --
    // y ademas cada prefijo es mas corto. Lo que se perderia es cache al SALTAR
    // de etapa, y eso vale mucho menos que los 2.242 tokens que ahorra el
    // enrutado en cada turno.
    const mismaEtapa = [CASOS[0][1], CASOS[0][2], 'LEAD: hola\nTU: buenas'];
    const a = (await cuerpoEnviado(env, CASOS[0][1], CASOS[0][2], CASOS[0][3])).messages[0].content;
    const b = (await cuerpoEnviado(env, mismaEtapa[0], mismaEtapa[1], mismaEtapa[2])).messages[0].content;
    const fin = a.indexOf('<estado_actual>');
    assert.ok(fin > 5000, 'el estado va DESPUES de todas las reglas fijas');
    assert.equal(b.slice(0, fin), a.slice(0, fin), 'mismo prefijo = cache reutilizable entre turnos');
  });

  test('etapas distintas traen prefijos distintos: eso ES el enrutado', async () => {
    const m2 = (await cuerpoEnviado(env, CASOS[0][1], CASOS[0][2], CASOS[0][3])).messages[0].content;
    const m5 = (await cuerpoEnviado(env, CASOS[1][1], CASOS[1][2], CASOS[1][3])).messages[0].content;
    assert.ok(m5.length < m2.length, 'M5 no necesita las reglas de plata y tiene que pesar menos');
    assert.match(m2, /RANGOS DE DEUDA/, 'M2 si lleva las reglas de deuda');
    assert.doesNotMatch(m5, /RANGOS DE DEUDA/, 'M5 no las necesita: no extrae deuda');
  });

  test('conserva TODAS las reglas: solo cambia el orden', async () => {
    const qwen = JSON.parse(readFileSync(new URL('./fixtures/prompts/m2_con_historial.json', import.meta.url), 'utf8')).system;
    // Con el enrutado apagado a ambos lados: lo que este test vigila es que el
    // ORDEN 'cache' no pierda reglas, no el enrutado (que tiene su propio test).
    const oss = (await cuerpoEnviado({ ...env, PROMPT_POR_ETAPA: 'false' },
      CASOS[0][1], CASOS[0][2], CASOS[0][3])).messages[0].content;
    for (const etiqueta of ['<rol_y_contexto>', '<estado_actual>', '<conversacion_previa>', '<reglas_de_oro>',
      '<definicion_de_intenciones>', '<campos_a_extraer>', '<redaccion>', '<ejemplos>',
      '<cierre_de_conversacion>', '<seguridad>', '<formato_de_salida>']) {
      assert.ok(oss.includes(etiqueta), `falta ${etiqueta}`);
    }
    const lineas = (t) => new Set(t.split('\n').map((l) => l.trim()).filter((l) => l.length > 25));
    const faltan = [...lineas(qwen)].filter((l) => !lineas(oss).has(l) && !/ahi arriba/.test(l));
    assert.deepEqual(faltan, [], 'ninguna regla del prompt de qwen puede perderse');
    assert.ok(oss.trimEnd().endsWith('}'), 'el esquema JSON sigue siendo lo ultimo');
  });
});
