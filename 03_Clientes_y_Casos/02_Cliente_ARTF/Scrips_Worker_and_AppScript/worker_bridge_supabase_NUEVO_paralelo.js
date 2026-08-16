/**
 * Cloudflare Worker — Bridge de captura ManyChat -> Supabase (DIRECTO)
 *
 * ============================================================================
 * ESTE ES UN WORKER NUEVO, EN PARALELO al que ya existe (worker_cloudflare.md).
 * NO reemplaza ni modifica el Worker actual. Se despliega como un proyecto
 * Cloudflare Worker SEPARADO, con su propia URL. El plan (confirmado con el
 * fundador, sesion 15-ago-2026) es:
 *   1. Desplegar este Worker nuevo (URL propia, secrets propios).
 *   2. En ManyChat, agregar una SEGUNDA accion "External Request" al flow
 *      (fire-and-forget, en paralelo a la que ya existe) apuntando a la URL
 *      de ESTE Worker. Esa es la UNICA parte que toca el sistema en vivo
 *      (el flow de ManyChat) -- el Worker actual y su Apps Script/Sheet NO
 *      se tocan para nada.
 *   3. Correr en paralelo un tiempo: el Sheet sigue siendo la fuente real
 *      que usa el equipo; este Worker solo alimenta Supabase en la sombra
 *      para validar el comportamiento con trafico real antes del corte.
 *   4. Corte definitivo (fecha/hora por definir, ventana 4-6am): se
 *      desconecta el Sheet y el dashboard pasa a depender 100% de Supabase.
 * ============================================================================
 *
 * ALCANCE: replica UNICAMENTE la captura pasiva -- lo que realmente corre
 * hoy en produccion con JAVIT_ACTIVO=false (confirmado por el fundador en
 * los logs de Cloudflare, 15-ago-2026). NO incluye la logica conversacional
 * de Claude/Anthropic (esa sigue siendo una iniciativa separada y diferida,
 * ver bitacora). Si mas adelante se decide reactivar el bot conversacional,
 * ese es un Worker/decision aparte -- no se mezcla aqui a proposito, para
 * mantener este bridge simple y con la menor superficie de riesgo posible.
 *
 * DESVIACION DELIBERADA vs el comportamiento actual del Sheet (marcar para
 * revision de el fundador): el codigo actual manda handoff_humano=true /
 * handoff_razon='javit_off' en esta rama, lo que via mapEstado() termina
 * clasificando el lead como "Handoff - Otro" (mapea a estado 'calificado').
 * Un lead recien capturado, al que el bot nunca le respondio nada, no deberia
 * marcarse como calificado -- no se califico nada. Este Worker NO manda
 * handoff_humano en la captura pasiva: el lead cae limpio en estado 'nuevo'.
 * La señal de "necesita atencion humana" la siguen dando los tags de
 * ManyChat (EXISTENTE_CONVERSACION/REQUIERE_RESPUESTA_HUMANA), no el estado
 * de Supabase.
 *
 * Secrets requeridos (Cloudflare Dashboard -> este Worker -> Settings -> Variables):
 * - SUPABASE_URL: URL del proyecto Supabase (staging: https://lrdtjsxtaadpgrzkchlw.supabase.co
 *   -- CAMBIAR a produccion cuando exista un proyecto de produccion separado)
 * - SUPABASE_SERVICE_ROLE_KEY: service_role key de ese proyecto (fn_sync_bot_turn
 *   solo tiene GRANT a service_role, ver fn_sync_bot_turn.sql)
 * - MANYCHAT_API_TOKEN: MISMO token que ya usa el Worker actual (misma cuenta
 *   ManyChat, mismos tags) -- no hace falta uno nuevo.
 */

export default {
  async fetch(request, env, ctx) {
    try {
      return await handleRequest(request, env, ctx);
    } catch (err) {
      console.error('UNCAUGHT exception en fetch handler (bridge Supabase):', err?.stack || err);
      return jsonResponse({ ok: false, error: 'uncaught_exception', detail: String(err?.message || err).slice(0, 200) }, 200);
    }
  },
};

