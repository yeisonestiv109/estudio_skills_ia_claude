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
  topeEndeudamiento,
  decidirSiResponder, decidirTurno,
  detectarVarianteM1, detectarConfirmacionAgenda, detectarAcompanante,
  detectarUrgencia, detectarDolorLetra, detectarDolorLetras, detectarHostilidad, detectarEndeudamientoPct,
  detectarAceptacion,
  pareceRemanente, esSoloPalabraClave, detectarSinHorarios, detectarSiNo, pareceDolorFinanciero,
  pareceIncertidumbre,
  etapaParaRetomar, cuentaCifrasDeDinero,
  preguntaPendiente, reencauzar,
} from '../bot_router_v42.js';
import {
  CALENDAR_LINK, CALENDAR_ARTF, CALENDAR_PRUEBAS, UMBRALES, OBJECIONES_HABILITADAS, PLANTILLAS,
  ESCALERA_REPREGUNTAS_HABILITADA, COPY_PENDIENTE_APROBACION, LIMPIAR_HANDOFF,
  CONOCIMIENTO_PLAYBOOK,
} from '../sop_v42_plantillas.js';

// Helper: estado como lo devuelve fn_bot_get_estado
const estadoEn = (etapa, extra = {}) => ({
  estado_codigo: 'contactado', es_terminal: false, etapa_bot: etapa,
  nombre: 'Ana', salario_monto: null, endeudamiento_pct: null,
  objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
  ...extra,
});

// ====================================================================

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

