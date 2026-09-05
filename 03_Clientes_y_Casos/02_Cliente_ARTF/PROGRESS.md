# PROGRESS — estado del loop del bot ARTF

> El órgano "estado" del loop (ver `LOOPS.md`). Qué se intentó, qué falló y qué
> queda. Se actualiza en cada iteración para no repetir errores ni perder el hilo.
>
> **Para retomar en una sesión nueva, empieza por `RETOMAR_AQUI.md`.**

**Compuerta:** `./verificar.sh` · **Última corrida: VERDE** (4-sep-2026) · **346 tests** · **5 de 5 compuertas corridas de verdad**
**Estado del bot: DESPLEGADO** (versión `e2f3799d`) **— 4 rondas de QA en vivo aplicadas.**
**Cierre: M5 pitch → M6 link SOLO → M7 acompañante → M8 pre-llamada.**
**Apertura personalizada ENCENDIDA**: el LLM redacta la frase de entrada, el cuerpo sigue siendo copy aprobado.
**Filtro 1: $6M.** · **Filtro 2: remanente ≥ $2.5M** (reemplaza el tope por %).
**Objeciones: las 9 abiertas.** · **Escalera de repreguntas: construida y APAGADA** hasta que Javier apruebe el copy.

---

## Iteraciones

### It. 1 — Construir la compuerta (hecho)
Se construyó el verificador **antes** que nada más, como manda la guía.

**Rojos reales en su primera corrida:** el link del calendario se enviaba con texto después (bug confirmado en producción por el equipo de Javier, que deja el link inválido en Instagram) — y **el mismo bug estaba repetido** en las objeciones 2/3/6, las 3 descalificaciones y los bumps. Se arregló con `partirEnBurbujas()`, que saca el link del texto y lo manda solo al final **conservando todas las frases en su orden**.

### It. 2 — Corpus y simulador (hecho)
`simulador.js` reproduce conversaciones completas contra el router, sin red ni base, **corriendo la compuerta en cada turno**. El corpus sale de conversaciones reales.

**Bug encontrado leyéndolas:** el turno 1 salía `¡Hola ! 👋`. En el primer mensaje el lead aún no existe en la base y el Worker no le pasaba el nombre al router — ese saludo roto le habría llegado a **todos los leads nuevos**.

### It. 3 — Smoke de las RPC (hecho)
`smoke_rpc.mjs` contra la base real: lead inexistente, escritura y lectura de un turno, **que la guarda de `agendado` siga saltando**, y que el CHECK acepte las etapas nuevas.

### It. 4 — Primera prueba en vivo y sus correcciones (hecho)
El bot recorrió el camino feliz completo en Instagram. De ahí salieron:
- **`"Listo"` se leía como "ya agendé"** → ahora el cierre exige **reunión vinculada en la base**. El bot no decide si agendó: lo decide la base, y quien vincula es el Setter.
- **M7 (asistencia) nunca se enviaba** → pasa a ir junto al link, antes de él.
- **Blindaje del show-up retirado** (no estaba en el SOP V4.2; se verificó en el PDF).
- **Empatía apagada**, mensajes largos troceados.
- Etapa `M7_ESPERANDO_VINCULO`: el acuse se manda **una sola vez** y después el bot espera en silencio.

### It. 5 — Segunda prueba en vivo: las 5 historias (hecho)
- **H1 — vincular = reclamar.** El bug era peor de lo reportado: `fn_vincular_reserva_flotante` **le fallaba al Setter** ("Este lead no te pertenece"), porque el bot deja `setter_id = Andrew`. Solo funcionaba siendo admin.
- **H2 — la causa no era un "Sí" mal leído.** El lead respondió *"es un dato delicado para compartir por aqui"* = **Objeción 6 del SOP**. Causa raíz: las objeciones solo se clasificaban **después del pitch**. Ahora en todas las etapas. Además, etapa `M1_RANGO_PREGUNTADO` para que un "Sí" al rango confirme el Filtro 1, y se corrigió el mapeo, que estaba invertido respecto al SOP.
- **H3 — el crash no se pudo reproducir** (`HANDOFF` y `DESCALIFICADO` llevan en el constraint desde el 1-sep). Probablemente fue una ventana de despliegue-antes-de-migración. El arreglo no fue ensanchar el constraint sino que **un desfase de versiones no pueda tumbar un turno**: la lista de etapas vive en una sola función que usan el CHECK y la RPC, y una etapa desconocida se guarda como `null` con el aviso anotado.
- **H4 — dolores múltiples** con el mismo formato del dashboard (`"B,C"`).
- **H5 — regresión de seguridad encontrada y corregida:** las etapas nuevas no tenían esquema de LLM, y `clasificarConLLM` retorna vacío sin esquema. **`crisis` y `hostil` no se evaluaban en 3 etapas** — siendo crisis la regla de máxima prioridad del diseño.

