# Control de Versiones — Playbook Setter IA (ARTF)

Registro histórico de versiones del playbook del Setter y del proyecto Setter-IA-Claude-Code-Project.

> **Fuente de verdad del contenido:** `Playbooks/SOP Setter DM en Instagram V4.2.docx` (y su sección CONTROL DE VERSIONES).
> Este archivo replica esa bitácora y agrega el detalle de qué archivos del proyecto cambió cada versión.
>
> **Norma:** cada cambio al playbook genera una versión **totalmente coherente** en todo su contenido — subtítulo/fecha, esta bitácora, etiquetas ★NUEVO de la versión correcta, nombre de archivo del SOP, y los prompts del proyecto que lo reflejan (`system-prompt-condensado`, `system-prompt-plan-b`).

---

## Versión vigente: **V4.2** · 01-09-2026 · Responsable: Javier + Claude · **ACTIVA**

Cambios:
1. **Eliminación de Datacrédito de la precalificación.** Se quita el Mensaje 3 (Datacrédito) y su filtro; el flujo pasa de 8 a 7 mensajes y los criterios de 4 a 3 filtros (ingreso, endeudamiento, urgencia). *Razón:* ya no se usará el reporte en Datacrédito para precalificar.
2. **Reordenamiento del cierre: la confirmación de asistencia (solo o acompañado) pasa a hacerse DESPUÉS de enviar el link de agendamiento — ahora el Mensaje 6 es el Cierre + link y el Mensaje 7 es la pregunta de asistencia.** *Razón:* enviar primero el link acelera el agendamiento; la asistencia se confirma justo antes de que el lead separe su espacio. La asistencia NO es un filtro (es post-cierre).

Archivos tocados: `SOP Setter DM en Instagram V4.2.docx`, `manychat/system-prompt-condensado.md`, `manychat/system-prompt-plan-b.md`, `manychat/custom-fields.md`, `manychat/flujo-completo.md`, `objection-handling/7-objeciones-estandar.md`, `scripts/descalificacion-con-valor.md`, `scripts/m2-endeudamiento.md`, `scripts/m2-frustracion.md`, `scripts/m3-urgencia.md`, `scripts/m4-pitch-llamada.md`, `scripts/m5-cierre-agendamiento.md`, `scripts/m5-5-confirmacion-post-calendly.md`, `scripts/m7-asistencia.md`, `scripts/bumps-recuperacion.md`, `knowledge-base/03-avatar-cliente-ideal.md`, `sops/sop-01-flujo-end-to-end.md`, `sops/sop-05-aprendizajes-produccion.md`, `README.md`, `CLAUDE.md`, `CONTROL-DE-VERSIONES.md`.

⚠️ **Pendiente:** el `SYSTEM_PROMPT` del Worker de producción `setter-ia-bridge` NO está actualizado — sigue con la numeración/filtros previos (incluido Datacrédito) y con umbral $8M. Requiere redeploy.

---

## V4.1 · 01-09-2026 · Responsable: Javier + Claude · **ARCHIVADA**

Cambios:
1. **Corrección de inconsistencias de la V4.0.** Renumeración de mensajes 1–8 y sus bifurcaciones, umbral de ingreso $8M→$7M en los scripts, y tope de endeudamiento condicional al ingreso (≤50% si gana ~$7M, hasta 60% si gana >$9M). *Razón:* la V4.0 tenía numeraciones y umbrales inconsistentes.
2. **Regla anti-descarte por ingreso ambiguo + glosario colombiano.** Nunca se descalifica sobre un ingreso sin cifra clara; se pide el número primero. «Mínimo integral» = ingreso ALTO (~$18–22M+), NO «salario mínimo». Incluye SMLV, «por quincena», «básico + comisiones», USD/EUR. *Razón:* caso real de lead de $22M descartada por leer «mínimo integral» como salario mínimo.
3. **Flujo de corrección de descarte (RetornoLead).** Si un lead descartado se recalifica, se rectifica sin humano y sin revelar que es IA.

Archivos tocados: `SOP Setter DM en Instagram V4.1.docx`, `scripts/m1-apertura.md`, `scripts/descalificacion-con-valor.md`, `manychat/system-prompt-condensado.md`, `manychat/system-prompt-plan-b.md`, `knowledge-base/03-avatar-cliente-ideal.md`, `CLAUDE.md`.

---

## Historial

| Versión | Fecha | Responsable | Estado | Qué cambió |
|---|---|---|---|---|
| **V4.2** | 01-09-2026 | Javier + Claude | **ACTIVA** | (1) Eliminación de Datacrédito de la precalificación: se quita el Mensaje 3 (Datacrédito) y su filtro; flujo de 8→7 mensajes y criterios de 4→3 filtros (ingreso, endeudamiento, urgencia). (2) Reordenamiento del cierre: el Mensaje 6 pasa a ser el Cierre + link y el Mensaje 7 la confirmación de asistencia (solo/acompañado), que ahora se pregunta DESPUÉS de enviar el link. |
| V4.1 | 01-09-2026 | Javier + Claude | Archivada | Corrección de inconsistencias V4.0; anti-descarte por ingreso ambiguo + glosario; corrección de descarte (RetornoLead). |
| V4.0 | 11-08-2026 | Catalina | Archivada | Nuevo Mensaje 3 (Datacrédito) + 4º filtro; refinamiento del filtro de endeudamiento (condicional al ingreso); nuevo Mensaje 7 (Asistencia solo/acompañado). Flujo pasa a 8 mensajes. |
| v3.0 | 08-06-2026 | Andrés + Javier + Claude | Archivada | Nuevo Mensaje 2 (Endeudamiento); ingresos mínimos $5M→$7M; criterio endeudamiento ≤50%; nueva Objeción 9; tuteo colombiano estricto; numeración 5→6 mensajes. |
| v2.0 | 23-05-2026 | Andrés + Javier | Archivada | Refinamiento de scripts; 8 objeciones estándar; SOP de recuperación con 3 bumps; descalificación con valor. |
| v1.0 | 13-01-2025 | Javier Suárez | Archivada | Versión inicial en primera persona (Andrés). Flujo de 5 mensajes: Apertura → Calificación → Frustración → Urgencia → Pitch → Cierre. |

---

## Convención de etiquetas
- **Versión vigente** = la fila ACTIVA de arriba (subtítulo del SOP, headers de los system-prompts).
- **★ NUEVO Vx** junto a una feature = la versión que la introdujo (las features viejas conservan su versión de origen; las nuevas llevan la versión vigente). Ej: Asistencia = ★ NUEVO V4.0; anti-descarte = ★ NUEVO V4.1.
