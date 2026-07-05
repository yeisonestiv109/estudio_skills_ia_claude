# SPEC — Construcción del "STR Financial System" (Google Sheets)

> **Para el agente de Kiro IDE (con MCP de Google Sheets + Context7).** Objetivo: construir/reparar el producto #1 de Etsy en el Sheet indicado, **autocorrigiendo errores** hasta dejarlo terminado. Fecha: 5-jul-2026.
>
> **Dos caminos válidos:**
> - **Camino rápido (recomendado):** ejecutar el script ya corregido `build_str_spreadsheet.py` (ver §7). Reconstruye todo de cero, incluida la limpieza.
> - **Camino MCP:** si prefieres construir con las herramientas MCP paso a paso, sigue esta spec al pie de la letra.

## 0. Datos base

- **Spreadsheet ID:** `1QDLhbEGhoPUmD4jKy57GTWb8E3RwJ2UwFomrbCmvbhA`
- **Producto:** sistema financiero para hosts de alquiler a corto plazo (STR/Airbnb), multi-propiedad + Schedule E.
- **Idioma del producto:** inglés (mercado US/UK).
- **Estilo:** "Minimalista Ejecutivo". Tipografía **Inter**. Paleta:
  - Header oscuro `#1E1F28` · Acento azul `#34A0DB` · Verde `#2ECC71` · Ámbar `#F1C40F` · Rojo `#E74C3C` · Gris claro `#F4F5F7` · Texto `#272B36`.

## 1. ⚠️ Errores conocidos que DEBES evitar (aprendidos en la 1ª corrida)

1. **No congelar filas que parten una celda combinada.** Si combinas filas 0–1 (header + subtítulo), **congela ≥2 filas**, o mejor: **combina cada fila por separado** (fila 0 en una celda, fila 1 en otra). *(Este fue el error real: `updateSheetProperties freeze rows` cortó una celda combinada.)*
2. **No combines título+subtítulo en UNA sola celda de 2 filas.** Google solo muestra el valor de la celda superior-izquierda → el subtítulo se pierde. Haz **dos merges de 1 fila**.
3. **VLOOKUP de comisiones:** la tabla de comisiones vive en `Setup!A14:B17` (Airbnb/Vrbo/Booking.com/Direct). Cualquier fórmula que la referencie debe apuntar ahí.
4. **Rate limits:** manda los cambios en lotes (batch) y con pausas (~0.3s) entre lotes. Si recibes 429, espera y reintenta.
5. **Fórmulas:** insértalas con `valueInputOption: USER_ENTERED` (no RAW) para que se evalúen.

## 2. Paso 0 — LIMPIEZA (obligatorio, ya hay pestañas creadas)

El Sheet quedó con pestañas a medio crear. Antes de construir:

1. Lee metadatos (`sheets_get_metadata`) → lista todos los `sheetId`.
2. Crea una pestaña temporal `_temp` (Sheets exige ≥1 hoja siempre).
3. **Borra todas las demás** pestañas.
4. Crea las 8 pestañas nuevas (§3).
5. Borra `_temp`.

## 3. Las 8 pestañas (orden e IDs sugeridos)

| Orden | Nombre | Color tab | Congelar |
|-------|--------|-----------|----------|
| 1 | 🏡 Setup | azul | 2 filas |
| 2 | 📅 Bookings | verde | 2 filas |
| 3 | 💳 Expenses | ámbar | 2 filas |
| 4 | 📊 Dashboard | azul | 2 filas |
| 5 | 📈 P&L | verde | 4 filas, 1 col |
| 6 | 🧾 Tax Summary | rojo | 2 filas |
| 7 | 🧹 Cleaning | gris | 2 filas |
| 8 | 📦 Supplies | gris | 2 filas |

### 3.1 🏡 Setup
- Fila 0: título (merge A0:F0), fila 1: subtítulo con disclaimer (merge A1:F1). **Dos merges separados.**
- STEP 1 — Properties (header fila 3): columnas `Property # | Property Name | Address | Platform(s) | Nightly Rate ($) | Notes`. 5 filas (Property 1–5), 2 con datos de ejemplo.
- STEP 2 — Commission Rates (header fila 11): tabla en filas 13–16 → `Airbnb 0.03 | Vrbo 0.05 | Booking.com 0.15 | Direct 0.00`. **Debe quedar en A14:B17** (A1-notation) para el VLOOKUP.
- STEP 3 — Quick Start Guide (header fila 19): 7 líneas incluyendo el **disclaimer fiscal**.

### 3.2 📅 Bookings
- Header (fila 1): `Check-In | Check-Out | Nights | Property | Platform | Guest | Gross ($) | Platform Fee ($) | Cleaning Fee ($) | Payout Net ($) | Status | Notes`.
- Fórmulas por fila `n`: `Nights = C{n}-B{n}` (fechas); `Platform Fee = G{n}*VLOOKUP(E{n},Setup!A14:B17,2,0)`; `Payout Net = G{n}-H{n}-I{n}`.
- Dropdowns: Property (col D → Property 1–5), Platform (col E → Airbnb/Vrbo/Booking.com/Direct/Other), Status (col K → Confirmed/Pending/Cancelled/Completed).
- 3 filas de ejemplo + ~47 filas vacías con formato alterno.
- Formato moneda `$#,##0.00` en G,H,I,J.