// ====================================================================

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

  // ═══════════════════════════════════════════════════════════════════════
  // REGLA NUEVA DEL FILTRO 2 (7-sep-2026). Estos tres tests se REESCRIBIERON:
  // el criterio dejo de ser "cuanta plata le queda" y paso a ser "que
  // porcentaje de su ingreso se le va en deudas", con un tope que sube con el
  // ingreso. No se borro ninguno -- cada uno fija ahora la regla nueva.
  //
  // Decidido con la medicion delante: contra los 20 leads reales de la base
  // que tienen ingreso Y endeudamiento, 8 (40%) que pasaban directo ahora van
  // a la verificacion del calculo. Se eligio el tope estricto a sabiendas.
  // ═══════════════════════════════════════════════════════════════════════
  test('Filtro 2: el criterio es el tope de endeudamiento segun el ingreso', () => {
    // Menos de 9M -> tope 50%.
    assert.equal(topeEndeudamiento(6_000_000), 50);
    assert.equal(topeEndeudamiento(8_999_999), 50);
    // 9M o mas -> tope 60%.
    assert.equal(topeEndeudamiento(9_000_000), 60);
    assert.equal(topeEndeudamiento(25_000_000), 60);
    // El limite exacto pasa: es "hasta el tope", no "por debajo del tope".
    assert.equal(evaluarEndeudamiento(50, 8_000_000), 'ok');
    assert.equal(evaluarEndeudamiento(60, 10_000_000), 'ok');
    // Un punto por encima ya va a verificar el calculo.
    assert.equal(evaluarEndeudamiento(51, 8_000_000), 'verificar_calculo');
    assert.equal(evaluarEndeudamiento(61, 10_000_000), 'verificar_calculo');
  });

  test('por encima del tope NUNCA se descalifica de una: primero se verifica', () => {
    // Es la regla que evita botar a alguien por una cuenta mal hecha. Ni el
    // caso mas extremo sale directo a descalificado.
    assert.equal(evaluarEndeudamiento(99, 30_000_000), 'verificar_calculo');
    assert.equal(evaluarEndeudamiento(100, 6_000_000), 'verificar_calculo');
    // `evaluarEndeudamiento` ya no devuelve 'borderline' ni 'descalifica':
    // esas dos decisiones ahora viven mas adelante en el embudo.
    const salidas = new Set();
    for (let ing = 1_000_000; ing <= 30_000_000; ing += 250_000) {
      for (let d = 0; d <= 100; d += 1) salidas.add(evaluarEndeudamiento(d, ing));
    }
    assert.deepEqual([...salidas].sort(), ['ok', 'verificar_calculo']);
  });

  test('el mismo % da distinto segun el ingreso: eso es el punto del cambio', () => {
    // 60% de deuda: quien gana 6M esta sobre su tope (50%) y va a verificar;
    // quien gana 10M esta justo en su tope (60%) y pasa.
    assert.equal(evaluarEndeudamiento(60, 6_000_000), 'verificar_calculo');
    assert.equal(evaluarEndeudamiento(60, 10_000_000), 'ok');
  });

  test('el escalon de los 9M premia al reves en plata, y es intencional', () => {
    // Efecto medido y aprobado a sabiendas por el fundador: quien gana 8,99M
    // pasa con 4,50M libres; quien gana 9,00M pasa con 3,60M. El que gana MAS
    // puede quedar con MENOS plata libre. El filtro es de habito de
    // endeudamiento, no de liquidez. Si algun dia se quiere lo contrario, hay
    // que volver a meter el piso de remanente como segunda condicion, y este
    // test es el que hay que reescribir.
    assert.equal(evaluarEndeudamiento(50, 8_999_999), 'ok');
    assert.equal(evaluarEndeudamiento(60, 9_000_000), 'ok');
    assert.ok(calcularRemanente(9_000_000, 60) < calcularRemanente(8_999_999, 50));
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

// ====================================================================

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

  // Reescrito el 5-sep-2026: el fundador prohibio mandarle al lead la misma
  // pregunta dos veces. Antes este test fijaba el bug -- "retoma en
  // M2_ENVIADO" significaba REENVIAR "Sin presion, dame un estimado..." pese
  // a que el mensaje de vuelta YA traia el 40% ("me da 40%"). Ahora, si el
  // dato que falta llega en el mismo mensaje de recuperacion, se avanza
  // derecho (aca a M3) en vez de repreguntar algo que el lead ya contesto.
  test('handoff recuperable + el lead pide seguir CON el dato: avanza derecho, no repregunta', () => {
    // El caso exacto del QA: "pero igual quiero seguir, me da 40%".
    const estado = estadoEn('HANDOFF', {
      handoff_razon: 'contenido_hostil', salario_monto: 11_000_000,
    });
    const p = decidirTurno(estado, { recupera_handoff: true, endeudamiento_pct: 40 },
      'pero igual quiero seguir, me da 40%');
    assert.equal(p.handoffRazon, LIMPIAR_HANDOFF, 'limpia el handoff');
    assert.equal(p.etapaNueva, 'M3_ENVIADO', 'el 40% SI resuelve el Filtro 2: avanza, no se queda pidiendo el mismo dato');
    assert.ok(p.mensajes.length > 0, 'y le vuelve a hablar');
    assert.ok(!/Sin presión, dame un estimado/.test(p.mensajes.join('\n')), 'nunca repite la pregunta que el mensaje ya contesto');
    assert.equal(p.permitirEmpatia, true, 'viene de un roce: la apertura personalizada importa');
  });

  // Reescrito el 6-sep-2026 (bug real, Marly): antes esto re-escalaba en
  // silencio -- CERO mensajes -- porque M2_NO_SABE escalaba de una al
  // segundo "no se". Ahora M2 usa reencauzar() como M4/M5 (decision
  // explicita de Gaby): al recuperarse del handoff sigue sin dato, pero se
  // le da un intento mas con contexto en vez de re-escalar mudo.
  test('handoff recuperable + el lead pide seguir SIN el dato: reencauza, no re-escala mudo', () => {
    const estado = estadoEn('HANDOFF', {
      handoff_razon: 'ambiguo', salario_monto: 11_000_000,
    });
    const p = decidirTurno(estado, { recupera_handoff: true }, 'pues sigo sin saber bien');
    assert.equal(p.handoffRazon, LIMPIAR_HANDOFF, 'se recupera: todavia no es la 3ra vez con la misma duda');
    assert.equal(p.etapaNueva, 'M2_NO_SABE', 'se queda insistiendo, no re-escala de una');
    assert.ok(p.mensajes.length > 0, 'no se queda mudo');
  });

  // POLITICA NUEVA (6-sep-2026): insistir sin dar el dato YA NO re-escala. El
  // lead confuso se atiende; lo que escala es que el LLM lleve N turnos caido.
  test('handoff recuperable + SIN el dato por 3ra vez: se le sigue atendiendo', () => {
    const estado = estadoEn('HANDOFF', {
      handoff_razon: 'ambiguo', salario_monto: 11_000_000, ambiguedad_consecutiva: 2,
    });
    const p = decidirTurno(estado, { recupera_handoff: true, es_duda_nueva: false }, 'sigo sin saber');
    assert.equal(p.handoffRazon, LIMPIAR_HANDOFF, 'se recupera, no se re-escala');
    assert.ok(p.mensajes.length > 0, 'y si le habla');
  });

  test('sin LLM se escala de INMEDIATO: no se adivina lo que dijo el lead', () => {
    // Regla de Gaby (6-sep-2026): "si Groq se cae prefiero que escale a humano
    // antes que dejar que un regex ciego adivine y le mande un calendario a
    // alguien que dijo 'claro que no quiero'". Ya no se cuentan 3 turnos.
    const estado = estadoEn('HANDOFF', {
      handoff_razon: 'ambiguo', salario_monto: 11_000_000,
    });
    const p = decidirTurno(estado, { recupera_handoff: true, llm_fallo: true }, 'sigo sin saber');
    assert.equal(p.etapaNueva, 'HANDOFF');
    assert.equal(p.handoffRazon, 'error_tecnico', 'la razon es tecnica, no del lead');
    assert.equal(p.mensajes.length, 0);
  });

  // BUG REAL reportado (5-sep-2026): "no lo se, no estoy segura" (fallback
  // exitoso, escala a HANDOFF ambiguo) -> lead responde en DOS mensajes:
  // "pues si me queda no se cuanto exactamente" (msg 1, sin cifra) y "por ahi
  // unos 4m" (msg 2). El msg 1 re-escala (ya cubierto arriba); el msg 2 es
  // este test: llega con el lead YA en HANDOFF, y antes NUNCA se clasificaba
  // (HANDOFF no tenia esquema de LLM -> recupera_handoff nunca podia ser
  // true). Aca se simula lo que el LLM real deberia extraer ahora que
  // ESQUEMA_POR_ETAPA.HANDOFF existe: remanente_cop=4_000_000.
  test('BUG REAL: remanente dado en un mensaje separado tras el handoff avanza sin repreguntar', () => {
    const estado = estadoEn('HANDOFF', {
      handoff_razon: 'ambiguo', salario_monto: 10_000_000,
    });
    const p = decidirTurno(estado,
      { recupera_handoff: true, remanente_cop: 4_000_000 },
      'por ahi unos 4m');
    // deuda = 10M - 4M = 6M -> 60% de 10M -> remanente ya calculado = 4M >= 2.5M -> ok
    assert.equal(p.handoffRazon, LIMPIAR_HANDOFF);
    assert.equal(p.etapaNueva, 'M3_ENVIADO', 'el remanente de 4M SI alcanza (>= 2.5M): avanza al dolor');
    assert.ok(!/Sin presión, dame un estimado/.test(p.mensajes.join('\n')));
  });

  // BUG REAL reportado (5-sep-2026): tras la Objecion 9 en M4 ("cual es la
  // diferencia si lo hago ahora o despues?"), el lead escribio "como asi?"
  // (confusion, no aceptacion) -> escalo a HANDOFF ambiguo en silencio.
  // Despues escribio "pero si agendemos" -- el codigo viejo solo reenviaba la
  // pregunta de urgencia (P.M4_P2), IGNORANDO la "bifurcacion oficial
  // post-Objecion 9" que ya existe en el case M4_ENVIADO (aceptar ahi debe
  // mandar el pitch real de M5, no repetir la pregunta). El replay generalizado
  // deja que esa logica corra de verdad.
  test('BUG REAL: aceptar tras la Objecion 9, ya en HANDOFF, manda el pitch real -- no repite la pregunta de urgencia', () => {
    const estado = estadoEn('HANDOFF', {
      handoff_razon: 'ambiguo', salario_monto: 10_000_000, endeudamiento_pct: 40,
      dolor: 'B', ultima_objecion_codigo: '9',
    });
    // La clasificacion viene del esquema de HANDOFF: no pregunta "acepta" ni
    // "urgencia" (esos campos no existen ahi) -- solo recupera_handoff.
    // `acepta` lo aporta ahora el LLM (entro al esquema de HANDOFF al quitar
    // los regex); antes se leia con `detectarAceptacion` sobre el texto.
    const p = decidirTurno(estado, { recupera_handoff: true, acepta: true }, 'pero si agendemos');
    assert.equal(p.handoffRazon, LIMPIAR_HANDOFF);
    assert.equal(p.etapaNueva, 'M5_ENVIADO', 'la bifurcacion oficial manda el pitch, no repite la pregunta de M4');
    assert.ok(!/prioridad AHORA/.test(p.mensajes.join('\n')), 'nunca repite la pregunta de urgencia ya hecha');
    assert.match(p.mensajes.join('\n'), /30 minutos/, 'el pitch real SI menciona los 30 minutos, por primera vez');
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

// ====================================================================

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

// ====================================================================

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
  //
  // SEGUNDO CAMBIO (fundador, 7-sep-2026): antes de preguntar el TIPO se
  // pregunta si la CUENTA esta bien hecha. El error mas comun no es que el
  // lead este ahogado, es que sumo la deuda total en vez de la cuota mensual,
  // o metio arriendo/servicios/mercado, que son gastos y no deudas. Este test
  // se reescribio para fijar el orden nuevo: calculo -> tipo -> descarte.
  test('endeudamiento muy alto -> primero se verifica el calculo', () => {
    const p = decidirTurno(estadoEn('M2_ENVIADO', { salario_monto: 8_000_000 }), { endeudamiento_pct: 85 });
    assert.equal(p.etapaNueva, 'M2_VERIFICAR_CALCULO', 'no se descarta sin preguntar');
    assert.equal(p.estadoDestino, 'contactado');
    assert.match(p.mensajes.join(' '), /pagas al mes en cuotas, o con el total de la deuda/);
    assert.match(p.mensajes.join(' '), /arriendo, servicios o mercado no son deudas/);
  });

  test('si ratifica la cifra alta, RECIEN ahi se pregunta el tipo de deuda', () => {
    // La hipoteca sigue siendo la ultima salida: descalificar aca botaria a
    // alguien con deuda de vivienda, que el playbook trata distinto a proposito.
    const p = decidirTurno(estadoEn('M2_VERIFICAR_CALCULO', { salario_monto: 8_000_000 }),
      { endeudamiento_pct: 85 });
    assert.equal(p.etapaNueva, 'M2_BORDERLINE');
    assert.equal(p.estadoDestino, 'contactado');
  });

  test('si corrige la cifra y entra en su tope, sigue el embudo', () => {
    // El caso que motiva toda la feature: habia sumado la deuda total.
    const p = decidirTurno(estadoEn('M2_VERIFICAR_CALCULO', { salario_monto: 8_000_000 }),
      { endeudamiento_pct: 35 });
    assert.equal(p.etapaNueva, 'M3_ENVIADO');
    assert.equal(p.estadoDestino, 'contactado');
  });

  test('si rectifica en plata y le sobra suficiente, sigue el embudo', () => {
    const p = decidirTurno(estadoEn('M2_VERIFICAR_CALCULO', { salario_monto: 8_000_000 }),
      { remanente_cop: 3_000_000 });
    assert.equal(p.etapaNueva, 'M3_ENVIADO');
    assert.equal(p.campos.remanente_cop, 3_000_000);
  });

  test('si no da NADA con que decidir, se le vuelve a preguntar: no se descarta sobre un vacio', () => {
    const p = decidirTurno(estadoEn('M2_VERIFICAR_CALCULO', { salario_monto: 8_000_000 }), {});
    assert.notEqual(p.estadoDestino, 'descalificado');
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

  // Reescrito el 5-sep-2026 (decision de Gaby: "dale mas libertad al LLM, que
  // no responda en automatico"): antes escalaba en silencio a la primera vez
  // que no habia datos. Ahora reencauza con contexto y repregunta -- sigue
  // sin descartar a ciegas, solo que ya no deja al lead sin respuesta.
  test('borderline SIN datos para decidir -> reencauza (nunca descarta a ciegas)', () => {
    const p = decidirTurno(estadoEn('M2_BORDERLINE', { salario_monto: 8_000_000 }), {}, 'no se');
    assert.equal(p.handoffRazon, null, 'primer intento: no escala todavia');
    assert.equal(p.etapaNueva, 'M2_BORDERLINE', 'se queda en la misma etapa a repreguntar');
    assert.notEqual(p.estadoDestino, 'descalificado');
    assert.ok(p.mensajes.length > 0, 'no se queda mudo');
  });

  test('borderline SIN datos e insistiendo: se le sigue respondiendo, no escala', () => {
    const estado = estadoEn('M2_BORDERLINE', { salario_monto: 8_000_000, ambiguedad_consecutiva: 2 });
    const p = decidirTurno(estado, { es_duda_nueva: false }, 'sigo sin entender');
    assert.equal(p.handoffRazon, null, 'el lead confuso ya no escala (6-sep-2026)');
    assert.ok(p.mensajes.length > 0);
    assert.notEqual(p.estadoDestino, 'descalificado');
  });

  test('borderline sin LLM: escala por tecnico, y JAMAS descalifica', () => {
    const estado = estadoEn('M2_BORDERLINE', { salario_monto: 8_000_000 });
    const p = decidirTurno(estado, { llm_fallo: true }, 'sigo sin entender');
    assert.equal(p.handoffRazon, 'error_tecnico');
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

  test('sigue ambiguo tras pedirla -> se le responde, y JAMAS se descarta', () => {
    // Antes escalaba aca. Desde el 6-sep-2026 se razona la respuesta: quien no
    // da la cifra casi siempre esta preguntando algo ("¿antes o despues de
    // impuestos?"). La regla de oro V4.1 (nunca descartar sobre un ingreso
    // ambiguo) sigue intacta, y es lo que este test protege de verdad.
    const p = decidirTurno(estadoEn('M1_INGRESO_AMBIGUO'), { ingreso_cop: null });
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0, 'nunca se queda mudo');
    assert.notEqual(p.estadoDestino, 'descalificado');
  });

  test('el ingreso ambiguo sin LLM escala por tecnico, nunca descarta', () => {
    const p = decidirTurno(estadoEn('M1_INGRESO_AMBIGUO'), { ingreso_cop: null, llm_fallo: true });
    assert.equal(p.handoffRazon, 'error_tecnico');
    assert.notEqual(p.estadoDestino, 'descalificado');
  });
});

// ====================================================================

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

// ====================================================================

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

  // ─────────────────────────────────────────────────────────────────────────
  // POLITICA NUEVA (6-sep-2026, auditoria B): los topes de objecion se
  // RETIRARON. Escalaban con el supuesto de que "la plantilla ya no le sirvio,
  // que entre un humano" -- cierto cuando la unica respuesta posible era esa
  // MISMA plantilla literal. Hoy el LLM la reformula con el contexto y puede
  // responder con el playbook completo: insistir ya no es repetirse.
  // El CONTADOR se mantiene (alimenta el dashboard); lo que se fue es el
  // handoff. Estos tests fijan justamente eso, para que nadie lo reintroduzca
  // sin darse cuenta.
  // ─────────────────────────────────────────────────────────────────────────
  test(`la MISMA objecion ${R_MISMA} veces YA NO escala: el bot le responde distinto`, () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '3', objeciones_consecutivas: R_MISMA - 1 });
    const p = decidirTurno(estado, { objecion_num: 3, objecion_conocida: true });
    assert.equal(p.handoffRazon, null, 'un lead que insiste no se saca del embudo');
    assert.ok(p.mensajes.length > 0, 'y si recibe respuesta');
    assert.match(p.summary, /REPITE la objecion/, 'pero el Setter lo ve en el summary');
  });

  test('volver a preguntar el precio YA NO escala: es un lead interesado', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '7', objeciones_consecutivas: 0 });
    const p = decidirTurno(estado, { objecion_num: 7, objecion_conocida: true });
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0);
  });

  test('repetir una pregunta informativa tampoco escala', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '1', objeciones_consecutivas: 0 });
    const p = decidirTurno(estado, { objecion_num: 1, objecion_conocida: true });
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0);
  });

  test('el precio preguntado la PRIMERA vez lo contesta el bot', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 7, objecion_conocida: true });
    assert.equal(p.handoffRazon, null);
    assert.match(p.mensajes.join('\n'), /el programa no tiene un precio único/);
  });

  test(`${R_ACUM} objeciones consecutivas YA NO escalan`, () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '2', objeciones_consecutivas: R_ACUM - 1 });
    const p = decidirTurno(estado, { objecion_num: 4, objecion_conocida: true });
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0);
    assert.equal(p.campos.objeciones_consecutivas, R_ACUM, 'el contador SI sigue contando');
  });

  test('objeciones consecutivas por debajo del umbral las contesta el bot', () => {
    const estado = estadoEn('M5_ENVIADO', { ultima_objecion_codigo: '2', objeciones_consecutivas: R_ACUM - 2 });
    const p = decidirTurno(estado, { objecion_num: 4, objecion_conocida: true });
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0);
  });

  test('objecion fuera de las 9: se razona la respuesta, no se escala', () => {
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_detectada: true, objecion_num: null, objecion_conocida: false });
    assert.equal(p.handoffRazon, null, 'el bot tiene el playbook completo: puede responderla');
    assert.ok(p.mensajes.length > 0);
    assert.ok(p.preguntaLibre, 'se le pide al Worker redactar con el playbook delante');
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

  test('la perilla de alcance apaga la PLANTILLA, ya no manda el lead a un humano', () => {
    // Apagar una objecion significa "no uses ESA plantilla", no "no atiendas a
    // este lead" (6-sep-2026). Se razona la respuesta con el playbook.
    OBJECIONES_HABILITADAS.delete(9);
    try {
      const p = decidirTurno(estadoEn('M4_ENVIADO'), { urgencia: 'pregunta_por_que' });
      assert.equal(p.handoffRazon, null);
      assert.ok(p.mensajes.length > 0, 'nunca se queda mudo');
      assert.ok(!/Lo más caro NO es la plata/.test(p.mensajes.join('\n')),
        'pero la plantilla apagada NO sale');
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

  test('una objecion FUERA del playbook ya no va a un humano: se razona', () => {
    // Cambio del 6-sep-2026: el bot tiene el playbook completo como corpus,
    // asi que puede responder algo que no es ninguna de las 9 -- o decir con
    // honestidad que eso se ve en la llamada. Escalarla era desperdiciar al lead.
    const fuera = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_detectada: true, objecion_conocida: false });
    assert.equal(fuera.handoffRazon, null);
    assert.ok(fuera.mensajes.length > 0, 'y si recibe respuesta');
  });

  test('cerrar la perilla apaga la plantilla, pero el lead sigue siendo atendido', () => {
    // La perilla sigue siendo una perilla: se deriva de `habilitada` en la tabla.
    // Lo que cambio (6-sep-2026) es que apagarla ya no manda el lead a un humano.
    OBJECIONES_HABILITADAS.delete(7);
    try {
      const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 7, objecion_conocida: true });
      assert.equal(p.handoffRazon, null);
      assert.ok(p.mensajes.length > 0, 'nunca se queda mudo');
      assert.ok(!/el programa no tiene un precio único/.test(p.mensajes.join(' ')),
        'pero la plantilla apagada NO sale');
    } finally {
      OBJECIONES_HABILITADAS.add(7);
    }
  });
});

