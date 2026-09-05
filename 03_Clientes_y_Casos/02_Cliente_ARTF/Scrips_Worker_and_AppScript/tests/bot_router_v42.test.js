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
  parseIngresoCOP, evaluarIngreso, calcularRemanente, evaluarEndeudamiento,
  decidirSiResponder, decidirTurno,
  detectarVarianteM1, detectarConfirmacionAgenda, detectarAcompanante,
  detectarUrgencia, detectarDolorLetra, detectarDolorLetras, detectarHostilidad, detectarEndeudamientoPct,
  detectarAceptacion,
  pareceRemanente, esSoloPalabraClave, detectarSinHorarios, detectarSiNo, pareceDolorFinanciero,
  pareceIncertidumbre,
  etapaParaRetomar, cuentaCifrasDeDinero,
  preguntaPendiente,
} from '../bot_router_v42.js';
import {
  CALENDAR_LINK, UMBRALES, OBJECIONES_HABILITADAS, PLANTILLAS,
  ESCALERA_REPREGUNTAS_HABILITADA, COPY_PENDIENTE_APROBACION, LIMPIAR_HANDOFF,
} from '../sop_v42_plantillas.js';

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
  // Los tests leen de UMBRALES: el fundador ya movio estas cifras dos veces
  // (7M -> 6M el 4-sep) y no tiene sentido que se pongan rojos por eso.
  const MIN = UMBRALES.INGRESO_MINIMO;
  const REM = UMBRALES.REMANENTE_MINIMO;

  test(`Filtro 1: umbral $${MIN / 1e6}M`, () => {
    assert.equal(evaluarIngreso(MIN), 'califica', 'el umbral exacto califica');
    assert.equal(evaluarIngreso(MIN - 1), 'descalifica');
    assert.equal(evaluarIngreso(null), 'ambiguo', 'sin cifra NUNCA se descarta');
  });

  test('el remanente es ingreso x (1 - deuda%)', () => {
    assert.equal(calcularRemanente(10_000_000, 30), 7_000_000);
    assert.equal(calcularRemanente(10_000_000, 0), 10_000_000);
    assert.equal(calcularRemanente(10_000_000, 100), 0);
  });

  test('sin ingreso o sin deuda el remanente es null, NUNCA cero', () => {
    // Devolver 0 significaria "no le queda nada" y descartaria por falta de dato.
    assert.equal(calcularRemanente(null, 30), null);
    assert.equal(calcularRemanente(10_000_000, null), null);
    assert.equal(calcularRemanente(0, 30), null);
    assert.equal(evaluarEndeudamiento(30, null), 'no_sabe', 'sin ingreso no se decide');
  });

  test(`Filtro 2: el criterio es que le queden $${REM / 1e6}M libres`, () => {
    // 10M con 70% de deuda -> le quedan 3M -> pasa.
    assert.equal(evaluarEndeudamiento(70, 10_000_000), 'ok');
    // 10M con 80% -> le quedan 2M -> no pasa, y la deuda lo explica -> borderline.
    assert.equal(evaluarEndeudamiento(80, 10_000_000), 'borderline');
    // El limite exacto pasa.
    assert.equal(evaluarEndeudamiento(75, 10_000_000), 'ok', '2.5M exactos pasan');
  });

  test('el mismo % da distinto segun el ingreso: eso es el punto del cambio', () => {
    // 60% de deuda: a quien gana 6M le quedan 2.4M (no pasa); a quien gana 10M
    // le quedan 4M (pasa). Con el modelo viejo de tope por %, ambos eran iguales.
    assert.equal(evaluarEndeudamiento(60, 6_000_000), 'borderline');
    assert.equal(evaluarEndeudamiento(60, 10_000_000), 'ok');
  });

  test('la rama "deuda baja y sin remanente" es inalcanzable pasando el Filtro 1', () => {
    // Comprobacion del hallazgo de la auditoria: con ingreso >= MIN y deuda
    // < 50%, el remanente SIEMPRE supera el minimo. La rama existe para cuando
    // el ingreso llegue por otra via (el Setter escribiendolo a mano), no por
    // el embudo. Si alguien baja INGRESO_MINIMO por debajo de 2*REM, deja de
    // ser inalcanzable -- y este test lo dira.
    let alcanzada = 0;
    for (let ing = MIN; ing <= 30_000_000; ing += 250_000) {
      for (let d = 0; d < 50; d += 1) {
        if (evaluarEndeudamiento(d, ing) === 'descalifica') alcanzada++;
      }
    }
    assert.equal(alcanzada, 0,
      'si esto deja de ser 0, revisa que INGRESO_MINIMO siga siendo >= 2 x REMANENTE_MINIMO');
    assert.ok(MIN >= 2 * REM, 'la relacion entre los dos umbrales cambio: revisa la rama');

    // Y con un ingreso por DEBAJO del filtro (via dashboard) si descalifica.
    assert.equal(evaluarEndeudamiento(20, 3_000_000), 'descalifica');
  });

  test('la cifra que se asume al confirmar el rango coincide con lo que dice el copy', () => {
    // Si el copy del rango cambia de cifra, la constante tiene que cambiar con
    // el: asumir una cifra distinta a la que se le pregunto seria inventarla.
    const cifraDelCopy = PLANTILLAS.M1_PEDIR_RANGO.match(/\$(\d+)M/)?.[1];
    assert.equal(Number(cifraDelCopy) * 1e6, UMBRALES.INGRESO_ASUMIDO_POR_RANGO,
      'M1_PEDIR_RANGO y INGRESO_ASUMIDO_POR_RANGO dicen cifras distintas');
    assert.ok(UMBRALES.INGRESO_ASUMIDO_POR_RANGO >= UMBRALES.INGRESO_MINIMO,
      'lo que se asume tiene que bastar para pasar el Filtro 1');
  });
});

