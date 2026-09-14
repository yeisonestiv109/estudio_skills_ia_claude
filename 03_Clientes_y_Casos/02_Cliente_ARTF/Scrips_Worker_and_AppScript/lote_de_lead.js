/**
 * FASE 2B — Agrupamiento de burbujas con Durable Objects (14-sep-2026).
 * =============================================================================
 *
 * POR QUE EXISTE (el experimento de la Fase 0, 13-sep-2026)
 * --------------------------------------------------------
 * Un lead casi nunca escribe una sola burbuja. Escribe "Hola", luego "soy
 * ingeniero", luego "gano 12 millones". Hasta hoy cada burbuja era un turno
 * entero del bot: tres lecturas de estado, tres llamadas al LLM y tres
 * respuestas, contestando a un mensaje incompleto.
 *
 * La Fase 0 midio como se comporta ManyChat metiendo una espera de 5 s en el
 * Worker. El resultado fue concluyente y descarto el camino facil:
 *
 *   · la traza que empezo a las 00:55:24 arranco su espera de 5 s;
 *   · la siguiente NO entro hasta las 00:55:31 -- 7 segundos despues, justo
 *     cuando el Worker solto la primera.
 *
 * Es decir: ManyChat ENCOLA los webhooks por contacto y no dispara el segundo
 * hasta que el Worker contesta el primero. Por eso el "debounce sincrono"
 * (dormir dentro del Worker) es inutil: no agrupa nada, solo bloquea la cola de
 * ManyChat y retrasa el mensaje siguiente.
 *
 * Para agrupar de verdad hace falta contestar RAPIDO y pensar DESPUES. Eso es
 * asincronia real, y en Cloudflare eso es un Durable Object.
 *
 * COMO FUNCIONA
 * -------------
 *   1. El Worker autentica el webhook y se lo pasa a este objeto -- uno por
 *      `subscriber_id` -- y contesta a ManyChat `responder:false` en ~50 ms.
 *      El Flow ya condiciona por ese campo, asi que no manda nada y libera la
 *      cola: la burbuja siguiente entra enseguida.
 *   2. Cada burbuja que llega se guarda y REPROGRAMA la alarma. Mientras el
 *      lead siga escribiendo, la alarma se corre hacia adelante (debounce).
 *   3. Cuando para de escribir y la alarma vence, se juntan las burbujas en un
 *      solo texto y se procesa UN turno con el pipeline de siempre.
 *   4. Como ya no hay una peticion HTTP viva a la que contestar, la respuesta
 *      sale por la API de ManyChat (`/fb/sending/sendContent`).
 *
 * POR QUE UN DURABLE OBJECT Y NO OTRA COSA
 * ----------------------------------------
 * Cloudflare garantiza que solo hay UNA instancia por nombre y que ejecuta en
 * un solo hilo. Como el nombre es el `subscriber_id`, los turnos de un mismo
 * lead quedan serializados POR CONSTRUCCION. Es el mismo problema que el
 * compare-and-swap de la Fase 1 resolvia en la base, pero atacado en el origen.
 *
 * ⚠️ EL CAS NO SE RETIRA. Durante el despliegue conviven turnos que entraron
 * por el camino viejo y por el nuevo, y el bot tambien escribe desde el
 * dashboard. El CAS es la red; esto es el orden.
 *
 * ⚠️ PLAN GRATUITO: SOLO BACKEND SQLITE. En el plan Free de Cloudflare
 * unicamente existen los Durable Objects con almacenamiento SQLite; los de
 * key-value exigen plan de pago. Por eso la migracion del `wrangler.toml` va
 * con `new_sqlite_classes` y NO con `new_classes` -- con el segundo el deploy
 * falla y el error no dice por que.
 *
 * LO QUE ESTE DISEÑO PIERDE, Y COMO SE COMPENSA
 * --------------------------------------------
 * Al contestar 200 antes de pensar, se pierde el reintento de ManyChat: si algo
 * falla despues, ManyChat ya recibio su OK y no vuelve a llamar. Por eso
 * `alarm()` relanza la excepcion cuando el envio falla: Cloudflare reintenta la
 * alarma con backoff propio, y las burbujas siguen guardadas hasta que salgan.
 */

