/**
 * Apps Script — Bridge entre Cloudflare Worker y CRM Google Sheet
 *
 * Recibe POST del Worker (después de cada turno del bot) y:
 *   1. Busca el lead por IG Handle o ManyChat ID en la pestaña "CRM"
 *   2. Si existe → actualiza campos NO manuales (no toca WhatsApp, Correo, Revenue, etc.)
 *   3. Si NO existe → inserta nueva fila al final
 *   4. Escribe un evento en la pestaña "Activity Log" para auditoría
 *
 * Despliegue:
 *   1. En el sheet → Extensiones → Apps Script
 *   2. Pegar este código en el editor
 *   3. Implementar → Nueva implementación → Tipo: Aplicación web
 *      - Ejecutar como: Yo (luisjavier.suarezmeza@gmail.com)
 *      - Quién tiene acceso: Cualquier persona
 *   4. Copiar la "URL de la aplicación web" → pegarla como Secret en Cloudflare:
 *      Nombre del Secret: APPS_SCRIPT_URL
 *      Valor: https://script.google.com/macros/s/AKfycb.../exec
 */

const SHEET_ID = '1iYLMAYV0XtN74ALBCmJkszUOpoINIt5tEs2CKGMvaf0';
const CRM_TAB = 'CRM';
const LOG_TAB = 'Activity Log';

// Formato de fecha+hora para todas las celdas de tipo fecha
// Coincide con el formato del CRM existente: yyyy-MM-dd HH:mm
const DATETIME_FORMAT = 'yyyy-MM-dd HH:mm';
const TIMEZONE = 'America/Bogota';

// Columnas del CRM (1-indexed para Apps Script)
const COL = {
  ID: 1,                      // A: #
  NOMBRE: 2,                  // B: Nombre
  IG_HANDLE: 3,               // C: IG Handle
  SETTER: 4,                  // D: Setter
  FUENTE: 5,                  // E: Fuente
  PROFESION: 6,               // F: Profesión
  SALARIO: 7,                 // G: Salario
  FECHA_CONTACTO: 8,          // H: Fecha Contacto
  FECHA_ATENDIDO: 9,          // I: Fecha Atendido
  ESTADO: 10,                 // J: Estado
  FECHA_AGENDAMIENTO: 11,     // K: Fecha Agendamiento
  FECHA_LLAMADA_PROG: 12,     // L: Fecha Llamada Programada
  WHATSAPP: 13,               // M: WhatsApp
  CORREO: 14,                 // N: Correo
  FECHA_LLAMADA_REAL: 15,     // O: Fecha Llamada Realizada
  FECHA_PAGO: 16,             // P: Fecha Pago
  REVENUE: 17,                // Q: Revenue COP
  UPFRONT: 18,                // R: Upfront Cash COP
  RECURRING: 19,              // S: Recurring Mensual
  NOTAS: 20,                  // T: Notas
  // Nuevas columnas que vas a agregar
  DOLOR: 21,                  // U: Dolor (A/B/C/D)
  URGENCIA: 22,               // V: Urgencia
  HANDOFF_RAZON: 23,          // W: Handoff Razón
  CALIFICA: 24,               // X: Califica (Sí/No)
  MANYCHAT_ID: 25             // Y: ManyChat ID
};


function doPost(e) {
  try {
    let data = JSON.parse(e.postData.contents);
    // Limpieza defensiva: por si algún {{cuf_XXX}} llega del Worker
    data = sanitizePayload(data);

    const ss = SpreadsheetApp.openById(SHEET_ID);
    const crm = ss.getSheetByName(CRM_TAB);
    const log = ss.getSheetByName(LOG_TAB);

    if (!crm) throw new Error('Pestaña CRM no encontrada');

    const now = new Date();
    const igHandle = normalizeHandle(data.ig_username);
    const manyChatId = String(data.manychat_subscriber_id || '');
    const estado = mapEstado(data);

    // Buscar lead existente
    const rowIdx = findLeadRow(crm, igHandle, manyChatId);

    if (rowIdx === -1) {
      insertNewLead(crm, data, now, igHandle, estado);
    } else {
      updateExistingLead(crm, rowIdx, data, now, estado);
    }

    // Activity log — siempre escribe (auditoría completa)
    if (log) {
      writeActivityLog(log, data, now);
    }

    return jsonResponse({
      ok: true,
      action: rowIdx === -1 ? 'inserted' : 'updated',
      row: rowIdx === -1 ? crm.getLastRow() : rowIdx,
      estado: estado
    });

  } catch (err) {
    return jsonResponse({ok: false, error: err.toString(), stack: err.stack}, 500);
  }
}


