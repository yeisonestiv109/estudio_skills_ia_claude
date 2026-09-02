# SOP-04 · Registro de Leads en Google Sheets

Cómo registrar cada lead conversado en el tracker de Google Sheets. La estructura del Sheet está en `templates/google-sheets-tracker.md`.

---

## Cuándo registrar

| Momento | Acción en el Sheet |
|---|---|
| **Primera respuesta del lead a M1** | Crear nueva fila con datos iniciales |
| **Después de cada turno con info nueva** | Actualizar columnas correspondientes |
| **Cuando se agenda llamada (post M5)** | Marcar fecha de agendamiento + estado "Agendado" |
| **Cuando se descalifica** | Marcar estado "Descalificado" + razón |
| **Cuando se escala a humano** | Marcar estado "Handoff" + razón |
| **Después del Bump 3 sin respuesta** | Marcar estado "Nurture largo plazo" |

---

## Datos a capturar por lead

### Columnas obligatorias
1. **Fecha de primer contacto** — cuándo entró el DM
2. **Nombre del lead** — extraído del perfil de IG o primer mensaje
3. **IG handle** — @username
4. **Palabra clave** — CONTROL / CLARIDAD / Otro
5. **Profesión** — de la respuesta a M1
6. **Ingreso aproximado COP** — de la respuesta a M1
7. **Dolor principal** — de M2 (A/B/C/D + descripción)
8. **Urgencia** — alta/media/baja, de M3
9. **Estado actual** — En conversación / Agendado / Descalificado / Handoff / Nurture
10. **Etapa última** — M1/M2/M3/M4/M5/M5.5.x
11. **Objeciones planteadas** — lista corta
12. **Razón si descalificado/handoff** — para análisis posterior
13. **Fecha de agendamiento** — si agendó, qué día/hora
14. **Link de la conversación IG** — para auditoría
15. **Notas adicionales** — cualquier patrón relevante

### Columnas calculadas (fórmulas en el Sheet)
- **Tiempo en conversación** — días desde primer contacto
- **¿Calificó?** — TRUE si financiera + dolor + urgencia están en verde
- **¿Convirtió a agenda?** — TRUE si estado = Agendado

---

## Cómo ejecutar el registro desde Claude Code

### Opción A — Sheets conectado por MCP

Si el MCP de Google Sheets está conectado y `SHEET_ID` está definido en `templates/google-sheets-tracker.md`:

```
"Registra este lead en el Sheet de tracking:
- Nombre: Daniela
- IG: @danielamp_
- Profesión: Ingeniera
- Ingreso: $7M COP
- Dolor: B (no sé en qué se va)
- Urgencia: alta
- Estado: En conversación
- Etapa: M3
- Notas: muy receptiva, mencionó comprar casa"
```

Claude usará la API de Sheets para agregar la fila directamente.

### Opción B — Sheets NO conectado (modo manual)

Si el MCP no está conectado, Claude te devolverá el bloque listo para pegar:

```
Fila para copiar al Sheet:

| 2026-05-22 14:32 | Daniela | @danielamp_ | CONTROL | Ingeniera | $7M | B - no sé en qué se va | alta | En conversación | M3 | - | - | - | [link IG] | Receptiva, mencionó comprar casa |
```

Lo copias y pegas como nueva fila en el Sheet.

---

## Actualización entre turnos

Cuando avances un lead de etapa, NO crees fila nueva — **actualiza la existente**.

Pídele a Claude:
```
"Actualiza la fila de Daniela: avanzó a M4, le pasé el pitch, sin objeciones todavía"
```

Claude buscará la fila por nombre + IG handle y actualizará solo las columnas que cambiaron.

---

## Reportes que el Sheet debe generar

Configura estas vistas/pivot en el Sheet para alimentar el Pulso Semanal:

1. **Conteo semanal de leads por estado**
   - X: Semana del año
   - Y: # de leads
   - Series: En conversación, Agendado, Descalificado, Handoff

2. **% Conversión a Agenda por semana**
   - Fórmula: `(# leads Agendados) / (# leads Calificados)`
   - Target: >60%

3. **Top dolores por frecuencia**
   - Qué dolor (A/B/C/D) es el más común
   - Sirve para que Andrés ajuste contenido

4. **Top objeciones por frecuencia**
   - Cuáles objeciones se repiten más
   - Sirve para mejorar el playbook

5. **Leads en Handoff por razón**
   - Identifica patrones que podrían integrarse al playbook (objeciones nuevas que ya son comunes)

---

## Integración con el Pulso Semanal

Los datos del Sheet alimentan directamente el reporte del Pulso Lunes:

- # de leads totales esta semana
- % Calificación (calificados / totales)
- % Conversión a Agenda (agendados / calificados)
- Top 3 dolores
- Top 3 objeciones
- # de handoffs y por qué

Claude puede generar este reporte automáticamente leyendo el Sheet:
```
"Genérame el reporte del Setter para el Pulso del lunes con los datos del Sheet"
```

---

## Datos sensibles — política de privacidad

- **No** registres conversaciones completas (texto del lead) en el Sheet. Solo metadata.
- **Sí** registra el link a la conversación de IG para auditoría posterior.
- **No** compartas el Sheet fuera del equipo de los 3 socios.
- Cualquier dato de salud/personal mencionado por el lead → omitir en el Sheet (queda solo en la conversación IG).
