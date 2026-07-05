# Guía MCP Google Sheets — Conectar la IA a Google Sheets

> Para construir el producto #1 (STR/Airbnb spreadsheet) de forma eficiente:
> yo (Kiro/Claude) **creo el archivo, escribo los datos, las fórmulas y el formato** directamente en tu Google Drive. Tú solo verificas y ajustas detalles. Fecha: **5-jul-2026**.
>
> **Fuentes:** [Google Workspace MCP oficial](https://developers.google.com/workspace/guides/configure-mcp-servers) · [mcp-gsheets (freema)](https://mcpservers.org/servers/freema/mcp-gsheets).

---

## 0. Las dos opciones — elige la que más encaje

| | Opción A: `mcp-gsheets` (freema) | Opción B: Google Workspace MCP (oficial Google) |
|--|----------------------------------|------------------------------------------------|
| **Quién lo mantiene** | Comunidad (Tomás Grásl, MIT) | Google (oficial) |
| **Autenticación** | Service Account (JSON key) — sin OAuth interactivo | OAuth 2.0 — requiere Google Cloud Project |
| **Capacidades Sheets** | ✅ Completo: crear, leer, escribir, formatear, gráficos, validación, fórmulas, condicionales, estructuras | 🟡 Google Drive MCP: subir/bajar archivos, buscar, leer; el **Sheets API avanzado** (crear pestañas, fórmulas, formatos) **no está incluido** en la versión remota oficial |
| **Setup** | ~15 min (solo Sheets API + service account) | ~30–40 min (Cloud Project + múltiples APIs + OAuth consent) |
| **Compatibilidad con Kiro** | ✅ Cualquier MCP stdio (via `npx`) | ✅ Remote MCP (URL) — también soportado |
| **Limitación clave** | Debes compartir el Sheet con la service account email | El Drive MCP oficial no expone el API completo de Sheets (formato, fórmulas avanzadas) |

## ✅ Elección recomendada: **Opción A — `mcp-gsheets` (freema)**

**Por qué:** para construir el STR spreadsheet necesitamos el **API completo de Sheets** — crear pestañas, escribir fórmulas (`=ARRAYFORMULA`, `=SUMIF`), aplicar formato, crear gráficos, validación de datos (dropdowns), formato condicional, y color-coding. El MCP oficial de Google Drive **no expone esas capacidades**; solo lee/escribe archivos de Drive.

`mcp-gsheets` tiene **todas esas herramientas** y es la opción más rápida de configurar para lo que necesitamos.

---

## Guía paso a paso — `mcp-gsheets` en Kiro

### Prerrequisitos
- Node.js v20+ instalado (`node --version`)
- Cuenta de Google
- Kiro IDE abierto en el proyecto

---

### Paso 1 — Crear el Google Cloud Project y habilitar la API

1. Ve a [console.cloud.google.com](https://console.cloud.google.com).
2. Haz clic en **"Select a project"** → **"New Project"**.
   - Nombre: `etsy-product-builder` (o el que quieras).
   - Click **Create**.
3. Con el proyecto seleccionado, ve a **"APIs & Services" → "Library"**.
4. Busca **"Google Sheets API"** → Click **"Enable"**.
5. *(Opcional pero recomendado)* Busca **"Google Drive API"** → Enable también (para listar archivos).

---

### Paso 2 — Crear la Service Account y descargar el JSON

1. Ve a **"APIs & Services" → "Credentials"**.
2. Click **"Create Credentials" → "Service Account"**.
   - Nombre: `sheets-mcp-agent` → **Create and Continue** → **Done**.
3. En la lista de Service Accounts, haz click en el que creaste.
4. Pestaña **"Keys"** → **"Add Key" → "Create new key" → JSON → Create**.
5. Se descarga un archivo `.json` (ej. `etsy-product-builder-abc123.json`).
   - **Guárdalo en un lugar seguro** (ej. `~/.config/mcp-credentials/sheets-key.json`).
   - ⚠️ **NUNCA** lo subas a un repositorio de Git.
6. Copia el campo `client_email` del JSON (lo necesitas en el Paso 4).

---

### Paso 3 — Agregar el MCP a Kiro

Abre (o crea) el archivo de configuración MCP de Kiro en tu proyecto:

**Ubicación:** `.kiro/settings/mcp.json` (workspace) o `~/.kiro/settings/mcp.json` (global)

Agrega esta entrada:

```json
{
  "mcpServers": {
    "google-sheets": {
      "command": "npx",
      "args": ["-y", "mcp-gsheets@latest"],
      "env": {
        "GOOGLE_PROJECT_ID": "TU_PROJECT_ID",
        "GOOGLE_APPLICATION_CREDENTIALS": "/ruta/absoluta/a/sheets-key.json"
      }
    }
  }
}
```

Reemplaza:
- `TU_PROJECT_ID` → el Project ID de Google Cloud (visible en el dashboard del proyecto).
- `/ruta/absoluta/...` → la ruta real al JSON descargado en el Paso 2.

> **Alternativa sin archivo** (más segura para entornos compartidos — usa variables de entorno directamente):
> ```json
> "env": {
>   "GOOGLE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
>   "GOOGLE_CLIENT_EMAIL": "sheets-mcp-agent@tu-proyecto.iam.gserviceaccount.com"
> }
> ```

---

### Paso 4 — Crear el Google Sheet y compartirlo con la Service Account

1. Ve a [sheets.new](https://sheets.new) — se crea un Sheet vacío en tu Drive.
2. Copia el **Spreadsheet ID** de la URL:
   ```
   https://docs.google.com/spreadsheets/d/[ESTE_ES_EL_ID]/edit
   ```
3. Click **"Share"** (esquina superior derecha).
4. Pega el `client_email` del JSON (ej. `sheets-mcp-agent@etsy-product-builder-xxx.iam.gserviceaccount.com`).
5. Dale permiso de **"Editor"** → **Send**.

---

### Paso 5 — Verificar que funciona

En el chat de Kiro, escríbeme:

```
"Usando el MCP de Google Sheets, lee los metadatos del spreadsheet con ID [TU_SPREADSHEET_ID]"
```

Si respondo con el título y las pestañas → **todo funciona**. Arrancamos a construir.

---

### Paso 6 — Construir el producto (mi trabajo)

Con el MCP conectado, yo puedo:
- ✅ Crear todas las pestañas (Setup, Dashboard, Bookings, Expenses, P&L, Tax Summary, Cleaning, Supplies).
- ✅ Escribir los headers, datos de ejemplo y **todas las fórmulas** (ADR, RevPAR, Occupancy, comisiones, P&L).
- ✅ Aplicar formato (colores, tipografía, bordes, color-coding condicional).
- ✅ Crear dropdowns de validación (plataformas, categorías de gasto, propiedades).
- ✅ Crear el dashboard con gráficos.
- ✅ Aplicar formato condicional (alertas de bajo stock, semáforos de ocupación).

**Tú:** revisas cada pestaña, validas que las fórmulas arrojen los números correctos con tus datos reales, y ajustas el estilo si lo necesitas.

---

## Solución de problemas comunes

| Error | Causa | Solución |
|-------|-------|----------|
| "Authentication failed" | Ruta del JSON incorrecta o no absoluta | Verificar que la ruta empiece con `/` (ej. `/home/usuario/...`, no `~/...`) |
| "Permission denied" | El Sheet no fue compartido con la service account | Paso 4: compartir con el email exacto del JSON |
| "Spreadsheet not found" | ID incorrecto | Copiar el ID de la URL (entre `/d/` y `/edit`) |
| MCP no aparece en Kiro | Config no guardada o JSON inválido | Validar el JSON con un linter antes de guardar |

---

## Seguridad

- El archivo `.json` de credenciales va en `.gitignore` — nunca en el repo.
- La service account **solo tiene acceso** a los Sheets que tú compartes explícitamente.
- Si en el futuro quieres revocar el acceso, elimina la key desde Google Cloud Console.

---

> **Siguiente paso:** completa los Pasos 1–5, y cuando me confirmes que el paso de verificación funcionó, yo arranco con la construcción completa del STR spreadsheet.
