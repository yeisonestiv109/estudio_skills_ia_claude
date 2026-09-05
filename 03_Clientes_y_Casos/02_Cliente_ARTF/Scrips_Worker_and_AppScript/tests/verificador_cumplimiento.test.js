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
import {
  PLANTILLAS as P, CALENDAR_LINK, render, OBJECIONES_CON_PREGUNTA_PROPIA,
  PLAYBOOK_OBJECIONES, OBJECIONES, OBJECIONES_HABILITADAS, OBJECIONES_PRE_PITCH,
  DISPARADORES_OBJECIONES, UMBRALES,
} from '../sop_v42_plantillas.js';
import { decidirTurno, reencauzar } from '../bot_router_v42.js';

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

// ===========================================================================
describe('Saludo sin nombre — bug encontrado leyendo el corpus', () => {
  test('sin nombre, el saludo NO queda como "¡Hola ! 👋"', () => {
    // ManyChat no siempre resuelve first_name. Antes esto le llegaba roto a
    // TODOS los leads nuevos, que es el primer mensaje que ven.
    const m1 = render(P.M1_CONTROL, '');
    assert.ok(!/ !/.test(m1), `saludo roto: "${m1.slice(0, 40)}"`);
    assert.match(m1, /^¡Hola! 👋/);
    assert.ok(!/ {2,}/.test(m1), 'quedaron espacios dobles');
  });

  test('con nombre sigue funcionando igual', () => {
    assert.match(render(P.M1_CONTROL, 'Daniela'), /^¡Hola Daniela! 👋/);
  });

  test('un nombre basura de la base se trata como sin nombre', () => {
    assert.match(render(P.M1_CONTROL, 'Lead 12345'), /^¡Hola! 👋/);
  });

  test('el saludo sin nombre sigue pasando la compuerta', () => {
    assert.equal(verificarMensajes([render(P.M1_CONTROL, '')], { nombre: '' }).pasa, true);
  });
});

