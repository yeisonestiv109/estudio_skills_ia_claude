# Template · Google Sheets Tracker de Leads

Estructura del Google Sheet donde se registra cada lead que entra al Setter IA.

---

## Setup inicial

### 1. Crear el Sheet
- Nombre sugerido: **"RTF · Setter IA · Pipeline de Leads"**
- Owner: Javier Suárez
- Compartido con: Andrés, Catalina (editor)
- Carpeta: Drive compartido de Resuelve Tus Finanzas

### 2. `SHEET_ID` activo:

```
SHEET_ID:  1iYLMAYV0XtN74ALBCmJkszUOpoINIt5tEs2CKGMvaf0
SHEET_URL: https://docs.google.com/spreadsheets/d/1iYLMAYV0XtN74ALBCmJkszUOpoINIt5tEs2CKGMvaf0/edit
TAB_GID_DEFAULT: 1344498607
```

Este es el CRM activo de Resuelve Tus Finanzas, ya probado en producción. Claude Code puede leerlo/escribirlo vía MCP de Google Drive / Sheets cuando esté conectado.

---

## Estructura de columnas

| # | Columna | Tipo | Ejemplo | Notas |
|---|---|---|---|---|
| A | Fecha primer contacto | Datetime | 2026-05-22 14:32 | Timezone Bogotá |
| B | Nombre lead | Texto | Daniela | Sin apellido en MOST cases |
| C | IG handle | Texto | @danielamp_ | Con @ |
| D | Palabra clave | Texto | CONTROL | CONTROL / CLARIDAD / Otro |
| E | Profesión | Texto | Ingeniera | De M1 |
| F | Ingreso aproximado COP | Texto | $7M | Texto, no número (puede ser "$5M-$7M") |
| G | Calificación financiera | Texto | Calificado | Calificado / Borderline / Descalificado / Desconocido |
| H | Dolor principal | Texto | B - no sé en qué se va | Letra de M2 + descripción |
| I | Calificación dolor | Texto | Calificado | Calificado / Descalificado / Desconocido |
| J | Urgencia | Texto | Alta | Alta / Media / Baja |
| K | Calificación urgencia | Texto | Calificado | Calificado / Descalificado / Desconocido |
| L | Etapa última | Texto | M5 | M1, M2, M3, M4, M5, M5.5.a, M5.5.b, M5.5.c, M5.5.d, Bump1, Bump2, Bump3, Handoff, Descalificado |
| M | Estado actual | Texto | Agendado | En conversación / Agendado / Asistió / No asistió / Descalificado / Handoff / Nurture largo plazo |
| N | Objeciones planteadas | Texto | "Precio (Obj 5)" | Lista separada por comas |
| O | Razón handoff/descalif | Texto | objecion_fuera_playbook | De catálogo de razones |
| P | Fecha agendamiento | Datetime | 2026-05-24 11:00 | Cuando aplique |
| Q | Link conversación IG | URL | https://instagram.com/direct/t/... | Para auditoría |
| R | Notas | Texto | "Muy receptiva, mencionó comprar casa" | Cualquier patrón relevante |
| S | Tiempo en conversación | Fórmula | =TODAY()-A2 | Días desde primer contacto |
| T | ¿Calificó? | Fórmula | =IF(AND(G2="Calificado",I2="Calificado",K2="Calificado"),TRUE,FALSE) | Auto |
| U | ¿Convirtió a agenda? | Fórmula | =IF(M2="Agendado",TRUE,FALSE) | Auto |
| V | ¿Asistió? | Fórmula | =IF(M2="Asistió",TRUE,FALSE) | Auto |

---

## Validación de datos (Data Validation)

Configura en el Sheet:

