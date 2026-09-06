/**
 * Tests de `calificacion_dinamica.js`.
 *
 * EL TEST QUE IMPORTA es el primero: corre el modelo contra los 50 casos que el
 * experto etiqueto y exige 50/50. Eso convierte el dataset en la especificacion
 * ejecutable del modulo -- si alguien mueve un umbral fuera de la banda
 * admisible, este test dice en rojo exactamente que caso rompio y con que
 * cifras, en vez de que la regresion salga meses despues en un lead real.
 *
 * Los demas fijan las decisiones de diseño: que sin datos no se adivina, que el
 * porcentaje de deuda NO entra en la decision, y que el interruptor apaga.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { calificar, remanenteDesdePct, MODELO } from '../calificacion_dinamica.js';

const DATOS = JSON.parse(readFileSync(new URL('./fixtures/etiquetado_calificacion_20260906.json', import.meta.url), 'utf8'));

describe('El modelo reproduce el criterio del experto', () => {
  test('acierta los 50 casos etiquetados', () => {
    const fallos = [];
    for (const c of DATOS.casos) {
      const r = calificar({ ingresoCop: c.salario_cop, remanenteCop: c.remanente_cop, endeudamientoPct: c.deuda_pct });
      if (r.veredicto !== c.decision) {
        fallos.push(`#${c.id} (${c.forma}) $${(c.salario_cop / 1e6).toFixed(2)}M al ${c.deuda_pct}%, `
          + `le quedan $${(c.remanente_cop / 1e6).toFixed(2)}M -> el experto dijo "${c.decision}", el modelo dice "${r.veredicto}"`);
      }
    }
    assert.deepEqual(fallos, [], `\n  ${fallos.join('\n  ')}\n`);
  });

  test('el dataset sigue siendo el que se uso para derivar los umbrales', () => {
    // Si alguien reetiqueta o recorta el corpus, los umbrales de arriba dejan
    // de estar justificados y hay que volver a derivarlos, no solo correr esto.
    assert.equal(DATOS.casos.length, 50);
    assert.equal(DATOS.semilla, MODELO.procedencia.semilla);
    assert.equal(DATOS.casos.filter((c) => c.decision === 'duda').length, 0,
      'aparecieron etiquetas "duda": el modelo binario ya no describe el criterio');
  });

  test('los umbrales estan dentro de la banda admisible que derivo el dataset', () => {
    // Banda calculada por busqueda exhaustiva sobre los 50 casos: cualquier par
    // (S, R) dentro de estos rangos da 0 errores. Fuera, ya no.
    const { INGRESO_MINIMO, REMANENTE_MINIMO } = MODELO.umbrales;
    assert.ok(INGRESO_MINIMO > 3_400_000 && INGRESO_MINIMO <= 5_750_000,
      `INGRESO_MINIMO ${INGRESO_MINIMO} fuera de la banda admisible (3.400.000, 5.750.000]`);
    assert.ok(REMANENTE_MINIMO > 1_924_000 && REMANENTE_MINIMO <= 2_520_000,
      `REMANENTE_MINIMO ${REMANENTE_MINIMO} fuera de la banda admisible (1.924.000, 2.520.000]`);
  });
});

describe('Los dos casos que el codigo viejo botaba y el experto aprobaba', () => {
  // Son la razon de ser de este modulo: leads que calificaban y se perdian por
  // un piso de ingreso de $6M que el dato no sostiene.
  test('#17 — $5,75M al 51%, le quedan $2,82M', () => {
    assert.equal(calificar({ ingresoCop: 5_750_000, remanenteCop: 2_817_500 }).veredicto, 'aprobar');
  });
  test('#46 — $5,9M al 48%, le quedan $3,07M', () => {
    assert.equal(calificar({ ingresoCop: 5_900_000, remanenteCop: 3_068_000 }).veredicto, 'aprobar');
  });
});

describe('El porcentaje de deuda no decide: decide el remanente', () => {
  // De los 13 casos con deuda >= 70%, el experto aprobo 5 y rechazo 8. Lo que
  // los separa es cuanta plata queda, no cuanto porcentaje se va.
  test('debe el 90% pero le quedan $2,65M: aprobar', () => {
    assert.equal(calificar({ ingresoCop: 26_550_000, remanenteCop: 2_655_000, endeudamientoPct: 90 }).veredicto, 'aprobar');
  });
  test('debe el 74% y le quedan $1,92M: rechazar', () => {
    assert.equal(calificar({ ingresoCop: 7_400_000, remanenteCop: 1_924_000, endeudamientoPct: 74 }).veredicto, 'rechazar');
  });
  test('el mismo caso con y sin el porcentaje da lo mismo', () => {
    const con = calificar({ ingresoCop: 9_000_000, remanenteCop: 3_000_000, endeudamientoPct: 67 });
    const sin = calificar({ ingresoCop: 9_000_000, remanenteCop: 3_000_000 });
    assert.equal(con.veredicto, sin.veredicto);
  });
});

describe('Sin datos no se adivina', () => {
  test('sin ingreso -> no_sabe', () => {
    assert.equal(calificar({ ingresoCop: null, remanenteCop: 3_000_000 }).veredicto, 'no_sabe');
  });
  test('sin remanente -> no_sabe', () => {
    assert.equal(calificar({ ingresoCop: 9_000_000, remanenteCop: null }).veredicto, 'no_sabe');
  });
  test('basura de entrada -> no_sabe, no una excepcion', () => {
    for (const malo of [{}, { ingresoCop: 'ocho millones', remanenteCop: 1 }, { ingresoCop: NaN, remanenteCop: 1 },
      { ingresoCop: 0, remanenteCop: 1 }, { ingresoCop: Infinity, remanenteCop: 1 }]) {
      assert.equal(calificar(malo).veredicto, 'no_sabe');
    }
  });
});

describe('El interruptor de apagado', () => {
  test('con MODELO.activo=false no decide nada y el llamador cae a la regla vieja', () => {
    MODELO.activo = false;
    try {
      const r = calificar({ ingresoCop: 20_000_000, remanenteCop: 15_000_000 });
      assert.equal(r.veredicto, 'no_sabe');
      assert.match(r.razon, /apagado/);
    } finally {
      MODELO.activo = true;
    }
  });
});

describe('Señal de "al filo" para los casos que rozan la frontera', () => {
  test('el caso #37 pasa por $20.000 y queda marcado al filo', () => {
    const r = calificar({ ingresoCop: 8_400_000, remanenteCop: 2_520_000 });
    assert.equal(r.veredicto, 'aprobar');
    assert.equal(r.alFilo, true);
    assert.equal(r.holguraRemanente, 20_000);
  });
  test('un caso holgado no se marca', () => {
    assert.equal(calificar({ ingresoCop: 25_000_000, remanenteCop: 18_000_000 }).alFilo, false);
  });
});

describe('remanenteDesdePct', () => {
  test('la cuenta de siempre', () => {
    assert.equal(remanenteDesdePct(10_000_000, 40), 6_000_000);
    assert.equal(remanenteDesdePct(7_000_000, 0), 7_000_000);
    assert.equal(remanenteDesdePct(7_000_000, 100), 0);
  });
  test('lo que no se puede calcular devuelve null, no un cero enganoso', () => {
    // Un 0 aca calificaria a alguien con un dato inventado, que es el bug de
    // clase que ya costo caro en este proyecto.
    assert.equal(remanenteDesdePct(null, 40), null);
    assert.equal(remanenteDesdePct(10_000_000, null), null);
    assert.equal(remanenteDesdePct(10_000_000, 140), null);
    assert.equal(remanenteDesdePct(10_000_000, -5), null);
    assert.equal(remanenteDesdePct(0, 40), null);
  });
});
