/**
 * Notificador de Handoff → Google Chat (Webhook)
 * ============================================================================
 * Modulo AISLADO a proposito. No importa NADA del Worker ni del Router: recibe
 * el `estado` del lead y el `plan` del turno, y arma el mensaje. Asi se puede
 * tocar, desplegar o desactivar sin riesgo de cruzarse con el bot, y otra
 * persona puede trabajarlo en paralelo.
 *
 * REGLAS DE DISEÑO:
 *  1. Sin `GOOGLE_CHAT_WEBHOOK` -> no hace nada. Seguro en tests y local.
 *  2. NUNCA lanza. Un fallo de notificacion jamas puede romper la respuesta.
 *  3. Se llama con `ctx.waitUntil()`: no bloquea la respuesta a ManyChat.
 *  4. LOGUEA TAMBIEN CUANDO ACIERTA. La primera version solo logueaba errores,
 *     y cuando el equipo reporto "no me llego nada" fue imposible distinguir
 *     "se envio bien" de "el codigo no estaba desplegado". El silencio no es
 *     un diagnostico.
 */

/** Las razones tecnicas no le dicen nada a un Setter. Se traducen. */
const RAZON_LEGIBLE = {
  crisis_emocional: 'Señales de crisis emocional',
  contenido_hostil: 'El lead se puso hostil',
  ex_cliente: 'Dice que ya fue cliente del programa',
  ambiguo: 'El bot no logro entender su respuesta',
  objecion_fuera_playbook: 'Objecion que no esta en el playbook',
  objecion_no_habilitada: 'Objecion que el bot todavia no contesta',
  pregunta_precio: 'Insiste en saber el precio del programa',
  resistencia_repetida: 'Repite la misma objecion',
  resistencia_acumulada: 'Acumulo varias objeciones seguidas',
  agendamiento_manual_pendiente: 'No encuentra horarios: hay que agendarlo a mano',
  error_tecnico: 'Fallo tecnico del bot',
};

/** Dolores del SOP: la letra sola no le sirve al Setter. */
const DOLOR_LEGIBLE = {
  A: 'A) No le alcanza, siempre en cero a fin de mes',
  B: 'B) No sabe en que se le va',
  C: 'C) Siente que deberia estar mejor con lo que gana',
  D: 'D) Otra',
};

const URGENCIA_LEGIBLE = {
  ahora: 'Quiere resolverlo YA',
  algun_dia: 'Lo deja para “algun dia”',
  pregunta_por_que: 'Pregunta por que deberia resolverlo ahora',
};

/** Las que exigen a una persona con cuidado, no una venta. */
const RAZONES_DELICADAS = new Set(['crisis_emocional', 'contenido_hostil']);

const money = (n) => `$${Number(n).toLocaleString('es-CO')} COP`;

/** Los 3 filtros, como los leeria un Setter de un vistazo. */
function bloqueFiltros(estado) {
  const lineas = [];

  if (estado?.salario_monto) {
    // ⚠️ Distinguir la cifra ASUMIDA de la que el lead dijo. Si el lead solo
    // confirmo el rango, `ingreso_confirmado` es false y el Setter NO puede
    // citarle ese numero como si se lo hubiera dado.
    const marca = estado.ingreso_confirmado === false ? ' _(asumido del rango, NO lo dijo)_' : '';
    lineas.push(`💰 *Ingreso:* ${money(estado.salario_monto)}${marca}`);
  } else {
    lineas.push('💰 *Ingreso:* — sin dato');
  }

  if (estado?.endeudamiento_pct != null) {
    const pct = Number(estado.endeudamiento_pct);
    const rem = estado?.salario_monto ? Math.round(estado.salario_monto * (1 - pct / 100)) : null;
    lineas.push(`📉 *Endeudamiento:* ${pct}%${rem !== null ? ` → le quedan ${money(rem)}` : ''}`);
  } else {
    lineas.push('📉 *Endeudamiento:* — sin dato');
  }

  if (estado?.dolor) {
    const letras = String(estado.dolor).split('|')[0].split(',').map((x) => x.trim());
    lineas.push(`🔥 *Dolor:* ${letras.map((l) => DOLOR_LEGIBLE[l] || l).join(' · ')}`);
  } else {
    lineas.push('🔥 *Dolor:* — sin dato');
  }

  lineas.push(`⏰ *Urgencia:* ${estado?.urgencia ? (URGENCIA_LEGIBLE[estado.urgencia] || estado.urgencia) : '— sin dato'}`);
  return lineas;
}

