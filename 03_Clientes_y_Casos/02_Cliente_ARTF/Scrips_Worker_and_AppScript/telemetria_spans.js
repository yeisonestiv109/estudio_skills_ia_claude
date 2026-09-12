/**
 * ===========================================================================
 * TELEMETRIA DE TRAZAS — observabilidad del bot V4.2 (11-sep-2026)
 * ===========================================================================
 *
 * QUE RESUELVE
 * Hasta hoy, cuando el bot le mandaba a un lead un mensaje raro, la unica
 * forma de saber por que era leer `activity_log` y adivinar hacia atras. No
 * quedaba registro de QUE entendio el LLM, que decidio el router, ni cuanto
 * tardo cada paso. Este modulo deja una traza por turno, con un span por paso.
 *
 * EL MODELO (OpenTelemetry, convenciones semanticas para GenAI)
 *   · Un TURNO del bot = un `trace_id`.
 *   · Cada PASO dentro del turno = un `span` (con inicio, fin y atributos).
 *   · `parent_span_id` arma el arbol: quien origino que.
 *
 * LAS TRES REGLAS QUE NO SE NEGOCIAN
 *
 *   1. CERO LATENCIA. Nada de esto corre en el camino de la respuesta a
 *      ManyChat. Los spans se acumulan en memoria (costo ~0) y se envian de
 *      UNA SOLA VEZ, en lote, dentro de `ctx.waitUntil()`. Una escritura extra
 *      por turno, no una por paso. Es O(1) respecto al numero de spans.
 *
 *      Por que NO se usan Cloudflare Queues (que es lo que recomienda el
 *      documento de arquitectura): Queues exige el plan Workers PAID. El lote
 *      en memoria logra el mismo desacoplamiento dentro del tier gratuito.
 *
 *   2. NUNCA TUMBA UN TURNO. Todo esta envuelto: si Supabase no responde, si
 *      el JSON no serializa, si falta una variable de entorno -- el turno del
 *      lead sigue exactamente igual. La telemetria es un testigo, no un actor.
 *
 *   3. DATOS PERSONALES ACOTADOS. Lo que escribe el lead es dato personal
 *      (Habeas Data). Aca se trunca a `MAX_TEXTO` caracteres y en la base se
 *      purga a los 30 dias (`fn_purgar_telemetry_spans`). Nunca se guarda un
 *      mensaje completo ni datos de contacto.
 *
 * COMO SE USA
 *
 *     const tz = nuevoTrazador(env, ctx, { manychat_id: subId });
 *     const s = tz.inicio(NODOS.LLM, { 'llm.model': GROQ_MODEL });
 *     ...
 *     tz.fin(s, 'OK', { 'llm.usage.total_tokens': 920 });
 *     tz.evento(NODOS.ROUTER, 'OK', { etapa_nueva: plan.etapaNueva }); // instantaneo
 *     ...
 *     tz.enviar();   // idempotente; agenda el flush en ctx.waitUntil
 */

/** Nodos del pipeline. El dashboard dibuja el mapa con ESTOS nombres: si se
 *  agrega uno aca, hay que agregarlo tambien en `telemetria/index.html`. */
export const NODOS = {
  WEBHOOK:    'MANYCHAT_WEBHOOK',
  ESTADO:     'ESTADO_DB',
  HISTORIAL:  'HISTORIAL_DB',
  LLM:        'GROQ_CLASIFICADOR',
  ROUTER:     'ROUTER_FSM',
  GENERACION: 'GENERACION_LLM',
  COMPLIANCE: 'COMPLIANCE_CHECK',
  ESCRITURA:  'SUPABASE_ESCRITURA',
  EFECTOS:    'EFECTOS_BACKGROUND',
};

/** Tope de spans por turno. Un turno normal usa 6-9; 40 es una red contra un
 *  bucle que inserte miles de filas por error. */
const MAX_SPANS = 40;

/** Recorte de cualquier texto que viaje en `attributes`. Alcanza para depurar
 *  ("¿que dijo el lead?") sin archivar la conversacion entera. */
const MAX_TEXTO = 160;

/** Probabilidad de disparar la purga de 30 dias en un turno cualquiera.
 *  Con ~60 leads/dia y varios turnos cada uno, 1% son varias purgas por semana:
 *  suficiente, y sin instalar pg_cron en una base compartida de produccion. */
const PROB_PURGA = 0.01;

const TIMEOUT_ENVIO_MS = 4000;

/** ¿La telemetria esta encendida? Se apaga con TELEMETRIA_ACTIVA="false" sin
 *  tocar codigo ni volver a desplegar la logica del bot. */
export function telemetriaActiva(env) {
  return String(env?.TELEMETRIA_ACTIVA ?? 'true').trim().toLowerCase() !== 'false';
}

/** Identificador corto y legible en el dashboard (`tr_4f9a2c…`). */
function nuevoId(prefijo) {
  const aleatorio = (globalThis.crypto?.randomUUID?.() || `${Date.now()}${Math.random()}`)
    .replace(/-/g, '').slice(0, 10);
  return `${prefijo}_${aleatorio}`;
}

/** Recorta strings largos; deja pasar numeros y booleanos tal cual. */
export function truncar(valor, max = MAX_TEXTO) {
  if (typeof valor !== 'string') return valor;
  const limpio = valor.replace(/\s+/g, ' ').trim();
  return limpio.length > max ? `${limpio.slice(0, max)}…` : limpio;
}

