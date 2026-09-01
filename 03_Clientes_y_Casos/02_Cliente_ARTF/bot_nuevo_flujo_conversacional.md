# Bot ARTF — Nuevo Flujo Conversacional (Diseño Definitivo v2 — SOP V4.2)

**Estado: IMPLEMENTADO (1-sep-2026).** El diseño dejó de ser solo diseño: las
migraciones están aplicadas y el Worker está escrito y probado. Ver
`GUIA_DESPLIEGUE_BOT_V42.md` para el paso a paso de despliegue y pruebas.

> **v2 — actualizado al SOP V4.2 (1-sep-2026).** Cambios que invalidan partes de
> la v1 de este documento:
> - **Datacrédito sale de la precalificación.** El flujo pasa de 8 a 7 mensajes y
>   de 4 a 3 filtros. Ya NO existe el paso "M2.5 (Datacrédito)" de la tabla 2.2,
>   ni la columna `datacredito_negativo` de la sección 6.
> - **Se reordena el cierre:** ahora **M6 = cierre + link** y **M7 = pregunta de
>   asistencia** (antes era al revés). La regla de aislamiento del link aplica a
>   M6, no a "M5/M8" como decía la v1.
> - **Tope de endeudamiento condicional al ingreso:** ≤50% si gana ~$7M, hasta
>   60% si gana >$9M (antes era 50% fijo).
> - **Nuevo: glosario de ingreso colombiano + regla anti-descarte** (V4.1). Nunca
>   se descalifica sobre un ingreso ambiguo; el descarte por ingreso es de 2
>   pasos. Motivado por un caso real: se descartó a una lead de $22M porque dijo
>   "gano el mínimo integral" y el bot leyó "mínimo".
> - **Nuevo: RetornoLead.** Un lead ya descartado que se recalifica se rectifica
>   solo, sin humano y sin revelar que es IA.

**Implementación:**
`Scrips_Worker_and_AppScript/{sop_v42_plantillas.js, bot_router_v42.js, worker_bot_setter_v42.js}`
+ 52 tests en `tests/` + migraciones `artf-pipeline-app/supabase/migrations/20260901*`.

Ver también el tablero Miro "Bot ARTF: Flujo Viejo vs Propuesta Nueva" (comparación
visual old/new) y el post-mortem verificado del bot viejo (sección 0).

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

### 2.2 Dónde entra el LLM — clasificación/extracción + **empatía dinámica acotada**
**Resuelto (sección 5): enfoque híbrido.** El LLM clasifica y extrae en JSON de esquema
cerrado (igual que en la v0), **y además** genera un campo `oracion_empatia` — máximo
1-2 oraciones reconociendo el dolor/lo que el lead acaba de decir, en tuteo colombiano.
El Worker arma el mensaje final como `oracion_empatia + "\n\n" + plantilla_SOP_exacta`.
El lead siente que lo escucharon; la pregunta/pitch real sigue siendo el copy exacto y
probado del SOP — nunca se parafrasea.

**Salvaguardas necesarias para que esto no reintroduzca el riesgo que motivó la
recomendación original** (el LLM sigue generando texto que el lead SÍ va a leer, solo
que ahora acotado a 1-2 frases en vez de todo el mensaje):
- **Reusar las 2 reglas innegociables del prompt viejo** para la generación de
  `oracion_empatia` específicamente: Regla 1 (primera persona, nunca hablar de "Andrés"
  en tercera persona) y Regla 2 (tuteo colombiano estricto, lista de regionalismos y
  palabras prohibidas — "barato", "sacrificio", "dieta financiera", "ahorro hormiga",
  etc.). Sin este guardrail explícito en el prompt del clasificador, la empatía dinámica
  puede colar exactamente el tipo de desliz de marca que el playbook prohíbe.
- **Límite duro de caracteres** en el Worker (ej. `.slice(0, 220)`), no solo confiar en
  la instrucción del prompt — mismo criterio defensivo que ya usaba el bot viejo con
  `msg.slice(0, 700)`.
- **Fallback silencioso:** si la generación de `oracion_empatia` falla o se demora, el
  Worker envía SOLO la plantilla, sin bloquear ni escalar a handoff por esto — la
  empatía es un plus, nunca un punto único de falla del turno.
- **Un solo llamado al LLM por turno**, no dos: cuando el paso ya requiere clasificar
  (tabla de la sección 2.2), `oracion_empatia` se pide en el MISMO JSON de esa llamada.
  Cuando el paso es 100% determinista (ej. confirmación de agendado, "ya agendé"), este
  sí sería un llamado nuevo solo para la empatía — **a confirmar con el fundador si vale
  la pena en esos pasos mecánicos, o si ahí se envía la plantilla sola** (ver nota al
  final de esta sección).