// ====================================================================

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

// ====================================================================

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

  // BUG REAL (5-sep-2026): "ahora" dentro de una PREGUNTA se leia como
  // afirmacion de urgencia -- el bot ignoraba la pregunta del lead y mandaba
  // directo al pitch de M5.
  test('BUG REAL: una pregunta sobre "ahora vs despues" no se lee como afirmacion de urgencia', () => {
    assert.equal(detectarUrgencia('cual es la diferencia si lo hago ahora o despues?'), 'pregunta_por_que');
    assert.equal(detectarUrgencia('que gano si lo hago ahora?'), 'pregunta_por_que');
    // Una pregunta que no calza en ningun patron especifico: se abstiene
    // (null), no fuerza "ahora" -- que decida el LLM.
    assert.equal(detectarUrgencia('debo hacerlo ahora?'), null);
    // La afirmacion normal (sin "?") sigue funcionando igual que siempre.
    assert.equal(detectarUrgencia('si, quiero resolverlo ahora'), 'ahora');
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

// ====================================================================
// Aprendizajes de produccion incorporados del proyecto original de Javier
// (Setter-IA-Claude-Code-Project). Cada uno viene de un caso REAL que ya
// paso en operacion -- no son casos hipoteticos.
// ====================================================================

describe('Aprendizajes de produccion (proyecto Setter IA de Javier)', () => {
  test('SOP-05 #2: "me quedan $5M" NO descalifica -- primero se aclara', () => {
    // Antes esto lo detectaba un regex sobre el texto (`pareceRemanente`).
    // Desde el 6-sep-2026 lo dice el LLM en `cifra_es_remanente`; la REGLA de
    // negocio no cambio: una cifra baja que es remanente NO descalifica.
    const p = decidirTurno(estadoEn('M1_ENVIADO'),
      { ingreso_cop: 5_000_000, cifra_es_remanente: true }, 'me quedan como 5 millones libres');
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

// ====================================================================
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
// ====================================================================

describe('Escalera de repreguntas antes de escalar', () => {
  const st = (etapa) => ({
    estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana',
    salario_monto: 12_000_000, objeciones_consecutivas: 0,
    ultima_objecion_codigo: null, handoff_razon: null,
  });

  test('M1 sigue escalando al segundo intento -- no gano un peldaño extra', () => {
    // Esto fija la medicion: si alguien agrega un reintento a M1 sin darse
    // cuenta de que ya tenia dos, este test lo atrapa. M2 se movio a su
    // propio test abajo: dejo de escalar en silencio al segundo intento
    // (bug real, Marly, 6-sep-2026) y ahora usa reencauzar() como M4/M5.
    assert.equal(decidirTurno(st('M1_ENVIADO'),
      { ingreso_cop: null, ingreso_glosario: 'salario_integral' }).etapaNueva, 'M1_INGRESO_AMBIGUO');
    // Y desde el 6-sep-2026 el segundo intento tampoco escala: se le responde.
    // El "peldaño extra" que este test vigila es el de la ESCALERA (una etapa
    // de reintento nueva), no el hecho de contestarle.
    const p = decidirTurno(st('M1_INGRESO_AMBIGUO'), { ingreso_cop: null });
    assert.equal(p.handoffRazon, null);
    assert.equal(p.etapaNueva, 'M1_INGRESO_AMBIGUO', 'no aparece ninguna etapa de reintento nueva');
  });

  // BUG REAL reportado en vivo (6-sep-2026, Marly): "no se" (M2_ENVIADO -> pasa
  // a M2_NO_SABE, correcto) -> "creo que si queda" (sin cifra) escalaba en
  // SILENCIO -- cero mensajes. Para el lead eso se ve identico a que el bot
  // dejo de responder. Decision explicita de Gaby: M2 se alinea con M4/M5 y
  // usa reencauzar() (contexto del LLM + tope de 3 intentos con la MISMA duda)
  // en vez de escalar al segundo intento.
  test('M2 ya no escala en silencio al segundo intento: reencauza como M4/M5', () => {
    const p = decidirTurno(st('M2_ENVIADO'), { endeudamiento_pct: null });
    assert.equal(p.etapaNueva, 'M2_NO_SABE');

    const p2 = decidirTurno(st('M2_NO_SABE'), { endeudamiento_pct: null }, 'creo que si queda');
    assert.equal(p2.handoffRazon, null, 'ya no escala al segundo intento');
    assert.equal(p2.etapaNueva, 'M2_NO_SABE');
    assert.ok(p2.mensajes.length > 0, 'no se queda mudo');
  });

  test('M2 ya no escala por insistir: solo si el LLM lleva 3 turnos caido', () => {
    const insiste = st('M2_NO_SABE'); insiste.ambiguedad_consecutiva = 2;
    assert.equal(
      decidirTurno(insiste, { endeudamiento_pct: null, es_duda_nueva: false }, 'sigo sin saber bien').handoffRazon,
      null, 'el lead confuso se atiende');

    assert.equal(
      decidirTurno(st('M2_NO_SABE'), { endeudamiento_pct: null, llm_fallo: true }, 'x').handoffRazon,
      'error_tecnico', 'el bot sin cerebro escala de inmediato');
  });

  describe('con la perilla APAGADA (estado actual)', () => {
    // Reescrito el 5-sep-2026 (decision de Gaby): el primer "no entendi" en
    // M4/M5 ya no escala en silencio -- reencauza con contexto (ver
    // reencauzar()). Solo insistir 3 veces en LA MISMA duda escala de verdad.
    test('M4 y M5 reencauzan en el primer intento (no escalan mudos)', () => {
      assert.equal(ESCALERA_REPREGUNTAS_HABILITADA, false,
        'si esto cambia, hay que mover estos tests al bloque de abajo');
      const p4 = decidirTurno(st('M4_ENVIADO'), { urgencia: null }, 'no se');
      assert.equal(p4.handoffRazon, null);
      assert.equal(p4.etapaNueva, 'M4_ENVIADO');
      assert.ok(p4.mensajes.length > 0, 'no se queda mudo');

      const p5 = decidirTurno(st('M5_ENVIADO'), {}, 'no se');
      assert.equal(p5.handoffRazon, null);
      assert.equal(p5.etapaNueva, 'M5_ENVIADO');
      assert.ok(p5.mensajes.length > 0, 'no se queda mudo');
    });

    test('M4 y M5 escalan por LLM caido, no por lead insistente', () => {
      const insiste4 = st('M4_ENVIADO'); insiste4.ambiguedad_consecutiva = 2;
      assert.equal(decidirTurno(insiste4, { urgencia: null, es_duda_nueva: false }, 'sigo sin entender').handoffRazon,
        null, 'insistir no saca del embudo');

      assert.equal(decidirTurno(st('M4_ENVIADO'), { urgencia: null, llm_fallo: true }, 'x').handoffRazon, 'error_tecnico');
      assert.equal(decidirTurno(st('M5_ENVIADO'), { llm_fallo: true }, 'x').handoffRazon, 'error_tecnico');
    });
  });

  describe('con la perilla ENCENDIDA', () => {
    // Se simula el encendido llamando al router con la etapa del peldaño, que
    // es el estado al que llevaria la perilla. Asi se prueba la mitad que la
    // perilla no puede apagar: que el peldaño sea terminal.
    // El contrato del peldaño terminal se mantiene -- no ofrece OTRO peldaño --
    // pero desde el 6-sep-2026 eso ya no significa escalar: significa que se le
    // responde sin darle otra plantilla de reintento.
    test('el peldaño de M4 NO ofrece otro peldaño, pero si responde', () => {
      const p = decidirTurno(st('M4_URGENCIA_REINTENTO'), { urgencia: null });
      assert.equal(p.handoffRazon, null);
      assert.ok(p.mensajes.length > 0, 'nunca mudo');
      assert.ok(p.preguntaLibre, 'se razona la respuesta con el playbook');
    });

    test('el peldaño de M5 NO ofrece otro peldaño, pero si responde', () => {
      const p = decidirTurno(st('M5_PITCH_REINTENTO'), {});
      assert.equal(p.handoffRazon, null);
      assert.ok(p.mensajes.length > 0);
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
      'M1_PREGUNTAR_VARIABLES', // rescate por comisiones/bonos antes de descalificar
      'M2_PEDIR_SOBRANTE',    // segundo dato del borderline
      'M4_URGENCIA_REINTENTO',
      'M5_PITCH_REINTENTO',
    ]);
  });
});

// ====================================================================
// LA BANDA DE TRAMPA $6M–$7M (4-sep-2026)
//
// El fundador bajo el Filtro 1 a $6M, pero el copy aprobado sigue preguntando
// por el rango de $7M. Todo lead que gane entre esas dos cifras CALIFICA y sin
// embargo contestaria "No" a la pregunta del rango. Este bloque existe para que
// ninguno de ellos se pierda mientras el copy no se alinee.
// ====================================================================

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

// ====================================================================

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

  // BUG REAL reportado en Instagram (6-sep-2026): el lead eligio D, contesto
  // la pregunta de M3_RECONDUCIR con algo que el LLM no logro leer como
  // financiero NI como no-financiero (dolor_financiero quedo undefined, no
  // false) -- y el bot lo trataba igual que una confirmacion real de "no es
  // financiero", escalando en silencio total. Solo debia escalar asi cuando
  // el LLM SI logra confirmar que no es financiero.
  test('BUG REAL: en M3_RECONDUCIR, si no se entiende la respuesta, reencauza (no escala mudo)', () => {
    const p = decidirTurno(st('M3_RECONDUCIR'), {}, 'pues no se, es complicado de explicar');
    assert.equal(p.handoffRazon, null, 'no escala en el primer intento sin entender');
    assert.equal(p.etapaNueva, 'M3_RECONDUCIR');
    assert.ok(p.mensajes.length > 0, 'nunca se queda mudo');
  });

  test('en M3_RECONDUCIR, un dolor NO financiero se responde con el playbook', () => {
    // Antes: "sin script del SOP para este cierre -> humano". El playbook si
    // tiene con que responderlo; lo que faltaba era darselo al LLM (6-sep-2026).
    const p = decidirTurno(st('M3_RECONDUCIR'), { dolor_financiero: false }, 'no, es un tema de salud');
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0);
    assert.ok(p.preguntaLibre, 'se le pide cerrar con honestidad, no descalificar de golpe');
  });

  test('"todo" o "toda" en otra frase no dispara el atajo', () => {
    // Falso positivo peligroso: "no me alcanza para todo el mes" no es "todas".
    assert.notDeepEqual(detectarDolorLetras('no me alcanza para todo el mes'), ['A', 'B', 'C', 'D']);
  });
});

// ====================================================================
// EL CIERRE, EN SU ORDEN NUEVO (fundador, 4-sep-2026)
//   M5 pitch -> M6 LINK SOLO -> M7 acompañante -> M8 (CIERRE_PRECALL)
//
// El orden viejo mandaba la pregunta del acompañante JUNTO al link, y por eso
// un "emm si" del lead era ambiguo: podia contestar al acompañante o al "¿ya
// agendaste?". En el QA el LLM lo leyo como agendamiento y salto hasta el
// cierre, omitiendo el link. Separar los turnos elimina la ambiguedad de raiz.
// ====================================================================

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

// ====================================================================

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
    // El caso exacto del QA. Antes un regex (`pareceDolorFinanciero`) rescataba
    // al lead cuando el LLM se equivocaba. Ese respaldo se quito el 6-sep-2026
    // junto con toda la capa de regex; la regla vive ahora en el prompt (ver
    // el test de abajo, que la fija). Aca se prueba lo que el router hace con
    // la lectura CORRECTA.
    const p = decidirTurno(
      { estado_codigo: 'contactado', etapa_bot: 'M3_ENVIADO', nombre: 'Marly',
        objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null },
      { dolores: ['D'], dolor_financiero: true, dolor_detalle: 'quiero ahorrar' },
      'd. quiero ahorrar',
    );
    assert.equal(p.etapaNueva, 'M4_ENVIADO');
    assert.ok(!p.mensajes.join('\n').includes('puede que no seamos el mejor fit'));
  });
});

