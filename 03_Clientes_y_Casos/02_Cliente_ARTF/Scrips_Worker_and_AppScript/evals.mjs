#!/usr/bin/env node
/**
 * EVALS DEL CLASIFICADOR — mide al LLM contra el corpus real
 * ============================================================================
 * POR QUE EXISTE (6-sep-2026). Al eliminar la capa de regex de negocio, el LLM
 * paso a ser la UNICA autoridad de comprension. Antes eso no se medía: los 476
 * tests corren con `fetch` mockeado o con la clasificacion ya resuelta en la
 * `pista`, asi que ninguno tocaba al modelo real. Lo unico que sabiamos de su
 * precision era que Gaby leyera conversaciones en Instagram.
 *
 * COMO FUNCIONA: cada `pista` del corpus es lo que el LLM DEBERIA extraer de
 * ese mensaje -- son etiquetas que ya existian, no hubo que inventarlas. Este
 * script corre el clasificador REAL sobre cada turno y compara campo por campo.
 *
 * El resultado es un numero. Sin el, tocar el prompt es a ciegas: recortas 500
 * tokens, no pasa nada visible, y tres dias despues un lead bueno se cae.
 *
 * Uso:  node evals.mjs            (todo el corpus)
 *       node evals.mjs 02 06      (solo esos fixtures)
 *
 * ⚠️ Gasta cupo de Groq: una llamada por turno etiquetado, espaciadas para no
 * chocar el limite por minuto. El corpus completo tarda varios minutos.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { clasificar, formatearHistorial } from './worker_bot_setter_v42.js';
import { decidirTurno } from './bot_router_v42.js';

const AQUI = dirname(fileURLToPath(import.meta.url));
const env = {};
for (const linea of readFileSync(join(AQUI, '.dev.vars'), 'utf8').split('\n')) {
  const m = linea.match(/^([A-Z_]+)=(.*)$/);
  if (m) env[m[1]] = m[2].trim();
}
if (!env.GROQ_API_KEY) {
  console.error('Falta GROQ_API_KEY en .dev.vars: sin llave no hay nada que medir.');
  process.exit(2);
}

// 28s y no menos: cada clasificacion son ~2200 tokens de entrada y el
// limite de Groq es 8000 por minuto. Con 21s se pasaba y los 429 se contaban
// como errores del modelo (la primera corrida dio 50% por eso).
const ESPERA_MS = Number(process.env.EVAL_ESPERA_MS || 28000);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Campos que NO se evaluan: no son comprension o dependen del turno anterior. */
const IGNORADOS = new Set(['profesion', 'dolor_detalle', 'objecion_detectada']);

const iguales = (esperado, real) => {
  if (Array.isArray(esperado)) {
    const r = Array.isArray(real) ? real : [];
    return esperado.length === r.length && esperado.every((x) => r.includes(x));
  }
  // `undefined` y `null` son lo mismo aca: "el modelo no puso nada".
  if (esperado === null) return real === null || real === undefined;
  // Y para un booleano `false`, omitir el campo equivale a decir false: el
  // router siempre compara con `=== true`. Exigir que el modelo emita cada
  // booleano en false seria gastar tokens en algo que no cambia ninguna
  // decision. Esto NO afloja la medicion: afloja solo donde el codigo no mira.
  if (esperado === false) return real === false || real === undefined || real === null;
  return esperado === real;
};

const filtro = process.argv.slice(2);
const DIR = join(AQUI, 'tests', 'corpus');
const archivos = readdirSync(DIR)
  .filter((f) => f.endsWith('.json') && (!filtro.length || filtro.some((x) => f.includes(x))))
  .sort();

let aciertos = 0;
let total = 0;
let saltados = 0;
const fallos = [];

