# AGENTS.md — Guía corta para agentes de IA

Este repositorio es la **fuente de la verdad** del proyecto de emprendimiento tecnológico de Yeison. Si eres un agente de IA trabajando aquí, lee esto primero.

## Cómo cargar contexto (estructura numerada canónica)

1. **Memoria de trabajo:** lee siempre primero [`00-Cortex_Operativo/estado_actual.md`](00-Cortex_Operativo/estado_actual.md) — handoff y objetivo de hoy.
2. **Neocórtex técnico (fuente de verdad para código):** [`10-Memoria_Consolidada/`](10-Memoria_Consolidada/). Contratos en `modelos_dominio_core.md`, flujos en `flujos_motor_1_y_2.md`. Subcarpetas: `tecnico/`, `validacion/`, `proyecto-catalina/` (**Aquí viven el Frente 1 - TBBC y el Frente 2 - Sandler/WhatsApp, prioridad absoluta**). Si no está ahí, no existe.
3. **ADN / estrategia:** [`01-Fundamentos_Estrategia/`](01-Fundamentos_Estrategia/) (incluye `pendientes-checklist.md`, el dashboard de tareas).
4. **Decisiones (porqué):** [`20-Bitacora_Decisiones/`](20-Bitacora_Decisiones/). **Ignora** `99-Archivo_Muerto/`.
5. **Grafo de código:** si existe `graphify-out/graph.json`, usa `graphify query "<pregunta>"` antes de leer archivos de `src/` sueltos — devuelve solo el subgrafo relevante.
6. El [`README.md`](README.md) tiene el mapa completo.

## Reglas de comportamiento (no negociables)

- **Antipsicofancia:** sé crítico, no complaciente. Cuestiona supuestos, expón riesgos, exige validación.
- **No inventes datos.** Si un archivo no tiene contenido o falta una fuente, dilo explícitamente. Nunca fabriques métricas, nombres de clientes ni resultados.
- **Vende resultados, no tareas.** Toda recomendación se conecta a las 3 reglas de oro (ganar dinero / ahorrar tiempo / ahorrar dinero).
- **Cita fuente + fecha** al afirmar algo verificable.
- **Respeta el marco legal** (Habeas Data Ley 1581/2012; ToS de plataformas) en cualquier estrategia de scraping o cold email.

## Higiene de memoria

Mantén `contexto-proyecto.md` ligero (índice + punteros). El detalle vive en los subarchivos. Si algo crece, muévelo a su archivo y deja el enlace.

## Estado actual

Handoff vivo: [`00-Cortex_Operativo/estado_actual.md`](00-Cortex_Operativo/estado_actual.md).
Dashboard de tareas: [`01-Fundamentos_Estrategia/pendientes-checklist.md`](01-Fundamentos_Estrategia/pendientes-checklist.md).
