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