// ===========================================================================
describe('Convivencia bot <-> Setter humano', () => {
  // AUTO-RECUPERACION (4-sep-2026). Con un handoff RECUPERABLE el bot se deja
  // clasificar el mensaje, pero solo habla si el lead pidio continuar.
  test('handoff NO recuperable: el bot se calla, punto', () => {
    for (const razon of ['crisis_emocional', 'ex_cliente', 'agendamiento_manual_pendiente']) {
      const r = decidirSiResponder(estadoEn('M2_ENVIADO', { handoff_razon: razon }));
      assert.equal(r.responder, false, `${razon} NUNCA se recupera`);
      assert.equal(r.razon, 'handoff_activo');
    }
  });

  test('handoff recuperable: se clasifica, pero sin pedir seguir el bot NO habla', () => {
    const estado = estadoEn('M2_ENVIADO', { handoff_razon: 'pregunta_precio' });
    assert.equal(decidirSiResponder(estado).responder, true, 'se deja clasificar');
    const p = decidirTurno(estado, {}, 'hola');
    assert.equal(p.mensajes.length, 0, 'pero no le habla si no pidio continuar');
    assert.equal(p.etapaNueva, null, 'y no toca la etapa');
  });

  test('handoff recuperable + el lead pide seguir: se recupera y retoma', () => {
    // El caso exacto del QA: "pero igual quiero seguir, me da 40%".
    const estado = estadoEn('HANDOFF', {
      handoff_razon: 'contenido_hostil', salario_monto: 11_000_000,
    });
    const p = decidirTurno(estado, { recupera_handoff: true, endeudamiento_pct: 40 },
      'pero igual quiero seguir, me da 40%');
    assert.equal(p.handoffRazon, LIMPIAR_HANDOFF, 'limpia el handoff');
    assert.equal(p.etapaNueva, 'M2_ENVIADO', 'retoma donde dicen los datos, no en HANDOFF');
    assert.ok(p.mensajes.length > 0, 'y le vuelve a hablar');
    assert.equal(p.permitirEmpatia, true, 'viene de un roce: la apertura personalizada importa');
  });

  test('la crisis NO se recupera aunque el lead diga que quiere seguir', () => {
    // Es la linea que no se cruza. Alguien en crisis que escribe "no, sigamos"
    // necesita a una persona, no que el bot siga vendiendo.
    const estado = estadoEn('HANDOFF', { handoff_razon: 'crisis_emocional', salario_monto: 11_000_000 });
    assert.equal(decidirSiResponder(estado).responder, false,
      'la puerta se cierra antes de que el LLM pueda opinar');
  });

  test('etapaParaRetomar deduce el punto por los DATOS, no por la etapa', () => {
    assert.equal(etapaParaRetomar({}), 'M1_ENVIADO');
    assert.equal(etapaParaRetomar({ salario_monto: 9_000_000 }), 'M2_ENVIADO');
    assert.equal(etapaParaRetomar({ salario_monto: 9_000_000, endeudamiento_pct: 30 }), 'M3_ENVIADO');
    assert.equal(etapaParaRetomar({ salario_monto: 9_000_000, endeudamiento_pct: 30, dolor: 'A' }), 'M4_ENVIADO');
    assert.equal(etapaParaRetomar({ salario_monto: 9_000_000, endeudamiento_pct: 30, dolor: 'A', urgencia: 'ahora' }), 'M5_ENVIADO');
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



  // CAMBIO del fundador (4-sep-2026): la despedida con las preguntas pre-llamada
  // tambien va al CONFIRMAR, no solo cuando la reunion ya esta vinculada.
  //
  // Lo que NO cambio, y es lo que este test protege de verdad: el bot sigue sin
  // adelantar el ESTADO. Decir la frase y falsear el dato son cosas distintas.


  test('el acuse se manda UNA vez: despues el bot espera en silencio', () => {
    // Sin esto, cada "listo"/"gracias"/"ya quedo" recibia el mismo
    // "¡Perfecto! 🙌" otra vez. Se ve robotico en el peor momento.
    const esperando = estadoEn('M7_ESPERANDO_VINCULO', { estado_codigo: 'calificado', tiene_reunion: false });
    assert.equal(decidirTurno(esperando, {}, 'gracias').mensajes.length, 0);
    assert.equal(decidirTurno(esperando, { confirmo_agendo: true }, 'ya quedo').mensajes.length, 0);
  });

  test('esperando el vinculo: cuando el Setter vincula, sale el cierre', () => {
    const p = decidirTurno(
      estadoEn('M7_ESPERANDO_VINCULO', { estado_codigo: 'calificado', tiene_reunion: true }),
      {}, 'ok');
    assert.equal(p.etapaNueva, 'CIERRE_PRECALL');
    assert.match(p.mensajes[0], /estimado total de créditos/);
  });

  test('esperando el vinculo: si dice que no encuentra horarios, escala', () => {
    const p = decidirTurno(
      estadoEn('M7_ESPERANDO_VINCULO', { estado_codigo: 'calificado' }),
      { sin_horarios: true }, 'no me aparece nada');
    assert.equal(p.handoffRazon, 'agendamiento_manual_pendiente');
  });

  test('M7 -> no encuentra horarios: pide la franja y escala', () => {
    const p = decidirTurno(estadoEn('M7_ENVIADO'), { sin_horarios: true });
    assert.equal(p.handoffRazon, 'agendamiento_manual_pendiente');
    assert.match(p.mensajes[0], /qué fecha y bloques de horarios te quedan bien/);
    assert.ok(!/Contame/.test(p.mensajes[0]), 'el "Contame" original era voseo');
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
    assert.equal(p.motivoPerdida, `Descalificado - Ingreso bajo (< $${UMBRALES.INGRESO_MINIMO / 1e6}M)`);
    assert.equal(p.campos.califica, false);
    assert.match(p.mensajes[0], /subir el ingreso primero/);
  });

  // CAMBIO DE REGLA (fundador, 4-sep-2026): un endeudamiento alto ya no
  // descalifica de una. Primero se pregunta que TIPO de deuda es, porque la
  // hipotecaria no cuenta igual. Solo se descarta si ademas es deuda de consumo
  // y no le sobra el minimo.
  test('endeudamiento muy alto -> primero se pregunta el tipo de deuda', () => {
    const p = decidirTurno(estadoEn('M2_ENVIADO', { salario_monto: 8_000_000 }), { endeudamiento_pct: 85 });
    assert.equal(p.etapaNueva, 'M2_BORDERLINE', 'no se descarta sin preguntar');
    assert.equal(p.estadoDestino, 'contactado');
  });

  test('deuda alta + deuda de consumo + poco sobrante -> script 2', () => {
    const p = decidirTurno(estadoEn('M2_BORDERLINE', { salario_monto: 8_000_000 }),
      { deuda_mayoritariamente_buena: false, remanente_cop: 900_000 });
    assert.equal(p.estadoDestino, 'descalificado');
    assert.equal(p.motivoPerdida, 'Descalificado - Endeudamiento sobre su tope');
  });

  test('deuda alta pero HIPOTECARIA -> sigue el guion', () => {
    const p = decidirTurno(estadoEn('M2_BORDERLINE', { salario_monto: 8_000_000 }),
      { deuda_mayoritariamente_buena: true });
    assert.equal(p.etapaNueva, 'M3_ENVIADO');
    assert.notEqual(p.estadoDestino, 'descalificado');
  });

  test('deuda de consumo pero RECTIFICA que le sobra suficiente -> sigue el guion', () => {
    // El % de M2 suele ser un estimado grueso. Si al preguntarle en plata
    // resulta que si le queda, el estimado estaba mal, no el lead.
    const p = decidirTurno(estadoEn('M2_BORDERLINE', { salario_monto: 8_000_000 }),
      { deuda_mayoritariamente_buena: false, remanente_cop: 3_000_000 });
    assert.equal(p.etapaNueva, 'M3_ENVIADO');
    assert.equal(p.campos.remanente_cop, 3_000_000, 'la cifra en plata manda sobre el % estimado');
  });

  test('borderline SIN datos para decidir -> humano, jamas descarte a ciegas', () => {
    const p = decidirTurno(estadoEn('M2_BORDERLINE', { salario_monto: 8_000_000 }), {});
    assert.equal(p.handoffRazon, 'ambiguo');
    assert.notEqual(p.estadoDestino, 'descalificado');
  });

  test('sin urgencia -> script 3', () => {
    const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'algun_dia' });
    assert.equal(p.estadoDestino, 'descalificado');
    assert.equal(p.motivoPerdida, 'Descalificado - Sin urgencia');
  });

  // QA 4-sep-2026: hay DOS variantes de la pregunta del rango. Sin objecion de
  // por medio se usa la SIMPLE; el "Te pregunto porque..." defensivo solo tiene
  // sentido despues de que el lead se niegue a dar el dato.
  test('Escenario B del SOP: no dio cifra -> rango, en su variante SIMPLE', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'), { ingreso_cop: null, profesion: 'Abogada' });
    assert.notEqual(p.estadoDestino, 'descalificado');
    assert.equal(p.etapaNueva, 'M1_RANGO_PREGUNTADO');
    assert.match(p.mensajes[0], /¿puedes indicarme si tu salario se encuentra entre/);
    assert.ok(!/Te pregunto porque el proceso funciona mejor/.test(p.mensajes[0]),
      'sin objecion no se pone a la defensiva');
  });

  test('con objecion de privacidad SI usa la variante defensiva', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'),
      { ingreso_cop: null, objecion_num: 6, objecion_conocida: true }, 'no quiero dar ese dato');
    const todo = p.mensajes.join('\n');
    assert.match(todo, /Esa info es sensible/, 'reconoce la objecion');
    assert.match(todo, /Te pregunto porque el proceso funciona mejor/,
      'y ahi si justifica por que insiste');
  });

  test('Escenario E del SOP: termino ambiguo -> se le pide la CIFRA', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'),
      { ingreso_cop: null, ingreso_glosario: 'salario_integral', profesion: 'Abogada' });
    assert.equal(p.etapaNueva, 'M1_INGRESO_AMBIGUO');
    assert.match(p.mensajes[0], /me confirmas el número aproximado/);
  });

  test('H2: un "Si" al rango CONFIRMA el Filtro 1 y avanza a M2', () => {
    // Antes esto caia como ambiguo y terminaba escalando a un humano un lead
    // que acababa de decir que si califica.
    const p = decidirTurno(estadoEn('M1_RANGO_PREGUNTADO'), { confirma_rango: true }, 'si');
    assert.equal(p.etapaNueva, 'M2_ENVIADO');
    assert.equal(p.estadoDestino, 'contactado');
    assert.equal(p.campos.salario_monto, UMBRALES.INGRESO_ASUMIDO_POR_RANGO,
      'se asume el piso del rango que el propio lead acepto');
    assert.equal(p.campos.ingreso_confirmado, false,
      'el lead nunca dijo un numero: la cifra es asumida y el dashboard tiene que saberlo');
    assert.match(p.mensajes[0], /nivel de endeudamiento/);
    assert.equal(p.handoffRazon, null, 'NO escala a humano');
  });

  // DECISION COMERCIAL del fundador (4-sep-2026): el copy sigue preguntando por
  // el rango de $7M aunque el filtro este en $6M, y un "No" descalifica directo.
  // Se asume a proposito la perdida de la banda $6M-$7M. Se dejo escrito para
  // que nadie lo lea como un bug.
  test('H2: un "No" al rango descalifica por ingreso', () => {
    const p = decidirTurno(estadoEn('M1_RANGO_PREGUNTADO'), { confirma_rango: false }, 'no, gano menos');
    assert.equal(p.estadoDestino, 'descalificado');
    assert.equal(p.motivoPerdida, 'Descalificado - Ingreso bajo (fuera del rango del playbook)',
      'el motivo no cita el umbral: este lead puede ganar $6.5M y seria mentira');
  });

  test('H2: si al rango responde con una cifra, la cifra manda sobre el si/no', () => {
    const p = decidirTurno(estadoEn('M1_RANGO_PREGUNTADO'), { ingreso_cop: 20_000_000 }, '20 millones');
    assert.equal(p.etapaNueva, 'M2_ENVIADO');
    assert.equal(p.campos.salario_monto, 20_000_000);
  });

  test('H2: respuesta al rango no clasificable -> pide la cifra, NUNCA descarta', () => {
    const p = decidirTurno(estadoEn('M1_RANGO_PREGUNTADO'), {}, 'mmm');
    assert.notEqual(p.estadoDestino, 'descalificado');
    assert.equal(p.etapaNueva, 'M1_INGRESO_AMBIGUO');
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
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 3, objecion_conocida: true });
    assert.equal(p.etapaNueva, 'M5_ENVIADO');
    assert.equal(p.handoffRazon, null);
    assert.equal(p.campos.ultima_objecion_codigo, '3');
    assert.equal(p.campos.objeciones_consecutivas, 1, 'la 3 es resistencia: si suma');
  });

  // QA 4-sep-2026: la curiosidad NO suma al tope de resistencia.
  test('las objeciones de CURIOSIDAD no acumulan resistencia', () => {
    for (const num of [1, 5, 7, 8, 9]) {
      const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: num, objecion_conocida: true });
      assert.equal(p.campos.objeciones_consecutivas, 0,
        `la objecion ${num} es una pregunta, no resistencia: no puede sumar al tope`);
    }
  });

  // Los umbrales los subio el fundador el 4-sep-2026 (misma objecion: 2->3;
  // acumuladas: 3->4). Los tests LEEN de UMBRALES a proposito: si mañana los
  // vuelve a mover, estos tests siguen siendo verdad en vez de ponerse rojos
  // por una razon que no es un bug.
  const R_MISMA = UMBRALES.RESISTENCIA_MISMA_OBJECION;
  const R_ACUM = UMBRALES.RESISTENCIA_ACUMULADA;

  test('la MISMA objecion, justo por debajo del umbral, NO escala', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '3', objeciones_consecutivas: R_MISMA - 2 });
    const p = decidirTurno(estado, { objecion_num: 3, objecion_conocida: true });
    assert.equal(p.handoffRazon, null, 'todavia le queda una ronda: la contesta el bot');
    assert.ok(p.mensajes.length > 0);
  });

  test(`la MISMA objecion ${R_MISMA} veces -> resistencia_repetida`, () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '3', objeciones_consecutivas: R_MISMA - 1 });
    const p = decidirTurno(estado, { objecion_num: 3, objecion_conocida: true });
    assert.equal(p.handoffRazon, 'resistencia_repetida');
  });

  // La 7 ya no acumula (es curiosidad), asi que la señal es que la REPITA: si
  // vuelve a preguntar el precio despues de nuestra respuesta, no le sirvio.
  test('volver a preguntar el precio -> pregunta_precio (mas util que el generico)', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '7', objeciones_consecutivas: 0 });
    const p = decidirTurno(estado, { objecion_num: 7, objecion_conocida: true });
    assert.equal(p.handoffRazon, 'pregunta_precio');
  });

  test('repetir una pregunta informativa tambien escala: la respuesta no sirvio', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '1', objeciones_consecutivas: 0 });
    const p = decidirTurno(estado, { objecion_num: 1, objecion_conocida: true });
    assert.equal(p.handoffRazon, 'resistencia_repetida');
  });

  test('el precio preguntado la PRIMERA vez lo contesta el bot', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 7, objecion_conocida: true });
    assert.equal(p.handoffRazon, null);
    assert.match(p.mensajes.join('\n'), /el programa no tiene un precio único/);
  });

  test(`${R_ACUM} objeciones consecutivas -> resistencia_acumulada`, () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '2', objeciones_consecutivas: R_ACUM - 1 });
    const p = decidirTurno(estado, { objecion_num: 4, objecion_conocida: true });
    assert.equal(p.handoffRazon, 'resistencia_acumulada');
  });

  test('objeciones consecutivas por debajo del umbral las contesta el bot', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '2', objeciones_consecutivas: R_ACUM - 2 });
    const p = decidirTurno(estado, { objecion_num: 4, objecion_conocida: true });
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0);
  });

  test('objecion fuera de las 9 -> objecion_fuera_playbook', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_detectada: true, objecion_num: null, objecion_conocida: false });
    assert.equal(p.handoffRazon, 'objecion_fuera_playbook');
  });

  test('Objecion 9 en M4: la contesta el bot y NUNCA descalifica', () => {
    // El SOP es explicito: preguntar "¿por que ahora?" es señal MIXTA, puede
    // ser duda legitima. Jamas se puede leer como falta de urgencia.
    // La 9 se habilito el 3-sep: es la unica que el SOP predice DENTRO del
    // flujo normal ("aparece en Mensaje 4").
    const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'pregunta_por_que' });
    assert.notEqual(p.estadoDestino, 'descalificado');
    assert.equal(p.handoffRazon, null);
    assert.match(p.mensajes[0], /Lo más caro NO es la plata/);
  });

  test('la perilla de alcance sigue funcionando: deshabilitar la 9 la escala', () => {
    OBJECIONES_HABILITADAS.delete(9);
    try {
      const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'pregunta_por_que' });
      assert.equal(p.handoffRazon, 'objecion_no_habilitada');
    } finally {
      OBJECIONES_HABILITADAS.add(9);
    }
  });

  test('H5: la Objecion 6 se ATIENDE en M1 antes de tratarla como ingreso', () => {
    // CASO REAL de la primera prueba: la lead respondio "es un dato delicado
    // para compartir por aqui" y el bot, sin atender la objecion, le pidio el
    // rango a secas. Lo que estaba mal no era preguntar por el rango: era no
    // reconocerle la objecion primero.
    const p = decidirTurno(estadoEn('M1_ENVIADO'),
      { ingreso_cop: null, objecion_num: 6, objecion_conocida: true },
      'es un dato delicado para compartir por aqui');
    assert.equal(p.handoffRazon, null, 'la 6 esta habilitada: la contesta el bot');
    assert.match(p.mensajes[0], /Esa info es sensible y no tienes por qué compartirla acá/,
      'la objecion se reconoce ANTES de volver a preguntar');
    assert.equal(p.campos.ultima_objecion_codigo, '6', 'queda registrada como objecion');
  });

  // Regla de negocio del fundador (3-sep-2026 (noche)): la Objecion 6 en M1 no remata
  // con la pregunta pendiente. Volver a pedir profesion + cifra exacta a quien
  // acaba de decir "ese dato es delicado" se lee como presion. Se le perdona la
  // profesion y se le pregunta solo por el rango, que se contesta con un "Si".
  test('O6 en M1: pide el RANGO, no la profesion ni la cifra exacta', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'),
      { ingreso_cop: null, objecion_num: 6, objecion_conocida: true },
      'no me gusta la idea de dar a conocer esos datos personales');
    const todo = p.mensajes.join('\n');

    assert.match(todo, /¿Estás en ese rango\?/, 'le ofrece el rango');
    assert.ok(!/¿A qué te dedicas y cuánto ganas al mes/.test(todo),
      'NO le vuelve a pedir la profesion ni la cifra exacta');
    assert.equal(p.mensajes.length, 2, 'empatia + pregunta del rango, nada mas');
    assert.ok(!/Te pregunto porque con eso puedo ver/.test(todo),
      'sin dos justificaciones seguidas arrancando igual');
  });

  test('O6 en M1: avanza a M1_RANGO_PREGUNTADO para que un "Si" valga', () => {
    // Sin esto el bot preguntaria por el rango pero seguiria escuchando en
    // M1_ENVIADO, donde un "Si" pelado no es respuesta valida de ingreso.
    const objecion = decidirTurno(estadoEn('M1_ENVIADO'),
      { ingreso_cop: null, objecion_num: 6, objecion_conocida: true },
      'ese dato es delicado');
    assert.equal(objecion.etapaNueva, 'M1_RANGO_PREGUNTADO');

    const siguiente = decidirTurno(estadoEn('M1_RANGO_PREGUNTADO'), { confirma_rango: true }, 'si');
    assert.equal(siguiente.etapaNueva, 'M2_ENVIADO', 'el "Si" confirma el Filtro 1');
    assert.equal(siguiente.handoffRazon, null, 'y no escala a un humano');
  });

  test('O6 fuera de M1 sigue reenviando su pregunta pendiente', () => {
    // El trato especial es SOLO para el Filtro 1. En M2 la objecion se contesta
    // y se vuelve a la pregunta del endeudamiento, como siempre.
    const p = decidirTurno(estadoEn('M2_ENVIADO'),
      { endeudamiento_pct: null, objecion_num: 6, objecion_conocida: true });
    const todo = p.mensajes.join('\n');
    assert.match(todo, /Te pregunto porque con eso puedo ver/, 'conserva la variante pre-pitch normal');
    assert.match(todo, /nivel de endeudamiento/, 'reenvia la pregunta pendiente de M2');
    assert.equal(p.etapaNueva, 'M2_ENVIADO', 'y no mueve de etapa');
  });

  test('H5: una objecion en M2 tampoco se lee como "no sabe"', () => {
    const p = decidirTurno(estadoEn('M2_ENVIADO'),
      { endeudamiento_pct: null, objecion_num: 6, objecion_conocida: true },
      'prefiero no dar ese dato por aca');
    assert.match(p.mensajes[0], /Esa info es sensible/);
  });

  test('H4: varios dolores se guardan todos, en el formato del dashboard', () => {
    const p = decidirTurno(estadoEn('M3_ENVIADO'), { dolores: ['C', 'B'], dolor_financiero: true });
    assert.equal(p.campos.dolor, 'B,C', 'ordenados y unidos por coma, como serializeDolor');
    assert.equal(p.etapaNueva, 'M4_ENVIADO');
  });

  test('H4: un solo dolor sigue guardandose igual que antes', () => {
    assert.equal(decidirTurno(estadoEn('M3_ENVIADO'), { dolores: ['B'] }).campos.dolor, 'B');
  });

  // El fundador abrio las 9 el 4-sep-2026. Lo que sigue yendo a un humano NO es
  // una objecion "no habilitada" sino una que no esta en el playbook.
  test('las 9 del playbook las contesta el bot', () => {
    for (const num of [1, 2, 3, 4, 5, 6, 7, 8, 9]) {
      const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: num, objecion_conocida: true });
      assert.equal(p.handoffRazon, null, `la objecion ${num} deberia contestarla el bot`);
      assert.ok(p.mensajes.length > 0, `la objecion ${num} no le mando nada al lead`);
    }
  });

  test('una objecion FUERA del playbook sigue yendo a un humano, sin copy', () => {
    const fuera = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_detectada: true, objecion_conocida: false });
    assert.equal(fuera.handoffRazon, 'objecion_fuera_playbook');
    assert.equal(fuera.mensajes.length, 0, 'no le manda copy al lead');
  });

  test('cerrar la perilla vuelve a mandar esa objecion a un humano', () => {
    // La perilla sigue siendo una perilla: se deriva de `habilitada` en la tabla.
    OBJECIONES_HABILITADAS.delete(7);
    try {
      const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 7, objecion_conocida: true });
      assert.equal(p.handoffRazon, 'objecion_no_habilitada');
      assert.equal(p.mensajes.length, 0, 'no le manda copy al lead');
    } finally {
      OBJECIONES_HABILITADAS.add(7);
    }
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

  // BUG P0 del 4-sep-2026. El fallback de "numero suelto" de
  // detectarEndeudamientoPct agarraba el 2 de "pago 2 millones al mes" y lo
  // reportaba como 2% de endeudamiento. 2% es EXCELENTE: el lead pasaba el
  // Filtro 2 con un dato inventado, en silencio. Ahora, si hay marca de plata,
  // el detector se abstiene y deja que el LLM aporte deuda_cop/remanente_cop
  // para que el router lo convierta contra el ingreso real.
  describe('endeudamiento: plata no es porcentaje', () => {
    const esPct = (t, esperado) => assert.equal(detectarEndeudamientoPct(t), esperado, JSON.stringify(t));

    test('un porcentaje de verdad se sigue leyendo', () => {
      esPct('Me da 30%', 30);
      esPct('30', 30);
      esPct('el 45', 45);
      esPct('40 por ciento', 40);
      esPct('25.5%', 25.5);
    });

    test('un monto en plata NO se lee como porcentaje', () => {
      for (const t of ['pago 2 millones al mes en deudas', 'me quedan 500 mil',
                       'gasto 1.5 millones', '$2.000.000', 'como 3 palos',
                       'debo 4M', 'unos 800 mil en tarjetas', '2 lucas']) {
        esPct(t, null);
      }
    });

    test('"no se" sigue devolviendo null, no cero', () => {
      esPct('no se', null);
      esPct('ni idea', null);
    });

    test('el router convierte el monto a % contra el ingreso conocido', () => {
      const estado = estadoEn('M2_ENVIADO');
      estado.salario_monto = 8_000_000;
      const p = decidirTurno(estado, { deuda_cop: 2_000_000 }, 'pago 2 millones al mes');
      assert.equal(p.campos.endeudamiento_pct, 25, '2M sobre 8M = 25%');
      assert.equal(p.handoffRazon, null, 'responder con plata no escala a un humano');
    });

    test('y el remanente tambien: lo que le SOBRA no es lo que DEBE', () => {
      const estado = estadoEn('M2_ENVIADO');
      estado.salario_monto = 10_000_000;
      const p = decidirTurno(estado, { remanente_cop: 4_000_000 }, 'me quedan 4 millones libres');
      assert.equal(p.campos.endeudamiento_pct, 60, 'gasta 6M de 10M = 60%');
    });
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

// ===========================================================================
// ESCALERA DE REPREGUNTAS (4-sep-2026)
//
// Decision del fundador: el bot escalaba demasiado pronto por ambiguedad. En
// vez de pasar a un humano al primer "no entendi", reformula UNA vez con una
// pregunta mas facil, y solo si ahi tampoco se entiende, escala.
//
// Se MIDIO antes de construirla: M1 y M2 ya preguntaban dos veces. Los unicos
// que escalaban al primer intento eran M4 y M5. Por eso son 2 peldaños, no 5.
//
// Va detras de una perilla porque su copy todavia no lo aprueba el fundador.
// ===========================================================================
describe('Escalera de repreguntas antes de escalar', () => {
  const st = (etapa) => ({
    estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana',
    salario_monto: 12_000_000, objeciones_consecutivas: 0,
    ultima_objecion_codigo: null, handoff_razon: null,
  });

  test('los filtros que YA preguntaban dos veces no ganaron un peldaño', () => {
    // Esto fija la medicion: si alguien agrega un reintento a M1 o M2 sin
    // darse cuenta de que ya tenian dos, este test lo atrapa.
    assert.equal(decidirTurno(st('M1_ENVIADO'),
      { ingreso_cop: null, ingreso_glosario: 'salario_integral' }).etapaNueva, 'M1_INGRESO_AMBIGUO');
    assert.equal(decidirTurno(st('M1_INGRESO_AMBIGUO'), { ingreso_cop: null }).handoffRazon, 'ambiguo');

    assert.equal(decidirTurno(st('M2_ENVIADO'), { endeudamiento_pct: null }).etapaNueva, 'M2_NO_SABE');
    assert.equal(decidirTurno(st('M2_NO_SABE'), { endeudamiento_pct: null }).handoffRazon, 'ambiguo');
  });

  describe('con la perilla APAGADA (estado actual)', () => {
    test('M4 y M5 escalan como siempre', () => {
      assert.equal(ESCALERA_REPREGUNTAS_HABILITADA, false,
        'si esto cambia, hay que mover estos tests al bloque de abajo');
      assert.equal(decidirTurno(st('M4_ENVIADO'), { urgencia: null }).handoffRazon, 'ambiguo');
      assert.equal(decidirTurno(st('M5_ENVIADO'), {}).handoffRazon, 'ambiguo');
    });
  });

  describe('con la perilla ENCENDIDA', () => {
    // Se simula el encendido llamando al router con la etapa del peldaño, que
    // es el estado al que llevaria la perilla. Asi se prueba la mitad que la
    // perilla no puede apagar: que el peldaño sea terminal.
    test('el peldaño de M4 NO ofrece otro peldaño: escala', () => {
      const p = decidirTurno(st('M4_URGENCIA_REINTENTO'), { urgencia: null });
      assert.equal(p.handoffRazon, 'ambiguo', 'del segundo intento se pasa a un humano');
      assert.notEqual(p.etapaNueva, 'M4_URGENCIA_REINTENTO', 'y NO se queda en bucle');
    });

    test('el peldaño de M5 NO ofrece otro peldaño: escala', () => {
      const p = decidirTurno(st('M5_PITCH_REINTENTO'), {});
      assert.equal(p.handoffRazon, 'ambiguo');
      assert.notEqual(p.etapaNueva, 'M5_PITCH_REINTENTO', 'y NO se queda en bucle');
    });

    test('si en el peldaño SI se entiende, el guion sigue normal', () => {
      const m4 = decidirTurno(st('M4_URGENCIA_REINTENTO'), { urgencia: 'ahora' });
      assert.equal(m4.etapaNueva, 'M5_ENVIADO', 'la urgencia leida en el peldaño vale igual');
      assert.equal(m4.estadoDestino, 'calificado');

      const m5 = decidirTurno(st('M5_PITCH_REINTENTO'), { acepta: true });
      assert.equal(m5.handoffRazon, null);
      assert.ok(m5.mensajes.join('\n').includes(CALENDAR_LINK), 'acepta -> se envia el link');
    });

    test('una objecion en el peldaño se atiende, no se escala', () => {
      const p = decidirTurno(st('M4_URGENCIA_REINTENTO'), { objecion_num: 3, objecion_conocida: true });
      assert.equal(p.handoffRazon, null);
      assert.ok(p.mensajes.length > 0);
    });
  });

  test('las etapas nuevas estan en los 4 sitios que exige la trampa', () => {
    for (const etapa of ['M4_URGENCIA_REINTENTO', 'M5_PITCH_REINTENTO']) {
      // sitio 3: preguntaPendiente tiene que saber que reenviar
      assert.ok(preguntaPendiente(etapa, 'Ana').length > 0,
        `${etapa} no tiene pregunta pendiente que reenviar`);
      // sitio 4: el switch la reconoce (no cae al default)
      const p = decidirTurno(st(etapa), { urgencia: 'ahora', acepta: true });
      assert.ok(p.etapaNueva !== etapa || p.handoffRazon,
        `${etapa} no la maneja el switch`);
    }
    // sitio 1 (CHECK de la base) se verifica en smoke_rpc.mjs;
    // sitio 2 (ESQUEMA_POR_ETAPA) en worker_seguridad.test.js.
  });

  test('el copy nuevo esta declarado como pendiente de aprobacion', () => {
    // Una plantilla nueva entra sola a la lista blanca del verificador. Sin
    // esta lista, copy sin aprobar pasaria la compuerta en silencio.
    assert.deepEqual(COPY_PENDIENTE_APROBACION, [
      'M2_PEDIR_SOBRANTE',    // segundo dato del borderline
      'M4_URGENCIA_REINTENTO',
      'M5_PITCH_REINTENTO',
    ]);
  });
});

// ===========================================================================
// LA BANDA DE TRAMPA $6M–$7M (4-sep-2026)
//
// El fundador bajo el Filtro 1 a $6M, pero el copy aprobado sigue preguntando
// por el rango de $7M. Todo lead que gane entre esas dos cifras CALIFICA y sin
// embargo contestaria "No" a la pregunta del rango. Este bloque existe para que
// ninguno de ellos se pierda mientras el copy no se alinee.
// ===========================================================================
describe('Banda de trampa entre el umbral y la cifra del copy', () => {
  const st = (etapa) => ({
    estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana',
    objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
  });

  test('quien gana dentro de la banda y da su cifra, CALIFICA', () => {
    for (const ingreso of [6_000_000, 6_500_000, 6_999_999]) {
      const p = decidirTurno(st('M1_ENVIADO'), { ingreso_cop: ingreso });
      assert.notEqual(p.estadoDestino, 'descalificado',
        `${ingreso} esta por encima del umbral y no puede descalificarse`);
      assert.equal(p.etapaNueva, 'M2_ENVIADO');
    }
  });

  test('quien gana en la banda y dice "No" al rango SE PIERDE, y es a proposito', () => {
    // Decision comercial del fundador: se prefiere perder estos leads antes que
    // gastar un turno pidiendo la cifra. Este test existe para que la perdida
    // sea VISIBLE y deliberada, no un descuido que alguien "arregle" sin saber.
    const p = decidirTurno(st('M1_RANGO_PREGUNTADO'), { confirma_rango: false }, 'no');
    assert.equal(p.estadoDestino, 'descalificado');
  });

  test('por debajo del umbral si se descalifica, con o sin rango', () => {
    assert.equal(decidirTurno(st('M1_ENVIADO'), { ingreso_cop: 3_000_000 }).estadoDestino, 'descalificado');
    assert.equal(decidirTurno(st('M1_RANGO_PREGUNTADO'), { ingreso_cop: 3_000_000 }).estadoDestino, 'descalificado');
  });

  test('el copy del rango y el umbral estan desalineados A PROPOSITO', () => {
    // No es un bug pendiente: es la decision comercial. Si algun dia se alinean,
    // este test avisa para que se revise el descarte directo del "No".
    assert.ok(PLANTILLAS.M1_PEDIR_RANGO.includes('$7M'),
      'el copy del rango sigue siendo el aprobado, con $7M');
    assert.equal(UMBRALES.INGRESO_MINIMO, 6_000_000);
    assert.ok(UMBRALES.INGRESO_ASUMIDO_POR_RANGO > UMBRALES.INGRESO_MINIMO,
      'la banda existe y se asume; si esto deja de ser cierto, revisa el case M1_RANGO_PREGUNTADO');
  });
});

// ===========================================================================
describe('M3: "todas" (fundador, 4-sep-2026)', () => {
  const st = (etapa) => ({
    estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana',
    objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
  });

  test('"todas" y sus variantes cuentan como A+B+C+D', () => {
    for (const t of ['todas', 'todas las anteriores', 'me pasan todas',
                     'todo lo anterior', 'la verdad todas me pasan', 'las cuatro']) {
      assert.deepEqual(detectarDolorLetras(t), ['A', 'B', 'C', 'D'], JSON.stringify(t));
    }
  });

  test('elegir "todas" salta la pregunta por el detalle de la D', () => {
    // La excepcion que pidio el fundador: a quien le pasan todas no hay que
    // preguntarle "¿cual es esa otra?". Funciona porque "todas" arrastra A, B y
    // C, que ya califican emocionalmente.
    const p = decidirTurno(st('M3_ENVIADO'), { dolores: ['A', 'B', 'C', 'D'] }, 'todas');
    assert.equal(p.etapaNueva, 'M4_ENVIADO', 'no se queda pidiendo el detalle');
    assert.notEqual(p.etapaNueva, 'M3_RECONDUCIR');
    assert.equal(p.campos.dolor, 'A,B,C,D');
  });

  test('la D SOLA y sin detalle sigue reconduciendo', () => {
    // Y M3_RECONDUCIR ya pregunta y valida si el tema es financiero, que es lo
    // que pedia el flujo: no hizo falta copy nuevo.
    const p = decidirTurno(st('M3_ENVIADO'), { dolores: ['D'], dolor_financiero: false }, 'otra cosa');
    assert.equal(p.etapaNueva, 'M3_RECONDUCIR');
    assert.match(p.mensajes[0], /¿O tu frustración está conectada con/);
  });

  test('"todo" o "toda" en otra frase no dispara el atajo', () => {
    // Falso positivo peligroso: "no me alcanza para todo el mes" no es "todas".
    assert.notDeepEqual(detectarDolorLetras('no me alcanza para todo el mes'), ['A', 'B', 'C', 'D']);
  });
});

// ===========================================================================
// EL CIERRE, EN SU ORDEN NUEVO (fundador, 4-sep-2026)
//   M5 pitch -> M6 LINK SOLO -> M7 acompañante -> M8 (CIERRE_PRECALL)
//
// El orden viejo mandaba la pregunta del acompañante JUNTO al link, y por eso
// un "emm si" del lead era ambiguo: podia contestar al acompañante o al "¿ya
// agendaste?". En el QA el LLM lo leyo como agendamiento y salto hasta el
// cierre, omitiendo el link. Separar los turnos elimina la ambiguedad de raiz.
// ===========================================================================
describe('Cierre M5 -> M6 -> M7 -> M8', () => {
  const st = (etapa, extra = {}) => ({
    estado_codigo: 'calificado', etapa_bot: etapa, nombre: 'Ana',
    salario_monto: 12_000_000, objeciones_consecutivas: 0,
    ultima_objecion_codigo: null, handoff_razon: null, ...extra,
  });

  test('M5 + acepta -> SOLO el link, y es la ultima burbuja', () => {
    const p = decidirTurno(st('M5_ENVIADO'), { acepta: true });
    assert.equal(p.etapaNueva, 'M6_ENVIADO');
    assert.equal(p.mensajes[p.mensajes.length - 1].trim(), CALENDAR_LINK,
      'el link va de ultimo y solo');
    assert.ok(!p.mensajes.join('\n').includes('asistirás solo tú'),
      'la pregunta del acompañante YA NO va en este turno: era la fuente de la ambiguedad');
    assert.equal(p.permitirEmpatia, false, 'el turno del link nunca lleva apertura generada');
  });

  test('M6 + confirma que agendo -> AHORA si la pregunta del acompañante', () => {
    const p = decidirTurno(st('M6_ENVIADO'), { confirmo_agendo: true }, 'listo, ya agende');
    assert.equal(p.etapaNueva, 'M7_ENVIADO');
    assert.match(p.mensajes.join('\n'), /asistirás solo tú/);
    assert.ok(!p.mensajes.join('\n').includes(CALENDAR_LINK), 'no reenvia el link porque si');
  });

  test('M6 sin confirmar: se queda esperando, no avanza ni manda link de nuevo', () => {
    const p = decidirTurno(st('M6_ENVIADO'), {}, 'ok');
    assert.equal(p.etapaNueva, 'M6_ENVIADO');
    assert.ok(!p.mensajes.join('\n').includes(CALENDAR_LINK));
  });

  test('M7 + responde el acompañante -> cierra con M8', () => {
    for (const [acompanado, marca] of [[false, /Perfecto/], [true, /coordina/i]]) {
      const p = decidirTurno(st('M7_ENVIADO'), { acompanado });
      assert.equal(p.etapaNueva, 'CIERRE_PRECALL', 'la respuesta del acompañante cierra');
      assert.match(p.mensajes.join('\n'), /estimado total de créditos/, 'se envia M8');
      assert.equal(p.campos.asiste_acompanado, acompanado);
      assert.notEqual(p.estadoDestino, 'agendado', 'JAMAS escribe agendado');
      assert.ok(marca);
    }
  });

  test('M7 sin entender la respuesta: repregunta, NO adivina', () => {
    // Adivinar aca fue exactamente lo que rompio el QA.
    const p = decidirTurno(st('M7_ENVIADO'), {}, 'emm');
    assert.equal(p.etapaNueva, 'M7_ENVIADO');
    assert.match(p.mensajes[0], /asistirás solo tú/);
    assert.notEqual(p.etapaNueva, 'CIERRE_PRECALL');
  });

  test('el camino feliz completo respeta el orden nuevo', () => {
    let etapa = 'M5_ENVIADO';
    const pasos = [
      [{ acepta: true }, 'M6_ENVIADO'],
      [{ confirmo_agendo: true }, 'M7_ENVIADO'],
      [{ acompanado: false }, 'CIERRE_PRECALL'],
    ];
    for (const [pista, esperada] of pasos) {
      const p = decidirTurno(st(etapa), pista);
      assert.equal(p.etapaNueva, esperada, `desde ${etapa}`);
      etapa = p.etapaNueva;
    }
  });

  test('"¿donde me agendo?" reenvia el link APROBADO, aislado', () => {
    // El LLM SEÑALA que lo pide; nunca teclea la URL. Un link generado seria a
    // la vez una violacion de la regla del link y un vector de suplantacion.
    for (const etapa of ['M6_ENVIADO', 'M7_ENVIADO']) {
      const p = decidirTurno(st(etapa), { pide_link: true }, 'donde me agendo?');
      assert.equal(p.mensajes[p.mensajes.length - 1].trim(), CALENDAR_LINK,
        `${etapa}: el link reenviado va solo y de ultimo`);
      assert.equal(p.permitirEmpatia, false, `${etapa}: sin apertura generada en un turno con link`);
    }
  });

  test('el cierre admite apertura personalizada, salvo los turnos con link', () => {
    assert.equal(decidirTurno(st('M6_ENVIADO'), { confirmo_agendo: true }).permitirEmpatia, true);
    assert.equal(decidirTurno(st('M7_ENVIADO'), { acompanado: false }).permitirEmpatia, true);
    assert.equal(decidirTurno(st('M5_ENVIADO'), { acepta: true }).permitirEmpatia, false);
  });
});

// ===========================================================================
describe('Dolor financiero: raíces de dinero (QA 4-sep-2026)', () => {
  // BUG PROPIO: la primera versión escribió las raíces con `\b` AL FINAL
  // (`\bahorr\b`), y `\b` no cierra entre dos letras -- así que `ahorr`,
  // `invers`, `financier` y `econom` no casaban NADA. Por eso una lead que
  // escribió "d. quiero ahorrar" salió por M3_RECONDUCIR.
  // Es la misma trampa del `\b` que ya costó una vez con las vocales acentuadas.
  test('las raíces de dinero casan de verdad', () => {
    for (const t of ['d. quiero ahorrar', 'quiero ahorrar', 'ahorro', 'ahorros',
                     'quiero invertir', 'inversion', 'inversiones',
                     'mi tema es financiero', 'problemas economicos',
                     'quiero construir patrimonio', 'pensando en mi futuro',
                     'quiero mi pension', 'busco rentabilidad']) {
      assert.equal(pareceDolorFinanciero(t), true, JSON.stringify(t));
    }
  });

  test('lo que ya funcionaba sigue funcionando', () => {
    for (const t of ['tengo deudas', 'debo mucho', 'no me alcanza', 'me cobran intereses',
                     'pago tres tarjetas', 'gano 8 millones', 'me pagan en pesos']) {
      assert.equal(pareceDolorFinanciero(t), true, JSON.stringify(t));
    }
  });

  test('y NO se traga lo que no es de dinero', () => {
    for (const t of ['mi problema es con mi pareja', 'tengo ansiedad', 'mi jefe me estresa',
                     'problemas de salud', 'quiero bajar de peso', 'subir de peso']) {
      assert.equal(pareceDolorFinanciero(t), false, JSON.stringify(t));
    }
  });

  test('"quiero ahorrar" en M3 ya NO sale por reconducir', () => {
    // El caso exacto del QA. Se simula el LLM fallando (dolor_financiero:false):
    // el determinista tiene que rescatarlo igual.
    const p = decidirTurno(
      { estado_codigo: 'contactado', etapa_bot: 'M3_ENVIADO', nombre: 'Marly',
        objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null },
      { dolores: ['D'], dolor_financiero: false, dolor_detalle: 'quiero ahorrar' },
      'd. quiero ahorrar',
    );
    assert.equal(p.etapaNueva, 'M4_ENVIADO');
    assert.ok(!p.mensajes.join('\n').includes('puede que no seamos el mejor fit'));
  });
});

// ===========================================================================
describe('Varias fuentes de ingreso (QA 4-sep-2026)', () => {
  // La lead escribió: "en mi trabajo son más o menos 4 millones, de mi negocio
  // familiar son 3 millones, y de un local donde soy socia recibo casi 4
  // millones" = 11M. El parser agarraba la PRIMERA cifra (4M) y, como los
  // deterministas GANAN sobre el LLM, tapaba la suma correcta del modelo. La
  // descalificó, y la lead tuvo que reclamar.
  const CASO_QA = 'tengo ingresos de diferentes fuentes, en mi trajo son mas o menos 4 millones, '
    + 'de mi negocio familiar son 3 millones, y de un local donde soy socia recibo casi 4 millones';

  test('ante varias cifras el parser SE ABSTIENE en vez de adivinar', () => {
    const r = parseIngresoCOP(CASO_QA);
    assert.equal(r.monto, null, 'no puede quedarse con la primera cifra');
    assert.equal(r.ambiguo, true);
    assert.equal(r.glosario, 'varias_fuentes');
  });

  test('una sola cifra se sigue leyendo igual que siempre', () => {
    assert.equal(parseIngresoCOP('gano 8 millones').monto, 8_000_000);
    assert.equal(parseIngresoCOP('soy ingeniero y gano 12 millones netos').monto, 12_000_000);
    assert.equal(parseIngresoCOP('12.000.000').monto, 12_000_000);
  });

  test('un RANGO es una sola idea, no dos fuentes', () => {
    // Abstenerse de más también cuesta: "entre 8 y 10 millones" es una cifra.
    assert.equal(cuentaCifrasDeDinero('entre 8 y 10 millones'), 1);
    assert.notEqual(parseIngresoCOP('entre 8 y 10 millones').monto, null);
  });

  test('con la suma del LLM, el lead del QA YA NO se descalifica', () => {
    const estado = estadoEn('M1_RANGO_PREGUNTADO');
    const p = decidirTurno(estado, { ingreso_cop: 11_000_000 }, CASO_QA);
    assert.notEqual(p.estadoDestino, 'descalificado');
    assert.equal(p.etapaNueva, 'M2_ENVIADO');
  });

  test('y si el LLM tampoco pudo sumar, se le pide el TOTAL (nunca se descarta)', () => {
    const p = decidirTurno(estadoEn('M1_ENVIADO'),
      { ingreso_cop: null, ingreso_glosario: 'varias_fuentes' }, CASO_QA);
    assert.notEqual(p.estadoDestino, 'descalificado', 'jamas se descarta sobre ambiguo');
    assert.equal(p.etapaNueva, 'M1_INGRESO_AMBIGUO');
    assert.match(p.mensajes[0], /me confirmas el número aproximado/);
  });
});

// ===========================================================================
describe('Hostilidad: la frustración NO es hostilidad', () => {
  test('el detector determinista no marca quejas', () => {
    // El QA del 4-sep escaló por "no gracias, eso es inaceptable las
    // confusiones". El determinista NO disparó (correcto); fue el LLM, que no
    // tenía ni una línea de definición en el prompt. Este test fija el lado
    // determinista para que nadie lo "endurezca" por error.
    for (const t of ['no gracias, eso es inaceptable las confusiones',
                     'que confusion',
                     'me estas haciendo perder el tiempo',
                     'no me estas entendiendo',
                     'esto esta mal']) {
      assert.equal(detectarHostilidad(t), false, JSON.stringify(t));
    }
  });

  test('la hostilidad de verdad sí se marca', () => {
    for (const t of ['eres un estafador', 'no me escribas mas', 'idiota', 'esto es una estafa']) {
      assert.equal(detectarHostilidad(t), true, JSON.stringify(t));
    }
  });
});

// ===========================================================================
describe('Detectores del cierre (QA 4-sep-2026)', () => {
  // El QA mandó el link a quien escribió "espérame, antes me gustaría tener más
  // claro de que trata el protocolo". `detectarAceptacion` devolvía true porque
  // "claro" casaba dentro de "más claro", y el freno de negación solo miraba
  // los primeros 12 caracteres.
  test('pedir información NO es aceptar', () => {
    for (const t of ['esperame, antes me gustaria tener mas claro de que trata el protocolo',
                     'quiero tener mas claro el tema', 'espera, primero dime el precio',
                     'no, todavia no', 'aun no', 'pero primero una pregunta']) {
      assert.equal(detectarAceptacion(t), false, JSON.stringify(t));
    }
  });

  test('aceptar de verdad se sigue detectando', () => {
    for (const t of ['si, agendemos', 'dale', 'listo', 'claro', 'claro que si',
                     'de una', 'perfecto, hagamoslo', 'me sirve']) {
      assert.equal(detectarAceptacion(t), true, JSON.stringify(t));
    }
  });

  test('el acompañante se nombra sin preposición y también cuenta', () => {
    // La gente contesta "va mi esposa", no "con mi esposa". Antes solo se
    // detectaba la forma con "con...".
    for (const t of ['va mi esposa', 'con mi pareja', 'estaria mi socio', 'mi mama tambien']) {
      assert.equal(detectarAcompanante(t), true, JSON.stringify(t));
    }
    for (const t of ['voy solo', 'solo yo', 'nadie mas']) {
      assert.equal(detectarAcompanante(t), false, JSON.stringify(t));
    }
  });

  test('"voy solo" gana aunque mencione a alguien', () => {
    // "voy solo, mi esposa trabaja" es un NO. Si se evaluara la persona primero
    // se leería al revés.
    assert.equal(detectarAcompanante('no, voy solo, mi esposa trabaja'), false);
  });

  test('una objeción en M5 se atiende ANTES de leerla como aceptación', () => {
    // La regla ya existía en M1 y M2; en M5 faltaba, y costó un link enviado a
    // quien había dicho "espérame".
    const p = decidirTurno(
      { estado_codigo: 'calificado', etapa_bot: 'M5_ENVIADO', nombre: 'Ana',
        salario_monto: 12_000_000, objeciones_consecutivas: 0,
        ultima_objecion_codigo: null, handoff_razon: null },
      { objecion_num: 8, objecion_conocida: true, acepta: true },
      'esperame, antes quiero saber que es el protocolo',
    );
    assert.equal(p.etapaNueva, 'M5_ENVIADO', 'no avanza');
    assert.ok(!p.mensajes.join('\n').includes(CALENDAR_LINK),
      'y NO le manda el link a quien pidió esperar');
    assert.match(p.mensajes.join('\n'), /Protocolo de Reconexión Financiera/);
  });
});

// ===========================================================================
// PROBLEMA 1 (5-sep-2026): el LLM confundia "no se/no estoy segura"
// (incertidumbre) con la Objecion 6 "info sensible" (reticencia). El bot
// anteponia la plantilla de "dato sensible" y repetia P.M2_P1/P.M2_P2 tal cual
// en vez de usar M2_NO_SABE, que ya existia para este caso exacto.
// ===========================================================================
describe('Incertidumbre de endeudamiento vs Objecion 6 (bug real 5-sep-2026)', () => {
  test('pareceIncertidumbre distingue "no se" de una reticencia real', () => {
    assert.equal(pareceIncertidumbre('no se, la verdad'), true);
    assert.equal(pareceIncertidumbre('no estoy segura de cuanto debo'), true);
    assert.equal(pareceIncertidumbre('ni idea'), true);
    assert.equal(pareceIncertidumbre('no tengo idea de mi endeudamiento'), true);
    assert.equal(pareceIncertidumbre('prefiero no dar esa info por aqui'), false);
    assert.equal(pareceIncertidumbre('eso es informacion privada'), false);
    assert.equal(pareceIncertidumbre(''), false);
  });

  test('BUG REAL: un "no se" que el LLM marca como Objecion 6 ya NO repite la pregunta inicial', () => {
    // Antes: cae en manejarObjecion y manda OBJ_6 + P.M2_P1/P.M2_P2 de nuevo.
    const p = decidirTurno(estadoEn('M2_ENVIADO'),
      { endeudamiento_pct: null, objecion_num: 6, objecion_conocida: true },
      'no se, la verdad no estoy segura');
    assert.equal(p.etapaNueva, 'M2_NO_SABE');
    assert.match(p.mensajes.join('\n'), /dame un estimado/i);
  });

  test('el mismo caso en M2_NO_SABE (insiste con "no se") SI escala, no repite otra vez', () => {
    const p = decidirTurno(estadoEn('M2_NO_SABE'),
      { endeudamiento_pct: null, objecion_num: 6, objecion_conocida: true }, 'no se, de verdad no tengo idea');
    assert.equal(p.handoffRazon, 'ambiguo');
  });

  test('una reticencia real (sin "no se") SIGUE yendo a la Objecion 6 -- no se rompe el caso bueno', () => {
    const p = decidirTurno(estadoEn('M2_ENVIADO'),
      { endeudamiento_pct: null, objecion_num: 6, objecion_conocida: true },
      'prefiero no dar esa info por aqui');
    assert.notEqual(p.etapaNueva, 'M2_NO_SABE');
    assert.match(p.mensajes.join('\n'), /sensible/i);
  });
});

// ===========================================================================
// PROBLEMA 2 (5-sep-2026): P.SIN_HORARIOS pregunta la franja, pero el turno
// saltaba directo a un HANDOFF no recuperable -- la respuesta del lead a esa
// misma pregunta caia en silencio total (decidirSiResponder cortaba antes de
// que el bot volviera a hablar).
// ===========================================================================
describe('SIN_HORARIOS ya no deja al lead en visto (bug real 5-sep-2026)', () => {
  test('sin_horarios en M6/M7/M7_ESPERANDO_VINCULO va a un estado intermedio, no directo a HANDOFF', () => {
    for (const etapa of ['M6_ENVIADO', 'M7_ENVIADO', 'M7_ESPERANDO_VINCULO']) {
      const p = decidirTurno(estadoEn(etapa), { sin_horarios: true }, 'no me aparece nada');
      assert.equal(p.etapaNueva, 'SIN_HORARIOS_ESPERANDO_FRANJA', `${etapa}: debe esperar la franja, no cerrar ya`);
      assert.equal(p.handoffRazon, 'agendamiento_manual_pendiente', `${etapa}: el Setter se entera YA, sin regresion`);
    }
  });

  test('decidirSiResponder deja pasar UN turno mas en SIN_HORARIOS_ESPERANDO_FRANJA aunque el handoff ya este puesto', () => {
    const estado = estadoEn('SIN_HORARIOS_ESPERANDO_FRANJA', { handoff_razon: 'agendamiento_manual_pendiente' });
    const r = decidirSiResponder(estado);
    assert.equal(r.responder, true);
    assert.equal(r.razon, 'cerrando_franja_sin_horarios');
  });

  test('BUG REAL: la respuesta a "que franja te queda bien" ya NO cae en silencio', () => {
    const estado = estadoEn('SIN_HORARIOS_ESPERANDO_FRANJA', { handoff_razon: 'agendamiento_manual_pendiente' });
    assert.equal(decidirSiResponder(estado).responder, true, 'el gate debe dejarlo pasar');

    const p = decidirTurno(estado, {}, 'los sábados en la mañana');
    assert.ok(p.mensajes.length > 0, 'no se queda mudo');
    assert.equal(p.etapaNueva, 'HANDOFF', 'y despues si cierra para siempre');
    assert.equal(p.handoffRazon, 'agendamiento_manual_pendiente');
    assert.match(p.summary, /sábados en la mañana/, 'la franja queda anotada para el Setter');
  });

  test('sin catch-all (respuesta_empatica vacia), usa el cierre determinista -- nunca se queda sin mensaje', () => {
    const estado = estadoEn('SIN_HORARIOS_ESPERANDO_FRANJA', { handoff_razon: 'agendamiento_manual_pendiente' });
    const p = decidirTurno(estado, { respuesta_empatica: '' }, 'los sábados en la mañana');
    assert.match(p.mensajes[0], /Ya le avisé al equipo/);
  });

  test('otra vez en SIN_HORARIOS_ESPERANDO_FRANJA (ya cerrado) el gate vuelve a callar para siempre', () => {
    // Tras el case, la etapa pasa a HANDOFF -- el carve-out ya no aplica.
    const estado = estadoEn('HANDOFF', { handoff_razon: 'agendamiento_manual_pendiente' });
    assert.equal(decidirSiResponder(estado).responder, false, 'sin guarda anti-bucle no habria limite');
  });
});