### It. 6 — Objeciones antes del pitch (hecho)
Al habilitar la Objeción 6 en M1 quedó expuesto un bug de negocio: su plantilla remata con el link, **entregándole la llamada a un lead que no ha pasado los filtros**. No era solo la 6: **la 2, la 3 y la 6** cargaban link.

Variantes sin cierre de agenda construidas **recortando párrafos por código** (no reescribiendo copy), y `manejarObjecion` reenvía la pregunta pendiente para reencarrilar. Post-pitch todo sigue igual.

**Dos huecos que encontraron los tests nuevos:** `preguntaPendiente` no cubría `M1_RANGO_PREGUNTADO`, y reencarrilar reenviaba el saludo completo de M1 como si el bot hubiera perdido el hilo.

### It. 7 — Redespliegue y la Objeción 6 con psicología de Setter (hecho)

**Lo que el `activity_log` mostró de verdad.** Antes de proponer nada se leyó el log de los dos leads de prueba. El de Marly (`1269883784`) dejó ver que el Worker **en vivo seguía siendo el de antes de los arreglos**: su respuesta a la Objeción 6 todavía terminaba en *"O directamente agenda la llamada de diagnóstico de..."* con el link. Los arreglos de la It. 6 estaban en el código, **no en Cloudflare**. Confirmó que el pendiente #1 (redesplegar) era real y era el primero.

**El roce de ventas.** Con los arreglos ya aplicados, la Objeción 6 en M1 quedaba así: *"Te entiendo, esa info es sensible..."* y acto seguido la pregunta pendiente de M1, que es **"¿A qué te dedicas y cuánto ganas al mes?"**. Es volver a pedirle exactamente lo que el lead acaba de negarse a dar. Se lee como presión, no como empatía.

**Regla de negocio nueva (fundador):** la Objeción 6 **durante el Filtro 1** le perdona la profesión y la cifra exacta, y pregunta **solo por el rango** — que se contesta con un "Sí".

Tres piezas, todas en `manejarObjecion`:
1. Plantilla `OBJ_6_EN_M1`: la Objeción 6 recortada **un párrafo más** que la variante pre-pitch normal. El párrafo que se quita empieza con *"Te pregunto porque..."* y `M1_PEDIR_RANGO` abre igual — pegados quedaban dos justificaciones seguidas con la misma cabeza de frase. Sigue siendo **recorte por código sobre copy aprobado: cero palabras nuevas.**
2. En vez de la pregunta pendiente, se envía `P.M1_PEDIR_RANGO`.
3. **Avanza a `M1_RANGO_PREGUNTADO`.** Sin esto el bot haría la pregunta del rango pero seguiría escuchando en `M1_ENVIADO`, donde un "Sí" pelado no es respuesta válida de ingreso — y se volvería a atascar exactamente igual que Marly. Es la **única** objeción que mueve de etapa, y mueve a la etapa que le corresponde a la pregunta que acaba de hacer.

**Rojo que encontró la compuerta, y que era correcto:** el verificador de cumplimiento rechazó la plantilla nueva con `R8_COPY_NO_APROBADO`. Hacía bien: su lista blanca se arma desde la biblioteca y `OBJ_6_EN_M1` no estaba. Se registró en la lista, igual que ya estaban las variantes pre-pitch — **no se debilitó la regla.**

**Tests que se reescribieron, y por qué está permitido.** Dos afirmaciones codificaban la regla vieja y el fundador cambió la regla a propósito (LOOPS.md §2):
- `assert.notEqual(p.etapaNueva, 'M1_RANGO_PREGUNTADO')` — su intención real era *"no la trata como ingreso ambiguo sin más"*, y eso se conserva: la objeción se reconoce antes de repreguntar. Ahora se afirma eso directamente.
- El test parametrizado de objeciones pre-pitch: sigue probando las 12 combinaciones y **sus asertos anti-link quedaron intactos**; solo la pregunta esperada y la etapa dependen ahora de si es la 6 en M1.

Se agregaron 4 tests (179 → **183**), incluido uno que fija que la 6 **fuera** de M1 sigue comportándose como siempre, y un guardarraíl que comprueba que la excepción no adelanta al lead más allá del Filtro 1.

**Despliegue y limpieza.** `npx wrangler deploy` → `artf-bot-setter-v42`, versión `ebf17b76`. Con el Worker arriba se corrió la compuerta **completa por primera vez**: las 5 de 5 en verde (la 4 y la 5 se venían omitiendo por falta de variables de entorno — se cargan desde `.dev.vars`). Los dos leads de prueba se reiniciaron a `nuevo` / `etapa_bot = null`, probando el UPDATE antes con `begin/rollback`.

---

### It. 8 — Dos P0 encontrados auditando la arquitectura (hecho)

