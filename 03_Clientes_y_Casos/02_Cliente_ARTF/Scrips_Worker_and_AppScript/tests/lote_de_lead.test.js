/**
 * Tests de la FASE 2B — agrupamiento de burbujas (14-sep-2026).
 *
 * Lo que NO se prueba aqui: `alarm()` de punta a punta, porque llama al
 * pipeline completo (Groq y Supabase reales). Eso lo cubre el smoke y la prueba
 * en vivo. Aqui se prueba lo que puede romperse en silencio y decidir mal un
 * turno: como se juntan las burbujas, cuando vence la ventana, el cuerpo exacto
 * que se le manda a ManyChat y el orden en que salen.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
  LoteDeLead, juntarBurbujas, cuerpoSendContent, enviarBurbujas, debeProcesarYa,
  enteroDeEnv, VENTANA_MS_POR_DEFECTO, TOPE_MS_POR_DEFECTO, MAX_BURBUJAS_POR_LOTE,
  CLAVE_MENSAJES, CLAVE_PRIMERO_EN, CLAVE_RESULTADO,
  esFalloPermanente, esVentanaVencida, FalloDeEnvio,
} from '../lote_de_lead.js';

/** Storage en memoria con la misma forma que el de un Durable Object. */
function storageFalso() {
  const datos = new Map();
  let alarma = null;
  return {
    async get(k) { return datos.get(k); },
    async put(k, v) { datos.set(k, v); },
    async delete(k) { return datos.delete(k); },
    async setAlarm(t) { alarma = t; },
    async getAlarm() { return alarma; },
    async deleteAlarm() { alarma = null; },
    _alarma: () => alarma,
    _datos: datos,
  };
}

function loteFalso(env = {}) {
  const storage = storageFalso();
  const lote = new LoteDeLead({ storage }, env);
  return { lote, storage };
}

