#!/usr/bin/env node
/**
 * Imprime una conversacion del corpus como se veria en el chat.
 * Uso:  node ver-conversacion.mjs [filtro]
 * Ej.:  node ver-conversacion.mjs 01
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { simular, imprimir } from './simulador.js';

const DIR = join(dirname(fileURLToPath(import.meta.url)), 'tests', 'corpus');
const filtro = process.argv[2] || '';
let fallos = 0;

for (const f of readdirSync(DIR).filter((x) => x.endsWith('.json') && x.includes(filtro)).sort()) {
  const conv = JSON.parse(readFileSync(join(DIR, f), 'utf8'));
  const r = simular(conv);
  console.log(imprimir(conv, r));
  if (!r.ok) fallos++;
}
process.exit(fallos ? 1 : 0);