- **Excepción obligatoria — mensajes del calendario (M5/M8):** el SOP exige que el link
  vaya SIEMPRE aislado, sin texto pegado en el mismo turno (Instagram puede romper el
  link). Para estos mensajes específicos, si se genera `oracion_empatia` se envía como
  burbuja SEPARADA antes del link — nunca concatenada en el mismo mensaje.

Casos concretos donde el LLM clasifica/extrae + genera empatía (JSON de esquema
cerrado, el campo `oracion_empatia` se suma a todos estos):
| Paso del SOP | Qué clasifica/extrae el LLM | Salida (enum cerrado) |
|---|---|---|
| M1 (profesión + ingreso) | Extrae el número de ingreso y la profesión de texto libre | `{ingreso_cop_m: number\|null, profesion: string\|null, oracion_empatia: string}` |
| M2 (endeudamiento) | Extrae % o monto, y clasifica el bucket | `{pct: number\|null, bucket: "≤50"\|"50-70"\|">70"\|"no_sabe", oracion_empatia: string}` |
| M2.5 (Datacrédito) | Clasifica sí/no/no sabe | `{tiene_reporte: true\|false\|null, oracion_empatia: string}` |
| Objeciones (cualquier etapa) | Matchea contra las 9 objeciones conocidas | `{objecion_num: 1-9\|null, es_conocida: bool, oracion_empatia: string}` |
| M3.B (beneficio propio) | ¿Nombró un beneficio concreto? | `{beneficio_concreto: bool, texto: string\|null, oracion_empatia: string}` |
| Cualquier turno | Señales de crisis emocional | `{crisis: bool}` (sin empatía — si hay crisis, el handoff toma prioridad total, no se genera texto adicional) |

Bifurcaciones simples (urgencia "ahora" vs "algún día", confirmaciones tipo "ya agendé",
"asisto solo/acompañado") se resuelven con palabras clave — mismo criterio que ya usaba
el bot viejo en su "PASO DETECCIÓN". **Nota pendiente de tu confirmación:** en estos
pasos puramente mecánicos, ¿vale la pena un llamado extra al LLM solo por la
`oracion_empatia`, o se envía la plantilla sola? Mi recomendación es plantilla sola —
son confirmaciones cortas donde la empatía agrega poco y cuesta latencia/tokens — pero
lo dejo a tu criterio.

### 2.3 El mensaje real siempre sale de una tabla determinista
Una vez que tenemos: `(estado_actual, clasificación_del_turno)` → una tabla de lookup
(en código o en una tabla de Supabase editable) decide `(estado_nuevo, plantilla_id)`.
La plantilla es el texto LITERAL del SOP V4.0 (M1-M8, las 9 objeciones, los 3 scripts de
descalificación, los 6 bumps de recuperación), con interpolación simple de `{nombre}`.
El mensaje final = `oracion_empatia` (si aplica y no es M5/M8) + la plantilla exacta.
Cero riesgo de parafraseo en la parte que importa (la pregunta/pitch), cero riesgo de
concatenar 2 plantillas por error.

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
| `contenido_hostil` ✅ **confirmado** | Nuevo, aprobado | Insultos o mensajes claramente abusivos — no está en el SOP original, pero aprobado explícitamente: no tiene sentido gastar tiempo/créditos con trolls, el Setter decide qué hacer desde el dashboard |

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

## 5. Decisiones resueltas (v0 → v1)

1. **✅ Resuelto — Enfoque híbrido:** el LLM clasifica/extrae y además genera
   `oracion_empatia` (1-2 frases), pero la pregunta/pitch real SIEMPRE sale de la
   plantilla literal del SOP. Ver sección 2.2 para las salvaguardas que agregué (reusar
   las reglas de tuteo/palabras prohibidas del prompt viejo, límite de caracteres,
   fallback si falla, excepción para los mensajes de calendario M5/M8).
2. **✅ Resuelto — `contenido_hostil` confirmado** como razón oficial de handoff. Ver
   sección 4.
3. **✅ Resuelto — ManyChat pasa a ser un tubo 100% abierto.** No importa si el
   kill-switch existía antes o después del bot viejo (ya no es relevante) — para el bot
   nuevo, ManyChat envía TODOS los mensajes al Worker, sin ninguna regla de Flow que
   bloquee turnos subsecuentes. La idempotencia (caché de 60s ante reintentos por
   latencia) sigue viviendo en el Worker, tal como se planteó en la sección 3.

### ✅ RESUELTO en la v2 — lo resolvió el propio playbook V4.2

La pregunta de abajo (¿qué hace el bot con un lead en estado terminal que vuelve
a escribir?) quedó resuelta sin necesidad de criterio propio, porque **el SOP
V4.2 la responde para el caso más importante**: exige que un lead ya descartado
que se recalifica sea rescatado automáticamente, "sin humano y sin revelar que es
IA" (RetornoLead). O sea que `descalificado` NO puede tratarse como puerta
cerrada.