// ===========================================================================
describe('Objeciones antes del pitch: NUNCA el link del calendario', () => {
  const estadoEn = (etapa, extra = {}) => ({
    estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana',
    salario_monto: 12_000_000, objeciones_consecutivas: 0,
    ultima_objecion_codigo: null, handoff_razon: null, ...extra,
  });

  // Bug de negocio real: al habilitar la Objecion 6 en M1, su plantilla remataba
  // con "O directamente agenda la llamada de diagnostico:" + el link. Eso le
  // entrega la llamada a un lead que aun no paso los filtros de deuda, dolor y
  // urgencia. De las objeciones habilitadas, la 2, la 3 y la 6 cargaban link.
  const etapasDeCalificacion = [
    ['M1_ENVIADO', /¿A qué te dedicas y cuánto ganas al mes/],
    // Desde el QA del 4-sep, reenviar la pregunta del rango usa la variante
    // SIMPLE. La defensiva ("Te pregunto porque...") queda solo para la O6, que
    // es el unico caso donde hay una negativa que desactivar.
    ['M1_RANGO_PREGUNTADO', /¿puedes indicarme si tu salario se encuentra entre/],
    ['M2_ENVIADO', /nivel de endeudamiento/],
    ['M3_ENVIADO', /mayor frustración hoy con tu dinero/],
  ];

  // Excepcion de negocio (fundador, 3-sep-2026 (noche)): la Objecion 6 durante el
  // Filtro 1 no reencarrila con la pregunta pendiente de M1 sino con la del
  // RANGO, y por eso mueve a la etapa que escucha esa respuesta. Volver a
  // pedirle profesion y cifra exacta a quien acaba de decir "ese dato es
  // delicado" se lee como presion. Fuera de M1 la 6 se comporta como la 2 y la 3.
  const esO6enFiltro1 = (num, etapa) => num === 6 && etapa.startsWith('M1_');

  // BUG LATENTE encontrado el 4-sep-2026 al abrir las 9 objeciones.
  //
  // El barrido de la It. 6 solo miro las objeciones que llevaban LINK (2, 3, 6)
  // y por eso se salto la 1 -- que ya estaba habilitada y venia cerrando agenda
  // en M1 con "Sin presion. ¿Te parece?", a un lead que no habia pasado ni el
  // primer filtro, y ademas dejando dos preguntas seguidas.
  //
  // Un cierre de agenda no necesita link para ser un cierre de agenda. Este
  // barrido ahora cubre LAS 9 y reconoce el cierre por la frase, no por la URL.
  // Las que ya cierran con SU propia pregunta no reenvian la pendiente: serian
  // dos preguntas seguidas. Sale de la tabla del playbook, no de una lista aparte.
  const SIN_PREGUNTA_PENDIENTE = OBJECIONES_CON_PREGUNTA_PROPIA;

  const CIERRE_DE_AGENDA =
    /agenda la llamada|revisa el calendario|te dejo el link|¿te parece\??|¿te parece justo\?|¿nos reunimos\?|¿te suena que agendemos|¿agendamos|¿listo\?/i;

  for (const [etapa, preguntaPend] of etapasDeCalificacion) {
    // La 9 es la excepcion fundamentada del SOP (ver el test de abajo): la
    // predice en M4 y su bifurcacion contempla que el lead agende ahi mismo.
    for (const num of [1, 2, 3, 4, 5, 6, 7, 8]) {
      const especial = esO6enFiltro1(num, etapa);
      const esperado = especial ? /¿Estás en ese rango\?/ : preguntaPend;
      const etapaEsperada = especial ? 'M1_RANGO_PREGUNTADO' : etapa;

      test(`Objecion ${num} en ${etapa}: sin link y re-preguntando`, () => {
        const p = decidirTurno(estadoEn(etapa), { objecion_num: num, objecion_conocida: true });
        const todo = p.mensajes.join('\n');

        assert.ok(!todo.includes(CALENDAR_LINK),
          `la Objecion ${num} en ${etapa} mando el link del calendario`);
        assert.ok(!CIERRE_DE_AGENDA.test(todo),
          `la Objecion ${num} en ${etapa} remata con un cierre de agenda (el lead aun no pasa los filtros)`);
        if (!SIN_PREGUNTA_PENDIENTE.has(num)) {
          assert.match(todo, esperado,
            `la Objecion ${num} en ${etapa} no reencarrila con la pregunta que le toca`);
        }
        assert.equal(p.etapaNueva, etapaEsperada,
          especial ? 'la O6 en M1 pasa a esperar la respuesta del rango' : 'no avanza el guion');
        assert.equal(verificarMensajes(p.mensajes, { nombre: 'Ana' }).pasa, true);
      });
    }
  }

  // El guardarraíl que protege la excepcion: la O6 en M1 sigue siendo copy
  // aprobado y sigue sin poder saltarse los filtros.
  test('la O6 en M1 nunca adelanta al lead mas alla del Filtro 1', () => {
    for (const etapa of ['M1_ENVIADO', 'M1_INGRESO_AMBIGUO', 'M1_ACLARAR_REMANENTE']) {
      const p = decidirTurno(estadoEn(etapa), { objecion_num: 6, objecion_conocida: true });
      assert.equal(p.etapaNueva, 'M1_RANGO_PREGUNTADO', `${etapa} deberia esperar el rango`);
      assert.equal(p.estadoDestino, null, `${etapa} no cambia el estado del lead`);
      assert.notEqual(p.campos.califica, true, `${etapa} no marca calificado`);
      assert.equal(verificarMensajes(p.mensajes, { nombre: 'Ana' }).pasa, true,
        `${etapa} emitio copy no aprobado`);
    }
  });

  test('DESPUES del pitch la objecion SI busca el agendamiento', () => {
    // Ahi el lead ya paso los 3 filtros: ofrecerle la llamada es el objetivo.
    //
    // Se usa la Objecion 3 ("dejame pensarlo") y no la 6: desde la matriz de
    // fases del 4-sep, la 6 ("esa info es sensible") solo vive en M1-M4, que es
    // donde se le piden datos. La 3 vive justo en M5/M6, que es donde se cierra.
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 3, objecion_conocida: true });
    const todo = p.mensajes.join('\n');
    assert.ok(todo.includes(CALENDAR_LINK), 'post-pitch la Objecion 3 si lleva el link');
    assert.equal(p.mensajes[p.mensajes.length - 1].trim(), CALENDAR_LINK,
      'y el link sigue siendo la ultima burbuja, solo');
  });

  test('la Objecion 6 post-pitch NO se contesta: se reencauza', () => {
    // Es la otra cara de la matriz. Si el clasificador cree ver "esa info es
    // sensible" cuando ya se le mando el pitch, casi seguro leyo mal: ahi ya no
    // se le esta pidiendo ningun dato.
    const p = decidirTurno(estadoEn('M5_ENVIADO'), { objecion_num: 6, objecion_conocida: true });
    const todo = p.mensajes.join('\n');
    assert.ok(!todo.includes('Esa info es sensible'), 'no usa la plantilla de la 6');
    assert.ok(!todo.includes(CALENDAR_LINK), 'y no le regala el link por una objecion mal leida');
    assert.equal(p.handoffRazon, null, 'tampoco escala: reencauza');
  });

  test('la Objecion 9 en M4 conserva su cierre propio (excepcion del SOP)', () => {
    // El SOP la predice en M4 y su bifurcacion contempla que el lead acepte
    // agendar ahi mismo. No lleva link, asi que no rompe el embudo.
    const p = decidirTurno(estadoEn('M4_ENVIADO'), { objecion_num: 9, objecion_conocida: true });
    const todo = p.mensajes.join('\n');
    assert.ok(!todo.includes(CALENDAR_LINK));
    assert.match(todo, /¿Agendamos los 30 minutos/);
  });

  test('tras la Objecion 9, aceptar agendar cuenta como urgencia (SOP)', () => {
    const p = decidirTurno(
      estadoEn('M4_ENVIADO', { ultima_objecion_codigo: '9' }), {}, 'tiene sentido, agendemos');
    assert.equal(p.etapaNueva, 'M5_ENVIADO');
    assert.equal(p.estadoDestino, 'calificado');
  });
});

