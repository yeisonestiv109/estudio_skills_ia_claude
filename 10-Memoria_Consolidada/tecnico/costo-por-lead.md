# Modelo de Costo por Lead y Precios de APIs

> **Nota Operativa Actual (Fase de Pruebas):** Actualmente, durante el Laboratorio Real (TBBC) y las pruebas de desarrollo, **operaremos en la capa gratuita (Free Tier)** de estas herramientas, rotando cuentas si es necesario para mantener el costo en cero. Sin embargo, para escalar a producción o cotizar a clientes a gran escala, dependemos del siguiente modelo de costos reales de API.

## 1. Costos Unitarios y Planes de las APIs Integradas (Actualizado)

*Los precios corresponden al uso programático vía API. Es importante notar que algunas plataformas no separan el costo de la API del costo de la suscripción.*

### A. Herramientas de Descubrimiento e Investigación
*   **Tavily (Search API):**
    *   *Free Tier:* 1.000 créditos gratis al mes.
    *   *Pago:* Pay-as-you-go a ~$0.008 por crédito. Búsquedas complejas gastan más créditos.
*   **Groq (llama-3.3-70b-versatile):**
    *   *Free Tier:* ~30 request/minuto.
    *   *Pago:* ~$0.59 por 1 Millón de tokens de entrada / ~$0.79 por 1 Millón de tokens de salida. Al ser tan barato, el costo por empresa analizada sigue siendo de centavos.

### B. Herramientas de Enriquecimiento (La Frontera de Costo Real)
*   **Hunter.io (Verificador y Buscador de Correos):**
    *   *Free Tier:* 25 búsquedas / 50 verificaciones al mes.
    *   *Pago:* Plan Starter desde **$34-$49/mes**. El consumo vía API se descuenta del mismo fondo de créditos que la aplicación web (ej. 500 créditos por el plan básico).
*   **Apollo.io (Base de datos de contactos):**
    *   *Restricción de API:* Apollo no vende la API "por consumo". **Exige tener un plan de pago (Professional u Organization)** para acceder al uso de la API.
    *   *Pago:* Plan Professional desde **~$79 por usuario/mes**. El consumo de API consume los créditos mensuales de la cuenta.

### C. Herramientas de Salida y Cierre
*   **Resend (Envío de correos e infraestructura SMTP):**
    *   *Free Tier:* Volumen básico para pruebas de desarrollo (estricto en límites diarios).
    *   *Pago:* Plan Pro desde **$20/mes** (incluye hasta 50.000 correos enviados) sin límite diario y acceso total a la REST API + Webhooks de rebote.

## 2. Cálculo del Costo Fijo y Variable
*(Este es un esqueleto analítico. Se debe correr un job de 100 empresas con los logs activos para obtener el número de créditos consumidos en la vida real y llenar esta tabla).*

| Métrica | Valor |
| :--- | :--- |
| **Costo Fijo Mensual Piso** (Suscripciones básicas Hunter + Apollo + Resend) | ~$133 - $148 USD / mes |
| **Consumo Variable por Empresa Analizada** (Tokens Groq + Búsquedas Tavily) | *Pendiente de Job de prueba* |
| **Tasa de Conversión a Lead Calificado** | *Pendiente de Job de prueba* |
| **COSTO FINAL POR LEAD CALIFICADO** | *Pendiente de Job de prueba* |

## 3. Estrategia de Mitigación de Costos
La arquitectura está diseñada con una **política de gasto defensivo**:
1. El despachador dinámico apaga fuentes innecesarias.
2. Apollo y Hunter (el costo fijo más alto) *solo* se invocan si los sensores de bajo costo detectan señales fuertes de necesidad comercial. Cero señales = Cero consultas de enriquecimiento.
