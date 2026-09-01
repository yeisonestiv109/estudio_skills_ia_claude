# Bot ARTF — Nuevo Flujo Conversacional (Diseño, sin código)

**Estado: BORRADOR para iterar — NO es el spec final.** Ver también el tablero Miro
"Bot ARTF: Flujo Viejo vs Propuesta Nueva" (comparación visual old/new) y el post-mortem
verificado del bot viejo (sección 0).

## 0. Causa raíz confirmada (post-mortem)

Verificado directo en el Response Mapping visual de ManyChat: **no existía ningún nodo
que concatenara el historial.** ManyChat tomaba el campo `summary` que devolvía el Worker
(por instrucción del propio prompt, un resumen de 1-2 frases **del turno actual**) y
**sobrescribía directo** el custom field `conversation_summary`. En cada turno el bot
perdía todo el contexto histórico y solo recordaba el turno inmediatamente anterior.
Los parches repetidos "si `etapa_actual` está vacío, infiere igual" que aparecen en casi
cada escenario del prompt viejo existían precisamente para compensar esta pérdida.

**No era falta de arquitectura para tener memoria — era una sobrescritura destructiva en
un paso de mapeo de ManyChat.** El bot, aun así, funcionó y agendó leads reales: la
ingeniería del Worker (reintentos, timeouts, rescate de JSON, tagging) era sólida. El
punto débil específico era este.

**Corrección de raíz en el diseño nuevo:** ManyChat deja de ser responsable de guardar
NADA. Es un conducto ("dumb pipe"): recibe el mensaje del lead, se lo pasa al Worker con
`manychat_id` + `last_text`, y al final solo envía el texto que el Worker le da. Toda la
memoria — corta y larga — vive exclusivamente en Supabase, en modo *append-only* para el
historial (`activity_log`) y estado mutable versionado para el perfil (`gestion_leads`/`clientes`).

---

## 1. Reconstrucción del contexto (memoria corta y larga)

Al recibir el webhook (`manychat_id`, `last_text`), el Worker hace **una sola consulta
combinada** (o dos consultas paralelas) antes de decidir nada:

### Memoria a largo plazo — el perfil acumulado del lead
```
SELECT gl.id, gl.estado_id, e.codigo AS estado_codigo, gl.dolor, gl.urgencia,
       gl.califica, gl.handoff_razon, gl.version,
       c.id AS cliente_id, c.profesion, c.salario_monto, c.salario_periodicidad,
       c.ig_handle
FROM gestion_leads gl
JOIN clientes c ON c.id = gl.cliente_id
JOIN estados_lead e ON e.id = gl.estado_id
WHERE c.manychat_id = :manychat_id
ORDER BY gl.fecha_contacto DESC
LIMIT 1
FOR UPDATE
```
Esto YA es, en esencia, lo que hace `fn_sync_bot_turn` hoy (mismo patrón de
find-or-create + `FOR UPDATE` para evitar condiciones de carrera si 2 mensajes del mismo
lead llegan casi simultáneos). Esta consulta responde: *¿en qué paso del SOP estamos,
AHORA MISMO, según la base — no según lo que el LLM cree recordar?*

### Memoria a corto plazo — el historial literal (uso acotado, no "todo el tiempo")
**Corrección importante frente al planteamiento original:** dado que el estado de largo
plazo YA nos dice determinísticamente qué pregunta está pendiente (ej. si `estado_codigo
= contactado` y `dolor` está vacío, sabemos que estamos esperando la respuesta al
Mensaje 2 de endeudamiento — no hace falta adivinarlo leyendo texto crudo), **la mayoría
de los turnos NO necesitan inyectar transcripción histórica en ningún prompt.**

Sí construimos la capacidad de traer las últimas N filas de `activity_log`
(`ultimo_msg_lead`, `ultimo_msg_bot`, `created_at`, ordenado desc, límite ~4-6 turnos),
pero la usamos **solo** en los 2-3 puntos del SOP donde el texto reciente de verdad
aporta algo que un contador no puede:
- Clasificar si una objeción es la MISMA que ya se contestó antes (para la regla de
  "misma objeción 2 veces → handoff") — aunque esto en realidad se resuelve mejor con un
  **contador determinista** (`ultima_objecion_codigo`, `objeciones_consecutivas`) que
  mantenemos nosotros mismos en cada turno, sin que el LLM tenga que releer el historial.
- Detección de crisis emocional — ahí sí puede ayudar ver 1-2 turnos de contexto además
  del mensaje actual, porque un patrón (no una frase suelta) es más confiable.

**Conclusión de esta fase:** construimos el mecanismo de lectura de `activity_log`
porque es útil tenerlo disponible, pero el diseño NO depende de él para saber "en qué
paso estamos" — eso lo dice `gestion_leads`, siempre.

---

## 2. Ejecución del SOP V4.0 — el "cerebro"