// ====================================================================

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

// ====================================================================

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

// ====================================================================

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

  // BUG REAL (5-sep-2026): "pero" al inicio SIEMPRE frenaba, aunque el lead
  // estuviera aceptando pese a la duda ("pero si agendemos" tras la Objecion 9).
  test('"pero" antes de una afirmacion clara SI es aceptar (no una negacion)', () => {
    for (const t of ['pero si agendemos', 'pero dale', 'pero bueno, si, hagamoslo']) {
      assert.equal(detectarAceptacion(t), true, JSON.stringify(t));
    }
    // "pero" seguido de una negacion o de nada claro SIGUE frenando.
    for (const t of ['pero no tengo tiempo', 'pero primero una pregunta', 'pero no se']) {
      assert.equal(detectarAceptacion(t), false, JSON.stringify(t));
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

// ====================================================================
// PROBLEMA 1 (5-sep-2026): el LLM confundia "no se/no estoy segura"
// (incertidumbre) con la Objecion 6 "info sensible" (reticencia). El bot
// anteponia la plantilla de "dato sensible" y repetia P.M2_P1/P.M2_P2 tal cual
// en vez de usar M2_NO_SABE, que ya existia para este caso exacto.
// ====================================================================

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

  test('BUG REAL: un "no se" NO se trata como Objecion 6 -- se pide un estimado', () => {
    // Antes un regex (`pareceIncertidumbre`) anulaba al LLM cuando marcaba la
    // Objecion 6 sobre un "no se". Se quito con el resto de la capa (6-sep-2026):
    // distinguir "no tengo el dato" de "no te lo quiero dar" es comprension, y
    // la regla esta escrita en el prompt (ver el test que la fija abajo).
    const p = decidirTurno(estadoEn('M2_ENVIADO'),
      { endeudamiento_pct: null, objecion_num: null },
      'no se, la verdad no estoy segura');
    assert.equal(p.etapaNueva, 'M2_NO_SABE');
    assert.match(p.mensajes.join('\n'), /dame un estimado/i);
  });

  // Reescrito el 6-sep-2026 (bug real, Marly): esto escalaba en silencio al
  // segundo "no se" -- CERO mensajes. Ahora reencauza como M4/M5 (decision
  // explicita de Gaby) y solo escala de verdad a la 3ra vez con la misma duda.
  test('el mismo caso en M2_NO_SABE (insiste con "no se") reencauza, no escala mudo', () => {
    const p = decidirTurno(estadoEn('M2_NO_SABE'),
      { endeudamiento_pct: null, objecion_num: 6, objecion_conocida: true }, 'no se, de verdad no tengo idea');
    assert.equal(p.handoffRazon, null);
    assert.equal(p.etapaNueva, 'M2_NO_SABE');
    assert.ok(p.mensajes.length > 0, 'no se queda mudo');
  });

  test('insistir con "no se" ya no escala: se le sigue respondiendo', () => {
    const estado = estadoEn('M2_NO_SABE', { ambiguedad_consecutiva: 2 });
    const p = decidirTurno(estado,
      { endeudamiento_pct: null, objecion_num: 6, objecion_conocida: true, es_duda_nueva: false },
      'no se, de verdad no tengo idea');
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0);
  });

  test('una reticencia real (sin "no se") SIGUE yendo a la Objecion 6 -- no se rompe el caso bueno', () => {
    const p = decidirTurno(estadoEn('M2_ENVIADO'),
      { endeudamiento_pct: null, objecion_num: 6, objecion_conocida: true },
      'prefiero no dar esa info por aqui');
    assert.notEqual(p.etapaNueva, 'M2_NO_SABE');
    assert.match(p.mensajes.join('\n'), /sensible/i);
  });
});

