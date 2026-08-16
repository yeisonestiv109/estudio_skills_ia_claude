/**
 * ============================================================================
 *  Daily Metrics Scorecard — Resuelve Tus Finanzas
 *  Reconstruye la pestaña de scorecard diario a partir de la pestaña "CRM".
 *
 *  Qué hace:
 *   - Genera bandas de MES y de SEMANA (Lun→Dom, recortadas al mes).
 *   - Encabezados de día con día de semana (ej. "Mié 1").
 *   - Totales de semana (verde) y totales de mes (azul) + TOTAL general.
 *   - Columna "% Conv" con la conversión de cada paso del funnel.
 *   - Sello de "Última actualización".
 *   - Las CIFRAS son fórmulas VIVAS que leen del CRM: se actualizan solas.
 *
 *  Instalación: Extensiones → Apps Script → pega este archivo → guarda →
 *  ejecuta la función  construirScorecard().  (Autoriza permisos la 1a vez.)
 *  Después aparece el menú "⚙️ Scorecard" al abrir el archivo.
 * ============================================================================
 */

// ------------------------------- CONFIG ------------------------------------
var CFG = {
  CRM_SHEET:    'CRM',                 // pestaña fuente
  OUT_SHEET:    'Daily Metrics v2',    // pestaña destino (se recrea cada corrida)
  START:        new Date(2026, 4, 18), // inicio del periodo (18-may-2026, lunes)
  END:          null,                  // null = fin del MES SIGUIENTE (auto-extiende; muestra A/R por vencer)
  TZ:           'America/Bogota',
  UMBRAL_OFERTA: 2000000               // "< $2.000.000" para Oferta de Valientes
};

// Métricas en orden de fila. Mapeo real leído del sheet actual.
//  type 'count' -> COUNTIFS ; type 'sum' -> SUMIFS ; type 'diff' -> resta filas
//  ltVal -> "< valor" (col ltCol) ; gteVal -> ">= valor" (col gteCol) ; gtVal -> "> valor" (col gtCol)
//  diff  -> minuend/subtrahend son 'key' de otras métricas (resta por columna)
var METRICS = [
  // === FUNNEL (conteos) ====================================================
  { key: 'leads',    label: 'Leads',                     section: 'funnel', type: 'count', col: 'H' },
  { key: 'conv',     label: 'Conversaciones',            section: 'funnel', type: 'count', col: 'I' },
  { key: 'book',     label: 'Bookings',                  section: 'funnel', type: 'count', col: 'K' },
  { key: 'dayqb',    label: 'Day QBookings',             section: 'funnel', type: 'count', col: 'L' },
  { key: 'qbsu',     label: 'Quality Bookings Show Ups', section: 'funnel', type: 'count', col: 'O' },
  { key: 'sales',    label: 'Sales',                     section: 'funnel', type: 'diff',  minuend: 'salesg', subtrahend: 'desist' },  // netas
  { key: 'ofvn',     label: 'Oferta de Valientes',       section: 'funnel', type: 'count', col: 'P', ltCol: 'Q', ltVal: CFG.UMBRAL_OFERTA, gtCol: 'R', gtVal: 0 },  // solo activas
  { key: 'estud',    label: 'Estudiantes activos',       section: 'funnel', type: 'diff',  minuend: 'sales', subtrahend: 'ofvn' },
  // === BASE / DESISTIDOS (conteos) =========================================
  //  Sales (arriba) = Sales bruto - Desistieron ; Oferta de Valientes (arriba) = solo activas (Q<umbral y R>0).
  { key: 'salesg',   label: 'Sales bruto',               section: 'base',   type: 'count', col: 'P' },
  { key: 'ofvg',     label: 'OFV bruto (reservas)',      section: 'base',   type: 'count', col: 'P', ltCol: 'Q', ltVal: CFG.UMBRAL_OFERTA },
  { key: 'desist',   label: 'Desistieron',               section: 'base',   type: 'diff',  minuend: 'ofvg', subtrahend: 'ofvn' },
  // === REVENUE (dinero) ====================================================
  { key: 'rev',      label: 'Revenue',                   section: 'revenue', type: 'sum',   valCol: 'R', dateCol: 'P', money: true },
  { key: 'revofv',   label: 'Revenue OFV',               section: 'revenue', type: 'sum',   valCol: 'R', dateCol: 'P', money: true, ltCol: 'Q', ltVal: CFG.UMBRAL_OFERTA },
  { key: 'revreal',  label: 'Revenue Real',              section: 'revenue', type: 'diff',  minuend: 'rev', subtrahend: 'revofv', money: true, emphasize: true },
  // === CASH (dinero) =======================================================
  { key: 'cash',     label: 'Upfront Cash',              section: 'cash', type: 'sum',   valCol: 'Q', dateCol: 'P', money: true },
  { key: 'cashofv',  label: 'Dinero de OFV (Reservar)',  section: 'cash', type: 'sum',   valCol: 'Q', dateCol: 'P', money: true, ltCol: 'Q', ltVal: CFG.UMBRAL_OFERTA },
  { key: 'cashreal', label: 'Upfront Cash Real',         section: 'cash', type: 'diff',  minuend: 'cash', subtrahend: 'cashofv', money: true, emphasize: true },
  // Cuotas Cobradas = cuota REAL cobrada (Monto AD) por su Fecha siguiente pago (AC), marcada como "Realizado" en AE (estado del pago).
  { key: 'feccpp',   label: 'Cuotas Cobradas',            section: 'cash', type: 'sum',   valCol: 'AD', dateCol: 'AC', money: true, eqCol: 'AE', eqVal: 'Realizado' },
  // Cuotas Proy. A/R = A/R PENDIENTE = cuota proyectada (Monto AD) por Fecha siguiente pago (AC) que AÚN NO está "Realizado".
  //   Se calcula como (total de cuotas por AC) - (las Realizadas): así incluye AE en blanco y "No realizado".
  { key: 'arproy',   label: 'Cuotas Proy. A/R (2º pago)', section: 'cash', type: 'sum',   valCol: 'AD', dateCol: 'AC', money: true, subEqCol: 'AE', subEqVal: 'Realizado' },
  { key: 'dinerodesist', label: 'Dinero Desistido (Reservar)', section: 'cash', type: 'diff', minuend: 'cashofv', subtrahend: 'reservaact', money: true },
  { key: 'reservaact',   label: 'Reserva Activa (Reservar)',   section: 'cash', type: 'sum', valCol: 'Q', dateCol: 'P', money: true, ltCol: 'Q', ltVal: CFG.UMBRAL_OFERTA, gtCol: 'R', gtVal: 0 }
];

