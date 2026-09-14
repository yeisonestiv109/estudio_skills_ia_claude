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
 * falla despues, ManyChat ya recibio su OK y no vuelve a llamar. El reintento lo
 * pone la alarma, pero SOLO sobre el envio (ver `alarm`).
 *
 * ⚠️ DOS FASES, Y LA SEPARACION NO ES ESTETICA (incidente del 14-sep-2026).
 * La primera version reintentaba la alarma entera cuando fallaba el envio, y
 * Cloudflare la reejecutaba DESDE EL PRINCIPIO: cada reintento volvia a llamar
 * al LLM y a escribir el turno. Se vio en produccion con el lead Vasco_ana --
 * una apertura correcta y cinco reprocesos detras, con su gasto de tokens.
 *
 *   FASE 1 (pensar): se procesa el turno UNA vez. Al terminar, el resultado se
 *                    guarda en `resultado_pendiente` y las burbujas de entrada
 *                    se borran. El turno esta hecho y no se repite jamas.
 *   FASE 2 (hablar): se envia, reanudando en la burbuja que fallo. Los
 *                    reintentos solo repiten esta fase.
 *
 * ⚠️ LA VENTANA DE 24 HORAS MANDA SOBRE TODO ESTO. Meta no deja escribirle por
 * API a un lead que no interactua hace mas de 24 h (codigo 3011), y el
 * `message_tag` que servia para saltarsela esta deprecado. Cuando pasa, no hay
 * reintento posible: se avisa al Setter para que escriba a mano.
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
/**
 * Resultado de un turno YA procesado, esperando salir por la API.
 *
 * Su existencia es la frontera entre las dos fases: si esta clave tiene algo,
 * el pipeline ya corrio y un reintento SOLO puede reenviar. Es lo que impide
 * que un fallo de envio vuelva a gastar una llamada al LLM.
 */
export const CLAVE_RESULTADO = 'resultado_pendiente';

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
 * por burbuja hace imposible ese error, y ademas permite reanudar en la que
 * fallo en vez de reenviar el bloque entero y duplicarle mensajes al lead.
 *
 * ⚠️ SIN `message_tag`, Y NO ES UN OLVIDO (verificado el 14-sep-2026 contra la
 * API real). Meta deprecio los message tags y ManyChat responde
 * "Message tags are no longer supported for Facebook Messenger" a quien los
 * manda. La firma ya no acepta el parametro para que nadie lo reintroduzca: el
 * dia que alguien lo "arregle" añadiendolo, rompe TODOS los envios.
 */
export function cuerpoSendContent(subscriberId, texto) {
  return {
    subscriber_id: subscriberId,
    data: {
      version: 'v2',
      content: {
        messages: [{ type: 'text', text: texto }],
      },
    },
  };
}

/**
 * ¿Este fallo de envio se puede arreglar reintentando?
 *
 * LA DISTINCION QUE FALTABA Y COSTO EL INCIDENTE DEL 14-SEP. Reintentar un
 * error PERMANENTE es un bucle por construccion: la respuesta no va a cambiar,
 * y cada vuelta gasta otro turno de LLM. Es la misma ley que dejo el incidente
 * de concurrencia -- "un conflicto 40001 nunca se reintenta con los mismos
 * datos" -- aplicada al canal de salida.
 *
 * TRANSITORIO (vale la pena reintentar): 429 y 5xx, y los fallos de red.
 * PERMANENTE (no se reintenta nunca):
 *   · 3011 — VENTANA DE 24 HORAS. Meta no deja escribirle por API a quien no
 *     interactua hace mas de 24 h, y el `message_tag` que servia para eso esta
 *     deprecado. No hay reintento que lo arregle: hace falta un humano.
 *   · cualquier otro 4xx — payload o permisos: reintentar no cambia nada.
 */
export function esFalloPermanente(status, cuerpo = '') {
  if (status === 429) return false;
  if (status >= 500) return false;
  return status >= 400;
}

