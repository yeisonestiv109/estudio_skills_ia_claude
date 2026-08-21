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

**🟡 Bug #4 — `ask_question` captura el texto de carga transitorio de NotebookLM en vez de
la respuesta real** ("Explorando tu material…", "Leyendo capítulos enteros…", "Recuperando
los detalles…", "Verificando el alcance…"), confirmado de nuevo el 20-ago-2026 (3/3 intentos
en sesiones frescas con preguntas cortas devolvieron solo texto de carga). No hay forma
confiable de "esperar" una respuesta pendiente — cada llamada a `ask_question` manda un
mensaje nuevo y reinicia la generación, así que esperar más tiempo entre llamadas no ayuda.
**Protocolo:** probar 2-3 preguntas cortas en sesiones frescas; si las 3 vuelven solo con
texto de carga, dejar de insistir con la herramienta y usar la documentación local en su
lugar, avisando que NotebookLM está inestable en ese momento — no proceder en silencio sobre
una respuesta vacía/de carga, ni quedarse en loop reintentando.

**Notebook activo:** "ARTF: Arquitectura de Software y Sistema Operativo de Negocio (Marco
EOS)" → `https://notebook.google.com/notebook/ae2ca639-f8f7-48b9-b5b8-526f5ace0a95`
(único en la librería local, sin duplicados tras la limpieza del 14-ago). **Es el "segundo
cerebro" de Yeisiton para arquitectura/historia de ARTF — consultarlo proactivamente ante
preguntas de ese tipo, no solo cuando se pida explícitamente.**

## Reestructuración de repos + Graphify + memoria compartida (20-ago-2026)

**Problema real detectado (no solo sospechado por Yeisiton):** la memoria auto-persistente
de Claude Code vive por defecto en `~/.claude/projects/<cwd-saneado>/memory/` — una carpeta
DISTINTA por cada directorio de trabajo raíz donde se abre una sesión. Confirmado en vivo que
esto ya había fragmentado contexto real: una sesión abierta antes directamente dentro de
`estudio_skills_ia_claude/` (13-ago) dejó 4 archivos de memoria completamente huérfanos
(perfil de usuario, referencia del notebook de NotebookLM, bug de NotebookLM, estado de
migración) que ninguna sesión posterior — incluida toda la ronda de trabajo del 19/20-ago —
llegó a ver. Rescatados y fusionados a la memoria activa el 20-ago.

**Fix aplicado — `autoMemoryDirectory` en `.claude/settings.local.json`** (mecanismo nativo
de Claude Code, no un workaround manual): `estudio_skills_ia_claude/`, `artf-pipeline-app/`,
`outbound-prospector-app/` y la carpeta padre misma apuntan ahora al mismo directorio
compartido (`~/.claude/projects/-home-estiv12-proyecto-cliente-catalina/memory`) — cualquier
sesión futura, sin importar en cuál de estas carpetas se abra, lee y escribe la MISMA
memoria. Archivo gitignored en los repos (config personal, no de equipo). (Ver corrección más
abajo: el tercer proyecto real es `outbound-prospector-app`, no `ai_lead_prospector` — ese es
un proyecto completamente distinto, sin relación con esta agencia.)

**`artf-pipeline-app` movido a `/home/estiv12/proyecto_negocio_doscaras/artf-pipeline-app/`**
(antes vivía separado en `/home/estiv12/artf-pipeline-app`, sin relación de carpetas con el
resto) — al mismo nivel que `estudio_skills_ia_claude/`, para que ambos proyectos conectados
(el código real y la base de conocimiento/gobernanza) se gestionen juntos. Movido excluyendo
`node_modules`/`.next` (regenerados con `npm install`/`next build` en el destino, no tenía
sentido copiar/mover ~1.4GB regenerable) — verificado con diff de archivos idéntico,
`git log`/remote intactos, y `npm run type-check` limpio tras el movimiento.

