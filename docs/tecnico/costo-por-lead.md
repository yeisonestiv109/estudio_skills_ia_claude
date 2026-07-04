# Costo por Lead Calificado — Modelo y Plantilla

> Objetivo: responder con rigor a **"¿cuánto me cuesta cada lead calificado del Prospector?"** para poder cotizar a Catalina (y a cualquier cliente) sin trabajar a pérdida.
>
> 🔴 **Estado (4-jul-2026): estimación modelada, NO medición real.** El fundador ha corrido pruebas en **capa gratuita** (costo real = $0 hasta ahora). Este documento proyecta lo que costaría **en plan pago** con el consumo de un job típico. Para cerrar el número real, falta llenar la plantilla de §4 con los datos exactos de una corrida.

## 1. La conclusión primero (lo que importa para el ROI)

El costo por lead del Prospector **NO está dominado por las llamadas a las APIs por empresa** (eso es de centavos), sino por el **piso fijo de suscripciones mensuales**. Por eso:

> **El costo por lead depende sobre todo del VOLUMEN, no de la tecnología.** A bajo volumen el costo por lead es alto (el piso fijo se reparte entre pocos leads); a volumen alto, cae rápido hacia el costo variable (casi cero).

Esto tiene una implicación comercial directa: **cotizar por lead solo tiene sentido con volumen comprometido.** Para un piloto pequeño con Catalina, conviene cotizar **precio cerrado del piloto**, no "precio por lead".

## 2. Precios unitarios (verificados jul-2026, ver [validación §6](../validacion/validacion-fuentes.md))

| Servicio | Unidad | Costo | Naturaleza |
|----------|--------|-------|------------|
| Tavily | crédito (búsqueda básica=1, avanzada=2, extract≈1) | Gratis 1.000/mes; luego ~USD $0.008/crédito *(asumido, confirmar plan)* | Variable |
| Groq (Llama 4 Scout) | 1M tokens | $0.11 entrada / $0.34 salida | Variable (centavos) |
| Apify | compute unit (CU) | ~$0.20/CU (una búsqueda = fracción de CU) | Variable |
| Hunter.io | suscripción + créditos (verify 0.5 cr/email) | Starter ~$34/mes anual | **Fijo** (piso mensual) |
| Apollo.io | suscripción + créditos (email 1 cr, tel 5–8 cr) | Basic ~$49/mes anual | **Fijo** (piso mensual) |

> ⚠️ Recordatorio de validación: el costo real de Apollo/Hunter suele correr **2–3×** el precio de lista al sumar overages. Presupuestar con colchón.

## 3. Modelo estimado (con supuestos explícitos)

**Supuestos** (ajustar con datos reales):
- Un job procesa **~20 empresas** descubiertas.
- Consumo variable por empresa: Tavily ~12 créditos (~$0.10) + Groq (~$0.01) + Apify (~$0.05) ≈ **~$0.16/empresa**.
- **Tasa de rendimiento:** ~1 lead calificado por cada **4–5 empresas** → ~**4–5 leads calificados por job**.
- Piso fijo mensual si operas en pago: Hunter (~$34) + Apollo (~$49) ≈ **~$83/mes** (+ Tavily plan si superas los 1.000 gratis).

**Costo variable por lead:** ~$0.16 × 4.5 empresas/lead ≈ **~$0.70/lead** (dominado por Tavily+Apify; enriquecimiento marginal dentro del plan).

**Costo total por lead = piso fijo / leads del mes + variable:**

| Leads calificados / mes | Fijo por lead (~$83) | + Variable (~$0.70) | **Costo total por lead** |
|-------------------------|----------------------|---------------------|--------------------------|
| 10 | $8.30 | $0.70 | **≈ $9** |
| 50 | $1.66 | $0.70 | **≈ $2.4** |
| 100 | $0.83 | $0.70 | **≈ $1.5** |
| 250 | $0.33 | $0.70 | **≈ $1.0** |

> **Lectura:** el costo por lead calificado cae aproximadamente en la banda **$1.5 – $9 USD**, y el número exacto lo decide el **volumen mensual**, no el pipeline. Sin volumen comprometido, cada lead sale caro.

## 4. Plantilla para el NÚMERO REAL (llenar con tu job)

Para reemplazar la estimación por el dato duro, necesito de una corrida real estos **6 números**:

| Dato | Valor de tu job | Notas |
|------|-----------------|-------|
| Empresas procesadas en el job | ______ | Cuántas descubrió/procesó |
| Créditos Tavily consumidos | ______ | Visible en el dashboard de Tavily |
| Compute units (CU) de Apify | ______ | Dashboard de Apify |
| Créditos Hunter/Apollo usados | ______ | Emails/teléfonos enriquecidos |
| Tokens Groq (entrada/salida) | ______ / ______ | Aprox., del log del job |
| **Leads CALIFICADOS resultantes** (`es_calificado=true`) | ______ | El denominador clave |

Con eso calculo: `costo_variable_total / leads_calificados` = **costo variable real por lead**, y le sumo el piso fijo del plan que elijas para el costo total.

## 5. Recomendación del coach

1. **Para el piloto de Catalina: cotiza precio cerrado del piloto** (no por lead). Aún no hay volumen ni ICP para justificar un precio unitario.
2. **Corre 1 job real y llena §4** antes de proponer cualquier plan mensual. Es el dato que separa una cotización seria de una adivinanza.
3. Cuando definas pricing recurrente, el margen sano exige **volumen mínimo comprometido** (para diluir el piso fijo). Piensa en planes tipo "X leads/mes" con mínimo, no "pago por lead" abierto.
