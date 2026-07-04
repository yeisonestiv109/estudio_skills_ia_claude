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
- **No aplica a Kiro.** ECC apunta a Claude Code/Cursor/Codex/etc. Para este entorno (Kiro) sirve como **referencia**, no como instalación.

## 3. Cómo lo usamos (recomendación concreta)

1. **Minar sus `rules/common`** para nutrir nuestro steering y un futuro `rules/` propio (sin copiar literal; adaptar a nuestro estilo).
2. **Probar AgentShield** (`npx ecc-agentshield scan`) sobre nuestras configs cuando trabajemos con Claude Code — seguridad de bajo costo.
3. **Adoptar patrones, no el paquete:** memoria persistente, continuous-learning, token-optimization, skills de `api-design`/`backend-patterns`/`cost-aware-llm-pipeline` como **guía de diseño** de nuestro build.
4. **Si algún día instalamos en Claude Code:** perfil **mínimo**, solo `rules/common` + nuestro stack, en entorno reversible (git limpio), revisando hooks. Nunca "apilar" métodos de instalación.

## 4. Encaje con las 3 reglas de oro

- **Ahorra tiempo:** patrones y skills listos aceleran el desarrollo (Vía A y Vía B).
- **Ahorra dinero:** token-optimization + quality/security gates = menos gasto de tokens y menos bugs.
- **Ganar dinero:** indirecto. **No lo vendas como producto**; es tooling interno. (Regla: la IA es vehículo, no producto.)

> **Conclusión:** referencia valiosa y un par de herramientas útiles (AgentShield, rules, token-opt). **Cherry-pick, no adopción total.** Fuente: [README de ECC](https://github.com/affaan-m/ECC) · nota de terceros: [augmentcode](https://www.augmentcode.com/learn/ecc-224k-stars-cross-harness-agent-config).
