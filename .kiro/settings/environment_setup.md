# Cabina de Mando — Configuración del Entorno AI-Native (Kiro + MCP)

---
*   **Proyecto:** El Prospector Greenfield Build
*   **Fecha de Creación:** 7 de Julio de 2026
*   **Autoría:** Yeison Estiven Delgado Ordoñez (Fundador)
---

> Documento de **configuración del entorno**, no de código de producto. Define cómo Kiro (Claude Opus 4.8)
> opera como agente AI-Native para TBBC: autónomo, documentado en tiempo real y con control de costos.
> Correcciones de diseño ya validadas se aplican aquí (context7 reubicado, Skills/Hooks nativos, límite de turnos).

---

## ETAPA 1 — Naturaleza y fundamentos del pipeline de prospección

### 1.1 Qué es prospectar bien (la tesis)
La prospección B2B de alto valor **replica a un SDR de élite**, no a un enviador masivo de correos. El flujo real
es: detectar una **señal de cambio** (trigger) → mapear al decisor correcto → contactar con un gancho de valor
personalizado. El foso competitivo es **precisión + personalización basada en valor**, nunca el volumen.

### 1.2 Ineficiencias de la competencia tradicional (lo que NO haremos)
| Ineficiencia | Qué es | Consecuencia |
|---|---|---|
| **Data decay** | Bases estáticas que envejecen: cargos que rotaron, correos que rebotan, empresas que cambiaron | Se prospecta a contactos inexistentes; se quema reputación de dominio |
| **Saturación de canales** | Secuencias genéricas masivas al mismo pool de decisores | Fatiga del prospecto, filtros de spam, tasa de respuesta que colapsa |
| **Volumen sobre criterio** | Miles de correos sin trigger real | Alto costo de APIs, cero personalización, rechazo |
| **GIGO (garbage in, garbage out)** | ICP mal definido → raspado de empresas equivocadas | Enriquecimiento caro de leads inútiles |

### 1.3 Cómo nuestra configuración técnica mitiga esas ineficiencias
- **Contra data decay:** triggers *fechados* (con `trigger_date_confidence`) y validación de vigencia; señales
  de contratación/technográficas (frescas por naturaleza) en vez de listas estáticas. (Ver diseño M2 en
  [`../../docs/tecnico/prospector-m1-m2-design.md`](../../docs/tecnico/prospector-m1-m2-design.md).)
- **Contra saturación:** outbound con "sabor inbound" (lead magnet de valor) y RAG de estilo, no plantillas.
- **Contra volumen sin criterio:** cascada barato→caro con **frontera de costo** (HITL antes de enriquecer).
- **Contra GIGO:** filtro de especificidad de ICP en M1 que **bloquea** el avance si el ICP es vago.

---

## ETAPA 2 — Acciones de configuración consolidadas en el entorno

