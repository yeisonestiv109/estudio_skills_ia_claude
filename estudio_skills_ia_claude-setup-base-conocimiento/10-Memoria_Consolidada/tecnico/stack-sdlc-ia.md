# Stack de Herramientas IA para el Ciclo de Vida del Software (SDLC)

El **SDLC** (Software Development Life Cycle) es el marco que guía la creación, entrega y mantenimiento de software. Divide el trabajo en etapas (planificación, análisis, diseño, codificación, pruebas, implementación, mantenimiento) para minimizar riesgos, controlar costos/plazos, alinear expectativas y garantizar requisitos funcionales y de seguridad.

## Principio: orquestar, no elegir una sola herramienta

La estrategia óptima en 2026 no es usar una sola IA, sino **orquestarlas por fase**. Cada herramienta domina una etapa por su arquitectura.

```
Problema  →  Kiro (Especificación/Plan)
Backend   →  Claude Code (Código + lógica compleja)
Frontend  →  Antigravity (UI + pruebas visuales/E2E)
Deploy    →  Claude Code (CI/CD headless)
```

## Mapa de fases

### 1. Definición del problema y arquitectura — Kiro

- Desarrollo basado en especificaciones (**spec-driven**).
- Describe el problema en lenguaje natural → genera requisitos, criterios de aceptación y diagramas de flujo antes de escribir código.
- **Valor:** evita "deuda de diseño"; aprobar la spec primero asegura resolver el problema real.
- **Salida:** archivos de especificación + plan paso a paso = fuente de la verdad de las siguientes fases.

### 2. Backend y lógica compleja — Claude Code

- Toma la spec de Kiro como contexto e implementa lógica de negocio, esquemas de BD y refactors grandes.
- Ventana de contexto de 1M tokens (modelos Opus 4.x): puede "leer" repo + spec a la vez.
- Automatización: archivos `CLAUDE.md` para recordar convenciones de arquitectura.

> 📝 **Corrección de vocabulario (verificada):** Claude Code es la herramienta CLI; el modelo es Claude Opus 4.x (Opus 4.6/4.7/4.8). La ventana de 1M tokens es real y está en disponibilidad general para Opus 4.6+ y Sonnet 4.6. Fuente: [Anthropic – contexto de 1M](https://www.anthropic.com). *Contenido reformulado para cumplir con licencias.*

### 3. Frontend, UI y pruebas visuales — Antigravity

- Vista de "Manager" que orquesta agentes para construir UI.
- Navegador integrado (Chromium): los agentes abren la app, interactúan, toman capturas y verifican que la UI coincida con el diseño.
- **Pruebas E2E:** el agente navega la app real y detecta errores de flujo/visuales que un linter no ve.
- Lee artefactos de Kiro y el backend de Claude Code para ensamblar la interfaz.

> ✅ **Verificado:** Antigravity es de Google, lanzado en preview público el 18-nov-2025 junto a Gemini 3 Pro; es un fork modificado de VS Code con editor + agent manager + terminal + navegador Chromium integrados. Fuente: [aiwiki.ai – Antigravity](https://aiwiki.ai). *Contenido reformulado para cumplir con licencias.*

### 4. Correcciones, despliegue y mantenimiento — híbrido

- **Bug lógico:** Claude Code en terminal (`--print`) para analizar logs y proponer fixes.
- **Bug de flujo/requisitos:** volver a Kiro para actualizar la spec y regenerar el plan.
- **CI/CD:** integrar Claude Code en GitHub Actions / GitLab CI (modo headless) para revisar PRs.
- **Mantenimiento:** Agent Hooks de Kiro para tareas rutinarias (deps, changelogs) y Antigravity para monitorear la salud visual en producción.

### 5. Migraciones, mejoras y plugins (ciclo iterativo)

1. Re-especificar alcance/riesgos en Kiro.
2. Ejecutar refactor masivo con Claude Code.
3. Validar que la migración no rompió la UX con Antigravity.

## Tabla resumen

| Fase | Herramienta | Rol |
|------|-------------|-----|
| Especificación / Arquitectura | **Kiro** | Spec-driven, plan, criterios de aceptación |
| Backend / Lógica | **Claude Code** (modelo Opus 4.x) | Implementación pesada, refactors, 1M tokens |
| Frontend / UI / Pruebas | **Antigravity** (Gemini 3 Pro) | UI + E2E con navegador integrado |
| Deploy / CI-CD | **Claude Code** headless | PR review, pipelines |
| Mantenimiento | **Kiro hooks + Antigravity** | Rutina + salud visual |

> Estado de validación detallado en [`../validacion/validacion-fuentes.md`](../validacion/validacion-fuentes.md).