### 3.3 💳 Expenses
- Header: `Date | Property | Category (Sch E) | Vendor | Amount ($) | Payment Method | Receipt? | Deductible? | Notes`.
- Dropdown Category = 14 categorías mapeadas a líneas de Schedule E (ver lista en el script, `EXP_CAT`).
- Dropdown Property (incluye "ALL"), Receipt? (Yes/No), Deductible? (Yes/No/Partial).
- 5 filas ejemplo + ~45 vacías.

### 3.4 📊 Dashboard
- Header fila 0 + subtítulo fila 1 (merges separados).
- 4 KPI cards (filas 4–5): `Total Payout =SUM(Bookings!J3:J100)`, `Total Expenses =SUM(Expenses!E3:E100)`, `Net Profit`, `Profit Margin` (formato %).
- Tabla "Performance by Property" (header fila 9): `Property | # Bookings | Nights Booked | ADR ($) | Occupancy % | RevPAR ($) | Net Revenue ($) | Expenses ($)`.
  - `# Bookings = COUNTIF(Bookings!D3:D100,"Property X")`
  - `Nights Booked = SUMIF(Bookings!D..,"Property X",Bookings!C..)`
  - `ADR = IFERROR(SUMIF(...Gross)/NightsBooked,0)`
  - `Occupancy % = IFERROR(NightsBooked/90,0)` (90 = noches disponibles/trimestre; documentar como editable)
  - `RevPAR = ADR*Occupancy`
  - Fila total "ALL PROPERTIES".

### 3.5 📈 P&L
- Estado de resultados por propiedad (cols B–F) + columna "ALL PROPERTIES" (`=SUM(B:F)` por fila).
- Secciones REVENUE (Gross, -Platform Fees, -Cleaning, Net Revenue) y EXPENSES (Cleaning, Supplies, Utilities, Insurance, Repairs, Total) → NET PROFIT + Profit Margin %.
- Usa `SUMIF`/`SUMPRODUCT` con búsqueda por categoría (`ISNUMBER(SEARCH("Cleaning",...))`).
- Congelar 4 filas + 1 columna.

### 3.6 🧾 Tax Summary
- Aviso ámbar (fila 1): "Share with your CPA. Organizational purposes only — NOT tax advice."
- Tabla por línea de Schedule E (L5..L19) con `SUMPRODUCT(ISNUMBER(SEARCH(...)))` sobre Expenses, + fila TOTAL.
- Sección Gross Income (bookings brutos, fees, net).

### 3.7 🧹 Cleaning & 3.8 📦 Supplies
- Cleaning: `Date | Property | Checkout Date | Cleaner | Cost ($) | Duration (hrs) | Status | Notes` + dropdown Status.
- Supplies: `Item | Property | Category | Par Level | Current Stock | Status | Last Restocked` + dropdown Status (OK/Low/Order Now).

## 4. Formato transversal
- Headers: fondo oscuro, texto blanco, negrita, centrado, Inter.
- Filas de datos: alternar `#F4F5F7` / blanco (zebra).
- Formato condicional (opcional pero recomendado): Supplies `Status="Order Now"` → rojo; `="Low"` → ámbar. Dashboard Occupancy < 40% → rojo.

## 5. Protocolo de autocorrección (para el agente)
1. Ejecuta cada lote de cambios.
2. Si la API devuelve **HTTP 400**, **lee el mensaje** (es específico: p.ej. "can't freeze rows which contain only part of a merged cell").
3. Consulta **Context7** la doc de `Google Sheets API - spreadsheets.batchUpdate` para el request problemático.
4. Aplica la corrección (ver §1 para los casos ya conocidos), reintenta ese lote.
5. Continúa hasta que las 8 pestañas estén completas sin errores.

## 6. Criterios de aceptación (verificar al final)
- [ ] 8 pestañas creadas, nombradas y con color; sin la `_temp` ni la hoja default.
- [ ] Bookings: al escribir una reserva real, `Platform Fee` y `Payout Net` se calculan solos.
- [ ] Dashboard: ADR, Occupancy y RevPAR muestran números (no #REF/#DIV) con datos de ejemplo.
- [ ] P&L y Tax Summary suman por categoría correctamente.
- [ ] Dropdowns funcionan en Property/Platform/Status/Category.
- [ ] Disclaimer fiscal visible en Setup y Tax Summary.
- [ ] Ningún error de "freeze/merge".

## 7. Camino rápido — ejecutar el script corregido
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/ruta/a/key.json"
python build_str_spreadsheet.py --id 1QDLhbEGhoPUmD4jKy57GTWb8E3RwJ2UwFomrbCmvbhA
```
El script ya incluye la **limpieza previa** (Paso 0) y las correcciones de §1. Reconstruye todo idempotentemente.
