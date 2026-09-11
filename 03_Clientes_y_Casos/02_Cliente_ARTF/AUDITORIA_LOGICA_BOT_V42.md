# Auditoría de la lógica del bot V4.2 — de la arquitectura al guion

**Fecha:** 11-sep-2026 · **Base:** código en `setup/base-conocimiento` @ `6abd18d` (incluye los fixes de Gabyota del 11-sep)
**Todo lo que sigue sale de leer el código actual, no de la memoria de sesiones anteriores.**

---

## 1. Arquitectura: el viaje de un mensaje

```
 Lead escribe en Instagram
        │
        ▼
 ManyChat (Flow) ──External Request──►  WORKER  artf-bot-setter-v42  (Cloudflare)
                                          │
   0. Autenticación del webhook ──────────┤  sin secreto → 401
   0b. Lista blanca (modo prueba) ────────┤
   1. Idempotencia (reintentos de ManyChat)
   2. leerEstado()  ──────────────────────┼──►  Supabase  fn_bot_get_estado
      decidirSiResponder()  ── ¿el bot habla o ya es turno del Setter?
      leerHistorial()  ── últimos 6 turnos de activity_log
   3. clasificar()  ───────────────────────┼──►  Groq (LLM)  ← ENTIENDE el mensaje
   4. decidirTurno()  ── router determinista  ← DECIDE qué hacer
      4c. guarda anti-repetición + verificador de copy  ← FILTRA lo que sale
   5. escribirTurno() SÍNCRONO ───────────┼──►  Supabase  fn_bot_procesar_turno
      (si falla, el lead NO recibe nada)          (valida la etapa, guarda estado)
        │
        ▼  respuesta a ManyChat → el lead recibe los mensajes
   6. En segundo plano (nunca retrasan la respuesta):
      tags de ManyChat · alerta a Google Chat · caché
```

### Quién hace qué

| Pieza | Archivo | Rol | Tamaño | Tests |
|---|---|---|---|---|
| **Worker** | `worker_bot_setter_v42.js` | Orquesta: auth, estado, LLM, escritura, efectos | 1.833 líneas | 87 (seguridad) |
| **Router** | `bot_router_v42.js` | **Decide**: los 3 filtros y la máquina de 25 etapas | 2.179 líneas | 200 |
| **Plantillas** | `sop_v42_plantillas.js` | **Habla y mide**: todo el copy, umbrales e interruptores | 1.379 líneas | — |
| **Verificador** | `verificador_cumplimiento.js` | **Filtra**: nada sale si no es copy aprobado o pasa las reglas G1–G10 | 447 líneas | 69 |
| **LLM** | `llm_groq.mjs` | Pool de llaves con failover | 112 líneas | 12 |
| **Alertas** | `notificador_google_chat.js` | Mensaje al Setter en cada handoff | 169 líneas | 18 |
| **Base** | `fn_bot_procesar_turno`, `fn_etapa_bot_valida` | Guarda el estado y **rechaza etapas que no conoce** | SQL | — |

**Total: 535 tests, compuerta `./verificar.sh`.**

### La división del trabajo (y por qué está bien)

- **El LLM entiende, el código decide.** El LLM extrae cifras, detecta objeciones y lee el tono. El router, con esos datos, hace la aritmética y elige la etapa. El LLM nunca decide si un lead califica.
- **La capa de regex de negocio se eliminó el 6-sep.** Tomaba la primera cifra de "4 millones del trabajo, 3 del negocio…" y descalificaba a leads que sí calificaban, sin avisar. Ahora la extracción la hace el LLM. Fue la decisión correcta: 6 de los 12 bugs de estas sesiones venían de ahí.
- **Escritura síncrona, efectos en segundo plano.** Si Supabase falla, el lead no recibe un mensaje que la base no registró. Los tags y las alertas no pueden trabar la respuesta.

---

## 2. La lógica de negocio, tal como corre hoy

```
 M1  Filtro 1 — INGRESO
      ├─ dio cifra ≥ $6M ............................ pasa
      ├─ dio cifra < $6M ............................ DESCALIFICADO
      └─ no dio cifra → "¿estás entre $7M y $15M?"
            ├─ Sí → pasa (se registra $7M, ingreso_confirmado=false)
            └─ No → DESCALIFICADO   ⚠️ corte real: $7M, no $6M
 M2  Filtro 2 — ENDEUDAMIENTO (% del ingreso que se va en cuotas)
      ├─ ≤ tope (50% si gana < $9M · 60% si gana ≥ $9M) ... pasa
      ├─ dio el SALDO total en vez de la cuota ......... M2_DEUDA_TOTAL (aclara)
      └─ > tope → M2_VERIFICAR_CALCULO ("¿seguro? revisemos la cuenta")
            ├─ corrige y entra en su tope ................ pasa
            ├─ le sobran ≥ $2,5M al mes ................. pasa (rescate)
            └─ ratifica → M2_BORDERLINE
                  ├─ la mayoría es deuda buena (vivienda) o sobran ≥ $2,5M ... pasa
                  └─ si no ......................................... DESCALIFICADO
 M3  Filtro 3 — DOLOR (A/B/C/D)  →  M4 URGENCIA  →  M5 PITCH
 M6  link del calendario  →  M7 asistencia / acompañante  →  cierre
      "no veo horarios" → pide franja → HANDOFF al Setter (UNA alerta)
```