El fundador pidió una auditoría del diseño, proponiendo pivotar a "LLM como
Evaluador de Filtros". Antes de opinar se verificó la premisa contra el código —
y **la premisa era cierta, pero la causa atribuida no.** Probando `clasificar()`
directamente aparecieron dos bugs P0, ambos en la capa determinista:

**P0-1 — `ReferenceError: limpio is not defined`.** En `clasificar()`, la rama de
M2 leía un `limpio` que solo existe dentro de `validarClasificacionLLM`
(copy-paste, introducido en las ediciones del 3-sep por la noche). **Reventaba
todo `M2_ENVIADO` y `M2_NO_SABE`** — el Filtro 2 entero, para todos los leads. El
crash cae antes de la escritura síncrona, así que el turno **no se registraba** y
el lead recibía `FALLBACK_ERROR` con handoff `error_tecnico`.

**P0-2 — la plata se leía como porcentaje.** `detectarEndeudamientoPct("pago 2
millones al mes en deudas")` devolvía **`2`**: el fallback de "número suelto"
agarraba el `2`. Y como los deterministas ganan sobre el LLM, tapaba el
`deuda_cop` correcto. **Peor que escalar: 2 % es un endeudamiento excelente, así
que el lead pasaba el Filtro 2 en silencio con un dato inventado.** La conversión
monto→% ya existía y era correcta en el router; nunca llegaba a ejecutarse.
Arreglo: si hay marca de plata en el texto, el detector **se abstiene** y deja que
el LLM aporte `deuda_cop`/`remanente_cop`.

**La causa raíz de fondo — el agujero de cobertura.** 183 tests, type-check verde,
verificador verde, smoke en vivo verde… y **`clasificar()`, que corre en cada
turno, tenía cero tests.** Los tests del router entran por `decidirTurno` con las
pistas **ya clasificadas**, saltándose la capa de clasificación entera; el
simulador hace lo mismo. La compuerta verificaba brillantemente la mitad del
sistema. Se agregaron 24 tests (183 → **207**), incluido un barrido que exige que
**ninguna etapa pueda reventar al clasificar**, sin LLM y sin red.

**Veredicto de la auditoría** (completo en `auditoria_arquitectura_bot_v42.md`):
se rechaza el pivote y se aceptan 2 de sus 5 componentes — el AI SDK con Zod, y
la memoria corta hacia el clasificador. Se rechaza `respuesta_generada` (reabre la
decisión de empatía apagada, reabre la superficie de inyección, **borra la
compuerta 3** y rompe el corpus), `estado_siguiente` por LLM y el playbook en el
system prompt.

---

### It. 9 — Playbook como tabla de datos, las 9 objeciones y la escalera (hecho)

El fundador pidió que el sistema "aprenda sin tocar código" y que deje de escalar
tan pronto. La evaluación completa está en `auditoria_arquitectura_bot_v42.md`
(§2, actualizada). Lo que se rechazó y por qué: **tool calling** para el glosario
(añade un viaje redondo dentro del timeout de ManyChat para consultar una tabla
estática de 20 líneas — y el glosario nunca fue lo que falló), y **mover el copy a
Supabase** (la compuerta 3 construye su lista blanca desde la biblioteca, offline,
en cada commit; con el copy en una tabla remota o metes red en los unit tests o
dejas de verificar el texto real — y una fila editada pone copy sin aprobar frente
a un lead sin revisión).

**El playbook es ahora UNA tabla de datos.** `PLAYBOOK_OBJECIONES` reemplaza los
4 sitios sueltos: el mapa `OBJECIONES`, el Set `OBJECIONES_HABILITADAS`, los
recortes `CORTE_PRE_PITCH` y la lista de disparadores que estaba **hardcodeada en
el prompt del Worker**. Los cuatro se derivan. Agregar una objeción es agregar una
entrada; hay tests que verifican que las derivaciones no se desincronizan.

**Bug latente encontrado al abrir las 9.** El barrido de la It. 6 solo miró las
objeciones que llevaban **link** (2, 3, 6) y por eso se saltó la **1** — que ya
estaba habilitada y venía cerrando agenda en M1 con *"Sin presión. ¿Te parece?"*,
a un lead que no había pasado ni el primer filtro, y encima dejando dos preguntas
seguidas. Un cierre de agenda no necesita link para ser un cierre de agenda. La
compuerta ahora barre **las 9 × 4 etapas** y reconoce el cierre por la frase.

**Umbrales de resistencia** subidos por el fundador (misma objeción 2→3,
acumuladas 3→4). ⚠️ Contradice el PDF V4.2 — **hay que comentárselo a Javier**.
Los tests leen de `UMBRALES` para que no se desincronicen otra vez.

