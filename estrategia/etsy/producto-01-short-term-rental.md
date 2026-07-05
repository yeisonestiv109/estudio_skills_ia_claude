# Producto #1 — Sistema Financiero para Alquileres a Corto Plazo (STR / Airbnb)

> Primer activo de calidad para Etsy. Nicho **validado** (5-jul-2026). Google Sheets, mercado angloparlante (US/UK). *Fuentes reformuladas; enlaces citados.*
>
> ✅ **Este producto NO tiene relación con el prospector ni con la contratante** → IP 100% limpia, sin riesgo de confidencialidad/no-competencia.

## 1. Veredicto de validación (honesto)

**Adelante con este producto.** La dirección que elegiste está respaldada por señales corroboradas. Pero seamos precisos sobre la evidencia:

- 🟡 **El volumen exacto NO está probado** (eRank te dio "Unknown/<20" por el límite del plan gratuito). No tenemos un número duro de búsquedas; **inferimos** demanda de: (a) vistas acumuladas del Top 100, (b) listings reales con miles de ventas, (c) precios sostenidos. Es evidencia **suficiente para apostar**, pero no la vendas como "x100 probado" — es una inferencia sólida, no un dato cerrado.
- 🟢 **Precios reales confirmados** (listings vivos): **$12, $16, $18.50, $20, $20.99** (y algunos con descuento). El rango premium **$16–25** es real. [Etsy listings](https://www.etsy.com/listing/1659926008/airbnb-income-and-expense-tracker-excel).
- 🟢 **Valor de "sustituir software caro" confirmado:** los PMS (Guesty/Hostaway/Lodgify) cuestan **~$10–50+ por propiedad al mes**. Un Sheets de pago único a ~$18 que cubra la capa financiera es una historia de valor potente. [Guesty](https://www.guesty.com/blog/how-much-is-property-management-software/).
- 🔴 **Cuidado — la competencia es baja en el keyword exacto, pero los líderes son fuertes:** ya manejan 1–10 propiedades, métricas de Superhost, logística de limpieza y mapeo fiscal. "Baja competencia" **≠ fácil**. Para ganar hay que **igualar y superar** su profundidad + ejecutar mejor en claridad y estética.

## 2. El wedge (por dónde atacamos — los huecos que encontraste + validados)

1. **Multi-propiedad claro (1–5, escalable a 10):** las plantillas genéricas se enredan con más de una propiedad. Separación limpia por propiedad + consolidado.
2. **Claridad fiscal (mapeo a Schedule E):** el gran dolor no es registrar, es **declarar impuestos**. Mapear categorías de gasto a las líneas del **Schedule E** de EE.UU. Es un diferenciador fuerte… **y una zona de riesgo** (ver §6 disclaimer).
3. **Métricas que sí importan (validadas):** **ADR, Occupancy y RevPAR** son las 3 métricas núcleo del sector; más **net-per-stay** y **cash on hand**. [hostfully](https://www.hostfully.com/blog/vacation-rental-kpis/), [templacity](https://templacity.com/airbnb/airbnb-tracking/). Un dashboard con eso = "software financiero", no "hoja de gastos".
4. **Estética "software financiero de confianza"** (Minimalista Ejecutivo, light/dark), lejos de los pasteles genéricos → eleva el valor percibido.

## 3. El ángulo fiscal — oportunidad y RIESGO (leer)

Dato validado y valioso: la mayoría de STR declaran en **Schedule E (sin self-employment tax)**; si hay **"servicios sustanciales"** (limpieza frecuente, concierge, estar 24/7) puede pasar a **Schedule C (+ SE tax)**. Existe la regla de **14 días** (≤14 días alquilado → ingreso excluido) y el "STR loophole" (estancias ≤7 días + participación material). Fuentes: [hostex](https://hostex.io/blog/ar/short-term-rental-tax-deductions/), [claimyr](https://claimyr.com/government-services/irs/Short-term-rental-tax-filing-Do-CPAs-have-authority-to-decide-between-Schedule-C-vs-Schedule-E/2025-04-11).

> 🔴 **Regla de oro legal (no negociable):** **no somos asesores fiscales.** La pestaña fiscal se vende como **herramienta de ORGANIZACIÓN** ("categoriza tus gastos alineados a las líneas comunes del Schedule E para facilitar el trabajo con tu contador"), **NUNCA** como consejo tributario. Disclaimer obligatorio en el producto y en el listing (§6). Esto nos da el valor sin la responsabilidad.

## 4. Blueprint del producto (estructura del Google Sheets)

| Pestaña | Contenido | Automatización |
|---------|-----------|----------------|
| **Start Here / Setup** | Instrucciones, cómo duplicar, ajustes: lista de propiedades, plataformas, % comisión, moneda | Menús desplegables |
| **Dashboard** | KPIs por propiedad y portafolio: Occupancy %, ADR, RevPAR, ingreso bruto, neto, cash on hand + gráficos | Todo auto-calculado |
| **Bookings / Income** | Fecha in/out, noches, plataforma, bruto, **comisión auto**, fee de limpieza, **payout neto**, propiedad | Fórmulas de comisión y neto |
| **Expenses** | Categoría (mapeada a línea Schedule E), propiedad, fecha, monto, proveedor, notas | Validación + suma por categoría |
| **Per-Property P&L** | Estado de resultados por propiedad | Auto |
| **Tax Summary** | Gastos agrupados por línea de Schedule E + disclaimer | Auto |
| **Cleaning & Turnover** (bonus) | Turnos, encargado, costo, estado | Estados |
| **Supplies / Restock** (bonus) | Inventario + alertas de reabastecimiento | Alertas condicionales |

Fórmulas núcleo: `Comisión = bruto × %plataforma`; `Neto = bruto − comisión − limpieza − otros`; `ADR = ingreso / noches reservadas`; `Occupancy = noches reservadas / noches disponibles`; `RevPAR = ingreso / noches disponibles` (= ADR × Occupancy).

## 5. Documento de Diseño

- **Avatar:** host de STR con **1–5 propiedades** (US/UK), no técnico, que odia el desorden financiero y teme la temporada de impuestos; no quiere pagar $30/mes de software.
- **Estilo:** **Minimalista Ejecutivo**. Light/Dark. Tipografías limpias (Inter / Montserrat). Nada de pasteles.
- **Colores (máx. 3):** un neutro base (grafito/blanco) + 1 acento sobrio (verde-azulado o azul profundo "confianza financiera") + 1 de alerta (ámbar).
- **Moodboard:** dashboards tipo fintech/SaaS (no "planner de Canva").

## 6. Pricing, posicionamiento y disclaimers

- **Precio de lanzamiento:** **$16.99–$19.99** (premium justificado por multi-propiedad + KPIs + fiscal). Se puede escalar a versión "Lite 1-propiedad" más barata después.
- **Posicionamiento honesto:** es la **capa financiera y de rendimiento** — NO un PMS completo (no sincroniza canales ni mensajería). Decirlo claro evita reseñas malas por sobrepromesa.
- **Disclaimers obligatorios (en listing + dentro del archivo):**
  1. *Herramienta de organización; NO es asesoría fiscal/financiera/legal. Consulta a un CPA.*
  2. *No afiliado ni respaldado por Airbnb/Vrbo; las marcas son de sus dueños.*
  3. *Producto digital descargable — sin reembolsos.*

## 7. SEO del listing

- **Título (long-tail, front-load keywords):** ej. `Short Term Rental Tracker Google Sheets | Airbnb & Vrbo Income Expense Bookkeeping | Vacation Rental Spreadsheet | Multi-Property + Tax`.
- **13 tags candidatas (validar en Everbee):** short term rental, airbnb spreadsheet, vacation rental, rental income tracker, airbnb bookkeeping, str tracker, vrbo spreadsheet, property management, google sheets template, expense tracker, rental property, income and expense, airbnb host tools.
- **Descripción:** la redacto yo (SEO + beneficios + qué incluye + qué NO + disclaimers).

## 8. ⚠️ Riesgo de marca "Airbnb" (importante)

Airbnb prohíbe usar su **logo/íconos** sin permiso, y "Airbnb" es marca registrada. Muchos vendedores usan la palabra "Airbnb" en títulos (uso descriptivo para indicar compatibilidad) y Etsy lo tolera, **pero hay riesgo** de takedown por queja de marca. [Airbnb Trademark Guidelines](https://www.airbnb.com/help/article/3233/).

**Estrategia de bajo riesgo:** marca/keyword principal en **"Short-Term Rental / Vacation Rental / STR"**; usar **"Airbnb & Vrbo" de forma descriptiva** ("for Airbnb & Vrbo hosts"), **sin logos**, sin implicar respaldo. El nombre del producto/tienda debe ser **neutro** (no "Airbnb...").

## 9. Reparto de trabajo (construcción)

- **Kiro (yo):** entrego el **spec completo de pestañas/columnas/fórmulas**, los textos, título, 13 tags, descripción SEO con disclaimers, guion de mockups, y el Documento de Diseño. Puedo generar un **CSV/estructura inicial** para que la importes. *(No puedo crear el Google Sheet vivo — no tengo cuenta Google conectada; te guío paso a paso o te doy el archivo base.)*
- **Tú:** montas el Sheet en tu cuenta, validas las fórmulas, generas mockups (ChatGPT/Canva), publicas en Etsy, y corres 1 job de prueba con tus datos.

## 10. Próximos pasos

1. ¿Confirmas este blueprint? (features, estilo, precio).
2. Kiro entrega el **spec detallado de fórmulas + CSV base** de todas las pestañas.
3. Montamos el Sheet → mockups → listing (título/tags/descripción) → publicar.
4. Etsy Ads mínimos (~$1/día) + tráfico Pinterest para generar data inicial.

> **Nota de foco:** este es el activo #1 de Etsy. Calidad > rapidez. No arrancamos un segundo producto hasta publicar y medir este.
