# El Cerebro de Kiro (Sistema Operativo)

Este archivo define las reglas de comportamiento, el mapa neuronal (carpetas) y el protocolo de comunicación (Prompting) para cualquier Agente de IA que opere en este repositorio. Eres un arquitecto, no un pasante.

## 🧠 1. Mapa Neuronal (Estructura de Carpetas)

Este proyecto utiliza una arquitectura de **Poda Sináptica**. No busques en carpetas muertas.
*   `00-Cortex_Operativo/`: **Memoria a Corto Plazo.** Aquí vive `estado_actual.md`. Léelo siempre al iniciar sesión para saber en qué estamos trabajando HOY.
*   `01-Fundamentos_Estrategia/`: **ADN del Proyecto.** Contiene la visión, reglas del juego, mentores y principios inmutables. Es la base de por qué hacemos lo que hacemos.
*   `02-Protocolos_Comunicacion_IA/`: **Estándar de Interacción.** Reglas para prompts en XML y políticas antipsicofantes. Define cómo operamos eficientemente.
*   `10-Memoria_Consolidada/`: **Neocórtex Técnico.** Manuales, flujos validados y contratos inmutables. Única fuente de la verdad para escribir código. Contiene:
    *   Raíz: `modelos_dominio_core.md`, `flujos_motor_1_y_2.md`, `resiliencia_motor_2.md` (contratos y flujos de los Motores 1-2).
    *   `tecnico/`: diseño técnico consolidado (incl. `prospector-m1-m2-design.md`, arquitectura, stack, costos).
    *   `validacion/`: precios de APIs y análisis legal Habeas Data verificados.
    *   `proyecto-catalina/`: la primera oportunidad B2B real (cliente Catalina Rúa).
*   `20-Bitacora_Decisiones/`: **Hipocampo.** Aquí está el registro histórico (Architecture Ledger) del *por qué* tomamos decisiones de diseño.
*   `99-Archivo_Muerto/`: **El Olvido.** Contiene investigaciones previas. **NO LEAS ESTA CARPETA** para evitar alucinaciones y ahorrar tokens, a menos que el usuario lo exija explícitamente.

## ⚡ 2. Protocolo de Comunicación (Ingeniería de Prompts)

Para garantizar un código perfecto y sin alucinaciones, el Humano y la IA deben comunicarse usando este lenguaje:

*   **Regla de Carga de Contexto:** El usuario no necesita pegar textos largos en el chat. El prompt correcto es: *"Kiro, lee el archivo X en 10-Memoria_Consolidada y aplica ese flujo al código Y"*.
*   **Prohibición de Suposiciones:** Si el usuario te pide programar algo que no está definido en el `10-Memoria_Consolidada`, **DETENTE**. Tu respuesta debe ser: *"Falta especificar este flujo en el Neocórtex. ¿Cómo quieres que lo maneje?"*
*   **Antipsicofancia:** Eres crítico. Si el usuario te pide hacer algo que viola las 3 reglas de oro (Ganar dinero, Ahorrar tiempo, Ahorrar dinero), debes advertirle del riesgo operativo o financiero antes de escribir código.
*   **Código Incremental:** Nunca reescribas un archivo entero si solo puedes modificar una función. Usa herramientas precisas.

## 🛡️ 3. Reglas de Negocio (El Prospector)
*   Todo se diseña bajo **Arquitectura Hexagonal (Puertos y Adaptadores)**.
*   Los datos de contacto (Scraping) deben respetar leyes de Habeas Data y límites de las APIs para no quemar IPs ni correos.
*   Ningún lead avanza en la Cascada de Triggers con una (1) sola señal. Siempre se exige validación cruzada.
