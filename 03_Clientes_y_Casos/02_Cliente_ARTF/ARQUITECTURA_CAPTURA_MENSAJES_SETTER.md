# Cómo hacer que el bot vea lo que escribe el Setter humano

**Fecha:** 11-sep-2026 · **Estado:** diseño, sin implementar (decisión pendiente)

---

## El problema, medido

Cuando un Setter humano interviene en una conversación desde Instagram, **ese texto no queda registrado en ningún lado**. Lo comprobé contra la base: en los últimos 10 días, de leads reales, hay **cero eventos `nota` y cero `handoff`**. Solo existen `mensaje_bot`, `creacion`, `cambio_estado` y `asignacion`.

La consecuencia es concreta. El lead lee algo que escribió un humano, responde a eso, y el bot recibe esa respuesta **sin ver a qué responde**. Para el modelo es un mensaje que sale de la nada.

### Lo que ya se hizo (mitigación, no solución)

La memoria ahora incluye los eventos del equipo y los pinta como `[EQUIPO: ...]`, y el prompt le dice explícitamente al modelo que puede haber mensajes que él no ve. Eso evita el error más caro —asumir que el último mensaje lo escribió él— pero **no le da el contenido**.

---

## Opción A — Webhook de Meta (`message_echoes`). La solución real.

Meta entrega, en los webhooks de Instagram Messaging, un campo llamado **`message_echoes`**: copias de los mensajes que salen *desde la cuenta*, incluidos los que un humano escribe a mano en la bandeja. Es exactamente el dato que falta.

```
Setter escribe en Instagram
        │
        ▼
  Meta (webhook message_echoes)
        │  POST
        ▼
  Worker  /webhook/echo   ──►  Supabase activity_log
                                evento = 'mensaje_setter'
                                ultimo_msg_bot = <texto del humano>
```

**Contrato del endpoint** (queda definido para implementarlo en cuanto se decida):

| | |
|---|---|
| Ruta | `POST /webhook/echo` en el mismo Worker |
| Auth | Verificación de firma `X-Hub-Signature-256` de Meta (HMAC-SHA256 con el App Secret). **No** el `X-Bot-Secret` del webhook de ManyChat: aquí el emisor es Meta, no ManyChat |
| `GET` | Meta exige responder el *handshake* `hub.challenge` para validar la suscripción |
| Idempotencia | Por `message.mid`, que Meta envía único por mensaje |
| Efecto | Un `INSERT` en `activity_log` con `evento='mensaje_setter'`; nada más. **No** dispara al bot, **no** cambia etapa, **no** responde |
| Filtro | Descartar los ecos de los mensajes que mandó el propio bot (vienen con el mismo `mid` que ManyChat ya reportó), o quedarían duplicados |

**Lo que hay que verificar antes de construirlo** — y no lo doy por hecho:

1. **Necesita una App de Meta propia** con el permiso `instagram_manage_messages` y la cuenta de Instagram conectada a ella.
2. **Posible conflicto con ManyChat.** ManyChat ya es la app suscrita a los mensajes de esa cuenta. Hay que confirmar con la documentación de Meta si una segunda app puede suscribirse al mismo perfil sin desplazar a la primera. **Si desplaza a ManyChat, se cae el bot entero** — es el riesgo serio de este camino y hay que probarlo en una cuenta de pruebas, nunca en la de producción.
3. Requiere revisión de app por parte de Meta para permisos avanzados, que toma días.

---

## Opción B — Disparador de ManyChat

ManyChat tiene disparadores de automatización (etiqueta aplicada, campo personalizado modificado, conversación asignada). Con uno de esos se puede llamar a una External Request al Worker.

**El límite honesto:** no me consta que ManyChat exponga un disparador de *"el admin envió un mensaje"* con el **texto** del mensaje. Los disparadores de automatización entregan el contexto del suscriptor, no el contenido de lo que escribió el humano. Antes de montar nada hay que abrir el Flow Builder y revisar qué disparadores ofrece el plan actual.

Lo que **sí** se puede lograr por esta vía, si existe un disparador de toma de conversación:

- Marcar *"aquí entró un humano, a esta hora"*, que es justo lo que hoy falta para que el `[EQUIPO: ...]` tenga sentido temporal.
- Sin el texto, pero ya no a ciegas.

Si decides explorarlo, lo que habría que configurar es:

1. Un **Flow** nuevo llamado `V42_AVISO_INTERVENCION_HUMANA`.
2. Disparador: el de toma de conversación / asignación que ofrezca tu plan.
3. Acción: **External Request** → `POST` al Worker, con el header `X-Bot-Secret` y el cuerpo `{"manychat_subscriber_id": "{{user_id}}", "tipo": "intervencion_humana"}`.

---

## Opción C — La que funciona hoy, sin construir nada

**El bot ya lee los eventos `nota` del `activity_log`** (se incluyeron en la memoria el 11-sep). El dashboard ya permite escribir notas sobre un lead.

O sea: si el Setter, después de intervenir, deja una nota de una línea —*"le expliqué que la llamada es gratis"*—, el bot la ve en el historial del siguiente turno. Cero ingeniería, disponible desde ya.

Es manual y depende de disciplina del equipo, pero resuelve el 80% del daño: el bot deja de responder a ciegas justo después de una intervención.

---

## Recomendación

1. **Ahora:** Opción C. No cuesta nada y se puede empezar mañana. Vale la pena acordarlo con el Setter antes de programar cualquier otra cosa.
2. **Cuando haya tiempo:** revisar en el Flow Builder qué disparadores existen (Opción B). Es media hora de exploración y define si vale la pena.
3. **Solo si el problema persiste:** Opción A. Es la solución correcta, pero el riesgo de desplazar la suscripción de ManyChat es real y hay que probarlo primero en una cuenta de pruebas.

**Lo que necesito de ti para avanzar con A o B:** una captura de los disparadores disponibles en tu Flow Builder, y si la cuenta de Instagram está conectada a una App de Meta propia o solo a la de ManyChat.
