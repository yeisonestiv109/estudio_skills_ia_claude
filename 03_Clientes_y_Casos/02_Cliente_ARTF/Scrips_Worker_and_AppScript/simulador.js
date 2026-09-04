/**
 * SIMULADOR DE CONVERSACIONES
 * ============================================================================
 * Reproduce una conversación completa contra el router, turno por turno, sin
 * red y sin base de datos. En cada turno corre el verificador de cumplimiento.
 *
 * Para qué sirve, en términos del loop: hace la verificación **rápida y
 * visual**. Una corrida dice si el bot recorre bien un camino completo, en vez
 * de tener que leer cada plantilla a mano. Es lo que la guía llama aprovechar
 * la "GPU de visión": verde o rojo de un vistazo.
 *
 * POR QUE NO USA EL LLM: los tests tienen que ser deterministas y hermeticos.
 * El simulador usa los MISMOS detectores deterministas que el Worker corre
 * antes de llamar al modelo. Donde el Worker sí necesitaría al LLM (extraer una
 * profesion de texto libre, clasificar una objecion), la conversacion del
 * corpus trae una `pista` con lo que el modelo habria devuelto. Asi se prueba
 * TODO el ruteo sin depender de que un modelo externo se porte igual dos veces.
 */

import {
  decidirTurno, decidirSiResponder,
  parseIngresoCOP, detectarEndeudamientoPct, detectarDolorLetras, detectarSiNo,
  detectarUrgencia, detectarAceptacion, detectarConfirmacionAgenda,
  detectarAcompanante, detectarHostilidad, detectarAgradecimiento,
  detectarSinHorarios,
} from './bot_router_v42.js';
import { verificarMensajes } from './verificador_cumplimiento.js';

/**
 * Los mismos deterministas que corre el Worker antes del LLM.
 * Si esto resuelve el turno, el Worker tampoco habria llamado al modelo.
 */
export function clasificarDeterminista(etapa, texto) {
  const c = { hostil: detectarHostilidad(texto) };
  if (!etapa || c.hostil) return c;

  if (['M1_ENVIADO', 'M1_INGRESO_AMBIGUO', 'M1_ACLARAR_REMANENTE', 'DESCALIFICADO',
       'RETORNO_PREGUNTA'].includes(etapa)) {
    const ing = parseIngresoCOP(texto);
    if (!ing.ambiguo) { c.ingreso_cop = ing.monto; c.ingreso_glosario = ing.glosario; }
    else if (ing.glosario) { c.ingreso_glosario = ing.glosario; c.ingreso_cop = null; }
  }
  if (etapa === 'M2_ENVIADO' || etapa === 'M2_NO_SABE') {
    const pct = detectarEndeudamientoPct(texto);
    if (pct !== null) c.endeudamiento_pct = pct;
  }
  if (etapa === 'M3_ENVIADO') {
    const letras = detectarDolorLetras(texto);
    if (letras.length) {
      c.dolores = letras;
      c.dolor_financiero = !letras.every((l) => l === 'D');
    }
  }
  if (etapa === 'M1_RANGO_PREGUNTADO') {
    const r = detectarSiNo(texto);
    if (r !== null) c.confirma_rango = r;
    const ing = parseIngresoCOP(texto);
    if (!ing.ambiguo) c.ingreso_cop = ing.monto;
  }
  if (etapa === 'M4_ENVIADO') {
    const u = detectarUrgencia(texto);
    if (u) c.urgencia = u;
  }
  if (etapa === 'M5_ENVIADO' && detectarAceptacion(texto)) c.acepta = true;
  if (etapa === 'M7_ESPERANDO_VINCULO' && detectarSinHorarios(texto)) c.sin_horarios = true;
  if (etapa === 'M6_ENVIADO' || etapa === 'M7_ENVIADO') {
    if (detectarConfirmacionAgenda(texto)) c.confirmo_agendo = true;
    if (detectarSinHorarios(texto)) c.sin_horarios = true;
    const acomp = detectarAcompanante(texto);
    if (acomp !== null) c.acompanado = acomp;
  }
  if (etapa === 'CIERRE_PRECALL' && detectarAgradecimiento(texto)) c.agradece = true;
  if (etapa === 'BLINDAJE_ENVIADO') {
    const comp = detectarCompromiso(texto);
    if (comp) c.compromiso = comp;
  }
  return c;
}

/**
 * Estado en memoria: imita lo que `fn_bot_procesar_turno` deja en la base,
 * incluida la regla de que sin señal explicita el estado se queda donde esta.
 */
function aplicarPlan(estado, plan) {
  const nuevo = { ...estado };
  if (plan.etapaNueva) nuevo.etapa_bot = plan.etapaNueva;
  if (plan.estadoDestino) nuevo.estado_codigo = plan.estadoDestino;
  if (plan.handoffRazon) nuevo.handoff_razon = plan.handoffRazon;

  const c = plan.campos || {};
  if (c.salario_monto != null) nuevo.salario_monto = c.salario_monto;
  if (c.profesion != null) nuevo.profesion = c.profesion;
  if (c.ingreso_confirmado != null) nuevo.ingreso_confirmado = c.ingreso_confirmado;
  if (c.endeudamiento_pct != null) nuevo.endeudamiento_pct = c.endeudamiento_pct;
  if (c.dolor != null) nuevo.dolor = c.dolor;
  if (c.urgencia_raw != null) nuevo.urgencia = c.urgencia_raw;
  if (c.asiste_acompanado != null) nuevo.asiste_acompanado = c.asiste_acompanado;
  if (c.califica != null) nuevo.califica = c.califica;
  if (c.ultima_objecion_codigo != null) nuevo.ultima_objecion_codigo = c.ultima_objecion_codigo;
  if (c.objeciones_consecutivas != null) nuevo.objeciones_consecutivas = c.objeciones_consecutivas;
  if (c.calendario_enviado) nuevo.calendario_enviado_at = new Date().toISOString();
  return nuevo;
}

