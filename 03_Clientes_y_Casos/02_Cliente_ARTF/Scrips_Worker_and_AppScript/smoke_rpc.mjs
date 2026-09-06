#!/usr/bin/env node
/**
 * COMPUERTA 4 — smoke de las RPC del bot contra la base REAL.
 *
 * Prueba lo que los tests unitarios no pueden: que las funciones existan en la
 * base, que respondan, y sobre todo que las GUARDAS sigan puestas. Todo dentro
 * de datos de prueba que se limpian al final.
 *
 * Necesita: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el entorno.
 * Si no estan, se salta sin fallar (no todo el mundo tiene la service_role).
 */
const URL_BASE = process.env.SUPABASE_URL;
const KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const ID = '900000001'; // manychat_id reservado para este smoke

if (!URL_BASE || !KEY) {
  console.log('  (omitido: exporta SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY)');
  process.exit(0);
}

let fallos = 0;
const ok = (m) => console.log(`\x1b[32m  PASA\x1b[0m  ${m}`);
const malo = (m) => { console.log(`\x1b[31m  FALLA\x1b[0m ${m}`); fallos++; };

async function rpc(fn, body) {
  const r = await fetch(`${URL_BASE}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return { status: r.status, cuerpo: await r.text() };
}

// 1. Un lead que no existe devuelve vacio (no revienta)
let r = await rpc('fn_bot_get_estado', { p_manychat_id: 'NO_EXISTE_999' });
r.status === 200 && r.cuerpo.trim() === '[]'
  ? ok('fn_bot_get_estado: lead inexistente -> []')
  : malo(`fn_bot_get_estado inexistente -> ${r.status} ${r.cuerpo.slice(0, 120)}`);

// 2. Escribir un turno y leerlo de vuelta
r = await rpc('fn_bot_procesar_turno', {
  p_manychat_id: ID, p_nombre: '[PRUEBA] Smoke RPC',
  p_etapa_bot: 'M1_ENVIADO', p_estado_destino: 'contactado',
  p_summary: 'smoke de la compuerta 4', p_ultimo_msg_lead: 'CONTROL',
});
r.status === 200 ? ok('fn_bot_procesar_turno: escribe un turno') : malo(`escritura -> ${r.status} ${r.cuerpo.slice(0, 160)}`);

r = await rpc('fn_bot_get_estado', { p_manychat_id: ID });
try {
  const fila = JSON.parse(r.cuerpo)[0];
  fila?.out_etapa_bot === 'M1_ENVIADO' && fila?.out_estado_codigo === 'contactado'
    ? ok('fn_bot_get_estado: devuelve el estado escrito')
    : malo(`lectura devolvio ${JSON.stringify(fila)}`);
} catch { malo(`lectura no parseable: ${r.cuerpo.slice(0, 120)}`); }

// 3. LA GUARDA: el bot NO puede escribir 'agendado'
r = await rpc('fn_bot_procesar_turno', { p_manychat_id: ID, p_estado_destino: 'agendado' });
r.status >= 400 && /no puede escribir el estado/.test(r.cuerpo)
  ? ok('guarda dura: el bot NO puede escribir "agendado"')
  : malo(`la guarda de "agendado" NO salto (status ${r.status})`);

// 4. SITIO 1 de la trampa: el CHECK de la base (via fn_etapa_bot_valida).
// Una etapa que el router escribe pero la base rechaza tumba el turno entero.
// Esta lista tiene que incluir TODA etapa que el router pueda escribir.
const ETAPAS_QUE_ESCRIBE_EL_ROUTER = [
  'M1_ENVIADO', 'M1_INGRESO_AMBIGUO', 'M1_RANGO_PREGUNTADO', 'M1_ACLARAR_REMANENTE',
  'M2_ENVIADO', 'M2_BORDERLINE', 'M2_NO_SABE',
  'M3_ENVIADO', 'M3_RECONDUCIR',
  'M4_ENVIADO', 'M4_URGENCIA_REINTENTO',
  'M5_ENVIADO', 'M5_PITCH_REINTENTO',
  'M6_ENVIADO', 'M7_ENVIADO', 'M7_ESPERANDO_VINCULO',
  'SIN_HORARIOS_ESPERANDO_FRANJA', // 5-sep-2026 -- ver bot_router_v42.js
  'RETORNO_PREGUNTA', 'HANDOFF',
];
for (const etapa of ETAPAS_QUE_ESCRIBE_EL_ROUTER) {
  r = await rpc('fn_bot_procesar_turno', { p_manychat_id: ID, p_etapa_bot: etapa });
  if (r.status !== 200) { malo(`la base rechazo la etapa ${etapa}: ${r.cuerpo.slice(0, 100)}`); break; }
}
fallos === 0 && ok(`la base acepta las ${ETAPAS_QUE_ESCRIBE_EL_ROUTER.length} etapas que escribe el router`);

// 4.b Telemetria del LLM: la tabla y la RPC que alimentan el dashboard.
r = await rpc('fn_registrar_telemetria_llm', {
  p_proveedor: 'groq', p_modelo: 'smoke-test', p_llave_alias: 'principal',
  p_resultado: 'ok', p_tokens_salida: 100,
  p_limite_tokens: 8000, p_restantes_tokens: 7900, p_reset_tokens: '480ms',
});
if (r.status === 200 || r.status === 204) {
  // 204 (sin cuerpo) es la respuesta NORMAL de PostgREST para una funcion
  // `RETURNS void` como esta -- no es un fallo. Bug real 5-sep-2026: el
  // smoke solo aceptaba 200 y marcaba rojo una llamada que si funciono.
  ok('fn_registrar_telemetria_llm: registra una llamada');
} else if (r.status === 404 && r.cuerpo.includes('PGRST202')) {
  // Caso visto el 5-sep: la tabla y la funcion EXISTEN y funcionan llamandolas
  // desde SQL, pero PostgREST no las tiene en su cache de esquema. Es infra de
  // Supabase, no el codigo. Se distingue a proposito de un fallo real: el
  // mensaje tiene que decir que hacer, no solo que fallo.
  malo('telemetria: PostgREST no ve la funcion todavia (cache de esquema obsoleta).\n'
     + '         La tabla y la RPC SI existen y funcionan desde SQL.\n'
     + '         ARREGLO: Supabase Dashboard -> Settings -> API -> "Restart server",\n'
     + '         o cualquier cambio de esquema desde la UI fuerza la recarga.');
} else {
  malo(`telemetria no registro (status ${r.status}): ${r.cuerpo.slice(0, 120)}`);
}

// La ventana de OTPM tiene que ACUMULAR dentro del mismo minuto: si se
// reiniciara en cada llamada, el dashboard mostraria siempre capacidad llena.
r = await rpc('fn_registrar_telemetria_llm', {
  p_proveedor: 'groq', p_modelo: 'smoke-test', p_llave_alias: 'principal',
  p_resultado: 'ok', p_tokens_salida: 50,
});
(r.status === 200 || r.status === 204)
  ? ok('telemetria: segunda llamada aceptada')
  : malo(`telemetria: segunda llamada fallo (status ${r.status})`);

// 5. Limpieza: el lead queda en terminal (activity_log es append-only, no se borra)
await rpc('fn_bot_procesar_turno', {
  p_manychat_id: ID, p_etapa_bot: 'DESCALIFICADO', p_estado_destino: 'descalificado',
  p_summary: 'fin del smoke -- lead de prueba, ignorar',
});
ok('lead de prueba cerrado (buscar "[PRUEBA] Smoke RPC" para limpiarlo)');

process.exit(fallos ? 1 : 0);