function doGet(e) {
  return jsonResponse({
    ok: true,
    service: 'Setter IA — CRM Bridge',
    info: 'Este endpoint solo acepta POST con JSON del Worker.',
    sheet: SHEET_ID
  });
}


function findLeadRow(crm, igHandle, manyChatId) {
  const lastRow = crm.getLastRow();
  if (lastRow < 2) return -1;

  // Lee toda la columna de IG Handle (col C) y la columna ManyChat ID (col Y) de una vez
  const numRows = lastRow - 1;
  const handles = crm.getRange(2, COL.IG_HANDLE, numRows, 1).getValues();
  let manyChatIds = [];
  try {
    manyChatIds = crm.getRange(2, COL.MANYCHAT_ID, numRows, 1).getValues();
  } catch (e) {
    // La columna Y puede no existir todavía si no la han creado
    manyChatIds = handles.map(() => ['']);
  }

  // Primero buscar por ManyChat ID (más confiable)
  if (manyChatId) {
    for (let i = 0; i < manyChatIds.length; i++) {
      if (String(manyChatIds[i][0] || '') === manyChatId) {
        return i + 2;
      }
    }
  }

  // Si no, buscar por IG Handle
  if (igHandle) {
    for (let i = 0; i < handles.length; i++) {
      if (normalizeHandle(handles[i][0]) === igHandle) {
        return i + 2;
      }
    }
  }

  return -1;
}


function insertNewLead(crm, data, now, igHandle, estado) {
  const lastRow = crm.getLastRow();
  const newRow = lastRow + 1;
  const id = newRow - 1;

  // Construye toda la fila en memoria y la escribe en una sola operación (más rápido)
  const row = new Array(25).fill('');

  row[COL.ID - 1] = id;
  // En el CRM usamos full_name (nombre + apellido) para facilitar revisión humana.
  // Fallback a first_name si por alguna razón no llega full_name.
  row[COL.NOMBRE - 1] = data.full_name || data.first_name || '';
  row[COL.IG_HANDLE - 1] = igHandle ? '@' + igHandle : '';
  row[COL.SETTER - 1] = 'Javit';
  row[COL.FUENTE - 1] = data.fuente || 'DM directo';
  row[COL.PROFESION - 1] = data.profesion || '';
  row[COL.SALARIO - 1] = formatSalario(data.ingreso_mensual_cop_M);
  row[COL.FECHA_CONTACTO - 1] = now;
  row[COL.FECHA_ATENDIDO - 1] = now;
  // Solo escribimos Estado si es un valor válido del dropdown.
  // Si es null, dejamos la celda vacía (el dropdown la rechazaría).
  if (estado) row[COL.ESTADO - 1] = estado;
  row[COL.NOTAS - 1] = data.summary || '';
  row[COL.DOLOR - 1] = data.dolor_opcion || '';
  row[COL.URGENCIA - 1] = data.urgencia || '';
  row[COL.HANDOFF_RAZON - 1] = data.handoff_razon || '';
  row[COL.CALIFICA - 1] = formatCalifica(data.califica);
  row[COL.MANYCHAT_ID - 1] = data.manychat_subscriber_id || '';

  if (data.etapa_actual === 'M5') {
    row[COL.FECHA_AGENDAMIENTO - 1] = now;
  }

  crm.getRange(newRow, 1, 1, row.length).setValues([row]);

  // Forzar formato datetime en todas las columnas de fecha de esta fila
  applyDatetimeFormat(crm, newRow);
}


