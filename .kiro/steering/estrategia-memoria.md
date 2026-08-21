---
inclusion: always
---

# Estrategia de Memoria — Protocolo Anti-Confusión (El Prospector)

> Por qué existe este archivo: en la auditoría del 24-jul-2026 se encontraron 3
> clases de confusión repetidas: (a) memoria que afirmaba tareas como pendientes
> cuando el código ya las tenía hechas (y viceversa), (b) links a carpetas que
> ya no existen, y (c) documentación que describía diseño que el código nunca
> materializó (`ScoringPolicy`, `industry_mapping` huérfano). Este protocolo
> evita repetirlas. **Es de lectura obligatoria antes de leer o escribir
> cualquier archivo de memoria.**
>
> ⚠️ **Nota (13-ago-2026):** el repo se reestructuró de la numeración plana
> (`00-`/`01-`/`02-`/`10-`/`20-`) al esquema EOS actual (`01_Gobernanza_EOS/`,
> `02_Lineas_de_Producto/`, `03_Clientes_y_Casos/`). Este documento ya refleja
> las rutas nuevas.

## 1. Jerarquía de verdad (qué le gana a qué en un conflicto)

Cuando dos fuentes se contradicen, gana la de MÁS arriba. Sin excepción.

1. **El código ejecutable + los tests en verde** (`src/`, `tests/` dentro de cada
   línea de producto en `02_Lineas_de_Producto/`). Es la única verdad sobre QUÉ
   HACE el sistema hoy. Si la memoria dice X y el código dice Y, **el código
   gana** y la memoria se corrige (nunca al revés).
2. **`01_Gobernanza_EOS/02_backlog_y_rocas.md`** — verdad sobre EN QUÉ VAMOS hoy
   (handoff, última sesión, objetivo próximo — sección "🔜 PRÓXIMO PASO" y el
   historial de sesiones encima de ella). Se lee SIEMPRE primero.
3. **`02_Lineas_de_Producto/<Linea>/docs/`** — verdad sobre los CONTRATOS y flujos
   de diseño (ej. `Inbound_AI_SDR/docs/`; Outbound Prospector ya no vive aquí,
   ver nivel 3b). Debe seguir al código.
3b. **Para Outbound Prospector específicamente:** su código y docs se extrajeron
   al repo hermano `outbound-prospector-app/` el 20-ago-2026
   (`outbound-prospector-app/docs/modelos_dominio_core.md`,
   `flujos_motor_1_y_2.md`) — mismo rango que el nivel 3, solo cambia la ruta
   física porque es un repo distinto, no una carpeta de este.
4. **`01_Gobernanza_EOS/02_backlog_y_rocas.md`, sección "BITÁCORA DE DECISIONES
   HISTÓRICAS"** — verdad sobre el PORQUÉ (decisiones tomadas). Una decisión
   marcada "pendiente" NO implica que el código la haya aplicado; verificar en
   el código antes de afirmar que está hecha.
5. **`01_Gobernanza_EOS/00_vision_y_principios.md`** y **`04_eos_vto_agencia.md`**
   — ADN, estrategia y V/TO de la agencia (rara vez cambian).
6. **Memoria auto-persistente de Claude Code** (`~/.claude/projects/.../memory/*.md`,
   compartida entre los 4 puntos de entrada vía `autoMemoryDirectory`, ver
   `01_entorno_y_operacion.md`) — el rango MÁS BAJO de los seis. Es caché de
   sesión y bitácora de hallazgos/decisiones no derivables del código (bugs de
   MCP, contexto de colaboración), nunca fuente de verdad sobre qué hace el
   sistema. Si contradice cualquiera de los 5 niveles de arriba, se corrige la
   memoria, nunca al revés — igual que con cualquier otro `.md`. (Añadido
   21-ago-2026, auditoría de arquitectura de memoria — ver
   `04_Segundo_Cerebro/guia_arquitectura_memoria.md` §1.7.)

Regla dura: **ninguna afirmación sobre el comportamiento del código se escribe en
memoria sin haberlo verificado en `src/` o en un test.** Si no se verificó, se
escribe como "sin verificar" o no se escribe.

## 2. Protocolo de LECTURA (contextualizarse sin quemar tokens)

Orden canónico al arrancar una sesión o tarea:

1. `01_Gobernanza_EOS/02_backlog_y_rocas.md` — dónde estamos.
2. Para preguntas de código/arquitectura: **primero `graphify query "<pregunta>"`**
   (o `god-nodes`, `graphify explain "X"`), NO leer `src/` archivo por archivo.
   El grafo devuelve el subgrafo relevante y evita el context-bloat.
3. Solo si el grafo no basta: leer el archivo puntual de `src/` que señaló el grafo.
4. `02_Lineas_de_Producto/<Linea>/docs/` solo el subarchivo pertinente al tema
   (no todo).
5. Para contexto del cliente activo: `03_Clientes_y_Casos/<Cliente>/`.

Señal de alarma al leer: si un `.md` enlaza a `docs/`, `estrategia/`,
`proyectos/`, o a la numeración vieja (`00-`/`01-`/`10-`/`20-` sueltos, rutas
purgadas el 13-ago-2026), o cita conteos de tests distintos al actual, o
describe clases que `graphify`/`grep` no encuentran en `src/` → **está
desactualizado; verificar contra código antes de creerle.**

## 3. Protocolo de ESCRITURA (mantener la memoria sana)

- **Verificar antes de escribir.** Todo dato de comportamiento se confirma con
  `grep`/lectura/test. Todo dato verificable lleva fuente + fecha.
- **Un concepto vive en UN solo lugar** (poda sináptica). Detalle en su subarchivo;
  el índice (`contexto-proyecto.md`) solo enlaza. Prohibido duplicar prosa larga.
- **`02_backlog_y_rocas.md` es append-por-sesión:** se agrega un bloque fechado
  arriba (nueva entrada de sesión); no se borra el historial.
- **Distinguir 3 estados de una idea, siempre explícito:**
  `PROPUESTO` (bitácora, sin código) · `IMPLEMENTADO` (en `src/` + test) ·
  `HUÉRFANO` (código escrito pero no cableado/no importado).
  Nunca escribir "hecho" para algo `PROPUESTO` ni `HUÉRFANO`.
- **Rutas:** usar SIEMPRE la estructura EOS vigente (`01_Gobernanza_EOS/`,
  `02_Lineas_de_Producto/<Linea>/{docs,src,tests}/`, `03_Clientes_y_Casos/<Cliente>/`).
  Rutas muertas (numeración plana `00-`/`01-`/`10-`/`20-`, `docs/`, `estrategia/`,
  `proyectos/`) fueron purgadas y consolidadas el 13-ago-2026.
- **Antipsicofancia al escribir memoria:** si el fundador afirma que algo está
  hecho y el código dice lo contrario, se documenta el estado REAL del código y
  se señala la discrepancia con evidencia. No se escribe "hecho" por complacer.

## 4. Sincronización código ↔ memoria (cada sesión de trabajo de código)

> ℹ️ **Estado (25-jul-2026):** `sincronizador-spec`, `handoff-cierre-sesion`,
> `cerrar-decision` y `memory-preload` se convirtieron de hooks manuales
> legacy a **Skills** (`.kiro/skills/<nombre>/SKILL.md`, invocación on-demand)
> — un hook es para eventos automáticos, estos 4 eran `userTriggered`
> (manuales), así que Skill es el mecanismo correcto. Los hooks de EVENTO que
> sí ejecutan automáticamente son los `.json` v1: `format-on-save-ruff` y
> `gate-verificacion-pytest`.

- Tras tocar el Core (`models.py`/`policies.py`/`interfaces.py`): ejecutar el
  protocolo `sincronizador-spec` (drift contra `modelos_dominio_core.md`).
- Al cerrar sesión: ejecutar el protocolo `handoff-cierre-sesion` (audita drift,
  corre tests, regenera `graphify-out/`, consolida memoria en los 3 niveles).
- Tras cambios de código: `graphify update .` (sin costo de API) para no dejar el
  grafo obsoleto. El `GRAPH_REPORT.md` trae el commit desde el que se construyó.

## 5. Checklist de 20 segundos antes de dar por buena una afirmación de memoria

- [ ] ¿Lo verifiqué en `src/`/test, o solo lo leí en un `.md`?
- [ ] ¿La fuente cita fecha? ¿Es la más reciente?
- [ ] ¿La idea es PROPUESTA, IMPLEMENTADA o HUÉRFANA? ¿Lo dije explícito?
- [ ] ¿Los links apuntan a la estructura numerada vigente?
- [ ] ¿El conteo de tests / nodos de grafo que cito es el actual?