/**
 * Corre una conversación completa.
 *
 * @param {object} conversacion  fixture del corpus
 * @returns {{ok: boolean, pasos: Array, errores: Array<string>}}
 */
export function simular(conversacion) {
  let estado = null;
  const pasos = [];
  const errores = [];

  conversacion.turnos.forEach((turno, i) => {
    const n = i + 1;

    // `base` simula algo que cambio en la base de datos ENTRE turnos, sin que
    // el bot lo hiciera. El caso real: el Setter vincula la reunion desde el
    // dashboard. Es lo unico que le permite al bot dar el cierre por hecho.
    if (turno.base && estado) Object.assign(estado, turno.base);

    const puerta = decidirSiResponder(estado);

    if (!puerta.responder) {
      pasos.push({ turno: n, lead: turno.lead, mudo: true, razon: puerta.razon, mensajes: [] });
      if (turno.espera && turno.espera.contiene) {
        errores.push(`Turno ${n}: se esperaba respuesta pero el bot quedo mudo (${puerta.razon}).`);
      }
      return;
    }

    // Deterministas primero; la `pista` cubre lo que resolveria el LLM.
    const clasificacion = {
      // El nombre viaja aca porque en el primer turno `estado` es null (el lead
      // todavia no existe en la base). Es exactamente lo que hace el Worker.
      nombre: conversacion.lead?.nombre || '',
      ...clasificarDeterminista(estado?.etapa_bot ?? null, turno.lead),
      ...(turno.pista || {}),
    };

    const plan = decidirTurno(estado, clasificacion, turno.lead);

    // LA COMPUERTA, en CADA turno. Es lo que hace util al simulador: no basta
    // con que el bot llegue al final, tiene que no romper el playbook en el camino.
    const chequeo = verificarMensajes(plan.mensajes, { nombre: conversacion.lead?.nombre || '' });
    if (!chequeo.pasa) {
      for (const f of chequeo.fallas) errores.push(`Turno ${n} [${f.regla}] ${f.detalle}`);
    }

    estado = aplicarPlan(estado || { nombre: conversacion.lead?.nombre || '', objeciones_consecutivas: 0 }, plan);

    // Expectativas declaradas en el fixture
    const e = turno.espera || {};
    if (e.etapa && estado.etapa_bot !== e.etapa) {
      errores.push(`Turno ${n}: etapa esperada "${e.etapa}", quedo "${estado.etapa_bot}".`);
    }
    if (e.estado && estado.estado_codigo !== e.estado) {
      errores.push(`Turno ${n}: estado esperado "${e.estado}", quedo "${estado.estado_codigo}".`);
    }
    if (e.handoff !== undefined) {
      const hubo = plan.handoffRazon || null;
      if (hubo !== e.handoff) errores.push(`Turno ${n}: handoff esperado "${e.handoff}", fue "${hubo}".`);
    }
    if (e.contiene) {
      const todos = plan.mensajes.join('\n');
      for (const frag of [].concat(e.contiene)) {
        if (!todos.includes(frag)) {
          errores.push(`Turno ${n}: la respuesta no contiene "${frag}". Envio: "${todos.slice(0, 120)}..."`);
        }
      }
    }
    // `no_contiene` afirma AUSENCIA. Hace falta para probar cosas como "aqui
    // NO puede aparecer el link del calendario", que es un requisito de negocio
    // tan real como los de presencia.
    if (e.no_contiene) {
      const todos = plan.mensajes.join('\n');
      for (const frag of [].concat(e.no_contiene)) {
        if (todos.includes(frag)) {
          errores.push(`Turno ${n}: la respuesta NO deberia contener "${frag}", pero lo contiene.`);
        }
      }
    }
    if (e.burbujas !== undefined && plan.mensajes.length !== e.burbujas) {
      errores.push(`Turno ${n}: se esperaban ${e.burbujas} burbujas, fueron ${plan.mensajes.length}.`);
    }

    pasos.push({ turno: n, lead: turno.lead, mensajes: plan.mensajes, etapa: estado.etapa_bot, estado: estado.estado_codigo, handoff: plan.handoffRazon });
  });

  return { ok: errores.length === 0, pasos, errores, estadoFinal: estado };
}

/** Render legible de una corrida, para leer una conversacion de un vistazo. */
export function imprimir(conversacion, resultado) {
  const out = [`\n=== ${conversacion.nombre} ===`];
  for (const p of resultado.pasos) {
    out.push(`\n[${p.turno}] LEAD: ${p.lead}`);
    if (p.mudo) { out.push(`     (bot en silencio: ${p.razon})`); continue; }
    p.mensajes.forEach((m, i) => out.push(`     BOT ${i + 1}: ${m.replace(/\n/g, '\n            ')}`));
    out.push(`     -> etapa=${p.etapa} estado=${p.estado}${p.handoff ? ` handoff=${p.handoff}` : ''}`);
  }
  out.push(resultado.ok ? '\nRESULTADO: OK' : `\nRESULTADO: ${resultado.errores.length} error(es)\n  ` + resultado.errores.join('\n  '));
  return out.join('\n');
}
