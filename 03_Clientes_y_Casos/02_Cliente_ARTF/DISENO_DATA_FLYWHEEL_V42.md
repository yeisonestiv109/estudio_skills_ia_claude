# Meta 3 — Cabos sueltos + diseño del Data Flywheel (V4.2)

**Fecha:** 7-sep-2026 · **Estado:** diseño conceptual, NO implementado (por instrucción explícita)
**Todo lo numérico de este documento salió de consultar la base real, no de estimaciones.**

---

## Parte A — Auditoría de cabos sueltos

### A.1 Los que ya estaban cerrados (verificado en código, no asumido)

| Cabo | Estado real | Evidencia |
|---|---|---|
| Integración de memoria conversacional | **CERRADO** | `leerHistorial()` lee 6 turnos de `activity_log`, degrada a `[]` sin tumbar el turno. `formatearHistorial()` recorta a 200/220 chars. |
| `adaptarObjecionConLLM` sin historial | **CERRADO el 6-sep** | `worker_bot_setter_v42.js:311-312` ya pasa `historial` **y** `pendienteObj`. El comentario en :308 lo documenta. |
| Deuda técnica en el router | **LIMPIO** | Cero `TODO`/`FIXME`/`HACK` reales. Los aciertos de grep son comentarios explicativos. |

**Conclusión:** no quedan cabos sueltos de *código*. Los que quedan son de *negocio y operación*.

### A.2 Los que siguen abiertos (y de quién dependen)

| # | Cabo | Bloqueado por | Riesgo si se ignora |
|---|---|---|---|
| 1 | `ESCALERA_REPREGUNTAS_HABILITADA = false`<br>`COPY_PENDIENTE_HABILITADO = false` | **Javier** (aprobar 3 plantillas) | Bajo. Las perillas en `false` son el estado seguro: el bot usa solo copy aprobado. |
| 2 | Bumps del SOP de Recuperación | Cloudflare Cron Trigger | Medio. Leads que se enfrían sin seguimiento. **Diferido por ti a propósito.** |
| 3 | `procesarSiAgendado` con Groq desconectada | Decisión del fundador (`worker_bridge_supabase_NUEVO_paralelo.js:177`) | Bajo. Documentado, deliberado. |
| 4 | Flow de ManyChat (`V42_EN_PRUEBA`) sin abrir | **Tú** | Alto: sin esto el canary no ve tráfico real. |
| 5 | Tier de Groq (techo ~2 leads/min) | Decisión comercial | **Alto en producción.** Ver A.3. |

### A.3 El riesgo que sí me preocupa: el techo de Groq

El plan gratuito topa en ~2 leads/min. En la base hay **~55-70 leads nuevos al día**, pero llegan en ráfagas (picos tras publicar contenido), no repartidos. En una ráfaga se agota el OTPM y el clasificador empieza a devolver `llm_fallo`.

Eso **no tumba el bot** — hay degradación controlada — pero sí lo vuelve más tonto justo cuando más leads hay. Es la decisión con más impacto económico pendiente.

---

## Parte B — Diseño del Data Flywheel

### B.1 El hallazgo que define todo el diseño

Fui a buscar con qué datos se alimentaría el volante. Esto es lo que hay **hoy**:

```
activity_log.payload (turnos del bot, desde 4-sep):
  sop_version → 1284 filas
  etapa_bot   → 1247 filas
  objecion    →   36 filas
```

```
llm_telemetria: proveedor, modelo, llave_alias, límites, 429s, errores…
  → salud de CUOTA, agregada. Cero información por decisión.
```

> **La decisión del LLM no se guarda en ninguna parte.**
> Sabemos en qué etapa quedó el lead, pero no qué clasificó el modelo,
> ni con qué confianza, ni si un determinista lo sobreescribió.

Esto es el bloqueante único y real del Flywheel. Sin ese registro no se puede medir si el modelo mejora ni construir un corpus de evaluación: solo se puede leer la conversación y adivinar hacia atrás.

**Corolario incómodo:** el diagnóstico de "12 bugs, 6 en regex determinista" se sostuvo leyendo conversaciones a mano. No es escalable, y es exactamente el trabajo que el Flywheel debería automatizar.

### B.2 Tamaño real del corpus disponible

Turnos desde el 3-sep (`evento='mensaje_bot'`):

| Contenido | Filas | Leads |
|---|---|---|
| Con mensaje del lead **y** del bot ← lo único usable | **284** | 42 |
| Solo mensaje del lead | 694 | 288 |
| Sin ninguno de los dos (basura: `Lead 900000001`) | 944 | 2 |

**284 pares utilizables.** Suficiente para un set de evaluación, insuficiente para afinar un modelo. El Flywheel debe diseñarse para *evaluar*, no para *entrenar* — al menos este trimestre.