| Columna | Tipo | Valores válidos |
|---|---|---|
| D Palabra clave | List | CONTROL, CLARIDAD, Otro |
| G Calificación financiera | List | Calificado, Borderline, Descalificado, Desconocido |
| I Calificación dolor | List | Calificado, Descalificado, Desconocido |
| J Urgencia | List | Alta, Media, Baja, Desconocida |
| K Calificación urgencia | List | Calificado, Descalificado, Desconocido |
| L Etapa última | List | M1, M2, M3, M4, M5, M5.5.a, M5.5.b, M5.5.c, M5.5.d, Bump1, Bump2, Bump3, Handoff, Descalificado |
| M Estado actual | List | En conversación, Agendado, Asistió, No asistió, Descalificado, Handoff, Nurture largo plazo |

---

## Semaforización (Conditional Formatting)

### Columna G (Calificación financiera)
- Calificado → 🟢 verde claro
- Borderline → 🟡 amarillo claro
- Descalificado → 🔴 rojo claro

### Columna J (Urgencia)
- Alta → 🟢 verde claro
- Media → 🟡 amarillo claro
- Baja → 🔴 rojo claro

### Columna M (Estado actual)
- Agendado / Asistió → 🟢 verde
- En conversación → 🔵 azul claro
- Handoff → 🟡 amarillo
- Descalificado / No asistió / Nurture → 🔴 rojo claro

### Columna S (Tiempo en conversación)
- 0-2 días → 🟢
- 3-7 días → 🟡
- 8+ días sin estado final → 🔴 (revisar — debería haber pasado a otro estado)

---

## Pestañas adicionales

### Pestaña 2 — "Dashboard semanal"

Tabla pivot con:
- Conteo de leads por estado (esta semana, semana pasada, mes)
- % Calificación = (Calificados) / (Total)
- % Conversión a Agenda = (Agendados) / (Calificados)
- % Show Up = (Asistió) / (Agendados)
- Top 3 dolores
- Top 3 objeciones
- Top 3 razones de handoff

### Pestaña 3 — "Histórico mensual"

Snapshot mensual de los KPIs para tracking longitudinal.

### Pestaña 4 — "Catálogo de razones"

| Razón handoff | Conteo |
|---|---|
| objecion_fuera_playbook | (fórmula COUNTIF) |
| solicitud_humano_explicita | ... |
| crisis_emocional | ... |
| ... | ... |

Esto te permite ver qué objeciones nuevas están apareciendo y agregarlas al playbook.

---

## Fórmulas clave

```
# % Calificación
=COUNTIF(G:G,"Calificado")/(COUNTIF(G:G,"Calificado")+COUNTIF(G:G,"Borderline")+COUNTIF(G:G,"Descalificado"))

# % Conversión a Agenda (entre calificados)
=COUNTIFS(M:M,"Agendado")/COUNTIF(G:G,"Calificado")

# % Show Up
=COUNTIF(M:M,"Asistió")/COUNTIF(M:M,"Agendado")

# Lead más viejo sin cerrar
=MAX(S:S) donde M:M="En conversación"
```

---

## Workflow operativo

### Cada vez que entra un lead nuevo
1. Claude/Setter humano captura datos básicos (A-D).
2. Después de M1, completa E-G.
3. Después de M2, completa H-I.
4. Después de M3, completa J-K.
5. Avanza columna L y M a medida que el flujo avanza.

### Cuando el lead agenda
- Estado M → "Agendado"
- Columna P → fecha/hora de la cita
- Tiempo en S se mide hasta este punto

### Cuando el lead asiste
- Estado M → "Asistió"
- Después de la llamada, Andrés actualiza si cerró venta (en otro Sheet de ventas).

### Cuando el lead no asiste
- Estado M → "No asistió"
- Se puede contactar para reagendar 1 vez.

---

## Integración con MCP

Cuando el MCP de Google Sheets esté conectado, puedes pedirle a Claude:

```
"Lee el Sheet de leads y dime cuántos están En conversación sin avanzar hace más de 3 días"
"Agrega a [Nombre] al Sheet con estos datos: ..."
"Actualiza la fila de [Nombre]: pasó a M4"
"Genera el reporte del Pulso semanal con los datos del Sheet"
```
