# Guía de Arquitectura de Memoria — proyecto_negocio_doscaras

> Meta-documento: cómo construir y mantener sano el sistema de memoria/contexto
> para trabajar con IA en este workspace y en futuros proyectos/negocios de
> Yeisiton. No duplica [`estrategia-memoria.md`](../.kiro/steering/estrategia-memoria.md)
> (protocolo de memoria del código) ni [`directrices_globales.md`](directrices_globales.md)
> (mapa de carpetas del Segundo Cerebro) — este documento es la capa de encima:
> el porqué, la auditoría, y el índice reproducible para otros negocios.

**Auditoría base:** 2026-08-21. Todo hallazgo de la sección 1 fue verificado en
vivo ese día (lectura de archivo, `list_notebooks`/`get_health`/`ask_question`
reales) — no es una suposición.

---

## 0. Resumen ejecutivo

El sistema actual (`estrategia-memoria.md` + `directrices_globales.md` +
Graphify + NotebookLM + `autoMemoryDirectory` bridge) ya implementa la mayoría
de lo que un equipo "senior" haría: jerarquía de verdad explícita, estados
tri-partitos (PROPUESTO/IMPLEMENTADO/HUÉRFANO), protocolo de lectura anti
context-bloat, y memoria de Claude Code ya des-fragmentada entre los 3 repos.
**No hace falta reconstruir nada de esto.** Lo que falta es: (a) purgar 3
skills con rutas muertas que fallarían si se invocan hoy, (b) decidir si el
MCP `memory` (knowledge-graph) se activa de verdad o se retira — hoy está
configurado pero vacío, (c) resolver que el canal de NotebookLM está roto en
lectura ahora mismo (bug confirmado en vivo, no solo documentado), y (d)
cerrar la brecha de cobertura: todo lo que sí está en NotebookLM es de
ARTF/Inbound — Outbound Prospector y el negocio general no tienen memoria
dinámica todavía, solo estática.

---

## 0.1 Estado de resolución (21-ago-2026, misma sesión)

El fundador autorizó ejecución directa tras leer esta auditoría. Estado real de
cada hallazgo — el detalle completo de qué se tocó en cada uno queda en la
sección 1, esto es solo el semáforo:

| # | Hallazgo | Estado |
|---|---|---|
| 1.1 | Rutas muertas en Skills de Kiro | ✅ Corregido — 3 skills + 8 docs adicionales con la misma ruta muerta (`AGENTS.md`, `contexto-proyecto.md`, `estrategia-memoria.md`, `directrices_globales.md`, `03_protocolos_comunicacion.md`, `mvp-prospector-limpio.md`, `02_backlog_y_rocas.md`, citas internas de `outbound-prospector-app/docs/tecnico/`) |
| 1.2 | MCP `memory` vacío | ✅ Retirado — `mcp.json` limpio, `memory-preload` reescrita como aviso de retiro, decisión en `02_backlog_y_rocas.md` y `architecture_ledger.md` Entrada 006 |
| 1.3 | Duplicado en NotebookLM | ✅ Eliminado (`artf-arquitectura-actual-y-rol-1`) |
| 1.4 | Bug #4 de `notebooklm-mcp` | 🟡 Causa raíz encontrada y parcheada localmente (lista de frases ES incompleta + heurística de elipsis no reconocía `…` Unicode). **No verificado en vivo** — el proceso MCP ya corriendo no recarga el parche hasta reiniciar Claude Code. Parche vive solo en el caché `npx` de esta máquina, no es una corrección río arriba |
| 1.5 | `guia_configuracion_memoria_ia.md` obsoleto | ✅ Encabezado de plantilla histórica agregado |
| 1.6 | Cobertura NotebookLM desbalanceada (Outbound sin notebook) | ⏸️ Por diseño — Outbound Prospector confirmado en pausa por el fundador; directriz "Paso 1 al reanudar = notebook" inyectada en `contexto-proyecto.md` y en memoria de Claude |
| 1.7 | Claude memory sin rango en la jerarquía | ✅ Corregido — 6º nivel agregado en `estrategia-memoria.md` §1 |
| — | `02_Lineas_de_Producto/Outbound_Prospector/` (solo caché, cero código real) | ⛔ **Bloqueado por el clasificador de seguridad de Claude Code** (`rm -rf`). Verificado 100% caché (`__pycache__`/`.pytest_cache`/`.ruff_cache`), pendiente de que el fundador lo borre manualmente o reautorice explícitamente |

