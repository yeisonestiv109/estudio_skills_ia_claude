# Situación Contractual y Propuesta de Sociedad — Análisis Crítico

> 🔴 **NO es asesoría legal.** Es análisis de negocio + qué preguntar a un abogado laboral/comercial. Kiro no es abogado. Documento interno del fundador. Fecha: **4-jul-2026**.
>
> ✅ **Contrato recibido y analizado** (4-jul-2026). El contrato firmado (en poder del fundador) identifica a la empresa contratante, su representante legal y NIT. Aquí se referencia como **"la contratante"** para respetar el borrado de marca del repo; el análisis de cláusulas es completo.

## 1. Los hechos (según relato del fundador + contrato)

- Contrato de **prestación de servicios independiente por resultados**, fecha **29-abr-2026**, duración **6 meses → vence 29-oct-2026**. Honorarios **$1.500.000 COP/mes**. Rol: "Ingeniero Junior de Automatización e IA".
- **Empezó a trabajar el 11-may** → le pagaron menos (prorrateo).
- **~29-may a ~23-jun:** la contratante dio por **terminado sin aviso previo**, alegando que el Prospector **no daba ganancias**; quedó **pago incompleto**.
- Ahora proponen **trabajar el Prospector juntos**: el fundador recibiría **15% de comisión por venta**, posiblemente **asumiendo parte de los gastos**.
- Formalmente el contrato **sigue vigente hasta el 29-oct**, pero hoy no está trabajando.
- El informe de costos lo hizo el fundador (posible trabajo fuera de alcance).

## 2. 📜 Análisis del contrato (cláusulas clave)

| Cláusula | Qué dice | Impacto para ti |
|----------|----------|-----------------|
| **8ª — Propiedad Intelectual** | TODO lo desarrollado (código, flujos, modelos IA, docs, BD) es **propiedad exclusiva de la contratante**. Cediste **todos los derechos patrimoniales** (mundial, todo el plazo legal); conservas solo derechos morales. Los honorarios **incluyen** esa cesión. | 🔴 **El Prospector que construiste NO es tuyo para vender.** Su código/arquitectura/flujos son de la empresa. Cesión **expresa**, sin vuelta. |
| **7ª — Confidencialidad (2 años)** | No usar info confidencial —incluye **arquitecturas, flujos de automatización, modelos de IA, metodologías propietarias**— para beneficio propio o de terceros, durante y **hasta 2 años** después. | 🔴 Construir "tu versión" **reutilizando esa arquitectura/metodología** puede violar confidencialidad hasta ~2028. Tu build propio debe ser **genuinamente independiente**. |
| **9ª — No competencia (12 meses)** | NO prohíbe competir en general. Prohíbe **servir a clientes de la contratante con los que tuviste contacto** por el contrato, por **12 meses** tras terminar. | ⚠️ Puedes construir un producto similar y servir a **otros** clientes. Pero **no** a clientes de la empresa que conociste por el contrato. → **¿Catalina/TBBC entra aquí? ACLARAR.** |
| **3ª (parágrafo) + 4ª** | Terminación exige **aviso escrito con 15 días**. Al terminar se pagan **honorarios causados y no pagados**. | 🟢 **A tu favor:** terminación sin aviso de 15 días + pago incompleto = **incumplimiento**; **te deben lo efectivamente trabajado**. |
| **5ª — Seguridad social** | Debías pagar tu seguridad social como condición de pago. | Verifica si eso se usó como excusa del pago incompleto. |
| **Declaración previa + 2ª + 11ª** | Insisten fuertemente en "no subordinación"; hasta prevén causal por "contrato realidad". | El contrato está **blindado contra reclasificación laboral**, pero en Colombia **prima la realidad**. Si hubo subordinación real (jefe asignando tareas/tiempos), un juez podría reclasificar. → abogado laboral. |

### 🔧 Corrección honesta (rectifico mi lectura anterior)

En el mensaje pasado te dije "quizá la IP sea tuya si no la cedieron expresamente". **El contrato la cede expresamente (cláusula 8ª). Me equivoqué en el tono optimista; corrijo:**

- **El Prospector que construiste = propiedad de la contratante.** No lo puedes vender como producto propio.
- **"El Prospector" que veníamos tratando como tu Vía B en realidad es de la empresa.** Tu producto propio tiene que ser **algo nuevo, construido desde cero, con otro nombre** (aquí conecta el ejercicio de naming) y **arquitectura independiente**.
- Lo que **sí es tuyo para siempre:** el **conocimiento y la habilidad** de construir prospectores con IA (eso no se cede), y la **autoría/experiencia** (derecho moral) de haberlo construido.

## 3. La oferta del 15% — ahora se entiende, pero sigue siendo mala

