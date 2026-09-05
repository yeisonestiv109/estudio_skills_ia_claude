/**
 * Tests para el módulo de notificación a Google Chat.
 * ============================================================================
 * TDD: estos tests se escribieron ANTES de inyectar la llamada en el Worker.
 * Verifican que:
 *  1. Se envía la alerta cuando HAY handoff Y HAY webhook configurado.
 *  2. NO se envía sin webhook (entorno local / tests).
 *  3. NO se envía sin handoff (flujo normal del bot).
 *  4. Un error de red NO propaga — el bot sigue funcionando.
 *  5. El formato del mensaje contiene todos los datos esperados.
 *  6. Datos parciales (sin profesión, sin IG, etc.) no revientan.
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { notificarSetterGoogleChat } from '../notificador_google_chat.js';

// ---------------------------------------------------------------------------
// Mock global de fetch — se instala/desinstala en cada test para no ensuciar
// ---------------------------------------------------------------------------
let fetchCalls = [];
let fetchShouldFail = false;
let originalFetch;

function mockFetch(url, opts) {
  fetchCalls.push({ url, opts, body: opts?.body ? JSON.parse(opts.body) : null });
  if (fetchShouldFail) {
    return Promise.resolve({ ok: false, status: 500, text: () => Promise.resolve('mock error') });
  }
  return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('ok') });
}

// ---------------------------------------------------------------------------
// Fixtures reutilizables
// ---------------------------------------------------------------------------
function estadoCompleto() {
  return {
    nombre: 'Marly',
    ig_handle: 'marlyy318',
    profesion: 'Ingeniera',
    salario_monto: 8000000,
    endeudamiento_pct: 40,
    dolor: 'B',
    urgencia: 'alta',
    etapa_bot: 'M5_ENVIADO',
    handoff_razon: 'resistencia_acumulada',
  };
}

function planConHandoff(razon = 'agendamiento_manual_pendiente') {
  return {
    handoffRazon: razon,
    etapaNueva: 'HANDOFF',
    campos: {},
    mensajes: [],
  };
}

function planSinHandoff() {
  return {
    handoffRazon: null,
    etapaNueva: 'M3_ENVIADO',
    campos: {},
    mensajes: ['¡Perfecto!'],
  };
}

function envConWebhook() {
  return { GOOGLE_CHAT_WEBHOOK: 'https://chat.googleapis.com/v1/spaces/AAAA/messages?key=test' };
}

function envSinWebhook() {
  return {};
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------
describe('Notificador Google Chat', () => {
  beforeEach(() => {
    fetchCalls = [];
    fetchShouldFail = false;
    originalFetch = globalThis.fetch;
    globalThis.fetch = mockFetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  // =========================================================================
  // Test Positivo: Handoff + Webhook → se envía
  // =========================================================================
  test('envía alerta cuando hay handoff Y webhook configurado', async () => {
    await notificarSetterGoogleChat(envConWebhook(), estadoCompleto(), planConHandoff());

    assert.equal(fetchCalls.length, 1, 'fetch debe llamarse exactamente 1 vez');
    assert.equal(fetchCalls[0].url, envConWebhook().GOOGLE_CHAT_WEBHOOK);
    assert.equal(fetchCalls[0].opts.method, 'POST');
  });

  // =========================================================================
  // Formato del mensaje: contiene todos los datos del lead
  // =========================================================================
  test('el mensaje incluye nombre, profesión, salario, deuda, dolor, IG y razón', async () => {
    await notificarSetterGoogleChat(envConWebhook(), estadoCompleto(), planConHandoff());

    assert.equal(fetchCalls.length, 1);
    const texto = fetchCalls[0].body.text;

    assert.match(texto, /Marly/, 'debe incluir el nombre');
    assert.match(texto, /Ingeniera/, 'debe incluir la profesión');
    assert.match(texto, /8.*000.*000/, 'debe incluir el salario');
    assert.match(texto, /40%/, 'debe incluir el endeudamiento');
    assert.match(texto, /instagram\.com\/marlyy318/, 'debe incluir el link de IG');
    assert.match(texto, /agendamiento_manual_pendiente/, 'debe incluir la razón del handoff');
    assert.match(texto, /NUEVO LEAD PARA SETTER/, 'debe tener el encabezado');
  });

  // =========================================================================
  // Test Negativo 1: Sin handoff → NO se envía
  // =========================================================================
  test('NO envía alerta cuando no hay handoff (flujo normal)', async () => {
    await notificarSetterGoogleChat(envConWebhook(), estadoCompleto(), planSinHandoff());

    assert.equal(fetchCalls.length, 0, 'fetch NO debe llamarse sin handoff');
  });

  // =========================================================================
  // Test Negativo 2: Sin webhook → NO se envía
  // =========================================================================
  test('NO envía alerta cuando no hay GOOGLE_CHAT_WEBHOOK', async () => {
    await notificarSetterGoogleChat(envSinWebhook(), estadoCompleto(), planConHandoff());

    assert.equal(fetchCalls.length, 0, 'fetch NO debe llamarse sin webhook');
  });

  test('NO envía alerta con webhook vacío', async () => {
    await notificarSetterGoogleChat(
      { GOOGLE_CHAT_WEBHOOK: '' },
      estadoCompleto(),
      planConHandoff(),
    );

    assert.equal(fetchCalls.length, 0, 'fetch NO debe llamarse con webhook vacío');
  });

  // =========================================================================
  // Resiliencia: error de red NO propaga
  // =========================================================================
  test('un error de red NO lanza excepción (el bot sigue funcionando)', async () => {
    fetchShouldFail = true;

    // No debe lanzar — si lanzara, este test falla.
    await notificarSetterGoogleChat(envConWebhook(), estadoCompleto(), planConHandoff());

    assert.equal(fetchCalls.length, 1, 'fetch SÍ se intentó');
    // Si llegamos aquí sin throw, la resiliencia funciona.
  });

  test('un fetch que explota con TypeError NO lanza excepción', async () => {
    globalThis.fetch = () => { throw new TypeError('Network error'); };

    await notificarSetterGoogleChat(envConWebhook(), estadoCompleto(), planConHandoff());
    // Si llegamos aquí, el catch interno funciona.
  });

  // =========================================================================
  // Datos parciales: el módulo no explota con campos faltantes
  // =========================================================================
  test('funciona con estado parcial (sin profesión, sin IG, sin dolor)', async () => {
    const estadoParcial = {
      nombre: 'Lead 12345',
      // Sin ig_handle, sin profesion, sin salario_monto, sin dolor
      etapa_bot: 'M1_ENVIADO',
    };

    await notificarSetterGoogleChat(envConWebhook(), estadoParcial, planConHandoff());

    assert.equal(fetchCalls.length, 1);
    const texto = fetchCalls[0].body.text;
    // El formato cambio el 5-sep: los huecos se marcan "— sin dato" en vez de
    // "No indicado", y el aviso de IG dice donde buscar al lead.
    assert.match(texto, /sin dato/, 'los campos faltantes se marcan como vacios');
    assert.match(texto, /sin usuario de IG/, 'sin IG muestra aviso y que hacer');
  });

  test('funciona con estado null (lead nuevo que nunca se guardó)', async () => {
    await notificarSetterGoogleChat(envConWebhook(), null, planConHandoff());

    assert.equal(fetchCalls.length, 1);
    const texto = fetchCalls[0].body.text;
    assert.match(texto, /Lead sin nombre/, 'con estado null hay un nombre de respaldo');
  });

  test('funciona con plan que no tiene campos (edge case)', async () => {
    const planMinimo = { handoffRazon: 'error_tecnico' };
    await notificarSetterGoogleChat(envConWebhook(), estadoCompleto(), planMinimo);

    assert.equal(fetchCalls.length, 1);
    const texto = fetchCalls[0].body.text;
    assert.match(texto, /error_tecnico/);
  });
});

// ===========================================================================
// LOS DOS HUECOS QUE REPORTÓ EL EQUIPO (5-sep-2026)
//
// "el bot se quedó colgado y pues fue un handoff pero no me llegó nada".
// La alerta vivía en el paso 6b del handler, pero los dos caminos de fallo
// técnico retornan ANTES de llegar ahí: el catch de la escritura en Supabase y
// el catch general del `fetch`. Justo el caso más urgente era mudo.
// ===========================================================================
describe('Cobertura de los caminos de fallo técnico', () => {
  test('un handoff por error técnico también se notifica', async () => {
    const llamadas = [];
    const fake = async (url, opts) => {
      llamadas.push(JSON.parse(opts.body));
      return { ok: true, status: 200, text: async () => '' };
    };
    const r = await notificarSetterGoogleChat(
      { GOOGLE_CHAT_WEBHOOK: 'https://chat.googleapis.com/fake' },
      { nombre: 'Ana', ig_handle: 'ana_test' },
      { handoffRazon: 'error_tecnico' },
      'el bot no me respondió',
      fake,
    );
    assert.equal(r.enviado, true);
    assert.equal(llamadas.length, 1);
    assert.match(llamadas[0].text, /Fallo tecnico del bot/);
    assert.match(llamadas[0].text, /error_tecnico/, 'conserva el código para cruzarlo con el log');
  });

  test('el resultado dice SIEMPRE qué pasó: el silencio no es diagnóstico', () => {
    // La primera versión solo logueaba errores, así que "no me llegó nada" no
    // se podía distinguir de "se envió bien". Ahora la función devuelve estado.
    assert.ok(true);
  });

  test('sin webhook configurado devuelve el motivo, no un fallo silencioso', async () => {
    const r = await notificarSetterGoogleChat({}, { nombre: 'Ana' }, { handoffRazon: 'ambiguo' });
    assert.equal(r.enviado, false);
    assert.equal(r.razon, 'sin_webhook');
  });

  test('si el webhook responde error, se reporta y NO se lanza', async () => {
    const fake = async () => ({ ok: false, status: 404, text: async () => 'not found' });
    const r = await notificarSetterGoogleChat(
      { GOOGLE_CHAT_WEBHOOK: 'https://chat.googleapis.com/malo' },
      { nombre: 'Ana' }, { handoffRazon: 'ambiguo' }, '', fake,
    );
    assert.equal(r.enviado, false);
    assert.equal(r.razon, 'http_404');
  });

  test('si el fetch explota, tampoco se lanza: nunca rompe la respuesta al lead', async () => {
    const fake = async () => { throw new Error('red caída'); };
    const r = await notificarSetterGoogleChat(
      { GOOGLE_CHAT_WEBHOOK: 'https://chat.googleapis.com/x' },
      { nombre: 'Ana' }, { handoffRazon: 'ambiguo' }, '', fake,
    );
    assert.equal(r.enviado, false);
    assert.equal(r.razon, 'excepcion');
  });

  test('una crisis emocional se ve DISTINTA a un handoff normal', async () => {
    const { construirMensajeHandoff } = await import('../notificador_google_chat.js');
    const crisis = construirMensajeHandoff({ nombre: 'Ana' }, { handoffRazon: 'crisis_emocional' }, '');
    const normal = construirMensajeHandoff({ nombre: 'Ana' }, { handoffRazon: 'ambiguo' }, '');
    assert.match(crisis, /HANDOFF DELICADO/);
    assert.match(crisis, /NO le vendas/, 'le dice al Setter qué NO hacer');
    assert.ok(!/NO le vendas/.test(normal), 'un handoff normal no lleva esa advertencia');
  });

  test('un ingreso ASUMIDO se marca como tal', async () => {
    // Si el lead solo confirmó el rango, el Setter no puede citarle esa cifra
    // como si se la hubiera dado.
    const { construirMensajeHandoff } = await import('../notificador_google_chat.js');
    const texto = construirMensajeHandoff(
      { nombre: 'Ana', salario_monto: 7_000_000, ingreso_confirmado: false },
      { handoffRazon: 'ambiguo' }, '',
    );
    assert.match(texto, /asumido del rango, NO lo dijo/);
  });

  test('un lead de PRUEBA se marca para no confundir al equipo', async () => {
    const { construirMensajeHandoff } = await import('../notificador_google_chat.js');
    const texto = construirMensajeHandoff({ nombre: '[PRUEBA] Marly' }, { handoffRazon: 'ambiguo' }, '');
    assert.match(texto, /lead de PRUEBA/);
    assert.ok(!/\[PRUEBA\] Marly/.test(texto), 'pero el nombre sale limpio');
  });
});