**Escalera de repreguntas: se midió antes de construirla.** La intuición era
agregar reintentos en los 5 sitios que escalaban por ambigüedad. Al medir,
**M1 y M2 ya preguntaban dos veces**; los únicos que escalaban al primer intento
eran **M4 y M5**. La escalera son 2 peldaños, no 5. Va detrás de
`ESCALERA_REPREGUNTAS_HABILITADA = false` porque su copy es nuevo y lo tiene que
aprobar Javier (ver `COPY_PENDIENTE_APROBACION`, fijado por un test para que copy
sin aprobar no entre solo a la lista blanca del verificador).

**La trampa de los 4 sitios, por fin verificable.** Las etapas nuevas obligaron a
cerrarla: el smoke de RPC ahora prueba **las 18 etapas que el router puede
escribir** contra el CHECK real (antes probaba 4), y hay un test que exige que
toda etapa conversacional tenga esquema de LLM — que es lo que ya apagó la
detección de crisis en 3 etapas sin que nadie lo viera.

Y una guarda anti-bucle: la etapa de reintento cae en el mismo `case` que su etapa
madre, así que sin `etapa !== 'M4_URGENCIA_REINTENTO'` el bot ofrecería el
reintento para siempre y el lead nunca llegaría a un humano. Tiene test propio.

179 → **264 tests**. Desplegado: `c1a7c171`.

---

### It. 10 — Modelo financiero nuevo: umbral $6M y remanente $2.5M (hecho)

El fundador mapeó el flujo real del Setter humano. La auditoría express encontró
**3 bloqueantes y 5 defectos** antes de escribir código (detalle en el Anexo B de
`auditoria_arquitectura_bot_v42.md`). Los que cambiaron el diseño:

**Una rama era matemáticamente inalcanzable.** La regla *"remanente < 2.5M **y**
deuda < 50% → descalificar"* nunca puede ejecutarse: como `remanente = S×(1−d)`,
con `S ≥ 6M` y `d < 50%` el remanente siempre supera 2.5M. Se probó el espacio
completo de 6M a 30M: **0 casos**. Se dejó escrita (deja de ser inalcanzable si
el ingreso llega por el dashboard, o si se baja el umbral por debajo de 2×el
remanente) y **hay un test que vigila esa relación entre los dos umbrales**.

**La banda de trampa $6M–$7M.** El umbral bajó a 6M pero el copy aprobado sigue
preguntando *"¿estás entre $7M y $15M?"* en tres sitios de cara al lead. Todo lead
en esa banda **califica y contestaría "No"**. Por eso un "No" al rango **ya no
descalifica**: pide la cifra y decide sobre el número real. Es un turno más y cero
leads buenos perdidos. Cuando Javier apruebe `M1_PEDIR_RANGO_6M` y `DESC_INGRESO_6M`,
copy y umbral coinciden y el "No" vuelve a ser descarte limpio — el código detecta
solo esa alineación y hay tests que cubren las dos ramas.

**Filtro 2 reescrito.** `topeEndeudamiento` (tope condicional por ingreso) fue
reemplazado por `calcularRemanente`. Consecuencia de negocio real: quien gana $15M
con 80% de deuda **ahora pasa** (le quedan $3M), donde antes se descartaba. Y quien
gana $6M con 60% **ahora va a borderline**, donde antes pasaba. El mismo porcentaje
dejó de significar lo mismo — que es exactamente el punto del cambio.

**Borderline con dos salidas a favor:** deuda buena (hipoteca) **o** que rectifique
que le sobran ≥ $2.5M. Y una tercera regla que no estaba en el spec y hacía falta:
si no dice ni el tipo de deuda ni cuánto le sobra, **va a un humano, no a descarte**
— la misma regla de oro del Filtro 1.

**El salario asumido al confirmar el rango** se implementó como pediste (cifra
real, avanza el flujo), pero atado a `INGRESO_ASUMIDO_POR_RANGO`, que un test
obliga a coincidir con la cifra que dice el copy: asumir una cifra distinta a la
que se le preguntó sí sería inventarla. Se marca `ingreso_confirmado: false` para
que el dashboard sepa de dónde salió; no cambia el flujo.

179 → **275 tests**. Desplegado: `2b620e4f`.

**Falta de esta directriz:** matriz de objeciones por etapa, M3 "todas", objeción 9
corta en M4, reestructura M6/M7/M8 y el catch-all del LLM. Ver el Anexo B.

---

### It. 11 — Matriz de objeciones por fase, catch-all del LLM y cierre M8 (hecho)

Cerradas las tres decisiones comerciales que faltaban. **Dos resultaron ser trabajo
que ya estaba hecho**, y verificarlo antes de escribir código ahorró duplicarlo:

- **La "versión corta" de la Objeción 9 ya era la nuestra.** Se comparó carácter a
  carácter contra `objection-handling/7-objeciones-estandar.md` del proyecto de
  Javier: idénticas. Hay test que lo fija contra ese archivo (terreno externo).