### B.3 Arquitectura propuesta (4 etapas)

```
   ①  CAPTURA            ②  ETIQUETADO         ③  EVALUACIÓN         ④  DECISIÓN
   cada turno       →    el Setter corrige  →  corpus dorado     →  cambio de prompt,
   deja su huella        lo que el bot erró    corre en cada        umbral o regla
                                               ./verificar.sh
        ↑                                                                  │
        └──────────────────────────────────────────────────────────────────┘
```

#### ① Captura — *lo único que hay que construir primero*

Ampliar `activity_log.payload` en el turno del bot con un bloque `decision`:

```jsonc
"decision": {
  "clasificacion_llm": { /* el JSON crudo del modelo */ },
  "razonamiento": "…",          // el CoT, cuando se pidió
  "deterministas": { "ganaron": ["endeudamiento_pct"], "valor_llm": 45, "valor_det": null },
  "regla_aplicada": "M2_VERIFICAR_CALCULO",
  "modelo": "qwen/qwen3.8-27b",
  "llave_alias": "groq_2",
  "latencia_ms": 812,
  "llm_fallo": false
}
```

Por qué así y no una tabla nueva:
- `activity_log` **ya se escribe en cada turno**. Cero llamadas extra, cero latencia añadida.
- Es aditivo sobre `jsonb`: no toca el esquema, no rompe el dashboard ni las RPC existentes.
- Ya está el índice por `gestion_lead_id`; el join sale gratis.

⚠️ **Antes de implementar hay que decidir la retención.** Guardar el texto del lead más el razonamiento del modelo por tiempo indefinido es un tema de Habeas Data (regla del `CLAUDE.md` de este repo). Propuesta: purga automática del bloque `decision` a los 90 días, conservando la conversación.

#### ② Etiquetado — el Setter ya hace el trabajo, solo hay que capturarlo

Cuando un handoff llega a Google Chat, el Setter lee la conversación y actúa. **Ese es el juicio experto que hoy se pierde.**

Propuesta mínima: un botón en el Dashboard, en la vista del lead — *"el bot se equivocó aquí"* — con un desplegable de 5 opciones (`clasificó mal la objeción` / `no entendió la cifra` / `escaló de más` / `escaló de menos` / `respondió algo que no debía`) y un campo de texto opcional.

Un clic, no un formulario. Si cuesta más de 3 segundos, no lo van a usar.

#### ③ Evaluación — conectarlo a la compuerta que ya existe

Ya hay `evals.mjs` y un corpus de 50 casos etiquetados que pasa en `./verificar.sh`. El Flywheel simplemente **lo alimenta**: cada caso etiquetado en ② se convierte en un caso nuevo del corpus.

La compuerta ya es el árbitro. No hay que inventar un mecanismo nuevo — hay que darle más casos.

#### ④ Decisión — la regla que evita el autoengaño

Un cambio de prompt/umbral/regla solo entra si **sube el acierto en el corpus dorado sin bajar ninguna categoría existente**. Sin esa regla, "mejorar el prompt" es mover el bulto de un lado a otro.

### B.4 Orden sugerido y por qué

| Fase | Qué | Esfuerzo | Depende de |
|---|---|---|---|
| 1 | ① Captura + decisión de retención | Bajo (un `payload` más rico) | Tu OK sobre retención |
| 2 | ③ Reproceso: volcar los 284 pares al corpus | Bajo | Fase 1 |
| 3 | ② Botón de corrección en el Dashboard | Medio | Fase 1 |
| 4 | ④ Regla de la compuerta | Trivial | Fase 3 |

**La fase 1 es la que urge**, y no por el Flywheel: cada día sin ella es un día de decisiones del modelo que se pierden para siempre. El resto puede esperar.

### B.5 Lo que este diseño NO resuelve

Honestidad sobre los límites:

- **No arregla el techo de Groq.** Es un problema de plan, no de datos.
- **284 pares no afinan un modelo.** Esto es evaluación, no entrenamiento. Con ~60 leads/día y captura activa, un corpus para afinar tardaría meses.
- **Depende de que el Setter use el botón.** Si no lo usa, el volante no gira. Vale la pena acordarlo con el equipo *antes* de programarlo.
- **Etiqueta lo que el Setter ve**, que son casi solo handoffs. Las conversaciones que salen bien no generan etiqueta — hay un sesgo de supervivencia que habrá que compensar muestreando conversaciones exitosas a mano.

---

## Resumen

- **Cabos de código:** cerrados. Los abiertos son de negocio (Javier, Flow de ManyChat, tier de Groq).
- **Flywheel:** hay un bloqueante único y concreto — no se guarda la decisión del LLM. Se arregla enriqueciendo un `payload` que ya se escribe.
- **Riesgo que quiero que mires:** el techo de Groq en ráfagas y la retención de datos personales en el bloque `decision`.
