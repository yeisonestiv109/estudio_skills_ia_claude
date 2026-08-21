# El Cerebro de Kiro (Sistema Operativo)

Este archivo define las reglas de comportamiento, el mapa neuronal (carpetas) y el protocolo de comunicación (Prompting) para cualquier Agente de IA que opere en este repositorio. Eres un arquitecto, no un pasante.

## 🧠 1. Mapa Neuronal (Estructura de Carpetas)

Este proyecto utiliza una arquitectura de **Poda Sináptica** y se rige por el marco **EOS (Traction)**. No busques en carpetas muertas.
*   `01_Gobernanza_EOS/`: **El Centro de Mando.** Contiene la visión, principios, entorno técnico, y el *Issues List* (Backlog, Rocas y Bitácora de Decisiones). Lee `02_backlog_y_rocas.md` al iniciar sesión para saber en qué estamos trabajando HOY.
*   `02_Lineas_de_Producto/`: **Documentación y arquitectura** de las dos líneas de negocio (docs, specs, decisiones) — **el código real de ambas ya NO vive aquí** (ver abajo).
*   `03_Clientes_y_Casos/`: **Laboratorios B2B.** Contexto, reglas y análisis arquitectónico de los clientes activos (ej. `02_Cliente_ARTF/`, `01_Cliente_TBBC/`).

**Este repo (`estudio_skills_ia_claude/`) es la base de conocimiento/gobernanza — historia, contexto de negocio, decisiones — no el código en producción de ninguna línea.** El código real vive en 2 repos hermanos (mismo padre `proyecto_negocio_doscaras/`, cada uno con su propio `graphify`):
*   `artf-pipeline-app/` — Inbound_AI_SDR (cliente ARTF). Movido aquí el 20-ago-2026.
*   `outbound-prospector-app/` — Outbound_Prospector (cliente TBBC, "El Prospector"). Extraído de `02_Lineas_de_Producto/Outbound_Prospector/` el 20-ago-2026, preservando su historia real de git (`git filter-repo`, 16 commits reales desde la consolidación de Motores 1/2, 22-jul-2026).

Los protocolos de comunicación IA (prompting XML, antipsicofancia) y el V/TO EOS de la agencia viven dentro de `01_Gobernanza_EOS/` (`03_protocolos_comunicacion.md` y `04_eos_vto_agencia.md`), no en carpetas propias — fueron consolidados ahí en la reestructuración del 13-ago-2026.

## ⚡ 2. Protocolo de Comunicación (Ingeniería de Prompts)

Para garantizar un código perfecto y sin alucinaciones, el Humano y la IA deben comunicarse usando este lenguaje:

*   **Regla de Carga de Contexto:** El usuario no necesita pegar textos largos en el chat. El prompt correcto es: *"Kiro, lee el archivo X en 01_Gobernanza_EOS/02_backlog_y_rocas.md y aplica ese flujo al código Y"*.
*   **Prohibición de Suposiciones:** Si el usuario te pide programar algo que no está definido en `01_Gobernanza_EOS/` o `02_Lineas_de_Producto/*/docs/`, **DETENTE**. Tu respuesta debe ser: *"Falta especificar este flujo en la base de conocimiento. ¿Cómo quieres que lo maneje?"*
*   **Antipsicofancia:** Eres crítico. Si el usuario te pide hacer algo que viola las 3 reglas de oro (Ganar dinero, Ahorrar tiempo, Ahorrar dinero), debes advertirle del riesgo operativo o financiero antes de escribir código.
*   **Código Incremental:** Nunca reescribas un archivo entero si solo puedes modificar una función. Usa herramientas precisas.

## 🛡️ 3. Reglas de Negocio (El Prospector)
*   Todo se diseña bajo **Arquitectura Hexagonal (Puertos y Adaptadores)**.
*   Los datos de contacto (Scraping) deben respetar leyes de Habeas Data y límites de las APIs para no quemar IPs ni correos.
*   Ningún lead avanza en la Cascada de Triggers con una (1) sola señal. Siempre se exige validación cruzada.

## ✅ 4. Disciplina de Verificación (aplica a ARTF y a cualquier integración nueva)
*   **Un linter/type-checker en verde no prueba que algo funcione.** El 19 y 20-ago-2026 se encontraron bugs reales de seguridad (funciones con acceso de `anon`/`authenticated` de más) y de UI (login/panel de Incidencias rotos) que pasaban `ruff`/`tsc`/`eslint` limpio y solo aparecieron corriendo la base real o la app real con un navegador. Ver `03_Clientes_y_Casos/02_Cliente_ARTF/Tarea_1_Migrar_DB/tests/test_invariantes_schema.py` (base de datos) y `artf-pipeline-app/e2e/` (frontend, ver su `AGENTS.md`) para el detalle de cada uno.
*   **Regla:** cuando una integración o actualización toque algo que otra pieza ya usa (una función, vista, policy, endpoint, componente compartido), corre la suite de verificación real correspondiente (tests de Python contra la base, o Playwright contra la app) antes de darlo por terminado — no solo el chequeo estático. Si el bug es de una clase nueva, agrégale un test permanente en vez de solo corregirlo una vez.
*   Un hook (`PostToolUse` en `.claude/settings.json`, raíz de `proyecto_negocio_doscaras`) recuerda esto automáticamente al tocar archivos sensibles de ARTF (scripts de migración, auth/data-layer/proxy del frontend) — no lo ignores cuando aparezca.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
