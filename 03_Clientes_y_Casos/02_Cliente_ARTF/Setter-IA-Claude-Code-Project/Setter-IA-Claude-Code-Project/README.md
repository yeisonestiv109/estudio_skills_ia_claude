# Setter IA — Proyecto Claude Code

Proyecto operativo del **Agente Setter IA de Resuelve Tus Finanzas**, listo para abrir en Claude Code y empezar a responder DMs de Instagram con el flujo completo de calificación.

---

## ¿Qué es esto?

Este es el "cerebro operacional" del Setter IA modularizado en archivos de markdown que Claude Code puede leer rápidamente. La diferencia con el system prompt monolítico (`Prompt-Agente-Setter-IA-Instagram.md`) es que:

- **Prompt monolítico:** se usa para Claude API en producción (n8n, Make, etc.).
- **Este proyecto Claude Code:** se usa de forma asistida para responder DMs uno a uno, calibrar respuestas difíciles, manejar objeciones complejas, y entrenar al Setter humano.

Ambos comparten el mismo contenido. Cuando uno se actualiza, el otro debe actualizarse también.

---

## Cómo abrirlo en Claude Code

1. Abre tu terminal.
2. Navega a este folder:
   ```bash
   cd "/Users/javiersuarez/Documents/ARTF + C&J/ARTF + C&J/Setter IA/Claude-Code-Project"
   ```
3. Lanza Claude Code:
   ```bash
   claude
   ```
4. Claude Code cargará automáticamente `CLAUDE.md` como contexto base de cada conversación.

---

## Flujos de uso típicos

### 1. Responder un DM entrante
Pega el mensaje del lead (o el historial completo) y pide:
> "Responde este DM como Setter IA, devuélveme el JSON"

Claude leerá los scripts y reglas, identificará la etapa, y devolverá el JSON listo para copiar a producción o para que tú lo envíes manualmente.

### 2. Calibrar una respuesta difícil
> "¿Cómo respondo a esta objeción? [texto]"

Claude consulta el playbook de objeciones, decide si está cubierta o si toca handoff, y propone respuesta.

### 3. Registrar lead en Google Sheets
> "Registra este lead en el tracker: [datos]"

Claude armará el row con todas las columnas del Sheet de tracking. Si tienes el Sheet conectado vía MCP, lo actualiza directo.

### 4. Generar bump de recuperación
> "Genera el bump 2 para [Nombre], no respondió hace 24h"

Claude personalizará el script de bump.

### 5. Auditar conversación
> "Revisa esta conversación pasada y dime qué hubiéramos hecho diferente"

Claude analiza contra el playbook y propone mejoras.

### 6. Pulso semanal del Setter
> "Prepárame el reporte del Setter para el Pulso del lunes"

Claude estructura los KPIs (% Calificación, % Conversión a Agenda, % Show Up) con código de colores.

---

## Estructura del proyecto

```
Claude-Code-Project/
├── CLAUDE.md                            ← Memoria operativa (auto-cargada)
├── README.md                            ← Este archivo
├── knowledge-base/                      ← Contexto base permanente
│   ├── 01-identidad-y-mision.md
│   ├── 02-contexto-negocio.md
│   ├── 03-avatar-cliente-ideal.md
│   ├── 04-voz-y-tono.md                 ← CRÍTICO
│   └── 05-casos-exito.md
├── scripts/                             ← Mensajes por etapa (V4.2: M1→M7)
│   ├── m1-apertura.md                   ← M1 Ingreso
│   ├── m2-endeudamiento.md              ← M2 Endeudamiento ★ NUEVO V4.0
│   ├── m2-frustracion.md                ← M3 Dolor (nombre viejo)
│   ├── m3-urgencia.md                   ← M4 Urgencia (nombre viejo)
│   ├── m4-pitch-llamada.md              ← M5 Pitch (nombre viejo)
│   ├── m5-cierre-agendamiento.md        ← M6 Cierre + link (nombre viejo)
│   ├── m7-asistencia.md                 ← M7 Asistencia (post-link) ★ NUEVO V4.0
│   ├── m5-5-confirmacion-post-calendly.md
│   ├── bumps-recuperacion.md
│   └── descalificacion-con-valor.md
├── objection-handling/
│   └── 7-objeciones-estandar.md         ← 9 objeciones (V4.0)
├── sops/                                ← Procesos operativos
│   ├── sop-01-flujo-end-to-end.md
│   ├── sop-02-analisis-inicial-conversacion.md
│   ├── sop-03-criterios-handoff-humano.md
│   ├── sop-04-registro-google-sheets.md
│   └── sop-05-aprendizajes-produccion.md
├── templates/
│   ├── json-output-format.md
│   ├── google-sheets-tracker.md
│   └── handoff-message-template.md
└── examples/                            ← Conversaciones modelo
    ├── 01-lead-calificado-cierra.md
    ├── 02-lead-borderline-recuperado.md
    ├── 03-lead-descalificado-valor.md
    └── 04-objecion-precio-superada.md
```

---

## Setup recomendado (una sola vez)

1. **Conecta Google Sheets vía MCP** para que Claude pueda escribir/leer el tracker directamente.
   - Crea un Sheet con la estructura de `templates/google-sheets-tracker.md`.
   - Conecta el MCP de Google Sheets en Claude Code.
   - Pega el ID del Sheet en `templates/google-sheets-tracker.md` (campo `SHEET_ID`).

2. **Define el link de Calendly oficial** y reemplaza en `scripts/m5-cierre-agendamiento.md` y `objection-handling/7-objeciones-estandar.md` (actualmente está placeholder `https://calendar.app.google/iMW5LBbkcAvorypF9`).

3. **Reemplaza los `[LINK_REEL_RELEVANTE]`** en `scripts/descalificacion-con-valor.md` con los URLs reales de los reels de Andrés por dolor.

4. **Conecta el MCP de Monday.com** si querés que el Setter cree items en el board de leads (opcional, por ahora se usa Sheets).

---

## Actualización del proyecto

Cuando aprendas algo nuevo de producción (un patrón, una objeción nueva, una corrección de tono):

1. Actualiza el archivo correspondiente en el proyecto.
2. Actualiza también `Prompt-Agente-Setter-IA-Instagram.md` (el monolítico).
3. Documenta el aprendizaje en `sops/sop-05-aprendizajes-produccion.md`.

La regla: **toda mejora se integra en caliente y queda escrita en alguna parte. Memoria de Claude ≠ documentación.**

---

## Contacto

Owner: **Javier Suárez** — Director de Operaciones e IA.
Fuente de verdad: este folder + `/Users/javiersuarez/Documents/ARTF + C&J/ARTF + C&J/Setter IA/`
