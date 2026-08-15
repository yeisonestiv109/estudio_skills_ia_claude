# 01 · Entorno, Operación y Hacks

> Documento maestro del entorno técnico, flujos operativos y contexto contractual.

# Perfiles de Colaboradores y Entorno Técnico

> Quién trabaja en este repo y con qué entorno local. **El contexto del proyecto (memoria, hooks, skills, specs) es compartido entre ambos.** Lo que NO es compartido es el entorno de máquina — no asumir que una configuración local aplica al otro colaborador.

## Yeisiton (Yeison Estiven Delgado Ordoñez) — Fundador

- Perfil profesional completo → [`00_vision_y_principios.md`](00_vision_y_principios.md) (consolidado ahí en la reestructuración del 13-ago-2026).
- **Entorno de trabajo local (solo aplica a su sesión, NO a Gabyota):**
  - Laptop: Dell Latitude 7430 (Intel Core i5 12th Gen, 16 GB RAM), Windows 11 Pro 64-bit.
  - **Entorno de ejecución principal: WSL2 (Ubuntu Linux nativo).** Todo el código, `.venv`, `node_modules` y compilación viven en el filesystem de Linux (`/home/estiv12/...`), nunca en `/mnt/c/...` (evita cuellos de botella de I/O).
  - Kiro IDE conectado vía extensión `kiro-wsl` (Proposed API `"enable-proposed-api": ["yishiashia.kiro-wsl"]`).
  - Runtimes: Node.js vía `fnm` (Fast Node Manager), Python vía `uv` (Astral) — `uv venv` + `uv pip install`/`uv run`. Docker Desktop con backend WSL2. Agente CLI: Google Antigravity `agy`. Control de versiones: Git + `gh`.
  - **Regla de comandos:** siempre Bash/Linux dentro de WSL2. Nunca `.ps1`/`.bat` para tareas del proyecto.
  - **Fix de entorno aplicado (24-jul-2026):** `~/.bashrc` no cargaba `fnm`/Node/npx en shells de login NO interactivos (los que usan los agentes vía `bash -lc "..."`) porque el guard `case $- in *i*) ;; *) return;; esac` corta la ejecución antes de llegar al bloque `# fnm`. Se replicó la inicialización de `fnm` en `~/.profile` (que sí corre siempre en shells de login). Sin este fix, `context7`/`memory` (MCP vía `npx`) fallan siempre en invocaciones de agente aunque funcionen en terminal interactiva manual.
  - Variables de entorno/API keys en `.env` (excluido de git); plantilla pública en `.env.example`.

## Gabyota — Cofundadora de la empresa

- **NO usa WSL.** No asumir que las rutas Linux (`/home/...`), el `.venv` vía `uv`, ni los hooks con comandos Bash aplican directamente a su máquina sin adaptación.
- Perfil detallado: pendiente de completar (ver [`00_vision_y_principios.md`](00_vision_y_principios.md), campo sin rellenar).
- Si se necesita que Gabyota ejecute hooks/comandos locales, verificar primero su entorno real antes de asumir paridad con el de Yeisiton.

## Regla operativa

- **Contexto compartido:** memoria (`01_Gobernanza_EOS/`, `02_Lineas_de_Producto/*/docs/`, `03_Clientes_y_Casos/`), hooks, skills, specs y steering — son del proyecto, no de una persona.
- **Entorno técnico NO compartido:** cualquier hook o comando que asuma una ruta de venv, un shell o un runtime específico debe declarar para qué colaborador es válido, o escribirse de forma portable (ej. `uv run` en vez de rutas fijas `.venv\Scripts\python.exe`).

## MCP — NotebookLM ("cerebro de información") — bugs conocidos y protocolo (14-ago-2026)

