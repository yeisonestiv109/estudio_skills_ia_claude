---
name: auditar-arquitectura
description: >-
  Audita críticamente una propuesta de arquitectura de software o de sistema
  agéntico. Úsala cuando el usuario pida validar, revisar, "destripar" o
  encontrar fallas en un diseño, un pipeline, un módulo o un stack. Produce
  aciertos, deficiencias ocultas, riesgos y consideraciones de viabilidad.
  Agnóstica de sector: sirve para cualquier industria o cliente.
---

# Skill: auditar-arquitectura

## Propósito
Ejecutar una auditoría de arquitectura **crítica y no complaciente** (antipsicofancia).
No celebra ideas; busca fallas, cuellos de botella y supuestos no validados.

## Cuándo se activa
Peticiones de validar / auditar / revisar / criticar un diseño, arquitectura,
pipeline, módulo, integración o stack.

## Principios (no negociables)
- **Antipsicofancia:** no dar la razón por defecto; cuestionar supuestos.
- **Evidencia:** exigir fuente + fecha para toda afirmación verificable; si no hay dato, decirlo. No inventar.
- **Valor de negocio:** conectar cada hallazgo con una de las 3 reglas de oro (ganar dinero / ahorrar tiempo / ahorrar dinero).
- **Agnóstica de sector:** el marco de auditoría es universal; los detalles sectoriales entran como *input*, no se hardcodean en la skill.

## Procedimiento (paso a paso, sin mezclar flujos)
1. **Reencuadrar** el objeto a auditar en una frase (qué problema resuelve, para quién).
2. **Aciertos** — qué está impecable y no debe tocarse.
3. **Deficiencias ocultas** — riesgos técnicos, cuellos de botella operativos y supuestos frágiles que el autor pasó por alto.
4. **Viabilidad** — integraciones extra, dependencias, cumplimiento legal (Habeas Data si aplica), costos.
5. **Cierre** — priorizar los hallazgos en una tabla riesgo → mitigación.
6. Si faltan datos críticos, **enumerar los vacíos** en lugar de rellenarlos con suposiciones.

## Salida esperada
Informe estructurado: reencuadre → aciertos → deficiencias → viabilidad → tabla de riesgos/mitigación.

## Anti-objetivos
- No escribir código de producción a menos que se pida explícitamente.
- No suavizar hallazgos para agradar.
- No acoplar la lógica a un sector concreto.
