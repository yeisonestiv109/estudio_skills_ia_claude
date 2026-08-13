---
name: sincronizador-spec
description: "Detecta y corrige drift entre el código del Core y la spec de dominio. Úsala tras cambiar models.py/policies.py/interfaces.py, cuando se sospeche desincronización, o antes de un cierre de sesión. Compara enums, modelos Pydantic y puertos del código contra modelos_dominio_core.md y sincroniza la spec al código."
---

# Sincronizador de Spec — El Prospector

> Reclasificado de hook a skill (24-jul-2026): se invoca on-demand cuando se
> sospecha drift, no en cada guardado (correr un análisis LLM completo en cada
> save sería ruidoso y caro). Ver `.kiro/steering/estrategia-memoria.md`.

Detecta drift entre el código del Core y la documentación de la spec.

> Asume `02_Lineas_de_Producto/Outbound_Prospector/` (única línea con Core real
> hoy). Adapta las rutas si el drift a revisar es de otra línea de producto.

1. **Lee el código fuente del Core:**
   - `02_Lineas_de_Producto/Outbound_Prospector/src/core/domain/models.py` (todos los Enums y modelos Pydantic)
   - `02_Lineas_de_Producto/Outbound_Prospector/src/core/domain/policies.py` (todas las políticas puras)
   - `02_Lineas_de_Producto/Outbound_Prospector/src/core/ports/interfaces.py` (todos los ABCs/puertos)

2. **Lee la spec:** `02_Lineas_de_Producto/Outbound_Prospector/docs/modelos_dominio_core.md`.

3. **Compara exhaustivamente:**
   - ¿Enums en el código que no están en la spec (o al revés)?
   - ¿Valores de enum que difieren entre código y spec?
   - ¿Campos de modelos Pydantic en el código que la spec no documenta?
   - ¿Puertos (ABCs) en el código que la spec no menciona?

4. **Reporta en tabla:** ITEM | ESTADO (✅ Sincronizado / ⚠️ Drift) | ACCIÓN.

5. **Si hay drift:** sincroniza la spec AL código (el código ejecutable es la
   verdad, nunca al revés). Aplica los cambios directamente en
   `02_Lineas_de_Producto/Outbound_Prospector/docs/modelos_dominio_core.md`.

NO inventes datos. Ante ambigüedad, reporta "requiere verificación manual".
Respeta `AGENTS.md` y `estrategia-memoria.md`.
