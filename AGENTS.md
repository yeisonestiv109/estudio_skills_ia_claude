# AGENTS.md — Guía corta para agentes de IA

Este repositorio es la **fuente de la verdad** del proyecto de emprendimiento tecnológico de Yeison. Si eres un agente de IA trabajando aquí, lee esto primero.

## 🤝 Ritual de inicio de sesión (OBLIGATORIO — antes de cualquier tarea)

Al arrancar una sesión nueva, pregunta siempre esto primero, tal cual, sin modificar:

> **"¿Hoy quién está al mando — Gabyota o Yeisiton?"**

Según la respuesta, responde con un mensaje corto de motivación (máx. 2 líneas, tono cálido y directo) y luego procede a cargar el contexto del proyecto. No empieces a trabajar sin haber hecho esta pregunta. Es una regla, no una sugerencia.

## Cómo cargar contexto (estructura numerada canónica)

1. **Memoria de trabajo (EOS):** lee siempre primero [`01_Gobernanza_EOS/02_backlog_y_rocas.md`](01_Gobernanza_EOS/02_backlog_y_rocas.md) — handoff, objetivos (rocas) y bitácora de decisiones.
2. **Neocórtex técnico (docs/arquitectura, NO el código):** Revisa `02_Lineas_de_Producto/` para docs — `Inbound_AI_SDR/docs/` (ARTF) u `Outbound_Prospector/docs/` (El Prospector). **El código real ya no vive aquí:** Inbound está en el repo hermano `artf-pipeline-app/`, Outbound en `outbound-prospector-app/` (ambos bajo el mismo padre `proyecto_negocio_doscaras/`).
3. **ADN / estrategia:** [`01_Gobernanza_EOS/00_vision_y_principios.md`](01_Gobernanza_EOS/00_vision_y_principios.md) (incluye la visión, las 3 reglas de oro y el perfil híbrido).
4. **Clientes y Laboratorios:** Revisa [`03_Clientes_y_Casos/`](03_Clientes_y_Casos/) para entender el contexto particular de la oportunidad comercial activa (ej. ARTF).
5. **Grafo de código:** si existe `graphify-out/graph.json`, usa `graphify query "<pregunta>"` antes de leer archivos de `src/` sueltos.
6. El [`README.md`](README.md) tiene el mapa completo de la nueva estructura de 2 Velocidades (Inbound/Outbound).

## Reglas de comportamiento (no negociables)

- **Antipsicofancia:** sé crítico, no complaciente. Cuestiona supuestos, expón riesgos, exige validación.
- **No inventes datos.** Si un archivo no tiene contenido o falta una fuente, dilo explícitamente. Nunca fabriques métricas, nombres de clientes ni resultados.
- **Vende resultados, no tareas.** Toda recomendación se conecta a las 3 reglas de oro (ganar dinero / ahorrar tiempo / ahorrar dinero).
- **Cita fuente + fecha** al afirmar algo verificable.
- **Respeta el marco legal** (Habeas Data Ley 1581/2012; ToS de plataformas) en cualquier estrategia de scraping o cold email.

## Higiene de memoria

Mantén el índice del `README.md` ligero. El detalle vive en los subarchivos. Si algo crece, muévelo a su archivo y deja el enlace.

**Protocolo anti-confusión (lectura obligatoria):** Regla núcleo: **el código ejecutable + tests en verde le ganan a cualquier `.md`**. Si la memoria contradice al código, gana el código y se corrige la memoria. Usa siempre la estructura numerada de carpetas (`01_Gobernanza_EOS`, `02_Lineas_de_Producto`, `03_Clientes_y_Casos`). Las rutas viejas (`10-Memoria_Consolidada`, `01-Fundamentos_Estrategia`, `docs/`) fueron purgadas y consolidadas.

## Perfiles y entorno

Yeisiton usa WSL2 (Ubuntu); Gabyota **no**. El contexto del proyecto (memoria/hooks/skills) es compartido; el entorno de máquina no. Detalle → [`01_Gobernanza_EOS/01_entorno_y_operacion.md`](01_Gobernanza_EOS/01_entorno_y_operacion.md).

## Estado actual

Handoff vivo y rocas de EOS: [`01_Gobernanza_EOS/02_backlog_y_rocas.md`](01_Gobernanza_EOS/02_backlog_y_rocas.md).
