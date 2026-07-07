---
name: diseno-hexagonal
description: >-
  Diseña o revisa arquitecturas bajo el patrón hexagonal (Ports & Adapters) con
  DDD y SOLID. Úsala cuando se pida estructurar un Core de dominio agnóstico,
  definir puertos/adaptadores, o asegurar extensibilidad (Open/Closed) para
  nuevos sectores/clientes sin tocar el núcleo. Agnóstica de sector.
---

# Skill: diseno-hexagonal

## Propósito
Aplicar Arquitectura Hexagonal para que el **Core del dominio sea 100% agnóstico**
de sector, proveedor e infraestructura, y que agregar un cliente/industria nuevo
sea escribir un adaptador — nunca modificar el núcleo.

## Cuándo se activa
Peticiones de diseñar/estructurar arquitectura, definir puertos e interfaces,
desacoplar proveedores, o hacer un sistema extensible a nuevos sectores.

## Reglas del patrón (no negociables)
1. **Dependencias hacia adentro:** los adaptadores conocen al Core; el Core JAMÁS conoce a los adaptadores.
2. **Core puro:** modelos y reglas de negocio sin librerías de red/DB; testeables sin internet.
3. **Puertos primero (Dependency Inversion):** el Core define las interfaces; la infraestructura las implementa.
4. **Open/Closed:** nueva funcionalidad por extensión (nuevo adaptador + policy), no por modificación del Core.
5. **Configuración inyectada:** pesos, políticas y umbrales sectoriales viven en `Policy` inyectada, no hardcodeados.

## Procedimiento
1. Identificar el **dominio puro** (entidades, motores de reglas, máquina de estados).
2. Definir **Inbound Ports** (driving) y **Outbound Ports** (driven).
3. Mapear **Adaptadores** concretos a cada puerto (intercambiables).
4. Mostrar cómo entra un **sector/cliente nuevo** como adaptador sin tocar el Core.
5. Diagramar en Mermaid (hexagonal) y, si aplica, la máquina de estados.

## Ejemplo de anclaje (Prospector Vía B)
- Core: `ICPManifest`, `SpecificityScoreEngine`, `TriggerScoringEngine`, `StateTransitionPolicy`.
- Puertos: `IntentParserPort`, `TriggerSourcePort`, `EnrichmentProviderPort`, `CompanyRepositoryPort`, `LLMPort`.
- Adaptadores: PydanticAI, TheirStack, LinkedIn, Waterfall, PostgreSQL.
- Detalle completo → `docs/tecnico/prospector-m1-m2-design.md`.

## Anti-objetivos
- No mezclar conocimiento sectorial dentro del Core.
- No acoplar el diseño a un proveedor específico (todo tras un puerto).