### 2.1 Filtros determinísticos (sin LLM en el caso general)
Los 3 filtros del SOP (Ingreso ≥ $7M, Endeudamiento ≤ 50%, Urgencia = "ahora") más el
criterio nuevo de Datacrédito son **umbrales numéricos y listas de palabras clave** — no
necesitan interpretación abierta una vez que el número o la palabra clave está extraído.
El router determinista decide el siguiente paso comparando el dato extraído contra el
umbral, sin llamar al LLM.

### 2.2 Dónde SÍ entra el LLM — tareas acotadas, nunca "generar el mensaje"
**Este es el punto que marco como decisión abierta (ver sección 5) frente al
planteamiento original**, que pedía que el LLM devuelva directamente el `mensaje para el
usuario`. Mi recomendación, consistente con lo que ya te señalé sobre el bot viejo: el
LLM **clasifica y extrae**, nunca redacta lo que le llega al lead. Los guiones del SOP
son copy ya optimizado con anotaciones explícitas de "por qué funciona" — dejar que un
LLM los parafrasee es riesgo de conversión sin necesidad, y es exactamente el patrón que
falló antes (regla "PROHIBIDO CONCATENAR" del prompt viejo, señal de que ya pasó).

Casos concretos donde SÍ se llama a un LLM (siempre con salida JSON de esquema cerrado,
nunca texto libre):
| Paso del SOP | Qué clasifica/extrae el LLM | Salida (enum cerrado) |
|---|---|---|
| M1 (profesión + ingreso) | Extrae el número de ingreso y la profesión de texto libre | `{ingreso_cop_m: number\|null, profesion: string\|null}` |
| M2 (endeudamiento) | Extrae % o monto, y clasifica el bucket | `{pct: number\|null, bucket: "≤50"\|"50-70"\|">70"\|"no_sabe"}` |
| M2.5 (Datacrédito) | Clasifica sí/no/no sabe | `{tiene_reporte: true\|false\|null}` |
| Objeciones (cualquier etapa) | Matchea contra las 9 objeciones conocidas | `{objecion_num: 1-9\|null, es_conocida: bool}` |
| M3.B (beneficio propio) | ¿Nombró un beneficio concreto? | `{beneficio_concreto: bool, texto: string\|null}` |
| Cualquier turno | Señales de crisis emocional | `{crisis: bool}` (usa 1-2 turnos de contexto, ver sección 1) |

Bifurcaciones simples (urgencia "ahora" vs "algún día", confirmaciones tipo "ya agendé",
"asisto solo/acompañado") se resuelven con palabras clave — mismo criterio que ya usaba
el bot viejo en su "PASO DETECCIÓN", que de hecho funcionaba bien para esto.

### 2.3 El mensaje real siempre sale de una tabla determinista
Una vez que tenemos: `(estado_actual, clasificación_del_turno)` → una tabla de lookup
(en código o en una tabla de Supabase editable) decide `(estado_nuevo, plantilla_id)`.
La plantilla es el texto LITERAL del SOP V4.0 (M1-M8, las 9 objeciones, los 3 scripts de
descalificación, los 6 bumps de recuperación), con interpolación simple de `{nombre}`.
Cero riesgo de parafraseo, cero riesgo de concatenar 2 mensajes por error.

---

## 3. Guardado y sincronización (append-only, antes de responder)

Orden estricto, síncrono (a diferencia del Worker de captura pasiva, que sí es
fire-and-forget — aquí si la escritura falla no queremos responder algo que la base
nunca reflejó):

1. **Idempotencia primero:** igual que el bot viejo, cachear `(manychat_id, last_text)`
   por ~60s (Cloudflare Cache API) — si ManyChat reintenta el mismo webhook, devolvemos
   la respuesta ya calculada sin volver a escribir ni volver a llamar al LLM.
2. **Clasificación** (sección 2.2), si el paso la requiere.
3. **Lookup determinista** → `estado_nuevo` + `plantilla_id`.
4. **Escribir en Supabase, síncrono, en una función tipo `fn_sync_bot_turn` extendida:**
   - `UPDATE clientes` con los campos nuevos extraídos (profesión, salario, etc.).
   - `UPDATE gestion_leads` con endeudamiento_pct, datacredito_negativo,
     asiste_acompanado, ultima_objecion_codigo, objeciones_consecutivas — campos nuevos
     que hoy no existen, ver sección 6.
   - `fn_avanzar_estado(gestion_lead_id, estado_nuevo)` — reusa la función que YA
     valida transiciones legales contra `estado_transiciones`.
   - `INSERT INTO activity_log` con `ultimo_msg_lead`, `ultimo_msg_bot` (la plantilla ya
     resuelta), `summary`, `evento` — esto YA es el patrón append-only de
     `fn_sync_bot_turn`, solo lo extendemos.
5. **Solo después de que la escritura confirma éxito**, devolver el `msg` (texto de la
   plantilla) a ManyChat.
6. Si la escritura falla → responder con un mensaje de fallback seguro + marcar
   `handoff_humano=true` razón `error_tecnico` (mismo espíritu que el "REGLA DE ORO" del
   bot viejo: ante cualquier incertidumbre, fallback seguro, nunca dejar al lead sin
   respuesta ni arriesgar datos inconsistentes).