// ===========================================================================
// INTEGRIDAD DE LA TABLA DEL PLAYBOOK (4-sep-2026)
//
// El objetivo del refactor era: "agregar una objecion es agregar UNA entrada,
// cero logica JS que tocar". Estos tests son lo que hace esa promesa
// verificable -- comprueban que las 4 derivaciones (mapa, perilla, variantes
// pre-pitch, disparadores del prompt) siguen saliendo de la tabla y no se
// desincronizaron.
// ===========================================================================
describe('Playbook de objeciones: una sola fuente de verdad', () => {
  test('cada entrada esta completa y es coherente', () => {
    for (const o of PLAYBOOK_OBJECIONES) {
      assert.ok(Number.isInteger(o.id) && o.id > 0, `id invalido: ${o.id}`);
      assert.ok(o.nombre && /^[a-z0-9_]+$/.test(o.nombre), `nombre invalido en ${o.id}`);
      assert.ok(o.disparador?.startsWith(`${o.id}=`), `el disparador de ${o.id} no empieza con "${o.id}="`);
      assert.ok(typeof o.plantilla === 'string' && o.plantilla.trim(), `sin plantilla: ${o.id}`);
      assert.equal(typeof o.habilitada, 'boolean', `habilitada no booleana en ${o.id}`);
      assert.ok(Number.isInteger(o.cortePrePitch) && o.cortePrePitch >= 0, `cortePrePitch invalido en ${o.id}`);
      assert.equal(typeof o.preguntaPropia, 'boolean', `preguntaPropia no booleana en ${o.id}`);

      // El recorte nunca puede dejar la plantilla vacia.
      const parrafos = o.plantilla.split('\n\n').length;
      assert.ok(o.cortePrePitch < parrafos,
        `el corte de ${o.id} (${o.cortePrePitch}) se comeria toda la plantilla (${parrafos} parrafos)`);
    }
  });

  test('los ids son unicos', () => {
    const ids = PLAYBOOK_OBJECIONES.map((o) => o.id);
    assert.equal(new Set(ids).size, ids.length, 'hay ids repetidos en el playbook');
  });

  test('las 4 derivaciones salen de la tabla, sin drift', () => {
    for (const o of PLAYBOOK_OBJECIONES) {
      // 1. el mapa
      assert.equal(OBJECIONES[o.id], o.plantilla, `OBJECIONES[${o.id}] no coincide con la tabla`);
      // 2. la perilla
      assert.equal(OBJECIONES_HABILITADAS.has(o.id), o.habilitada, `la perilla de ${o.id} no coincide`);
      // 3. las variantes sin cierre de agenda
      const tieneVariante = OBJECIONES_PRE_PITCH[String(o.id)] !== undefined;
      assert.equal(tieneVariante, o.cortePrePitch > 0, `la variante pre-pitch de ${o.id} no coincide`);
      // 4. los disparadores que ve el clasificador
      assert.ok(DISPARADORES_OBJECIONES.includes(o.disparador),
        `el disparador de ${o.id} no llego al prompt del clasificador`);
      // y el Set de "trae su propia pregunta"
      assert.equal(OBJECIONES_CON_PREGUNTA_PROPIA.has(o.id), o.preguntaPropia,
        `preguntaPropia de ${o.id} no coincide`);
    }
  });

  test('la variante pre-pitch es un PREFIJO del copy aprobado, nunca copy nuevo', () => {
    // Esta es la garantia de fondo: las variantes se construyen recortando, no
    // reescribiendo. Si alguien "mejora" el texto a mano, esto se pone rojo.
    for (const [num, variante] of Object.entries(OBJECIONES_PRE_PITCH)) {
      assert.ok(OBJECIONES[Number(num)].startsWith(variante),
        `la variante pre-pitch de la objecion ${num} no es un recorte del original`);
    }
  });

  test('toda objecion habilitada emite copy aprobado en TODAS las etapas', () => {
    const etapas = ['M1_ENVIADO', 'M1_RANGO_PREGUNTADO', 'M2_ENVIADO', 'M3_ENVIADO',
      'M4_ENVIADO', 'M5_ENVIADO', 'M7_ENVIADO'];
    for (const o of PLAYBOOK_OBJECIONES.filter((x) => x.habilitada)) {
      for (const etapa of etapas) {
        const p = decidirTurno(
          { estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana', salario_monto: 12_000_000,
            objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null },
          { objecion_num: o.id, objecion_conocida: true },
        );
        if (!p.mensajes.length) continue;
        const res = verificarMensajes(p.mensajes, { nombre: 'Ana' });
        assert.equal(res.pasa, true,
          `objecion ${o.id} en ${etapa}: ${JSON.stringify(res.fallas)}`);
      }
    }
  });
});