/** ¿El fallo es porque el lead lleva mas de 24 h sin escribir? */
export function esVentanaVencida(status, cuerpo = '') {
  const t = String(cuerpo || '');
  return status >= 400 && (/"code"\s*:\s*3011/.test(t) || /more than 24 hours ago/i.test(t));
}

export class FalloDeEnvio extends Error {
  constructor(mensaje, { status, cuerpo, indice, total }) {
    super(mensaje);
    this.name = 'FalloDeEnvio';
    this.status = status;
    this.cuerpo = cuerpo;
    this.indice = indice;           // cuantas salieron ANTES de la que fallo
    this.total = total;
    this.permanente = esFalloPermanente(status, cuerpo);
    this.ventanaVencida = esVentanaVencida(status, cuerpo);
  }
}

/**
 * Envia las burbujas EN ORDEN, una por una, REANUDANDO donde se quedo.
 *
 * Secuencial y no en paralelo: el orden del guion importa -- el link va de
 * ultimo -- y con `Promise.all` el orden de llegada no esta garantizado.
 *
 * `desde` es lo que evita duplicarle mensajes al lead en un reintento: si en el
 * intento anterior salieron dos de cuatro, se empieza por la tercera. Sin esto,
 * un fallo a mitad significaba que el lead recibia las dos primeras OTRA VEZ.
 *
 * Devuelve cuantas van enviadas EN TOTAL (no cuantas envio esta llamada).
 */
