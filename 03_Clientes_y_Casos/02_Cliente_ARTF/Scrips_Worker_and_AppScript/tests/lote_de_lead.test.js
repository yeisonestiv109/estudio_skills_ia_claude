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
  CLAVE_MENSAJES, CLAVE_PRIMERO_EN,
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

  test('message_tag solo aparece si se pide', () => {
    assert.equal('message_tag' in cuerpoSendContent('123', 'x'), false);
    assert.equal(cuerpoSendContent('123', 'x', 'ACCOUNT_UPDATE').message_tag, 'ACCOUNT_UPDATE');
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

describe('limpiar: el lote no deja basura', () => {
  test('borra mensajes, marcas y alarma', async () => {
    const { lote, storage } = loteFalso();
    await lote.fetch(peticion({ manychat_subscriber_id: '123', last_text: 'Hola' }));
    await lote.limpiar();

    assert.equal(await storage.get(CLAVE_MENSAJES), undefined);
    assert.equal(await storage.get(CLAVE_PRIMERO_EN), undefined);
    assert.equal(await storage.get('payload_base'), undefined);
    assert.equal(storage._alarma(), null);
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