Regla final implementada en `decidirSiResponder()`:
- `ganado`, `perdido`, `nutricion` → el bot **no responde**, solo registra.
- `agendado`, `show_up`, `oferta_presentada`, `seguimiento`, … (dominio del
  Setter/Closer) → el bot **no responde**, solo registra.
- `handoff_razon` no nulo → el bot **no vuelve a hablar** hasta que un humano lo
  limpie.
- `descalificado` → **sí escucha**, pero únicamente para el RetornoLead: si el
  mensaje trae una cifra de ingreso que ahora califica, rectifica y retoma en M2;
  cualquier otra cosa solo se registra.

Texto original del hallazgo, que se conserva por trazabilidad:

### Hallazgo nuevo que esta resolución destapa — necesita tu confirmación
Abrir el tubo 100% resuelve el problema de continuidad, pero crea uno que el
kill-switch viejo resolvía sin que nadie lo pidiera explícitamente: **hoy nada impide
que un lead en estado TERMINAL** (`ganado`, `perdido`, `descalificado`, `nutricion`)
escriba meses después (ej. "gracias!", o un comentario viejo que dispara alguno de los 7
triggers de nuevo) **y el router intente correr el SOP desde M1 otra vez** sobre un lead
que ya cerró su ciclo.

La caché de 60s de idempotencia NO cubre este caso — esa caché es para reintentos
inmediatos del MISMO mensaje, no para "este lead ya terminó su recorrido hace tiempo".

**Mi recomendación:** el router (sección 2.1), antes de cualquier otra cosa, revisa si
`estado_actual` es terminal. Si lo es, el bot **no vuelve a correr el SOP** — solo
registra el mensaje en `activity_log` (visibilidad para el equipo) y no responde nada
automático, o responde con un acuse breve neutro y tag para que un humano decida si
quiere reabrir la conversación. Me inclino por "no responder nada, solo loguear" como
default más seguro (evita reabrir una venta ya cerrada de forma rara), pero es tu
llamada — dímelo antes de que lo lleve a la migración/código.

---

## 6. Campos de `gestion_leads` — APLICADO (migración `20260901120000`)

Lo que efectivamente se agregó (difiere de lo planeado en la v1):

| Columna | Por qué |
|---|---|
| `etapa_bot text` | **La más importante, no estaba en el plan v1.** Sin ella el Worker no sabe en qué pregunta del SOP va: `estado_id` no alcanza porque `contactado` cubre de M1 a M5. Tiene CHECK con las 14 etapas válidas |
| `endeudamiento_pct numeric` | Filtro 2 |
| `ingreso_confirmado boolean` | **Nueva, no estaba en el plan v1.** Regla anti-descarte V4.1: distingue "aún no le pedí la cifra" de "ya se la pedí y sigue ambigua" |
| `asiste_acompanado boolean` | M7 |
| `ultima_objecion_codigo text` | Regla "misma objeción 2 veces" |
| `objeciones_consecutivas smallint` | Regla "3+ objeciones consecutivas" |
| ~~`datacredito_negativo`~~ | **NO se agregó:** V4.2 elimina Datacrédito de la precalificación |

**Lo que NO hubo que crear porque ya existía** (hallazgo al revisar el esquema
real, ahorró trabajo): `calendario_enviado_at`, `bump_tipo`, `bump_numero`,
`motivo_perdida_id` (+ 3 motivos nuevos insertados), `ultima_actividad_at`,
`total_interacciones`, y los estados `mensaje_enviado_espera`/`ghosteo_bump`.

También se agregaron las 6 columnas nuevas a la whitelist del rol `setter` en
`fn_columnas_por_rol()`: sin eso el Setter humano no podría corregir a mano lo
que el bot extrajo mal — que es justo la convivencia que se busca.

## 7. Funciones nuevas (aplicadas)

- **`fn_bot_get_estado(manychat_id)`** — lectura del contexto completo en una
  sola llamada. Devuelve 0 filas si el lead no existe.
- **`fn_bot_procesar_turno(...)`** — escritura del turno. A diferencia de
  `fn_sync_bot_turn`, el estado destino lo manda el Worker **explícito** en vez
  de inferirse de un `CASE` en plpgsql: esa duplicación entre código y SQL fue
  justo la que produjo el bug del 29-ago (`else 'nuevo'` regresaba leads
  agendados a `nuevo`).
  **Guarda dura:** rechaza `agendado` con excepción. El único dueño de ese estado
  es la sincronización de Google Calendar — verificado con una prueba que
  confirma que la excepción salta.

Ambas con `revoke` a `public/anon/authenticated` y `grant` solo a `service_role`
(la lección de `vw_show_ups`, 31-ago). Confirmado en los advisors: no aparecen
como ejecutables por usuarios logueados.