// ====================================================================
// PROBLEMA 2 (5-sep-2026): P.SIN_HORARIOS pregunta la franja, pero el turno
// saltaba directo a un HANDOFF no recuperable -- la respuesta del lead a esa
// misma pregunta caia en silencio total (decidirSiResponder cortaba antes de
// que el bot volviera a hablar).
// ====================================================================

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

describe('Calendario de producción (5-sep-2026)', () => {
  test('el link es el de ARTF, NO el personal del fundador', () => {
    // Fue el bloqueante rojo #1 durante toda la construcción: cada lead que
    // agendaba entraba en la agenda personal de Andrés. Este test existe para
    // que volver atrás sea imposible sin darse cuenta.
    assert.equal(CALENDAR_LINK, CALENDAR_ARTF);
    assert.notEqual(CALENDAR_LINK, CALENDAR_PRUEBAS,
      'el calendario de pruebas NO puede llegar a un lead real');
  });

  test('todo lo que emite el bot usa ese mismo link', () => {
    // Si alguien deja una plantilla con el link viejo escrito a mano, el lead
    // recibiría una agenda distinta según la rama del guion.
    for (const [nombre, txt] of Object.entries(PLANTILLAS)) {
      if (typeof txt !== 'string') continue;
      const urls = txt.match(/https:\/\/calendar\.app\.google\/\S+/g) || [];
      for (const u of urls) {
        assert.equal(u.trim(), CALENDAR_LINK, `la plantilla ${nombre} apunta a otro calendario`);
      }
    }
  });
});

