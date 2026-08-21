<!--
================================================================================
 ARCHITECTURE LEDGER — El Prospector
================================================================================
 Autoría / Fundador : Yeison Estiven Delgado Ordoñez
 Proyecto           : El Prospector —  Greenfield Build
 Inicio del ledger  : 7-jul-2026
 Naturaleza         : Documento histórico APPEND-ONLY. No se reescriben entradas
                      previas; solo se añaden nuevas al final.
 Formato por entrada: 3 etapas → (1) Investigación · (2) Acción Consolidada ·
                      (3) Conclusión de Diseño (máx. 3 líneas: Verbo+Objeto+Razón).
================================================================================
 Metáforas de control:
  • Etapa 1 (río)   : rastreamos el origen del agua para que no arrastre sedimentos.
  • Etapa 2 (dique) : compuerta que detiene el flujo de costos antes de las APIs de pago.
  • Etapa 3 (faro)  : veredicto sintético que alimenta hooks de telemetría → Sheets.
================================================================================
-->

# Architecture Ledger — El Prospector

> Registro histórico append-only de decisiones de arquitectura. Cada entrada sigue
> el formato de tres etapas. **No editar entradas pasadas; solo añadir al final.**

---

## Entrada 001 — Validación de la Cabina de Mando (fase DX)

- **Fecha:** 7-jul-2026
- **Rama Git:** `feature/arquitectura-prospector`
- **Autor:** Yeison Estiven Delgado Ordoñez

### Etapa 1 · Investigación
Se auditó el entorno local de Kiro IDE antes de diseñar M3/M4: (a) tronco Git y
ramas, (b) integridad de la purga greenfield (rastreo de referencias a canales 
Workana/Etsy), (c) validez sintáctica de `~/.kiro/settings/mcp.json` y estado de los
servidores MCP (`Memory MCP`, `google-sheets`). El río se rastreó hasta su origen: las
referencias residuales resultaron ser documentación histórica, un `GOOGLE_PROJECT_ID`
de configuración y una rama en el historial de git — no archivos físicos a purgar.

### Etapa 2 · Acción Consolidada
Se estableció este `architecture_ledger.md` append-only como dique documental único
del build greenfield. No se ejecutaron borrados (no existen residuos físicos) ni se
alteró la config MCP sin confirmación, preservando la reversibilidad del entorno.

### Etapa 3 · Conclusión de Diseño
Consolidar ledger append-only para trazar decisiones sin cuello de botella manual.
Aislar discrepancias de entorno (Memory MCP ausente, ruta de credenciales no-Windows)
para resolución explícita antes de M3/M4.

---

## Entrada 002 — Diseño de Módulos 3 (Pre-CRM / Anti-Basura) y 4 (Outbound RAG · Voz de Oro)

- **Fecha:** 7-jul-2026
- **Rama Git:** `feature/arquitectura-prospector`
- **Autor:** Yeison Estiven Delgado Ordoñez
- **Artefacto:** `docs/tecnico/prospector-m3-m4-design.md`

### Etapa 1 · Investigación
Se rastreó el río aguas arriba desde M1/M2: la data de vacantes (TheirStack/Get on Board) es el trigger
más caro de producir y la resolución de email corporativo en PYME tech colombiana es el eslabón que más
falla (data decay ~2.1%/mes; entregabilidad Google/Yahoo con umbral de spam 0.3%). Para M4 se analizó
el patrón RAG few-shot dinámico (pgvector sobre Supabase) como vía para clonar la voz de oro del fundador
sin hardcodear estilo, y las limitaciones de los correos plantilla genéricos (respuesta 3–5%).

### Etapa 2 · Acción Consolidada
Se resolvió: (a) M3 persiste `DecisionMaker` 1:N con `Company` con email nullable, un `CrmSanitationEngine`
determinista (costo cero) y un Kanban donde `CONTACTO_PENDIENTE_MANUAL` es estado de primera clase que
antepone el trigger al hueco del email; (b) M4 usa `GoldVoiceCorpusPort`/`EmbeddingPort`/`EmailGeneratorPort`
con `EmailConstraintValidator` en el Core que impone por código 120 palabras, 3 párrafos, CTA de activo
gratis y cero saludos de IA; (c) se añade una segunda compuerta HITL de envío. El Core no se modificó:
todo entró como puertos, adaptadores y policies nuevas (Open/Closed).

### Etapa 3 · Conclusión de Diseño
Persistir decisores con email opcional para no descartar triggers válidos por el dato más barato.
Clonar la voz de oro vía RAG few-shot por afinidad de sector para elevar la tasa de respuesta.
Blindar la salida del LLM con validador determinista y HITL de envío para proteger dominio y margen.

---

## Entrada 003 — Integración MCP Google Docs y consolidación del Libro Maestro

- **Fecha:** 7-jul-2026
- **Rama Git:** `feature/arquitectura-prospector`
- **Autor:** Yeison Estiven Delgado Ordoñez
- **Destino:** Google Doc "Sistema de Prospeccion para Catalina Rua" (`1b0indKB_YNDmPZ-mPlbGBBSbynNosePymbXS7ffVJZg`)