function peticion(payload) {
  return new Request('https://lote.interno/encolar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

describe('juntarBurbujas: tres mensajes son UN turno', () => {
  test('se unen en orden de llegada, con salto de linea', () => {
    const texto = juntarBurbujas([
      { texto: 'Hola' }, { texto: 'soy ingeniero' }, { texto: 'gano 12 millones' },
    ]);
    assert.equal(texto, 'Hola\nsoy ingeniero\ngano 12 millones');
  });

  test('no reordena: el orden en que lo escribio es el orden en que lo penso', () => {
    const texto = juntarBurbujas([{ texto: 'gano 12 millones' }, { texto: 'soy ingeniero' }]);
    assert.equal(texto, 'gano 12 millones\nsoy ingeniero');
  });

  test('las vacias se descartan (un sticker llega con last_text vacio)', () => {
    assert.equal(juntarBurbujas([{ texto: 'Hola' }, { texto: '   ' }, { texto: 'que tal' }]), 'Hola\nque tal');
    assert.equal(juntarBurbujas([{ texto: '' }, { texto: null }]), '');
  });

  test('una repetida CONSECUTIVA se colapsa: casi siempre es doble envio', () => {
    assert.equal(juntarBurbujas([{ texto: 'Si' }, { texto: 'Si' }]), 'Si');
  });

  test('pero repetida NO consecutiva se conserva: puede ser una respuesta real', () => {
    assert.equal(juntarBurbujas([{ texto: 'Si' }, { texto: 'como asi?' }, { texto: 'Si' }]), 'Si\ncomo asi?\nSi');
  });

  test('lista vacia o basura no revienta', () => {
    assert.equal(juntarBurbujas([]), '');
    assert.equal(juntarBurbujas(null), '');
  });
});

describe('debeProcesarYa: la ventana no se puede renovar para siempre', () => {
  const ahora = 1_000_000;

  test('con pocas burbujas y dentro del tope, se sigue esperando', () => {
    assert.equal(debeProcesarYa([{}, {}], ahora - 3000, ahora, TOPE_MS_POR_DEFECTO, MAX_BURBUJAS_POR_LOTE), false);
  });

  test('⚠️ pasado el tope desde la PRIMERA burbuja, se procesa aunque siga escribiendo', () => {
    // Sin esto, un lead que escribe una palabra cada 5 s no recibe respuesta
    // NUNCA: cada burbuja correria la alarma hacia adelante.
    assert.equal(debeProcesarYa([{}, {}], ahora - 26_000, ahora, TOPE_MS_POR_DEFECTO, MAX_BURBUJAS_POR_LOTE), true);
  });

  test('demasiadas burbujas tambien fuerzan el proceso', () => {
    const muchas = Array.from({ length: MAX_BURBUJAS_POR_LOTE }, () => ({}));
    assert.equal(debeProcesarYa(muchas, ahora, ahora, TOPE_MS_POR_DEFECTO, MAX_BURBUJAS_POR_LOTE), true);
  });

  test('sin primera marca de tiempo no se fuerza por tope', () => {
    assert.equal(debeProcesarYa([{}], null, ahora, TOPE_MS_POR_DEFECTO, MAX_BURBUJAS_POR_LOTE), false);
  });
});

describe('enteroDeEnv: la configuracion mala no tumba el lote', () => {
  test('lee el valor cuando es valido', () => {
    assert.equal(enteroDeEnv({ LOTE_VENTANA_MS: '8000' }, 'LOTE_VENTANA_MS', 7000), 8000);
  });

  test('cae al default con basura, vacio, cero o negativo', () => {
    for (const v of ['abc', '', '0', '-5', null, undefined]) {
      assert.equal(enteroDeEnv({ LOTE_VENTANA_MS: v }, 'LOTE_VENTANA_MS', 7000), 7000, `valor: ${v}`);
    }
    assert.equal(enteroDeEnv(undefined, 'LOTE_VENTANA_MS', 7000), 7000);
  });
});

describe('encolar: cada burbuja corre la alarma hacia adelante (debounce)', () => {
  test('la primera burbuja programa la alarma a una ventana', async () => {
    const { lote, storage } = loteFalso({ LOTE_VENTANA_MS: '7000' });
    const antes = Date.now();
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'Hola' }));

    const alarma = storage._alarma();
    assert.ok(alarma >= antes + 7000, 'la alarma queda una ventana por delante');
    assert.equal((await storage.get(CLAVE_MENSAJES)).length, 1);
  });

  test('la segunda burbuja REPROGRAMA: se cuenta desde la ultima, no desde la primera', async () => {
    const { lote, storage } = loteFalso({ LOTE_VENTANA_MS: '7000' });
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'Hola' }));
    const primeraAlarma = storage._alarma();

    await new Promise((r) => setTimeout(r, 25));
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'soy ingeniero' }));

    assert.ok(storage._alarma() > primeraAlarma, 'la alarma se corrio hacia adelante');
    assert.equal((await storage.get(CLAVE_MENSAJES)).length, 2);
  });

  test('el payload base es el de la PRIMERA burbuja (trae nombre y handle)', async () => {
    const { lote, storage } = loteFalso();
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'Hola', first_name: 'Ana' }));
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'que tal' }));

    const base = await storage.get('payload_base');
    assert.equal(base.first_name, 'Ana', 'un campo que solo viene a veces no se pierde');
  });

  test('⚠️ pasado el tope, la alarma NO se sigue corriendo', async () => {
    const { lote, storage } = loteFalso({ LOTE_TOPE_MS: '1', LOTE_VENTANA_MS: '7000' });
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'uno' }));
    await new Promise((r) => setTimeout(r, 5));
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'dos' }));

    assert.ok(storage._alarma() <= Date.now(), 'la alarma quedo para ya, no una ventana mas adelante');
  });

  test('la marca de la primera burbuja no se pisa con las siguientes', async () => {
    const { lote, storage } = loteFalso();
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'uno' }));
    const primero = await storage.get(CLAVE_PRIMERO_EN);
    await new Promise((r) => setTimeout(r, 15));
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'dos' }));

    assert.equal(await storage.get(CLAVE_PRIMERO_EN), primero);
  });
});

describe('cuerpoSendContent: el contrato con la API v2 de ManyChat', () => {
  test('forma exacta que espera /fb/sending/sendContent', () => {
    assert.deepEqual(cuerpoSendContent('123', 'Hola Ana'), {
      subscriber_id: '123',
      data: { version: 'v2', content: { messages: [{ type: 'text', text: 'Hola Ana' }] } },
    });
  });

  test('⚠️ NUNCA lleva message_tag, y la firma ya no lo acepta', () => {
    // Verificado contra la API real el 14-sep-2026: Meta deprecio los message
    // tags y ManyChat responde "Message tags are no longer supported for
    // Facebook Messenger". Si alguien "arregla" el envio añadiendolo, rompe
    // TODOS los mensajes. Por eso el parametro se retiro de la firma.
    assert.equal('message_tag' in cuerpoSendContent('123', 'x'), false);
    assert.equal('message_tag' in cuerpoSendContent('123', 'x', 'ACCOUNT_UPDATE'), false,
      'aunque alguien pase un tercer argumento, no debe llegar al cuerpo');
    assert.equal(cuerpoSendContent.length, 2, 'la firma solo acepta subscriberId y texto');
  });

  test('⚠️ UNA burbuja por llamada: R1_LINK_AISLADO', () => {
    // El link NUNCA puede viajar pegado a otro texto: Instagram los concatena y
    // queda invalido ("Dynamic Link Not Found"), bug confirmado en produccion.
    // Una burbuja por cuerpo hace ese error imposible por construccion.
    const cuerpo = cuerpoSendContent('123', 'https://calendar.app.google/xxx');
    assert.equal(cuerpo.data.content.messages.length, 1);
  });
});