**Reutilización explícita:** no se construye un mecanismo de guardado desde cero —
`fn_sync_bot_turn` ya resuelve el 90% de esto (upsert de cliente, mapeo de fuente/
urgencia, find-or-create de `gestion_leads` con `FOR UPDATE`, avance vía
`fn_avanzar_estado`, log en `activity_log`). Se extiende con los parámetros nuevos.

---

## 4. Escalamiento seguro (handoff a humano)

**Corrección importante de alcance:** descalificar a un lead (ingresos bajos,
endeudamiento alto, sin urgencia, Datacrédito negativo) **NO es un handoff** — el SOP
tiene scripts propios para cada caso ("Descalificación con Valor") que el bot maneja
solo, sin intervención humana. Handoff es específicamente para cuando **el bot no puede
seguir el SOP con confianza por su cuenta**. Criterios, todos ya sea explícitos en el
SOP o extensiones razonables que dejo marcadas como tal:

| Razón (`handoff_razon`) | Origen | Disparador |
|---|---|---|
| `crisis_emocional` | SOP explícito | Clasificador de crisis = true, máxima prioridad, se evalúa primero que cualquier otra cosa |
| `pregunta_precio` | SOP explícito | Insiste en precio del programa una 2ª vez tras el script de manejo |
| `ex_cliente` | SOP explícito | Dice que ya fue cliente antes |
| `resistencia_repetida` | SOP explícito | Misma objeción 2 veces (contador determinista) |
| `resistencia_acumulada` | SOP explícito | 3+ objeciones consecutivas (contador determinista) |
| `objecion_fuera_playbook` | SOP explícito | El clasificador no matchea ninguna de las 9 objeciones conocidas |
| `agendamiento_manual_pendiente` | SOP explícito | Sub-flujo de agenda manual completado (fecha+correo+whatsapp capturados) |
| `ambiguo` | SOP explícito | Mensaje vacío, "?", o el router no puede decidir con confianza |
| `error_tecnico` | Nuevo (operacional) | Falla la escritura en Supabase, el LLM no devuelve JSON válido, o se agota el timeout |
| `contenido_hostil` ⚠️ **propuesta mía, no está en el SOP original** | Nuevo | Insultos o mensajes claramente abusivos — el SOP no lo contempla explícitamente, lo agrego por sentido común operativo. **Necesito tu confirmación antes de darlo por definitivo.** |

Mecánica de escalamiento (reusa lo que ya existe, no se inventa nada nuevo):
- `gestion_leads.handoff_razon` (columna que YA existe) + estado pasa a `calificado`
  (o `nutricion` si `crisis_emocional`) vía `fn_avanzar_estado` — mismo mapeo que
  `fn_sync_bot_turn` ya implementa hoy.
- Tag en ManyChat (`HANDOFF_ANDRES` + tag específica por razón) para que el Setter lo
  vea filtrando contactos, exactamente como ya lo hacía el bot viejo.
- El Setter lo ve en el dashboard (Incidencias/Pipeline, ya construido) y retoma desde
  ahí — el bot no vuelve a auto-responder a ese lead salvo que un humano lo reactive.

**Caso especial, no es handoff:** después del 3er bump de recuperación sin respuesta, el
lead pasa a "Nurture de largo plazo" — el bot deja de intentar, pero no es una
intervención humana urgente, es simplemente fin del intento activo.

---

## 5. Decisiones abiertas — necesito tu confirmación antes de dar esto por definitivo

1. **¿El LLM clasifica/extrae (mi recomendación) o genera el mensaje libre (como pedía
   el planteamiento original de esta tarea)?** Mantuve mi recomendación en este
   documento — plantillas literales, LLM nunca redacta lo que ve el lead — pero es tu
   llamada, no la tomé por mi cuenta.
2. **`contenido_hostil` como nueva razón de handoff** — no está en el SOP original, lo
   propongo yo. ¿Lo agregamos, o lo mapeamos a `ambiguo`/`objecion_fuera_playbook` en
   vez de crear una categoría nueva?
3. **Sigue pendiente** (de la conversación anterior, sin resolver): si el kill-switch de
   ManyChat (`EXISTENTE_CONVERSACION`) existía como nodo de Flow independiente mientras
   el bot viejo estaba ACTIVO, o si es una pieza que se agregó después, junto con el
   Worker de captura pasiva. Esto define si el bot nuevo necesita el mismo cambio de
   Flow que ya dejamos pendiente para la captura pasiva, o si ya hay una vía para que
   cada mensaje llegue al Worker.

---

## 6. Campos nuevos que necesita `gestion_leads` (para la Fase 3)

No existen hoy — se agregarían en una migración cuando pasemos a código:
`endeudamiento_pct numeric`, `datacredito_negativo boolean`, `asiste_acompanado
boolean`, `ultima_objecion_codigo text`, `objeciones_consecutivas smallint default 0`.