### Etapa 1 · Investigación
Se validó vía README oficial el servidor `@a-bonus/google-docs-mcp` (MIT, activo, cubre Docs/Sheets/Drive/Gmail/Calendar). Se confirmó que autentica con OAuth Client ID/Secret (Desktop app) y comando `npx -y @a-bonus/google-docs-mcp auth`, distinto del service-account de Sheets. Se probó la conexión con una lectura real del Doc destino y se leyó el borrador inicial existente (planteamiento + M1/M2, con un bloque de pseudocódigo mal formateado).

### Etapa 2 · Acción Consolidada
Se integró el servidor en `mcp.json` (disabled hasta cargar credenciales, autoApprove solo de lectura; backup en mcp.json.bak2). Se adoptó estrategia template-driven (markdown puro, sin fuentes) y se complementó el Doc con una "Parte II" (M1–M4, incluyendo los nuevos M3/M4) vía appendMarkdown, sin sobrescribir el borrador del fundador.

### Etapa 3 · Conclusión de Diseño
Integrar Google Docs MCP para centralizar documentación sin fricción de estilo.
Complementar el borrador con la spec M1–M4 preservando la voz del fundador.
Mantener credenciales fuera de git y escritura no destructiva para proteger el activo documental.

---

## Entrada 004 — Reescritura total y unificación del Libro Maestro en Google Docs

- **Fecha:** 7-jul-2026
- **Rama Git:** `feature/arquitectura-prospector`
- **Autor:** Yeison Estiven Delgado Ordoñez
- **Destino:** Google Doc "Sistema de Prospeccion para Catalina Rua" (`1b0indKB_YNDmPZ-mPlbGBBSbynNosePymbXS7ffVJZg`)
- **Backup:** `docs/tecnico/backups/libro-maestro-gdoc_backup_2026-07-07.md` + historial de versiones de Google

### Etapa 1 · Investigación
Se corroboró de forma independiente el umbral de spam 0.3% de Google/Yahoo (obligatorio desde feb-2024,
estándar estricto 2026, objetivo recomendado <0.1%) vía documentación oficial de Google y guías 2026. Se
investigaron competidores cercanos no nombrados y se validaron para 2026: Instantly y Smartlead (cold email
por volumen, tarifa plana), Amplemarket (sales engagement integral) y 11x.ai (SDR autónomo sin HITL, caja negra).

### Etapa 2 · Acción Consolidada
Se respaldó el contenido previo y se ejecutó una reescritura destructiva autorizada con
replaceDocumentWithMarkdown: un único libro maestro de 7 capítulos (misión, marco híbrido, competencia,
hexagonal, motor M1–M4, gobernanza/telemetría, citas). Se eliminaron el bloque de pseudocódigo mal formateado
y las divisiones "Parte I/II"; los contratos se expresaron en prosa. Los valores de pricing se marcaron como
parámetros internos de gobernanza, no como tarifa oficial verificable.

### Etapa 3 · Conclusión de Diseño
Unificar la documentación en un Google Doc formal, fluido y citado para uso ejecutivo.
Corroborar datos duros (0.3% spam) y ampliar el análisis competitivo con fuentes 2026.
Preservar rollback (backup local + historial de versiones) ante la operación destructiva.

---

## Entrada 005 — Auditoría crítica de Motores 1 y 2, y automatización de descubrimiento de mercado

- **Fecha:** 9-jul-2026
- **Rama Git:** `feature/arquitectura-prospector`
- **Autor:** Yeison Estiven Delgado Ordoñez
- **Destino:** Google Doc "Sistema de Prospeccion para Catalina Rua" (Pestaña: Desarrollo tecnico)

### Etapa 1 · Investigación
Se analizó la vulnerabilidad del Motor 2 frente a "Ghost Jobs" (27-30% del mercado) y la volatilidad del Data Decay tecnológico (30-70% anual). Adicionalmente, se investigaron patrones no tradicionales de abasto de software: contrataciones clave (Líderes de transformación), Tech Stack Signals (herramientas EOL o ausentes), y Expansión/Cumplimiento (M&A, nuevas leyes). Se exploró la automatización de estos patrones vía fuentes RSS y APIs.

### Etapa 2 · Acción Consolidada
Se ejecutó el volcado exitoso al MCP de Google Docs (pestaña "Desarrollo tecnico") del Informe Maestro de Ingeniería. Se consolidó la arquitectura con: guardrail determinista de doble verificación para vacantes >30 días, inyección de `ScoringPolicy` para mitigar volatilidad macroeconómica, y blindaje DDD en el repositorio (devolviendo la entidad `RegistroInteraccionExitosa` en lugar de strings crudos).

### Etapa 3 · Conclusión de Diseño
Implementar validación cruzada obligatoria (antigüedad + señal technográfica/escala) para triggers.
Delegar los pesos de evaluación a políticas inyectables (ScoringPolicy) para asegurar adaptabilidad.
Corregir tipados de Pydantic v2 (fecha_captura, ultima_verificacion) para control riguroso de obsolescencia.