- **`P.CIERRE_PRECALL` ya era el texto exacto de M8**, palabra por palabra. Lo
  único que cambió: ahora también se envía **al confirmar** el agendamiento, no
  solo cuando la reunión está vinculada. ⚠️ Riesgo aceptado y anotado: si el lead
  dijo que agendó y no lo hizo, recibe un "Nos vemos en la llamada" que no es
  cierto. **Lo que NO se cedió es el estado**: la etapa sigue en
  `M7_ESPERANDO_VINCULO` y `agendado` lo escribe solo la sync de Calendar.

**Decisión comercial sobre la banda $6M–$7M:** el copy no cambia y un "No" al
rango descalifica directo. El fundador asume la pérdida. Queda con test propio
para que la pérdida sea **visible y deliberada**, no algo que alguien "arregle"
sin saber. El copy de 6M que se había escrito se eliminó.

**Matriz de objeciones por fase.** `FASE_POR_ETAPA` traduce entre la numeración
del fundador (M1..M8) y nuestras 20 etapas — el único sitio donde se traduce, y
hacía falta: **su "M6" es nuestra `M7_ENVIADO`** (donde sale el link) y **su "M8"
es `CIERRE_PRECALL`/`M7_ESPERANDO_VINCULO`**. Confundirlas era bug garantizado.

**Bug real que encontró un test mío mientras lo escribía:** la comprobación de la
matriz estaba **antes** de las reglas de escalamiento, así que un lead que
insistía con una objeción fuera de fase se reencauzaba **indefinidamente y nunca
llegaba a un humano**. Se movió después. Tiene test propio.

**Catch-all del LLM** (`CATCHALL_LLM_HABILITADO = true`, a prueba por decisión del
fundador). Es la única pieza de texto libre que ve el lead, así que se construyó
con la verificación que sí queda cuando se cede el determinismo del texto:
`verificarTextoGenerado` rechaza links, datos de contacto, léxico de inyección,
voseo/regionalismos, tercera persona de Andrés, léxico prohibido del playbook y
afirmar un agendamiento. **El saneo del Worker usa exactamente esas mismas
reglas**, así que lo que se envía y lo que se verifica no pueden divergir. Si
falla cualquiera, se descarta y queda el reencauce determinista, que siempre
funciona. Y la exención de la lista blanca aplica **solo** a la burbuja que el
router marcó como generada: hay test de que no sirve para colar copy.

**M3 "todas"**: `detectarDolorLetras` mapea "todas"/"todo lo anterior"/"las cuatro"
a A+B+C+D, que arrastra A/B/C y por eso salta la pregunta del detalle de la D —
la excepción exacta que se pidió, sin copy nuevo. `M3_RECONDUCIR` ya preguntaba y
validaba, así que el otro caso tampoco necesitó nada.

179 → **293 tests**. Desplegado: `1dc20dcb`.

---

### It. 12 — Primer QA en vivo: 3 hallazgos, y el más caro no era el que parecía (hecho)