Kiro trae **de forma nativa** Steering, Skills, Hooks y compactación de conversación. La estrategia NO es
construir infraestructura, sino **orquestar lo nativo + los MCP**. Fuentes: docs oficiales de Kiro
([Hooks](https://kiro.dev/docs/hooks/), [Skills](https://kiro.dev/docs/skills/), [Steering](https://kiro.dev/docs/steering/)).
*Contenido reformulado por cumplimiento de licencias.*

### 2.1 Capas de conocimiento (anti data-decay del prompt)
| Capa | Mecanismo | Rol | Peso en contexto |
|---|---|---|---|
| Permanente | **Steering** (`.kiro/steering/`) | 3 reglas de oro, reglas del juego, diseño hexagonal | Siempre (mínimo) |
| Bajo demanda | **Skills** (`.kiro/skills/`) | `auditar-arquitectura`, `diseno-hexagonal` | Solo al activarse |
| Sesiones largas | **Compactación nativa** | Comprime historial sin perder lo esencial | Automático |
| Entre sesiones | **Memory MCP** (a agregar) | Knowledge-graph persistente del Prospector | Consulta en pre-prompt |
| Docs de librerías | **context7** (pausado) | APIs version-específicas para fase de código | Solo al codificar |

### 2.2 Corrección crítica sobre `context7`
`context7` **NO es memoria entre sesiones**. Es un recuperador de *documentación viva de librerías* (Upstash)
que inyecta APIs actualizadas para no alucinar versiones ([Upstash — Context7](https://upstash.com/blog/context7-mcp)).
Queda **pausado** y reservado para la futura fase de código (FastAPI, PydanticAI, Next.js). La persistencia
semántica entre sesiones la cubre un **Memory MCP (knowledge-graph)**, no context7.

### 2.3 Orquestación de MCP (estado objetivo)
| MCP | Estado | Función en la Cabina de Mando |
|---|---|---|
| `google-sheets` | ✅ Activo | Motor del ledger dual (decisiones + costos), append-only |
| `Memory (knowledge-graph)` | ➕ Agregar | Persistencia semántica entre sesiones; se consulta antes de tareas complejas |
| `context7` | ⏸️ Pausado | Docs vivas de librerías — se reactiva en la fase de desarrollo de código |

Config → [`mcp.json`](mcp.json). Skills → [`../skills/`](../skills/). Hooks → [`../hooks/`](../hooks/).

### 2.4 Hooks configurados (resumen; detalle en `.kiro/hooks/`)
1. **`cerrar-decision` (post-prompt, manual):** al invocar `/cerrar-decision`, registra append-only en el
   Google Sheet (fecha, módulo, tipo, conclusión, fuentes).
2. **`cost-audit` (post-tarea):** captura tokens de input/output/reasoning y los escribe en la pestaña
   `cost_ledger`, con un **circuit breaker** que alerta si la tarea supera el presupuesto.
3. **`memory-preload` (pre-prompt):** antes de una tarea compleja, consulta el Memory MCP para no trabajar a ciegas.

---

## ETAPA 3 — Conclusiones de viabilidad técnica y operativa

### 3.1 Viabilidad técnica
- **Alta.** Todo se apoya en primitivas nativas de Kiro (Steering/Skills/Hooks/compactación) + MCP estándar.
  No se construye infraestructura nueva; se configura la existente. Riesgo de implementación: bajo.
- **Dependencia externa acotada:** solo el Memory MCP es nuevo por instalar; `google-sheets` ya está autorizado.

### 3.2 Viabilidad operativa (ROI de tokens)
- El costo dominante en Opus 4.8 es **output + reasoning**; el contexto es "peso" que se re-lee cada turno.
  Métricas de industria 2026: los tokens crecen cuadráticamente por turno y un loop de 20 pasos puede consumir
  >10x lo estimado ([arXiv 2510.16786](https://arxiv.org/html/2510.16786v2); [Augment Code](https://www.augmentcode.com/guides/ai-agent-loop-token-cost-context-constraints)).
- **Mitigación adoptada (directrices de loops autónomos):**
  1. **Límite dinámico de turnos** en torno al **percentil 75** del baseline (recorta costo 24–68% con impacto
     mínimo en resolución); extender turnos solo bajo demanda cuando la tarea lo justifique.
  2. **Patrón coordinador-especialista:** delegar sub-tareas a sub-agentes con contexto acotado en vez de un
     único loop que arrastra todo el historial.
  3. **Checkpoints HITL estrictos:** ningún loop desatendido cierra sin verificación humana — "un loop sin
     verificador despacha bugs con confianza" ([TechTimes](https://www.techtimes.com/articles/318828/20260622/claude-code-loop-engineering-stop-prompting-start-designing-autonomous-agent-workflows.htm)).
  4. **Reset de estado entre tareas no relacionadas** para evitar context bloat.
- **Control financiero:** el hook `cost-audit` + circuit breaker convierten el gasto en una métrica vigilada
  (costo por decisión validada), coherente con la regla de oro "medir el dinero por unidad".

### 3.3 Los 3 errores críticos a eliminar en diseño
1. **Loops autónomos sin verificador** → costo compuesto + bugs confiados. *Fix:* límite de turnos + HITL.
2. **Context bloat** (el agente re-lee todo cada turno; ~80% de tokens se va en "buscar") → *Fix:* Steering para
   lo permanente, Skills bajo demanda, compactación, reset de estado.
3. **Confundir "más contexto/MCP" con "mejor resultado"** (ej. asignar context7 a memoria) → *Fix:* cada
   componente justifica su lugar con función medible; si no reduce fricción o costo, no entra.

### 3.4 Veredicto
La Cabina de Mando es **viable y lista para operar**: mitiga data decay y saturación por diseño, documenta sin
fricción vía Hooks + Google Sheets, y controla el costo de un modelo de alta capacidad con límites de turno y
verificación humana. Próximo paso operativo: autorizar el **Memory MCP** y activar los tres Hooks.
