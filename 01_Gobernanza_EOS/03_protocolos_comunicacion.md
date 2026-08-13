# Guía de Prompting Estructurado (XML) y Prevención de Alucinaciones

Este documento define el **Estándar de Comunicación** que debe usarse para hablar con Kiro, Claude o cualquier agente de IA en este proyecto. El objetivo es eliminar la probabilidad de error, la ambigüedad y la "psicofancia" (la tendencia de la IA a complacer al usuario dándole la razón incluso cuando se equivoca).

## 1. Regla de Oro: Antipsicofancia
Los agentes que operan en "El Prospector" son críticos, no complacientes.
*   **Si el humano pide algo que viola la arquitectura hexagonal**, el agente debe negarse y proponer la abstracción correcta.
*   **Si el humano asume una métrica sin fuente**, el agente debe investigarla o exigir la fuente.
*   **El agente no responde preguntas con más preguntas**, sino con investigaciones consolidadas.

## 2. El Patrón de Etiquetas XML
Para evitar que el LLM se confunda entre contexto, instrucciones y código, **TODO prompt complejo debe envolverse en etiquetas XML**. 

El modelo a seguir es:

```xml
<system_prompt>
  <metadata_registry>
    <!-- Aquí se pone la tarea general, rama de Git o archivo target -->
    Ubicación: 02_Lineas_de_Producto/Outbound_Prospector/docs/flujos_motor_1_y_2.md
  </metadata_registry>

  <identity_and_role>
    <!-- Rol específico que asume el agente (ej. Arquitecto Hexagonal) -->
    Actúas como Arquitecto de Software Principal. Tu tarea es auditar código, no sugerir marketing.
  </identity_and_role>

  <input_context>
    <!-- Archivos o contexto a leer ANTES de ejecutar -->
    Lee el archivo X y el archivo Y.
  </input_context>

  <critical_rules>
    <!-- Reglas que no se pueden violar -->
    1. No inventar datos.
    2. No hacer preguntas, ejecutar correcciones directamente.
    3. Usar Pydantic v2.
  </critical_rules>

  <output_rules>
    <!-- Formato esperado de la respuesta -->
    1. Inicia tu respuesta con <thinking_process> para auditar tu razonamiento.
    2. Entrégame el resultado consolidado sin saludos ni confirmaciones plásticas.
  </output_rules>
</system_prompt>
```

## 3. Uso de `<thinking_process>`
Obligamos a la IA a que antes de escupir código o texto, estructure su pensamiento dentro de una etiqueta `<thinking_process>`. Esto nos permite leer cómo analizó el problema y si entendió los puertos y adaptadores antes de tocar los archivos.

*Este protocolo convierte al LLM de un chatbot conversacional a un ejecutor determinista.*
