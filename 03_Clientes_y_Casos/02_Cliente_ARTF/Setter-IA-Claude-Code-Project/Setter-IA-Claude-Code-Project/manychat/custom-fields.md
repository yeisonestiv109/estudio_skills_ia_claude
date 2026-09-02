# Custom Fields a crear en ManyChat

Estos son los campos personalizados que persisten el estado de cada lead entre turnos. Crear en **Settings → Custom Fields** antes de armar el flujo.

## Campos del lead (Contact-level)

| Nombre del campo | Tipo | Valor inicial | Descripción |
|---|---|---|---|
| `etapa_actual` | Text | `M1` | Última etapa del flujo (V4.2): M1, M2, M3, M4, M5, M6, M7, M7.B, M5.5.a, M5.5.d, Bump1_General, Bump2_General, Bump3_General, Bump1_Agendamiento, Bump2_Agendamiento, Bump3_Agendamiento, Handoff, Descalificado, Agendado |
| `profesion` | Text | (vacío) | Profesión del lead — ej: "Médico", "Contadora", "Ingeniero" |
| `ingreso_mensual_cop_M` | Number | 0 | Ingreso mensual en millones COP — ej: 8.5 |
| `endeudamiento_pct` | Number | 0 | % de endeudamiento reportado en M2 — ej: 35 ★ NUEVO V4.0 |
| `asiste_acompanado` | Text | (vacío) | `si`, `no`, `desconocido` — validado en M7 ★ NUEVO V4.0 |
| `dolor_opcion` | Text | (vacío) | A, B, C, o D |
| `dolor_descripcion` | Text | (vacío) | Texto libre del dolor — ej: "saco créditos para pagar otros" |
| `urgencia` | Text | `desconocida` | `ahora`, `algun_dia`, `desconocida` |
| `califica` | Boolean | `false` | true si pasa el filtro de avatar |
| `objeciones_planteadas` | Text | (vacío) | CSV de objeciones — ej: "Obj1,Obj7" |
| `handoff_humano` | Boolean | `false` | true → notificar a Andrés/Javier |
| `razon_handoff` | Text | (vacío) | Por qué se escaló |
| `caso_exito_usado` | Text | (vacío) | `Carlos`, `Sandra`, `ninguno` |
| `historial_resumido` | Text | (vacío) | Resumen comprimido de los últimos 3 turnos (Claude lo actualiza cada vuelta) |
| `agendamiento_fecha` | Text | (vacío) | Si el lead agendó manualmente, fecha + hora |
| `agendamiento_email` | Text | (vacío) | Email para invitación manual |
| `agendamiento_whatsapp` | Text | (vacío) | WhatsApp para contacto |
| `claude_response_json` | Text | (vacío) | Output crudo de Claude para parseo |
| `fecha_ultimo_mensaje_setter` | DateTime | (vacío) | Timestamp del último mensaje enviado por el Setter — base para bumps |
| `nurture_largo_plazo` | Boolean | `false` | true después del Bump 3 sin respuesta |

## Campos del bot (Bot-level, opcionales)

Para controlar capacidad y métricas globales:

| Nombre | Tipo | Descripción |
|---|---|---|
| `cupos_disponibles_semana` | Number | Si Andrés tiene <5, el Setter usa escasez en M5 |
| `total_agendamientos_dia` | Number | Counter — para dashboard |
| `total_descalificados_dia` | Number | Counter |
| `total_handoffs_dia` | Number | Counter |

---

## Tags a crear (en lugar de algunos boolean fields)

ManyChat también usa **tags** como categorización. Conviene crear:

- `CALIFICA` — lead que pasó M1
- `M5_PITCH_ENVIADO` — para activar bumps de agendamiento
- `M6_LINK_ENVIADO` — para activar M5.5.a si vio el link
- `AGENDADO` — confirmado en Calendly
- `HANDOFF_ANDRES` — notificar a Andrés
- `NURTURE_LARGO_PLAZO` — después de Bump 3 final
- `DESCALIFICADO_INGRESO` — <$7M
- `DESCALIFICADO_ENDEUDAMIENTO` — endeudamiento por encima de su tope ★ NUEVO V4.0
- `DESCALIFICADO_TIMING` — "para algún día"

---

## Cómo poblar los campos desde la respuesta de Claude

Después de cada llamada a Claude, ManyChat parsea `claude_response_json` y actualiza:

```
etapa_actual ← claude_response_json.etapa_nueva
profesion ← claude_response_json.metadata.profesion
ingreso_mensual_cop_M ← claude_response_json.metadata.ingreso_mensual_cop_M
dolor_opcion ← claude_response_json.metadata.dolor_opcion
urgencia ← claude_response_json.metadata.urgencia
califica ← claude_response_json.califica
handoff_humano ← claude_response_json.metadata.handoff_humano
caso_exito_usado ← claude_response_json.metadata.caso_exito_usado
```

Luego envía los mensajes del array `mensaje_para_lead` uno por uno con un delay corto (1-2s) entre ellos para que se vean naturales.