function updateExistingLead(crm, rowIdx, data, now, estado) {
  // Solo actualiza los campos que el bot conoce. NO toca campos manuales:
  // WhatsApp (M), Correo (N), Fecha Llamada Realizada (O), Fecha Pago (P),
  // Revenue (Q), Upfront (R), Recurring (S).

  setDateCell(crm, rowIdx, COL.FECHA_ATENDIDO, now);
  // Solo actualizamos Estado si el valor mapeado es válido para el dropdown.
  // Si es null, dejamos el Estado actual sin cambios.
  if (estado) crm.getRange(rowIdx, COL.ESTADO).setValue(estado);

  if (data.profesion) crm.getRange(rowIdx, COL.PROFESION).setValue(data.profesion);
  if (data.ingreso_mensual_cop_M) {
    crm.getRange(rowIdx, COL.SALARIO).setValue(formatSalario(data.ingreso_mensual_cop_M));
  }
  if (data.summary) crm.getRange(rowIdx, COL.NOTAS).setValue(data.summary);
  if (data.dolor_opcion) crm.getRange(rowIdx, COL.DOLOR).setValue(data.dolor_opcion);
  if (data.urgencia) crm.getRange(rowIdx, COL.URGENCIA).setValue(data.urgencia);
  if (data.handoff_razon) crm.getRange(rowIdx, COL.HANDOFF_RAZON).setValue(data.handoff_razon);
  if (data.califica !== null && data.califica !== undefined) {
    crm.getRange(rowIdx, COL.CALIFICA).setValue(formatCalifica(data.califica));
  }
  if (data.manychat_subscriber_id) {
    crm.getRange(rowIdx, COL.MANYCHAT_ID).setValue(data.manychat_subscriber_id);
  }

  // Fecha Agendamiento — solo se setea la primera vez que la etapa llega a M5
  if (data.etapa_actual === 'M5') {
    const fechaAgendamientoActual = crm.getRange(rowIdx, COL.FECHA_AGENDAMIENTO).getValue();
    if (!fechaAgendamientoActual) {
      setDateCell(crm, rowIdx, COL.FECHA_AGENDAMIENTO, now);
    }
  }
}


/**
 * Escribe una fecha en una celda y le aplica el formato datetime.
 * Garantiza que la celda muestre fecha+hora aunque la columna estuviera
 * configurada solo para fecha.
 */
function setDateCell(sheet, row, col, dateValue) {
  const range = sheet.getRange(row, col);
  range.setValue(dateValue);
  range.setNumberFormat(DATETIME_FORMAT);
}


/**
 * Aplica formato datetime a todas las columnas de fecha de una fila.
 * Se llama después de insertar un lead nuevo (cuando setValues escribe
 * todas las columnas de una vez y queremos forzar el formato correcto).
 */
function applyDatetimeFormat(sheet, row) {
  const dateColumns = [
    COL.FECHA_CONTACTO,
    COL.FECHA_ATENDIDO,
    COL.FECHA_AGENDAMIENTO,
    COL.FECHA_LLAMADA_PROG,
    COL.FECHA_LLAMADA_REAL,
    COL.FECHA_PAGO
  ];
  dateColumns.forEach(col => {
    sheet.getRange(row, col).setNumberFormat(DATETIME_FORMAT);
  });
}


function writeActivityLog(log, data, now) {
  log.appendRow([
    now,                                            // A: Timestamp
    data.ig_username || '',                         // B: IG Handle
    data.first_name || '',                          // C: First Name
    data.evento || '',                              // D: Evento (M1_enviado, M3_dolor, handoff, etc.)
    data.etapa_actual || '',                        // E: Etapa actual
    data.etapa_anterior || '',                      // F: Etapa anterior
    data.profesion || '',                           // G: Profesión
    data.ingreso_mensual_cop_M || '',               // H: Ingreso (M COP)
    data.dolor_opcion || '',                        // I: Dolor
    data.urgencia || '',                            // J: Urgencia
    formatCalifica(data.califica),                  // K: Califica
    data.handoff_humano ? 'true' : 'false',         // L: Handoff
    data.handoff_razon || '',                       // M: Handoff Razón
    String(data.ultimo_mensaje_lead || '').slice(0, 500),  // N: Último msg del lead
    String(data.ultimo_mensaje_bot || '').slice(0, 500),   // O: Último msg del bot
    data.summary || ''                              // P: Summary
  ]);

  // Forzar formato datetime en la columna A (Timestamp) de la nueva fila
  const lastRow = log.getLastRow();
  log.getRange(lastRow, 1).setNumberFormat(DATETIME_FORMAT);
}


