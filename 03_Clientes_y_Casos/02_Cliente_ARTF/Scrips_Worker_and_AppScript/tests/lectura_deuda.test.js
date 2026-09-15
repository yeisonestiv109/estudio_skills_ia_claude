/**
 * Tests de `leerDeuda` — la lectura FIEL de la cifra de deuda (12-sep-2026).
 *
 * Caso real que lo origino (traza tr_cd45365f7f): lead con ingreso de $22M
 * responde "1200" a la pregunta del porcentaje. Qwen devolvio
 * deuda_cop=12000000 -- una escala que el lead nunca escribio -- y el router
 * lo dejo pasar ("le quedan 9900000 libres, deuda 55%").
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { leerDeuda, aNumero, numerosDelTexto } from '../lectura_deuda.js';

const I22 = 22_000_000;

describe('aNumero: numeros como los escribe un colombiano', () => {
  test('miles con punto o coma, decimal latino, porcentaje y peso', () => {
    assert.equal(aNumero('1.500.000'), 1_500_000);
    assert.equal(aNumero('1,500,000'), 1_500_000);
    assert.equal(aNumero('66.6'), 66.6);
    assert.equal(aNumero('42,5'), 42.5);
    assert.equal(aNumero(' $ 12000000 COP '), 12_000_000);
    assert.equal(aNumero(70), 70);
    assert.equal(aNumero('setenta'), null);
    assert.equal(aNumero(null), null);
  });

  test('numerosDelTexto saca TODAS las cifras escritas, normalizadas', () => {
    assert.deepEqual(numerosDelTexto('1200, 1200%,120%, 300%'), [1200, 1200, 120, 300]);
    assert.deepEqual(numerosDelTexto('pago 1.500.000 al mes'), [1_500_000]);
    assert.deepEqual(numerosDelTexto('entre 23-24 millones'), [23, 24]);
    assert.deepEqual(numerosDelTexto('no se'), []);
  });
});

describe('CASO 1 — porcentaje normal', () => {
  test('"70" pelado en M2_ENVIADO es 70%', () => {
    const r = leerDeuda({ endeudamiento_pct: 70, deuda_literal: '70', deuda_unidad_dicha: 'ninguna' }, '70', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 70);
    assert.equal(r.deuda_cop, null);
    assert.equal(r.plausibilidad, 'plausible');
    assert.equal(r.diagnostico['deuda.discrepancia'], null);
  });

  test('"30%" con simbolo', () => {
    const r = leerDeuda({ endeudamiento_pct: 30, deuda_literal: '30%', deuda_unidad_dicha: 'porcentaje' }, 'me da 30%', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 30);
    assert.equal(r.plausibilidad, 'plausible');
  });
});

describe('CASO 2 — dinero explicito plausible', () => {
  test('"pago 8 millones" con ingreso de $22M se lee como cuota de $8M', () => {
    const r = leerDeuda({ deuda_cop: 8_000_000, deuda_literal: '8 millones', deuda_unidad_dicha: 'pesos' },
      'pago 8 millones', 'M2_ENVIADO', I22);
    assert.equal(r.deuda_cop, 8_000_000);
    assert.equal(r.endeudamiento_pct, null);
    assert.equal(r.plausibilidad, 'plausible');
  });

  test('"pago 1.500.000" (verbo de pago, sin palabra de escala) es cuota en pesos', () => {
    const r = leerDeuda({ deuda_cop: 1_500_000, deuda_literal: '1.500.000', deuda_unidad_dicha: 'pesos' },
      'pago 1.500.000', 'M2_ENVIADO', 10_000_000);
    assert.equal(r.deuda_cop, 1_500_000);
    assert.equal(r.plausibilidad, 'plausible');
  });
});

describe('CASO 3 — saldo total en pesos', () => {
  test('"120.000.000" contra $22M es imposible como cuota', () => {
    const r = leerDeuda({ deuda_cop: 120_000_000, deuda_literal: '120.000.000', deuda_unidad_dicha: 'pesos' },
      '120.000.000', 'M2_ENVIADO', I22);
    assert.equal(r.plausibilidad, 'imposible');
    assert.equal(r.diagnostico['deuda.motivo'], 'cuota_mayor_o_igual_al_ingreso');
  });
});

describe('CASO 4 — porcentaje absurdo (el bug)', () => {
  test('la traza real: "1200" y Qwen inventa deuda_cop=12000000 -> se lee 1200% e imposible', () => {
    const r = leerDeuda({ deuda_cop: 12_000_000, deuda_literal: '1200', deuda_unidad_dicha: 'ninguna' },
      '1200', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 1200);
    assert.equal(r.deuda_cop, null);
    assert.equal(r.plausibilidad, 'imposible');
    assert.equal(r.diagnostico['deuda.discrepancia'], 'llm_cambio_la_cifra');
    assert.equal(r.diagnostico['deuda.llm_deuda_cop'], 12_000_000);
  });

  test('Qwen "corrige" 1200% a 12% -> manda lo que escribio el lead', () => {
    const r = leerDeuda({ endeudamiento_pct: 12, deuda_literal: '1200%', deuda_unidad_dicha: 'porcentaje' },
      '1200%', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 1200);
    assert.equal(r.plausibilidad, 'imposible');
    assert.equal(r.diagnostico['deuda.discrepancia'], 'llm_cambio_la_cifra');
  });

  test('Qwen lo pasa a pesos (deuda_cop=1200) aunque el lead puso % -> 1200%', () => {
    const r = leerDeuda({ deuda_cop: 1200, deuda_literal: '1200%', deuda_unidad_dicha: 'porcentaje' },
      '1200%', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 1200);
    assert.equal(r.deuda_cop, null);
    assert.equal(r.plausibilidad, 'imposible');
  });

  test('120% y 300% tambien son imposibles; exactamente 100% tambien', () => {
    for (const [lit, v] of [['120%', 120], ['300%', 300], ['100%', 100]]) {
      const r = leerDeuda({ endeudamiento_pct: v, deuda_literal: lit, deuda_unidad_dicha: 'porcentaje' }, lit, 'M2_ENVIADO', I22);
      assert.equal(r.plausibilidad, 'imposible', lit);
      assert.equal(r.diagnostico['deuda.motivo'], 'porcentaje_mayor_o_igual_a_100', lit);
    }
  });

  test('sin literal (clasificacion antigua) igual se ataja un % >= 100', () => {
    const r = leerDeuda({ endeudamiento_pct: 1200 }, 'me da como 1200', 'M2_ENVIADO', I22);
    assert.equal(r.plausibilidad, 'imposible');
    assert.equal(r.diagnostico['deuda.anclaje'], 'sin_literal');
  });
});

describe('La pregunta de la etapa decide que es un numero pelado', () => {
  test('en M2_DEUDA_TOTAL se pidio la cuota en plata: "1.500.000" pelado son pesos', () => {
    const r = leerDeuda({ deuda_literal: '1.500.000', deuda_unidad_dicha: 'ninguna' },
      '1.500.000', 'M2_DEUDA_TOTAL', 10_000_000);
    assert.equal(r.deuda_cop, 1_500_000);
    assert.equal(r.endeudamiento_pct, null);
    assert.equal(r.plausibilidad, 'plausible');
  });

  test('en M2_ENVIADO se pidio el %: "1.500.000" pelado no se puede leer como cuota, se aclara', () => {
    const r = leerDeuda({ deuda_cop: 1_500_000, deuda_literal: '1.500.000', deuda_unidad_dicha: 'ninguna' },
      '1.500.000', 'M2_ENVIADO', 10_000_000);
    assert.equal(r.plausibilidad, 'imposible');
  });

  test('un numero <= 100 nunca es plata, en ninguna etapa', () => {
    const r = leerDeuda({ deuda_cop: 70, deuda_literal: '70', deuda_unidad_dicha: 'ninguna' }, '70', 'M2_DEUDA_TOTAL', I22);
    assert.equal(r.endeudamiento_pct, 70);
    assert.equal(r.deuda_cop, null);
  });

  test('etapa de pregunta abierta: > 100 pelado se lee como pesos', () => {
    const r = leerDeuda({ deuda_literal: '2.000.000', deuda_unidad_dicha: 'ninguna' }, '2.000.000', 'M2_VERIFICAR_CALCULO', I22);
    assert.equal(r.deuda_cop, 2_000_000);
  });
});

describe('Cifra ambigua: le falta un "mil" o es un % mal hecho', () => {
  test('"1200" como cuota en pesos contra $22M es ambigua (1.200 pesos no es una cuota)', () => {
    const r = leerDeuda({ deuda_cop: 1200, deuda_literal: '1200', deuda_unidad_dicha: 'ninguna' }, '1200', 'M2_DEUDA_TOTAL', I22);
    assert.equal(r.plausibilidad, 'ambigua');
    assert.equal(r.diagnostico['deuda.motivo'], 'cuota_mil_veces_menor_al_ingreso');
  });

  test('"8 mil" de cuota contra $22M tambien es ambigua, aunque traiga palabra', () => {
    const r = leerDeuda({ deuda_cop: 8000, deuda_literal: '8 mil', deuda_unidad_dicha: 'pesos' }, 'pago 8 mil', 'M2_ENVIADO', I22);
    assert.equal(r.plausibilidad, 'ambigua');
  });

  test('con palabra de escala escrita ("1200 mil") no hay ambiguedad', () => {
    const r = leerDeuda({ deuda_cop: 1_200_000, deuda_literal: '1200 mil', deuda_unidad_dicha: 'pesos' }, 'pago 1200 mil', 'M2_DEUDA_TOTAL', I22);
    assert.equal(r.deuda_cop, 1_200_000);
    assert.equal(r.plausibilidad, 'plausible');
  });

  test('una palabra nunca ACHICA la cifra: "1.500.000 pesos" -> 1500 es un cambio del LLM', () => {
    const r = leerDeuda({ deuda_cop: 1500, deuda_literal: '1.500.000 pesos', deuda_unidad_dicha: 'pesos' },
      'pago 1.500.000 pesos', 'M2_ENVIADO', 10_000_000);
    assert.equal(r.deuda_cop, 1_500_000, 'manda lo que escribio el lead');
    assert.equal(r.diagnostico['deuda.discrepancia'], 'llm_cambio_la_cifra');
    assert.equal(r.plausibilidad, 'plausible');
  });

  test('sin palabra de escala el LLM no puede reescalar: "$1.200" -> 1200000 se corrige a 1200', () => {
    const r = leerDeuda({ deuda_cop: 1_200_000, deuda_literal: '$1.200', deuda_unidad_dicha: 'pesos' }, '$1.200', 'M2_DEUDA_TOTAL', I22);
    assert.equal(r.deuda_cop, 1200);
    assert.equal(r.diagnostico['deuda.discrepancia'], 'llm_cambio_la_cifra');
    assert.equal(r.plausibilidad, 'ambigua');
  });
});

describe('Si el LLM no llena la cita, un mensaje sin palabras ES la cita', () => {
  test('la traza real sin deuda_literal: "1200" + deuda_cop=12000000 igual se ataja', () => {
    const r = leerDeuda({ deuda_cop: 12_000_000 }, '1200', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 1200);
    assert.equal(r.plausibilidad, 'imposible');
    assert.equal(r.diagnostico['deuda.anclaje'], 'mensaje_sin_palabras');
    assert.equal(r.diagnostico['deuda.discrepancia'], 'llm_cambio_la_cifra');
  });

  test('"70%" sin cita del LLM', () => {
    const r = leerDeuda({ endeudamiento_pct: 70 }, '70%', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 70);
    assert.equal(r.diagnostico['deuda.discrepancia'], null);
  });

  test('con palabras en el mensaje y sin cita, se confia en el LLM (interpretar es lenguaje)', () => {
    const r = leerDeuda({ deuda_cop: 8_000_000 }, 'pago como 8 millones', 'M2_ENVIADO', I22);
    assert.equal(r.deuda_cop, 8_000_000);
    assert.equal(r.diagnostico['deuda.anclaje'], 'sin_literal');
  });
});

describe('Anclaje: la cifra tiene que existir en el mensaje', () => {
  test('literal con digitos que el lead no escribio -> no se usa ningun numero', () => {
    const r = leerDeuda({ endeudamiento_pct: 40, deuda_literal: '40%', deuda_unidad_dicha: 'porcentaje' },
      'creo que la mitad mas o menos', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, null);
    assert.equal(r.deuda_cop, null);
    assert.equal(r.diagnostico['deuda.anclaje'], 'literal_no_esta_en_el_mensaje');
    assert.equal(r.plausibilidad, 'sin_cifra');
  });

  test('cifra en palabras ("setenta") -> se confia en el LLM y se deja dicho', () => {
    const r = leerDeuda({ endeudamiento_pct: 70, deuda_literal: 'setenta', deuda_unidad_dicha: 'ninguna' }, 'setenta', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 70);
    assert.equal(r.diagnostico['deuda.anclaje'], 'en_palabras');
  });

  test('"1.200" en el mensaje ancla un literal "1200" (mismo numero, otro formato)', () => {
    const r = leerDeuda({ endeudamiento_pct: 1200, deuda_literal: '1200', deuda_unidad_dicha: 'ninguna' }, '1.200', 'M2_ENVIADO', I22);
    assert.equal(r.diagnostico['deuda.anclaje'], 'ok');
  });
});

describe('Remanente y sin datos', () => {
  test('"me quedan 5 millones" respeta remanente_cop', () => {
    const r = leerDeuda({ remanente_cop: 5_000_000, deuda_literal: '5 millones', deuda_unidad_dicha: 'pesos' },
      'me quedan 5 millones', 'M2_ENVIADO', I22);
    assert.equal(r.remanente_cop, 5_000_000);
    assert.equal(r.plausibilidad, 'plausible');
  });

  test('sin cifra alguna', () => {
    const r = leerDeuda({}, 'no se', 'M2_ENVIADO', I22);
    assert.equal(r.plausibilidad, 'sin_cifra');
  });

  test('el diagnostico siempre trae lo que dijo el LLM crudo, para la telemetria', () => {
    const r = leerDeuda({ endeudamiento_pct: 12, deuda_literal: '1200%', deuda_unidad_dicha: 'porcentaje' }, '1200%', 'M2_ENVIADO', I22);
    assert.equal(r.diagnostico['deuda.llm_pct'], 12);
    assert.equal(r.diagnostico['deuda.literal'], '1200%');
    assert.equal(r.diagnostico['deuda.unidad_esperada'], 'porcentaje');
  });
});

describe('CASO 9 — RANGOS DE DEUDA: manda el techo, no el piso (14-sep-2026)', () => {
  /**
   * Caso real reportado por el fundador: a la pregunta del endeudamiento el lead
   * respondio "Entre 7 y 15" y entro como 7%. El lead pasaba el Filtro 2 con la
   * MITAD de su deuda.
   *
   * Son DOS capas y las dos fallaban:
   *   1. el prompt solo tenia regla de rangos para el INGRESO (tomar el piso), y
   *      el LLM la generalizo a la deuda;
   *   2. `leerDeuda` anclaba en la PRIMERA cifra del literal, asi que aunque el
   *      LLM extrajera bien el 15, el ancla lo bajaba a 7 -- y encima lo
   *      registraba como `llm_cambio_la_cifra`, culpando al modelo.
   *
   * La regla: con el INGRESO se toma el piso y con la DEUDA el techo. Los dos
   * eligen el escenario menos favorable para el lead.
   */
  test('"Entre 7 y 15" es 15%, no 7%', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 15, deuda_literal: 'entre 7 y 15', deuda_unidad_dicha: 'ninguna' },
      'Entre 7 y 15', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 15);
    assert.equal(r.deuda_cop, null);
    assert.equal(r.diagnostico['deuda.anclaje'], 'ok');
  });

  test('el ancla ya no acusa al LLM de cambiar la cifra cuando dio el techo', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 15, deuda_literal: 'entre 7 y 15', deuda_unidad_dicha: 'ninguna' },
      'Entre 7 y 15', 'M2_ENVIADO', I22);
    assert.equal(r.diagnostico['deuda.discrepancia'], null);
  });

  test('si el LLM se queda con el piso, el ancla lo sube al techo', () => {
    // El literal es la fuente de verdad: el lead escribio las dos cifras.
    const r = leerDeuda(
      { endeudamiento_pct: 7, deuda_literal: 'entre 7 y 15', deuda_unidad_dicha: 'ninguna' },
      'Entre 7 y 15', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 15);
  });

  test('"del 20 al 30%" es 30%', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 30, deuda_literal: 'del 20 al 30%', deuda_unidad_dicha: 'porcentaje' },
      'del 20 al 30%', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 30);
  });

  test('rango en PLATA: "entre 2 y 3 millones" es la cuota de $3M', () => {
    const r = leerDeuda(
      { deuda_cop: 3_000_000, deuda_literal: 'entre 2 y 3 millones', deuda_unidad_dicha: 'pesos' },
      'Pago entre 2 y 3 millones al mes', 'M2_ENVIADO', I22);
    assert.equal(r.deuda_cop, 3_000_000);
    assert.equal(r.endeudamiento_pct, null);
  });

  test('UNA sola cifra se comporta exactamente igual que antes', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 15, deuda_literal: '15', deuda_unidad_dicha: 'ninguna' },
      '15', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 15);
    assert.equal(r.diagnostico['deuda.discrepancia'], null);
  });

  test('un rango absurdo NO se corrige: "entre 100 y 1200" es 1200 e imposible', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 1200, deuda_literal: 'entre 100 y 1200', deuda_unidad_dicha: 'ninguna' },
      'entre 100 y 1200', 'M2_ENVIADO', I22);
    assert.equal(r.endeudamiento_pct, 1200);
    assert.equal(r.plausibilidad, 'imposible');
  });
});

