# Reglas del loop — Bot conversacional ARTF

> Aplicación de `Loop_Engineering_Guia_Viva.md` (v1.0) a este proyecto.
> **Este loop es de DESARROLLO**, no del runtime del bot. El generador soy yo
> (Claude) produciendo código; el verificador decide si *mi trabajo* pasa.
> El comportamiento del bot en vivo es un tema aparte.

**Estado del loop:** activo desde el 2-sep-2026.

---

## 1. Objetivo verificable

No sirve "dejar el bot listo". Sirve esto, porque puede **fallar**:

```bash
./verificar.sh        # verde = objetivo alcanzado, paro
```

Las 5 compuertas que corre:

| # | Compuerta | Qué prueba |
|---|---|---|
| 1 | `node --test` en `Scrips_Worker_and_AppScript/` | Router, glosario de ingreso, objeciones, seguridad del Worker y **cumplimiento del playbook** |
| 2 | `npm run type-check` en `artf-pipeline-app/` | Que el dashboard sigue compilando |
| 3 | Verificador de cumplimiento sobre la salida real del router | Que ningún mensaje que el bot pueda emitir viola el playbook |
| 4 | Smoke de las RPC contra la base real | Que `fn_bot_get_estado` / `fn_bot_procesar_turno` responden y la guarda de `agendado` sigue puesta |
| 5 | Smoke HTTP del Worker desplegado | `200` con el secreto, `401` sin él |

La 5 solo aplica una vez desplegado. Las 1–4 corren siempre.

---

## 2. El verificador y por qué está fuera de mi alcance

La guía (principio 4) advierte: *"si el generador puede tocar su propio examen, hará trampa"*. Yo escribo el código **y** los tests, así que esto importa de verdad.

**Terreno externo — cosas que yo no escribí y que la compuerta usa como verdad:**

- `SOP Setter DM en Instagram V4.2.pdf` — documento del cliente.
- `Setter-IA-Claude-Code-Project/` — el proyecto del Setter IA de Javier. En especial `knowledge-base/04-voz-y-tono.md` (sus dos reglas "no negociables", rotas en producción) y `sops/sop-05-aprendizajes-produccion.md`.
- `examples/` de ese proyecto — conversaciones reales, base del corpus.
- Las restricciones de Postgres (CHECK de `etapa_bot`, `estado_transiciones`, la guarda que impide escribir `agendado`).
- La base real respondiendo.

**Regla:** si un cambio mío contradice cualquiera de esas fuentes, la compuerta se pone roja. No puedo debilitar el verificador sin contradecir un documento del cliente.

**Antipatrón vigilado:** si un test se pone rojo tras un cambio mío, la salida por defecto es **arreglar el código**, no reescribir el test. Reescribir el test solo es válido cuando el comportamiento cambió por una decisión explícita del fundador — y en ese caso queda anotado en el commit.

---

## 3. Reglas de generación

- Incrementos pequeños, un commit por cambio verificable.
- **No tocar:** el PDF del SOP, `Setter-IA-Claude-Code-Project/` (es terreno externo), secretos, ManyChat de producción.
- La base de Supabase es compartida con producción: migraciones **aditivas** únicamente, y probadas con `begin/rollback` antes de aplicar.
- Todo lo que ve el lead sale de la biblioteca de plantillas. Copy nuevo = decisión del fundador, no mía.

---

## 4. Estado

- `PROGRESS.md` (junto a este archivo) — qué se intentó, qué falló, qué queda.
- Bitácora: `01_Gobernanza_EOS/02_backlog_y_rocas.md`.
- Memoria: `artf_bot_v42_implementado`.

---

## 5. Parada, presupuesto y escalado

| Regla | Valor |
|---|---|
| **Presupuesto** | Abierto hasta sacar la v1 desplegada y probada (decisión del fundador, 2-sep-2026: *"si llegas al límite quedamos a medias"*) |
| **Reporte** | En cada checkpoint informo cuántos turnos llevo |
| **Regla de atasco** | 3 intentos fallidos sobre la misma compuerta → paro y pregunto. **Esta sigue firme:** el presupuesto abierto no es licencia para insistir en algo que no avanza |
| **Escalo siempre que** | La decisión sea de negocio (copy nuevo, un umbral del playbook, una política), no técnica |

> El tope duro se levantó a propósito, pero la regla de atasco lo reemplaza como
> freno: lo que protege el presupuesto no es un número, es no iterar a ciegas.

---

## 6. Autonomía (autonomy slider)

**Nivel actual: alto.** Acordado con el fundador el 2-sep-2026.

- **Sin preguntar:** código, tests, migraciones aditivas, commits, push.
- **Preguntando:** copy que no exista en el playbook, umbrales del negocio, cualquier cosa destructiva, y los atascos.

La guía dice que la autonomía se gana con el verificador. Este nivel se justifica porque la compuerta ya atrapó cosas reales: el bug del link (que 52 tests y el type-check no vieron) y el mismo bug repetido en objeciones, descalificaciones y bumps.

**Se baja el slider si** la compuerta deja pasar un fallo que llegue al lead.

---

## 7. Sandbox

- El Worker de prueba es un despliegue **separado**, con su propia URL, sus propios secretos y una cuenta de ManyChat/Instagram de prueba.
- Lo único compartido con producción es la base de datos — por eso las migraciones son aditivas y los leads de prueba van marcados con `[PRUEBA]`.
- El Worker exige `X-Bot-Secret` y se niega a operar si el secreto no está configurado.
