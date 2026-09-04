# PROGRESS — estado del loop del bot ARTF

> El órgano "estado" del loop (ver `LOOPS.md`). Qué se intentó, qué falló y qué
> queda. Se actualiza en cada iteración para no repetir errores ni perder el hilo.
>
> **Para retomar en una sesión nueva, empieza por `RETOMAR_AQUI.md`.**

**Compuerta:** `./verificar.sh` · **Última corrida: VERDE** (3-sep-2026) · **179 tests** · 5 de 5 compuertas automatizadas
**Estado del bot: DESPLEGADO y probado en vivo en Instagram.**

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

---

## Decisiones cerradas (no volver a abrir)

- `calificado` se marca al pasar los 3 filtros, no al enviar el link.
- El bot **nunca** escribe `agendado`; eso es de la sync de Google Calendar, con guarda dura en la base.
- El cierre exige **reunión vinculada**: que el lead diga "ya agendé" no es prueba.
- El link va **siempre** de último y solo. Aplica a cualquier URL.
- Una objeción **antes del pitch** no remata con el link.
- Empatía apagada: el bot es 100% copy aprobado.
- Objeciones habilitadas: **1, 2, 3, 6, 9**. Fuera 4, 5, 7 y 8.
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

- Redesplegar el Worker y volver a probar.
- Probar la vinculación de reserva **como Setter**, no como admin.
- Cambiar el link al de ARTF antes de producción.
- Bumps del SOP de Recuperación: necesitan un Cron Trigger de Cloudflare.
- Objeciones 4, 5, 7 y 8: ampliar cuando haya datos de cuáles aparecen.
- Debounce real (KV) solo si el double-texting resulta frecuente.
- Re-correr `e2e/setter-agendado.spec.ts` con el entorno estable.
- Comentarle a Javier las 4 inconsistencias del PDF V4.2 y el `"Contame"` (voseo en 3 de sus archivos).