export async function enviarBurbujas(token, subscriberId, burbujas, fetchImpl = fetch, desde = 0) {
  let enviadas = desde;
  for (let i = desde; i < burbujas.length; i++) {
    const r = await fetchImpl('https://api.manychat.com/fb/sending/sendContent', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpoSendContent(subscriberId, burbujas[i])),
    });
    if (!r.ok) {
      const detalle = await r.text().catch(() => '');
      // ⚠️ EL CUERPO ENTERO EN EL LOG, NO UN RECORTE (14-sep-2026). La primera
      // version recortaba a 200 caracteres y el diagnostico del incidente se
      // fue en adivinar: el motivo real de ManyChat viaja dentro de
      // `details.messages[].message`, que es justo lo que el recorte se comia.
      // Un fallo de envio deja al lead sin respuesta: no puede costar dos
      // rondas de hipotesis averiguar por que.
      console.error(`[lote][envio] subscriber=${subscriberId} status=${r.status} burbuja=${i + 1}/${burbujas.length} respuesta=${detalle}`);
      throw new FalloDeEnvio(
        `sendContent ${r.status}: ${detalle.slice(0, 300)} (burbuja ${i + 1}/${burbujas.length})`,
        { status: r.status, cuerpo: detalle, indice: enviadas, total: burbujas.length },
      );
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
   * ⚠️ PROCESAR Y ENVIAR SON DOS FASES SEPARADAS. Esto es el arreglo del
   * incidente del 14-sep-2026 y es la razon de ser de `resultado_pendiente`.
   *
   * QUE PASO: la primera version dejaba las burbujas de ENTRADA en el storage
   * "para no perder el mensaje del lead" y relanzaba la excepcion cuando el
   * envio fallaba, contando con que Cloudflare reintentara la alarma. Y la
   * reintentaba... DESDE EL PRINCIPIO. Cada reintento volvia a llamar al LLM y
   * a escribir el turno en la base, cuando lo unico que habia fallado era el
   * ultimo paso. En produccion se vio con el lead Vasco_ana: una apertura
   * correcta a las 16:04:05 y cinco reprocesos detras
   * ("Repitio la palabra clave estando en M1_ENVIADO"), con su gasto de tokens.
   *
   * La idempotencia del Worker no lo atajo porque vive en `caches.default`, y
   * la Cache API no retiene entre invocaciones de una alarma de Durable Object.
   *
   * COMO SE ARREGLA: en cuanto el turno esta procesado, su resultado se guarda
   * en el storage DURABLE del objeto y las burbujas de entrada se borran. A
   * partir de ahi el turno esta hecho y no se vuelve a hacer: los reintentos
   * solo reenvian. El storage del Durable Object si es durable -- es el mismo
   * sitio donde ya viven las burbujas -- asi que no hace falta ni una columna
   * nueva en la base ni tocar las RPC.
   */
  async alarm() {
    // FASE 2 pendiente de un intento anterior: el turno YA se proceso y lo unico
    // que falta es que salga. Nunca se vuelve a pasar por el pipeline.
    const pendiente = await this.storage.get(CLAVE_RESULTADO);
    if (pendiente) return this.enviarPendiente(pendiente);

    const mensajes = (await this.storage.get(CLAVE_MENSAJES)) || [];
    if (!mensajes.length) return;

    const payloadBase = (await this.storage.get('payload_base')) || {};
    const texto = juntarBurbujas(mensajes);
    const subId = String(payloadBase.manychat_subscriber_id ?? '');

    if (!texto || !subId) {
      // Nada que procesar: el lote solo traia stickers o imagenes, que llegan
      // con `last_text` vacio. Se BORRA la entrada antes de limpiar -- si no,
      // `limpiar` la veria como un turno pendiente y reprogramaria la alarma
      // sobre un lote que nunca va a tener texto: una alarma cada 7 s, para
      // siempre.
      await this.storage.delete(CLAVE_MENSAJES);
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
      await this.storage.delete(CLAVE_MENSAJES);
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

    // ⚠️ AQUI ESTA LA FRONTERA ENTRE LAS DOS FASES.
    //
    // El turno ya se proceso: el LLM hablo y la base tiene el estado nuevo. Se
    // guarda el resultado y se BORRAN las burbujas de entrada, para que ningun
    // reintento pueda volver a procesarlo. A partir de esta linea, lo unico que
    // puede repetirse es el envio.
    const resultado = { subId, burbujas, enviadas: 0, estado: datos?.etapa ?? null };
    await this.storage.put(CLAVE_RESULTADO, resultado);
    await this.storage.delete(CLAVE_MENSAJES);
    await this.storage.delete(CLAVE_PRIMERO_EN);
    await this.storage.delete('payload_base');

    return this.enviarPendiente(resultado);
  }

  /**
   * FASE 2: sacar por la API las burbujas de un turno YA procesado.
   *
   * Se entra aca tanto desde `alarm()` recien procesado como desde un reintento
   * de la alarma. En los dos casos el pipeline ya corrio: esto no vuelve a
   * pensar, solo habla.
   */
  async enviarPendiente(resultado) {
    const { subId, burbujas } = resultado;
    const yaEnviadas = resultado.enviadas || 0;

    try {
      await enviarBurbujas(this.env.MANYCHAT_API_TOKEN, subId, burbujas, fetch, yaEnviadas);
      await this.limpiar();
      return;
    } catch (err) {
      // Lo que SI salio no se reenvia: sin esto, un fallo en la burbuja 3 hacia
      // que el lead recibiera la 1 y la 2 otra vez en cada reintento.
      const enviadas = Number.isInteger(err?.indice) ? err.indice : yaEnviadas;
      await this.storage.put(CLAVE_RESULTADO, { ...resultado, enviadas });

      // ⚠️ UN FALLO PERMANENTE NO SE REINTENTA. Es la misma ley que dejo el
      // incidente de concurrencia: si la respuesta no puede cambiar, reintentar
      // es un bucle por construccion. Aqui ademas cada vuelta costaba tokens.
      if (err?.permanente) {
        await this.rendirse(resultado, err, enviadas);
        return;
      }

      const reintentos = ((await this.storage.get(CLAVE_REINTENTOS)) || 0) + 1;
      await this.storage.put(CLAVE_REINTENTOS, reintentos);
      const maxReintentos = enteroDeEnv(this.env, 'LOTE_MAX_REINTENTOS', MAX_REINTENTOS_ENVIO);

      if (reintentos >= maxReintentos) {
        await this.rendirse(resultado, err, enviadas);
        return;
      }

      console.warn(`[lote] ${subId}: fallo transitorio del envio (intento ${reintentos}/${maxReintentos}), van ${enviadas}/${burbujas.length}. ${err?.message}`);
      // Relanzar hace que Cloudflare reintente la alarma con su propio backoff.
      // Ahora es seguro: el turno ya no se reprocesa, solo se reenvia el resto.
      throw err;
    }
  }

  /**
   * Se acabaron las opciones: el lead se queda sin respuesta.
   *
   * Nunca en silencio. El turno SI quedo escrito en la base, asi que el bot y
   * el lead estan desincronizados -- el bot cree que dijo algo que el lead no
   * recibio -- y eso solo lo puede arreglar una persona.
   *
   * El caso mas comun y el que no tiene vuelta atras es la VENTANA DE 24 H
   * (codigo 3011): Meta no deja escribirle por API a quien lleva mas de un dia
   * sin interactuar, y el `message_tag` que servia para eso esta deprecado. No
   * hay reintento, ni parametro, ni formato que lo resuelva.
   */
  async rendirse(resultado, err, enviadas) {
    const { subId, burbujas } = resultado;
    // El motivo que se le cuenta al humano sale de lo que DIJO ManyChat, no de
    // lo que supongamos nosotros. El 3011 se nombra aparte solo porque no tiene
    // arreglo tecnico posible; el resto va con la respuesta cruda.
    const motivo = err?.ventanaVencida
      ? 'ventana de 24 h vencida (codigo 3011): Meta no permite escribir por API y los message tags estan deprecados'
      : `HTTP ${err?.status ?? '?'} de ManyChat: ${String(err?.cuerpo ?? '').slice(0, 300) || 'sin cuerpo'}`;

    console.error(`[lote] ${subId}: ENVIO ABANDONADO (${motivo}). Salieron ${enviadas}/${burbujas.length} burbujas. El turno esta escrito en la base pero el lead no lo recibio. ${err?.message}`);

    try {
      const { notificarSetterGoogleChat } = await import('./notificador_google_chat.js');
      await notificarSetterGoogleChat(
        this.env,
        { nombre: `Lead ${subId}`, ig_handle: null, manychat_id: subId },
        { handoffRazon: 'error_tecnico' },
        `No se le pudo ENVIAR la respuesta (${motivo}). Salieron ${enviadas} de ${burbujas.length} burbujas. El turno quedo escrito en la base: el bot cree que respondio y el lead no lo recibio. Hay que escribirle a mano.`,
      );
    } catch (e) {
      console.error(`[lote] ${subId}: ademas fallo la alerta al Setter. ${e?.message}`);
    }

    await this.limpiar();
  }

  /**
   * Cierra el turno enviado y deja el objeto listo para el siguiente.
   *
   * ⚠️ NO BORRA LAS BURBUJAS QUE LLEGARON MIENTRAS TANTO. El lead escribe
   * mientras el bot le responde: es lo normal, no el caso raro. Si mientras
   * habia un envio pendiente entro una burbuja nueva, esa burbuja es el turno
   * SIGUIENTE -- borrarla seria tragarse un mensaje del lead sin dejar rastro.
   * Por eso, si queda entrada sin procesar, se reprograma la alarma en vez de
   * apagarla.
   */
  async limpiar() {
    await this.storage.delete(CLAVE_RESULTADO);
    await this.storage.delete(CLAVE_REINTENTOS);

    const pendientes = (await this.storage.get(CLAVE_MENSAJES)) || [];
    if (pendientes.length) {
      const ventanaMs = enteroDeEnv(this.env, 'LOTE_VENTANA_MS', VENTANA_MS_POR_DEFECTO);
      await this.storage.setAlarm(Date.now() + ventanaMs);
      return;
    }

    await this.storage.delete(CLAVE_PRIMERO_EN);
    await this.storage.delete('payload_base');
    await this.storage.deleteAlarm();
  }
}