---

## 1. Auditoría — hallazgos verificados hoy

### 1.1 Rutas muertas en 3 Skills de Kiro

`.kiro/skills/handoff-cierre-sesion/SKILL.md`,
`.kiro/skills/sincronizador-spec/SKILL.md` y
`.kiro/skills/memory-preload/SKILL.md` (indirectamente, vía su dependencia del
Core) asumen textualmente `02_Lineas_de_Producto/Outbound_Prospector/src/...`
como "única línea con código real hoy". Esa ruta ya no existe: el código real
se extrajo a `outbound-prospector-app/` el 20-ago-2026 (ver
`bridge_memory_via_autoMemoryDirectory` en memoria). Si alguien invoca
`handoff-cierre-sesion` o `sincronizador-spec` hoy tal cual están escritas,
apuntan a un directorio vacío/inexistente. Es exactamente la señal de alarma
que la sección 2 de `estrategia-memoria.md` describe ("ruta purgada") aplicada
a un Skill, no a un `.md` de contenido — el protocolo audita docs pero no se
había corrido sobre los Skills mismos.

**Acción:** reescribir las 3 rutas a `outbound-prospector-app/src/...` (repo
hermano, no subcarpeta) y quitar la frase "única línea con código real hoy" —
ya no es cierto, Inbound/ARTF es el frente activo.

### 1.2 MCP `memory` (knowledge-graph) — configurado pero vacío

`.kiro/settings/mcp.json` registra un servidor `memory`
(`@modelcontextprotocol/server-memory`, oficial) apuntando a
`.kiro/memory/prospector-knowledge-graph.json`. La skill `memory-preload` lo
documenta como paso obligatorio antes de tareas complejas. El archivo real
contiene `{}` — 3 bytes, nunca se ha escrito una entidad. Es una capa de
memoria completa, documentada y con guardrails, que hoy no aporta nada porque
nunca se alimentó. Además solapa con lo que Graphify + los `.md` de
`02_Lineas_de_Producto/*/docs/` ya cubren (relaciones código↔spec), y con lo
que la memoria auto-persistente de Claude Code ya cubre (decisiones,
contexto). Tres sistemas de grafo/memoria distintos sin una regla de "cuál
gana" entre ellos es exactamente el tipo de fragmentación que
`bridge_memory_via_autoMemoryDirectory` ya solucionó una vez para otro caso.

**Acción (decisión pendiente del usuario, no ejecutar sin luz verde):**
o (a) se retira el servidor `memory` de `mcp.json` y se borra la skill
`memory-preload` (lo que hace ya lo cubren Graphify + backlog + memoria de
Claude), o (b) se le da un propósito que NINGÚN otro sistema cubre (ej.
relaciones humanas/negocio que no son código ni docs versionados — leads,
contactos, decisiones de clientes) y se empieza a alimentar de verdad. No
dejarlo en este estado intermedio (documentado + configurado + vacío).

### 1.3 Duplicado real en la librería NotebookLM (no en un doc, en el sistema vivo)

`list_notebooks` (ejecutado hoy) devuelve **5** notebooks, no 4. Dos entradas
distintas (`artf-arquitectura-actual-y-rol` agregado 15-ago, y
`artf-arquitectura-actual-y-rol-1` agregado 19-ago) apuntan a la **misma** URL
(`.../e98171ed-cba6-4da6-9dfc-22cf40820a7f`) con descripciones ligeramente
distintas. La limpieza de duplicados del 14-ago-2026 documentada en
`01_entorno_y_operacion.md` sólo cubrió el notebook técnico; este duplicado es
nuevo y no está registrado en ningún `.md`. Con Bug #2 de `cleanup_data`
(borra `library.json` en vez de preservarlo) confirmado, la única forma segura
de arreglarlo es `remove_notebook` sobre el id sobrante (`-1`, menor
`use_count`), no un `cleanup_data`.