describe('enviarBurbujas: en orden, y si una falla no se siguen mandando', () => {
  test('sale una llamada por burbuja, en orden', async () => {
    const vistas = [];
    const fetchFalso = async (url, opts) => {
      vistas.push(JSON.parse(opts.body).data.content.messages[0].text);
      return { ok: true, status: 200, text: async () => '' };
    };
    const n = await enviarBurbujas('token', '123', ['uno', 'dos', 'tres'], fetchFalso);

    assert.equal(n, 3);
    assert.deepEqual(vistas, ['uno', 'dos', 'tres'], 'el orden del guion importa: el link va de ultimo');
  });

  test('va al endpoint correcto y con el token', async () => {
    let url; let cabeceras;
    const fetchFalso = async (u, opts) => { url = u; cabeceras = opts.headers; return { ok: true, text: async () => '' }; };
    await enviarBurbujas('tok123', '123', ['hola'], fetchFalso);

    assert.equal(url, 'https://api.manychat.com/fb/sending/sendContent');
    assert.equal(cabeceras.Authorization, 'Bearer tok123');
  });

  test('⚠️ si la segunda falla, la tercera NO se manda', async () => {
    // Reenviar las siguientes dejaria al lead una conversacion con huecos, que
    // es peor que una respuesta incompleta que el reintento puede completar.
    const vistas = [];
    const fetchFalso = async (url, opts) => {
      const t = JSON.parse(opts.body).data.content.messages[0].text;
      vistas.push(t);
      if (t === 'dos') return { ok: false, status: 429, text: async () => 'rate limited' };
      return { ok: true, text: async () => '' };
    };

    await assert.rejects(
      () => enviarBurbujas('token', '123', ['uno', 'dos', 'tres'], fetchFalso),
      /sendContent 429/,
    );
    assert.deepEqual(vistas, ['uno', 'dos'], 'la tercera nunca se intento');
  });

  test('el error dice en que burbuja se quedo, para poder diagnosticar', async () => {
    const fetchFalso = async () => ({ ok: false, status: 500, text: async () => 'boom' });
    await assert.rejects(() => enviarBurbujas('token', '123', ['uno'], fetchFalso), /burbuja 1\/1/);
  });
});

describe('limpiar: cierra el turno sin tragarse el siguiente', () => {
  test('sin entrada pendiente, borra todo y apaga la alarma', async () => {
    const { lote, storage } = loteFalso();
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'Hola' }));
    await storage.delete(CLAVE_MENSAJES); // el turno ya se proceso
    await lote.limpiar();

    assert.equal(await storage.get(CLAVE_PRIMERO_EN), undefined);
    assert.equal(await storage.get('payload_base'), undefined);
    assert.equal(storage._alarma(), null);
  });

  test('⚠️ si llego una burbuja MIENTRAS se enviaba, NO se borra: es el turno siguiente', async () => {
    // El lead escribe mientras el bot le responde. Es lo normal, no el caso
    // raro. Borrar esa burbuja seria tragarse un mensaje sin dejar rastro.
    const { lote, storage } = loteFalso({ LOTE_VENTANA_MS: '7000' });
    await storage.put(CLAVE_RESULTADO, { subId: '123', burbujas: ['ya enviada'], enviadas: 1 });
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'ah espera' }));

    await lote.limpiar();

    assert.equal((await storage.get(CLAVE_MENSAJES)).length, 1, 'la burbuja nueva sigue ahi');
    assert.equal(await storage.get(CLAVE_RESULTADO), undefined, 'el turno enviado si se cerro');
    assert.ok(storage._alarma() > Date.now(), 'y queda alarma para procesarla');
  });

  test('un lote de solo stickers no deja una alarma girando para siempre', async () => {
    const { lote, storage } = loteFalso();
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: '   ' }));
    await lote.alarm();

    assert.equal(await storage.get(CLAVE_MENSAJES), undefined);
    assert.equal(storage._alarma(), null, 'sin texto que procesar, la alarma se apaga');
  });
});