// ===========================================================================
// MATRIZ DE OBJECIONES POR FASE + CATCH-ALL (fundador, 4-sep-2026)
// ===========================================================================
describe('Matriz de objeciones por fase del embudo', () => {
  const st = (etapa) => ({
    estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana',
    salario_monto: 12_000_000, objeciones_consecutivas: 0,
    ultima_objecion_codigo: null, handoff_razon: null,
  });

  // La matriz tal como la definio el fundador. Este literal es la fuente de
  // verdad del test: si el codigo se desvia, el test lo dice.
  const MATRIZ = {
    1: ['M5', 'M6', 'M7', 'M8'],
    2: ['M5', 'M6'],
    3: ['M5', 'M6'],
    4: 'TODAS',
    5: 'TODAS',
    6: ['M1', 'M2', 'M3', 'M4'],
    7: 'TODAS',
    8: 'TODAS',
    9: ['M4', 'M5'],
  };

  test('la tabla del playbook dice exactamente lo que definio el fundador', () => {
    for (const o of PLAYBOOK_OBJECIONES) {
      assert.deepEqual(o.fasesPermitidas, MATRIZ[o.id], `la objecion ${o.id} no coincide con la matriz`);
    }
  });

  const ETAPA_DE_FASE = {
    M1: 'M1_ENVIADO', M2: 'M2_ENVIADO', M3: 'M3_ENVIADO', M4: 'M4_ENVIADO',
    M5: 'M5_ENVIADO', M6: 'M7_ENVIADO', M8: 'M7_ESPERANDO_VINCULO',
  };

  test('dentro de su fase, la objecion se contesta con su plantilla', () => {
    for (const [num, fases] of Object.entries(MATRIZ)) {
      const permitidas = fases === 'TODAS' ? Object.keys(ETAPA_DE_FASE) : fases;
      for (const fase of permitidas) {
        const etapa = ETAPA_DE_FASE[fase];
        if (!etapa) continue; // M7 no tiene etapa propia en nuestro flujo
        const p = decidirTurno(st(etapa), { objecion_num: Number(num), objecion_conocida: true });
        assert.ok(p.mensajes.length > 0, `objecion ${num} en ${fase} no respondio nada`);
        assert.equal(p.handoffRazon, null, `objecion ${num} en ${fase} escalo`);
      }
    }
  });

  test('fuera de su fase NO usa la plantilla: reencauza sin escalar', () => {
    // "no tengo tiempo" en M1, cuando todavia no se le propuso ninguna llamada,
    // casi seguro no es la Objecion 2: es el clasificador leyendo mal.
    const p = decidirTurno(st('M1_ENVIADO'), { objecion_num: 2, objecion_conocida: true });
    assert.ok(!p.mensajes.join('\n').includes('30 minutos que te pueden ahorrar'),
      'no debe usar la plantilla de la objecion 2');
    assert.match(p.mensajes.join('\n'), /¿A qué te dedicas y cuánto ganas al mes/,
      'reencauza con la pregunta pendiente de la etapa');
    assert.equal(p.handoffRazon, null, 'y no escala');
    assert.equal(p.etapaNueva, 'M1_ENVIADO', 'ni avanza el guion');
  });

  test('el reencauce nunca emite copy sin aprobar', () => {
    for (const [fase, etapa] of Object.entries(ETAPA_DE_FASE)) {
      for (let num = 1; num <= 9; num++) {
        const p = decidirTurno(st(etapa), { objecion_num: num, objecion_conocida: true });
        if (!p.mensajes.length) continue;
        const res = verificarMensajes(p.mensajes, { nombre: 'Ana', generado: p.textoGenerado });
        assert.equal(res.pasa, true, `objecion ${num} en ${fase}: ${JSON.stringify(res.fallas)}`);
      }
    }
  });

  test('la resistencia repetida gana sobre la matriz: un lead que insiste llega a un humano', () => {
    // Si no fuera asi, una objecion fuera de fase se reencauzaria para siempre.
    const insiste = {
      estado_codigo: 'contactado', etapa_bot: 'M5_ENVIADO', nombre: 'Ana',
      salario_monto: 12_000_000,
      ultima_objecion_codigo: '6',
      objeciones_consecutivas: UMBRALES.RESISTENCIA_ACUMULADA - 1,
      handoff_razon: null,
    };
    const p = decidirTurno(insiste, { objecion_num: 6, objecion_conocida: true });
    assert.ok(p.handoffRazon, 'tiene que escalar aunque la 6 este fuera de fase en M5');
  });
});

