# Auditoría de arquitectura — Bot conversacional ARTF V4.2

> Respuesta a la propuesta de pivote a "LLM como Evaluador de Filtros"
> (Vercel AI SDK + `generateObject`, router pasivo, playbook en el system prompt).
> **4-sep-2026.** Escrita después de verificar la premisa contra el código real.

---

## 0. Veredicto en una línea

**Se rechaza el pivote tal como está planteado. Se aceptan 2 de sus 5 componentes.**
El diagnóstico apuntaba al órgano equivocado —la arquitectura no era lo que estaba
fallando—, pero el dolor era real y venía de un **agujero de cobertura**, no de un
límite de diseño.

---

## 1. La premisa, verificada

La propuesta parte de: *"si el usuario responde con variables no esperadas (ej.
montos de dinero en lugar de porcentajes)… el LLM devuelve null. Como resultado,
el código JS falla o escala a un humano prematuramente."*

**El síntoma era cierto. La causa atribuida, no.** Al probar `clasificar()`
directamente aparecieron **dos bugs P0**, ambos en la capa determinista y ninguno
arquitectónico:

### Bug 1 — `ReferenceError: limpio is not defined`

En `clasificar()`, la rama de M2 leía un `limpio` que solo existe dentro de
`validarClasificacionLLM` (copy-paste). Resultado: **toda respuesta en
`M2_ENVIADO` y `M2_NO_SABE` reventaba** — es decir, el Filtro 2 completo, para
todos los leads.

El crash ocurre en el paso 3 del handler, **antes de la escritura síncrona del
paso 5**. O sea: el turno no se registraba en la base, la etapa no avanzaba, y el
lead recibía `FALLBACK_ERROR` con handoff `error_tecnico`. **Exactamente el
síntoma reportado.**

### Bug 2 — la plata se leía como porcentaje

`detectarEndeudamientoPct("pago 2 millones al mes en deudas")` devolvía **`2`**.
El fallback de "número suelto" agarraba el `2`. Y como los deterministas **ganan**
sobre el LLM en la fusión, el `deuda_cop` correcto del LLM quedaba tapado.

Esto es **peor que escalar**: 2 % es un endeudamiento excelente, así que el lead
**pasaba el Filtro 2 en silencio con un dato inventado**. Sin error, sin handoff,
sin rastro.

Lo irónico: la conversión monto→% **ya estaba implementada y correcta** en el
router (`deuda_cop / ingreso × 100`, más la variante por remanente). Nunca llegó a
ejecutarse.

### Lo que sí es un problema real de diseño

**El agujero de cobertura.** 207 tests hoy; hasta esta sesión eran 183, con
type-check verde, verificador de cumplimiento verde y smoke en vivo verde —
y **`clasificar()`, que corre en cada turno, tenía cero tests**.

La razón es estructural: los tests del router entran por `decidirTurno(estado,
pistas, texto)` con las pistas **ya clasificadas**, saltándose la capa de
clasificación entera. El simulador hace lo mismo. La compuerta verificaba
brillantemente la mitad del sistema.

> **Esa es la lección que hay que llevarse, y no es "cambiemos de framework".**

---

## 2. Análisis componente por componente de la propuesta

### 2.1 `respuesta_generada` — **RECHAZADO, y es el punto que hunde la propuesta**

Que el LLM redacte lo que ve el lead rompe cuatro cosas que hoy sostienen el
sistema:

**a) Reabre una decisión cerrada del fundador.** Empatía apagada, *"parece mucha
IA"*. Está en `PROGRESS.md` bajo "Decisiones cerradas (no volver a abrir)". La
propuesta no matiza esa decisión: la invierte y la multiplica.

**b) Reabre toda la superficie de inyección de prompt.** Hoy el único texto libre
del LLM que puede llegar al lead es `oracion_empatia`: máximo 200 caracteres,
saneado por `sanearEmpatia`, y **actualmente apagado**. Con `respuesta_generada`,
el 100 % de lo que el lead lee es salida del modelo condicionada por texto que el
lead controla. **Y este bot envía un link de calendario.** Un lead que logre
sustituir ese link tiene un vector de phishing sobre un embudo real. No es
hipotético: el prompt actual ya tiene una sección de seguridad precisamente
porque el equipo lo consideró.