/**
 * Arma el texto de la alerta. Exportada aparte para poder testearla sin red.
 */
export function construirMensajeHandoff(estado, plan, ultimoMensajeLead = '') {
  const razon = plan?.handoffRazon || 'desconocida';
  const delicada = RAZONES_DELICADAS.has(razon);
  const nombre = (estado?.nombre || 'Lead sin nombre').replace(/^\[PRUEBA\]\s*/i, '').trim() || 'Lead sin nombre';
  const esPrueba = /^\[PRUEBA\]/i.test(String(estado?.nombre || ''));

  const cabecera = delicada
    ? '🛑 *ATENCION — HANDOFF DELICADO* 🛑'
    : '🚨 *NUEVO LEAD PARA SETTER* 🚨';

  const lineas = [cabecera];
  if (esPrueba) lineas.push('_(lead de PRUEBA — no es real)_');
  lineas.push('');
  lineas.push(`👤 *Lead:* ${nombre}`);
  if (estado?.profesion) lineas.push(`💼 *Profesion:* ${estado.profesion}`);
  // Se muestran las DOS: la traduccion para el Setter y el codigo tecnico para
  // poder cruzarlo con el activity_log y los tags de ManyChat.
  const legible = RAZON_LEGIBLE[razon];
  lineas.push(`⚠️ *Motivo:* ${legible ? `${legible} \`${razon}\`` : razon}`);

  if (razon === 'crisis_emocional') {
    lineas.push('❗ *NO le vendas.* Atiende a la persona primero.');
  }

  lineas.push('');
  lineas.push(...bloqueFiltros(estado));
  lineas.push(`✅ *¿Califico?:* ${estado?.califica === true ? 'SI, paso los 3 filtros' : estado?.califica === false ? 'No' : 'Todavia no'}`);
  lineas.push(`📍 *Se quedo en:* ${estado?.etapa_bot || plan?.etapaNueva || 'inicio'}`);

  if (ultimoMensajeLead) {
    lineas.push('');
    lineas.push(`💬 *Ultimo mensaje del lead:* “${String(ultimoMensajeLead).slice(0, 300)}”`);
  }

  lineas.push('');
  lineas.push(estado?.ig_handle
    ? `🔗 *Ir al chat:* https://instagram.com/${estado.ig_handle}`
    : '🔗 *Ir al chat:* ⚠️ sin usuario de IG registrado — buscalo por nombre en el Inbox');

  return lineas.join('\n');
}

/**
 * Envia la alerta. Fire-and-forget: se llama desde `ctx.waitUntil()`.
 *
 * @param {Object} env    - necesita `GOOGLE_CHAT_WEBHOOK`
 * @param {Object} estado - snapshot del lead (`leerEstado()`)
 * @param {Object} plan   - plan del turno (`decidirTurno()`)
 * @param {string} ultimoMensajeLead
 * @param {Function} fetchImpl - inyectable para poder testear sin red
 * @returns {Promise<{enviado: boolean, razon?: string}>}
 */
export async function notificarSetterGoogleChat(env, estado, plan, ultimoMensajeLead = '', fetchImpl = fetch) {
  const url = env?.GOOGLE_CHAT_WEBHOOK;
  if (!url || !String(url).trim()) {
    console.log('[gchat] sin GOOGLE_CHAT_WEBHOOK configurado: no se notifica.');
    return { enviado: false, razon: 'sin_webhook' };
  }
  if (!plan?.handoffRazon) return { enviado: false, razon: 'no_es_handoff' };

  try {
    const texto = construirMensajeHandoff(estado, plan, ultimoMensajeLead);
    const resp = await fetchImpl(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=UTF-8' },
      body: JSON.stringify({ text: texto }),
    });
    if (!resp.ok) {
      const cuerpo = await resp.text().catch(() => '');
      console.error(`[gchat] FALLO HTTP ${resp.status}: ${cuerpo.slice(0, 300)}`);
      return { enviado: false, razon: `http_${resp.status}` };
    }
    // El log de EXITO es lo que faltaba: sin el, "no me llego nada" no se puede
    // diagnosticar desde los logs del Worker.
    console.log(`[gchat] alerta enviada OK (${plan.handoffRazon})`);
    return { enviado: true };
  } catch (err) {
    console.error('[gchat] ERROR:', err?.message || err);
    return { enviado: false, razon: 'excepcion' };
  }
}