/**
 * Lista canónica de valores válidos del dropdown en columna J (Estado).
 * Esta lista se aplica al dropdown del sheet con la función `migrarYActualizarDropdown()`.
 *
 * IMPORTANTE: si agregas un nuevo valor aquí, también debes:
 *   1. Mapearlo desde alguna etapa en `mapEstado()` (más abajo)
 *   2. Correr `migrarYActualizarDropdown()` desde el editor de Apps Script para
 *      que el dropdown del sheet incluya el nuevo valor.
 */
const ESTADOS_VALIDOS = [
  // Estado inicial / sin atender
  'Lead Nuevo - Sin Atender',

  // Etapas del bot — más descriptivas que P1/P2/P3
  'M1 Enviado - Esperando P1',
  'P1 Respondida - Esperando M2',
  'M2 Enviado - Esperando dolor',
  'M2 D - Clarificación enviada',
  'M3 Enviado - Esperando urgencia',
  'M3 Enviado - Esperando respuesta',
  'M4 Enviado - Esperando agendar',
  'M4 Enviado - Esperando respuesta',
  'M4 Pitch + Objeción 5 manejada',
  'M4 Pitch personalizado',
  'M5 Enviado - Esperando Calendly',

  // Agendamiento confirmado
  'Aceptó llamada - Pendiente datos',
  'Agendada - Sin datos',
  'Agendada - Confirmada',
  'Agendada - Manual sábado 30 10:30 AM',

  // Descalificaciones
  'Descalificado - Ingresos bajos',
  'Descalificado - Sin urgencia',

  // Handoffs explícitos
  'Handoff - Agendamiento manual',
  'Handoff - Pregunta precio',
  'Handoff - Crisis emocional',
  'Handoff - Ex cliente',
  'Handoff - Otro',

  // Bumps de re-engagement
  'Ghosteo - Bump 1 enviado'
];


function mapEstado(data) {
  let estado = '';

  // Handoff tiene prioridad sobre etapa
  if (data.handoff_humano === true) {
    const razon = data.handoff_razon || '';
    if (razon === 'agendamiento_manual_pendiente') {
      estado = 'Handoff - Agendamiento manual';
    } else if (razon === 'pregunta_precio') {
      estado = 'Handoff - Pregunta precio';
    } else if (razon === 'crisis_emocional') {
      estado = 'Handoff - Crisis emocional';
    } else if (razon === 'lead_existente' || razon === 'ex_cliente') {
      estado = 'Handoff - Ex cliente';
    } else {
      estado = 'Handoff - Otro';
    }
  }
  // Descalificado
  else if (data.etapa_actual === 'Descalificado' || data.califica === false) {
    if (data.urgencia === 'algun_dia') {
      estado = 'Descalificado - Sin urgencia';
    } else {
      estado = 'Descalificado - Ingresos bajos';
    }
  }
  // Mapeo por etapa del bot → dropdown del CRM (versión descriptiva)
  else {
    const map = {
      'Inicial': 'Lead Nuevo - Sin Atender',
      'M1': 'M1 Enviado - Esperando P1',
      'M2': 'M2 Enviado - Esperando dolor',
      'M2.D': 'M2 D - Clarificación enviada',
      'M3': 'M3 Enviado - Esperando urgencia',
      // M3.B = sub-etapa de M3 después de Objeción 8 ("¿Cuál es el beneficio?").
      // El bot ya respondió con MSG_OBJ8 y devolvió la pregunta. Esperando que el lead
      // nombre SU beneficio personal. Lo mapeamos a "M3 Enviado - Esperando respuesta"
      // (que ya existe en ESTADOS_VALIDOS) para que el equipo entienda que aún no
      // calificó urgencia.
      'M3.B': 'M3 Enviado - Esperando respuesta',
      'M4': 'M4 Enviado - Esperando agendar',
      'M5': 'M5 Enviado - Esperando Calendly',
      'M5.B': 'Agendada - Confirmada',
      'M5.C': 'Agendada - Confirmada',
      'AgendaManual_1': 'Handoff - Agendamiento manual',
      'AgendaManual_2': 'Handoff - Agendamiento manual',
      'Descalificado': 'Descalificado - Ingresos bajos',
      // Cuando Javit está apagado (JAVIT_ACTIVO=false), el Worker registra el lead
      // en CRM con etapa=JavitOff. Lo mapeamos a "Lead Nuevo - Sin Atender" para
      // que aparezca en la cola del equipo para procesamiento manual.
      'JavitOff': 'Lead Nuevo - Sin Atender'
    };
    estado = map[data.etapa_actual] || '';
  }

  // Validación defensiva: si el estado no está en la lista válida, devuelve null
  // para que el caller NO intente escribirlo y rompa por validación.
  if (!estado || ESTADOS_VALIDOS.indexOf(estado) === -1) {
    return null;
  }
  return estado;
}