for (const archivo of archivos) {
  const conv = JSON.parse(readFileSync(join(DIR, archivo), 'utf8'));
  console.log(`\n=== ${conv.nombre} ===`);

  // Se reconstruye el estado turno a turno con el router, igual que el
  // simulador: sin eso, el mensaje 5 se evaluaria en la etapa equivocada.
  let estado = null;
  const historial = [];

  for (const turno of conv.turnos) {
    const etapa = estado?.etapa_bot ?? null;
    const pista = turno.pista || {};
    const campos = Object.keys(pista).filter((k) => !IGNORADOS.has(k));

    let clasificacion = { ...pista };
    if (etapa && campos.length) {
      if (total > 0) await sleep(ESPERA_MS);

      // ⚠️ UN 429 NO ES UN ERROR DE CLASIFICACION, y confundirlos invalida la
      // medicion entera. Cuando Groq rechaza por cupo, `clasificarConLLM`
      // devuelve `{llm_fallo:true}` y TODOS los campos quedan undefined --
      // identico a que el modelo se hubiera equivocado en todos. La primera
      // corrida de este script dio 50% por eso; probando los mismos mensajes
      // uno por uno, el modelo los acertaba. Se reintenta con espera.
      let real;
      for (let intento = 1; intento <= 4; intento += 1) {
        real = await clasificar(env, estado, turno.lead, null, formatearHistorial(historial));
        if (!real.llm_fallo) break;
        const espera = ESPERA_MS * intento;
        console.log(`      (sin cupo de Groq, reintento ${intento} en ${Math.round(espera / 1000)}s)`);
        await sleep(espera);
      }
      if (real.llm_fallo) {
        // No se cuenta ni a favor ni en contra, pero el turno SI se juega con
        // la pista: si no, la conversacion se desincroniza y los turnos
        // siguientes se evaluarian en la etapa equivocada.
        saltados += 1;
        console.log(`  ~ "${turno.lead.slice(0, 46)}"  SALTADO: Groq sin cupo tras 4 intentos`);
      } else {
        const malos = [];
        for (const campo of campos) {
          total += 1;
          if (iguales(pista[campo], real[campo])) aciertos += 1;
          else malos.push(`${campo}: esperaba ${JSON.stringify(pista[campo])}, dio ${JSON.stringify(real[campo])}`);
        }
        const marca = malos.length ? '✗' : '✓';
        console.log(`  ${marca} "${turno.lead.slice(0, 46)}"${malos.length ? '' : `  (${campos.join(', ')})`}`);
        for (const m of malos) {
          console.log(`      ${m}`);
          fallos.push({ conv: conv.nombre, lead: turno.lead, detalle: m });
        }
      }
      // Se avanza con la pista, no con lo que dijo el LLM: un error en el
      // turno 3 no debe descarrilar la medicion de los turnos 4 al 9.
      clasificacion = { ...real, ...pista };
    }

    const plan = decidirTurno(estado, { ...clasificacion, nombre: conv.lead?.nombre || '' }, turno.lead);
    historial.push({ ultimo_msg_lead: turno.lead, ultimo_msg_bot: plan.mensajes.join('\n---\n') });
    if (historial.length > 6) historial.shift();
    estado = { ...(estado || { nombre: conv.lead?.nombre || '' }) };
    if (plan.etapaNueva) estado.etapa_bot = plan.etapaNueva;
    if (plan.estadoDestino) estado.estado_codigo = plan.estadoDestino;
    for (const [k, v] of Object.entries(plan.campos || {})) if (v !== undefined) estado[k] = v;
    if (plan.campos?.urgencia_raw != null) estado.urgencia = plan.campos.urgencia_raw;
  }
}

const pct = total ? (100 * aciertos / total) : 0;
console.log(`\n${'='.repeat(60)}`);
console.log(`ACIERTO DEL CLASIFICADOR: ${aciertos}/${total} campos = ${pct.toFixed(1)}%`);
if (saltados) console.log(`(${saltados} turno(s) saltados por falta de cupo en Groq: no cuentan)`);
if (fallos.length) {
  console.log('\nFallos:');
  for (const f of fallos) console.log(`  · [${f.conv.slice(0, 24)}] "${f.lead.slice(0, 34)}" -> ${f.detalle}`);
}
// Umbral de la auditoria externa: >=95% de clasificacion correcta.
const UMBRAL = Number(process.env.EVAL_UMBRAL || 95);
console.log(`\n${pct >= UMBRAL ? 'PASA' : 'NO PASA'} el umbral de ${UMBRAL}%`);
process.exit(pct >= UMBRAL ? 0 : 1);