**Regla de oro en todo el embudo:** nunca se descalifica sobre un vacío. Si falta el dato, se pregunta.

---

## 3. Hallazgos

### 🔴 H1 — Dos umbrales de ingreso, y el que parece activo no lo está

`calificacion_dinamica.js` dice `INGRESO_MINIMO: 4_500_000` con `activo: true`. **Nadie lo importa**: solo su propio test. El que manda es `UMBRALES.INGRESO_MINIMO = 6_000_000` en `sop_v42_plantillas.js`.

**Riesgo:** alguien cambia el 4,5M creyendo que cambia el bot (no pasa nada), o lo "conecta" pensando que es una mejora y baja el piso a 4,5M sin que nadie lo haya decidido. El modelo sale de los 50 casos del experto y dice que 6M está *fuera* de la banda admisible: es una recomendación válida, pero no está aplicada. **Hay que decidir:** se conecta (y se baja el piso, con OK del fundador) o se marca claramente como experimento no conectado.

### 🔴 H2 — "Solo 6M en adelante" es verdad a medias

- Con cifra, el corte es $6M.
- **Sin cifra, el corte es $7M.** La pregunta del rango dice "$7M a $15M" y un "No" descalifica directo. Quien gana $6,5M y responde "No" se pierde.
- El mensaje de descarte (`DESC_INGRESO`) le dice al lead que el programa es "para personas que ganan **más de $7M**" aunque el corte sea 6M.

Esto es una **decisión comercial del 4-sep** (preferir perder la franja 6–7M a gastar un turno pidiendo la cifra), y hay un test que la fija a propósito. No es un bug, pero conviene tenerla presente cada vez que alguien diga "el bot admite desde 6M".

### 🟠 H3 — Los comentarios mienten sobre las reglas más importantes

En este código los comentarios hacen de documentación, y en tres sitios dicen lo contrario de lo que hace el código:

| Dónde | Qué dice | Qué hace |
|---|---|---|
| `sop_v42_plantillas.js:217-229` (UMBRALES) | "un 'No' al rango NO descalifica: se le pide la cifra" | Descalifica directo (decisión del 4-sep) |
| `bot_router_v42.js:170` (`evaluarIngreso`) | "Filtro 1: ingreso >= $7M" | Compara contra $6M |
| `bot_router_v42.js:196-212` (docstring del Filtro 2) | Regla del remanente ≥ $2,5M / 50% | Tope por ingreso 50% / 60% |

Quien lea el comentario y no el código tomará decisiones equivocadas.

### 🟠 H4 — Código muerto en el Filtro 2

`evaluarEndeudamiento` solo devuelve `ok`, `verificar_calculo` o `no_sabe` desde el 7-sep. Pero `evaluarYResponderEndeudamiento` (`bot_router_v42.js` ~508-535) conserva ramas para `'borderline'` y `'descalifica'` que **ya no se ejecutan**. Hoy no rompen nada; confunden porque parece que el Filtro 2 descalifica en el primer paso, y no lo hace.

(La regla del remanente de $2,5M **sigue viva**: es la vía de rescate en `M2_VERIFICAR_CALCULO` y `M2_BORDERLINE`.)

### 🟠 H5 — `decidirTurno` es una sola función de 1.017 líneas

25 etapas en un único `switch` (líneas 551–1568). Cambiar una etapa exige entender el switch entero, y los errores de orden (una condición evaluada antes que otra) son la clase de bug más repetida del proyecto: el fix #1 de Gabyota del 11-sep fue exactamente eso. La red que lo sostiene son los 200 tests del router. No es urgente partirla, pero cada etapa nueva la hace más frágil.

### 🟡 H6 — Editar una plantilla la aprueba automáticamente

La lista blanca del verificador (`HUELLAS_APROBADAS`) se arma sola a partir de todo lo que hay en `P`. Ventaja: no hay una segunda lista que mantener. Consecuencia: la compuerta protege contra que **el LLM** invente texto, no contra que **una persona** pegue en `P` copy que Javier no aprobó. El control real de copy son las marcas `_pendienteAprobacion` + `COPY_PENDIENTE_HABILITADO = false` (hoy hay 4 plantillas esperando y están apagadas).

### 🟡 H7 — Operación

