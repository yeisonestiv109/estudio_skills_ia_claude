# PROGRESS — estado del loop del bot ARTF

> El órgano "estado" del loop (ver `LOOPS.md`). Qué se intentó, qué falló y qué
> queda. Se actualiza en cada iteración para no repetir errores ni perder el hilo.

**Compuerta:** `./verificar.sh` · **Última corrida: VERDE** (2-sep-2026)

---

## Presupuesto

| | |
|---|---|
| Estimado | ~9–12 turnos |
| Consumidos | ~7 |
| Tope duro | 15 → paro y escalo |

---

## Iteraciones

### It. 1 — Construir la compuerta (hecho)
Se construyó el verificador **antes** que nada más, como manda la guía.
`verificador_cumplimiento.js` + 119 tests + `verificar.sh`.

**Rojos que encontró en su primera corrida — todos reales:**

| Hallazgo | Veredicto |
|---|---|
| `"Sabes"` marcado como voseo | **Falso positivo mío.** `sabes` es tuteo; el voseo es `sabés`, con tilde. Corregido: las formas ambiguas (`sabés/hacés/andás`) ahora exigen tilde |
| Objeciones **2, 3 y 6** llevan el link incrustado con texto después | **Bug real.** Es el mismo bug del M6 que ya habíamos arreglado, repetido en el playbook |
| Las **3 descalificaciones** y los **bumps** igual, con los links de reels | **Bug real.** Su regla dice "aplica a cualquier link futuro" |

**Cómo se arregló el link:** no reescribiendo 9 plantillas a mano (habría cambiado copy aprobado), sino con `partirEnBurbujas()`, que saca el link del texto y lo manda solo al final **conservando todas las frases en su orden**. R1 del verificador pasó a chequear *cualquier* URL, no solo la del calendario.

### It. 1b — Alcance de la v1 y copy del link (hecho)
Decisiones del fundador (2-sep-2026), que **él puede aprobar como Setter actual** — no hay que escalar a Catalina/Javier salvo algo que ninguno de los dos pueda resolver:

- **Copy reordenado:** la frase que anuncia el link se movió al final en la Objeción 3 y en las 3 descalificaciones, para que no quede anunciando algo que llega en la burbuja siguiente. Mismas frases del SOP, distinto orden. (Las Objeciones 2 y 6 ya quedaban bien.)
- **Alcance v1 de objeciones:** el bot contesta solo la **1, 2 y 3** (las mecánicas de agendamiento). Las otras 6 van a handoff con razón `objecion_no_habilitada`. Se controla con `OBJECIONES_HABILITADAS` en `sop_v42_plantillas.js`: **ampliar es agregar un número al Set**, el copy y el ruteo de las 9 ya existen y están probados.

**⚠️ Consecuencia que hay que vigilar en la prueba:** la **Objeción 9** ("¿por qué resolverlo ahora?") es la única que el SOP predice como parte del flujo normal — dice literal *"aparece en Mensaje 4 (urgencia)"*. Con el alcance actual, ese lead va a handoff en vez de recibir el reframe. Si en la prueba aparece seguido, el arreglo es agregar `9` al Set. El invariante crítico sí se mantiene: preguntar "¿por qué ahora?" **nunca** se lee como falta de urgencia.

### It. 2 — Corpus y simulador (pendiente)
Convertir `Setter-IA-Claude-Code-Project/examples/` (4 conversaciones modelo reales) en fixtures y reproducirlas turno por turno contra el router, con la compuerta corriendo en cada turno.

**Por qué importa:** es el terreno externo más fuerte que tenemos — conversaciones que yo no escribí, con las frases literales del lead (`"gano alrededor de 7 millones netos al mes"`, `"B sin duda"`, `"Firme firme, lo tengo agendado"`). Sirven para probar los detectores deterministas contra lenguaje real, no contra casos que yo invente.

### It. 3 — Automatizar la compuerta 4 (pendiente)
Hoy el smoke de las RPC contra la base real es manual. Convertirlo en script.

---

## Decisiones cerradas (no volver a abrir)

- `calificado` se marca al pasar los 3 filtros, no al enviar el link.
- El bot **nunca** escribe `agendado`; eso es de la sync de Google Calendar (con guarda dura en la base).
- Única puerta abierta en estado terminal: `descalificado`, por el RetornoLead que exige el SOP.
- Acuse corto aprobado para "asisto solo".
- Blindaje del show-up (M5.5.d) incorporado.
- Autonomía alta: técnico sin preguntar; copy nuevo y umbrales de negocio, preguntando.

---

## Riesgos vivos

1. **Auto-juicio.** Yo escribo código y tests. Mitigado con terreno externo (PDF del SOP, proyecto de Javier, constraints de Postgres). **Vigilar:** si un test se pone rojo, la salida por defecto es arreglar el código, no reescribir el test.
2. **Reordenamiento de copy por el link.** `partirEnBurbujas()` no inventa texto, pero **sí cambia el orden** en que el lead lee las frases de 9 plantillas. Conviene que Javier/Catalina lo bendigan.
3. **Base compartida con producción.** Migraciones aditivas y probadas con `begin/rollback`. Leads de prueba marcados `[PRUEBA]`.
4. **La compuerta 5 no se ha corrido nunca** — requiere el Worker desplegado.

---

## Pendientes que no bloquean el verde

- Bumps del SOP de Recuperación: necesitan un Cron Trigger de Cloudflare.
- Re-correr `e2e/setter-agendado.spec.ts` cuando el entorno esté estable (el fix está probado a nivel SQL, no con navegador).
- 4 inconsistencias de renumeración en el PDF V4.2 (documentadas, las corrige Javier).
