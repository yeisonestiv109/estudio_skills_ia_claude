/**
 * Tests del VERIFICADOR — la compuerta del loop.
 *
 * Un verificador que nunca reprueba no es una compuerta, es decoracion. Por eso
 * la mitad de estos tests le pasan mensajes MALOS a proposito y exigen que los
 * repruebe.
 *
 * El test mas importante del archivo es el primero: reconstruye el bug real del
 * link (mandabamos link + 2 mensajes despues en el mismo turno) y exige que la
 * compuerta lo hubiera atrapado sola. Ese bug no lo detectaron 52 tests ni el
 * type-check -- solo aparecio leyendo la experiencia de produccion del equipo
 * de Javier.
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { verificarMensajes, esCopyAprobado } from '../verificador_cumplimiento.js';
import { PLANTILLAS as P, CALENDAR_LINK, render } from '../sop_v42_plantillas.js';
import { decidirTurno } from '../bot_router_v42.js';

const ctx = { nombre: 'Ana' };

describe('R1 — el link va SOLO y de ULTIMO (bug real de produccion)', () => {
  test('REGRESION: la version con el bug es REPROBADA por la compuerta', () => {
    // Esto es literalmente lo que enviabamos antes del arreglo.
    const conElBug = [
      `¡Perfecto! 🙌\n\nAcá te dejo el link para que elijas el día y hora que mejor te quede:\n${CALENDAR_LINK}`,
      render(P.M6_CONFIRMAME, 'Ana'),
      render(P.M7, 'Ana'),
    ];
    const r = verificarMensajes(conElBug, ctx);
    assert.equal(r.pasa, false, 'la compuerta TIENE que reprobar esto');
    assert.ok(r.fallas.some((f) => f.regla === 'R1_LINK_AISLADO'),
      'debe señalar exactamente la regla del link');
  });

  test('la version arreglada PASA', () => {
    const arreglado = [render(P.M6_SALUDO, 'Ana'), P.M6_LINK];
    const r = verificarMensajes(arreglado, ctx);
    assert.equal(r.pasa, true, JSON.stringify(r.fallas));
  });

  test('reprueba si el link lleva texto pegado en la misma burbuja', () => {
    const r = verificarMensajes([`Acá va: ${CALENDAR_LINK} cuéntame`], ctx);
    assert.equal(r.pasa, false);
    assert.ok(r.fallas.some((f) => f.regla === 'R1_LINK_AISLADO'));
  });

  test('reprueba si el link se manda dos veces', () => {
    const r = verificarMensajes([P.M6_LINK, P.M6_LINK], ctx);
    assert.ok(r.fallas.some((f) => f.regla === 'R1_LINK_AISLADO'));
  });
});

describe('R2/R4 — voz colombiana (reglas no negociables de Javier)', () => {
  test('reprueba voseo, que ya rompio en produccion el 21-may-2026', () => {
    for (const malo of [
      '¿Sabés qué pasa? Te entiendo.',
      'Lo que tenés que hacer es agendar.',
      '¿Querés resolver esto ya?',
    ]) {
      const r = verificarMensajes([malo], ctx);
      assert.ok(r.fallas.some((f) => f.regla === 'R2_VOSEO'), malo);
    }
  });

  test('reprueba lexico de otras regiones', () => {
    assert.ok(verificarMensajes(['Órale, qué chido'], ctx).fallas.some((f) => f.regla === 'R4_LEXICO_REGIONAL'));
    assert.ok(verificarMensajes(['Qué guay, tío'], ctx).fallas.some((f) => f.regla === 'R4_LEXICO_REGIONAL'));
  });
});

describe('R3 — palabras prohibidas', () => {
  test('reprueba las que refuerzan "ahorrar = sufrir"', () => {
    for (const malo of [
      'Es cuestión de sacrificio.',
      'Te propongo una dieta financiera.',
      'Hay que recortar gastos.',
      'Es más barato de lo que crees.',
    ]) {
      const r = verificarMensajes([malo], ctx);
      assert.ok(r.fallas.some((f) => f.regla === 'R3_PALABRA_PROHIBIDA'), malo);
    }
  });
});

describe('R5/R6 — identidad', () => {
  test('reprueba hablar de Andres en tercera persona', () => {
    const r = verificarMensajes(['Andrés te espera en la llamada.'], ctx);
    assert.ok(r.fallas.some((f) => f.regla === 'R5_TERCERA_PERSONA'));
  });

  test('reprueba revelar que es una IA', () => {
    for (const malo of ['Soy un bot que responde por él.', 'Como IA no puedo darte eso.']) {
      assert.ok(verificarMensajes([malo], ctx).fallas.some((f) => f.regla === 'R6_REVELA_IA'), malo);
    }
  });
});

describe('R8 — todo lo que ve el lead sale de la biblioteca', () => {
  test('reprueba copy inventado aunque suene bien', () => {
    const r = verificarMensajes(['Hola! Cuéntame un poco más sobre tu situación financiera.'], ctx);
    assert.equal(r.pasa, false);
    assert.ok(r.fallas.some((f) => f.regla === 'R8_COPY_NO_APROBADO'));
  });

  test('acepta una plantilla con la empatia antepuesta', () => {
    const conEmpatia = `Te entiendo, esa sensación desgasta.\n\n${render(P.M3, 'Ana')}`;
    assert.equal(esCopyAprobado(conEmpatia, 'Ana'), true);
    assert.equal(verificarMensajes([conEmpatia], ctx).pasa, true);
  });

  test('las plantillas del SOP que citan cifras NO se confunden con mencionar precio', () => {
    // La Objecion 7 dice "$7M y $15M+" a proposito, es copy aprobado.
    const r = verificarMensajes([render(P.OBJ_7, 'Ana')], ctx);
    assert.equal(r.pasa, true, JSON.stringify(r.fallas));
  });

  test('reprueba un mensaje vacio', () => {
    assert.ok(verificarMensajes([''], ctx).fallas.some((f) => f.regla === 'R0_VACIO'));
  });
});

// ===========================================================================
// La compuerta aplicada a la salida REAL del router, no a textos de laboratorio
// ===========================================================================
describe('El router completo pasa la compuerta en cada etapa', () => {
  const estadoEn = (etapa, extra = {}) => ({
    estado_codigo: 'contactado', es_terminal: false, etapa_bot: etapa,
    nombre: 'Ana', salario_monto: 12_000_000, endeudamiento_pct: null,
    objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
    ...extra,
  });

  const casos = [
    ['lead nuevo', null, {}, 'CONTROL'],
    ['M1 -> M2', estadoEn('M1_ENVIADO'), { ingreso_cop: 12_000_000, profesion: 'Ingeniera' }, ''],
    ['M1 ambiguo', estadoEn('M1_ENVIADO'), { ingreso_cop: null, profesion: 'Abogada' }, ''],
    ['M1 descalifica', estadoEn('M1_ENVIADO'), { ingreso_cop: 2_000_000 }, 'gano 2 millones'],
    ['M2 -> M3', estadoEn('M2_ENVIADO'), { endeudamiento_pct: 30 }, ''],
    ['M2 borderline', estadoEn('M2_ENVIADO'), { endeudamiento_pct: 65 }, ''],
    ['M2 descalifica', estadoEn('M2_ENVIADO'), { endeudamiento_pct: 90 }, ''],
    ['M3 -> M4', estadoEn('M3_ENVIADO'), { dolor: 'B' }, ''],
    ['M3 reconducir', estadoEn('M3_ENVIADO'), { dolor: 'D', dolor_financiero: false }, ''],
    ['M4 califica', estadoEn('M4_ENVIADO'), { urgencia: 'ahora' }, ''],
    ['M4 sin urgencia', estadoEn('M4_ENVIADO'), { urgencia: 'algun_dia' }, ''],
    ['M4 objecion 9', estadoEn('M4_ENVIADO'), { urgencia: 'pregunta_por_que' }, ''],
    ['M5 acepta (LINK)', estadoEn('M5_ENVIADO'), { acepta: true }, ''],
    ['M6 -> M7', estadoEn('M6_ENVIADO'), {}, 'listo'],
    ['M7 acompañado', estadoEn('M7_ENVIADO'), { acompanado: true }, ''],
    ['M7 solo', estadoEn('M7_ENVIADO'), { acompanado: false }, ''],
    ['M7 confirma', estadoEn('M7_ENVIADO'), { confirmo_agendo: true }, ''],
    ['blindaje', estadoEn('CIERRE_PRECALL'), { agradece: true }, 'gracias'],
    ['blindaje firme', estadoEn('BLINDAJE_ENVIADO'), { compromiso: 'firme' }, ''],
    ['blindaje dudoso (LINK)', estadoEn('BLINDAJE_ENVIADO'), { compromiso: 'dudoso' }, ''],
    ['retorno lead', estadoEn('DESCALIFICADO', { estado_codigo: 'descalificado' }), { ingreso_cop: 22_000_000 }, ''],
  ];

  for (const [nombre, estado, clasif, texto] of casos) {
    test(`"${nombre}" produce mensajes que pasan la compuerta`, () => {
      const plan = decidirTurno(estado, clasif, texto);
      const r = verificarMensajes(plan.mensajes, { nombre: 'Ana' });
      assert.equal(r.pasa, true,
        `FALLAS en "${nombre}":\n${r.fallas.map((f) => `[${f.regla}] ${f.detalle}`).join('\n')}`);
    });
  }

  for (const num of [1, 2, 3, 4, 5, 6, 7, 8, 9]) {
    test(`la Objecion ${num} pasa la compuerta`, () => {
      const plan = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: num, objecion_conocida: true });
      const r = verificarMensajes(plan.mensajes, { nombre: 'Ana' });
      assert.equal(r.pasa, true,
        `FALLAS en objecion ${num}:\n${r.fallas.map((f) => `[${f.regla}] ${f.detalle}`).join('\n')}`);
    });
  }
});
