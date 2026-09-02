# SOP-01 · Flujo End-to-End del Setter IA

Mapa visual del flujo completo: desde que el lead comenta "CONTROL" hasta que asiste a la llamada (o se descarta).

> **⚠️ V4.2 — el flujo ahora tiene 7 mensajes y 3 filtros.** Orden correcto:
> **M1** Ingreso (≥$7M) → **M2** Endeudamiento (tope según ingreso: ≤50% si ~$7M, ≤60% si >$9M) → **M3** Dolor → **M4** Urgencia → **M5** Pitch → **M6** Cierre + link → **M7** Asistencia (solo/acompañado, DESPUÉS del link).
> El diagrama de abajo es el esqueleto heredado (5 pasos). Los pasos nuevos **M2 Endeudamiento** (`scripts/m2-endeudamiento.md`) y **M7 Asistencia** (`scripts/m7-asistencia.md`) se insertan según ese orden, y las cajas de abajo están renumeradas entre paréntesis.

---

## Vista general

```
┌─────────────────────────────────────────────────────────────────┐
│  REEL DE ANDRÉS (orgánico o pagado)                             │
└────────────────────────┬────────────────────────────────────────┘
                         │ Lead comenta "CONTROL" o "CLARIDAD"
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  AUTOMATIZACIÓN MANYCHAT/META: DM automático con saludo         │
└────────────────────────┬────────────────────────────────────────┘
                         │ Lead responde al DM
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  M1 — Apertura + Pregunta de profesión/ingresos                 │
│  scripts/m1-apertura.md                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        Califica   Borderline   <$7M COP
              │          │          │
              │          │          ▼
              │          │     Descalificar
              │          │     scripts/descalificacion-con-valor.md
              ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│  M3 — Validación de dolor + opciones A/B/C/D  (antes M2)        │
│  scripts/m2-frustracion.md · precede: M2 Endeudamiento          │
└────────────────────────┬────────────────────────────────────────┘
                         │ Lead elige A, B, C o D válido
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  M4 — Empatía + pregunta de urgencia  (antes M3)                │
│  scripts/m3-urgencia.md                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │ "Es prioridad ahora"
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  M5 — Pitch de la llamada (chunking en 2 mensajes)  (antes M4)  │
│  scripts/m4-pitch-llamada.md → luego M6 Cierre + link           │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         "Sí, dale"   Objeción   No responde
              │          │          │
              │          ▼          ▼
              │   objection-handling/   Bumps 1, 2, 3
              │   7-objeciones-estandar.md   scripts/bumps-recuperacion.md
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  M6 — Cierre + link Calendly (chunking obligatorio, link al     │
│        final aislado)  (antes M5)                               │
│  scripts/m5-cierre-agendamiento.md                              │
└────────────────────────┬────────────────────────────────────────┘
                         │ Link enviado
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  M7 — Asistencia (solo o acompañado, DESPUÉS del link)          │
│  scripts/m7-asistencia.md                                       │
└────────────────────────┬────────────────────────────────────────┘
                         │ Lead vio el link (20-30 min sin respuesta)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  M5.5.a — "¿Pudiste agendar sin problema?"                      │
│  scripts/m5-5-confirmacion-post-calendly.md                     │
└────────────────────────┬────────────────────────────────────────┘
                         │ "Sí, ya agendé"
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  M5.5.b — "¿Te llegó el correo de confirmación?"                │
└────────────────────────┬────────────────────────────────────────┘
                         │ "Sí"
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  M5.5.c — Preguntas pre-llamada + "¡Nos vemos!"                 │
└────────────────────────┬────────────────────────────────────────┘
                         │ Lead agradece
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  M5.5.d — Agradecimiento + pregunta de blindaje del show-up     │
└────────────────────────┬────────────────────────────────────────┘
                         │ "Firme"
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  CONVERSACIÓN CERRADA CON ÉXITO ✅                              │
│  → Lead asiste a la llamada con Andrés (no es tu responsabilidad)│
└─────────────────────────────────────────────────────────────────┘
```

---

## KPIs vinculados al flujo

Cada etapa tiene un KPI que mide su salud:

| Etapa | KPI vinculado | Target | Acción si rojo |
|---|---|---|---|
| Reel → CONTROL | CP-L | <$10 USD | Andrés revisa creativos |
| M1 → respuesta | % Calificación | >40% | Andrés ajusta mensaje del ad |
| M4 → M5 (cierre) | **% Conversión a Agenda** | >60% | **Setter IA revisa M5 y manejo de objeciones** |
| M6/M7 → Llamada Agendada | % Show Up | >70% | M5.5.d (pregunta de blindaje) en todas |
| Llamada → Venta | % Cierre | >30% | Andrés ajusta pitch (no es tu KPI) |

Tu KPI principal es **% Conversión a Agenda** (de leads calificados que llegan a agendar).

---

## Tiempos de respuesta esperados

| Situación | Tiempo objetivo |
|---|---|
| Lead manda DM nuevo (M1) | <5 min en horario laboral, <30 min fuera |
| Lead responde a M2/M3/M4 | <10 min |
| M6 (link enviado) al lead | <2 min (el link debe llegar rápido) |
| Bump 1 después de M6 sin respuesta | 30 min después |
| M5.5.a (vio el link, no respondió) | 20-30 min después de "Visto" |
| Bump 2 | 24h después del Bump 1 |
| Bump 3 | 72h después del Bump 2 |

---

## Escalaciones a humano dentro del flujo

Ver detalle completo en `sops/sop-03-criterios-handoff-humano.md`. Los puntos del flujo donde más frecuentemente se escala:

- **M2-M3:** crisis emocional detectada (vs. motivación profunda).
- **M5:** objeción fuera del playbook estándar.
- **M5.5.a:** lead dice "ya no quiero agendar" + objeción tardía.
- **Cualquier momento:** lead pide hablar con humano explícitamente.