**Hallazgo 1 — el bot se ponía a la defensiva sin motivo.** A una lead que
simplemente olvidó decir su salario se le respondía con el texto que está escrito
para desactivar una objeción (*"Te pregunto porque el proceso funciona mejor
para..."*). Ahora hay **dos variantes**: la SIMPLE cuando no hubo objeción, y la
defensiva solo cuando el lead sí se negó a dar el dato.

**Hallazgo 2 — el LLM leyó "deudas" y dijo que no era financiero.** La lead
escribió *"D, me siento preocupada por la cantidad de deudas que tengo"* y el LLM
devolvió `dolor_financiero: false`, así que el bot le respondió *"puede que no
seamos el mejor fit"* a alguien cuyo dolor es **literalmente deudas**. Se arregló
en los dos lados: el prompt lo dice explícito **y** hay un detector determinista
(`pareceDolorFinanciero`) que **gana sobre el LLM**. El prompt solo no bastaba —
el modelo ya había fallado con un caso obvio.

**Hallazgo 3 — el silencio en M5, y la causa no era ninguna de las sospechas.**
Ni el candado del texto generado (`verificarTextoGenerado` es compuerta de
desarrollo y no corrió) ni la máquina de estados (transicionó bien). El log real:

| hora | lead | clasificación |
|---|---|---|
| 16:08:57 | "es gratis? de que se trata el programa?" | Objeción 1 ✔ |
| 16:09:32 | "pero quiero saber mas sobre el metodo" | Objeción 5 ✔ |
| 16:10:14 | "cuanto cuesta el programa" | Objeción 7 ✔ |
| 16:10:39 | "lo voy a pensar" | Objeción 3 → **4 acumuladas → HANDOFF** |
| 16:11:10 | "pero mejor si, agendemos" | *sin respuesta (handoff_activo)* |

Las cuatro clasificaciones fueron **correctas**. El bot hizo exactamente lo
diseñado. **El defecto era la regla**: se llama `resistencia_acumulada` pero
contaba *curiosidad*. "¿Es gratis?", "quiero saber más" y "¿cuánto cuesta?" son
**señales de compra**; un lead interesado que hace cuatro preguntas se veía igual
que uno que se resiste.

Ahora la tabla del playbook marca `cuentaComoResistencia`: solo la **2, 3, 4 y 6**
suman al tope. La 1, 5, 7, 8 y 9 son preguntas y se contestan sin acumular. Como
la 7 ya no acumula, la señal de "precio insistido" pasó a ser que **la repita**:
si vuelve a preguntar después de la respuesta, no le sirvió. La secuencia exacta
del QA ahora **convierte a M7_ENVIADO en vez de escalar**, y está fija como
corpus (`06-qa-marly-curiosidad-no-es-resistencia.json`).

**Red de seguridad añadida:** cuando el handoff sí es correcto y el lead acepta
después, el `activity_log` lo marca `⚠️ EL LEAD QUIERE AGENDAR y el bot está en
silencio`. Antes esa aceptación quedaba enterrada en un log genérico, y es la
señal más valiosa del embudo.

179 → **300 tests**. Desplegado: `93e6182b`.

---

### It. 13 — 2º QA: raíces muertas y apertura personalizada (hecho)

**Bug propio, y peor de lo reportado.** El QA dijo que `"d. quiero ahorrar"` no se
detectaba como dolor financiero. Al probarlo: **`ahorro`, `ahorrar`, `invertir`,
`inversion`, `financiero` y `economicos` fallaban todos.** La causa es mía: escribí
las raíces con `\b` **al final** (`\bahorr\b`), y `\b` no cierra entre dos letras
— así que esas cuatro raíces **no casaban nada desde el día uno**. Es la misma
trampa del `\b` que ya está documentada para las vocales acentuadas, en otra
forma. Ahora las raíces llevan `\b` solo al inicio, con el vocabulario que pidió
el fundador (ahorro, inversión, patrimonio, futuro, pensión, rentabilidad).

Y un falso positivo que apareció al probarlo: `"quiero bajar de peso"` casaba con
`peso`. El dinero va en plural (`pesos`) o como `millones`.

**Apertura personalizada: encendida, con la compuerta reforzada ANTES de aflojar.**

La forma es la del ejemplo del fundador — **apertura generada + cuerpo aprobado
literal**:

```
"Entiendo que tu meta principal sea ahorrar, Marly."   <- lo escribe el LLM
                                                        <- linea en blanco
"Lo que pasa es que nos especializamos en..."          <- plantilla, literal
```

**El hueco que había que cerrar primero:** `esCopyAprobado` ya aceptaba ese
formato mirando solo lo que va DESPUÉS de la línea en blanco — o sea, el prefijo,
que es lo único que el lead lee sin aprobar, **pasaba sin verificarse**. Ahora el
cuerpo se valida contra la biblioteca **y** el prefijo contra las reglas del texto
generado.

**Dos reglas nuevas, y son las que importan:** el resto del set comprueba que el
texto sea *seguro*; ninguna puede comprobar que sea *cierto*. Un modelo puede
escribir "te garantizamos ahorrar el 30% en 8 semanas" y pasar todas las demás.
Por eso `G9_PROMESA` y `G10_CIFRA_INVENTADA` prohíben el léxico con el que se
inventan hechos del programa. **Lo que el programa promete de verdad vive en las
plantillas, y esas sí se verifican contra la biblioteca** — por eso el cuerpo no
se genera.

**Nota histórica:** esto no es una decisión nueva, es la reversión de una. Nació
como `oracion_empatia`, el fundador la apagó el 3-sep (*"parece mucha IA"*) y se
reenciende el 4-sep. La diferencia es que entonces el texto generado no lo
verificaba nadie.

El turno del link **nunca** lleva apertura generada: es el más frágil del embudo y
el único que ya se rompió en producción.

179 → **317 tests**. Desplegado: `832e672b`.

---

### It. 14 — 3er QA: la suma de ingresos, la hostilidad falsa y la recuperación (hecho)

Una sola conversación destapó tres cosas distintas.

**1. El CoT solo no habría arreglado la suma.** La lead dio tres fuentes
(4M + 3M + 4M = 11M) y el sistema se quedó con **4M** y la descalificó. La causa
no era que el LLM no razonara: `parseIngresoCOP` agarra la **primera** cifra, y
**los deterministas ganan sobre el LLM** en la fusión — así que aunque el modelo
sumara bien, se sobrescribía. Se arreglaron las dos capas:

- El parser **se abstiene** cuando cuenta más de una cifra de dinero
  (`varias_fuentes`). Es la misma regla que ya salvó al detector de
  endeudamiento: **abstenerse es mejor que adivinar**. Sumar aquí sería adivinar
  — no se sabe si las cifras se suman, se restan o son un rango.
- **CoT `analisis_paso_a_paso`, primero en el JSON.** El orden importa de verdad:
  el modelo genera en secuencia, así que el razonamiento antes de los campos los
  condiciona; puesto al final no sirve de nada.
- Y un detalle que habría dejado el arreglo sin efecto: el guard
  `ingreso_forzado_ambiguo` **anula la cifra del LLM**. Existe para "integral",
  donde el modelo adivinaría; `varias_fuentes` es el caso contrario y quedó
  exento.

**2. La hostilidad falsa.** El handoff fue `contenido_hostil` por *"no gracias,
eso es inaceptable las confusiones"*. El detector determinista **NO disparó** —
fue el LLM, y el prompt no tenía **ni una línea** definiendo `hostil` (`crisis`
tiene su aviso de falso positivo desde hace días; `hostil` no tenía nada). Ahora
la tiene: **la frustración no es hostilidad.** Un lead enojado es un lead.

**3. Auto-recuperación de handoff.** Con `recupera_handoff`, un lead que pide
continuar sale del handoff y el bot retoma. Dos detalles que costaron trabajo:

- **La etapa quedaba en `HANDOFF`, que no dice dónde iba.** Se retoma con
  `etapaParaRetomar()`, que deduce el punto por los **datos** que ya tiene: el
  primer filtro que falte.
- **La RPC no podía limpiar el handoff.** Asigna
  `handoff_razon = coalesce(nullif(...), handoff_razon)`, o sea que pasar NULL lo
  **conserva**. Reescribir una función de 11K en una base compartida con
  producción era desproporcionado, así que el Worker lo limpia con un **PATCH
  dirigido** — escritura de datos normal, cero DDL. Se hace *antes* de escribir
  el turno, y si falla no se sigue: responder con el handoff todavía puesto sería
  lo peor de los dos mundos.

**Tres razones NO se recuperan nunca:** `crisis_emocional` (regla de máxima
prioridad: quien está en crisis y dice "no, sigamos" necesita a una persona),
`ex_cliente` y `agendamiento_manual_pendiente`.

179 → **335 tests**. Desplegado: `8c017f9f`.

---

### It. 15 — 4º QA: el cierre reordenado y el simulador que ocultaba bugs (hecho)

Una conversación con **tres fallos encadenados**, y el tercero destapó un cuarto
que llevaba tiempo escondido.

**1. "Espérame" se leyó como aceptación.** El lead escribió *"esperame, antes me
gustaría tener más claro de que trata el protocolo"* y recibió el link.
`detectarAceptacion` devolvía `true` porque **`claro` casaba dentro de "más
claro"**, y el freno de negación solo miraba **los primeros 12 caracteres**, así
que "esperame, antes..." se le escapaba. Además M5 evaluaba `acepta` **antes** que
la objeción — al revés que M1 y M2, donde esa regla ya existía. Las tres cosas
arregladas.

**2. El `"emm si"` ambiguo.** Contestaba a la pregunta del acompañante, y se leyó
como *"ya agendé"*. La causa de fondo: **acompañante y link viajaban en el mismo
turno**, así que un sí/no podía contestar a cualquiera de los dos. El orden nuevo
lo elimina de raíz:

```
M5 pitch → M6 LINK SOLO → M7 acompañante → M8 pre-llamada
```

Cada etapa espera **una** señal: M6 solo `confirmo_agendo`, M7 solo `acompanado`.
Y en M7 un "sí" pelado ya no es ambiguo, porque es la única pregunta abierta.
Bonus: el turno del cierre bajó de 4 burbujas a 3, que era el riesgo #1 vigilado.

**3. `"¿dónde me agendo?"` recibía silencio.** El fundador pidió que el LLM
respondiera *"Aquí tienes el link: [Link]"*. **Eso no se implementó así**: un link
escrito por el LLM viola la regla del link (va solo y de último — bug confirmado
en producción) y reabre el vector de suplantación que `G2_LLEVA_LINK` bloquea. En
su lugar el LLM **señala** `pide_link` y el router reenvía la plantilla aprobada,
aislada. El modelo nunca teclea una URL.

**4. El hallazgo de fondo: `simulador.js` tenía su PROPIA copia de la
clasificación determinista.** Era el agujero que la auditoría ya había señalado y
seguía abierto: el corpus no ejercitaba el camino de producción. Ahora el
simulador llama a `clasificar()` del Worker con `env = {}` (sin LLM, sin red).

**Al hacerlo, el corpus 03 se puso rojo y destapó un bug real:** el Worker **no
parseaba el ingreso en `M1_ACLARAR_REMANENTE` ni en `RETORNO_PREGUNTA`** — dos
etapas donde se le pide una cifra al lead. La copia del simulador sí las incluía,
y por eso el corpus pasaba mientras producción dependía solo del LLM ahí.

También se arregló `detectarAcompanante`: la gente contesta *"va mi esposa"*, no
*"con mi esposa"*, y solo se detectaba la forma con preposición.

179 → **346 tests**. Desplegado: `e2f3799d`.

---

---

## Decisiones cerradas (no volver a abrir)

- `calificado` se marca al pasar los 3 filtros, no al enviar el link.
- El bot **nunca** escribe `agendado`; eso es de la sync de Google Calendar, con guarda dura en la base.
- El cierre exige **reunión vinculada**: que el lead diga "ya agendé" no es prueba.
- El link va **siempre** de último y solo. Aplica a cualquier URL, **y el LLM nunca la escribe**: señala `pide_link` y el router la envía.
- **El simulador usa el clasificador REAL del Worker**, no una copia. La copia ya ocultó un bug de producción.
- Una objeción **antes del pitch** no remata con el link.
- La **Objeción 6 durante el Filtro 1** no repregunta profesión ni cifra exacta: pide **solo el rango** y pasa a `M1_RANGO_PREGUNTADO`.
- **Apertura personalizada ENCENDIDA** (4-sep-2026, revierte la decisión del 3-sep): el LLM escribe la frase de entrada, **el cuerpo sigue siendo copy aprobado literal**. La diferencia con entonces es que ahora el prefijo pasa por `verificarTextoGenerado`.
- **La frustración no es hostilidad** y **la curiosidad no es resistencia**: ambas sacaban leads buenos del embudo.
- Un handoff **recuperable** se deshace si el lead pide continuar; `crisis_emocional` **nunca** se recupera.
- **La curiosidad no es resistencia**: solo las objeciones 2, 3, 4 y 6 suman al tope de escalamiento.
- Objeciones habilitadas: **las 9**, con **matriz de fases** (4-sep-2026): fuera de su fase se reencauza, no se contesta.
- La banda **$6M–$7M se pierde a propósito**: el copy del rango no cambia y un "No" descalifica.
- El bot dice la despedida al confirmar, pero **nunca adelanta el estado**: `agendado` sigue siendo solo de la sync de Calendar.
- Objeciones habilitadas: **las 9** (4-sep-2026). La perilla sigue siendo el campo `habilitada` de `PLAYBOOK_OBJECIONES`.
- El copy del playbook vive **en código**, no en Supabase: la compuerta 3 necesita construir su lista blanca offline en cada commit.
- Las escaladas de **seguridad** (crisis, hostilidad, ex cliente) no se tocan nunca.
- Blindaje del show-up: retirado.
- Única puerta abierta en estado terminal: `descalificado`, y solo para el RetornoLead.
- Vincular una reserva **reclama** el lead para el Setter.

---

## Riesgos vivos

1. **Las 4 burbujas del cierre sin pausa.** ManyChat no permite pausas <10s. Con 2 burbujas ya funcionó; con 4 no se ha probado. Si Instagram las entrega desordenadas, el link deja de ser el último. **Es lo #1 a vigilar en la próxima prueba.** Plan B listo: bajar a 2 burbujas.
2. 🔴 **El link es el calendario PERSONAL de Yeison.** Cambiar a `CALENDAR_ARTF` antes de producción.
3. **Auto-juicio.** Quien escribe el código escribe los tests. Mitigado con terreno externo (PDF del SOP, proyecto de Javier, constraints de Postgres, base real). **Vigilar:** si un test se pone rojo, arreglar el código, no reescribir el test.
4. **Una etapa nueva necesita 4 sitios**: el CHECK (vía `fn_etapa_bot_valida`), `ESQUEMA_POR_ETAPA`, `preguntaPendiente()` y el `switch`. Olvidar el segundo apagó la detección de crisis; olvidar el tercero dejó una etapa sin qué reenviar. **Ambos ya pasaron.**
5. **Base compartida con producción.** Migraciones aditivas, probadas con `begin/rollback`. Leads de prueba marcados `[PRUEBA]`.

---

## Pendientes

Ver `RETOMAR_AQUI.md` para la lista ordenada y el prompt de arranque.

- ~~Redesplegar el Worker~~ (hecho, versión `ebf17b76`). **Falta la 3ª prueba en vivo.**
- Probar la vinculación de reserva **como Setter**, no como admin.
- Cambiar el link al de ARTF antes de producción.
- Bumps del SOP de Recuperación: necesitan un Cron Trigger de Cloudflare.
- Objeciones 4, 5, 7 y 8: ampliar cuando haya datos de cuáles aparecen.
- Debounce real (KV) solo si el double-texting resulta frecuente.
- Re-correr `e2e/setter-agendado.spec.ts` con el entorno estable.
- Comentarle a Javier las 4 inconsistencias del PDF V4.2 y el `"Contame"` (voseo en 3 de sus archivos).