// ===========================================================================
// REENCAUZAR CON CONTEXTO (5-sep-2026, decision de Gaby): "dale mas libertad
// al LLM, que no responda en automatico". Reemplaza 3 de los 6 sitios donde
// el bot escalaba en silencio ante un mensaje que no clasifico en nada, por
// una respuesta con contexto + repregunta.
//
// EL TOPE CAMBIO DE SIGNIFICADO el 6-sep-2026 (auditoria B, decision de Gaby):
// ya no cuenta "el lead insiste con la misma duda" -- eso no escala nunca,
// porque frente a cada mensaje tiene que haber razonamiento. Cuenta turnos
// SEGUIDOS en los que el LLM no pudo responder (`llm_fallo`). No escala el
// lead confuso: escala el bot sin cerebro.
// ===========================================================================
describe('Reencauzar con contexto: el tope es del LLM, no del lead', () => {
  const st = (etapa, extra = {}) => ({
    estado_codigo: 'calificado', etapa_bot: etapa, nombre: 'Marly',
    salario_monto: 10_000_000, ambiguedad_consecutiva: 0, handoff_razon: null,
    ...extra,
  });

  // BUG REAL reportado: "cual es la diferencia si lo hago ahora o despues?"
  // el determinista de detectarUrgencia lo arreglo (ver otro describe), pero
  // si el LLM aun asi no logra clasificar algo en M4, "como asi?" ya NO se
  // queda sin respuesta.
  test('BUG REAL: "como asi?" en M4 ya no escala mudo -- responde con contexto', () => {
    const p = reencauzar(st('M4_ENVIADO'), {}, 'Marly', 'No se pudo leer la urgencia con confianza.');
    assert.equal(p.handoffRazon, null);
    assert.equal(p.etapaNueva, 'M4_ENVIADO');
    assert.ok(p.mensajes.length > 0, 'nunca se queda mudo');
    assert.ok(p.preguntaLibre, 'y se le pide al Worker razonar la respuesta con el playbook');
  });

  test('insistir con LA MISMA duda 5 veces NO escala: se le responde siempre', () => {
    let estado = st('M4_ENVIADO');
    for (let i = 1; i <= 5; i++) {
      const p = reencauzar(estado, { es_duda_nueva: false }, 'Marly', 'ctx');
      assert.equal(p.handoffRazon, null, `intento ${i}: un lead confuso nunca escala`);
      assert.ok(p.mensajes.length > 0, `intento ${i}: nunca mudo`);
      estado = { ...estado, ambiguedad_consecutiva: p.campos.ambiguedad_consecutiva };
    }
  });

  test('3 turnos SEGUIDOS con el LLM caido -> AHI si escala', () => {
    let estado = st('M4_ENVIADO');
    let p = reencauzar(estado, { llm_fallo: true }, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, null);
    assert.equal(p.campos.ambiguedad_consecutiva, 1);

    estado = { ...estado, ambiguedad_consecutiva: p.campos.ambiguedad_consecutiva };
    p = reencauzar(estado, { llm_fallo: true }, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, null, 'segundo fallo: todavia aguanta');
    assert.equal(p.campos.ambiguedad_consecutiva, 2);

    estado = { ...estado, ambiguedad_consecutiva: p.campos.ambiguedad_consecutiva };
    p = reencauzar(estado, { llm_fallo: true }, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, 'ambiguo', 'tercer fallo seguido: entra un humano');
    assert.equal(p.campos.ambiguedad_consecutiva, 0, 'se resetea al escalar');
    assert.match(p.summary, /sin responder/);
  });

  test('un turno con LLM vivo resetea el conteo de fallos', () => {
    const estado = st('M4_ENVIADO', { ambiguedad_consecutiva: 2 });
    const p = reencauzar(estado, { es_duda_nueva: false }, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, null, 'el LLM respondio: no hereda los fallos anteriores');
    assert.equal(p.campos.ambiguedad_consecutiva, 0);
  });

  test('sin pregunta pendiente en la etapa, no hay a donde reencauzar: escala directo', () => {
    const p = reencauzar(st('CIERRE_PRECALL'), {}, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, 'ambiguo');
    assert.equal(p.campos.ambiguedad_consecutiva, 0);
  });

  // BUG REAL encontrado en vivo (6-sep-2026): probando con la GROQ_API_KEY
  // real bajo rate limit sostenido (429 en cada llamada), el lead quedaba en
  // un bucle IMPOSIBLE de romper -- 12 turnos seguidos, el bot repitiendo
  // literalmente el mismo mensaje sin importar que el lead dijera "ya agende"
  // o cualquier otra cosa. Causa: `es_duda_nueva` queda `undefined` tanto si
  // el LLM nunca corrio como si corrio y REVENTO (429/timeout/red), y el
  // default ("undefined -> nueva") reseteaba el contador a 1 en cada fallo,
  // sin importar cuantas veces seguidas pasara. `llm_fallo` (worker_bot_setter_v42.js,
  // marcado SOLO cuando la llamada a Groq revienta de verdad) rompe ese ciclo:
  // un fallo real de Groq cuenta como "misma duda" para el tope de 3.
  test('BUG REAL: Groq caido (llm_fallo) SI acumula hacia la escalada -- nunca bucle infinito', () => {
    let estado = st('M2_NO_SABE');
    let p = reencauzar(estado, { llm_fallo: true }, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, null);
    assert.equal(p.campos.ambiguedad_consecutiva, 1, 'un solo fallo no escala, pero SI cuenta');

    estado = { ...estado, ambiguedad_consecutiva: p.campos.ambiguedad_consecutiva };
    p = reencauzar(estado, { llm_fallo: true }, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, null);
    assert.equal(p.campos.ambiguedad_consecutiva, 2);

    estado = { ...estado, ambiguedad_consecutiva: p.campos.ambiguedad_consecutiva };
    p = reencauzar(estado, { llm_fallo: true }, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, 'ambiguo', 'el 3er fallo SEGUIDO de Groq escala -- garantiza que nunca queda mudo para siempre');
  });

  test('llm_fallo puntual (no sostenido) no rompe el conteo de dudas nuevas normal', () => {
    // Un solo fallo de Groq en medio de una conversacion sana no debe leerse
    // distinto de una duda cualquiera: sigue sumando 1, como cualquier otra.
    const p = reencauzar(st('M2_NO_SABE'), { llm_fallo: true }, 'Marly', 'ctx');
    assert.equal(p.handoffRazon, null);
    assert.ok(p.mensajes.length > 0, 'nunca se queda mudo');
  });
});

