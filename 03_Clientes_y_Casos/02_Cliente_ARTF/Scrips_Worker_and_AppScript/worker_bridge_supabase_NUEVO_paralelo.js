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
 * ============================================================================
 * AMPLIACION 29-ago-2026 -- Captura total + validacion de agenda con Groq
 * ============================================================================
 * 1. Captura total: este Worker ahora se llama en CADA mensaje entrante del
 *    lead (antes solo en el primer mensaje -- el "Kill switch-leads
 *    existentes" del Flow de ManyChat bloqueaba el resto, ver instrucciones
 *    de Flow entregadas al fundador la misma sesion). fn_sync_bot_turn ya
 *    insertaba una fila nueva en activity_log en cada llamada (append-only
 *    real, sin cambios) -- lo que SI tenia un bug real y se corrigio en la
 *    misma sesion: sin p_etapa_bot (este Worker nunca lo manda), el destino
 *    por default era 'nuevo' fijo, y 'agendado'->'nuevo' SI es una
 *    transicion legal (existe para "Devolver a Nuevo") -- cualquier mensaje
 *    de un lead ya agendado lo regresaba a 'nuevo' en silencio. Corregido en
 *    fn_sync_bot_turn.sql: sin señal de etapa, el destino es quedarse donde
 *    esta, nunca 'nuevo' fijo.
 * 2. Validacion de agenda con Groq: cuando fn_sync_bot_turn devuelve
 *    out_estado_codigo='agendado' (el lead YA tiene una cita real
 *    confirmada contra Google Calendar -- eso no lo evalua el LLM, ya esta
 *    verificado), se clasifica el mensaje del lead en 3 categorias
 *    (confirmacion / reagendar_o_cancelar / otro) -- NO un booleano
 *    confirmo/problema, ver procesarSiAgendado() para el razonamiento
 *    completo. Enteramente fire-and-forget dentro del mismo ctx.waitUntil
 *    que ya corria syncToSupabase -- nunca retrasa la respuesta HTTP a
 *    ManyChat.
 *
 * ============================================================================
 * PAUSA 30-ago-2026 -- la validacion de agenda con Groq (punto 2 de arriba)
 * ============================================================================
 * Decision del fundador: por ahora se prioriza dejar todo el sistema
 * funcionando end-to-end (captura total en activity_log SI sigue aprobada,
 * ver punto 1) para poder lanzarse a probarlo con trafico real, aunque
 * ciertas cosas no sean automaticas todavia. La llamada a
 * procesarSiAgendado() esta comentada en handleRequest() -- la funcion sigue
 * completa e intacta en este archivo, es solo cuestion de descomentar esa
 * linea cuando se retome (estimado: proximas semanas, una vez el sistema
 * este probado y con datos limpios). Ver bitacora, sesion 30-ago-2026.
 *
 * Secrets requeridos (Cloudflare Dashboard -> este Worker -> Settings -> Variables):
 * - SUPABASE_URL: URL del proyecto Supabase (staging: https://lrdtjsxtaadpgrzkchlw.supabase.co
 *   -- CAMBIAR a produccion cuando exista un proyecto de produccion separado)
 * - SUPABASE_SERVICE_ROLE_KEY: service_role key de ese proyecto (fn_sync_bot_turn
 *   solo tiene GRANT a service_role, ver fn_sync_bot_turn.sql)
 * - MANYCHAT_API_TOKEN: MISMO token que ya usa el Worker actual (misma cuenta
 *   ManyChat, mismos tags) -- no hace falta uno nuevo.
 * - GROQ_API_KEY: nueva (29-ago-2026) -- key de Groq para la clasificacion de
 *   respuesta post-agenda. Sin esta, procesarSiAgendado() se salta entero,
 *   sin error (mismo contrato de resiliencia de siempre).
 * - MANYCHAT_FLOW_NS_CONFIRMACION: MISMO flow_ns que ya usa el dashboard
 *   Next.js (src/lib/manychat/actions.ts, confirmarRespuestaLeadYNotificar)
 *   -- reusar el mismo, no crear uno nuevo en ManyChat.
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
    // Sin handoff_humano / etapa_bot: nunca se mueve el lead hacia atras ni
    // adelante sin señal real (ver fix 29-ago-2026 en fn_sync_bot_turn.sql).
    // Sin profesion/salario/dolor/urgencia: el bot nunca los pregunto en
    // esta rama.
    p_summary: 'Captura pasiva del lead via ManyChat -- sin bot conversacional activo.',
    p_ultimo_msg_lead: last_text || null,
  };
  if (ctx?.waitUntil) {
    // PAUSADO (30-ago-2026, decision del fundador): la validacion de agenda
    // con Groq (procesarSiAgendado) queda desconectada por ahora -- prioridad
    // es dejar el sistema funcionando end-to-end (aunque ciertas cosas no
    // sean automaticas) para poder lanzarse a probarlo, no agregar mas
    // automatizacion todavia. La funcion procesarSiAgendado() sigue completa
    // mas abajo en este archivo, lista para reconectarse en unas semanas --
    // ver bitacora 01_Gobernanza_EOS/02_backlog_y_rocas.md, sesion 30-ago,
    // para el detalle de la decision. Para reactivar: descomentar el
    // .then(...) de abajo (requiere GROQ_API_KEY + MANYCHAT_FLOW_NS_CONFIRMACION
    // configurados en este Worker).
    ctx.waitUntil(
      syncToSupabase(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, rpcPayload),
      // .then((resultado) => procesarSiAgendado(resultado, last_text, subId, env)),
    );
  }

  return jsonResponse({ ok: true, action: 'captured', manychat_id: subId }, 200);
}

