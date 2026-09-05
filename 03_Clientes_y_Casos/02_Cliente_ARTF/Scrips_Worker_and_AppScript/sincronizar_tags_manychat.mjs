#!/usr/bin/env node
/**
 * Sincroniza los tags del bot en ManyChat.
 * ============================================================================
 * POR QUE EXISTE: el 5-sep-2026 se descubrio que TODOS los `addTagByName` de
 * handoff fallaban con "Tag does not exist". En la cuenta solo habia un tag
 * llamado literalmente `V42_HANDOFF_*` -- alguien creyo que el asterisco era un
 * comodin. ManyChat no soporta comodines. Resultado: la señal de handoff hacia
 * el Setter estaba muerta desde el primer dia.
 *
 * Es IDEMPOTENTE: solo crea los que faltan. Se vuelve a correr cada vez que se
 * agregue una razon de handoff nueva a `RAZONES_HANDOFF`.
 *
 *   set -a && . .dev.vars && set +a && node sincronizar_tags_manychat.mjs
 *   ... y con --dry-run para ver que haria sin tocar nada.
 */
import { TAGS_DEL_BOT } from './sop_v42_plantillas.js';

const TOKEN = process.env.MANYCHAT_API_TOKEN;
const PREFIJO = (process.env.TAG_PREFIX || '').trim();
const DRY = process.argv.includes('--dry-run');

if (!TOKEN) {
  console.error('Falta MANYCHAT_API_TOKEN. Corre:  set -a && . .dev.vars && set +a');
  process.exit(1);
}

const api = async (ruta, opciones = {}) => {
  const resp = await fetch(`https://api.manychat.com/fb/${ruta}`, {
    headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
    ...opciones,
  });
  const cuerpo = await resp.json().catch(() => ({}));
  if (!resp.ok || cuerpo.status !== 'success') {
    throw new Error(`${ruta} -> ${resp.status} ${JSON.stringify(cuerpo).slice(0, 200)}`);
  }
  return cuerpo;
};

const esperados = TAGS_DEL_BOT.map((t) => `${PREFIJO}${t}`);
const { data: existentes } = await api('page/getTags');
const nombres = new Set(existentes.map((t) => t.name));

const faltantes = esperados.filter((t) => !nombres.has(t));
const sobrantes = existentes
  .filter((t) => PREFIJO && t.name.startsWith(PREFIJO) && !esperados.includes(t.name))
  .map((t) => t.name);

console.log(`Prefijo: "${PREFIJO || '(ninguno)'}"  ·  esperados: ${esperados.length}  ·  ya existen: ${esperados.length - faltantes.length}`);

if (!faltantes.length) {
  console.log('\x1b[32mNada que crear: todos los tags del bot existen.\x1b[0m');
} else {
  console.log(`\nFaltan ${faltantes.length}:`);
  for (const t of faltantes) {
    if (DRY) { console.log(`  (dry-run) crearia ${t}`); continue; }
    try {
      await api('page/createTag', { method: 'POST', body: JSON.stringify({ name: t }) });
      console.log(`  \x1b[32m+\x1b[0m ${t}`);
    } catch (e) {
      console.error(`  \x1b[31mx\x1b[0m ${t}: ${e.message}`);
    }
  }
}

if (sobrantes.length) {
  console.log(`\n\x1b[33mAviso:\x1b[0m ${sobrantes.length} tag(s) con el prefijo que el bot NO usa:`);
  sobrantes.forEach((t) => console.log(`  ? ${t}`));
  console.log('  (no se borran desde aqui: revisalos a mano antes de eliminar nada)');
}