/**
 * Normaliza los atributos antes de guardarlos.
 *
 * Descarta `undefined` (JSON los pierde igual y ensucian el diff), trunca
 * strings y corta objetos anidados a su representacion corta: `attributes` es
 * para depurar, no un volcado de memoria.
 */
export function sanearAtributos(attrs) {
  const salida = {};
  if (!attrs || typeof attrs !== 'object') return salida;
  for (const [clave, valor] of Object.entries(attrs)) {
    if (valor === undefined) continue;
    if (valor === null || typeof valor === 'number' || typeof valor === 'boolean') {
      salida[clave] = valor;
    } else if (typeof valor === 'string') {
      salida[clave] = truncar(valor);
    } else {
      try { salida[clave] = truncar(JSON.stringify(valor)); } catch { /* se omite */ }
    }
  }
  return salida;
}

/**
 * Crea el trazador de UN turno.
 *
 * @param {object} env   variables del Worker (SUPABASE_URL, SERVICE_ROLE_KEY…)
 * @param {object} ctx   contexto de Cloudflare; de aca sale `waitUntil`
 * @param {object} contexto  { manychat_id, gestion_lead_id, etapa_bot }
 */
export function nuevoTrazador(env, ctx, contexto = {}) {
  const activa = telemetriaActiva(env) && Boolean(env?.SUPABASE_URL && env?.SUPABASE_SERVICE_ROLE_KEY);
  const traceId = nuevoId('tr');
  const spans = [];
  let enviado = false;
  let meta = {
    manychat_id: contexto.manychat_id ?? null,
    gestion_lead_id: contexto.gestion_lead_id ?? null,
    etapa_bot: contexto.etapa_bot ?? null,
  };

  /** Datos del lead que se conocen tarde (el gestion_lead_id llega con el
   *  estado, la etapa con el router). Se aplican a TODOS los spans al enviar. */
  function contexto_(datos = {}) {
    meta = { ...meta, ...Object.fromEntries(Object.entries(datos).filter(([, v]) => v !== undefined)) };
  }

  /** Abre un span. Devuelve el objeto para cerrarlo con `fin()`. */
  function inicio(nodo, attrs = {}, padre = null) {
    if (!activa || spans.length >= MAX_SPANS) return null;
    const span = {
      trace_id: traceId,
      span_id: nuevoId('sp'),
      parent_span_id: padre?.span_id ?? null,
      node_name: nodo,
      status: 'PENDING',
      started_at: new Date().toISOString(),
      ended_at: null,
      duration_ms: null,
      attributes: sanearAtributos(attrs),
      _t0: Date.now(),
    };
    spans.push(span);
    return span;
  }

  /** Cierra un span abierto por `inicio()`. Tolera `null` (telemetria apagada). */
  function fin(span, status = 'OK', attrs = {}) {
    if (!span) return null;
    span.status = status;
    span.ended_at = new Date().toISOString();
    span.duration_ms = Date.now() - span._t0;
    span.attributes = { ...span.attributes, ...sanearAtributos(attrs) };
    return span;
  }

  /** Span instantaneo: para hechos sin duracion ("el router decidio X"). */
  function evento(nodo, status = 'OK', attrs = {}) {
    const s = inicio(nodo, attrs);
    return fin(s, status);
  }

  /**
   * Arma el lote final. Los spans que quedaron abiertos se marcan PENDING: es
   * justo la señal de "el turno se murio aca", que es lo que se quiere ver.
   */
  function lote() {
    return spans.map(({ _t0, ...s }) => ({ ...s, ...meta }));
  }

  /** El envio real. Una sola llamada HTTP con todas las filas. */
  async function despachar() {
    const filas = lote();
    if (!filas.length) return;
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_ENVIO_MS);
    try {
      const resp = await fetch(`${env.SUPABASE_URL}/rest/v1/telemetry_spans`, {
        method: 'POST',
        headers: {
          apikey: env.SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
          'Content-Type': 'application/json',
          Prefer: 'return=minimal',
        },
        body: JSON.stringify(filas),
        signal: ctrl.signal,
      });
      if (!resp.ok) {
        console.warn('[telemetria] insert', resp.status, (await resp.text()).slice(0, 200));
      }
    } catch (e) {
      // A proposito no se re-lanza: la telemetria jamas puede afectar al lead.
      console.warn('[telemetria] no se pudo enviar:', e?.message);
    } finally {
      clearTimeout(t);
    }

    // Purga oportunista de datos personales viejos (ver PROB_PURGA).
    if (Math.random() < PROB_PURGA) {
      try {
        await fetch(`${env.SUPABASE_URL}/rest/v1/rpc/fn_purgar_telemetry_spans`, {
          method: 'POST',
          headers: {
            apikey: env.SUPABASE_SERVICE_ROLE_KEY,
            Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ p_dias: 30 }),
        });
      } catch (e) { console.warn('[telemetria] purga fallo:', e?.message); }
    }
  }

  /**
   * Agenda el envio. Idempotente: llamarlo dos veces no duplica filas.
   *
   * `ctx.waitUntil` mantiene vivo el isolate DESPUES de que la respuesta ya
   * viajo a ManyChat, asi que esta escritura no entra en el tiempo que el lead
   * espera. Sin `ctx` (tests, ejecucion local) simplemente no se envia nada.
   */
  function enviar() {
    if (!activa || enviado) return;
    enviado = true;
    if (ctx?.waitUntil) ctx.waitUntil(despachar());
  }

  return {
    traceId, activa, inicio, fin, evento, enviar,
    contexto: contexto_,
    // Expuestos para los tests: permiten afirmar sobre el lote sin red.
    _spans: spans,
    _lote: lote,
  };
}
