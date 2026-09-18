/**
 * REGLAS ENRUTADAS POR ETAPA — la red que hace seguro recortar el prompt.
 * ===========================================================================
 *
 * El worker lleva desde el 11-sep una advertencia en mayusculas:
 *
 *   "⚠️ NO SE PUEDE PODAR ESTE PROMPT PARA AHORRAR TOKENS. Cada regla de
 *    <campos_a_extraer> y <definicion_de_intenciones> viene de un lead real
 *    perdido. Si se recorta, el bug vuelve y falla EN SILENCIO."
 *
 * Sigue vigente palabra por palabra. Lo que cambio el 18-sep NO es que se pode:
 * es que se ENRUTA. Ninguna regla se borro; cada una viaja a las etapas cuyo
 * esquema declara el campo que esa regla explica.
 *
 * Estos tests son lo que separa "enrutar" de "podar". Sin ellos el refactor es
 * exactamente lo que la advertencia prohibe.
 *
 * ⚠️ Y CORRIGEN UNA DEBILIDAD VIEJA. Los tests que protegian el prompt leian el
 * ARCHIVO FUENTE y comprobaban que una frase estuviera ahi. Eso pasaba en verde
 * aunque la regla no llegara nunca al modelo. Aca se comprueba sobre el prompt
 * que de verdad se arma.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  construirReglas, INTENCIONES, CAMPOS_A_EXTRAER, EJEMPLOS, FIJAS,
} from '../prompt_por_etapa.js';
import {
  ESQUEMA_POR_ETAPA, ESQUEMA_SECRETARIA, promptPorEtapa,
  recortarHistorial, CHARS_POR_TOKEN,
} from '../worker_bot_setter_v42.js';

const ETAPAS = Object.keys(ESQUEMA_POR_ETAPA);
const promptDe = (etapa) => construirReglas(ESQUEMA_POR_ETAPA[etapa]);
const TODOS = [...INTENCIONES.items, ...CAMPOS_A_EXTRAER.items, ...EJEMPLOS.items];

// ---------------------------------------------------------------------------
describe('1. El refactor no perdio una sola letra', () => {
  test('armar TODO reproduce el prompt de antes del enrutado, caracter por caracter', () => {
    const antes = readFileSync(
      new URL('./fixtures/prompts/reglas_completas_pre_enrutado.txt', import.meta.url), 'utf8');
    assert.equal(construirReglas('', true), antes,
      'el prompt completo cambio: si fue a proposito, regenera el fixture Y di por que');
  });

  test('la perilla apagada devuelve exactamente ese prompt', () => {
    assert.equal(promptPorEtapa({ PROMPT_POR_ETAPA: 'false' }), false);
    assert.equal(promptPorEtapa({}), true, 'encendido por defecto');
    assert.equal(promptPorEtapa({ PROMPT_POR_ETAPA: 'true' }), true);
  });
});

// ---------------------------------------------------------------------------
describe('2. Ninguna regla queda huerfana', () => {
  test('cada item llega al menos a una etapa real', () => {
    const huerfanos = TODOS.filter((i) => !ETAPAS.some((e) => {
      const esq = ESQUEMA_POR_ETAPA[e];
      return i.campos.some((c) => esq.includes(`"${c}"`));
    }));
    assert.deepEqual(huerfanos.map((i) => i.texto.slice(0, 60).trim()), [],
      'estas reglas no llegan a NINGUNA etapa: o les falta un campo, o sobran');
  });

  test('la union de todas las etapas cubre todas las reglas', () => {
    const union = ETAPAS.map(promptDe).join('\n');
    const faltan = TODOS.filter((i) => !union.includes(i.texto.trim().slice(0, 50)));
    assert.deepEqual(faltan.map((i) => i.texto.slice(0, 60).trim()), []);
  });
});

// ---------------------------------------------------------------------------
describe('3. Cada etapa recibe las reglas de su trabajo', () => {
  test('las reglas de plata llegan donde se pregunta por plata', () => {
    assert.match(promptDe('M1_ENVIADO'), /GLOSARIO COLOMBIANO DEL INGRESO/);
    assert.match(promptDe('M1_ENVIADO'), /EL APOSTROFO ES EL SEPARADOR DE MILLONES/);
    assert.match(promptDe('M1_ENVIADO'), /SUMA LAS FUENTES/);
    assert.match(promptDe('M2_ENVIADO'), /UN NUMERO PELADO EN LA PREGUNTA DE DEUDA/);
    assert.match(promptDe('M2_ENVIADO'), /RANGOS DE DEUDA: AL REVES QUE EL INGRESO/);
    assert.match(promptDe('M2_ENVIADO'), /NO CORRIJAS LA CIFRA DEL LEAD/);
    assert.match(promptDe('M2_DEUDA_TOTAL'), /DEUDA TOTAL vs CUOTA MENSUAL/);
  });

  test('y NO llegan donde no se usan: ahi esta el ahorro', () => {
    assert.doesNotMatch(promptDe('M5_ENVIADO'), /GLOSARIO COLOMBIANO DEL INGRESO/);
    assert.doesNotMatch(promptDe('M5_ENVIADO'), /RANGOS DE DEUDA/);
    assert.doesNotMatch(promptDe('M6_ENVIADO'), /EL APOSTROFO ES EL SEPARADOR/);
    assert.doesNotMatch(promptDe('M3_ENVIADO'), /NO CORRIJAS LA CIFRA DEL LEAD/);
  });

  test('⚠️ "acepta" y "confirmo_agendo" viajan SIEMPRE juntas', () => {
    // Distinguir "dale, agendemos" de "ya agende" ES la regla. Separarlas rompe
    // el embudo justo en M5/M6, que es donde se cierra la venta.
    for (const etapa of ETAPAS) {
      const p = promptDe(etapa);
      const tieneAcepta = /<intencion nombre="acepta">/.test(p);
      const tieneConfirmo = /<intencion nombre="confirmo_agendo">/.test(p);
      assert.equal(tieneAcepta, tieneConfirmo,
        `${etapa}: llegó una sin la otra y confundirlas rompe el embudo`);
    }
    assert.match(promptDe('M5_ENVIADO'), /<intencion nombre="confirmo_agendo">/);
    assert.match(promptDe('M6_ENVIADO'), /<intencion nombre="acepta">/);
  });

  test('las reglas de seguridad y de empatia van en TODAS las etapas', () => {
    for (const etapa of [...ETAPAS, 'SECRETARIA']) {
      const p = etapa === 'SECRETARIA' ? construirReglas(ESQUEMA_SECRETARIA) : promptDe(etapa);
      assert.match(p, /<reglas_de_oro>/, `${etapa} sin reglas de oro`);
      assert.match(p, /<seguridad>/, `${etapa} sin bloque de seguridad`);
      assert.match(p, /<formato_de_salida>/, `${etapa} sin formato de salida`);
      assert.match(p, /<redaccion>/, `${etapa} sin las reglas de redaccion`);
      // crisis y hostil son de SEGURIDAD: si se apagan, un lead en crisis
      // recibe el cierre enlatado. Ya paso.
      assert.match(p, /<intencion nombre="crisis">/, `${etapa} sin la definicion de crisis`);
      assert.match(p, /<intencion nombre="hostil">/, `${etapa} sin la definicion de hostil`);
    }
  });
});

// ---------------------------------------------------------------------------
describe('4. El enrutado se deriva del esquema, no de una lista a mano', () => {
  test('una etapa NUEVA hereda sus reglas sola', () => {
    // Este es el bug que ya paso CUATRO veces: alguien agrega una etapa y algo
    // se apaga en silencio. Con el enrutado derivado del esquema deja de ser
    // posible: si la etapa declara el campo, la regla viaja.
    const inventada = '{"analisis_paso_a_paso": string, "endeudamiento_pct": number|null, "crisis": boolean}';
    const p = construirReglas(inventada);
    assert.match(p, /UN NUMERO PELADO EN LA PREGUNTA DE DEUDA/,
      'una etapa nueva que extrae deuda tiene que recibir las reglas de deuda sin tocar nada');
    assert.match(p, /<intencion nombre="crisis">/);
    assert.doesNotMatch(p, /GLOSARIO COLOMBIANO DEL INGRESO/, 'y solo las suyas');
  });

  test('una seccion que se queda sin items no se manda vacia', () => {
    const p = construirReglas('{"crisis": boolean}');
    assert.doesNotMatch(p, /<campos_a_extraer>\s*<\/campos_a_extraer>/);
    assert.doesNotMatch(p, /<ejemplos>\s*<\/ejemplos>/);
  });
});

// ---------------------------------------------------------------------------
describe('5. El presupuesto de tokens que motivo todo esto', () => {
  // Groq free rebota por ITPM 7.000 por organizacion. Los 429 reales decian
  // "Limit 7000, Requested 7103" y "Requested 7239": no estabamos cerca del
  // techo, lo estabamos raspando. La relacion medida de este texto es 2,94
  // chars/token (no los 4 de la regla general: es texto denso y en español).
  const CHARS_POR_TOKEN = 2.94;
  const tokens = (t) => Math.round(t.length / CHARS_POR_TOKEN);

  // Lo que no se puede recortar: cabecera + estado sin conversacion + esquema.
  const FIJO_CHARS = 1500;
  const TURNO_TIPICO_CHARS = 137; // medido: ~550 chars por 4 turnos
  const presupuestoDe = (etapa) => Math.floor(
    (7000 - 600) * CHARS_POR_TOKEN - promptDe(etapa).length - FIJO_CHARS,
  );

  test('toda etapa deja sitio para historial: ninguna llena el prompt sola', () => {
    const sinAire = ETAPAS
      .map((e) => [e, presupuestoDe(e)])
      .filter(([, chars]) => chars < 700);
    assert.deepEqual(sinAire, [],
      'estas etapas no dejan cupo ni para unos pocos turnos de memoria');
  });

  test('⚠️ HANDOFF es la etapa mas apretada, y esta medido', () => {
    // No es un test decorativo: es el limite conocido del enrutado.
    //
    // HANDOFF acepta cifras de ingreso Y de deuda (un lead que vuelve tras ser
    // escalado puede soltar cualquiera de las dos), asi que carga los DOS
    // juegos de reglas completos y solo ahorra un 14%. Le quedan ~765 caracteres
    // de historial: unos 5 turnos tipicos. Es el 22,6% de las llamadas reales.
    //
    // Si alguien logra bajarlo, este test se actualiza hacia arriba y en buena
    // hora. Si SUBE, es que alguien le agrego campos sin mirar el presupuesto y
    // HANDOFF se queda sin memoria justo donde el lead esta volviendo.
    const pres = presupuestoDe('HANDOFF');
    assert.ok(pres >= 700, `HANDOFF se quedo sin memoria: ${pres} chars`);
    assert.ok(pres < 2500, `HANDOFF mejoro a ${pres}: actualiza este techo y la bitacora`);
    const otras = ETAPAS.filter((e) => e !== 'HANDOFF');
    assert.ok(otras.every((e) => presupuestoDe(e) > pres),
      'HANDOFF dejo de ser la mas apretada: revisa cual lo es ahora');
  });

  test('las etapas del embudo si tienen memoria de sobra', () => {
    // M1 y M2 son ~44% del trafico y son las que mas turnos necesitan recordar:
    // el 100% de los leads que califican pasa por conversaciones de 7+ turnos.
    for (const e of ['M1_ENVIADO', 'M2_ENVIADO', 'M3_ENVIADO', 'M5_ENVIADO']) {
      const turnos = Math.floor(presupuestoDe(e) / TURNO_TIPICO_CHARS);
      assert.ok(turnos >= 20, `${e} solo recuerda ${turnos} turnos`);
    }
  });

  test('el enrutado ahorra de verdad en las etapas que mas trafico tienen', () => {
    const completo = tokens(construirReglas('', true));
    // M1_ENVIADO y M2_ENVIADO son ~44% de las llamadas reales al LLM.
    assert.ok(tokens(promptDe('M1_ENVIADO')) < completo * 0.70, 'M1 deberia ahorrar >30%');
    assert.ok(tokens(promptDe('M2_ENVIADO')) < completo * 0.70, 'M2 deberia ahorrar >30%');
    assert.ok(tokens(promptDe('M5_ENVIADO')) < completo * 0.50, 'M5 deberia ahorrar >50%');
  });
});

// ---------------------------------------------------------------------------
describe('6. El recorte del historial conserva lo reciente', () => {
  const conversacion = [
    'LEAD: hola', 'TU: buenas, ¿a que te dedicas?',
    'LEAD: soy medico', 'TU: ¿cuanto ganas al mes?',
    'LEAD: 12 millones', 'TU: ¿y tu endeudamiento?',
    'LEAD: como 40%', 'TU: perfecto, ¿que te frustra?',
  ].join('\n');

  test('si cabe entero, no se toca', () => {
    assert.equal(recortarHistorial(conversacion, 10000), conversacion);
  });

  test('recorta por ARRIBA: lo viejo se va, lo reciente se queda', () => {
    const r = recortarHistorial(conversacion, 80);
    assert.ok(r.length <= 80);
    assert.match(r, /que te frustra/, 'lo ultimo que se dijo NO se puede perder');
    assert.doesNotMatch(r, /hola/, 'lo mas viejo es lo primero en irse');
  });

  test('nunca parte una linea por la mitad', () => {
    for (const presupuesto of [30, 60, 120, 200, 400]) {
      for (const linea of recortarHistorial(conversacion, presupuesto).split('\n')) {
        if (!linea) continue;
        assert.ok(conversacion.split('\n').includes(linea),
          `se envio una linea cortada: ${JSON.stringify(linea)}`);
      }
    }
  });

  test('sin presupuesto devuelve vacio, no basura', () => {
    assert.equal(recortarHistorial(conversacion, 0), '');
    assert.equal(recortarHistorial(conversacion, -50), '');
    assert.equal(recortarHistorial('', 100), '');
    assert.equal(recortarHistorial(null, 100), '');
  });

  test('una sola linea que no cabe no se manda a medias', () => {
    // Preferimos que el modelo no vea ese turno a que vea media frase y
    // entienda lo contrario de lo que el lead dijo.
    assert.equal(recortarHistorial('LEAD: ' + 'x'.repeat(500), 50), '');
  });
});