- Hay un cambio sin commitear en `worker_bot_setter_v42.js` (añade `bot_activo` a las respuestas JSON).
- Producción corre `6236373f` (11-sep 18:49). Si ese deploy salió con el cambio sin commitear, lo que está en Cloudflare no está en git.

### ✅ Lo que está bien y conviene no tocar

LLM que entiende y código que decide · escritura síncrona antes de responder · efectos en segundo plano · idempotencia · lista blanca y modo secretaria · compuerta con 535 tests · "nunca descalificar sobre un vacío".

---

## 4. Dónde se cambia cada cosa

| Quiero cambiar… | Archivo | Qué tocar |
|---|---|---|
| **Un número** (umbral de ingreso, tope de deuda, remanente, resistencia) | `sop_v42_plantillas.js` | `UMBRALES` (línea ~216) |
| **El texto de un mensaje** | `sop_v42_plantillas.js` | `P.NOMBRE_DEL_MENSAJE`. Si es copy nuevo: marcar `P.X_pendienteAprobacion = true` y pedir OK a Javier |
| **Una objeción** (texto, en qué etapas aplica, si cuenta como resistencia) | `sop_v42_plantillas.js` | `PLAYBOOK_OBJECIONES` |
| **Encender o apagar un comportamiento** | `sop_v42_plantillas.js` | `EMPATIA_HABILITADA`, `CATCHALL_LLM_HABILITADO`, `COPY_PENDIENTE_HABILITADO`, `ESCALERA_REPREGUNTAS_HABILITADA` |
| **Qué hace el bot con una respuesta** (el flujo) | `bot_router_v42.js` | El `case 'ETAPA'` dentro de `decidirTurno` |
| **Qué entiende del mensaje** (qué extrae el LLM) | `worker_bot_setter_v42.js` | Prompt y esquema de `clasificarConLLM` (~línea 847) |
| **Una etapa nueva** | `bot_router_v42.js` **+ migración** | El `case` nuevo + migración en `Tarea_1_Migrar_DB/migraciones/` que la agregue a `fn_etapa_bot_valida`. Sin la migración, la base la rechaza |
| **La alerta al Setter** | `notificador_google_chat.js` | `construirMensajeHandoff` |
| **Encender o apagar el bot** | Cloudflare | Variable `BOT_ACTIVO` (`"false"` = modo secretaria: escucha y registra, no habla) |

**Después de cualquier cambio, siempre:** ajustar o agregar el test → `./verificar.sh` en verde → commit → `npx wrangler deploy`.

---

## 5. Receta: el caso "admitir solo leads con $6M en adelante"

`UMBRALES.INGRESO_MINIMO` **ya está en 6.000.000.** Lo que falta es que el resto del guion hable el mismo idioma. Hay dos caminos:

### Opción A — Dejarlo como está (decisión vigente del 4-sep)

No se toca nada. Se acepta que el corte real es $6M con cifra y $7M sin cifra.

### Opción B — Que sea $6M de verdad para todos

Hay que tocar **estas piezas juntas**, porque están encadenadas y un test vigila cada una:

| # | Qué | Dónde | Por qué |
|---|---|---|---|
| 1 | Texto del rango: `$7M` → `$6M` | `P.M1_PEDIR_RANGO` y `P.M1_PEDIR_RANGO_SIMPLE` (`sop_v42_plantillas.js:342-344`) | Es la pregunta que decide a quien no dio cifra. **Copy nuevo: necesita OK de Javier** |
| 2 | Cifra asumida: `7_000_000` → `6_000_000` | `UMBRALES.INGRESO_ASUMIDO_POR_RANGO` | Va atada al texto del rango: es "el piso de lo que el lead dijo". Un test exige que no quede por debajo del mínimo |
| 3 | Mensaje de descarte: "más de $7M" → "$6M" | `P.DESC_INGRESO` (`sop_v42_plantillas.js:749`) | Si no, al lead de $5M se le dice una cifra que no es la real. **También necesita OK de Javier** |
| 4 | Actualizar el test "Banda de trampa" | `tests/bot_router_v42.test.js` ~1362-1400 | Hoy fija a propósito el desalineamiento. Cambia porque se cambia la regla a propósito, que es la única excepción a "no se reescriben tests" |
| 5 | Decidir qué pasa con `calificacion_dinamica.js` | ese archivo | Ver H1: sigue diciendo 4,5M |
| 6 | Arreglar el comentario de `UMBRALES` y el de `evaluarIngreso` | ver H3 | Para que el próximo que lea no se confunda |
| 7 | `./verificar.sh` → commit → deploy | — | — |

**No hace falta tocar:** el motivo de pérdida que se guarda en la base (`Descalificado - Ingreso bajo (< $6M)`) ya se arma solo a partir de `INGRESO_MINIMO`.

**Si algún día se baja de $6M:** revisar el Filtro 2. El rescate por remanente de $2,5M empieza a pesar más con ingresos bajos (con $5M y 50% de deuda quedan justo $2,5M).
