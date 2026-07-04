# Hacks de Productividad con Agentes de IA (Claude Code y similares)

Extraído y organizado de las guías freelance del fundador (`documento_1`/`documento_2`), ampliado con criterio técnico. Aplica a Claude Code, Cursor, Kiro y cualquier agente de código/automatización. Útil tanto para el fundador como para los agentes que trabajen en este repo.

## El concepto clave: IA "mente" vs IA "mente + manos"

- **IA conversacional (navegador):** la "mente" — aconseja, redacta, explica. No ejecuta.
- **IA agéntica (Claude Code, Cursor, Kiro):** la "mente + manos" — accede a tus archivos, ejecuta comandos, construye y corrige. Por eso se instala localmente (necesita acceso a tus carpetas) o corre en un entorno con tus archivos.

Esta distinción es la misma que sostiene el posicionamiento del fundador: no es "usar un chat", es **orquestar ejecutores** para entregar resultados reales.

## Hacks prácticos

| Hack | Qué es | Cuándo usarlo |
|------|--------|---------------|
| **Imagen → código** | Subir captura de un diseño y pedir que construya la estructura web | Maquetar rápido una landing o UI a partir de una referencia |
| **Modo automático** | Desbloquear permisos para que el agente ejecute sin pedir confirmación en cada paso | Depuración larga o tareas repetitivas (con cuidado, ver riesgos) |
| **Conexiones externas (MCP/integraciones)** | Conectar el agente a Gmail, Notion, CRM, Shopify, GitHub | Automatizar flujos que tocan herramientas de negocio |
| **Memoria estructurada en archivos** | Pedir que organice el contexto en varios archivos enlazados (ej. `CLAUDE.md`, `AGENTS.md`) | Proyectos complejos, para evitar pérdida de contexto |
| **Autocorrección visual** | El agente toma capturas, detecta fallos visuales/de código y los corrige antes de entregar | QA antes de la entrega final (lo que hace Antigravity en el stack) |

> El hack de "memoria estructurada" **ya lo aplicamos en este repo:** `AGENTS.md`, `.kiro/steering/contexto-proyecto.md` y los `README.md` por carpeta son la memoria del agente.

## Conexión con el stack SDLC del proyecto

Esto encaja con el stack orquestado: **Kiro** (spec/plan) → **Claude Code** (backend/lógica) → **Antigravity** (frontend + QA visual). Los hacks de arriba son tácticas dentro de ese flujo. Ver [`stack-sdlc-ia.md`](stack-sdlc-ia.md).

## ⚠️ Lectura crítica del coach (riesgos a manejar)

- **"Modo automático" (auto-aprobar comandos):** cómodo, pero peligroso si el agente borra archivos, hace `push --force` o expone secretos. Úsalo solo en entornos aislados/reversibles (git limpio, ramas, backups). Nunca con credenciales de producción a la mano.
- **Conexiones externas:** cada integración (Gmail/CRM/Shopify) es una superficie de riesgo de datos. Revisar permisos mínimos y no conectar datos sensibles sin necesidad.
- **"Software en 3 días sin código":** sirve para MVP/demo, no para producción crítica sin pruebas. A un cliente se le entrega validado, no "rápido y mágico".
- **Sycophancy:** el agente tiende a darte la razón. Pídele siempre contras y validación (disciplina ya documentada en [validación de fuentes](../validacion/validacion-fuentes.md)).
- **Costo:** vigilar consumo de tokens/APIs en tareas largas en modo automático (puede disparar gasto).

## Aplicación inmediata para el fundador

- Mantener `AGENTS.md`/steering actualizados = mejor memoria del agente en cada sesión.
- Usar agentes para automatizar tus propias tareas (ver [roadmap de productividad](../../estrategia/productividad-y-automatizacion.md)).
- Para entregables de cliente: agente construye, tú validas antes de entregar.