**c) Borra la compuerta 3.** `verificador_cumplimiento.js` funciona comparando cada
burbuja contra `HUELLAS_APROBADAS`, una lista blanca **derivada de la biblioteca
de plantillas**. Si el LLM redacta, no hay huella contra la cual comparar. Habría
que reemplazar un chequeo determinista por un LLM-juez: más lento, con costo por
turno, no determinista, y **imposible de correr en cada commit**.

Recordar qué atrapó esa compuerta: el bug del link, **confirmado en producción por
el equipo de Javier**, que **52 tests y el type-check no vieron**. Es el artefacto
más valioso del repo. La propuesta lo entrega.

**d) Rompe el corpus.** `tests/corpus/*.json` afirma sobre strings exactos
(`contiene` / `no_contiene`). Con prosa generada esas aserciones se vuelven
semánticas y frágiles. Se evapora la suite que codifica cada fallo real: Marly, la
lead de $22M, el saludo roto.

### 2.2 `estado_siguiente` decidido por el LLM — **RECHAZADO**

La máquina de etapas se enforza en **cuatro** sitios, uno de ellos un CHECK de
Postgres (`fn_etapa_bot_valida`). La base es la última línea de defensa, y la
memoria del proyecto ya registra que olvidar uno de esos cuatro sitios **apagó en
silencio la detección de crisis en 3 etapas**.

Además existe la guarda dura de `agendado`: el bot **nunca** puede declarar que
alguien agendó. Un modelo que emite `estado_siguiente` eventualmente emitirá
`agendado`. La base lo rechazaría — bien — pero pasas de "nunca se le pregunta" a
"la base atrapa errores del modelo en cada turno".

En un embudo que hay que poder auditar frente al cliente, **las transiciones de
estado son código**.

### 2.3 `supera_filtro` como booleano del LLM — **RECHAZADO en esa forma, pero acá está tu razón**

Los tres filtros son **umbrales numéricos** (ingreso ≥ $7M; tope de deuda según
ingreso; urgencia ∈ enum). Eso es aritmética, y la aritmética va en código: un
modelo que devuelva `supera_filtro: true` para un lead de $6.9M es un error de
negocio que ningún test atrapa.

**Pero la extracción que alimenta esos umbrales sí es un problema de lenguaje**, y
ahí es donde el sistema estaba débil — es literalmente donde vivían los dos P0.

> El corte correcto no es *"el LLM evalúa el filtro"*.
> Es ***"el LLM normaliza a valores tipados; el código evalúa el umbral"*.**

Que es lo que la arquitectura ya decía hacer, y que los bugs impedían.

### 2.4 `razonamiento_interno` — **ACEPTADO, pero por otra razón**

Es barato y útil, pero **no como palanca de precisión**: con `temperature: 0` y
un esquema JSON estricto, el patrón "CoT dentro de un campo JSON" aporta poco
comparado con razonamiento real.

Su valor acá es **auditabilidad para el cliente**: escrito en
`activity_log.payload`, le da al Setter el rastro de *por qué* el bot hizo lo que
hizo. Adóptalo como artefacto de auditoría, no como mejora de accuracy.

### 2.5 Vercel AI SDK + `generateObject` + Zod — **ACEPTADO**

Acá voy a ser franco en la otra dirección: **esta parte es una mejora real y hay
que tomarla** — pero es mucho más pequeña de lo que crees. **No es un pivote: es
cambiar de librería en ~80 líneas.**

Lo que hay hoy es, literalmente, un Zod mal hecho a mano:

| Hoy | Con AI SDK |
|---|---|
| `ESQUEMA_POR_ETAPA`: el esquema como **string** dentro de un template literal | una declaración Zod |
| `response_format: {type:'json_object'}` — garantiza JSON válido, **no TU JSON** | decodificación restringida al esquema |
| `parseJsonLLM` con fallback por regex para desenterrar un `{...}` de la prosa | innecesario |
| `validarClasificacionLLM` — 45 líneas de coerción a mano | `.transform()` / `.refine()` |

Gana además que el esquema pasa a ser **fuente única de verdad**, y la trampa
documentada de *"una etapa nueva necesita 4 sitios"* pierde uno.

**Condiciones para que no sea un retroceso:**
- **Conservar los clamps de negocio** de `validarClasificacionLLM` (0 ≤ pct ≤ 100,
  coerción de enums, rango de `objecion_num`). Zod valida forma; no sabe que un
  150 % de endeudamiento es absurdo.
- **Conservar la degradación a `{}`**: si el parseo falla, el turno lo lleva la
  capa determinista. Ese `catch → {}` de hoy es correcto y debe sobrevivir.
- **Verificar antes de comprometerse**: que el modelo actual (`qwen/qwen3.8-27b`
  vía Groq) soporte structured outputs con el SDK, y **medir el bundle**. Hoy son
  23.5 KB gzip con arranque en frío de 6 ms; eso es parte del presupuesto.

### 2.6 Memoria corta: últimos N mensajes del `activity_log` — **ACEPTADO, acotado**

Segunda buena idea, y la que priorizaría después del SDK. Pero acotada:

- **Solo al clasificador.** Nunca a un generador (no hay generador).
- **Arregla un hueco real y nombrado**: hoy `objeciones_consecutivas` cuenta, pero
  el clasificador no ve *qué* objetó antes. `resistencia_repetida` se detecta por
  contador, no por contenido. Con historial se distingue "repite la misma
  objeción" de "objeción nueva".
- **En la misma RPC.** Extender `fn_bot_get_estado` para devolver los últimos N
  turnos, no agregar un segundo viaje: estás en un Worker con presupuesto de
  latencia y ManyChat esperando.
- **El historial es texto controlado por el lead** → entra con los mismos
  delimitadores `<mensaje_lead>` y nunca alcanza nada que emita texto.

> Nota crítica: el historial es seguro **porque** rechazaste `respuesta_generada`.
> Las dos propuestas están acopladas.

### 2.7 Playbook de objeciones en el system prompt — **RECHAZADO**

El playbook es copy aprobado por el cliente en `sop_v42_plantillas.js`, y las
variantes pre-pitch se **derivan por código** (`sinCierreDeAgenda`) justamente para
que no puedan desincronizarse del original. Moverlo al prompt implica:

- cambiar copy exige deploy **y** re-evaluación, en vez de editar un archivo que la
  compuerta lee;
- el truco de derivación (recortar N párrafos) pasa de ser código a ser una
  instrucción que un modelo puede ignorar;
- `HUELLAS_APROBADAS` deja de poder construirse desde la biblioteca.

La **selección** ("¿cuál objeción es esta?") ya es trabajo del LLM y ahí se queda.
El **texto** se queda en código. Esa separación es la razón por la que el sistema
actual es defendible frente al cliente.

---

## 3. Alternativas de industria — qué aplica y qué no

Lo que tienes ya es, en el vocabulario actual, **un workflow, no un agente**. La
guía de Anthropic (*Building Effective Agents*) es explícita: para tareas con
pasos bien definidos hay que preferir workflows, y en particular el patrón
**routing** (clasificar la entrada y despachar a un handler especializado). Un
embudo con SOP estricto y filtros numéricos es el caso de manual para **no**
entregarle el control de flujo a un modelo.

**Patrones que sí vale la pena tomar:**

| Patrón | Estado |
|---|---|
| Structured output / decodificación restringida | 👉 tomarlo (§2.5) |
| Router + tabla de transiciones determinista | ✅ ya lo tienes, conservar |
| Escalamiento a humano por baja confianza | ⚠️ existe, pero **binario**: hoy `null` → escalar. Falta una señal de confianza para distinguir *"ambiguo, repregunto"* de *"fuera del playbook, escalo"* |
| Suite de evals sobre corpus dorado | ✅ ya lo tienes — y estás **por delante** de la mayoría. Solo falta que cubra el clasificador |

