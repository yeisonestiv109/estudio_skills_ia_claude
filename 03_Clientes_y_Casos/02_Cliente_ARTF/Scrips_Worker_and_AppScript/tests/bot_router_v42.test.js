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
  pareceRemanente, esSoloPalabraClave, detectarSinHorarios, detectarSiNo,
} from '../bot_router_v42.js';
import { CALENDAR_LINK, UMBRALES, OBJECIONES_HABILITADAS } from '../sop_v42_plantillas.js';

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

  test('entregadas las preguntas pre-llamada, el bot se calla', () => {
    // El blindaje del show-up se retiro el 3-sep: NO estaba en el SOP V4.2
    // (verificado en el PDF) y el % de asistencia ya lo marca el Closer desde
    // su dashboard. Preguntarselo al lead era fricción innecesaria.
    assert.equal(decidirSiResponder(estadoEn('CIERRE_PRECALL')).responder, false);
    assert.equal(decidirSiResponder(estadoEn('BLINDAJE_CERRADO')).responder, false);
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
    assert.equal(p.mensajes.length, 2, 'el pitch va troceado en 2 burbujas');
    assert.match(p.mensajes[1], /¿Agendamos\?/);
  });

  /**
   * REGRESION del bug mas grave encontrado (1-sep-2026, revisando el proyecto
   * original del Setter IA de Javier): la version anterior mandaba el link y
   * DESPUES dos mensajes mas en el mismo turno. Ellos lo tienen documentado
   * como bug confirmado en produccion -- Instagram concatena el link con el
   * texto siguiente y lo deja invalido ("Dynamic Link Not Found"), rompiendo
   * el agendamiento, que es lo unico que este bot existe para lograr.
   */
  test('M5 -> acepta: el LINK ES LA ULTIMA BURBUJA, nada despues', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { acepta: true });
    // 4 burbujas: asistencia (M7) -> saludo -> confirmame -> link.
    // M7 va ANTES del link a proposito: su propio texto dice "antes de que
    // separes tu espacio", y si fuera en turno aparte podria no enviarse nunca.
    assert.equal(p.mensajes.length, 4);
    assert.match(p.mensajes[0], /asistirás solo tú/);
    assert.ok(p.mensajes.slice(0, 3).every((m) => !m.includes(CALENDAR_LINK)));
    assert.equal(p.mensajes[p.mensajes.length - 1].trim(), CALENDAR_LINK,
      'REGLA DURA: el link es el ULTIMO elemento del turno');
    assert.equal(p.etapaNueva, 'M7_ENVIADO');
    assert.equal(p.campos.calendario_enviado, true);
    assert.equal(p.estadoDestino, 'calificado');
    assert.notEqual(p.estadoDestino, 'agendado', 'el bot jamas escribe agendado');
    assert.equal(p.permitirEmpatia, false, 'nada de texto generado junto al link');
  });

  test('turno siguiente al link: ahi SI van M7 + confirmame (ya sin link)', () => {
    const p = decidirTurno(estadoEn('M6_ENVIADO', { estado_codigo: 'calificado' }), {});
    assert.equal(p.etapaNueva, 'M7_ENVIADO');
    assert.match(p.mensajes[0], /solo tú o consideras importante que participe alguien más/);
    assert.match(p.mensajes[1], /Confirmame cuando te hayas agendado/);
    assert.ok(p.mensajes.every((m) => !m.includes(CALENDAR_LINK)), 'sin link en este turno');
  });

  test('M7 -> dice que agendo Y la base lo confirma: preguntas pre-llamada', () => {
    const p = decidirTurno(
      estadoEn('M7_ENVIADO', { estado_codigo: 'calificado', tiene_reunion: true }),
      { confirmo_agendo: true });
    assert.equal(p.etapaNueva, 'CIERRE_PRECALL');
    assert.match(p.mensajes[0], /estimado total de créditos/);
  });

  test('M7 -> dice que agendo pero la base NO lo respalda: solo acuse', () => {
    // El bot no decide si agendo: lo decide la base. Quien vincula la reunion
    // es el Setter desde el dashboard.
    const p = decidirTurno(
      estadoEn('M7_ENVIADO', { estado_codigo: 'calificado', tiene_reunion: false }),
      { confirmo_agendo: true });
    assert.equal(p.etapaNueva, 'M7_ENVIADO', 'no avanza al cierre');
    assert.equal(p.mensajes.length, 1);
    assert.ok(!/estimado total de créditos/.test(p.mensajes[0]),
      'no manda las preguntas pre-llamada sin reunion vinculada');
  });

  test('M7 -> no encuentra horarios: pide la franja y escala', () => {
    const p = decidirTurno(estadoEn('M7_ENVIADO'), { sin_horarios: true });
    assert.equal(p.handoffRazon, 'agendamiento_manual_pendiente');
    assert.match(p.mensajes[0], /qué fecha y bloques de horarios te quedan bien/);
    assert.ok(!/Contame/.test(p.mensajes[0]), 'el "Contame" original era voseo');
  });

  test('M7 -> asiste solo: acuse corto aprobado, sin abrir hilos nuevos', () => {
    const p = decidirTurno(estadoEn('M7_ENVIADO'), { acompanado: false });
    assert.equal(p.campos.asiste_acompanado, false);
    assert.equal(p.mensajes.length, 1);
    assert.match(p.mensajes[0], /Quedo pendiente de tu confirmación/);
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

  test('vuelve sin cifra -> se le pregunta por el motivo EXACTO del descarte', () => {
    const estado = estadoEn('DESCALIFICADO', {
      estado_codigo: 'descalificado',
      motivo_perdida: 'Descalificado - Endeudamiento sobre su tope',
    });
    const p = decidirTurno(estado, { ingreso_cop: null }, 'hola, volvi');
    assert.equal(p.etapaNueva, 'RETORNO_PREGUNTA');
    assert.match(p.mensajes[0], /tus deudas se llevaban buena parte de tu ingreso/);
  });

  test('retorno: dice que SI cambio -> revalida el filtro que fallo', () => {
    const estado = estadoEn('RETORNO_PREGUNTA', {
      estado_codigo: 'descalificado',
      motivo_perdida: 'Descalificado - Endeudamiento sobre su tope',
    });
    const p = decidirTurno(estado, { retoma: true }, 'si, ya la baje');
    assert.equal(p.etapaNueva, 'M2_ENVIADO');
    assert.equal(p.estadoDestino, 'contactado');
    assert.match(p.mensajes[0], /nivel de endeudamiento/);
  });

  test('retorno: dice que NO cambio -> se cierra sin insistir', () => {
    const estado = estadoEn('RETORNO_PREGUNTA', { estado_codigo: 'descalificado' });
    const p = decidirTurno(estado, { retoma: false }, 'no, sigue igual');
    assert.equal(p.etapaNueva, 'DESCALIFICADO');
    assert.match(p.mensajes[0], /Cuando la situación cambie, acá estoy/);
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

  test('Objecion 9 en M4: NUNCA descalifica (invariante del SOP)', () => {
    // El SOP es explicito: preguntar "¿por que ahora?" es señal MIXTA, puede
    // ser duda legitima. Jamas se puede leer como falta de urgencia. Ese
    // invariante se mantiene tanto si el bot la contesta como si la escala.
    const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'pregunta_por_que' });
    assert.notEqual(p.estadoDestino, 'descalificado');
    // Con el alcance de la v1 (objeciones 1-3), la 9 la atiende un humano.
    assert.equal(p.handoffRazon, 'objecion_no_habilitada');
  });

  test('la perilla de alcance funciona: habilitar la 9 la hace contestar sola', () => {
    // Prueba que ampliar el alcance es UNA linea, y que el copy ya esta listo.
    OBJECIONES_HABILITADAS.add(9);
    try {
      const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'pregunta_por_que' });
      assert.equal(p.handoffRazon, null);
      assert.match(p.mensajes[0], /Lo más caro NO es la plata/);
    } finally {
      OBJECIONES_HABILITADAS.delete(9);
    }
  });

  test('objecion habilitada (1) la contesta el bot; no habilitada (7) va a humano', () => {
    const habilitada = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 1, objecion_conocida: true });
    assert.equal(habilitada.handoffRazon, null);
    assert.match(habilitada.mensajes[0], /100% gratis/);

    const noHabilitada = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 7, objecion_conocida: true });
    assert.equal(noHabilitada.handoffRazon, 'objecion_no_habilitada');
    assert.equal(noHabilitada.mensajes.length, 0, 'no le manda copy al lead');
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

  test('dolor: letra sola y letra con texto (mejorado con el corpus)', () => {
    // El corpus real mostro que el lead NO responde "B" a secas, responde
    // "B sin duda. Siento que me llega la plata...". Antes eso caia al LLM sin
    // necesidad; ahora se resuelve determinista.
    assert.equal(detectarDolorLetra('B'), 'B');
    assert.equal(detectarDolorLetra('c)'), 'C');
    assert.equal(detectarDolorLetra('B sin duda. Siento que me llega la plata'), 'B');
    assert.equal(detectarDolorLetra('la B porque no se en que se va'), 'B');
    assert.equal(detectarDolorLetra('seria la c'), 'C');
  });

  test('dolor: la "a" no se confunde con la preposicion', () => {
    // "a" es palabra en español; b/c/d no. Por eso la "a" solo cuenta aislada
    // o con puntuacion -- si no, "a mi me pasa que..." se leeria como opcion A.
    assert.equal(detectarDolorLetra('A'), 'A');
    assert.equal(detectarDolorLetra('a.'), 'A');
    assert.equal(detectarDolorLetra('la a'), 'A');
    assert.equal(detectarDolorLetra('a mi me pasa que no me alcanza'), null);
    assert.equal(detectarDolorLetra('a veces siento eso'), null);
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

// ===========================================================================
// Aprendizajes de produccion incorporados del proyecto original de Javier
// (Setter-IA-Claude-Code-Project). Cada uno viene de un caso REAL que ya
// paso en operacion -- no son casos hipoteticos.
// ===========================================================================
describe('Aprendizajes de produccion (proyecto Setter IA de Javier)', () => {
  test('SOP-05 #2: "me quedan $5M" NO descalifica -- primero se aclara', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'), { ingreso_cop: 5_000_000 }, 'me quedan como 5 millones libres');
    assert.notEqual(p.estadoDestino, 'descalificado');
    assert.equal(p.etapaNueva, 'M1_ACLARAR_REMANENTE');
    assert.match(p.mensajes[0], /ingreso total al mes, o lo que te queda/);
  });

  test('SOP-05 #2: si tras aclarar sigue bajo, ahi si descalifica', () => {
    const p = decidirTurno(estadoEn('M1_ACLARAR_REMANENTE'), { ingreso_cop: 5_000_000 }, 'no, es mi total');
    assert.equal(p.estadoDestino, 'descalificado');
  });

  test('un ingreso bajo SIN marca de remanente descalifica de una', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'), { ingreso_cop: 3_000_000 }, 'gano 3 millones');
    assert.equal(p.estadoDestino, 'descalificado');
  });

  test('repetir la palabra clave NO avanza el flujo: reenvia la pregunta', () => {
    // Bug real de la primera prueba en vivo: el lead reenvio "PRUEBAV42"
    // estando en M1 y el bot lo leyo como su respuesta de ingreso.
    const p = decidirTurno(estadoEn('M2_ENVIADO'), {}, 'CONTROL');
    assert.equal(p.etapaNueva, null, 'no avanza de etapa');
    assert.equal(p.estadoDestino, null);
    assert.match(p.mensajes[0], /nivel de endeudamiento/, 'reenvia la pregunta pendiente');
  });

  test('el lead que vuelve semanas despues retoma donde quedo', () => {
    const p = decidirTurno(estadoEn('M4_ENVIADO', { dias_sin_actividad: 21 }), {}, 'CONTROL');
    assert.match(p.mensajes[p.mensajes.length - 1], /¿Resolver esto es una prioridad AHORA/);
  });

  test('detectores nuevos', () => {
    assert.equal(pareceRemanente('me quedan 5 millones'), true);
    assert.equal(pareceRemanente('gano 5 millones'), false);
    assert.equal(esSoloPalabraClave('CONTROL'), true);
    assert.equal(esSoloPalabraClave('Hola'), true);
    assert.equal(esSoloPalabraClave('hola, gano 8 millones'), false);
    assert.equal(detectarSinHorarios('no me aparece nada disponible'), true);
    assert.equal(detectarSinHorarios('listo ya agende'), false);
    assert.equal(detectarSiNo('si, ya mejoro'), true);
    assert.equal(detectarSiNo('no, sigue igual'), false);
  });
});
