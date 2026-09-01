/**
 * Tests del router del bot ARTF — SOP V4.2
 *
 * Correr:  cd Scrips_Worker_and_AppScript && node --test tests/
 *
 * Disciplina de este proyecto (ver CLAUDE.md): un linter en verde no prueba
 * nada. Estos tests apuntan a los casos que ROMPIERON de verdad en produccion,
 * no a cobertura decorativa:
 *  - El caso real de la lead de $22M descartada por leer "minimo integral"
 *    como "salario minimo" (motivo la regla V4.1).
 *  - Que el bot NUNCA pueda descalificar sobre un ingreso ambiguo.
 *  - Que el link del calendario salga aislado en su propia burbuja.
 *  - Que las reglas de escalamiento por objeciones se disparen exacto.
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
  parseIngresoCOP, evaluarIngreso, topeEndeudamiento, evaluarEndeudamiento,
  decidirSiResponder, decidirTurno,
  detectarVarianteM1, detectarConfirmacionAgenda, detectarAcompanante,
  detectarUrgencia, detectarDolorLetra, detectarHostilidad, detectarEndeudamientoPct,
} from '../bot_router_v42.js';
import { CALENDAR_LINK, UMBRALES } from '../sop_v42_plantillas.js';

// Helper: estado como lo devuelve fn_bot_get_estado
const estadoEn = (etapa, extra = {}) => ({
  estado_codigo: 'contactado', es_terminal: false, etapa_bot: etapa,
  nombre: 'Ana', salario_monto: null, endeudamiento_pct: null,
  objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
  ...extra,
});

// ===========================================================================
describe('parseIngresoCOP — glosario colombiano (★ V4.1)', () => {
  test('EL BUG REAL: "minimo integral" NUNCA se lee como salario minimo', () => {
    const r = parseIngresoCOP('gano el minimo integral');
    assert.equal(r.glosario, 'salario_integral');
    assert.equal(r.ambiguo, true, 'debe pedir la cifra, no asumir');
    // Lo critico: jamas puede terminar descalificando.
    assert.notEqual(evaluarIngreso(r.monto), 'descalifica');
  });

  test('"salario integral" tambien, con tilde y variantes', () => {
    for (const t of ['salario integral', 'tengo un contrato integral', 'gano integral']) {
      assert.equal(parseIngresoCOP(t).glosario, 'salario_integral', t);
    }
  });

  test('"el minimo" SIN integral si es el salario minimo', () => {
    const r = parseIngresoCOP('gano el minimo');
    assert.equal(r.monto, UMBRALES.SMLV_2026);
    assert.equal(evaluarIngreso(r.monto), 'descalifica');
  });

  test('SMLV se multiplica', () => {
    assert.equal(parseIngresoCOP('gano 3 smlv').monto, 3 * UMBRALES.SMLV_2026);
    assert.equal(parseIngresoCOP('como 2 salarios minimos').monto, 2 * UMBRALES.SMLV_2026);
  });

  test('millones en varias formas', () => {
    assert.equal(parseIngresoCOP('gano 12 millones').monto, 12_000_000);
    assert.equal(parseIngresoCOP('12 millones y medio').monto, 12_500_000);
    assert.equal(parseIngresoCOP('unos 8 millones al mes').monto, 8_000_000);
  });

  test('cifra escrita completa con separadores', () => {
    assert.equal(parseIngresoCOP('gano 12.000.000').monto, 12_000_000);
    assert.equal(parseIngresoCOP("8'500.000").monto, 8_500_000);
    assert.equal(parseIngresoCOP('9500000').monto, 9_500_000);
  });

  test('"palos" = millones', () => {
    assert.equal(parseIngresoCOP('gano como 8 palos').monto, 8_000_000);
    assert.equal(parseIngresoCOP('un palo').monto, 1_000_000);
  });

  test('"por quincena" multiplica por 2', () => {
    assert.equal(parseIngresoCOP('5 millones por quincena').monto, 10_000_000);
  });

  test('ingreso variable sin cifra queda ambiguo (no se adivina)', () => {
    for (const t of ['basico mas comisiones', 'es variable', 'depende del mes']) {
      assert.equal(parseIngresoCOP(t).ambiguo, true, t);
    }
  });

  test('numero suelto grande y sin unidad NO se asume', () => {
    assert.equal(parseIngresoCOP('gano 800').ambiguo, true);
  });

  test('dolares se convierten y quedan marcados como aproximados', () => {
    const r = parseIngresoCOP('gano 3000 usd');
    assert.equal(r.aproximado, true);
    assert.equal(evaluarIngreso(r.monto), 'califica');
  });
});

// ===========================================================================
describe('Filtros del SOP V4.2', () => {
  test('Filtro 1: umbral $7M', () => {
    assert.equal(evaluarIngreso(7_000_000), 'califica');
    assert.equal(evaluarIngreso(6_999_999), 'descalifica');
    assert.equal(evaluarIngreso(null), 'ambiguo');
  });

  test('Filtro 2: el tope depende del ingreso (50% / 60%)', () => {
    assert.equal(topeEndeudamiento(7_000_000), 50);
    assert.equal(topeEndeudamiento(9_000_000), 50, 'exactamente 9M todavia usa el tope base');
    assert.equal(topeEndeudamiento(12_000_000), 60);
  });

  test('Filtro 2: 55% descalifica a quien gana $7M pero pasa a quien gana $12M', () => {
    assert.equal(evaluarEndeudamiento(55, 7_000_000), 'borderline');
    assert.equal(evaluarEndeudamiento(55, 12_000_000), 'ok');
  });

  test('Filtro 2: borderline es hasta ~10 puntos sobre el tope', () => {
    assert.equal(evaluarEndeudamiento(60, 7_000_000), 'borderline');
    assert.equal(evaluarEndeudamiento(61, 7_000_000), 'descalifica');
  });
});

// ===========================================================================
describe('Convivencia bot <-> Setter humano', () => {
  test('handoff activo: el bot se calla', () => {
    const r = decidirSiResponder(estadoEn('M2_ENVIADO', { handoff_razon: 'pregunta_precio' }));
    assert.equal(r.responder, false);
  });

  test('lead ya agendado (dominio del Setter): el bot se calla', () => {
    const r = decidirSiResponder(estadoEn('M7_ENVIADO', { estado_codigo: 'agendado' }));
    assert.equal(r.responder, false);
    assert.equal(r.razon, 'estado_de_humano');
  });

  test('perdido / nutricion: el bot se calla', () => {
    assert.equal(decidirSiResponder(estadoEn(null, { estado_codigo: 'perdido' })).responder, false);
    assert.equal(decidirSiResponder(estadoEn(null, { estado_codigo: 'nutricion' })).responder, false);
  });

  test('descalificado SI deja pasar: es la unica puerta del RetornoLead', () => {
    const r = decidirSiResponder(estadoEn('DESCALIFICADO', { estado_codigo: 'descalificado' }));
    assert.equal(r.responder, true);
    assert.equal(r.razon, 'posible_retorno_lead');
  });

  test('ya se entregaron las preguntas pre-llamada: el bot no sigue hablando', () => {
    assert.equal(decidirSiResponder(estadoEn('CIERRE_PRECALL')).responder, false);
  });
});

// ===========================================================================
describe('Camino feliz completo M1 -> M7', () => {
  test('lead nuevo con "CONTROL" recibe la variante CONTROL', () => {
    const p = decidirTurno(null, {}, 'CONTROL');
    assert.equal(p.etapaNueva, 'M1_ENVIADO');
    assert.equal(p.estadoDestino, 'contactado');
    assert.match(p.mensajes[0], /no tener el control real de tu dinero/);
  });

  test('lead nuevo con "CLARIDAD" recibe la otra variante', () => {
    assert.match(decidirTurno(null, {}, 'CLARIDAD').mensajes[0], /buscas tener claridad/);
  });

  test('M1 -> ingreso 12M pasa Filtro 1 y va a M2', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'), { ingreso_cop: 12_000_000, profesion: 'Ingeniera' });
    assert.equal(p.etapaNueva, 'M2_ENVIADO');
    assert.equal(p.campos.salario_monto, 12_000_000);
    assert.equal(p.campos.ingreso_confirmado, true);
    assert.match(p.mensajes[0], /nivel de endeudamiento/);
  });

  test('M2 -> 30% pasa Filtro 2 y va a M3 (dolor)', () => {
    const p = decidirTurno(estadoEn('M2_ENVIADO', { salario_monto: 12_000_000 }), { endeudamiento_pct: 30 });
    assert.equal(p.etapaNueva, 'M3_ENVIADO');
    assert.match(p.mensajes[0], /mayor frustración/);
  });

  test('M3 -> dolor B va a M4 (urgencia)', () => {
    const p = decidirTurno(estadoEn('M3_ENVIADO'), { dolor: 'B' });
    assert.equal(p.etapaNueva, 'M4_ENVIADO');
    assert.equal(p.campos.dolor, 'B');
  });

  test('M4 -> urgencia "ahora" CALIFICA al lead y manda el pitch', () => {
    const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'ahora' });
    assert.equal(p.etapaNueva, 'M5_ENVIADO');
    assert.equal(p.estadoDestino, 'calificado', '3/3 filtros -> calificado');
    assert.equal(p.campos.califica, true);
    assert.match(p.mensajes[0], /¿Agendamos\?/);
  });

  test('M5 -> acepta: link aislado + confirmame + M7, y NUNCA "agendado"', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { acepta: true });
    assert.equal(p.mensajes.length, 3);
    // REGLA CRITICA: el link va en su propia burbuja, sin texto pegado despues.
    assert.ok(p.mensajes[0].includes(CALENDAR_LINK));
    assert.ok(!p.mensajes[1].includes(CALENDAR_LINK));
    assert.match(p.mensajes[1], /Confirmame cuando te hayas agendado/);
    assert.match(p.mensajes[2], /solo tú o consideras importante que participe alguien más/);
    assert.equal(p.campos.calendario_enviado, true);
    assert.equal(p.estadoDestino, 'calificado');
    assert.notEqual(p.estadoDestino, 'agendado', 'el bot jamas escribe agendado');
    assert.equal(p.permitirEmpatia, false, 'nada de texto generado junto al link');
  });

  test('M7 -> confirma que agendo: preguntas pre-llamada, sigue en calificado', () => {
    const p = decidirTurno(estadoEn('M7_ENVIADO', { estado_codigo: 'calificado' }), { confirmo_agendo: true });
    assert.equal(p.etapaNueva, 'CIERRE_PRECALL');
    assert.equal(p.estadoDestino, 'calificado');
    assert.match(p.mensajes[0], /estimado total de créditos/);
  });

  test('M7 -> va acompañado', () => {
    const p = decidirTurno(estadoEn('M7_ENVIADO'), { acompanado: true });
    assert.equal(p.campos.asiste_acompanado, true);
    assert.match(p.mensajes[0], /esa persona también pueda estar ese día/);
  });
});

// ===========================================================================
describe('Descalificacion con valor', () => {
  test('ingreso bajo -> script 1 + motivo de perdida', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'), { ingreso_cop: 3_000_000 });
    assert.equal(p.estadoDestino, 'descalificado');
    assert.equal(p.motivoPerdida, 'Descalificado - Ingreso bajo (< $7M)');
    assert.equal(p.campos.califica, false);
    assert.match(p.mensajes[0], /subir el ingreso primero/);
  });

  test('endeudamiento muy alto -> script 2', () => {
    const p = decidirTurno(estadoEn('M2_ENVIADO', { salario_monto: 8_000_000 }), { endeudamiento_pct: 85 });
    assert.equal(p.estadoDestino, 'descalificado');
    assert.equal(p.motivoPerdida, 'Descalificado - Endeudamiento sobre su tope');
  });

  test('sin urgencia -> script 3', () => {
    const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'algun_dia' });
    assert.equal(p.estadoDestino, 'descalificado');
    assert.equal(p.motivoPerdida, 'Descalificado - Sin urgencia');
  });

  test('REGLA DE ORO V4.1: ingreso ambiguo NUNCA descalifica, pide la cifra', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'), { ingreso_cop: null, profesion: 'Abogada' });
    assert.notEqual(p.estadoDestino, 'descalificado');
    assert.equal(p.etapaNueva, 'M1_INGRESO_AMBIGUO');
    assert.match(p.mensajes[0], /me confirmas el número aproximado/);
  });

  test('sigue ambiguo tras pedirla -> handoff, jamas descarte', () => {
    const p = decidirTurno(estadoEn('M1_INGRESO_AMBIGUO'), { ingreso_cop: null });
    assert.equal(p.handoffRazon, 'ambiguo');
    assert.notEqual(p.estadoDestino, 'descalificado');
  });
});

// ===========================================================================
describe('RetornoLead (★ V4.1) — descartado que se recalifica', () => {
  test('da una cifra que si califica -> rectifica y retoma en M2', () => {
    const estado = estadoEn('DESCALIFICADO', { estado_codigo: 'descalificado', es_terminal: true });
    const p = decidirTurno(estado, { ingreso_cop: 22_000_000 }, 'pero yo gano 22 millones');
    assert.equal(p.estadoDestino, 'contactado');
    assert.equal(p.etapaNueva, 'M2_ENVIADO');
    assert.equal(p.campos.salario_monto, 22_000_000);
    assert.match(p.mensajes[0], /tienes toda la razón/);
    assert.match(p.mensajes[1], /nivel de endeudamiento/);
    // "sin revelar que es IA": el copy no puede mencionar bot/sistema/error.
    assert.ok(!/bot|sistema|autom[aá]tic|inteligencia artificial/i.test(p.mensajes[0]));
  });

  test('escribe cualquier otra cosa -> solo se registra, sin responder', () => {
    const estado = estadoEn('DESCALIFICADO', { estado_codigo: 'descalificado' });
    const p = decidirTurno(estado, { ingreso_cop: null }, 'gracias igual');
    assert.equal(p.mensajes.length, 0);
    assert.equal(p.estadoDestino, null);
  });
});

// ===========================================================================
describe('Objeciones y escalamiento', () => {
  test('objecion conocida se responde con su script y no avanza la etapa', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 1, objecion_conocida: true });
    assert.match(p.mensajes[0], /100% gratis/);
    assert.equal(p.etapaNueva, 'M5_ENVIADO');
    assert.equal(p.campos.objeciones_consecutivas, 1);
  });

  test('MISMA objecion 2 veces -> resistencia_repetida', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '3', objeciones_consecutivas: 1 });
    const p = decidirTurno(estado, { objecion_num: 3, objecion_conocida: true });
    assert.equal(p.handoffRazon, 'resistencia_repetida');
  });

  test('precio insistido 2 veces -> pregunta_precio (mas util que el generico)', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '7', objeciones_consecutivas: 1 });
    const p = decidirTurno(estado, { objecion_num: 7, objecion_conocida: true });
    assert.equal(p.handoffRazon, 'pregunta_precio');
  });

  test('3 objeciones consecutivas -> resistencia_acumulada', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '2', objeciones_consecutivas: 2 });
    const p = decidirTurno(estado, { objecion_num: 4, objecion_conocida: true });
    assert.equal(p.handoffRazon, 'resistencia_acumulada');
  });

  test('objecion fuera de las 9 -> objecion_fuera_playbook', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_detectada: true, objecion_num: null, objecion_conocida: false });
    assert.equal(p.handoffRazon, 'objecion_fuera_playbook');
  });

  test('Objecion 9 en el filtro de urgencia (M4) se maneja sin descalificar', () => {
    const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'pregunta_por_que' });
    assert.match(p.mensajes[0], /Lo más caro NO es la plata/);
    assert.notEqual(p.estadoDestino, 'descalificado');
  });
});

// ===========================================================================
describe('Prioridad maxima: crisis y hostilidad', () => {
  test('crisis gana sobre cualquier etapa y manda a nutricion', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { crisis: true, acepta: true });
    assert.equal(p.handoffRazon, 'crisis_emocional');
    assert.equal(p.estadoDestino, 'nutricion');
    assert.equal(p.mensajes.length, 0, 'no se le manda copy de ventas a alguien en crisis');
  });

  test('hostilidad -> contenido_hostil', () => {
    const p = decidirTurno(estadoEn('M2_ENVIADO'), { hostil: true });
    assert.equal(p.handoffRazon, 'contenido_hostil');
  });

  test('ex cliente -> handoff', () => {
    assert.equal(decidirTurno(estadoEn('M1_ENVIADO'), { ex_cliente: true }).handoffRazon, 'ex_cliente');
  });
});

// ===========================================================================
describe('Detectores deterministas', () => {
  test('variante de M1 por keyword', () => {
    assert.equal(detectarVarianteM1('CONTROL'), 'M1_CONTROL');
    assert.equal(detectarVarianteM1('quiero claridad'), 'M1_CLARIDAD');
    assert.equal(detectarVarianteM1('hola'), 'M1_GENERAL');
  });

  test('confirmacion de agenda', () => {
    for (const t of ['ya agende', 'listo ya quede agendada', 'reserve el espacio']) {
      assert.equal(detectarConfirmacionAgenda(t), true, t);
    }
    assert.equal(detectarConfirmacionAgenda('no he podido'), false);
  });

  test('solo vs acompañado', () => {
    assert.equal(detectarAcompanante('voy con mi esposa'), true);
    assert.equal(detectarAcompanante('voy solo'), false);
    assert.equal(detectarAcompanante('mmm no se'), null);
  });

  test('urgencia', () => {
    assert.equal(detectarUrgencia('es prioridad ahora'), 'ahora');
    assert.equal(detectarUrgencia('mas adelante'), 'algun_dia');
    assert.equal(detectarUrgencia('por que es importante resolverlo ahora?'), 'pregunta_por_que');
  });

  test('dolor por letra sola', () => {
    assert.equal(detectarDolorLetra('B'), 'B');
    assert.equal(detectarDolorLetra('c)'), 'C');
    assert.equal(detectarDolorLetra('la B porque no se en que se va'), null, 'texto largo lo resuelve el LLM');
  });

  test('endeudamiento en %', () => {
    assert.equal(detectarEndeudamientoPct('como el 35%'), 35);
    assert.equal(detectarEndeudamientoPct('40'), 40);
    assert.equal(detectarEndeudamientoPct('no se'), null);
  });

  test('hostilidad', () => {
    assert.equal(detectarHostilidad('esto es una estafa'), true);
    assert.equal(detectarHostilidad('gracias, me interesa'), false);
  });
});
