/**
 * Tests del trazador de telemetria.
 *
 * LO QUE DE VERDAD IMPORTA AQUI no es el formato de los spans: es que esta
 * pieza NUNCA pueda dañar un turno del lead. Por eso la mayoria de los tests
 * son sobre el comportamiento defensivo (apagado, sin ctx, sin credenciales,
 * atributos raros) y sobre el costo (UNA escritura por turno, no una por span).
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
  nuevoTrazador, NODOS, truncar, sanearAtributos, telemetriaActiva,
} from '../telemetria_spans.js';

const ENV = { SUPABASE_URL: 'https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'k' };
/** ctx falso: guarda las promesas en vez de ejecutarlas, como hace Cloudflare. */
const ctxFalso = () => { const p = []; return { waitUntil: (x) => p.push(x), _p: p }; };

describe('Trazador: no puede dañar el turno del lead', () => {
  test('con TELEMETRIA_ACTIVA="false" queda inerte y no revienta', () => {
    const tz = nuevoTrazador({ ...ENV, TELEMETRIA_ACTIVA: 'false' }, ctxFalso());
    assert.equal(tz.activa, false);
    const s = tz.inicio(NODOS.LLM);
    assert.equal(s, null, 'no crea spans');
    // Cerrar un span nulo tiene que ser inofensivo: es el caso real cuando
    // alguien apaga la telemetria con el codigo ya instrumentado.
    assert.doesNotThrow(() => tz.fin(s, 'OK'));
    assert.doesNotThrow(() => tz.evento(NODOS.ROUTER, 'OK'));
    assert.doesNotThrow(() => tz.enviar());
    assert.equal(tz._spans.length, 0);
  });

  test('sin credenciales de Supabase tampoco intenta nada', () => {
    const tz = nuevoTrazador({}, ctxFalso());
    assert.equal(tz.activa, false);
  });

  test('sin ctx (tests, ejecucion local) no agenda ningun envio', () => {
    const tz = nuevoTrazador(ENV, null);
    tz.evento(NODOS.WEBHOOK, 'OK');
    assert.doesNotThrow(() => tz.enviar());
  });

  test('la perilla por defecto esta encendida', () => {
    assert.equal(telemetriaActiva({}), true);
    assert.equal(telemetriaActiva({ TELEMETRIA_ACTIVA: 'false' }), false);
    assert.equal(telemetriaActiva({ TELEMETRIA_ACTIVA: 'FALSE' }), false);
  });
});

describe('Trazador: costo acotado (regla anti-overload)', () => {
  test('UN turno = UNA sola escritura, sin importar cuantos spans haya', () => {
    const ctx = ctxFalso();
    const tz = nuevoTrazador(ENV, ctx);
    for (let i = 0; i < 9; i += 1) tz.evento(NODOS.ROUTER, 'OK', { i });
    tz.enviar();
    assert.equal(ctx._p.length, 1, '9 spans, 1 promesa: el lote es lo que hace O(1) el costo');
  });

  test('enviar() dos veces no duplica filas', () => {
    const ctx = ctxFalso();
    const tz = nuevoTrazador(ENV, ctx);
    tz.evento(NODOS.WEBHOOK, 'OK');
    tz.enviar();
    tz.enviar();
    assert.equal(ctx._p.length, 1);
  });

  test('hay tope de spans por turno: un bucle no puede inundar la tabla', () => {
    const tz = nuevoTrazador(ENV, ctxFalso());
    for (let i = 0; i < 500; i += 1) tz.evento(NODOS.ROUTER, 'OK');
    assert.ok(tz._spans.length <= 40, `se corta en 40, hubo ${tz._spans.length}`);
  });
});

describe('Trazador: la traza cuenta lo que paso', () => {
  test('un span cerrado lleva duracion y estado', () => {
    const tz = nuevoTrazador(ENV, ctxFalso());
    const s = tz.inicio(NODOS.LLM, { 'llm.model': 'qwen' });
    tz.fin(s, 'OK', { 'llm.usage.total_tokens': 920 });
    assert.equal(s.status, 'OK');
    assert.ok(s.duration_ms >= 0);
    assert.equal(s.attributes['llm.model'], 'qwen');
    assert.equal(s.attributes['llm.usage.total_tokens'], 920);
  });

  test('un span que nunca cierra queda PENDING: asi se ve donde murio el turno', () => {
    const tz = nuevoTrazador(ENV, ctxFalso());
    tz.inicio(NODOS.ESCRITURA);
    const [fila] = tz._lote();
    assert.equal(fila.status, 'PENDING');
    assert.equal(fila.ended_at, null);
  });

  test('todos los spans comparten el trace_id del turno', () => {
    const tz = nuevoTrazador(ENV, ctxFalso());
    tz.evento(NODOS.WEBHOOK, 'OK');
    tz.evento(NODOS.ROUTER, 'OK');
    const filas = tz._lote();
    assert.equal(new Set(filas.map((f) => f.trace_id)).size, 1);
    assert.equal(new Set(filas.map((f) => f.span_id)).size, 2, 'cada span tiene id propio');
  });

  test('el contexto que se conoce tarde se aplica a TODOS los spans', () => {
    // El gestion_lead_id llega con el estado, despues del primer span. Sin
    // esto, el dashboard no podria agrupar el turno completo por lead.
    const tz = nuevoTrazador(ENV, ctxFalso(), { manychat_id: '123' });
    tz.evento(NODOS.WEBHOOK, 'OK');
    tz.contexto({ gestion_lead_id: 'uuid-1', etapa_bot: 'M2_ENVIADO' });
    tz.evento(NODOS.ROUTER, 'OK');
    for (const fila of tz._lote()) {
      assert.equal(fila.manychat_id, '123');
      assert.equal(fila.gestion_lead_id, 'uuid-1');
      assert.equal(fila.etapa_bot, 'M2_ENVIADO');
    }
  });

  test('el lote no filtra campos internos', () => {
    const tz = nuevoTrazador(ENV, ctxFalso());
    tz.evento(NODOS.WEBHOOK, 'OK');
    assert.ok(!('_t0' in tz._lote()[0]), '_t0 es de la implementacion, no va a la base');
  });
});

describe('Datos personales: el texto del lead va acotado', () => {
  test('los strings largos se truncan', () => {
    const largo = 'a'.repeat(500);
    assert.ok(truncar(largo).length <= 161, 'se recorta a ~160 + el caracter de corte');
    assert.equal(truncar('hola'), 'hola');
  });

  test('los espacios y saltos de linea se colapsan', () => {
    assert.equal(truncar('  hola\n\n  mundo '), 'hola mundo');
  });

  test('numeros y booleanos pasan intactos; undefined se descarta', () => {
    const a = sanearAtributos({ n: 42, b: false, nulo: null, fuera: undefined });
    assert.deepEqual(a, { n: 42, b: false, nulo: null });
  });

  test('los objetos no se vuelcan crudos: se serializan y recortan', () => {
    const a = sanearAtributos({ obj: { muy: 'anidado', lista: [1, 2, 3] } });
    assert.equal(typeof a.obj, 'string');
    assert.ok(a.obj.length <= 161);
  });

  test('atributos invalidos no rompen nada', () => {
    assert.deepEqual(sanearAtributos(null), {});
    assert.deepEqual(sanearAtributos('texto'), {});
  });
});