**Lo que NO aplica, y conviene decirlo:**

- **LangGraph / orquestadores de grafo de estado.** Tu máquina de estados son 17
  etapas con un CHECK de Postgres enforzándola y un dashboard leyéndola.
  LangGraph agregaría una **segunda** noción de estado en proceso que habría que
  reconciliar con la de la base. Terminarías manteniendo dos máquinas de estado.
  Su historia en Workers además es pobre.
- **Multi-agente / frameworks de handoff (Swarm, CrewAI).** Nada acá es
  paralelizable ni separable por roles. Una conversación, un guion. Overhead puro.
- **Loop de agente con tool-calling.** El bot no tiene herramientas que llamar:
  tiene un guion que seguir. Un loop metería un número de pasos no determinista en
  un Worker con presupuesto de CPU y un timeout de ManyChat.

---

## 4. Diseño objetivo

```
ManyChat ──► Worker (Cloudflare)
                │
                ├─1─ leerEstado()  ── fn_bot_get_estado ──► Supabase
                │     └─ devuelve estado + últimos N turnos   (§2.6)
                │
                ├─2─ CLASIFICADOR  ◄── única pieza con LLM
                │     ├─ deterministas primero (glosario COP, letras, sí/no)
                │     │   └─ ganan SOLO donde están seguros ── ese "solo"
                │     │      es el Bug 2: abstenerse > adivinar
                │     └─ LLM → generateObject(Zod)            (§2.5)
                │         · normaliza a valores TIPADOS
                │         · union discriminada para dinero    (§5, paso 3)
                │         · objeción / crisis / hostil / ex-cliente
                │         · razonamiento_interno → activity_log (§2.4)
                │         · falla ⇒ {} y el turno lo lleva lo determinista
                │
                ├─3─ ROUTER (bot_router_v42.js) ── 100 % determinista
                │     · aritmética de los 3 filtros
                │     · transiciones de etapa
                │     · selecciona PLANTILLAS APROBADAS (nunca redacta)
                │
                ├─4─ verificador_cumplimiento ── compuerta 3, sobre la salida real
                │
                ├─5─ escritura SÍNCRONA ── fn_bot_procesar_turno ──► Supabase
                │     · CHECK de etapa + guarda dura de `agendado`
                │
                └─6─ envío a ManyChat (link SIEMPRE última burbuja, solo)
```

**La línea que no se cruza:** el LLM solo escribe en el paso 2, y solo produce
**datos tipados**. Del paso 3 en adelante todo es determinista, verificable y
testeable sin red.

---

## 5. Plan de refactor, por valor/riesgo

| # | Cambio | Por qué primero |
|---|---|---|
| **1** | **Cerrar el agujero de cobertura.** Una compuerta que corra cada conversación del corpus por `clasificar → decidirTurno`, no solo `decidirTurno` con pistas | **Es lo que habría atrapado los dos P0 de hoy.** Costo casi nulo, valor máximo. Hecho parcialmente: `clasificar` ya tiene tests |
| **2** | Cambiar el JSON a mano por **AI SDK `generateObject` + Zod** | Borra `parseJsonLLM`, unifica el esquema, quita un sitio de la trampa de los 4 |
| **3** | **Unión discriminada para dinero vs. porcentaje** en el esquema: `{tipo:'porcentaje',valor}` \| `{tipo:'deuda_mensual_cop',cop}` \| `{tipo:'remanente_cop',cop}` \| `{tipo:'no_sabe'}` | Convierte "respondió con plata" en un **caso representado** en vez de un accidente. Es el arreglo de fondo del Bug 2 |
| **4** | **Memoria corta** (últimos N turnos) dentro de `fn_bot_get_estado`, solo al clasificador | Arregla `resistencia_repetida` por contenido, no por contador |
| **5** | Señal de **confianza** del clasificador para separar "repregunto" de "escalo" | Hoy el escalamiento es binario y por eso se siente prematuro |
| **6** | `razonamiento_interno` → `activity_log.payload` | Auditabilidad para el Setter |

