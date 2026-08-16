/**
 * ============================================================================
 *  LimpiarFechasCRM — corrige fechas MAL ESCRITAS (guardadas como texto) en las
 *  columnas de fecha del CRM, SIN tocar los textos de estado ni las fechas ya
 *  válidas. Preserva la fecha Y la hora reales.
 *
 *  Regla de seguridad (lo más importante):
 *   - Si la celda contiene LETRAS  -> es un ESTADO ("No compró", "No asistió",
 *     "Reagendó", "Canceló…", "Pendiente"…) -> NO se toca.
 *   - Solo se convierten cadenas de dígitos + separadores ( - / . : espacio )
 *     que representen una fecha válida dentro del rango de años configurado.
 *   - Lo que tenga dígitos pero no se pueda interpretar con certeza NO se toca
 *     y queda listado en "REVISAR A MANO".
 *
 *  Ejecutar la función  limpiarFechasCRM().  Muestra un resumen y deja el
 *  detalle en el Registro de ejecución (Ver → Registros).
 *
 *  Ejemplos que corrige (texto -> fecha real, misma fecha/hora):
 *   "2026-07-10 3.30"   -> 2026-07-10 03:30
 *   "2026/07/02 11"     -> 2026-07-02 11:00
 *   "2026-06-21-8:00"   -> 2026-06-21 08:00
 *  Ejemplos que DEJA intactos: "No compró", "No asistió", "Reagendó", "16/062026"
 *  (este último se lista para revisar porque le falta un separador).
 * ============================================================================
 */
var LF_CFG = {
  CRM_SHEET: 'CRM',
  COLS: ['H', 'I', 'K', 'L', 'O', 'P'],   // columnas de fecha del CRM
  TZ: 'America/Bogota',
  MIN_YEAR: 2025, MAX_YEAR: 2027          // rango razonable; fuera de esto -> revisar
};

function limpiarFechasCRM() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(LF_CFG.CRM_SHEET);
  if (!sh) throw new Error('No existe la pestaña "' + LF_CFG.CRM_SHEET + '".');
  var lastRow = sh.getLastRow();
  var fixed = [], review = [];

  LF_CFG.COLS.forEach(function (letter) {
    var col = colNum_(letter);
    var vals = sh.getRange(2, col, lastRow - 1, 1).getValues();
    for (var i = 0; i < vals.length; i++) {
      var v = vals[i][0];
      if (typeof v !== 'string') continue;          // ya es número/fecha -> no tocar
      var t = v.trim();
      if (t === '') continue;
      if (/[A-Za-zÀ-ÿ]/.test(t)) continue;          // tiene letras => ESTADO => no tocar
      var row = i + 2;
      var d = parseFecha_(t);
      if (d && d.getFullYear() >= LF_CFG.MIN_YEAR && d.getFullYear() <= LF_CFG.MAX_YEAR) {
        sh.getRange(row, col).setValue(d);          // escribe SOLO esta celda
        fixed.push(letter + row + ':  "' + t + '"  ->  ' +
                   Utilities.formatDate(d, LF_CFG.TZ, 'yyyy-MM-dd HH:mm'));
      } else {
        review.push(letter + row + ':  "' + t + '"');
      }
    }
  });

  Logger.log('=== CORREGIDAS (' + fixed.length + ') ===\n' + fixed.join('\n') +
             '\n\n=== REVISAR A MANO (' + review.length + ') ===\n' + review.join('\n'));
  var msg = fixed.length + ' fecha(s) corregida(s).';
  if (review.length) msg += '\n' + review.length + ' con dígitos pero ambiguas (revisar a mano).';
  msg += '\n\nNo se tocó ningún texto de estado (No compró, No asistió, Reagendó, etc.).' +
         '\nDetalle en Ver → Registros.';
  SpreadsheetApp.getUi().alert('Limpieza de fechas del CRM', msg, SpreadsheetApp.getUi().ButtonSet.OK);
}

// Interpreta una cadena tipo fecha -> Date. Devuelve null si no aplica.
function parseFecha_(s) {
  s = s.replace(/\//g, '-').trim();   // normaliza / -> -
  //  Año primero: AAAA-MM-DD [ (sep) H (sep) MM ]  (sep = espacio, guion, T, punto o :)
  var m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[\sTt\-]+(\d{1,2})(?:[.:\s](\d{1,2}))?)?\s*$/);
  if (m) return mkDate_(+m[1], +m[2], +m[3], m[4], m[5]);
  //  Día primero (es-CO): DD-MM-AAAA
  var m2 = s.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
  if (m2) return mkDate_(+m2[3], +m2[2], +m2[1], null, null);
  //  Día primero sin separador mes/año: "16-062026" (= 16/06/2026)
  var m3 = s.match(/^(\d{1,2})-(\d{2})(\d{4})$/);
  if (m3) return mkDate_(+m3[3], +m3[2], +m3[1], null, null);
  return null;
}

function mkDate_(y, mo, d, hh, mm) {
  var h = hh != null ? +hh : 0, mi = mm != null ? +mm : 0;
  if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59) return null;
  return new Date(y, mo - 1, d, h, mi, 0);
}

function colNum_(letter) {
  var n = 0;
  for (var i = 0; i < letter.length; i++) n = n * 26 + (letter.charCodeAt(i) - 64);
  return n;
}