# Evaluación de ECC ("Everything Claude Code") — ¿nos sirve?

> Análisis del repo [github.com/affaan-m/ECC](https://github.com/affaan-m/ECC) que el fundador encontró y quiere evaluar para nuestros desarrollos. Fecha: **4-jul-2026**. *Contenido de fuentes externas reformulado para cumplir licencias; se citan enlaces.*

## 1. Qué es (de dónde nace, para qué sirve, qué hace)

- **Autor:** Affaan Mustafa (@affaan-m). Nace de ~10 meses de uso intensivo diario configurando agentes de código; ganó un hackathon de Anthropic.
- **Qué es:** un "sistema operativo para harnesses de agentes" — una colección grande de configuración y tooling para **agentes de código de IA**: Claude Code (nativo), Cursor, Codex, OpenCode, Gemini, Copilot, Antigravity, Zed.
- **Licencia:** **MIT** (libre de usar/modificar). Alrededor hay monetización: ECC Pro ($19/seat/mes), sponsors, GitHub App.
- **Qué trae:**
  - **Agents** (~67): definiciones de subagentes (planner, architect, code-reviewer, security-reviewer, reviewers por lenguaje).
  - **Skills** (~277): flujos de trabajo (TDD, security-review, `api-design`, `backend-patterns`, `deployment-patterns`, `docker-patterns`, `cost-aware-llm-pipeline`, `mcp-server-patterns`, etc.).
  - **Rules**: guías siempre-activas (coding-style, git-workflow, testing con 80% cobertura, security) comunes + por lenguaje.
  - **Hooks**: automatizaciones por evento (detección de secretos en prompts, auto-format, typecheck, guardas de comandos destructivos, **persistencia de memoria de sesión**).
  - **AgentShield**: escáner de seguridad de *tus propias* configs de agente (`npx ecc-agentshield scan`).
  - **Continuous learning / instincts**: extrae patrones de tus sesiones y los vuelve skills reutilizables.
  - **Token optimization**: settings para bajar costo (sonnet por defecto, límites de thinking, compactación).

## 2. Veredicto crítico (antipsicofancia)

**Sí sirve, pero como fuente de patrones y herramientas puntuales — NO para adoptarlo entero.** Razones:

### 🟢 Lo genuinamente valioso para nosotros
- **`rules/common`** (coding-style, testing 80%, security, git-workflow): excelente insumo para redactar **nuestras propias reglas/steering**.
- **AgentShield**: auditar nuestras configs de Claude Code/agentes es útil y de bajo compromiso (paquete npm suelto).
- **Patrón de memoria persistente + instincts**: refuerza y valida nuestro **Hack de Memoria Modular**.
- **Skills concretas** aplicables a nuestro build: `cost-aware-llm-pipeline`, `api-design`, `backend-patterns`, `tdd-workflow`, `deployment-patterns`, `security-review`.
- **Token optimization**: ahorro real de costo en Claude Code.

### 🔴 Señales de alerta / cautelas
- **La cifra de "211.9K estrellas" es sospechosa:** se muestra con un **badge propio (`api.ecc.tools`)**, no con el badge estándar de GitHub. Sería de los repos más estrellados de la historia; **trátalo con escepticismo**. (La sustancia del repo es útil **independientemente** del número.)
- **Fuerte monetización** (Pro, sponsors, GitHub App) alrededor de un core MIT. Nada malo, pero explica el marketing agresivo.
- **Instalación invasiva:** modifica `~/.claude` globalmente y **corre hooks/scripts**. Su propio README advierte usar **solo fuentes oficiales** (riesgo de malware en mirrors). → revisar hooks antes de habilitarlos.
- **Bloat de contexto:** 277 skills / 67 agents. Adoptarlo entero **satura el contexto** (ellos mismos advierten que demasiados MCP se comen la ventana). Instalar **selectivo**.
- **Es la config opinada de un solo autor**, no un estándar de industria.

## 2.b Corrección: ECC SÍ tiene adaptador nativo para Kiro

En el análisis anterior dije "no aplica a Kiro". **Me corrijo:** ECC incluye un adaptador **`.kiro/`** instalable en cualquier proyecto Kiro con `./install.sh` (copia **no destructiva**, no sobreescribe tus archivos). Inventario del adaptador Kiro:

- **33 agentes** (JSON para CLI + MD para IDE): `planner`, `architect`, `code-reviewer`, `security-reviewer`, `python-reviewer`, `database-reviewer`, `performance-optimizer`, `refactor-cleaner`, `doc-updater`, `build-error-resolver`, etc.
- **43 skills**: `fastapi-patterns`, `backend-patterns`, `api-design`, `postgres-patterns`, `database-migrations`, `security-review`, `tdd-workflow`, `verification-loop`, `deployment-patterns`, `docker-patterns`, `agentic-engineering`, `autonomous-loops`, `deep-research`, `strategic-compact`, `python-patterns`/`-testing`, etc.
- **22 steering files** (auto: `coding-style`, `security`, `testing`, `git-workflow`, `patterns`, `performance`, `lessons-learned`; fileMatch por lenguaje; manual: `dev/review/research-mode`).
- **13 IDE hooks** (`.kiro.hook`): `quality-gate`, `typecheck-on-edit`, `tdd-reminder`, `security-check-on-create`, `python-lint-on-edit`, `extract-patterns`, `session-summary`, `git-push-review`, etc.
- **2 scripts** (`quality-gate.sh`, `format.sh`) + `mcp.json.example`.

### Qué cherry-pickear del adaptador Kiro (para NUESTRO stack Python/backend)

- **Steering:** `coding-style`, `security`, `testing`, `git-workflow`, `patterns`, `performance` como base para pulir los nuestros (adaptar, no copiar ciego).
- **Skills:** `fastapi-patterns`, `backend-patterns`, `api-design`, `postgres-patterns`, `database-migrations`, `security-review`, `tdd-workflow`, `verification-loop`, `deployment-patterns`, `docker-patterns`, `agentic-engineering`, `autonomous-loops`, `deep-research`.
- **Agentes:** `planner`, `architect`, `python-reviewer`, `database-reviewer`, `security-reviewer`, `performance-optimizer`.
- **Hooks:** `quality-gate`, `python-lint-on-edit`, `security-check-on-create`, `extract-patterns` (ver [guía práctica de Kiro](kiro-guia-practica.md) §3).

> **Cómo instalarlo con criterio:** clonar ECC, `cd .kiro && ./install.sh /ruta/proyecto`, y **revisar/podar** lo que no usemos (evitar bloat de 43 skills + 33 agentes). Revisar los hooks/scripts antes de habilitarlos (corren comandos). Es copia no destructiva, pero igual **instalar selectivo**.

## 3. Cómo lo usamos (recomendación concreta)

1. **Minar sus `rules/common`** para nutrir nuestro steering y un futuro `rules/` propio (sin copiar literal; adaptar a nuestro estilo).
2. **Probar AgentShield** (`npx ecc-agentshield scan`) sobre nuestras configs cuando trabajemos con Claude Code — seguridad de bajo costo.
3. **Adoptar patrones, no el paquete:** memoria persistente, continuous-learning, token-optimization, skills de `api-design`/`backend-patterns`/`cost-aware-llm-pipeline` como **guía de diseño** de nuestro build.
4. **Si algún día instalamos en Claude Code:** perfil **mínimo**, solo `rules/common` + nuestro stack, en entorno reversible (git limpio), revisando hooks. Nunca "apilar" métodos de instalación.

## 4. Encaje con las 3 reglas de oro

- **Ahorra tiempo:** patrones y skills listos aceleran el desarrollo.
- **Ahorra dinero:** token-optimization + quality/security gates = menos gasto de tokens y menos bugs.
- **Ganar dinero:** indirecto. **No lo vendas como producto**; es tooling interno. (Regla: la IA es vehículo, no producto.)

> **Conclusión:** referencia valiosa y un par de herramientas útiles (AgentShield, rules, token-opt). **Cherry-pick, no adopción total.** Fuente: [README de ECC](https://github.com/affaan-m/ECC) · nota de terceros: [augmentcode](https://www.augmentcode.com/learn/ecc-224k-stars-cross-harness-agent-config).
