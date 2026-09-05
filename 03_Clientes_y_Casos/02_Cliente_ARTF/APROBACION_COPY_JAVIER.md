# Copy pendiente de tu aprobación — Bot ARTF V4.2

> Yeison → Javier. **Tres textos nuevos y dos ajustes de umbral.** Nada de esto está
> activo hoy: el bot los tiene escritos pero apagados hasta tu OK.
> Encenderlos son dos constantes y un despliegue.

---

## 1. Los tres textos nuevos

### `M2_PEDIR_SOBRANTE` — Filtro 2 — borderline

**Texto propuesto:**

> Y una última cosa para no sacar conclusiones: después de pagar todo eso, ¿cuánto te queda libre al mes, más o menos?

**Por qué:** Cuando el lead tiene deuda alta y le queda poco, hoy solo le preguntamos QUÉ TIPO de deuda es. Esto añade la segunda mitad: cuánto le sobra. Sin esa cifra no podemos rescatar a quien dio un porcentaje mal estimado.

**Cuándo lo ve el lead:** Va como segunda burbuja, después de la pregunta del tipo de deuda.

### `M4_URGENCIA_REINTENTO` — Filtro 3 — urgencia

**Texto propuesto:**

> Te lo pregunto de otra forma, [nombre]: si tuvieras el mapa claro esta semana, ¿empezarías ya, o lo dejarías para más adelante?

**Por qué:** Hoy, si no entendemos la respuesta sobre urgencia, el lead pasa a un humano al PRIMER intento. Esto le da una segunda oportunidad reformulando, en vez de escalar.

**Cuándo lo ve el lead:** Solo si la primera pregunta de urgencia no se entendió.

### `M5_PITCH_REINTENTO` — Tras el pitch

**Texto propuesto:**

> Para no darte vueltas, [nombre]: ¿te sirve que reservemos esos 30 minutos? Si no es el momento, me lo dices sin problema.

**Por qué:** Igual que el anterior pero después del pitch. Le da salida honesta: un "no" claro también es respuesta válida.

**Cuándo lo ve el lead:** Solo si la respuesta al pitch no se entendió.

---

## 2. Los umbrales de escalamiento

Tus documentos dicen, en cuatro sitios distintos:

> *"Misma objeción repetida **2 veces** → resistencia_repetida; **3+** objeciones seguidas → resistencia_acumulada."*

Hoy el bot usa **3 y 4**. Fue una decisión de Yeison del 4-sep para que aguantara una ronda más antes de pasar el lead a un humano.

**Hay un matiz importante que apareció después,** y por eso te lo consultamos:

Un QA real mostró que la regla contaba como "resistencia" cosas que son **señales de compra**. Una lead preguntó *"¿es gratis?"*, *"¿cuánto cuesta?"* y *"quiero saber más del método"* — tres preguntas de alguien interesado — y el bot la escaló. Treinta segundos después escribió *"mejor sí, agendemos"* y el bot ya estaba callado.

Se corrigió: **ahora solo cuentan las objeciones que de verdad frenan** (no tengo tiempo, déjame pensarlo, ya probé cosas así, info sensible). Las preguntas ya no suman.

**La pregunta para ti:** con ese arreglo ya puesto, ¿los umbrales vuelven a 2 y 3 como dice tu SOP, o se quedan en 3 y 4?

Nuestra recomendación es **volver a 2 y 3**: el arreglo de arriba ya hizo la regla bastante más tolerante por sí solo, y así el bot no contradice tu documento.

---

## 3. Cómo se activa

| Qué | Dónde |
|---|---|
| Los 3 textos | `COPY_PENDIENTE_HABILITADO = true` |
| Los reintentos de M4 y M5 | `ESCALERA_REPREGUNTAS_HABILITADA = true` |
| Los umbrales | `UMBRALES.RESISTENCIA_MISMA_OBJECION` y `RESISTENCIA_ACUMULADA` |

_Generado el 5-sep-2026._