// ===========================================================================
// RESPUESTA LIBRE GUIADA POR EL PLAYBOOK (6-sep-2026)
//
// Auditoria de la conversacion REAL de marlyy318 (Instagram). Dos turnos donde
// el bot contesto al lado, y ninguno era un bug de una rama: era que "el lead
// pregunto algo" no existia como concepto en el sistema. El clasificador tiene
// un vocabulario CERRADO por etapa; lo que no encaja en un campo se volvia
// "no clasifico" y caia en una plantilla que no responde lo que se pregunto.
//
//  · M2 — la lead pregunto "los gastos que le paso a mi mama, ¿los incluyo?"
//    y recibio "Sin presion, dame un estimado". El LLM SI habia entendido la
//    pregunta: el router tiraba esa lectura a la basura (permitirEmpatia:false
//    y respuesta_empatica solo se consumia dentro de reencauzar()).
//
//  · M3 — el playbook ofrece "D) Otra (¿cuál?)" pero no habia rama que
//    preguntara el "¿cuál?": contestar "d" caia en M3_RECONDUCIR, que le
//    insinua al lead que no es buen fit.
//
// El router NO redacta: solo EXPONE que hay que resolverle algo al lead
// (`preguntaLibre`). Quien redacta es el Worker, con el playbook aprobado
// delante y pasando por `verificarRespuestaLibre`. Si eso falla, `mensajes`
// ya trae el turno determinista de siempre.
// ===========================================================================
describe('Respuesta libre: el router expone lo que hay que resolverle al lead', () => {
  const stM2 = (extra = {}) => ({
    estado_codigo: 'contactado', etapa_bot: 'M2_ENVIADO', nombre: 'Marly',
    salario_monto: 7_000_000, endeudamiento_pct: null,
    objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
    ...extra,
  });
  const stM3 = (extra = {}) => ({
    estado_codigo: 'contactado', etapa_bot: 'M3_ENVIADO', nombre: 'Marly',
    salario_monto: 7_000_000, endeudamiento_pct: 57,
    objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
    ...extra,
  });

  test('BUG REAL M2: una pregunta sin cifra ya no se traga -- se expone para responderla', () => {
    const p = decidirTurno(
      stM2(),
      { endeudamiento_pct: null, pregunta_libre: 'si los gastos que le da a su mama cuentan como deuda' },
      'los gastos mensuales que le paso a mi mamá los incluyo?',
    );
    assert.equal(p.preguntaLibre, 'si los gastos que le da a su mama cuentan como deuda');
    assert.ok(!p.preguntaLibreReemplaza, 'la respuesta se ANTEPONE: la pregunta pendiente sigue yendo detras');
    assert.match(p.mensajes.join('\n'), /dame un estimado/i, 'el fallback determinista sigue ahi');
    assert.equal(p.etapaNueva, 'M2_NO_SABE', 'la etapa la decide el codigo, no el LLM');
  });

  test('M2 sin pregunta del lead: se comporta igual que siempre', () => {
    const p = decidirTurno(stM2(), { endeudamiento_pct: null }, 'no se');
    assert.equal(p.preguntaLibre, null, 'nadie pregunto nada: no hay que responder nada');
    assert.match(p.mensajes.join('\n'), /dame un estimado/i);
  });

  test('BUG REAL M3: "d" a secas se le pregunta cual es, no se le insinua que no es fit', () => {
    const p = decidirTurno(stM3(), { dolores: ['D'], dolor_financiero: false }, 'd');
    assert.ok(p.preguntaLibre, 'hay algo que resolverle: no dijo cual es esa "otra"');
    assert.equal(p.preguntaLibreReemplaza, true, 'el LLM redacta el turno entero, no se antepone a nada');
    assert.match(p.preguntaLibre, /cual es/i);
    assert.ok(p.mensajes.length > 0, 'si el LLM falla, sale la plantilla de siempre -- nunca mudo');
    assert.equal(p.handoffRazon, null, 'elegir D no escala a un humano');
  });

  test('M3 con "D" Y detalle NO pide redaccion libre: ya conto su caso', () => {
    const p = decidirTurno(
      stM3(),
      { dolores: ['D'], dolor_detalle: 'no puedo ahorrar nada', dolor_financiero: true },
      'otra: no puedo ahorrar nada',
    );
    assert.ok(!p.preguntaLibreReemplaza);
    assert.equal(p.etapaNueva, 'M4_ENVIADO', 'el dolor si es financiero: avanza normal');
  });

  test('el camino feliz de M2 no gana ninguna llamada extra al LLM', () => {
    const p = decidirTurno(stM2(), { endeudamiento_pct: 20 }, 'como el 20%');
    assert.ok(!p.preguntaLibre, 'dio la cifra: no hay nada que responderle aparte');
    assert.equal(p.etapaNueva, 'M3_ENVIADO');
  });
});