/** Ventana de agrupamiento. Decision del fundador (14-sep-2026): 6-8 s. */
export const VENTANA_MS_POR_DEFECTO = 7000;

/**
 * Tope duro desde la PRIMERA burbuja del lote.
 *
 * Sin esto el debounce se puede renovar para siempre: un lead que escribe una
 * palabra cada 5 segundos nunca dejaria vencer la alarma y el bot no
 * contestaria jamas. Pasado el tope se procesa lo que haya.
 */
export const TOPE_MS_POR_DEFECTO = 25000;

/** Mas burbujas que esto en un lote y se procesa ya, sin esperar la ventana. */
export const MAX_BURBUJAS_POR_LOTE = 12;

/** Reintentos del envio a ManyChat antes de rendirse y dejarlo en la traza. */
export const MAX_REINTENTOS_ENVIO = 3;

export const CLAVE_MENSAJES = 'mensajes';
export const CLAVE_PRIMERO_EN = 'primero_en';
export const CLAVE_REINTENTOS = 'reintentos';

/** Lee un entero de env con default, ignorando basura. */
export function enteroDeEnv(env, nombre, porDefecto) {
  const n = Number(env?.[nombre]);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : porDefecto;
}

/**
 * Junta las burbujas en el texto de UN turno.
 *
 * Se separan con salto de linea, que es como el LLM ya ve el historial. No se
 * inventa puntuacion ni se reordena: el orden de llegada es el orden en que el
 * lead lo penso.
 *
 * Se descartan las vacias (ManyChat manda `last_text` vacio cuando el lead
 * envia un sticker o una imagen) y se colapsan las repetidas CONSECUTIVAS, que
 * son casi siempre un doble envio del mismo mensaje.
 */
export function juntarBurbujas(mensajes) {
  const textos = [];
  for (const m of mensajes || []) {
    const t = String(m?.texto ?? '').trim();
    if (!t) continue;
    if (textos.length && textos[textos.length - 1] === t) continue;
    textos.push(t);
  }
  return textos.join('\n');
}

/**
 * Cuerpo para `POST /fb/sending/sendContent` (API v2 de ManyChat).
 *
 * UNA burbuja por llamada, a proposito. Meter varias en `messages` seria una
 * sola llamada, pero la regla R1_LINK_AISLADO del playbook existe por un bug
 * CONFIRMADO en produccion: si algo viaja pegado al link, Instagram los
 * concatena y el link queda invalido ("Dynamic Link Not Found"). Una llamada
 * por burbuja hace imposible ese error, y ademas permite reintentar solo la que
 * fallo en vez de reenviar el bloque entero y duplicarle mensajes al lead.
 */
export function cuerpoSendContent(subscriberId, texto, messageTag = null) {
  const cuerpo = {
    subscriber_id: subscriberId,
    data: {
      version: 'v2',
      content: {
        messages: [{ type: 'text', text: texto }],
      },
    },
  };
  if (messageTag) cuerpo.message_tag = messageTag;
  return cuerpo;
}

/**
 * Envia las burbujas EN ORDEN y una por una.
 *
 * Secuencial y no en paralelo: el orden del guion importa -- el link va de
 * ultimo -- y con `Promise.all` el orden de llegada no esta garantizado.
 *
 * Devuelve cuantas salieron. Si una falla se corta ahi: reenviar las siguientes
 * dejaria al lead con una conversacion con huecos, que es peor que una respuesta
 * incompleta que el reintento puede completar.
 */
export async function enviarBurbujas(token, subscriberId, burbujas, fetchImpl = fetch) {
  let enviadas = 0;
  for (const texto of burbujas) {
    const r = await fetchImpl('https://api.manychat.com/fb/sending/sendContent', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpoSendContent(subscriberId, texto)),
    });
    if (!r.ok) {
      const detalle = await r.text().catch(() => '');
      throw new Error(`sendContent ${r.status}: ${detalle.slice(0, 200)} (burbuja ${enviadas + 1}/${burbujas.length})`);
    }
    enviadas++;
  }
  return enviadas;
}