// Índice de fila por 'key' (para las métricas tipo diff).
var METRIC_IDX = {};
METRICS.forEach(function (m, i) { if (m.key) METRIC_IDX[m.key] = i; });

// % Conv: fila -> fila anterior del funnel (índices en METRICS). Solo estos 5.
var FUNNEL_PREV = { 1: 0, 2: 1, 3: 2, 4: 3, 5: 4 };

// Paleta (inspirada en el formato de referencia)
var C = {
  NAVY:      '#1c2e4a', NAVY2: '#33475b',
  GREEN_H:   '#4c8c46', GREEN_C: '#e2efda',
  BLUE_H:    '#3c78d8', BLUE_C:  '#c9daf8',
  TOTAL_H:   '#0b1a33', TOTAL_C: '#a4c2f4',
  WHITE:     '#ffffff', GREY_C:  '#f1f3f4',
  LABEL_C:   '#f8f9fa',
  MONEY_C:   '#f6f1e7',   // fondo sutil sección de dinero
  REAL_C:    '#ecdfc2'    // más notorio: filas de $ reales
};

// Colores por sección: data = celdas de datos; label = columna A (más fuerte);
// emph = filas "reales"; total = celdas de los totales semana/mes/TOTAL (tono más fuerte de la sección).
var SEC = {
  funnel:  { data: '#eef3fb', label: '#d7e3f6', emph: '#c7d8f2', total: '#b8cdf0' },   // azul   (conteos funnel)
  base:    { data: '#f1f1f1', label: '#e0e0e0', emph: '#d4d4d4', total: '#d0d0d0' },   // gris   (bruto / desistidos)
  revenue: { data: '#eaf4ee', label: '#d3ecdb', emph: '#bfe1cb', total: '#a9dabb' },   // verde  (revenue)
  cash:    { data: '#f7f1e6', label: '#efe4c8', emph: '#e6d3a8', total: '#e6d09a' }    // dorado (cash)
};