/**
 * Llama a fn_sync_bot_turn via PostgREST RPC. Mismo espiritu que syncToCRM()
 * del Worker actual: en background, si falla solo loguea (no rompe el flujo).
 *
 * Devuelve el resultado parseado (29-ago-2026, antes no devolvia nada) --
 * PostgREST entrega RETURNS TABLE como un array de filas, ej.
 * [{ out_cliente_id, out_gestion_lead_id, out_estado_codigo, out_avanzo }].
 * Devuelve null si falla, para que el caller lo trate igual que "sin dato".
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
      return null;
    }
    const result = await resp.json();
    console.log('Supabase sync OK:', JSON.stringify(result));
    return result;
  } catch (e) {
    console.error('Error sincronizando a Supabase:', e?.message);
    return null;
  }
}

// Modelo Groq (29-ago-2026): qwen/qwen3.8-27b, NO openai/gpt-oss-120b --
// bug documentado (ignora json_schema/strict:true de forma inconsistente,
// ver memoria artf_feature2_llm_extraction_blocked -- reverificado contra
// docs oficiales + comunidad de Groq, reportes siguen activos pese a que
// los docs ya lo listan soportado). Mismo modelo ya usado en
// src/lib/ai/extraerDatosLead.ts del dashboard Next.js, por consistencia.
const GROQ_MODEL = 'qwen/qwen3.8-27b';
// Groq es rapido (normalmente <1s) -- este limite es una red de seguridad
// para no dejar el ctx.waitUntil colgado, no un presupuesto de latencia real.
const GROQ_TIMEOUT_MS = 4000;

/**
 * Clasifica la respuesta de un lead YA agendado (29-ago-2026).
 *
 * Decision de diseño, no la propuesta original: NO es un booleano
 * confirmo=true/false. Razon real: out_estado_codigo='agendado' en Supabase
 * ya es un HECHO verificado contra un evento real de Google Calendar (ver
 * sync.ts del dashboard) -- la base de datos no necesita que el LLM le
 * confirme que el agendamiento existe, eso ya lo sabe. La pregunta que de
 * verdad hace falta responder es otra: dado que el lead YA esta agendado,
 * ¿este mensaje nuevo pide cambiar/cancelar esa cita, o es solo un
 * agradecimiento sin accion? Un booleano confirmo/problema fuerza una
 * eleccion falsa en los casos reales mas comunes (agradecimiento simple,
 * pregunta sin relacion, silencio) -- 3 categorias cubre esto sin adivinar.
 *
 * Devuelve 'confirmacion' | 'reagendar_o_cancelar' | 'otro' | null (null =
 * Groq fallo/timeout/respuesta no parseable -- el caller debe tratarlo como
 * "no se pudo clasificar", nunca como "confirmo").
 */
