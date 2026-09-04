# RETOMAR AQUÍ — Bot conversacional ARTF V4.2

> Punto de entrada para continuar el trabajo del bot en una sesión nueva.
> **Última actualización: 3-sep-2026.**
> Estado: **desplegado y probado en vivo en Instagram.** Compuerta en verde, 179 tests.

---

## 1. Prompt para arrancar la sesión

Copia y pega esto tal cual al inicio:

```
Lee, en este orden, antes de asumir nada del estado del proyecto:
1. La memoria artf_bot_v42_implementado
2. estudio_skills_ia_claude/03_Clientes_y_Casos/02_Cliente_ARTF/PROGRESS.md
3. .../02_Cliente_ARTF/LOOPS.md  (las reglas del loop de desarrollo)
4. La bitácora 01_Gobernanza_EOS/02_backlog_y_rocas.md, sección
   "Sesión 2 y 3-sep-2026 — Bot V4.2 desplegado"

Contexto: el bot conversacional V4.2 ya está DESPLEGADO y probado en vivo en
Instagram, corriendo sobre el ManyChat de producción pero aislado con 3 frenos
(tag V42_EN_PRUEBA, lista blanca MANYCHAT_IDS_PRUEBA en el código, y
TAG_PREFIX=V42_). La compuerta ./verificar.sh está en verde con 179 tests.

Trabajamos con Loop Engineering: el loop es de DESARROLLO (tú generas, la
compuerta decide si tu trabajo pasa), no del runtime del bot. Autonomía alta:
técnico sin preguntar; copy nuevo, umbrales de negocio y atascos, preguntando.
Regla firme: si un test se pone rojo, arregla el código — no reescribas el test,
salvo que yo haya cambiado el comportamiento a propósito.

Retomamos en el paso 1 de los pendientes de la bitácora. Antes de proponerme
nada, revisa el activity_log de los leads de prueba en Supabase para ver qué
pasó de verdad, como venías haciendo.
```

---

## 2. Los siguientes pasos, en orden

| # | Tarea | Quién |
|---|---|---|
| 1 | **Redesplegar el Worker** (`npx wrangler deploy`) — el código cambió mucho desde el último despliegue | Yeison |
| 2 | Reiniciar los leads de prueba `813370090` y `1269883784` (quedaron a mitad de flujo) | Claude, una línea |
| 3 | **Probar de nuevo en Instagram** | Yeison |
| 4 | Probar la vinculación de reserva **como Setter, no como admin** — es lo que arregla H1 | Yeison |

---

## 3. ⚠️ Lo más importante que hay que mirar en la próxima prueba

**Que las 4 burbujas del turno del cierre lleguen en orden y el link quede último y clickeable.**

ManyChat no permite pausas menores a **10 segundos**, así que las burbujas van sin pausa. Con 2 burbujas ya se comprobó que funciona; **con 4 nunca se ha probado**. Si llegan desordenadas, el link deja de ser el último — que es exactamente el fallo que todo el diseño evita.

**Plan B listo** si falla: bajar el turno del cierre a 2 burbujas (saludo + link) y mover la pregunta de asistencia al turno siguiente. Son ~3 líneas en `bot_router_v42.js`, caso `M5_ENVIADO`.

### Casos que se arreglaron a ciegas y hay que confirmar en vivo

| Escribe esto | Debe pasar |
|---|---|
| `es un dato delicado para compartir por aqui` (en M1) | Responde la Objeción 6 **sin link** y repregunta el ingreso |
| `si` (a la pregunta del rango $7M–$15M) | Avanza a M2. **No** escala a humano |
| `C y B` (en el dolor) | Guarda `"B,C"` en la base |
| `no me aparece nada disponible` (tras el link) | Pide la franja horaria y escala con `agendamiento_manual_pendiente` |
| `PRUEBAV42` repetido a mitad del guion | Reenvía la pregunta pendiente, **sin** avanzar de etapa |

---

## 4. Pendientes de fondo

- 🔴 **El link del calendario es el PERSONAL de Yeison.** Antes de producción hay que cambiar `CALENDAR_LINK` de `CALENDAR_PRUEBAS` a `CALENDAR_ARTF` en `sop_v42_plantillas.js`. La compuerta valida el cambio sola.
- **Bumps del SOP de Recuperación** (30min / 24h / 72h): las plantillas están escritas, pero el disparo por tiempo necesita un **Cron Trigger** de Cloudflare, no un webhook.
- **Objeciones 4, 5, 7 y 8** siguen yendo a handoff. Ampliar es agregar el número al Set `OBJECIONES_HABILITADAS` — hacerlo cuando haya datos de cuáles aparecen de verdad.
- **Debounce real de double-texting** (Cloudflare KV): solo si las pruebas muestran que pasa seguido. Hoy no hay evidencia de que sea frecuente.
- Re-correr `e2e/setter-agendado.spec.ts` cuando el entorno esté estable (el fix está probado a nivel SQL, no con navegador).

---

## 5. Dos cosas para comentarle a Javier

1. **4 inconsistencias de renumeración en el PDF del SOP V4.2** — quedaron referencias a "Mensaje 6/7" con la numeración vieja tras el reordenamiento. Listadas en `GUIA_DESPLIEGUE_BOT_V42.md`, sección 10.
2. **`"Contame"` es voseo** y aparece en 3 archivos de su proyecto (`scripts/m5-cierre-agendamiento.md`, `scripts/m5-5-confirmacion-post-calendly.md`, `templates/handoff-message-template.md`), violando su propia Regla #2 de tuteo colombiano estricto. En nuestra copia va corregido a `"Cuéntame"`.

---

## 6. Cómo revisar el bot sin tocar Instagram

```bash
cd estudio_skills_ia_claude/03_Clientes_y_Casos/02_Cliente_ARTF
./verificar.sh                       # las 5 compuertas

cd Scrips_Worker_and_AppScript
node ver-conversacion.mjs            # todas las conversaciones del corpus
node ver-conversacion.mjs 05         # solo la del caso de Marly
```

`ver-conversacion.mjs` imprime el ida y vuelta completo como se vería en el chat, con la etapa y el estado en cada turno. **Es la forma más rápida de revisar el bot sin leer código** — y donde el ojo de Setter ve cosas que el código no.

---

## 7. Mapa de archivos

| Archivo | Qué es |
|---|---|
| `LOOPS.md` | Reglas del loop: objetivo verificable, terreno externo, presupuesto, autonomía, sandbox |
| `PROGRESS.md` | Estado del loop: qué se intentó, qué falló, qué queda |
| `GUIA_DESPLIEGUE_BOT_V42.md` | Despliegue del Worker + ManyChat, guion de prueba, limpieza de datos |
| `verificar.sh` | La compuerta. Verde = objetivo alcanzado |
| `Scrips_Worker_and_AppScript/sop_v42_plantillas.js` | Copy literal del playbook. Las perillas de alcance viven aquí |
| `Scrips_Worker_and_AppScript/bot_router_v42.js` | Lógica pura: filtros, objeciones, transiciones. Sin red |
| `Scrips_Worker_and_AppScript/verificador_cumplimiento.js` | La compuerta de cumplimiento del playbook |
| `Scrips_Worker_and_AppScript/simulador.js` | Reproduce conversaciones sin red ni base |
| `Scrips_Worker_and_AppScript/tests/corpus/` | Conversaciones REALES. Agregar una es copiar un JSON |