var MESES = ['enero','febrero','marzo','abril','mayo','junio','julio',
             'agosto','septiembre','octubre','noviembre','diciembre'];
var DIAS  = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'];

var HDR = { MONTH: 3, WEEK: 4, DAY: 5 };  // filas de encabezado
var DATA0 = 6;                            // primera fila de datos

// --------------------------- MENÚ / TRIGGERS -------------------------------
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('⚙️ Scorecard')
    .addItem('Reconstruir Daily Metrics', 'construirScorecard')
    .addItem('Instalar refresco diario (sello)', 'instalarTriggerDiario')
    .addToUi();
}

function instalarTriggerDiario() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'refrescarSello') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('refrescarSello').timeBased().everyDays(1).atHour(7).create();
  SpreadsheetApp.getActive().toast('Refresco diario instalado (7am).');
}

function refrescarSello() {
  var sh = SpreadsheetApp.getActive().getSheetByName(CFG.OUT_SHEET);
  if (!sh) return;
  sh.getRange('A2').setValue(subtitulo_());
}

// ------------------------------ HELPERS ------------------------------------
function colLetter_(n) {                     // 1 -> A, 27 -> AA
  var s = '';
  while (n > 0) { var r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = (n - r - 1) / 26; }
  return s;
}
function endOfMonth_(y, m) { return new Date(y, m + 1, 0); }   // m 0-based
function subtitulo_() {
  var ts = Utilities.formatDate(new Date(), CFG.TZ, 'dd/MM/yyyy HH:mm');
  return 'Datos en vivo desde CRM · Última actualización: ' + ts;
}

function buildDays_(mStart, mEnd) {
  var out = [], d = new Date(mStart);
  while (d <= mEnd) { out.push(new Date(d)); d.setDate(d.getDate() + 1); }
  return out;
}
function groupWeeks_(days) {                 // semanas Lun→Dom recortadas al mes
  var weeks = [], cur = [];
  for (var i = 0; i < days.length; i++) {
    if (cur.length && days[i].getDay() === 1) { weeks.push(cur); cur = []; }
    cur.push(days[i]);
  }
  if (cur.length) weeks.push(cur);
  return weeks;
}

// Fórmula de una celda-día para una métrica dada.
// Funciones en inglés (API) pero separador ';' porque el sheet usa locale es-CO.
function dayFormula_(mt, y, m, d) {
  var D  = 'DATE(' + y + ';' + m + ';' + d + ')';
  var D1 = '(' + D + '+1)';
  if (mt.type === 'count') {
    var c = 'CRM!$' + mt.col + ':$' + mt.col;
    return '=COUNTIFS(' + c + ';">="&' + D + ';' + c + ';"<"&' + D1 + extraFiltros_(mt) + ')';
  } else {
    var v = 'CRM!$' + mt.valCol + ':$' + mt.valCol;
    var p = 'CRM!$' + mt.dateCol + ':$' + mt.dateCol;
    var base = 'SUMIFS(' + v + ';' + p + ';">="&' + D + ';' + p + ';"<"&' + D1 + extraFiltros_(mt) + ')';
    if (mt.subEqCol) {
      // A/R pendiente = total por fecha (AC) - las marcadas Realizado (así cuenta AE en blanco / "No realizado")
      var sub = 'SUMIFS(' + v + ';' + p + ';">="&' + D + ';' + p + ';"<"&' + D1 +
                ';CRM!$' + mt.subEqCol + ':$' + mt.subEqCol + ';"' + mt.subEqVal + '")';
      return '=' + base + '-' + sub;
    }
    return '=' + base;
  }
}

// Filtros extra opcionales, iguales para COUNTIFS y SUMIFS.
function extraFiltros_(mt) {
  var s = '';
  if (mt.ltVal)         s += ';CRM!$' + mt.ltCol  + ':$' + mt.ltCol  + ';"<'  + mt.ltVal  + '"';
  if (mt.gteVal)        s += ';CRM!$' + mt.gteCol + ':$' + mt.gteCol + ';">=' + mt.gteVal + '"';
  if (mt.gtVal != null) s += ';CRM!$' + mt.gtCol  + ':$' + mt.gtCol  + ';">'  + mt.gtVal  + '"';
  if (mt.blankCol)      s += ';CRM!$' + mt.blankCol + ':$' + mt.blankCol + ';""';   // celda vacía
  if (mt.eqCol)         s += ';CRM!$' + mt.eqCol + ':$' + mt.eqCol + ';"' + mt.eqVal + '"';  // igual a texto (ej. AE = "Realizado")
  return s;
}