describe('alarm: sin nada que procesar no hace nada', () => {
  test('lote vacio: no revienta ni llama al pipeline', async () => {
    const { lote } = loteFalso();
    await lote.alarm(); // si intentara importar el pipeline o llamar a ManyChat, fallaria
  });

  test('solo stickers (texto vacio): limpia y sale sin responder', async () => {
    const { lote, storage } = loteFalso();
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: '   ' }));
    await lote.alarm();

    assert.equal(await storage.get(CLAVE_MENSAJES), undefined, 'el lote quedo limpio');
  });
});

describe('la ventana por defecto respeta la decision del fundador', () => {
  test('7 s, dentro del rango 6-8 s que se pidio', () => {
    assert.ok(VENTANA_MS_POR_DEFECTO >= 6000 && VENTANA_MS_POR_DEFECTO <= 8000,
      `la ventana por defecto (${VENTANA_MS_POR_DEFECTO} ms) salio del rango acordado`);
  });

  test('el tope es varias veces la ventana: si no, el debounce no serviria', () => {
    assert.ok(TOPE_MS_POR_DEFECTO > VENTANA_MS_POR_DEFECTO * 2);
  });
});

// ===========================================================================
// INCIDENTE DEL 14-SEP-2026 — el bucle de reprocesamiento
//
// Que paso: la primera version dejaba las burbujas de ENTRADA en el storage y
// relanzaba la excepcion cuando fallaba el envio, contando con el reintento de
// alarma de Cloudflare. Pero la alarma se reejecuta DESDE EL PRINCIPIO: cada
// reintento volvia a llamar al LLM y a escribir el turno en la base. En
// produccion, el lead Vasco_ana tuvo una apertura correcta a las 16:04:05 y
// CINCO reprocesos detras ("Repitio la palabra clave estando en M1_ENVIADO").
//
// La idempotencia del Worker no lo atajo porque vive en `caches.default`, y la
// Cache API no retiene entre invocaciones de una alarma de Durable Object.
// ===========================================================================

describe('esFalloPermanente: reintentar lo irreparable es un bucle', () => {
  test('transitorios: 429 y 5xx SI se reintentan', () => {
    assert.equal(esFalloPermanente(429), false);
    assert.equal(esFalloPermanente(500), false);
    assert.equal(esFalloPermanente(503), false);
  });

  test('permanentes: el resto de 4xx NO se reintenta nunca', () => {
    assert.equal(esFalloPermanente(400), true);
    assert.equal(esFalloPermanente(401), true);
    assert.equal(esFalloPermanente(404), true);
  });
});

describe('esVentanaVencida: el 3011 de Meta se reconoce por lo que es', () => {
  const cuerpo3011 = '{"status":"error","message":"Subscriber last interaction was over 266h ago (more than 24 hours ago)","code":3011}';

  test('detecta el codigo 3011', () => {
    assert.equal(esVentanaVencida(400, cuerpo3011), true);
  });

  test('detecta tambien por el texto, si el codigo cambiara de forma', () => {
    assert.equal(esVentanaVencida(400, 'last interaction was more than 24 hours ago'), true);
  });

  test('un 400 cualquiera NO es ventana vencida', () => {
    assert.equal(esVentanaVencida(400, '{"message":"Subscriber does not exist"}'), false);
  });

  test('es permanente: no hay message_tag que lo salve, Meta los deprecó', () => {
    assert.equal(esFalloPermanente(400, cuerpo3011), true);
  });
});

describe('enviarBurbujas: un reintento NO le duplica mensajes al lead', () => {
  test('`desde` reanuda donde se quedo', async () => {
    const vistas = [];
    const fetchFalso = async (url, opts) => {
      vistas.push(JSON.parse(opts.body).data.content.messages[0].text);
      return { ok: true, text: async () => '' };
    };
    const total = await enviarBurbujas('tok', '123', ['uno', 'dos', 'tres'], fetchFalso, 2);

    assert.deepEqual(vistas, ['tres'], 'las dos primeras ya habian salido: no se repiten');
    assert.equal(total, 3, 'devuelve el total acumulado, no lo enviado en esta llamada');
  });

  test('el error dice CUANTAS salieron antes de fallar', async () => {
    const fetchFalso = async (url, opts) => {
      const t = JSON.parse(opts.body).data.content.messages[0].text;
      return t === 'tres' ? { ok: false, status: 500, text: async () => 'boom' } : { ok: true, text: async () => '' };
    };
    const err = await enviarBurbujas('tok', '123', ['uno', 'dos', 'tres'], fetchFalso).catch((e) => e);

    assert.ok(err instanceof FalloDeEnvio);
    assert.equal(err.indice, 2, 'dos salieron; el reintento debe empezar por la tercera');
    assert.equal(err.permanente, false, '500 es transitorio');
  });
});

