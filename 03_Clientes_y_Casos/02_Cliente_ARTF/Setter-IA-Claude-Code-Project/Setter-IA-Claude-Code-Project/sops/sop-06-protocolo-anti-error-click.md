# SOP-06 · Protocolo Anti-Error de Click en el Inbox de IG

> **Por qué existe este SOP:** durante operación en vivo, la lista de chats de Instagram se reordena CONSTANTEMENTE conforme entran mensajes nuevos de otros leads. Hacer click "por memoria de posición" en lugar de verificar nombre te lleva a chats equivocados. Esto se ha detectado **3 veces el 2026-05-22** (R1: Juliana, R4: Gabriel x2) y debe quedar eliminado del flujo.

---

## La regla suprema

**NUNCA tipees un mensaje sin verificar EXPLÍCITAMENTE el header del chat (panel derecho) en el screenshot inmediato anterior.**

Si el screenshot que tienes en context muestra el header de "X" pero estás escribiendo un mensaje destinado a "Y", **detente y aborta**.

---

## Flujo correcto de navegación entre chats

### Paso A — Screenshot fresco SIEMPRE antes de cualquier click de navegación

```
1. screenshot del inbox completo
2. leer la lista: nombre + estado + tiempo
3. decidir cuál es el siguiente chat objetivo
4. CONFIRMAR la coordenada y observar el nombre EN el screenshot
5. click
```

### Paso B — Después del click, OTRA screenshot ANTES de tipear

```
1. click en el chat objetivo
2. wait 2 segundos
3. screenshot
4. LEER EL HEADER del panel derecho (nombre del lead)
5. SI header coincide con el objetivo → proceder a tipear
6. SI header NO coincide → ABORTAR, volver al inbox, intentar de nuevo
```

### Paso C — Si la lista se reordenó múltiples veces

**Síntomas de fatiga del inbox:**
- Has hecho >5 clicks en la ronda y la lista ha cambiado entre cada uno.
- Has tenido 1+ errores ya.
- El counter de notificaciones cambia entre screenshots.

**Estrategia más segura:** usar la **búsqueda por nombre** en lugar de click por posición:
1. Click en el campo "Buscar" (arriba en la sidebar de chats).
2. Tipear el nombre del lead objetivo.
3. Click en el resultado.
4. Verificar header.

Esto elimina por completo el riesgo de reordenamiento.

---

## Anti-patterns observados (NO repetir)

### Anti-pattern 1 — Encadenar clicks sin verificar
```
❌ click(y=370) → type "Aleja, te entiendo..." → enter
❌ click(y=370) → type "Vanessa, te entiendo..." → enter  ← lista reordenada
```
**Consecuencia real:** Vanessa fue para Gabriel (2026-05-22, R4).

### Anti-pattern 2 — Asumir que la coordenada del chat anterior sigue válida
```
❌ click(y=655) → escribir M5 a Ángela → 
   click(y=725) pensando que es Harol → 
   pero Harol pasó a y=805 porque entró Sara Luna
```

### Anti-pattern 3 — No leer el screenshot después del click
```
❌ click → wait → type directamente
```
Sin re-leer el header, no hay forma de detectar el error antes del envío.

---

## Patrón correcto (PEGAR como template mental antes de cada click)

```
[screenshot fresco]
↓
"En este screenshot veo: [nombre del lead objetivo] en posición [y=X]"
↓
click(y=X)
↓
wait 2
↓
[screenshot fresco]
↓
"El header dice: [nombre actual]. ¿Coincide con el objetivo? Sí/No"
↓
SI sí → tipear mensaje (con vocativo del nombre verificado en el header)
SI no → abortar, volver al inbox, intentar de nuevo
```

---

## Si igual ocurre el error (manejo)

Pasos exactos:

1. **NO tipees más mensajes en ese chat.**
2. Si ya enviaste el mensaje al chat equivocado, **disculpa breve y honesta** en ese chat:
   ```
   Disculpa [Nombre], ese mensaje anterior se fue por error a tu chat 🙊
   ```
3. **Vuelve al inbox** y busca el chat correcto **por nombre** (no por coordenada).
4. Verifica el header del chat correcto.
5. Envía el mensaje original al chat correcto.
6. En el reporte de la ronda, documenta el error como parte del aprendizaje.

**NO escalas a humano por este motivo** — es error operativo, no del flujo.

---

## Para el Agente Setter IA (cuando opera en producción API)

Aunque el LLM no opera en IG directamente, este SOP-06 es relevante porque:
- El sistema externo (n8n/Make) que orquesta los mensajes debe identificar al lead por **conversation_id único** (NO por nombre ni por posición).
- En cada turno, el sistema reinyecta el contexto del lead correcto al modelo.
- El modelo debe verificar en `metadata.resumen_lead.nombre` que el `[Nombre]` que va a usar en el mensaje coincide con el lead activo.

Si el sistema externo pasa un `conversation_id` con un `nombre` inconsistente al historial recibido → flag el error y handoff.

---

## Para el operador humano (Javier, Catalina, Setter humano)

Cuando ejecutes una ronda manualmente en IG web:

1. **Antes de empezar:** ten una pestaña con este archivo abierta.
2. **Cada chat:** sigue el "Patrón correcto" arriba paso por paso.
3. **Si tienes prisa:** usa el campo de búsqueda en lugar de scroll + click.
4. **Si te equivocaste:** disculpa breve y sigue.
5. **Al final de la ronda:** anota cuántos clicks y cuántos errores. Si errores > 0, considera trabajar más despacio.

---

## Historial de incidentes

| Fecha | Operador | Lead esperado | Lead equivocado | Causa |
|---|---|---|---|---|
| 2026-05-22 R1 | Setter IA | Xiomara | Juliana | Lista se reordenó al hacer scroll → coordenada y=866 ya no era Xiomara |
| 2026-05-22 R4 | Setter IA | Vanessa Hoyos | Gabriel Torres | Click en y=867 con lista reordenada |
| 2026-05-22 R4 | Setter IA | Vanessa López Suaza | Gabriel Torres (2da vez) | Mismo patrón, no escarmentado todavía |

---

## Lecciones operativas

1. **El inbox de IG NO es estable durante operación intensa.** Asume reordenamiento entre cada click.
2. **El costo de verificar el header (1 screenshot) es mucho menor que el costo de un error (1 disculpa + posible quemado de lead).**
3. **Errores en cadena (mismo patrón 2-3 veces) indican que el operador no aprendió** — pausar, releer este SOP, retomar.
4. **La búsqueda por nombre es el método más seguro** cuando la lista se mueve mucho.