// ===========================================================================
// La base de conocimiento es lo que evita que el LLM invente REGLAS.
//
// El caso real: al redactar libre, lo unico que se le daba como "playbook"
// eran los 9 disparadores (etiquetas tipo "7=¿cuanto cuesta el PROGRAMA?"),
// sin una linea de contenido. Con eso el modelo respondio "sumamos todos los
// gastos fijos... sin importar a quien van", que CONTRADICE a P.M2 ("El
// arriendo, servicios y mercado NO CUENTAN"). No fue una alucinacion gratuita:
// se le pidio apoyarse en un playbook que nunca se le mostro.
// ===========================================================================
describe('CONOCIMIENTO_PLAYBOOK: el corpus que ancla las respuestas libres', () => {
  test('trae la regla de calculo de deuda que el bot contesto mal en produccion', () => {
    assert.match(CONOCIMIENTO_PLAYBOOK, /NO CUENTAN/,
      'sin esta linea el LLM vuelve a decirle al lead que los gastos fijos si cuentan');
    assert.match(CONOCIMIENTO_PLAYBOOK, /cr[eé]ditos, tarjetas, pr[eé]stamos o deudas con alguien/i);
  });

  test('trae las 4 opciones de dolor, incluida la "D) Otra (¿cuál?)"', () => {
    assert.match(CONOCIMIENTO_PLAYBOOK, /D\) Otra/);
  });

  test('se arma SOLO con plantillas aprobadas -- ni un dato nuevo', () => {
    // Cada bloque del corpus tiene que existir literal en la biblioteca de
    // copy. Si alguien escribe conocimiento a mano aca, este test se pone rojo.
    // Misma normalizacion que aplica el corpus: sin {nombre} y sin el link
    // (que se arranca a proposito, ver el test de abajo).
    const normalizar = (t) => t
      .replace(/\{nombre\}/g, '')
      .replace(/https?:\/\/\S+/g, '[el sistema envia el link del calendario, tu nunca lo escribes]')
      .trim();
    const aprobadas = Object.entries(PLANTILLAS)
      .filter(([k, v]) => typeof v === 'string' && !k.endsWith('_pendienteAprobacion'))
      .map(([, v]) => normalizar(v));
    const bloques = CONOCIMIENTO_PLAYBOOK.split(/^### .+$/m).map((b) => b.trim()).filter(Boolean);
    assert.ok(bloques.length >= 10, `se esperaban >=10 bloques, hay ${bloques.length}`);
    for (const bloque of bloques) {
      assert.ok(aprobadas.some((t) => t === bloque),
        `este bloque del corpus no sale de ninguna plantilla aprobada: "${bloque.slice(0, 70)}..."`);
    }
  });

  test('no filtra el link del calendario al prompt del LLM', () => {
    // El link lo envia el router, jamas el modelo. Si entrara al corpus, el
    // LLM podria citarlo -- y G2_LLEVA_LINK lo descartaria, pero mejor que ni
    // siquiera lo vea.
    assert.ok(!/https?:\/\//.test(CONOCIMIENTO_PLAYBOOK),
      'el corpus de conocimiento no puede contener URLs');
  });
});