describe('las dos fases: procesar una vez, enviar las que haga falta', () => {
  test('⚠️ con un resultado pendiente, alarm() NO vuelve a procesar', async () => {
    // Es EL test del incidente: si esto se rompe, vuelve el gasto de tokens.
    const { lote, storage } = loteFalso({ MANYCHAT_API_TOKEN: 'tok' });
    let envios = 0;
    lote.enviarPendiente = async () => { envios++; };

    await storage.put(CLAVE_RESULTADO, { subId: '123', burbujas: ['hola'], enviadas: 0 });
    // Hay burbujas de entrada ademas del pendiente: no deben tocarse.
    await storage.put(CLAVE_MENSAJES, [{ texto: 'hola' }]);
    await lote.alarm();

    assert.equal(envios, 1, 'se fue directo a enviar');
    assert.deepEqual(await storage.get(CLAVE_MENSAJES), [{ texto: 'hola' }], 'no consumio la entrada');
  });

  test('un fallo permanente no relanza: se rinde y avisa', async () => {
    const { lote, storage } = loteFalso({ MANYCHAT_API_TOKEN: 'tok' });
    let rendido = null;
    lote.rendirse = async (res, err, enviadas) => { rendido = { err, enviadas }; await lote.limpiar(); };

    const resultado = { subId: '123', burbujas: ['a', 'b'], enviadas: 0 };
    await storage.put(CLAVE_RESULTADO, resultado);
    const original = globalThis.fetch;
    globalThis.fetch = async () => ({ ok: false, status: 400, text: async () => '{"code":3011}' });
    try {
      await lote.enviarPendiente(resultado); // NO debe lanzar
    } finally { globalThis.fetch = original; }

    assert.ok(rendido, 'se rindio en vez de reintentar');
    assert.equal(rendido.err.ventanaVencida, true);
  });

  test('un fallo transitorio SI relanza, para que Cloudflare reintente', async () => {
    const { lote, storage } = loteFalso({ MANYCHAT_API_TOKEN: 'tok', LOTE_MAX_REINTENTOS: '3' });
    const resultado = { subId: '123', burbujas: ['a', 'b'], enviadas: 0 };
    await storage.put(CLAVE_RESULTADO, resultado);
    const original = globalThis.fetch;
    globalThis.fetch = async () => ({ ok: false, status: 503, text: async () => 'upstream' });
    try {
      await assert.rejects(() => lote.enviarPendiente(resultado));
    } finally { globalThis.fetch = original; }

    const guardado = await storage.get(CLAVE_RESULTADO);
    assert.equal(guardado.enviadas, 0, 'guarda cuantas iban para no repetirlas');
  });

  test('agotados los reintentos, se rinde en vez de seguir para siempre', async () => {
    const { lote, storage } = loteFalso({ MANYCHAT_API_TOKEN: 'tok', LOTE_MAX_REINTENTOS: '1' });
    let rendido = false;
    lote.rendirse = async () => { rendido = true; await lote.limpiar(); };

    const resultado = { subId: '123', burbujas: ['a'], enviadas: 0 };
    await storage.put(CLAVE_RESULTADO, resultado);
    const original = globalThis.fetch;
    globalThis.fetch = async () => ({ ok: false, status: 503, text: async () => 'x' });
    try { await lote.enviarPendiente(resultado); } finally { globalThis.fetch = original; }

    assert.equal(rendido, true);
  });

  test('tras enviar bien, no queda resultado pendiente', async () => {
    const { lote, storage } = loteFalso({ MANYCHAT_API_TOKEN: 'tok' });
    const resultado = { subId: '123', burbujas: ['a'], enviadas: 0 };
    await storage.put(CLAVE_RESULTADO, resultado);
    const original = globalThis.fetch;
    globalThis.fetch = async () => ({ ok: true, text: async () => '' });
    try { await lote.enviarPendiente(resultado); } finally { globalThis.fetch = original; }

    assert.equal(await storage.get(CLAVE_RESULTADO), undefined);
  });
});
