# 03 · Protocolos de Comunicación y Prompt Engineering Avanzado

Este documento define el **Estándar de Comunicación** que debe usarse para interactuar y dirigir a Claude (Claude Code, Sonnet 5.0, Opus 5.0, modelos 4.8+, etc.) en este proyecto. El objetivo es eliminar la probabilidad de error, mantener el contexto limpio, evitar la "psicofancia" (complacencia) y maximizar las capacidades de razonamiento del modelo.

## 1. Regla de Oro: Antipsicofancia y Sentido Crítico
Los agentes que operan en este proyecto son auditores técnicos, no asistentes complacientes.
*   **Si el humano pide algo que viola la arquitectura (ej. acoplar un puerto a la DB)**, el agente debe negarse, exponer el riesgo y proponer la abstracción correcta.
*   **No asumas nada sin datos:** Si el humano asume una métrica o estado sin fuente, el agente debe investigar (leer archivos, buscar en la web) o exigir la fuente. No tragar entero.
*   **El agente no responde con más preguntas abiertas**, sino con propuestas, investigaciones consolidadas y pasos ejecutables.

## 2. Context Engineering (El Nuevo Prompting)
La inteligencia ya no es el cuello de botella en los modelos avanzados; es la gestión de la ventana de contexto (hasta 200K tokens). Rellenar el contexto de forma desordenada ("prompt stuffing") degrada el rendimiento ("context rot").
*   **El Principio "Tight":** Mantén el contexto mínimo y de alta señal. No le pases toda la base de código de golpe; dale los puntos de entrada y deja que él use herramientas de lectura/búsqueda.
*   **El Patrón de Etiquetas XML:** Todo prompt complejo debe separar instrucciones, contexto y datos usando etiquetas XML explícitas.

```xml
<system_prompt>
  <metadata>Ubicación: outbound-prospector-app/src/ (repo hermano, no subcarpeta de este)</metadata>
  <role>Arquitecto de Software Principal. Tu tarea es auditar y escribir código de producción.</role>
  <input_context>Revisa `archivo_a.py` y `archivo_b.py`.</input_context>
  <rules>
    1. Usa Pydantic v2.
    2. Maneja los errores con `try/except` específicos.
  </rules>
</system_prompt>
```

## 3. Framing Positivo y Razonamiento Extendido
*   **Framing Positivo:** Claude responde mucho mejor a reglas en positivo. En lugar de decir "No uses librerías antiguas", usa "Prioriza el uso de la API estándar moderna o librerías actualizadas al 2024".
*   **El uso de `<thinking_process>` y "Ultrathink":** Obliga a la IA a planear antes de codificar. Si la tarea es de alta complejidad arquitectónica, usa prompts que exijan un análisis profundo: "Genera un plan paso a paso en una etiqueta `<thinking_process>` detallando los edge cases antes de proponer cualquier código".

## 4. Gestión de Sesiones y Memoria (El "Cerebro")
Claude no tiene memoria nativa a largo plazo entre sesiones de CLI independientes. Para proyectos continuos como este, el conocimiento debe persistirse:
*   **Archivo `CLAUDE.md`:** Todo proyecto debe tener un archivo `CLAUDE.md` en su raíz con las convenciones de código y reglas core. Claude Code lo detecta y lee automáticamente en cada sesión para alinearse.
*   **State of the Union (Artefactos de Memoria):** Cuando una sesión de desarrollo larga está por terminar, pídele a Claude que genere un archivo markdown de resumen (ej. `estado_dashboard_v10.md`). Al iniciar la sesión del día siguiente, tu primer prompt debe ser: "Lee el archivo `estado_dashboard_v10.md` para recuperar tu memoria de trabajo".
*   **Poda de Contexto:** Si la sesión actual acumula muchos errores, diffs fallidos o salidas de terminal gigantes (ej. logs largos), el contexto se "ensucia". Es mejor guardar el estado en un archivo, matar la sesión y abrir una nueva, totalmente limpia y enfocada.

## 5. Herramientas, MCP y Delegación con Claude Code
Cuando uses Claude Code o agentes con acceso al entorno:
*   **Herramientas CLI Nativas:** Deja que Claude use herramientas estándar como `grep`, `jq`, `gh` (GitHub CLI) o `pytest`. Si necesitas que interactúe con algo nuevo, dile: "Ejecuta `[comando] --help` para aprender su uso y luego aplícalo".
*   **Sub-Problemas (Divide y Vencerás):** Si la tarea es grande (ej. "Construye el dashboard entero"), Claude puede abrumarse. Córtalo en historias de usuario pequeñas: primero el Kanban, luego los filtros, luego las gráficas.
*   **Human-in-the-Loop (Verificación Obligatoria):** NUNCA asumas que un bloque de código masivo funciona. En tus prompts, exige que Claude corra el linter, los tests unitarios o un build de prueba (`npm run build`, `pytest`) ANTES de dar la tarea por terminada.