Con la cláusula 8ª, el 15% cobra sentido desde la óptica de la contratante: **el IP es de ellos**, y te ofrecen 15% por seguir trabajando **sobre su activo**. Es coherente con el contrato, pero la economía para ti es pobre.

Usando los planes reales del [modelo de costos](../docs/tecnico/costo-por-lead.md):

| Plan | Precio/mes | Tu 15% |
|------|------------|--------|
| Natural | $149.000 | $22.350 |
| Negocio | $390.000 | $58.500 |
| Growth | $790.000 | $118.500 |
| Business | $1.900.000 | $285.000 |

**A plena capacidad del stack** (~$2,6M/mes de ingreso): tu 15% ≈ **$397.000 COP/mes**; y **~$181.000** si además compartes gastos. Para quien **construyó todo el sistema**, es ~20–25% de un salario mínimo. **No asumas gastos Y comisión baja a la vez.**

## 4. Tus opciones (marco de decisión)

| Opción | En qué consiste | Viabilidad legal | Veredicto |
|--------|-----------------|------------------|-----------|
| **A. Producto propio independiente** | Construir un prospector **nuevo desde cero** (arquitectura/código propios, nombre nuevo), para tus clientes | ✅ Legal **si** no reutilizas su arquitectura/metodología (confidencialidad 2 años) y no tocas sus clientes (no-comp 12 meses) | **Recomendada**, con disciplina de "clean room" |
| **B. Aceptar el 15%** | Vender el Prospector (de ellos) por comisión | ✅ Legal (es su IP) | Economía pobre; solo si traen clientes y cubren costos |
| **C. Renegociar** | Equity/% real por ser quien construye y opera | ✅ | Usa tu leverage: sin ti el activo no produce |
| **D. Cobrar lo adeudado y salir** | Reclamar honorarios impagos + salida limpia | ✅ | Hazlo en paralelo a A |

> **Recomendación del coach:** **Opción A + D.** Construye **tu propio producto desde cero** (nombre nuevo, arquitectura nueva) y **reclama lo que te deben**. El 15% (B) solo como canal extra si ellos realmente traen clientes que pagan y cubren el 100% de costos. Renegociar (C) solo si demuestran que aportan ventas.

## 5. ⚠️ Implicación CRÍTICA para Catalina

Si "el Prospector" que le mostrarías a Catalina es el que construiste **bajo contrato**, venderle ese sistema de forma independiente **violaría** las cláusulas 7ª (confidencialidad) y 8ª (IP de la contratante). Rutas limpias:

1. **Venderle TU producto nuevo e independiente** (Opción A) — no el de la contratante.
2. **Rutar la venta por la contratante** (esquema 15%) — legal pero es negocio de ellos.
3. **Autorización escrita** de la contratante.

Y además: **aclarar si Catalina (o TBBC) es un cliente que conociste por el contrato con la contratante.** Si lo es, la cláusula 9ª (no-competencia, 12 meses) te impediría servirle de forma independiente hasta ~mediados de 2027. **Este punto hay que resolverlo antes de avanzar con Catalina.**

## 6. Sobre "poner a mi compañera como autora"

- ✅ **Co-autoría legítima:** si tu compañera **co-crea de verdad** el producto **nuevo e independiente**, es co-autora real. Bien para una marca de dos fundadores.
- 🔴 **Atribución falsa como escudo:** poner su nombre sobre el trabajo **hecho bajo contrato** NO sirve — ese IP ya es de la contratante por cláusula 8ª, sin importar el nombre. Y declarar autoría falsa te mete un problema nuevo. La protección real = **build limpio e independiente**, no un cambio de nombre.

## 7. Diversificar más allá del Prospector (buena intuición)

Trabajar con tu compañera en **otros módulos del marco comercial** (van en M2; hay M1–M5) y empaquetar servicios (calificación M3, onboarding/retención M5) es sólido y **no toca el IP de la contratante**. Reduce dependencia y amplía catálogo.

## 8. Preguntas / acciones antes de decidir

- [ ] **Abogado laboral:** ¿pago incompleto reclamable? (terminación sin aviso de 15 días = incumplimiento). ¿Riesgo/beneficio de "contrato realidad"?
- [ ] **Abogado IP/comercial:** ¿qué tan "independiente" debe ser tu nuevo build para no rozar confidencialidad (cláusula 7ª, 2 años)?
- [ ] **Aclarar:** ¿Catalina/TBBC son clientes que conociste por el contrato? (cláusula 9ª, no-competencia 12 meses).
- [ ] Reclamar formalmente los **honorarios causados y no pagados**.
- [ ] Decidir: **A (propio) + D (cobrar)** vs. B/C.
- [ ] Si vas por A: definir **nombre nuevo** (ver [`marca-naming.md`](marca-naming.md)) y arquitectura propia documentada como creación independiente.
