# Template · Catálogo de Reels por Dolor

Mapeo de los reels de Andrés Ramírez para usar en:
- **Descalificación con valor** — cuando el lead no califica y le damos algo útil.
- **Objeciones (D no-financiero)** — reconducción suave con un recurso.

> 🚫 **Bump 3 General NO usa este catálogo.** Desde 2026-05-23 el Bump 3 General usa siempre el reel fijo `https://www.instagram.com/reel/DX73ACPNvRV/?igsh=MXQ3anYycWUzNXBoMA==` (el mismo del Bump 3 de Agendamiento). Ver `scripts/bumps-recuperacion.md`.

---

## Reels actuales

| Dolor / Tema | Reel | Cuándo usarlo |
|---|---|---|
| **Gastos hormiga** (no sé en qué se me va) | https://www.instagram.com/reel/DJDejvjtfzH/?igsh=MW5qY2s2a2VqM2VmdQ== | Lead dolor B en M2. Lead que menciona "gastos pequeños que suman". Lead descalificado por bajo ingreso pero quiere optimizar. |
| **Hábitos de ahorro** | https://www.instagram.com/reel/DJDejvjtfzH/?igsh=MW5qY2s2a2VqM2VmdQ== | Lead que ya tiene ingresos altos pero no logra ahorrar. Caso genérico de descalificación con valor cuando el dolor no es claro. |
| **Beneficios de tarjetas de crédito** | https://www.instagram.com/reel/DJDejvjtfzH/?igsh=MW5qY2s2a2VqM2VmdQ== | Lead que menciona problema con tarjetas de crédito específicamente. Lead con deudas tipo "estatus". |
| **Bump 3 fijo (General + Agendamiento)** | https://www.instagram.com/reel/DX73ACPNvRV/?igsh=MXQ3anYycWUzNXBoMA== | Reel único para ambos Bump 3. No se elige por dolor — siempre este. Ver `scripts/bumps-recuperacion.md`. |

---

## Cómo elegir el reel correcto

Mira la última respuesta concreta del lead antes del silencio:

| Si el lead dijo... | Usa el reel de... |
|---|---|
| "No sé en qué se me va la plata" / "Se evapora" | Gastos hormiga |
| "Me gano X pero no logro ahorrar" / "Nunca queda" | Hábitos de ahorro |
| "Las tarjetas de crédito" / "Pago el mínimo" / "Tengo varias tarjetas" | Beneficios de tarjetas de crédito |
| Lead silencioso después de M1/M2/M3 (Bump 3 General) | **Reel fijo DX73ACPNvRV** (no se elige por dolor) |
| Lead silencioso después del link de Calendly (Bump 3 Agendamiento) | **Reel fijo DX73ACPNvRV** (no se elige por dolor) |
| Caso genérico sin dolor claro (descalificación con valor) | Hábitos de ahorro (default) |

---

## Plantillas de uso

### En Bump 3 General (lead silencioso después de M1/M2/M3):

```
[Nombre], me alegra que hayas llegado hasta aquí, aunque no hayamos podido hablar. 😊 Te dejo este video que a mucha gente le ha servido un montón: https://www.instagram.com/reel/DX73ACPNvRV/?igsh=MXQ3anYycWUzNXBoMA==

Si algo resuena contigo, ya sabes dónde encontrarme. ¡Éxitos!
```

**Wording oficial** — copiar tal cual desde `scripts/bumps-recuperacion.md`. Link fijo, NO se sustituye por dolor.

### En Bump 3 de Agendamiento (lead silencioso después de M5/Calendly):

```
[Nombre], último mensaje, lo prometo. 😄

Te dejo este video antes de irme, creo que te va a servir:
https://www.instagram.com/reel/DX73ACPNvRV/?igsh=MXQ3anYycWUzNXBoMA==

Si en algún momento quieres retomar, aquí estoy. ¡Éxitos! 💪
```

### En Descalificación con valor:

```
Gracias por la sinceridad, [Nombre].

Con lo que me cuentas, creo que mi programa todavía no es el mejor fit para ti [razón breve].

Igual, no quiero que te vayas sin nada. Te recomiendo este recurso sobre [tema relacionado a su dolor]:
[LINK_DEL_REEL_SEGÚN_DOLOR]

Te va a dar claridad sobre [beneficio específico]. Impleméntalo y va a hacer una diferencia enorme.

Cualquier cosa, acá estoy. ¡Éxitos! 💪
```

---

## ⚠️ Regla del link aislado aplica también aquí

Cuando envíes un reel en chunking:
- **Texto antes del link**, luego turno separado con SOLO el link.
- Nunca texto después del link en el mismo turno.

Ejemplo (caso de descalificación con valor, donde sí se elige reel por dolor):
```json
"mensaje_para_lead": [
  "Gracias por la sinceridad, [Nombre].\n\nCon lo que me cuentas, creo que mi programa todavía no es el mejor fit para ti.\n\nIgual, no quiero que te vayas sin nada. Te recomiendo este recurso:",
  "https://www.instagram.com/reel/DJDejvjtfzH/?igsh=MW5qY2s2a2VqM2VmdQ==",
  "Te va a dar claridad sobre [beneficio]. ¡Éxitos! 💪"
]
```

⚠️ En el Bump 3 General/Agendamiento NO se chunkea — se envía todo como un solo mensaje con el link inline (ver wording oficial arriba).

⚠️ En la práctica Instagram suele renderizar bien los reels propios (de la misma cuenta) sin romper el link, pero por consistencia con la regla de Calendly aplica la misma disciplina.

---

## Mantenimiento del catálogo

Cuando Andrés publique un reel nuevo que cubra un dolor del avatar:

1. Agregarlo a la tabla "Reels actuales".
2. Definir cuándo usarlo en la tabla "Cómo elegir el reel correcto".
3. Si reemplaza a uno existente, actualizar referencias en `scripts/bumps-recuperacion.md` y `scripts/descalificacion-con-valor.md`.

---

## Historial de cambios

- **2026-05-22:** Catálogo creado con los 3 reels iniciales entregados por Javier + el reel del Bump 3 de Agendamiento (DX73ACPNvRV).
- **2026-05-23:** Bump 3 General ya NO usa mapeo variable por dolor — usa el mismo reel fijo (DX73ACPNvRV) que el Bump 3 de Agendamiento. Catálogo de dolor restringido a Descalificación con valor + Objeciones (D no-financiero). Wording final del Bump 3 General actualizado a "¡Éxitos!" (sin "Muchos" ni 👋).