### 1.4 Bug #4 de `notebooklm-mcp` confirmado en vivo hoy (3/3), no solo documentado

Se probaron 3 preguntas cortas contra el notebook activo de ARTF
(`ask_question`, sesión `f9757b43`) durante esta auditoría. Las 3 devolvieron
únicamente texto de carga transitorio de NotebookLM ("Descubriendo la idea
principal…", "Verificando el alcance…", "Leyendo tus fuentes…"), nunca la
respuesta real — el mismo bug documentado el 20-ago, reproducido de nuevo hoy
21-ago. **Implicación directa para el objetivo 3 del usuario:** el canal de
lectura/consulta de NotebookLM vía MCP no es confiable *hoy* como fuente
dinámica consultable en vivo desde una sesión de Claude Code. Se puede seguir
alimentando (`add_source` no está afectado por este bug) y usando desde el
navegador manualmente, pero no asumir que un agente puede "preguntarle a
NotebookLM" en este momento y confiar en la respuesta.

### 1.5 Doc obsoleto: `guia_configuracion_memoria_ia.md`

`outbound-prospector-app/docs/guia_configuracion_memoria_ia.md` describe una
estructura de carpetas Obsidian (`00-Contexto/10-Fuentes_Raw/20-Wiki_Conceptos/
40-Sistema/50-Media`) que **no es** la estructura EOS real actual
(`01_Gobernanza_EOS/`, `02_Lineas_de_Producto/`, `03_Clientes_y_Casos/`,
`04_Segundo_Cerebro/`). Es un documento previo a la reestructuración del
13-ago-2026, nunca actualizado ni marcado como histórico. Es exactamente el
patrón de alarma que `estrategia-memoria.md` §2 pide detectar. Sí tiene valor
como plantilla genérica reutilizable para un negocio *nuevo* (objetivo 4 del
usuario) — pero hoy convive sin aviso con la estructura real, lo que puede
confundir a una sesión futura que lo lea primero.

**Acción:** encabezarlo con una nota "PLANTILLA GENÉRICA / NO es la estructura
vigente de este repo — ver `contexto-proyecto.md` para la real" y moverlo
conceptualmente al rol de "punto de partida para otro negocio", no de
documentación activa de este.

### 1.6 Cobertura de NotebookLM desbalanceada

De los notebooks reales: **4 IMPLEMENTADO, todos sobre ARTF/Inbound** (técnico,
negocio/reuniones, UX deep research, setter) + **4 PROPUESTO, cero creados**
(Outbound Prospector, Negocio General, Desarrollo Personal, Mentoría
Javier/Catalina — ver tabla en `directrices_globales.md`). Confirma la
sospecha del usuario: la "memoria dinámica" real hoy vive solo en una rama del
árbol. Outbound Prospector (476/480 tests, código real y maduro) no tiene
ningún notebook — su memoria es 100% estática (`.md` + Graphify).

### 1.7 La jerarquía de verdad no incluye la memoria nativa de Claude Code

`estrategia-memoria.md` §1 define 5 niveles de jerarquía de verdad (código →
backlog → docs de línea → bitácora de decisiones → visión). Ninguno de los 5
es "la memoria auto-persistente de Claude Code"
(`~/.claude/projects/.../memory/*.md`, la que este mismo documento usa para
recordar contexto entre sesiones). Hoy funciona porque el hábito real ya es
"si hay conflicto, corrígase el `.md` del repo" (reforzado por
`feedback_docs_belong_in_repo_not_only_memory`), pero no está escrito como
regla dura en el documento que sí define todo lo demás con precisión
milimétrica. Con 15 archivos y ~125KB en la memoria compartida y creciendo,
vale la pena la única línea que falta.

**Acción:** agregar una fila explícita a la jerarquía: la memoria de Claude
Code es *cache de sesión y bitácora de decisiones no derivables del código*,
nunca fuente de verdad sobre comportamiento del sistema — y si contradice
cualquiera de los 5 niveles existentes, se corrige la memoria, nunca al revés.

---

## 2. Lo que ya está a nivel Senior — no reinventar

- **Jerarquía de verdad explícita y ordenada** (`estrategia-memoria.md` §1) —
  la mayoría de equipos ni siquiera escriben esto; aquí ya resuelve el 90% de
  la "alucinación entre sesiones" porque da una regla de desempate objetiva.
- **Tri-estado PROPUESTO/IMPLEMENTADO/HUÉRFANO** aplicado consistentemente a
  código, decisiones Y notebooks (`directrices_globales.md` reusa el mismo
  concepto en vez de inventar uno nuevo — exactamente la disciplina de "un
  concepto, un lugar" que se predica).
- **Protocolo de lectura anti context-bloat**: backlog primero, luego
  `graphify query` antes que grep/lectura cruda, luego solo el subarchivo
  puntual. Esto es lo que industrias con agentes maduros llaman "progressive
  disclosure" — aquí ya está implementado, no solo aspirado.
- **Bridge de `autoMemoryDirectory`** resolvió una fragmentación real
  (4 archivos huérfanos rescatados) con el mecanismo nativo correcto, sin
  workaround manual — decisión ya validada, no tocar.
- **Un notebook por tema coherente, no por cliente** (regla explícita en
  `directrices_globales.md` §2: "mezclar SQL con mentoría diluye el RAG de
  ambos") — esto es la práctica correcta de chunking temático para RAG y ya
  está aplicada, no solo escrita.
- **Skills reclasificadas de hooks a on-demand** cuando corresponde (24-jul) —
  criterio correcto: evento automático → hook; procedimiento invocado por el
  humano → skill. Evita correr análisis LLM caro en cada save.

---

## 3. Estrategia de industria — evitar alucinación y pérdida de contexto

Lo que hacen los equipos que gestionan bien esto (y cómo se compara con lo que
ya existe aquí):

1. **Un solo árbol de verdad con jerarquía explícita, nunca "la memoria
   completa cargada de golpe".** Ya implementado (§1 de `estrategia-memoria.md`).
   El riesgo real no es la falta de estructura — es el punto 1.7: una fuente
   más (Claude memory) circulando sin rango asignado.
2. **Grafo de código como capa intermedia entre el LLM y el archivo crudo**
   (Graphify aquí) — evita que el modelo tenga que "adivinar" relaciones
   leyendo miles de líneas. Ya implementado en los 3 repos con hooks de
   reconstrucción automática (post-commit/post-checkout).
3. **RAG por documentos vivos y curados, no por PDFs sueltos sin estructura.**
   NotebookLM cumple esto siempre que el input tenga YAML/convención de
   nombre y esté particionado por tema — ya es la regla en
   `docs/notebooklm/README.md`. El gap no es de diseño, es de ejecución: 4 de
   8 notebooks planeados nunca se crearon (§1.6).
4. **Verificación obligatoria antes de escribir memoria** ("antipsicofancia
   al escribir", §3 de `estrategia-memoria.md`) — evita el problema más común
   de que la IA registre como hecho algo que el usuario afirmó pero el código
   contradice. Ya implementado y con ejemplos reales de aplicación (ver
   `feedback_verification_discipline_and_tooling`).
5. **Auditoría periódica del propio sistema de memoria, no solo del código.**
   Este es el gap real: existe un protocolo de auditoría para código↔spec
   (`sincronizador-spec`) y para sesión↔backlog (`handoff-cierre-sesion`),
   pero no había ninguno que auditara Skills/MCP/NotebookLM mismos — por eso
   los hallazgos de §1 llevaban semanas sin detectarse pese a que el sistema
   de detección de drift ya existía para otras capas. **Recomendación
   concreta: agregar un 5º Skill, `auditar-memoria` (mismo patrón que
   `auditar-arquitectura`), que corra trimestral o post-reestructuración.**
6. **Separar memoria de "qué pasó" (bitácora, append-only) de memoria de "qué
   es verdad hoy" (docs, mutable, se corrige in-place).** Ya implementado:
   `02_backlog_y_rocas.md` es append-por-sesión, los docs de línea se
   sobrescriben. Distinción correcta y poco común de ver bien hecha.

---

## 4. Integración NotebookLM — flujo operativo objetivo

**Regla de oro ya vigente, mantener:** 1 notebook = 1 tema coherente, nunca
1:1 forzado con carpeta o cliente. `PROPUESTO` no se crea hasta que llega la
primera fuente real (evita notebooks vacíos acumulando deuda).

**Qué falta para que sea el "cerebro dinámico" que el usuario quiere, en
orden de impacto:**

1. **Resolver el Bug #4 antes de prometer nada dinámico.** Mientras
   `ask_question` devuelva solo texto de carga (confirmado 3/3 hoy), el flujo
   real es: `add_source` sí funciona (alimentar es confiable) → pero la
   consulta desde un agente NO. Fallback mientras tanto: abrir el notebook en
   el navegador manualmente para preguntas que de verdad importan, y no
   depender del MCP para decisiones. Vale la pena revisar si
   `PleasePrompto/notebooklm-mcp` tiene una versión más nueva en npm que ya
   corrija esto (el bug es del cambio de dominio `notebooklm.google.com` →
   `notebook.google.com`, es plausible que ya esté parchado río arriba).
2. **Cerrar los 4 `PROPUESTO`, empezando por Outbound Prospector** (es el que
   tiene más código real sin memoria dinámica). Primer archivo real en
   `outbound-prospector-app/docs/notebooklm/` (convención ya definida:
   `AAAA-MM-DD_tema-corto.md`) dispara la creación del notebook.
3. **Formato de fuente para NotebookLM** (ya implícito en las convenciones
   existentes, hacerlo explícito): cada archivo que entra a un notebook debe
   poder leerse solo, sin contexto externo — NotebookLM no ve las relaciones
   de carpeta del repo, solo el texto de la fuente. Un `.md` que dice "ver
   sección de arriba" falla en RAG; debe ser autocontenido con el contexto
   mínimo repetido si hace falta.
4. **Prompt de recuperación estándar** (para cuando el MCP vuelva a
   responder, o para uso manual en el navegador): preguntar por el CONCEPTO,
   no por "resume el documento" — NotebookLM cita mejor con preguntas
   puntuales ("¿qué política define X?") que con pedidos abiertos. Pedir
   `source_format: "footnotes"` en `ask_question` para verificar que la
   respuesta cita una fuente real antes de confiar en ella (barato, ya
   soportado por la tool, no se está usando).
5. **Deduplicar la librería ahora** (`remove_notebook` sobre
   `artf-arquitectura-actual-y-rol-1`) antes de que el problema crezca con 4
   notebooks nuevos por venir.

---

## 5. Sistema de evaluación — señales de que la memoria está fallando

Métricas concretas, chequeables sin subjetividad, en cascada de más barata a
más cara:

| Señal | Cómo se detecta | Umbral de alarma |
|---|---|---|
| Ruta muerta en un `.md` o Skill | `grep` de rutas viejas conocidas (`02_Lineas_de_Producto/Outbound_Prospector/src`, numeración `00-`/`10-`/`20-`) contra el repo completo | Cualquier match fuera de la bitácora histórica |
| Duplicado en NotebookLM | `list_notebooks`, agrupar por `url` | >1 id con la misma url |
| Notebook `PROPUESTO` envejeciendo | Fecha de la primera fuente real en `docs/notebooklm/` vs. hoy | >30 días sin crear el notebook tras la primera fuente |
| `ask_question` no confiable | 3 preguntas cortas en sesión fresca | 3/3 solo texto de carga → reportar, no reintentar |
| Memoria de Claude Code contradice código | Al tocar un archivo que una memoria describe, comparar antes de escribir | Cualquier discrepancia → memoria se corrige, se documenta el hallazgo |
| Skill con guardrail no verificado en meses | Fecha de última modificación del `SKILL.md` vs. última vez que el código que referencia cambió | Skill más vieja que 2 reestructuraciones de repo |
| Sistema de memoria paralelo sin dueño claro | ¿Hay un archivo con datos (`{}` o vacío) que un doc documenta como "activo"? | Cualquier "configurado pero vacío" (caso §1.2) |
| Tamaño de memoria compartida | `wc -c` sobre `~/.claude/projects/.../memory/*.md` | Un solo archivo >50KB (ya pasa con `artf_formulario_dashboard_status.md`, 83KB) → candidato a partir en subarchivos, mismo principio de poda sináptica que ya rige el repo |

**Cadencia recomendada:** correr la fila 1 y 2 (las más baratas, sin LLM) en
cada `handoff-cierre-sesion`; correr la tabla completa como un Skill nuevo
(`auditar-memoria`, propuesto en §3.5) cada vez que se cierre una
reestructuración grande de carpetas — es exactamente el tipo de evento que
generó los 7 hallazgos de §1.

---

## 6. Índice del Meta-Manual (borrador)

*"Cómo construir sistemas de memoria reproducibles para proyectos impulsados
por IA" — para usar como plantilla en el próximo negocio/proyecto de
Yeisiton, no solo en este.*

1. **Por qué esto importa** — el costo real de la fragmentación de contexto
   (caso real: 4 archivos huérfanos por 5+ semanas, este mismo workspace).
2. **La jerarquía de verdad** — cómo definir qué gana en un conflicto antes
   de escribir una sola nota (código > operación activa > contratos/diseño >
   historial de decisiones > visión — adaptar niveles al dominio).
3. **Memoria de sesión (agente) vs. memoria de repo (equipo) vs. memoria
   externa (RAG/NotebookLM)** — qué vive en cada una y la regla de que nunca
   se contradicen sin que una se corrija.
4. **El patrón tri-estado** (PROPUESTO/IMPLEMENTADO/HUÉRFANO) aplicado a
   código, decisiones y fuentes de RAG por igual.
5. **Grafo de código como capa intermedia** (Graphify u homólogo) — cuándo
   vale la pena vs. cuándo es sobre-ingeniería para el tamaño del proyecto.
6. **Diseño de notebooks/RAG por tema coherente**, no por carpeta — patrón de
   nombrado de fuentes, cuándo crear un notebook nuevo vs. añadir a uno
   existente.
7. **Protocolo de lectura** (progressive disclosure: índice ligero → grafo →
   archivo puntual) y **protocolo de escritura** (verificar antes de
   afirmar, un concepto un lugar, append-only para bitácora / mutable para
   estado).
8. **Bootstrap en un proyecto nuevo** — checklist de los primeros 5 archivos
   a crear (`CLAUDE.md`/steering, índice de contexto, backlog append-only,
   `.gitignore` de credenciales, `autoMemoryDirectory` si hay repos hermanos)
   antes de escribir la primera línea de código de negocio.
9. **Auditoría periódica del propio sistema** (el Skill `auditar-memoria`,
   la tabla de señales de la sección 5 de este documento) — el punto que
   faltaba aquí y motivó esta auditoría.
10. **Casos reales de este workspace** (apéndice, con fecha) — cada
    hallazgo real sirve de ejemplo para no repetir el mismo error en el
    próximo proyecto.

*(Cuerpo completo: pendiente, a llenar de a uno cuando cada sección tenga un
caso real que la sustente — misma regla anti-genérico que rige el resto de
este workspace: no se documenta lo que no se ha verificado.)*