> Servidor no oficial (Google no tiene MCP propio para NotebookLM). Elegido tras comparar
> varias alternativas de comunidad: `PleasePrompto/notebooklm-mcp` (npm `notebooklm-mcp`),
> por respuestas con citas verificables y mejor cobertura independiente. Registrado a nivel
> `user` (todas las sesiones/proyectos, no solo este repo):
> `claude mcp add -s user notebooklm -- npx notebooklm-mcp@latest`.
> Usa Chrome real vía Patchright con perfil persistente en
> `~/.local/share/notebooklm-mcp/chrome_profile/` — requiere WSLg (`DISPLAY`,
> `WAYLAND_DISPLAY`, socket en `/mnt/wslg/.X11-unix`) para mostrar la ventana de login.

**🔴 Bug #1 — `setup_auth` reporta falso negativo.** Devuelve
`{"success": false, "error": "Authentication failed or was cancelled"}` **incluso cuando el
login sí fue exitoso.** Verificado en vivo: tras un "fallo" reportado, las cookies de sesión
quedaban guardadas y frescas (`accounts.google.com`, `notebook.google.com`,
`notebooklm.google.com` en `chrome_profile/Default/Cookies`) y `ask_question` respondía
normalmente. La detección interna de éxito del paquete está rota (probablemente por el
cambio de dominio, ver Bug #3), no la autenticación real.
**Protocolo:** NUNCA confiar en el resultado de `setup_auth` a secas. Después de un intento
(éxito o "fallo"), verificar con `get_health` (`authenticated` también puede quedar en
`false` de forma engañosa) y, si hay dudas, hacer una pregunta real de prueba con
`ask_question` — esa es la única señal confiable de que el login funcionó.

**🔴 Bug #2 — `cleanup_data(confirm=true, preserve_library=true)` NO preserva la librería.**
Pese a documentar que conserva `library.json`, borra el directorio completo
`~/.local/share/notebooklm-mcp/` (incluido `library.json`) y ni siquiera recrea el
directorio en la siguiente escritura (`ENOENT` en `update_notebook`/`add_notebook` hasta
hacer `mkdir -p` manual). **Protocolo:** antes de correr `cleanup_data` con cualquier flag,
copiar `library.json` a otro lado manualmente. Si ya se corrió y se perdió: la sesión MCP
activa suele conservar la librería EN MEMORIA (`list_notebooks` la sigue mostrando aunque el
archivo ya no exista) — usar esos datos para `mkdir -p ~/.local/share/notebooklm-mcp` +
recrear con `add_notebook` antes de que la sesión se reinicie (si se reinicia, se pierde
para siempre).

**🟡 Bug #3 (hipótesis, explica el #1) — cambio de dominio no reconocido.** Las notebooks
reales quedan con URL `https://notebook.google.com/notebook/<uuid>` (sin "lm"), pero la
documentación/schema del propio servidor todavía espera
`https://notebooklm.google.com/notebook/<uuid>`. Es probable que la lógica interna de
detección de "login exitoso" siga chequeando el dominio viejo.

**Diagnóstico útil para el futuro:** los MCP tool calls dejan logs en
`~/.cache/claude-cli-nodejs/<cwd-slug>/mcp-logs-notebooklm/*.jsonl` — sirven para ver
cuánto tiempo real corrió una tool call (`"Tool 'X' still running (Ns elapsed)"`) y
descartar timeouts cortos como causa. Para confirmar si el navegador automatizado
realmente se lanza (vs. que el usuario esté interactuando con otra ventana), monitorear
`ps aux | grep -i chrom` durante el intento — el Chrome real corre con
`--user-data-dir=.../notebooklm-mcp/chrome_profile` y `--ozone-platform=x11`.

**Notebook activo:** "ARTF: Arquitectura de Software y Sistema Operativo de Negocio (Marco
EOS)" → `https://notebook.google.com/notebook/ae2ca639-f8f7-48b9-b5b8-526f5ace0a95`
(único en la librería local, sin duplicados tras la limpieza del 14-ago).