---

## Entrada 006 — Cierre del Memory MCP flaggeado en la Entrada 001

- **Fecha:** 21-ago-2026
- **Rama Git:** N/A (repo de gobernanza, sin código de producto)
- **Autor:** Yeison Estiven Delgado Ordoñez (ejecutado por Claude Code, auditoría de memoria)

### Etapa 1 · Investigación
La Entrada 001 (7-jul-2026) validó el estado de `Memory MCP` y `google-sheets` al arrancar el proyecto, sin auditar después si se usaban de verdad. La auditoría del 21-ago-2026 encontró que `Memory MCP` (`@modelcontextprotocol/server-memory`, grafo en `.kiro/memory/prospector-knowledge-graph.json`) seguía configurado y documentado (`memory-preload` skill) pero el archivo del grafo era `{}` — nunca se escribió una sola entidad en más de un mes de uso del proyecto.

### Etapa 2 · Acción Consolidada
Se retiró `memory` de `.kiro/settings/mcp.json` (mismo criterio que el retiro del `decision_ledger` de Google Sheets, 24-jul-2026: la trazabilidad vive 100% en el repo). `memory-preload/SKILL.md` se reescribió como aviso de retiro con el contenido original conservado como referencia histórica; `cerrar-decision/SKILL.md` ya no referencia el MCP en su paso opcional.

### Etapa 3 · Conclusión de Diseño
No mantener infraestructura configurada "por si acaso" sin un problema de negocio real detrás — coherente con "Lo Aburrido es Oro" (`04_Segundo_Cerebro/directrices_globales.md`).
Si aparece un caso de uso real que Graphify + los `.md` del repo no cubran, evaluarlo desde cero con el caso de uso concreto documentado primero, no reactivar esta configuración a ciegas.
Detalle completo de la auditoría → `04_Segundo_Cerebro/guia_arquitectura_memoria.md`.

---

## Entrada 007 — Visión estratégica: orquestación Kiro + Antigravity (PROPUESTO)

- **Fecha:** 21-ago-2026
- **Rama Git:** N/A (decisión de arquitectura, sin código de producto todavía)
- **Autor:** Yeison Estiven Delgado Ordoñez

### Etapa 1 · Investigación
Durante la auditoría de memoria del 21-ago se confirmó que las carpetas `.kiro/`
(presentes en los 3 repos) y `.agents/` (Antigravity, en `estudio_skills_ia_claude/`)
se mantienen deliberadamente, no por inercia: el fundador ya tiene decidido que en
el futuro ambas herramientas se integrarán y trabajarán en conjunto con Claude Code,
cada una explotada por su fortaleza real. Precedente ya validado y en uso: la
decisión de adopción de Antigravity CLI (`agy`) para 3 casos de uso concretos
(auditoría masiva, triage de incidentes, segunda opinión/revisión cruzada) —
memoria `antigravity_cli_adoption_decision`, audio permanece en NotebookLM.

### Etapa 2 · Acción Consolidada
Ninguna todavía — es una declaración de intención estratégica, no una integración
técnica. Se documenta ahora para que sesiones futuras (de Kiro, de Antigravity, o
de Claude Code) no reinventen el criterio de reparto ni asuman que una herramienta
reemplaza a la otra.

### Etapa 3 · Conclusión de Diseño
**Principio de reparto (a refinar cuando se ejecute, "en el momento oportuno" —
palabras del fundador, sin fecha fijada):**
- **Kiro** — IDE de registro de este workspace: specs, steering (`.kiro/steering/`,
  carga automática), hooks de evento, skills on-demand. Su fortaleza es el trabajo
  spec-driven, nativo del repo, donde reglas de largo plazo deben cargarse solas en
  cada sesión sin que el humano las repita.
- **Antigravity CLI (`agy`)** — agente de Google, ya validado para auditoría masiva,
  triage de incidentes y segunda opinión/revisión cruzada sobre el trabajo de
  Claude. Su fortaleza es actuar como verificador independiente (otro modelo, otro
  ángulo) y absorber volumen que no necesita el contexto profundo de una sesión de
  Claude Code.
- **Claude Code** — orquestador de la mayoría del desarrollo profundo y de esta
  misma auditoría de memoria.
- **Regla dura, no negociable:** ninguna herramienta se usa "a medias". No se
  delega a una tarea que la otra resuelve mejor solo por comodidad — cada
  integración futura debe justificar explícitamente por qué esa herramienta y no
  otra, mismo criterio anti-bazuca que ya rige el resto del proyecto.
- **Pendiente real (no inventar hasta que se decida):** no existe todavía una matriz
  de enrutamiento tarea→herramienta ni una integración técnica entre Kiro/Antigravity
  y la memoria compartida de este workspace. Cuando se ejecute, debe pasar primero
  por `estrategia-memoria.md`/`guia_arquitectura_memoria.md` para que ambas
  herramientas hereden la misma jerarquía de verdad, no una paralela.