**CORRECCIÓN REAL (misma sesión, confirmada por Yeisiton, no asumida): `/home/estiv12/ai_lead_prospector`
NO es El Prospector de la agencia.** Es un proyecto totalmente distinto ("AI LEAD PROSPECTOR"
v3.14.0, branding "Glovar", autoría "Antigravity AI", historia de git real propia hasta el
3-jul-2026) — se había tocado por error ahí un `autoMemoryDirectory` asumiendo que era el
mismo proyecto; revertido por completo (`.claude/` borrado, `.gitignore` restaurado con
`git checkout`) en cuanto Yeisiton corrigió el error. **El Prospector real** siempre vivió
anidado dentro de este mismo repo, en `02_Lineas_de_Producto/Outbound_Prospector/` (antes,
antes de la reestructuración EOS del 13-ago, en una estructura plana `src/`/`tests/` en la
raíz) — 8.957 líneas reales en `src/` + 7.440 en `tests/`, nada de scaffold.

**Extraído a su propio repo hermano `outbound-prospector-app/`, preservando su historia real
de git** (`git filter-repo`, no un simple `mv`/copia — habría perdido la historia): 16 commits
reales recuperados desde `chore: consolidacion de memoria y arquitectura base Motores 1 y 2`
(22-jul-2026). Verificado standalone tras la extracción: 476/480 tests pasan (los 4 fallos
son de calibración de tiers/aging de TheirStack ya documentada como en curso, no una
regresión de la extracción). `pyproject.toml` propio creado (dependencias reales inferidas de
los imports: `pydantic[email]`, `requests`, `tenacity`, `feedparser`, `groq`, `bs4`, dev:
`pytest`+`ruff`+`playwright` — antes dependía del `pyproject.toml` compartido del repo padre).

**Carpeta padre renombrada de `proyecto_cliente_catalina/` a `proyecto_negocio_doscaras/`**
(decisión de Yeisiton, "las dos caras de la moneda" — Inbound/Outbound) — corregidas todas las
rutas absolutas que la referenciaban (`.claude/settings.json` del padre, hooks de Kiro
`.kiro/hooks/*.json`, MCP `.kiro/settings/mcp.json`). Estructura final, 3 repos hermanos, cada
uno con su propio `graphify`: `estudio_skills_ia_claude/` (base de conocimiento/gobernanza,
sin código de producto), `artf-pipeline-app/` (Inbound, ARTF), `outbound-prospector-app/`
(Outbound, TBBC/El Prospector).

**Vault de Obsidian también movido al padre** (`proyecto_negocio_doscaras/.obsidian/`, antes
solo `estudio_skills_ia_claude/.obsidian/`) — Obsidian no le importan los límites de repos git,
un vault es solo un árbol de carpetas, así que ahora el grafo visual/backlinks abarca los 3
repos en vez de solo uno. Plugin de comunidad **Dataview** recomendado (no instalado por
Claude — instalar desde el navegador de plugins de Obsidian mismo) para un dashboard en vivo
consultando frontmatter YAML entre proyectos.

**Graphify instalado en ambos repos** (`estudio_skills_ia_claude/` y `artf-pipeline-app/`,
vía `uv tool install graphifyy[sql]` — incluye soporte de parseo SQL, relevante por el
volumen de migraciones de ARTF). Construye un grafo de conocimiento del código con
tree-sitter (AST, determinístico, sin costo de LLM) + opcionalmente una capa semántica de
LLM (no configurada aún, requiere `GEMINI_API_KEY`/`GOOGLE_API_KEY`). `graphify claude
install` en cada repo escribió la sección `## graphify` en su `CLAUDE.md` (instruye a
Claude a consultar `graphify query`/`graphify explain` ANTES de leer/grepear código crudo,
no después) + un hook `PreToolUse` (`Bash|Grep` y `Read|Glob`) que recuerda esto en cada
intento de búsqueda/lectura — no bloquea, solo orienta. `graphify hook install` dejó un
post-commit/post-checkout que reconstruye el grafo automáticamente (via Husky en
`artf-pipeline-app`, git hooks nativos en `estudio_skills_ia_claude`) — el grafo anterior de
`estudio_skills_ia_claude` estaba desactualizado desde el 26-jul, ya reconstruido (2877
nodos, 7320 edges). `graphify-out/` gitignored en ambos repos (regenerable, no se commitea);
`.gitattributes` con el merge driver de `graphify` sí se commitea.