describe('CASO 10 — el lead escribe la CUENTA, no la cifra (15-sep-2026)', () => {
  /**
   * Dos casos reales el mismo dia, Kevin y Angela, los dos calificando y los dos
   * en HANDOFF.
   *
   * Responden con la operacion hecha: "4.840.000/9.500.000x100= 50,94". El LLM
   * extrajo bien el 50,94, pero el ancla -- que desde el 14-sep tomaba el TECHO
   * del literal para resolver los rangos -- elegia 9.500.000, que es SU PROPIO
   * INGRESO copiado dentro de la formula. Salia "endeudamiento 9500000%",
   * imposible, y el router lo mandaba a M2_DEUDA_TOTAL y de ahi a HANDOFF.
   *
   * La leccion: "toma el numero mas grande" no distingue un RANGO de una CUENTA.
   * Hay que reconocer que clase de texto escribio el lead.
   */
  test('⚠️ Kevin: "4.840.000/9.500.000x100= 50,94" es 50,94, no su ingreso', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 50.94, deuda_literal: '4.840.000/9.500.000x100= 50,94', deuda_unidad_dicha: 'porcentaje' },
      '4.840.000/9.500.000x100= 50,94', 'M2_ENVIADO', 9_500_000);
    assert.equal(r.endeudamiento_pct, 50.94);
    assert.equal(r.plausibilidad, 'plausible');
    assert.equal(r.diagnostico['deuda.discrepancia'], null, 'y no se acusa al LLM de cambiarla');
  });

  test('⚠️ Angela: "3.000.000/6.000.000 x 100 =50%" es 50', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 50, deuda_literal: '3.000.000/6.000.000 x 100 =50%', deuda_unidad_dicha: 'porcentaje' },
      '3.000.000/6.000.000 x 100 =50%', 'M2_ENVIADO', 6_000_000);
    assert.equal(r.endeudamiento_pct, 50);
    assert.equal(r.plausibilidad, 'plausible');
  });

  test('manda lo que hay tras el ULTIMO igual', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 30, deuda_literal: '3.000.000 / 10.000.000 = 0,3 = 30%', deuda_unidad_dicha: 'porcentaje' },
      '3.000.000 / 10.000.000 = 0,3 = 30%', 'M2_ENVIADO', 10_000_000);
    assert.equal(r.endeudamiento_pct, 30);
  });

  test('una cuenta SIN resultado escrito: no se ancla al azar, manda el LLM', () => {
    // Entre el 3.000.000 y el 6.000.000 ninguno es la respuesta. Elegir uno
    // seria inventar; el LLM entiende el lenguaje y aqui es quien decide.
    const r = leerDeuda(
      { endeudamiento_pct: 50, deuda_literal: '3.000.000 de 6.000.000 / al mes', deuda_unidad_dicha: 'porcentaje' },
      '3.000.000 de 6.000.000 / al mes', 'M2_ENVIADO', 6_000_000);
    assert.equal(r.endeudamiento_pct, 50);
  });

  test('⚠️ el RANGO sigue tomando el techo: el arreglo no deroga al anterior', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 15, deuda_literal: 'entre 7 y 15', deuda_unidad_dicha: 'ninguna' },
      'Entre 7 y 15', 'M2_ENVIADO', 22_000_000);
    assert.equal(r.endeudamiento_pct, 15);
  });

  test('y una cifra absurda sigue sin corregirse', () => {
    const r = leerDeuda(
      { endeudamiento_pct: 1200, deuda_literal: '1200', deuda_unidad_dicha: 'ninguna' },
      '1200', 'M2_ENVIADO', 22_000_000);
    assert.equal(r.endeudamiento_pct, 1200);
    assert.equal(r.plausibilidad, 'imposible');
  });
});
