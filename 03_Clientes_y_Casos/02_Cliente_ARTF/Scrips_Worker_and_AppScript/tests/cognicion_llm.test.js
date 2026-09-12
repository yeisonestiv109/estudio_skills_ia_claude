/**
 * Tests de las fases 2 y 3 del plan de cognición (11-sep-2026).
 *
 * Cubren tres cosas que se arreglaron el mismo día:
 *   1. La apertura empática que NUNCA se enviaba (el esquema no la pedía).
 *   2. La ceguera del bot a las intervenciones del Setter humano.
 *   3. La corrección guiada: el LLM replantea en vez de quedar amordazado.
 *
 * El test más importante de este archivo es el último de todos: comprueba que
 * la corrección NO ablanda ninguna guarda. Si alguien "mejora" el reintento
 * dejando pasar un texto que rompe una regla, ese test se pone rojo.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  ESQUEMA_POR_ETAPA, ESQUEMA_SECRETARIA, formatearHistorial, generarConCorreccion,
  validarClasificacionLLM,
} from '../worker_bot_setter_v42.js';
import { EMPATIA_HABILITADA, CORRECCION_LLM_HABILITADA } from '../sop_v42_plantillas.js';

const src = readFileSync(new URL('../worker_bot_setter_v42.js', import.meta.url), 'utf8');

describe('BUG 1 — la apertura empática ya se le pide al modelo', () => {
  test('el esquema declara "oracion_empatia", que es lo que el Worker lee', () => {
    // EL BUG: el Worker hacía `clasificacion.oracion_empatia` pero el esquema
    // solo declaraba `respuesta_empatica`. El campo llegaba siempre undefined
    // y la apertura NUNCA se enviaba, con EMPATIA_HABILITADA en true.
    // Verificado en producción: 20 mensajes reales del 11-sep, ninguno la tenía.
    assert.equal(EMPATIA_HABILITADA, true, 'si se apaga la perilla, este test deja de aplicar');
    for (const [etapa, esquema] of Object.entries(ESQUEMA_POR_ETAPA)) {
      assert.ok(esquema.includes('"oracion_empatia"'),
        `${etapa} no le pide la apertura al modelo: la empatía volvería a morir en silencio`);
    }
  });

  test('el Worker lee EXACTAMENTE el campo que el esquema pide', () => {
    // La guarda contra que vuelvan a divergir los dos nombres.
    assert.ok(src.includes('clasificacion.oracion_empatia'), 'el Worker lee oracion_empatia');
    assert.ok(ESQUEMA_SECRETARIA.includes('"oracion_empatia"'), 'modo secretaria también');
  });

  test('siguen siendo DOS campos distintos, no uno renombrado', () => {
    // `oracion_empatia` = prefijo de 1-2 frases ANTES de una plantilla.
    // `respuesta_empatica` = el turno COMPLETO cuando nada del guion aplica.
    // Confundirlos haría que el catch-all se pegue encima de una plantilla.
    const m1 = ESQUEMA_POR_ETAPA.M1_ENVIADO;
    assert.ok(m1.includes('"oracion_empatia"') && m1.includes('"respuesta_empatica"'),
      'los dos campos conviven: hacen cosas distintas');
  });
});

describe('BUG 2 — el bot ya no es ciego a las intervenciones del equipo', () => {
  test('la memoria marca cuándo intervino un humano', () => {
    const filas = [
      { evento: 'mensaje_bot', ultimo_msg_lead: 'gano 8 millones', ultimo_msg_bot: '¿y tus deudas?' },
      { evento: 'handoff', summary: 'Escalado al Setter: pregunta_precio' },
      { evento: 'mensaje_bot', ultimo_msg_lead: 'ahh ok, listo' },
    ];
    const texto = formatearHistorial(filas);
    assert.match(texto, /\[EQUIPO: .*Setter/, 'la huella del humano tiene que verse');
    assert.match(texto, /LEAD: ahh ok, listo/);
  });

  test('los eventos del equipo no se confunden con mensajes del bot', () => {
    // Un evento de equipo no trae ultimo_msg_bot: si se imprimiera como "TU:",
    // el modelo creería que él escribió algo que nunca escribió.
    const texto = formatearHistorial([{ evento: 'cambio_estado', summary: 'Etapa calificado -> agendado' }]);
    assert.ok(!texto.includes('TU:'), 'nada de atribuirle al bot lo que hizo el equipo');
    assert.match(texto, /\[EQUIPO: Etapa calificado -> agendado\]/);
  });

  test('una conversación normal se ve igual que siempre', () => {
    // La forma vieja de las filas (sin `evento`) tiene que seguir funcionando.
    const texto = formatearHistorial([{ ultimo_msg_lead: 'hola', ultimo_msg_bot: '¡Hola!' }]);
    assert.equal(texto, 'LEAD: hola\nTU: ¡Hola!');
  });

  test('la consulta de memoria pide los eventos del equipo', () => {
    assert.match(src, /evento=in\.\(mensaje_bot,handoff,nota,cambio_estado,asignacion\)/);
    assert.match(src, /select=evento,ultimo_msg_lead,ultimo_msg_bot,summary/);
  });
});

describe('FASE 3 — corrección guiada: replantear, no amordazar', () => {
  const sinFallas = () => [];
  const siempreFalla = () => [{ regla: 'G9_PROMESA', detalle: 'promete un resultado.' }];

  test('si el texto pasa a la primera, no se gasta un reintento', async () => {
    let llamadas = 0;
    const texto = await generarConCorreccion({
      etiqueta: 'prueba',
      pedir: async () => { llamadas += 1; return 'texto correcto'; },
      verificar: sinFallas,
    });
    assert.equal(texto, 'texto correcto');
    assert.equal(llamadas, 1, 'el camino feliz no puede costar llamadas de más (techo de Groq)');
  });

  test('si rompe una guarda, se le dice QUÉ rompió y replantea', async () => {
    const recibido = [];
    const texto = await generarConCorreccion({
      etiqueta: 'prueba',
      pedir: async (correccion) => {
        recibido.push(correccion);
        return recibido.length === 1 ? 'te garantizo resultados' : 'texto corregido';
      },
      verificar: (t) => (t === 'texto corregido' ? [] : siempreFalla()),
    });
    assert.equal(texto, 'texto corregido');
    assert.equal(recibido.length, 2, 'exactamente un reintento');
    assert.equal(recibido[0], '', 'el primer intento va limpio');
    assert.match(recibido[1], /G9_PROMESA/, 'el modelo tiene que saber qué regla rompió');
    assert.match(recibido[1], /promete un resultado/, 'y el detalle, no solo el código');
  });

  test('⚠️ LA GUARDA ES ABSOLUTA: si el replanteo también falla, NO sale nada', async () => {
    // Este es el test que protege la decisión del fundador. La corrección da
    // una segunda oportunidad; NUNCA convierte un texto prohibido en enviable.
    let llamadas = 0;
    const texto = await generarConCorreccion({
      etiqueta: 'prueba',
      pedir: async () => { llamadas += 1; return 'te garantizo resultados en 8 semanas'; },
      verificar: siempreFalla,
    });
    assert.equal(texto, '', 'se cae a la plantilla aprobada, que es el último recurso');
    assert.equal(llamadas, 2, 'un solo reintento, no un bucle');
  });

  test('con la perilla apagada vuelve al comportamiento viejo', async () => {
    // Se puede desactivar sin tocar código si el reintento diera problemas.
    assert.equal(CORRECCION_LLM_HABILITADA, true, 'hoy está encendida');
    assert.ok(src.includes('if (!CORRECCION_LLM_HABILITADA)'),
      'existe el camino de apagado que descarta sin reintentar');
  });

  test('un texto vacío del LLM no dispara reintentos infinitos', async () => {
    let llamadas = 0;
    await generarConCorreccion({
      etiqueta: 'prueba',
      pedir: async () => { llamadas += 1; return ''; },
      verificar: (t) => (t ? [] : [{ regla: 'A0_VACIO', detalle: 'vino vacía.' }]),
    });
    assert.equal(llamadas, 2);
  });
});

describe('FASE 2 — el prompt sigue la metodología de la guía', () => {
  // Estos tests existen porque un prompt es lo más fácil de "optimizar"
  // recortando. La estructura XML no es decorativa: es lo que separa las
  // instrucciones del texto del lead y lo que evita el sobreajuste a palabras.
  test('está estructurado con etiquetas XML, no con viñetas sueltas', () => {
    for (const etiqueta of ['rol_y_contexto', 'estado_actual', 'reglas_de_oro',
                            'definicion_de_intenciones', 'campos_a_extraer',
                            'redaccion', 'ejemplos', 'seguridad', 'formato_de_salida']) {
      assert.ok(src.includes(`<${etiqueta}>`), `falta el bloque <${etiqueta}>`);
    }
  });

  test('las intenciones se definen por significado, con casos negativos', () => {
    // El sobreajuste era el bug de fondo: una lista de palabras permitidas
    // convierte al modelo en un buscador de strings y pierde "de una", "obvio".
    assert.match(src, /<intencion nombre="acepta">/);
    assert.match(src, /de una/, 'un "de una" colombiano es un sí');
    assert.match(src, /NO: .*cuanto cuesta/s, 'y tiene que saber qué NO es aceptar');
  });

  test('hay few-shot de casos límite reales', () => {
    const ejemplos = (src.match(/<ejemplo>/g) || []).length;
    assert.ok(ejemplos >= 5, `solo ${ejemplos} ejemplos: la frontera se calibra con casos`);
    assert.match(src, /4 \+ 3 \+ 4 = 11 millones/, 'el caso de las tres fuentes');
  });

  test('el razonamiento sigue siendo obligatorio y PRIMERO', () => {
    // El modelo genera en orden: si el razonamiento va después, no sirve de nada.
    assert.match(src, /"analisis_paso_a_paso" es OBLIGATORIO, va PRIMERO/);
    assert.ok(src.includes('"analisis_paso_a_paso": string, '),
      'y sigue siendo el primer campo del esquema JSON');
  });

  test('el prompt le avisa al modelo que hay mensajes humanos que no ve', () => {
    assert.match(src, /\[EQUIPO: \.\.\.\] son intervenciones de un humano/);
    assert.match(src, /no asumas que el\s*\n?ultimo mensaje que leyo el lead lo escribiste tu/s);
  });

  test('la apertura y el catch-all quedan explicados como campos distintos', () => {
    assert.match(src, /<campo nombre="oracion_empatia">/);
    assert.match(src, /<campo nombre="respuesta_empatica">/);
  });
});

// ===========================================================================
// Los 5 requerimientos de cierre (11-sep-2026, noche)
// ===========================================================================
import { decidirTurno, decidirSiResponder } from '../bot_router_v42.js';
import { PLANTILLAS } from '../sop_v42_plantillas.js';

const leadEn = (etapa, extra = {}) => ({
  estado_codigo: 'calificado', etapa_bot: etapa, nombre: 'Ana',
  objeciones_consecutivas: 0, ultima_objecion_codigo: null, handoff_razon: null,
  dias_sin_actividad: 0, ...extra,
});

describe('PUNTO 1 — la compuerta de cumplimiento ya corre en producción', () => {
  test('el Worker invoca verificarMensajes en el flujo real', () => {
    // Existía con 69 tests y NUNCA se llamaba fuera del simulador: la única
    // compuerta que mira el turno completo no corría contra un lead real.
    assert.ok(src.includes('verificarMensajes, formatearFallas'), 'se importa');
    assert.match(src, /let compliance = verificarMensajes\(mensajes, \{ nombre, generado \}\)/,
      'y se ejecuta sobre lo que se va a enviar');
  });

  test('si falla, cae al copy aprobado en vez de enviar algo prohibido', () => {
    assert.match(src, /const soloAprobado = \[\.\.\.plan\.mensajes\]/);
    assert.match(src, /if \(segundo\.pasa\)/, 'y se revalida antes de enviarlo');
  });

  test('el resultado queda en la telemetría para poder verlo', () => {
    assert.match(src, /'compliance\.pasa': compliance\.pasa/);
    assert.match(src, /'compliance\.fallas'/);
  });
});

describe('PUNTO 5 — un "gracias" al final cierra, no reabre', () => {
  test('agradecer con el embudo cerrado recibe despedida, no un saludo', () => {
    const p = decidirTurno(leadEn('CIERRE_PRECALL'), {}, 'muchas gracias!');
    assert.equal(p.mensajes.length, 1);
    assert.match(p.mensajes[0], /Éxitos y nos vemos en la llamada/);
    assert.ok(!/Hola de nuevo/i.test(p.mensajes[0]), 'NUNCA saludarlo como si volviera');
  });

  test('después de despedirse, la etapa queda terminal: no hay bucle posible', () => {
    const p = decidirTurno(leadEn('CIERRE_PRECALL'), {}, 'gracias');
    assert.equal(p.etapaNueva, 'BLINDAJE_CERRADO');
    // Y desde ahí el bot ya no vuelve a hablar nunca.
    assert.equal(decidirSiResponder(leadEn('BLINDAJE_CERRADO')).responder, false);
  });

  test('si con el embudo cerrado dice algo que NO es despedida, el bot calla', () => {
    const p = decidirTurno(leadEn('CIERRE_PRECALL'), {}, 'oye una pregunta sobre el precio');
    assert.equal(p.mensajes.length, 0, 'eso lo atiende un humano, no el bot');
  });

  test('el prompt también se lo dice al modelo', () => {
    assert.match(src, /<cierre_de_conversacion>/);
    assert.match(src, /NUNCA lo saludes de nuevo/);
  });
});

describe('PUNTO 4 — intuición del LLM sobre la cifra de deuda', () => {
  test('un número pelado en la pregunta de deuda es un porcentaje', () => {
    assert.match(src, /UN NUMERO PELADO EN LA PREGUNTA DE DEUDA ES UN PORCENTAJE/);
    assert.match(src, /responde "50", "30", "70", quiere decir 50%/);
  });

  test('una cifra imposible como cuota mensual es el saldo total', () => {
    assert.match(src, /gana \$1\.000\.000 y dice que debe \$1\.230\.000 al mes/);
    assert.match(src, /aca no hay router que valga/i);
  });

  test('y el copy lo resuelve en UN solo mensaje', () => {
    const t = PLANTILLAS.M2_DEUDA_TOTAL_VS_CUOTA;
    assert.match(t, /cuota mensual/i, 'dice con qué se hace la cuenta');
    assert.match(t, /arriendo/i, 'y que los gastos fijos no cuentan');
    assert.match(t, /\?/, 'y pregunta, todo junto');
  });
});

// ===========================================================================
// Fallos encontrados en la TELEMETRÍA REAL (12-sep-2026)
//
// Los cuatro salieron de leer trazas de producción, no de hipótesis. Cada
// test aquí es la garantía de que no vuelven.
// ===========================================================================

describe('RAÍZ 1 — ninguna etapa puede dejar al LLM apagado', () => {
  // El bug: DESCALIFICADO, CIERRE_PRECALL y BLINDAJE_CERRADO no tenían
  // esquema, y `clasificarConLLM` hace `if (!esquema) return {}`. En la
  // telemetría se veía como GROQ_CLASIFICADOR en 0 ms con llm.fallo=false.
  // Como `crisis` y `hostil` SOLO los llena el LLM, esas etapas quedaban
  // ciegas a una crisis emocional. Ya había pasado cuatro veces.
  const routerSrc = readFileSync(new URL('../bot_router_v42.js', import.meta.url), 'utf8');

  test('TODA etapa que el router puede dejar en la base tiene esquema propio', () => {
    const etapas = [...new Set(
      [...routerSrc.matchAll(/etapaNueva: '([A-Z0-9_]+)'/g)].map((m) => m[1]),
    )].filter((e) => e !== 'HANDOFF');   // HANDOFF lo pone el helper, y sí tiene esquema

    const sinEsquema = etapas.filter((e) => !ESQUEMA_POR_ETAPA[e]);
    assert.deepEqual(sinEsquema, [],
      `estas etapas dejarían el LLM apagado (crisis y hostilidad incluidas): ${sinEsquema.join(', ')}`);
  });

  test('las etapas de cierre evalúan crisis y hostilidad', () => {
    for (const etapa of ['DESCALIFICADO', 'CIERRE_PRECALL', 'BLINDAJE_CERRADO']) {
      assert.ok(ESQUEMA_POR_ETAPA[etapa], `falta el esquema de ${etapa}`);
      assert.match(ESQUEMA_POR_ETAPA[etapa], /"crisis"/, `${etapa} ciego a una crisis`);
      assert.match(ESQUEMA_POR_ETAPA[etapa], /"hostil"/);
    }
  });

  test('DESCALIFICADO además extrae cifras: el RetornoLead lo necesita', () => {
    assert.match(ESQUEMA_POR_ETAPA.DESCALIFICADO, /"ingreso_cop"/);
  });

  test('RED DE FONDO: una etapa olvidada cae al esquema universal, no al vacío', () => {
    // Aunque el test de arriba proteja el caso conocido, el día que alguien
    // agregue una etapa nueva el LLM tiene que seguir corriendo igual.
    assert.match(src, /ESQUEMA_POR_ETAPA\[etapa\] \|\| ESQUEMA_SECRETARIA/);
    assert.match(ESQUEMA_SECRETARIA, /"crisis"/, 'el universal también evalúa seguridad');
  });
});

describe('RAÍZ 2 — un error de tipado del LLM no puede costar un lead', () => {
  test('un número que llega como string YA NO se descarta', () => {
    // El bug: `typeof v === 'number'` convertía "70" en null, en silencio.
    assert.equal(validarClasificacionLLM({ endeudamiento_pct: '70' }).endeudamiento_pct, 70);
    assert.equal(validarClasificacionLLM({ ingreso_cop: '8500000' }).ingreso_cop, 8_500_000);
  });

  test('los separadores de miles inequívocos se entienden', () => {
    assert.equal(validarClasificacionLLM({ ingreso_cop: '8.500.000' }).ingreso_cop, 8_500_000);
    assert.equal(validarClasificacionLLM({ ingreso_cop: '8,500,000' }).ingreso_cop, 8_500_000);
    assert.equal(validarClasificacionLLM({ ingreso_cop: ' $ 12000000 COP ' }).ingreso_cop, 12_000_000);
  });

  test('un decimal latino se respeta como decimal, no como miles', () => {
    assert.equal(validarClasificacionLLM({ endeudamiento_pct: '42,5' }).endeudamiento_pct, 42.5);
  });

  test('y lo que NO es número sigue siendo null: no se adivina', () => {
    assert.equal(validarClasificacionLLM({ ingreso_cop: 'como ocho palos' }).ingreso_cop, null);
    assert.equal(validarClasificacionLLM({ ingreso_cop: '' }).ingreso_cop, null);
    assert.equal(validarClasificacionLLM({ ingreso_cop: {} }).ingreso_cop, null);
    // Un porcentaje fuera de rango sigue rechazándose.
    assert.equal(validarClasificacionLLM({ endeudamiento_pct: '150' }).endeudamiento_pct, null);
  });
});

describe('RAÍZ 3 — a un lead con datos no se le vuelve a mandar el saludo', () => {
  test('lead con ingreso ya registrado y sin etapa: retoma, no saluda', () => {
    // Visto en producción: 2 turnos de historial, hablando de sus deudas, y
    // el bot le respondió "Apertura enviada (M1_GENERAL)".
    const p = decidirTurno(
      { estado_codigo: 'contactado', etapa_bot: null, nombre: 'Ana', salario_monto: 9_000_000,
        objeciones_consecutivas: 0, handoff_razon: null },
      {}, 'pago como 2 millones al mes',
    );
    assert.ok(!/Llegas al lugar correcto|Te entiendo, no tener el control/.test(p.mensajes.join(' ')),
      'no puede reabrir el embudo desde cero');
    assert.match(p.summary, /se retoma en/);
  });

  test('un lead de verdad nuevo SÍ recibe la apertura', () => {
    const p = decidirTurno(null, {}, 'CONTROL');
    assert.equal(p.etapaNueva, 'M1_ENVIADO');
    assert.match(p.summary, /Apertura enviada/);
  });

  test('un lead que existe pero no ha dicho nada también recibe la apertura', () => {
    const p = decidirTurno(
      { estado_codigo: 'contactado', etapa_bot: null, nombre: 'Ana', objeciones_consecutivas: 0 },
      {}, 'CONTROL',
    );
    assert.match(p.summary, /Apertura enviada/);
  });
});

describe('RAÍZ 4 — la telemetría no puede mentir por omisión', () => {
  test('reporta también profesión y dolor: "Soy concejal" ya no es "sin_señal"', () => {
    assert.match(src, /'profesion', 'dolores'/);
    assert.match(src, /'dolor_financiero'/);
    assert.match(src, /'recupera_handoff'/);
  });

  test('el dashboard ordena los pasos por hora real, no por orden de llegada', () => {
    const dash = readFileSync(new URL('../telemetria/index.html', import.meta.url), 'utf8');
    assert.match(dash, /new Date\(a\.started_at\) - new Date\(b\.started_at\)/);
    assert.match(dash, /function encolar/, 'los spans en vivo se ordenan antes de pintarse');
  });
});