function normalizeHandle(h) {
  return String(h || '').replace(/^@/, '').toLowerCase().trim();
}


/**
 * Limpieza defensiva de payload por si llegan placeholders sin resolver de ManyChat
 * (ej. "{{cuf_14624253}}", "{{user_id}}", etc.).
 *
 * Recorre todos los campos string del payload y los limpia si son placeholders.
 * Esta es una red de seguridad — el Worker idealmente ya los sanitiza antes.
 */
function sanitizePayload(data) {
  if (!data || typeof data !== 'object') return data;
  const cleaned = {};
  for (const key in data) {
    cleaned[key] = sanitizeValue(data[key]);
  }
  return cleaned;
}


function sanitizeValue(value) {
  if (value === null || value === undefined) return value;
  if (typeof value !== 'string') return value;
  const str = value.trim();
  // Detecta placeholders sin resolver de ManyChat
  if (/^\{\{(cuf_|sys_|user_|sub_|first_name|last_name|ig_username|user_id|fullname)/i.test(str)) {
    return '';
  }
  if (/^\{\{.+\}\}$/.test(str)) {
    return '';
  }
  return str;
}


function formatSalario(ingresoM) {
  if (!ingresoM && ingresoM !== 0) return '';
  return '$' + ingresoM + 'M COP';
}


function formatCalifica(califica) {
  if (califica === true) return 'Sí';
  if (califica === false) return 'No';
  return '';
}


function jsonResponse(obj, status) {
  // Apps Script no permite cambiar status code, así que solo devuelve el JSON
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}


/**
 * MIGRACIÓN — ejecuta UNA SOLA VEZ desde el editor de Apps Script.
 *
 * Qué hace:
 *   1. Quita la validación de datos actual de la columna J (Estado).
 *   2. Recorre todas las filas existentes y reemplaza los valores viejos
 *      por la nomenclatura nueva descriptiva (ej. "M2 Enviado - Esperando P2"
 *      → "M2 Enviado - Esperando dolor").
 *   3. Aplica la nueva regla de validación con la lista actualizada
 *      (ESTADOS_VALIDOS) que incluye los valores descriptivos + handoffs.
 *
 * Cómo correrla:
 *   - En el editor de Apps Script → dropdown de funciones (arriba) → seleccionar
 *     `migrarYActualizarDropdown` → Ejecutar.
 *   - Revisa el Registro de ejecución: debe decir "Migración completa. X valores actualizados."
 *
 * Es idempotente: si la corres varias veces, no rompe nada (los valores ya
 * migrados no cambian).
 */
function migrarYActualizarDropdown() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const crm = ss.getSheetByName(CRM_TAB);
  if (!crm) throw new Error('Pestaña CRM no encontrada');

  const lastRow = crm.getLastRow();
  if (lastRow < 2) {
    Logger.log('No hay datos en el CRM para migrar.');
    return;
  }

  // Mapeo de valores viejos → nuevos (nomenclatura descriptiva)
  const migrationMap = {
    'M2 Enviado - Esperando P2': 'M2 Enviado - Esperando dolor',
    'M3 Enviado - Esperando P3': 'M3 Enviado - Esperando urgencia',
    'M4 Enviado - Esperando respuesta': 'M4 Enviado - Esperando agendar'
    // Nota: 'M3 Enviado - Esperando respuesta' se queda como está
    //       (puede ser una variante intencional para casos sin urgencia clara).
  };

  // Rango de Estado: J2 hasta la última fila
  const estadoRange = crm.getRange(2, COL.ESTADO, lastRow - 1, 1);

  // Paso 1: liberar la validación temporalmente para poder escribir cualquier valor
  estadoRange.clearDataValidations();

  // Paso 2: leer valores actuales, migrar, escribir de vuelta
  const valores = estadoRange.getValues();
  let migrados = 0;
  for (let i = 0; i < valores.length; i++) {
    const actual = String(valores[i][0] || '').trim();
    if (migrationMap[actual]) {
      valores[i][0] = migrationMap[actual];
      migrados++;
    }
  }
  estadoRange.setValues(valores);

  // Paso 3: aplicar la nueva regla de validación con la lista completa
  // setAllowInvalid(false) = rechaza valores que no estén en la lista
  // showCustomUi(true) = muestra el dropdown como menú visual
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(ESTADOS_VALIDOS, true)
    .setAllowInvalid(false)
    .setHelpText('Solo se permiten valores definidos en ESTADOS_VALIDOS del Apps Script.')
    .build();

  // Aplica la validación a TODA la columna J (incluidas las filas vacías futuras)
  // hasta una cantidad razonable (1000 filas).
  const fullColumnRange = crm.getRange(2, COL.ESTADO, 1000, 1);
  fullColumnRange.setDataValidation(rule);

  Logger.log('Migración completa. ' + migrados + ' valores actualizados.');
  Logger.log('Nuevo dropdown aplicado a J2:J1001 con ' + ESTADOS_VALIDOS.length + ' opciones.');
  return migrados;
}


/**
 * Test manual del script — corre esta función desde el editor de Apps Script
 * para verificar que escribe correctamente al CRM antes de conectar el Worker.
 */
function testInsertNewLead() {
  const payload = {
    ig_username: 'test_lead_javit',
    first_name: 'TestLead',
    manychat_subscriber_id: '999999999',
    evento: 'M1_enviado',
    etapa_actual: 'M1',
    etapa_anterior: 'Inicial',
    profesion: 'Ingeniero',
    ingreso_mensual_cop_M: 8,
    dolor_opcion: null,
    urgencia: null,
    califica: null,
    handoff_humano: false,
    handoff_razon: null,
    ultimo_mensaje_lead: 'CONTROL',
    ultimo_mensaje_bot: 'Hola TestLead, qué bueno que estés acá...',
    summary: 'Lead nuevo, ingeniero, primer mensaje recibido',
    fuente: 'DM directo'
  };

  const fakeEvent = { postData: { contents: JSON.stringify(payload) } };
  const result = doPost(fakeEvent);
  Logger.log(result.getContent());
}


function testUpdateLead() {
  const payload = {
    ig_username: 'test_lead_javit',
    first_name: 'TestLead',
    manychat_subscriber_id: '999999999',
    evento: 'M3_dolor_identificado',
    etapa_actual: 'M3',
    etapa_anterior: 'M2',
    profesion: 'Ingeniero',
    ingreso_mensual_cop_M: 8,
    dolor_opcion: 'B',
    urgencia: null,
    califica: true,
    handoff_humano: false,
    handoff_razon: null,
    ultimo_mensaje_lead: 'B',
    ultimo_mensaje_bot: 'Te entiendo. Es la trampa del ingreso medio-alto...',
    summary: 'Lead califica (8M COP), dolor B (no sabe en qué se va)',
    fuente: 'DM directo'
  };

  const fakeEvent = { postData: { contents: JSON.stringify(payload) } };
  const result = doPost(fakeEvent);
  Logger.log(result.getContent());
}