// ===========================================================================
describe('Catch-all: el unico texto generado que ve el lead', () => {
  const st = (etapa) => ({
    estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana',
    salario_monto: 12_000_000, objeciones_consecutivas: 0,
    ultima_objecion_codigo: null, handoff_razon: null,
  });

  test('la respuesta generada se antepone y despues va la pregunta pendiente', () => {
    const p = decidirTurno(st('M1_ENVIADO'), {
      objecion_num: 2, objecion_conocida: true,
      respuesta_empatica: 'Te entiendo, es una duda muy justa.',
    });
    assert.equal(p.mensajes[0], 'Te entiendo, es una duda muy justa.');
    assert.match(p.mensajes[p.mensajes.length - 1], /¿A qué te dedicas y cuánto ganas al mes/,
      'la conversacion vuelve al carril siempre');
    assert.equal(p.textoGenerado, 'Te entiendo, es una duda muy justa.',
      'el router marca cual burbuja es generada, para que el verificador la trate distinto');
  });

  test('sin respuesta del LLM el reencauce sigue funcionando solo', () => {
    const p = decidirTurno(st('M1_ENVIADO'), { objecion_num: 2, objecion_conocida: true });
    assert.equal(p.textoGenerado, null);
    assert.equal(p.mensajes.length, 1, 'solo la pregunta pendiente');
    assert.equal(p.handoffRazon, null);
  });

  test('sin pregunta pendiente que reenviar, va a un humano', () => {
    // Se prueba `reencauzar` directo: es la unica forma honesta de llegar a este
    // caso. En el router, las etapas sin pregunta pendiente (DESCALIFICADO,
    // HANDOFF) ni siquiera alcanzan `manejarObjecion` -- las atiende antes el
    // flujo de RetornoLead o la puerta de `decidirSiResponder`.
    const sinPregunta = {
      estado_codigo: 'calificado', etapa_bot: 'CIERRE_PRECALL', nombre: 'Ana',
      objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
    };
    const p = reencauzar(sinPregunta, { respuesta_empatica: 'Claro, te entiendo.' }, 'Ana', 'test');
    assert.equal(p.handoffRazon, 'ambiguo', 'no hay a donde reencauzar: eso si es callejon sin salida');
    assert.equal(p.mensajes.length, 0, 'y no le manda copy suelto al lead');
  });

  test('el reencauce NUNCA deja al lead sin respuesta en las etapas del guion', () => {
    // La otra mitad: en toda etapa donde el bot conversa de verdad, siempre hay
    // algo que reenviar. Si alguien agrega una etapa y olvida preguntaPendiente,
    // esto se pone rojo antes de que un lead se quede mudo.
    const ETAPAS_CONVERSACIONALES = [
      'M1_ENVIADO', 'M1_INGRESO_AMBIGUO', 'M1_RANGO_PREGUNTADO', 'M1_ACLARAR_REMANENTE',
      'M2_ENVIADO', 'M2_NO_SABE', 'M3_ENVIADO', 'M3_RECONDUCIR',
      'M4_ENVIADO', 'M4_URGENCIA_REINTENTO', 'M5_ENVIADO', 'M5_PITCH_REINTENTO',
      'M7_ENVIADO', 'M7_ESPERANDO_VINCULO',
    ];
    for (const etapa of ETAPAS_CONVERSACIONALES) {
      const p = reencauzar({ estado_codigo: 'contactado', etapa_bot: etapa, nombre: 'Ana' }, {}, 'Ana', 'test');
      assert.equal(p.handoffRazon, null, `${etapa} no tiene pregunta pendiente: el lead quedaria mudo`);
      assert.ok(p.mensajes.length > 0, `${etapa} no reenvio nada`);
    }
  });

  test('el texto generado pasa por SUS reglas, no por la lista blanca', () => {
    const peligroso = 'Claro, mira el calendario en https://otro-sitio.com';
    const p = decidirTurno(st('M1_ENVIADO'), {
      objecion_num: 2, objecion_conocida: true, respuesta_empatica: peligroso,
    });
    const res = verificarMensajes(p.mensajes, { nombre: 'Ana', generado: p.textoGenerado });
    assert.equal(res.pasa, false, 'la compuerta tiene que atrapar un link generado');
    assert.ok(res.fallas.some((f) => f.regla === 'R1_LINK_AISLADO' || f.regla === 'G2_LLEVA_LINK'),
      `esperaba una falla de link, llegaron: ${JSON.stringify(res.fallas.map((f) => f.regla))}`);
  });

  test('una respuesta generada limpia SI pasa la compuerta', () => {
    const p = decidirTurno(st('M1_ENVIADO'), {
      objecion_num: 2, objecion_conocida: true,
      respuesta_empatica: 'Te entiendo, y por eso mismo quiero ser breve contigo.',
    });
    assert.equal(verificarMensajes(p.mensajes, { nombre: 'Ana', generado: p.textoGenerado }).pasa, true);
  });

  test('pero SIN declararla como generada, la compuerta la rechaza', () => {
    // Esto es lo que impide que el mecanismo se use para colar copy: solo se
    // exime la burbuja que el router marco explicitamente como generada.
    const p = decidirTurno(st('M1_ENVIADO'), {
      objecion_num: 2, objecion_conocida: true,
      respuesta_empatica: 'Te entiendo, y por eso mismo quiero ser breve contigo.',
    });
    assert.equal(verificarMensajes(p.mensajes, { nombre: 'Ana' }).pasa, false);
  });
});