async function handleRequest(request, env, ctx) {
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders() });
  }
  if (request.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed. Use POST.' }, 405);
  }

  let payload;
  try {
    payload = await request.json();
  } catch (e) {
    return jsonResponse({ ok: false, error: 'json_parse_error' }, 200);
  }

  // Mismo guard que el Worker actual (Bug #9): si no hay ni subscriber_id ni
  // last_text resueltos, es un retry manual sin contexto real -- no llamamos
  // a Supabase, no aplicamos tags, no gastamos nada.
  if (hasNoResolvedContext(payload)) {
    console.warn('Payload sin subscriber_id ni last_text resueltos (bridge Supabase). Ignorado.');
    return jsonResponse({ ok: true, action: 'ignored_no_context' }, 200);
  }

  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) {
    console.error('SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no configurados.');
    return jsonResponse({ ok: false, error: 'supabase_config_missing' }, 200);
  }

  // Mismos campos que ya sanitiza el Worker actual para la rama de captura pasiva.
  const subId = sanitize(payload.manychat_subscriber_id);
  const ig_username = sanitize(payload.ig_username);
  const first_name = sanitize(payload.first_name);
  const last_name = sanitize(payload.last_name);
  const full_name = sanitize(payload.full_name) ||
                     [first_name, last_name].filter(Boolean).join(' ').trim() ||
                     first_name;
  const fuente = sanitize(payload.fuente);
  const last_text = sanitize(payload.last_text);

  if (!subId) {
    // last_text si vino resuelto (paso el guard de arriba), pero sin
    // subscriber_id no hay con que hacer upsert en clientes (manychat_id
    // es la clave). No tiene sentido llamar a Supabase sin eso.
    console.warn('last_text resuelto pero sin manychat_subscriber_id. Ignorado (bridge Supabase).');
    return jsonResponse({ ok: true, action: 'ignored_no_subscriber_id' }, 200);
  }

  // 1. Tags via ManyChat API -- MISMOS 3 tags que ya aplica el Worker actual
  //    en la rama JAVIT_ACTIVO=false, mismo criterio: kill-switch a futuro +
  //    señal de "necesita atencion humana" para el equipo.
  if (env.MANYCHAT_API_TOKEN && ctx?.waitUntil) {
    ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, subId, 'EXISTENTE_CONVERSACION', 'add'));
    ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, subId, 'CONVERSACION_ACTIVA', 'remove'));
    ctx.waitUntil(applyTagAsync(env.MANYCHAT_API_TOKEN, subId, 'REQUIERE_RESPUESTA_HUMANA', 'add'));
  }

  // 2. Sincronizar a Supabase via fn_sync_bot_turn (reemplaza syncToCRM()/
  //    Apps Script/Sheet). Fire-and-forget, no bloquea la respuesta a
  //    ManyChat -- mismo patron que el Worker actual.
  const rpcPayload = {
    p_manychat_id: subId,
    p_nombre: full_name || null,
    p_ig_handle: ig_username || null,
    p_fuente_raw: fuente || null,
    // Sin handoff_humano / etapa_bot: cae en 'nuevo' por diseño (ver nota de
    // cabecera). Sin profesion/salario/dolor/urgencia: el bot nunca los
    // pregunto en esta rama.
    p_summary: 'Lead capturado en modo bridge (bot apagado). Pendiente de atencion manual.',
    p_ultimo_msg_lead: last_text || null,
  };
  if (ctx?.waitUntil) {
    ctx.waitUntil(syncToSupabase(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, rpcPayload));
  }

  return jsonResponse({ ok: true, action: 'captured', manychat_id: subId }, 200);
}

/**
 * Llama a fn_sync_bot_turn via PostgREST RPC. Mismo espiritu que syncToCRM()
 * del Worker actual: en background, si falla solo loguea (no rompe el flujo).
 */
async function syncToSupabase(supabaseUrl, serviceRoleKey, payload) {
  try {
    const resp = await fetch(`${supabaseUrl}/rest/v1/rpc/fn_sync_bot_turn`, {
      method: 'POST',
      headers: {
        'apikey': serviceRoleKey,
        'Authorization': `Bearer ${serviceRoleKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      console.error('fn_sync_bot_turn error:', resp.status, await resp.text());
    } else {
      const result = await resp.json();
      console.log('Supabase sync OK:', JSON.stringify(result));
    }
  } catch (e) {
    console.error('Error sincronizando a Supabase:', e?.message);
  }
}

/**
 * Aplica/remueve un tag a un contacto via API de ManyChat. Identico al
 * helper del Worker actual (mismo comportamiento, mismo fire-and-forget).
 */
async function applyTagAsync(token, subscriberId, tagName, action) {
  if (!token || !subscriberId || !tagName) return;
  const endpoint = action === 'remove' ? 'removeTagByName' : 'addTagByName';
  try {
    const resp = await fetch('https://api.manychat.com/fb/subscriber/' + endpoint, {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ subscriber_id: subscriberId, tag_name: tagName }),
    });
    if (!resp.ok) {
      console.error('Tag ' + action + ' failed:', tagName, resp.status, await resp.text());
    }
  } catch (e) {
    console.error('Error aplicando tag ' + tagName + ':', e?.message);
  }
}

/** Identico al Worker actual: limpia placeholders de ManyChat sin resolver. */
function sanitize(value) {
  if (value === null || value === undefined) return '';
  const str = String(value).trim();
  if (/^\{\{(cuf_|sys_|user_|sub_|sub_id|first_name|last_name|ig_username|user_id)/i.test(str)) {
    return '';
  }
  if (/^\{\{.+\}\}$/.test(str)) {
    return '';
  }
  return str;
}

/** Identico al Worker actual (Bug #9). */
function hasNoResolvedContext(payload) {
  return !sanitize(payload?.manychat_subscriber_id) && !sanitize(payload?.last_text);
}

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders() },
  });
}

export { sanitize, hasNoResolvedContext };