**No se toca:** router dueño de transiciones y aritmética · 100 % copy aprobado al
lead · `verificador_cumplimiento` como compuerta 3 · deterministas ganando donde
están seguros.

---

## 6. La conclusión incómoda

La arquitectura no era frágil. **La verificación lo era.** Y la propuesta de
pivote habría cambiado la mitad sana del sistema —la que ya atrapó un bug real de
producción que 52 tests no vieron— dejando intacta la mitad que fallaba.

Peor: con `respuesta_generada` los dos bugs de hoy **no habrían sido detectables**.
El Bug 2 no lanza excepción; califica un lead con un dato inventado, en silencio.
Se encontró porque existe una capa determinista a la que se le puede hacer
`assert.equal(detectarEndeudamientoPct('pago 2 millones'), null)`.

**El determinismo no es la deuda técnica de este sistema. Es su instrumentación.**


---

# ANEXO — Segunda ronda: RAG de objeciones, tool calling y escalamiento restringido
**4-sep-2026, después de implementar.**

## A.1 La premisa, verificada otra vez

> *"si el lead dice 'gano el mínimo integral' (que en Colombia son +13 millones)… el sistema actual colapsa o lo malinterpreta"*

**Falso.** `parseIngresoCOP` trata `integral` **primero**, antes que cualquier otra regla:

```
"gano el minimo integral" → {monto: null, ambiguo: true, glosario: "salario_integral"}
"gano el minimo"          → {monto: 1420000, glosario: "salario_minimo"}
```

Nunca descalifica; pide la cifra. Es la lección de la lead de $22M, arreglada en V4.1, con corpus propio. **El glosario nunca fue lo que falló** — fallaron un `ReferenceError` y un detector que adivinaba.

Y el caso del calendario **ya hacía exactamente lo pedido**: `P.SIN_HORARIOS` pregunta por la franja y escala en el mismo turno.

## A.2 Veredicto por componente

| Propuesta | Veredicto |
|---|---|
| **Tool calling** para el glosario | ❌ Añade un viaje redondo (modelo→tool→modelo) dentro del timeout de ManyChat para consultar una tabla estática de 20 líneas. Tool calling es para cuando el modelo debe *actuar* o traer algo que no puede saber. Va en el system prompt — y la mitad ya estaba ahí |
| **Enrutamiento semántico → `template_id`** | ✅ **Implementado.** Con enum cerrado; un id desconocido cae a fallback determinista y nunca se emite |
| **Repositorio en Supabase** | ❌ **JSON/JS en el repo.** La compuerta 3 construye `HUELLAS_APROBADAS` desde la biblioteca, offline, en cada commit. Con el copy remoto: o metes red en los unit tests (y tu compuerta depende de que un servicio esté arriba), o dejas de verificar el texto real. Peor: una fila editada pone copy sin aprobar frente a leads sin ninguna revisión |
| **Escalamiento restringido** | ✅ **Implementado, con una corrección** (ver A.4) |
| **3 intentos de parafraseo** | ⚠️ Parafrasear con el LLM = el LLM redactando al lead = lo que se rechazó en §2.1. Los peldaños son plantillas de la biblioteca |

## A.3 El playbook como tabla de datos

`PLAYBOOK_OBJECIONES` reemplaza 4 sitios sueltos. Todo se deriva:

```
PLAYBOOK_OBJECIONES  ──┬──► OBJECIONES              (mapa id → plantilla)
  {id, nombre,         ├──► OBJECIONES_HABILITADAS  (la perilla)
   disparador,         ├──► OBJECIONES_PRE_PITCH    (recorte por código)
   plantilla,          ├──► DISPARADORES_OBJECIONES ──► prompt del clasificador
   habilitada,         └──► OBJECIONES_CON_PREGUNTA_PROPIA
   cortePrePitch,
   preguntaPropia}
```