// ===========================================================================
// APERTURA PERSONALIZADA: contexto del lead + cuerpo aprobado (4-sep-2026)
//
// El fundador pidió aflojar el determinismo porque las respuestas 100% estáticas
// estaban matando la conversión. La forma acordada es la de su ejemplo:
//
//   "Entiendo que tu meta principal sea ahorrar, Marly."   <- generado
//                                                          <- linea en blanco
//   "Lo que pasa es que nos especializamos en..."          <- plantilla literal
//
// HUECO QUE ESTOS TESTS CIERRAN: `esCopyAprobado` acepta ese formato mirando
// solo lo que va DESPUES de la linea en blanco, asi que el prefijo -- lo unico
// que el lead lee sin aprobar -- pasaba SIN verificarse. Ahora el cuerpo se
// valida contra la biblioteca y el prefijo contra las reglas del texto generado.
// ===========================================================================
describe('Apertura personalizada sobre plantilla aprobada', () => {
  const cuerpo = render(P.M3_RECONDUCIR, 'Marly');

  test('una apertura legitima + plantilla aprobada PASA', () => {
    const msg = `Entiendo que tu meta principal sea ahorrar, Marly.\n\n${cuerpo}`;
    assert.equal(verificarMensajes([msg], { nombre: 'Marly' }).pasa, true);
  });

  test('la plantilla sola sigue pasando', () => {
    assert.equal(verificarMensajes([cuerpo], { nombre: 'Marly' }).pasa, true);
  });

  const aperturasProhibidas = [
    ['Vas a liberar el 30% de tus ingresos.', 'G10_CIFRA_INVENTADA'],
    ['En 8 semanas ves resultados.', 'G10_CIFRA_INVENTADA'],
    ['Te garantizamos que lo vas a lograr.', 'G9_PROMESA'],
    ['Tenés toda la razón con eso.', 'G5_VOSEO_O_REGIONALISMO'],
    ['Andrés te va a explicar todo.', 'G6_TERCERA_PERSONA'],
    ['Escríbeme a mi correo personal, algo@gmail.com', 'G2_LLEVA_LINK'],
    ['Es cuestión de recortar gastos.', 'G7_LEXICO_PROHIBIDO'],
  ];

  for (const [apertura, reglaEsperada] of aperturasProhibidas) {
    test(`una apertura con "${apertura.slice(0, 30)}..." NO pasa`, () => {
      const msg = `${apertura}\n\n${cuerpo}`;
      const res = verificarMensajes([msg], { nombre: 'Marly' });
      assert.equal(res.pasa, false, 'la compuerta tiene que atrapar la apertura');
      assert.ok(res.fallas.some((f) => f.regla === reglaEsperada),
        `esperaba ${reglaEsperada}, llegaron: ${JSON.stringify(res.fallas.map((f) => f.regla))}`);
    });
  }

  test('el CUERPO sigue teniendo que ser copy aprobado: la apertura no lo exime', () => {
    // Esto es lo que impide que el mecanismo se use para escribir el mensaje
    // entero. Se puede personalizar la entrada; no se puede reescribir lo que el
    // bot afirma sobre el programa.
    const msg = 'Entiendo que quieras ahorrar.\n\nNuestro programa te devuelve el dinero si no funciona.';
    const res = verificarMensajes([msg], { nombre: 'Marly' });
    assert.equal(res.pasa, false);
    assert.ok(res.fallas.some((f) => f.regla === 'R8_COPY_NO_APROBADO'),
      'el cuerpo inventado tiene que caer por copy no aprobado');
  });

  test('el turno del link NUNCA lleva apertura generada', () => {
    // Es el turno mas fragil del embudo y el unico que ya se rompio en
    // produccion. El router lo marca `permitirEmpatia: false` cuando hay URL.
    const p = decidirTurno(
      { estado_codigo: 'calificado', etapa_bot: 'M5_ENVIADO', nombre: 'Marly',
        salario_monto: 12_000_000, objeciones_consecutivas: 0,
        ultima_objecion_codigo: null, handoff_razon: null },
      { acepta: true },
    );
    assert.ok(p.mensajes.some((m) => m.includes(CALENDAR_LINK)), 'este turno lleva el link');
    assert.equal(p.permitirEmpatia, false, 'y por eso no admite apertura generada');
  });

  test('una objecion SIN link si admite apertura personalizada', () => {
    const p = decidirTurno(
      { estado_codigo: 'contactado', etapa_bot: 'M1_ENVIADO', nombre: 'Marly',
        objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null },
      { objecion_num: 6, objecion_conocida: true },
    );
    assert.equal(p.permitirEmpatia, true);
  });

  test('M3_RECONDUCIR admite apertura: es el caso que reporto el QA', () => {
    const p = decidirTurno(
      { estado_codigo: 'contactado', etapa_bot: 'M3_ENVIADO', nombre: 'Marly',
        objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null },
      { dolores: ['D'], dolor_financiero: false, dolor_detalle: 'quiero mudarme de ciudad' },
      'd. quiero mudarme de ciudad',
    );
    assert.equal(p.etapaNueva, 'M3_RECONDUCIR');
    assert.equal(p.permitirEmpatia, true, 'aca es donde sonaba a robot');
  });
});
