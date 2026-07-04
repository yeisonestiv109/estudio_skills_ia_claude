# Facturación, Impuestos y Contratos para Freelance (Colombia) — 2026

> Investigación del coach para que el cobro a clientes (nacionales y extranjeros) quede claro. Validado vía fuentes oficiales/especializadas, jun-2026; **re-confirmado 4-jul-2026**. *Contenido reformulado para cumplir licencias; enlaces a la fuente.*
>
> 🔴 **DESCARGO IMPORTANTE: no soy contador ni abogado.** Esto es una guía orientativa para que sepas qué preguntar. Antes de facturar en serio, **consulta a un contador público** (es barato y te evita multas de la DIAN). Este punto queda como pendiente en el checklist del proyecto.

## 0. Dato base 2026

- **UVT 2026 = COP $52.374** (fijado por la DIAN). La UVT es la unidad con la que se miden los topes tributarios. [Fuente: RSM](https://www.rsm.global/colombia/en/insights/tax-compliance-2026-attention-new-withholding-bases) · [Bloomberg Law](https://news.bloomberglaw.com/daily-tax-report/colombia-tax-agency-issues-press-release-on-tax-calendar-tax-value-unit-for-2026)
  - ⚠️ *Nota jul-2026: algunas fuentes secundarias citan cifras distintas ($52.347 / $49.799). Usar $52.374 (RSM/Bloomberg) y confirmar el valor oficial con el contador.*
- **IVA general = 19%** (estable desde 2016). [Fuente](https://taxdo.com/resources/countries/la/colombia)

## 1. Lo primero: RUT y factura electrónica

- **RUT (Registro Único Tributario):** es tu identificación fiscal ante la **DIAN**. Gratis, se saca en línea. Sin RUT no puedes facturar formalmente. Debe reflejar tus **actividades económicas** (códigos CIIU de desarrollo de software / consultoría TI).
- **Factura electrónica de venta:** en Colombia la facturación electrónica con **validación previa de la DIAN** es obligatoria para quienes venden bienes/servicios. Una empresa **te exigirá factura electrónica** para poder deducir el gasto. [Fuente: Sovos](https://sovos.com/blog/company/e-invoicing-now-a-reality-in-colombia-pilot-program-concludes/)

> **Traducción práctica:** para cobrarle a una empresa B2B colombiana, necesitas RUT + estar habilitado como facturador electrónico.

### Cómo emitir la factura electrónica (opciones)

1. **Solución gratuita de la DIAN** (portal de facturación gratuito) — sirve para volumen bajo.
2. **Software de un proveedor tecnológico** (Alegra, Siigo, etc.) — más cómodo si facturas seguido. *(Validar planes/precios actuales antes de elegir; varios tienen plan económico o gratuito inicial.)*

## 2. ¿Soy "responsable de IVA" o "no responsable"?

Como **persona natural** que presta servicios, NO eres responsable de IVA (no cobras el 19%) mientras cumplas TODOS los topes de "no responsable", principalmente:

- **Ingresos brutos del año (actual o anterior) por debajo de 3.500 UVT.**
  - 3.500 × $52.374 = **≈ COP $183.300.000 al año** (2026). [Fuente: Fonoa](https://www.fonoa.com/resources/country-tax-guides/colombia)
- No tener más de un establecimiento, no operar franquicia, y que los contratos individuales y las consignaciones bancarias tampoco superen ese tope (condiciones del Estatuto Tributario).

**Implicación:**

- Por debajo del tope → eres **NO responsable de IVA**: facturas **sin** IVA. Más simple para arrancar.
- Si superas el tope → te vuelves **responsable de IVA** y debes cobrar **19%** sobre servicios de desarrollo/consultoría y declararlo. Aquí ya sí necesitas contador.

> ⚠️ Servicios de desarrollo de software/consultoría a clientes nacionales **están gravados con IVA (19%)** cuando eres responsable. No es un servicio excluido.

## 3. Clientes NACIONALES (empresas colombianas)

- Debes **expedir factura electrónica** a nombre de la empresa (con su NIT).
- La empresa probablemente te practicará **retención en la fuente** (te descuenta un % del pago y lo abona a tu impuesto de renta). Para honorarios/servicios de persona natural suele rondar **10%–11%** (honorarios) o tarifas menores para servicios, según el caso y si declaras renta. *(El % exacto lo confirma tu contador.)*
- También puede haber **retención de ICA** (impuesto municipal de industria y comercio), que varía por municipio (Popayán/Cali/Bogotá tienen tarifas distintas).

> **Para tu flujo de caja:** si cobras COP $1.600.000 y te retienen ~11%, recibes ~$1.424.000. La retención **no es un costo perdido**: se descuenta de tu impuesto de renta anual. Tenlo en cuenta al pactar precios.

## 4. Clientes EXTRANJEROS (exportación de servicios)

Aquí hay una **ventaja importante**: los **servicios exportados están EXENTOS de IVA** en Colombia (Art. 481 del Estatuto Tributario). Es decir, **NO le cobras el 19%** a un cliente del exterior. [Contexto](https://investincolombia.com.co/es/recursos/cartilla-ruta-para-la-internacionalizacion-de-servicios)

Para que aplique la exención, en general se exige:

- Que el **cliente no tenga negocios ni residencia en Colombia**.
- Que el servicio se **use o consuma exclusivamente en el exterior**.
- **Registrar/cumplir el requisito formal** ante la DIAN (registro del contrato de exportación de servicios) y conservar soporte. → **Esto es lo que debe ayudarte a montar el contador.**

**Otros puntos de cobrar al exterior:**

- Cobras en **divisas** (USD). Plataformas como Payoneer/Wise o cuenta en USD facilitan el cobro y te protegen de la devaluación.
- Aun exento de IVA, el **ingreso sí cuenta para tu impuesto de renta** en Colombia.
- Algunas plataformas (Workana/Upwork) gestionan parte del flujo; igual debes declarar el ingreso.

## 5. Impuesto de renta (no confundir con IVA)

- IVA y renta son cosas distintas. Aunque no cobres IVA, **sí puedes tener que declarar renta**.
- En 2026, los primeros **1.090 UVT ≈ COP $57.000.000** de base gravable están a tarifa 0%; por encima, tarifas progresivas (19%, 28%, 33%...). [Fuente](https://www.countrytaxcalc.com/tax-calculator/colombia/)
- **Régimen Simple de Tributación (RST):** alternativa opcional que unifica varios impuestos en una sola tarifa según ingresos; puede simplificarte la vida. Evaluarlo **con el contador**.

## 6. Seguridad social (¡no olvidar!)

Como contratista independiente debes cotizar **salud y pensión** por tu cuenta. La base de cotización (IBC) es normalmente el **40% del valor del contrato/ingreso mensual**, y sobre eso se liquidan los aportes. Muchas empresas **exigen la planilla (PILA) al día** para pagarte. Inclúyelo en tus costos al fijar precios.

## 7. El contrato de prestación de servicios (elementos mínimos)

Para cada cliente, un contrato simple pero claro evita problemas. Debe incluir:

- **Partes** (tú/ustedes como contratista, el cliente) y que es **prestación de servicios, NO relación laboral** (cláusula de no subordinación → evita que luego reclamen vínculo laboral).
- **Objeto y alcance:** qué se hace y, crítico, **qué NO está incluido** (evita el "scope creep").
- **Entregables y cronograma** (criterios de aceptación).
- **Precio, moneda y forma de pago** (ej. 50% anticipo / 50% contra entrega).
- **Propiedad intelectual:** quién queda dueño del código/entregable al pagar (normalmente el cliente al pago total; tú conservas tu know-how y librerías propias).
- **Confidencialidad** (NDA) y manejo de datos (alineado con Habeas Data).
- **Causales de terminación** y manejo de cambios (qué pasa si piden más alcance).

> Esto refuerza el error #2 de la [guía freelance](guia-freelance-30-dias.md): "no definir el alcance". El contrato es tu protección.

## 8. Checklist de acción (orden recomendado)

1. [ ] Sacar/actualizar el **RUT** con las actividades correctas (desarrollo software / consultoría TI).
2. [ ] **Hablar con un contador** (1 sesión): confirmar si arrancas como no responsable de IVA, RST sí/no, y el flujo de exportación de servicios.
3. [ ] Habilitarse como **facturador electrónico** (DIAN gratuito o software).
4. [ ] Definir **plantilla de contrato** de prestación de servicios (con cláusula de no laboralidad + PI + NDA).
5. [ ] Abrir medio de **cobro internacional** (Payoneer/Wise/cuenta USD) para clientes extranjeros.
6. [ ] Tener al día la **seguridad social (PILA)** y guardarlo como costo en los precios.

## 9. Resumen ejecutivo (lo esencial)

| Situación | ¿Cobras IVA? | Qué necesitas |
|-----------|--------------|---------------|
| Cliente colombiano (empresa), tú no responsable de IVA | **No** (bajo el tope 3.500 UVT) | RUT + factura electrónica |
| Cliente colombiano, tú responsable de IVA | **Sí, 19%** | RUT + factura + declarar IVA (contador) |
| Cliente extranjero (exportación de servicios) | **No (exento, art. 481)** | Cumplir requisitos DIAN + cobro en divisas |

> 🟡 **Pendiente real (no resoluble por IA):** una sesión con un **contador público** para personalizar esto a tu caso. Es el equivalente fiscal del "abogado para Habeas Data".