/**
 * ¿Toca procesar ya, sin esperar mas?
 *
 * Separado de la clase para poder probarlo sin levantar el runtime de
 * Cloudflare, que es donde vive el resto.
 */
export function debeProcesarYa(mensajes, primeroEn, ahora, topeMs, maxBurbujas) {
  if (mensajes.length >= maxBurbujas) return true;
  if (primeroEn && ahora - primeroEn >= topeMs) return true;
  return false;
}

export class LoteDeLead {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    this.storage = ctx.storage;
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === '/encolar') return this.encolar(request);
    if (url.pathname === '/estado') return this.verEstado();
    return new Response('ruta desconocida', { status: 404 });
  }

  /** Diagnostico: que hay en el lote ahora mismo. No expone el texto completo. */
  async verEstado() {
    const mensajes = (await this.storage.get(CLAVE_MENSAJES)) || [];
    const primeroEn = (await this.storage.get(CLAVE_PRIMERO_EN)) || null;
    const alarma = await this.storage.getAlarm();
    return Response.json({
      burbujas: mensajes.length,
      primero_en: primeroEn,
      alarma_en: alarma,
      faltan_ms: alarma ? Math.max(0, alarma - Date.now()) : null,
    });
  }

  /**
   * Guarda una burbuja y corre la alarma hacia adelante.
   *
   * El Worker ya autentico y ya valido el payload: aca no se vuelve a hacer
   * porque este objeto no es alcanzable desde fuera -- solo desde el binding.
   */
  async encolar(request) {
    const payload = await request.json();
    const ahora = Date.now();

    const mensajes = (await this.storage.get(CLAVE_MENSAJES)) || [];
    const primeroEn = (await this.storage.get(CLAVE_PRIMERO_EN)) || ahora;

    mensajes.push({
      texto: String(payload?.last_text ?? ''),
      last_interaction: payload?.last_interaction ?? null,
      recibido_en: ahora,
    });

    // El payload base es el del PRIMER mensaje del lote (trae nombre, handle y
    // demas campos del Flow); solo el texto y el timestamp se recalculan al
    // procesar. Asi un campo que ManyChat solo manda a veces no se pierde.
    if (mensajes.length === 1) await this.storage.put('payload_base', payload);

    await this.storage.put(CLAVE_MENSAJES, mensajes);
    await this.storage.put(CLAVE_PRIMERO_EN, primeroEn);

    const topeMs = enteroDeEnv(this.env, 'LOTE_TOPE_MS', TOPE_MS_POR_DEFECTO);
    const ventanaMs = enteroDeEnv(this.env, 'LOTE_VENTANA_MS', VENTANA_MS_POR_DEFECTO);
    const maxBurbujas = enteroDeEnv(this.env, 'LOTE_MAX_BURBUJAS', MAX_BURBUJAS_POR_LOTE);

    // Con el tope alcanzado la alarma se deja donde esta (o se pone ya mismo):
    // renovarla otra vez seria justamente lo que el tope existe para impedir.
    if (debeProcesarYa(mensajes, primeroEn, ahora, topeMs, maxBurbujas)) {
      const alarmaActual = await this.storage.getAlarm();
      if (!alarmaActual || alarmaActual > ahora) await this.storage.setAlarm(ahora);
    } else {
      await this.storage.setAlarm(ahora + ventanaMs);
    }

    return Response.json({ ok: true, burbujas: mensajes.length });
  }

  /**
   * Vence la ventana: se procesa el lote.
   *
   * ⚠️ Las burbujas NO se borran hasta que la respuesta salio. Si esto falla a
   * medias, la excepcion hace que Cloudflare reintente la alarma y el lote
   * sigue intacto. Borrar antes seria perder el mensaje del lead.
   */
  async alarm() {
    const mensajes = (await this.storage.get(CLAVE_MENSAJES)) || [];
    if (!mensajes.length) return;

    const payloadBase = (await this.storage.get('payload_base')) || {};
    const texto = juntarBurbujas(mensajes);
    const subId = String(payloadBase.manychat_subscriber_id ?? '');

    if (!texto || !subId) {
      // Nada que procesar (solo stickers, por ejemplo). Se limpia y se sale.
      await this.limpiar();
      return;
    }

    // El `last_interaction` del lote es el de la ULTIMA burbuja: es lo que hace
    // distinta esta clave de idempotencia de la del turno anterior.
    const ultima = mensajes[mensajes.length - 1];
    const payload = {
      ...payloadBase,
      last_text: texto,
      last_interaction: ultima?.last_interaction ?? payloadBase.last_interaction ?? null,
    };

    // Se reusa el pipeline COMPLETO del Worker (auth, estado, memoria, LLM,
    // router, compare-and-swap, tags, alertas y telemetria) construyendo la
    // peticion que ese pipeline espera. Duplicar 600 lineas aca para "adaptarlo"
    // seria crear un segundo bot que se desincroniza del primero al primer
    // cambio de reglas.
    const { manejar } = await import('./worker_bot_setter_v42.js');

    const pendientes = [];
    const ctxFalso = { waitUntil: (p) => { pendientes.push(p); } };

    const peticion = new Request('https://lote.interno/turno', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Bot-Secret': this.env.WEBHOOK_SECRET || '',
      },
      body: JSON.stringify(payload),
    });

    const respuesta = await manejar(peticion, this.env, ctxFalso);
    const datos = await respuesta.json();

    // Los efectos de fondo (tags, alerta al Setter, telemetria) se lanzaron con
    // el waitUntil falso: aca se esperan de verdad. En el Worker los remataba
    // el runtime despues de responder; en la alarma, si no se esperan, el
    // objeto puede irse a dormir con las promesas a medias.
    await Promise.allSettled(pendientes);

    const burbujas = [datos.msg, datos.msg2, datos.msg3, datos.msg4]
      .map((x) => String(x ?? '').trim())
      .filter(Boolean);

    if (!datos.responder || !burbujas.length) {
      // El pipeline decidio callar (handoff activo, fuera de lista blanca,
      // modo secretaria...). Es una salida legitima, no un fallo.
      await this.limpiar();
      return;
    }

    if (!this.env.MANYCHAT_API_TOKEN) {
      console.error('[lote] MANYCHAT_API_TOKEN ausente: el turno se proceso pero el lead no recibe nada.');
      await this.limpiar();
      return;
    }

    try {
      await enviarBurbujas(this.env.MANYCHAT_API_TOKEN, subId, burbujas);
      await this.limpiar();
    } catch (err) {
      const reintentos = ((await this.storage.get(CLAVE_REINTENTOS)) || 0) + 1;
      await this.storage.put(CLAVE_REINTENTOS, reintentos);
      const maxReintentos = enteroDeEnv(this.env, 'LOTE_MAX_REINTENTOS', MAX_REINTENTOS_ENVIO);

      if (reintentos >= maxReintentos) {
        // Ya se intento suficiente. Se abandona el lote para no dejar al objeto
        // reintentando para siempre, pero queda dicho en el log: el turno SI se
        // escribio en la base, lo que no salio fue el mensaje al lead.
        console.error(`[lote] ${subId}: ${reintentos} intentos fallidos de sendContent, se abandona. ${err?.message}`);
        await this.limpiar();
        return;
      }

      console.warn(`[lote] ${subId}: fallo el envio (intento ${reintentos}). Se reintenta. ${err?.message}`);
      // Relanzar hace que Cloudflare reintente la alarma con su propio backoff.
      throw err;
    }
  }

  async limpiar() {
    await this.storage.delete(CLAVE_MENSAJES);
    await this.storage.delete(CLAVE_PRIMERO_EN);
    await this.storage.delete(CLAVE_REINTENTOS);
    await this.storage.delete('payload_base');
    await this.storage.deleteAlarm();
  }
}