**Agregar una objeción = agregar una entrada.** Hay tests que verifican que las 5 derivaciones no se desincronizan, que el recorte pre-pitch sigue siendo un **prefijo** del copy aprobado (o sea, recorte y no reescritura), y que toda objeción habilitada emite copy aprobado en todas las etapas.

### Bug latente que esto destapó

El barrido de la It. 6 solo miró las objeciones que llevaban **link** (2, 3, 6) y se saltó la **1**, que ya estaba habilitada y cerraba agenda en M1 con *"Sin presión. ¿Te parece?"* — a un lead que no había pasado ningún filtro, y con dos preguntas seguidas. **Un cierre de agenda no necesita link para serlo.** La compuerta ahora barre las 9 × 4 etapas y lo reconoce por la frase.

## A.4 La escalera: se midió antes de construirla

La intuición era poner reintentos en los 5 sitios que escalaban por ambigüedad. Al medir:

| Filtro | Preguntas antes de escalar (antes) | ¿Necesitaba peldaño? |
|---|---|---|
| M1 (ingreso) | 2 — `M1_ENVIADO` → `M1_INGRESO_AMBIGUO` → handoff | No |
| M2 (deuda) | 2 — `M2_ENVIADO` → `M2_NO_SABE` → handoff | No |
| M3 (dolor) | El lead ya confirmó dos veces que no es financiero | No: es decisión de fit, no ambigüedad |
| **M4 (urgencia)** | **1** | **Sí** |
| **M5 (pitch)** | **1** | **Sí** |

**La escalera son 2 peldaños, no 5.** Detrás de `ESCALERA_REPREGUNTAS_HABILITADA = false` hasta que Javier apruebe el copy nuevo (`COPY_PENDIENTE_APROBACION`, fijado por un test para que copy sin aprobar no entre solo a la lista blanca).

**Guarda anti-bucle:** la etapa de reintento cae en el mismo `case` que su etapa madre. Sin `etapa !== 'M4_URGENCIA_REINTENTO'`, el bot ofrecería el reintento para siempre y el lead **nunca** llegaría a un humano. Tiene test propio.

## A.5 Lo que NO se tocó, y por qué

- **Escaladas de seguridad** (`crisis_emocional`, `contenido_hostil`, `ex_cliente`): intactas. Crisis es la regla de máxima prioridad del diseño y cubre señales de duelo, ansiedad y autolesión.
- **`resistencia_repetida` / `resistencia_acumulada`**: son reglas del SOP del cliente. Los umbrales se subieron a 3 y 4 por decisión del fundador — **⚠️ eso contradice el PDF V4.2 y hay que comentárselo a Javier.**
- **`objecion_fuera_playbook`**: sigue yendo a un humano. Es lo correcto: el bot no sabe qué es.

## A.6 La trampa de los 4 sitios, por fin verificable

Las etapas nuevas obligaron a cerrarla del todo:

| Sitio | Antes | Ahora |
|---|---|---|
| CHECK de la base | el smoke probaba 4 etapas | prueba **las 18 que el router puede escribir** |
| `ESQUEMA_POR_ETAPA` | sin cobertura — ya apagó crisis en 3 etapas | test que exige esquema con `crisis`/`hostil`/`objecion_num` en toda etapa conversacional |
| `preguntaPendiente` | sin cobertura | test por etapa nueva |
| el `switch` | sin cobertura | test por etapa nueva |

## A.7 Lo que sigue

1. **Javier aprueba** el copy de los 2 peldaños → encender la perilla.
2. **Comentarle a Javier** los umbrales de resistencia (contradicen su PDF).
3. **AI SDK + Zod** (§2.5): sigue siendo la mejora correcta y sigue siendo ~80 líneas. Verificar antes que Groq soporte structured outputs con el modelo actual, y medir el bundle.
4. **Memoria corta** (§2.6) dentro de `fn_bot_get_estado`.
5. **Señal de confianza** del clasificador para separar "repregunto" de "escalo".