async function clasificarRespuestaAgendado(groqApiKey, mensajeLead) {
  if (!groqApiKey || !mensajeLead) return null;

  const systemPrompt = `Eres un clasificador. Un lead YA tiene una cita real confirmada en el calendario -- esto ya está verificado, no es algo que tengas que evaluar tú. Acaba de responder algo después de que se le envió el link para agendar. Clasifica su mensaje en UNA sola categoría:

- "confirmacion": agradecimiento, confirmación simple, o cualquier mensaje neutral/positivo sin pedir cambios (ej. "listo", "gracias", "perfecto", "nos vemos", un emoji, "ya quedé agendada").
- "reagendar_o_cancelar": el lead pide cambiar la hora, cancelar, dice que tuvo un problema con el horario, o que no puede asistir a la cita que ya tiene.
- "otro": cualquier otra cosa -- pregunta no relacionada, mensaje ambiguo, o cualquier caso que no encaje claramente en las dos anteriores.

Si tienes duda entre "confirmacion" y cualquier otra categoría, elige la otra -- nunca asumas confirmación sin que el mensaje sea claro.

Devuelve ÚNICAMENTE este JSON, sin texto antes ni después, sin markdown:
{"categoria": "confirmacion" | "reagendar_o_cancelar" | "otro"}`;

  const abortController = new AbortController();
  const timeoutId = setTimeout(() => abortController.abort(), GROQ_TIMEOUT_MS);
  try {
    const resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${groqApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: GROQ_MODEL,
        temperature: 0,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: mensajeLead.slice(0, 1000) },
        ],
      }),
      signal: abortController.signal,
    });
    if (!resp.ok) {
      console.error('Groq error:', resp.status, await resp.text());
      return null;
    }
    const data = await resp.json();
    const raw = data?.choices?.[0]?.message?.content;
    if (!raw || typeof raw !== 'string') return null;

    // Limpieza defensiva de fences markdown residuales antes de parsear
    // (mismo criterio que extraerDatosLead.ts del dashboard), por si el
    // modelo los agrega pese a response_format: json_object.
    const limpio = raw
      .trim()
      .replace(/^```json\s*/i, '')
      .replace(/^```\s*/i, '')
      .replace(/\s*```\s*$/i, '')
      .trim();

    const parsed = JSON.parse(limpio);
    const categoriasValidas = ['confirmacion', 'reagendar_o_cancelar', 'otro'];
    if (!categoriasValidas.includes(parsed?.categoria)) return null;
    return parsed.categoria;
  } catch (e) {
    console.error('Error clasificando con Groq:', e?.message);
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Dispara un Flow de ManyChat via API -- mismo endpoint que ya usa el
 * dashboard Next.js (enviarFlujo en src/lib/manychat/client.ts), replicado
 * acá porque este Worker corre en un runtime separado (Cloudflare, no
 * Vercel) y no puede importar ese modulo directo.
 */
async function enviarFlujoAsync(token, subscriberId, flowNs) {
  if (!token || !subscriberId || !flowNs) return;
  try {
    const resp = await fetch('https://api.manychat.com/fb/sending/sendFlow', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer ' + token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ subscriber_id: subscriberId, flow_ns: flowNs }),
    });
    if (!resp.ok) {
      console.error('sendFlow failed:', resp.status, await resp.text());
    }
  } catch (e) {
    console.error('Error enviando flow:', e?.message);
  }
}

/**
 * Orquesta la clasificación + acción cuando fn_sync_bot_turn confirma que
 * el lead ya está "agendado" (29-ago-2026). Se llama encadenada DESPUES de
 * syncToSupabase, dentro del mismo ctx.waitUntil -- nunca retrasa la
 * respuesta HTTP a ManyChat (esa ya se mandó antes).
 *
 * Sin GROQ_API_KEY o MANYCHAT_API_TOKEN configurados: se sale sin hacer
 * nada, sin error -- mismo contrato de resiliencia que el resto del
 * sistema (esto es una mejora, no un requisito para que el resto del
 * Worker funcione).
 *
 * Si Groq no logra clasificar (categoria === null): tampoco se hace nada
 * acá -- el Smart Delay de 30 min en ManyChat (ver instrucciones aparte)
 * manda el agradecimiento de todos modos si nadie puso el tag
 * RESPUESTA_AGENDA_PROCESADA, así que un fallo de Groq nunca deja al lead
 * sin su mensaje final.
 */
async function procesarSiAgendado(resultadoSync, lastText, subId, env) {
  const estado = resultadoSync?.[0]?.out_estado_codigo;
  if (estado !== 'agendado') return;
  if (!env.GROQ_API_KEY || !env.MANYCHAT_API_TOKEN) return;

  const categoria = await clasificarRespuestaAgendado(env.GROQ_API_KEY, lastText);
  const TAG_PROCESADO = 'RESPUESTA_AGENDA_PROCESADA';

  if (categoria === 'confirmacion') {
    if (env.MANYCHAT_FLOW_NS_CONFIRMACION) {
      await enviarFlujoAsync(env.MANYCHAT_API_TOKEN, subId, env.MANYCHAT_FLOW_NS_CONFIRMACION);
    }
    await applyTagAsync(env.MANYCHAT_API_TOKEN, subId, TAG_PROCESADO, 'add');
  } else if (categoria === 'reagendar_o_cancelar' || categoria === 'otro') {
    // Deliberado: NO se manda el flow de agradecimiento acá -- seria
    // insensible mandar "gracias, nos vemos" justo cuando el lead dijo que
    // necesita cambiar o cancelar la cita.
    await applyTagAsync(env.MANYCHAT_API_TOKEN, subId, 'REQUIERE_ATENCION_AGENDA', 'add');
    await applyTagAsync(env.MANYCHAT_API_TOKEN, subId, TAG_PROCESADO, 'add');
  }
  // categoria === null (Groq fallo/timeout/respuesta invalida): no se toca
  // ningun tag -- el Smart Delay de 30 min manda el agradecimiento igual.
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
