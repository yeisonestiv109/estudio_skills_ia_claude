/**
 * Corpus de conversaciones — el terreno externo más fuerte del loop.
 *
 * Cada archivo de `corpus/` es una conversación completa cuyas frases del lead
 * NO las escribí yo: salen de las conversaciones modelo del proyecto de Javier
 * y de casos documentados en el PDF del SOP del cliente. Por eso sirven como
 * examen: no puedo ablandarlas sin contradecir un documento del cliente.
 *
 * Cada conversación se reproduce turno por turno contra el router y **la
 * compuerta de cumplimiento corre en CADA turno** -- no basta con que el bot
 * llegue al final, tiene que no romper el playbook en el camino.
 *
 * Para agregar una conversación: copia un JSON de `corpus/`, pega el ida y
 * vuelta real y declara qué esperas. No hay que tocar código.
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { simular, imprimir } from '../simulador.js';

const AQUI = dirname(fileURLToPath(import.meta.url));
const DIR = join(AQUI, 'corpus');

const archivos = readdirSync(DIR).filter((f) => f.endsWith('.json')).sort();

describe('Corpus de conversaciones reales', () => {
  test('hay conversaciones en el corpus', () => {
    assert.ok(archivos.length >= 4, `solo ${archivos.length} conversaciones`);
  });

  for (const archivo of archivos) {
    const conversacion = JSON.parse(readFileSync(join(DIR, archivo), 'utf8'));

    test(`${conversacion.nombre}`, async () => {
      const r = await simular(conversacion);
      assert.equal(r.ok, true, imprimir(conversacion, r));
    });
  }
});

describe('Invariantes que ninguna conversación puede romper', () => {
  for (const archivo of archivos) {
    const conversacion = JSON.parse(readFileSync(join(DIR, archivo), 'utf8'));
    // `simular` es async desde que usa el clasificador REAL del Worker, así que
    // cada test resuelve su propia corrida en vez de compartir una de arriba.
    test(`${archivo}: el bot nunca escribe "agendado"`, async () => {
      const r = await simular(conversacion);
      // Ese estado es exclusivo de la sincronización con Google Calendar.
      for (const p of r.pasos) {
        assert.notEqual(p.estado, 'agendado',
          `turno ${p.turno} dejó el lead en "agendado"`);
      }
    });

    test(`${archivo}: si hay link, es siempre la última burbuja y va solo`, async () => {
      const r = await simular(conversacion);
      for (const p of r.pasos) {
        const conLink = (p.mensajes || []).filter((m) => /https?:\/\//.test(m));
        if (conLink.length === 0) continue;
        assert.equal(conLink.length, 1, `turno ${p.turno}: más de una burbuja con link`);
        const ultima = p.mensajes[p.mensajes.length - 1];
        assert.match(ultima.trim(), /^https?:\/\/\S+$/,
          `turno ${p.turno}: la última burbuja no es solo el link`);
      }
    });

    test(`${archivo}: nunca se descalifica sin una cifra de ingreso confirmada`, async () => {
      const r = await simular(conversacion);
      // Regla de oro V4.1 del playbook: el descarte por ingreso es de 2 pasos.
      let descalificoPorIngreso = false;
      for (const p of r.pasos) {
        if (p.estado === 'descalificado' && !descalificoPorIngreso) {
          descalificoPorIngreso = true;
          const previos = r.pasos.slice(0, p.turno).map((x) => x.lead).join(' ');
          assert.match(previos, /\d/,
            `turno ${p.turno}: descalificó sin que el lead diera nunca una cifra`);
        }
      }
    });
  }
});