// ------------------------------ BUILD --------------------------------------
function construirScorecard() {
  var ss = SpreadsheetApp.getActive();
  if (!ss.getSheetByName(CFG.CRM_SHEET)) throw new Error('No existe la pestaña "' + CFG.CRM_SHEET + '".');

  var start = CFG.START;
  // null = auto-extiende hasta fin del MES SIGUIENTE (para ver cuotas A/R por vencer).
  var end   = CFG.END || endOfMonth_(new Date().getFullYear(), new Date().getMonth() + 1);

  // 1) Planear columnas -----------------------------------------------------
  var columns = [];              // {kind, col, ...}
  var months  = [];              // metadata por mes para encabezados
  var mtColsAll = [];
  var ptr = 3;                   // empieza en C

  var cur = new Date(start.getFullYear(), start.getMonth(), 1);
  var last = new Date(end.getFullYear(), end.getMonth(), 1);
  while (cur <= last) {
    var y = cur.getFullYear(), m0 = cur.getMonth();
    var mStart = new Date(Math.max(start.getTime(), new Date(y, m0, 1).getTime()));
    var mEnd   = new Date(Math.min(end.getTime(),   endOfMonth_(y, m0).getTime()));
    var weeks  = groupWeeks_(buildDays_(mStart, mEnd));

    var monthStartCol = ptr, wtCols = [], weekMeta = [];
    for (var w = 0; w < weeks.length; w++) {
      var wk = weeks[w], dayStart = ptr;
      for (var i = 0; i < wk.length; i++) {
        columns.push({ kind: 'day', col: ptr, y: wk[i].getFullYear(), m: wk[i].getMonth() + 1, d: wk[i].getDate(), dow: wk[i].getDay() });
        ptr++;
      }
      var dayEnd = ptr - 1;
      columns.push({ kind: 'wt', col: ptr, start: dayStart, end: dayEnd });
      weekMeta.push({ start: dayStart, totalCol: ptr, n: w + 1 });
      wtCols.push(ptr); ptr++;
    }
    columns.push({ kind: 'mt', col: ptr, wtCols: wtCols.slice() });
    var monthTotalCol = ptr; mtColsAll.push(ptr); ptr++;

    months.push({
      startCol: monthStartCol, endCol: monthTotalCol, totalCol: monthTotalCol,
      label: MESES[m0] + ' ' + y, abbr: MESES[m0].substring(0, 3).toUpperCase() + '-' + String(y).substring(2),
      weeks: weekMeta
    });
    cur.setMonth(cur.getMonth() + 1);
  }
  columns.push({ kind: 'grand', col: ptr, mtCols: mtColsAll.slice() });
  var grandCol = ptr;
  var lastCol = grandCol;

  // 2) Reusar la hoja SIN borrarla ------------------------------------------
  // CRÍTICO: borrar+recrear la hoja (o insertar columnas ANTES de las de datos)
  // desplaza las referencias externas de Global (ej. BC6 -> DR6). Por eso aquí
  // se limpia EN SITIO y las columnas nuevas se agregan solo al FINAL.
  var sh = ss.getSheetByName(CFG.OUT_SHEET);
  if (!sh) sh = ss.insertSheet(CFG.OUT_SHEET);
  sh.setFrozenRows(0);
  sh.setFrozenColumns(0);
  sh.getRange(1, 1, sh.getMaxRows(), sh.getMaxColumns()).breakApart();  // deshacer merges
  sh.clear();                                                           // contenido + formato
  var faltan = lastCol - sh.getMaxColumns();     // agregar columnas SOLO al final
  if (faltan > 0) sh.insertColumnsAfter(sh.getMaxColumns(), faltan);
  sh.setHiddenGridlines(true);

  // 3) Título + subtítulo ---------------------------------------------------
  // Sin merge: un merge que cruce la columna congelada (2) rompe setFrozenColumns.
  // El texto simplemente desborda sobre las celdas vacías a la derecha.
  sh.getRange(1, 1).setValue('Daily Metrics — Reconexión Financiera')
    .setFontSize(14).setFontWeight('bold').setFontColor(C.NAVY);
  sh.getRange(2, 1).setValue(subtitulo_()).setFontColor('#5f6368').setFontStyle('italic');

  // 4) Encabezados izquierda ------------------------------------------------
  sh.getRange(HDR.MONTH, 1, 3, 1).merge().setValue('Métrica');
  sh.getRange(HDR.MONTH, 2, 3, 1).merge().setValue('% Conv');
  sh.getRange(HDR.MONTH, 1, 3, 2)
    .setBackground(C.NAVY).setFontColor(C.WHITE).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');

  // 5) Bandas de mes / semana / día -----------------------------------------
  months.forEach(function (mo) {
    // banda de mes (row 3)
    sh.getRange(HDR.MONTH, mo.startCol, 1, mo.endCol - mo.startCol + 1).merge()
      .setValue(mo.label).setBackground(C.NAVY).setFontColor(C.WHITE)
      .setFontWeight('bold').setHorizontalAlignment('center');
    // bandas de semana (row 4)
    mo.weeks.forEach(function (wk) {
      sh.getRange(HDR.WEEK, wk.start, 1, wk.totalCol - wk.start + 1).merge()
        .setValue('Semana ' + wk.n).setBackground(C.NAVY2).setFontColor(C.WHITE)
        .setHorizontalAlignment('center');
    });
    // celda "Mensual" sobre la col total de mes (row 4)
    sh.getRange(HDR.WEEK, mo.totalCol).setValue('Mensual')
      .setBackground(C.BLUE_H).setFontColor(C.WHITE).setFontWeight('bold')
      .setHorizontalAlignment('center');
  });

  // grand total: merge filas 3-5
  sh.getRange(HDR.MONTH, grandCol, 3, 1).merge().setValue('TOTAL')
    .setBackground(C.TOTAL_H).setFontColor(C.WHITE).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');

  // fila de día (row 5)
  columns.forEach(function (c) {
    var cell = sh.getRange(HDR.DAY, c.col);
    if (c.kind === 'day') {
      cell.setValue(DIAS[c.dow] + ' ' + c.d).setBackground(C.NAVY).setFontColor(C.WHITE);
    } else if (c.kind === 'wt') {
      cell.setValue('Total').setBackground(C.GREEN_H).setFontColor(C.WHITE).setFontWeight('bold');
    } else if (c.kind === 'mt') {
      var mo = months.filter(function (x) { return x.totalCol === c.col; })[0];
      cell.setValue(mo ? mo.abbr : 'MES').setBackground(C.BLUE_H).setFontColor(C.WHITE).setFontWeight('bold');
    }
    cell.setHorizontalAlignment('center').setFontSize(9);
  });

  // 6) Etiquetas de métrica (col A) + % Conv (col B) ------------------------
  var labels = METRICS.map(function (mt) { return [mt.label]; });
  sh.getRange(DATA0, 1, METRICS.length, 1).setValues(labels).setFontWeight('bold');
  // (el fondo de la columna A se pinta por sección en el paso 8.5)

  var convFormulas = [];
  for (var r = 0; r < METRICS.length; r++) {
    if (FUNNEL_PREV.hasOwnProperty(r)) {
      var gl = colLetter_(grandCol);
      var rowThis = DATA0 + r, rowPrev = DATA0 + FUNNEL_PREV[r];
      convFormulas.push(['=IFERROR(' + gl + rowThis + '/' + gl + rowPrev + ';"")']);
    } else {
      convFormulas.push(['']);
    }
  }
  sh.getRange(DATA0, 2, METRICS.length, 1).setFormulas(convFormulas)
    .setNumberFormat('0.0%').setBackground(C.GREY_C).setHorizontalAlignment('center');

  // 7) Bloque de datos (fórmulas) ------------------------------------------
  var nCols = lastCol - 2;                 // desde col 3
  var grid = [];
  for (var rr = 0; rr < METRICS.length; rr++) {
    var mt = METRICS[rr], rowNum = DATA0 + rr, line = [];
    for (var cc = 0; cc < columns.length; cc++) {
      var c = columns[cc], f;
      if (mt.type === 'diff') {
        // resta por columna: mismaColumna(minuendo) - mismaColumna(sustraendo)
        var Ld = colLetter_(c.col);
        f = '=' + Ld + (DATA0 + METRIC_IDX[mt.minuend]) + '-' + Ld + (DATA0 + METRIC_IDX[mt.subtrahend]);
      } else if (c.kind === 'day') {
        f = dayFormula_(mt, c.y, c.m, c.d);
      } else if (c.kind === 'wt') {
        f = '=SUM(' + colLetter_(c.start) + rowNum + ':' + colLetter_(c.end) + rowNum + ')';
      } else if (c.kind === 'mt') {
        f = '=' + c.wtCols.map(function (x) { return colLetter_(x) + rowNum; }).join('+');
      } else {
        f = '=' + c.mtCols.map(function (x) { return colLetter_(x) + rowNum; }).join('+');
      }
      line.push(f);
    }
    grid.push(line);
  }
  var dataRange = sh.getRange(DATA0, 3, METRICS.length, nCols);
  dataRange.setFormulas(grid);

  // 8) Formatos numéricos por fila -----------------------------------------
  for (var q = 0; q < METRICS.length; q++) {
    var fmt = METRICS[q].money ? '"$"#,##0' : '#,##0';
    sh.getRange(DATA0 + q, 3, 1, nCols).setNumberFormat(fmt);
  }

  // 8.5) Fondo por SECCIÓN (funnel/base/revenue/cash); columna A un tono más fuerte;
  //      filas "reales" (emphasize) con tono aún más marcado y en negrita.
  for (var s = 0; s < METRICS.length; s++) {
    var sec = SEC[METRICS[s].section] || SEC.base;
    var row = DATA0 + s, emph = METRICS[s].emphasize;
    sh.getRange(row, 1, 1, lastCol).setBackground(emph ? sec.emph : sec.data);  // toda la fila
    sh.getRange(row, 1).setBackground(emph ? sec.emph : sec.label);             // etiqueta (col A)
    if (emph) sh.getRange(row, 1, 1, lastCol).setFontWeight('bold');
  }

  // 9) Totales (datos) con el color FUERTE de la sección de cada fila, para
  //    que los totales también diferencien secciones (no verde/azul uniforme).
  //    Se pinta por columna (un setBackgrounds por columna de total) = eficiente.
  var totBg = METRICS.map(function (mt) { return [(SEC[mt.section] || SEC.base).total]; });
  columns.forEach(function (c) {
    if (c.kind === 'wt' || c.kind === 'mt' || c.kind === 'grand') {
      sh.getRange(DATA0, c.col, METRICS.length, 1).setBackgrounds(totBg);
    }
  });
  // resaltar filas de dinero en la etiqueta
  sh.getRange(DATA0, 1, METRICS.length, lastCol).setFontSize(9);
  sh.getRange(DATA0, 1, METRICS.length, 1).setFontSize(10);

  // 10) Anchos, bordes, congelar -------------------------------------------
  sh.setColumnWidth(1, 190);
  sh.setColumnWidth(2, 62);
  columns.forEach(function (c) {
    var w = c.kind === 'day' ? 46 : (c.kind === 'wt' ? 58 : (c.kind === 'mt' ? 76 : 86));
    sh.setColumnWidth(c.col, w);
  });
  sh.getRange(HDR.MONTH, 1, METRICS.length + 3, lastCol)
    .setBorder(true, true, true, true, true, true, '#d0d7de', SpreadsheetApp.BorderStyle.SOLID);
  sh.setFrozenRows(HDR.DAY);
  sh.setFrozenColumns(2);
  sh.getRange(HDR.MONTH, 3, 3, lastCol - 2).setVerticalAlignment('middle');

  // limpiar filas/columnas sobrantes
  var maxR = sh.getMaxRows(), lastUsedR = DATA0 + METRICS.length - 1;
  if (maxR > lastUsedR + 2) sh.deleteRows(lastUsedR + 3, maxR - (lastUsedR + 2));
  var maxC = sh.getMaxColumns();
  if (maxC > lastCol) sh.deleteColumns(lastCol + 1, maxC - lastCol);

  ss.setActiveSheet(sh);
  ss.toast('Scorecard reconstruido: ' + Utilities.formatDate(new Date(), CFG.TZ, 'HH:mm'), '✅ Listo', 5);
}

function tintCol_(sh, col, color) {
  sh.getRange(DATA0, col, METRICS.length, 1).setBackground(color);
}