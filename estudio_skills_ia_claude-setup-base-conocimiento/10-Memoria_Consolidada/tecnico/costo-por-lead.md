# Costo por Lead y Modelo de Planes — el Prospector

> ✅ **Datos REALES aportados por el fundador (jul-2026)**, verificados sobre facturación de las plataformas. Reemplaza la estimación modelada anterior. Referencia: **TRM $4.000 COP/USD**.
>
> ⚠️ Nota crítica de estructura de negocio: este modelo asume que **quien paga el stack se queda el margen**. Hoy eso no está definido (ver [`../../estrategia/situacion-contractual-y-sociedad.md`](../../estrategia/situacion-contractual-y-sociedad.md)). Si operas bajo comisión del 15%, **estos márgenes NO son tuyos**.

## 1. Stack pagado (solo 3 plataformas)

| Plataforma | Plan | Costo/mes (USD) | COP (~) | Para qué |
|------------|------|-----------------|---------|----------|
| Tavily | Project | $30 | ~$120.000 | Descubrir empresas, noticias/triggers, buscar contactos |
| Apify | Starter | $29 | ~$116.000 | Scraping LinkedIn (solo modo profundo/empresas) |
| Hunter | Starter | $49 | ~$196.000 | Correos verificados |
| **Stack completo (empresas)** | — | **$108** | **~$432.000** | Los 3 servicios |
| Stack solo personas (sin Apify) | — | $79 | ~$316.000 | Tavily + Hunter |

> Vercel, Supabase, Modal y Groq operan en **capa gratuita** → no suman costo.

## 2. Límites (el cuello de botella lo pone Hunter)

| Plataforma | Cupo/mes | Capacidad real |
|------------|----------|----------------|
| **Hunter** | 2.000 créditos | **~1.500 contactos verificados → LÍMITE MAESTRO** |
| Tavily | 4.000 créditos | ~950 empresas profundas · o ~5.000 búsquedas rápidas |
| Apify | ~$29 de uso | ~1.300 empresas (solo profundo) |

**Tope del sistema: ~1.500 contactos verificados/mes.** Tavily y Apify tienen holgura.

## 3. Costo marginal por lead (lo que consume de cupos ya pagados)

| Tipo de lead | Consumo | Costo | COP (~) |
|--------------|---------|-------|---------|
| Contacto rápido (persona) | 0,8 cr Tavily + 1,3 cr Hunter | ~$0,04 | ~$155 |
| Contacto profundo (empresa) | 1,2 cr Tavily + Apify + 1,3 cr Hunter | ~$0,05 | ~$190 |
| Empresa completa (~3,5 contactos) | 4,2 cr Tavily + $0,022 Apify + ~4 cr Hunter | ~$0,16 | ~$625 |

**Costo real por lead = stack mensual ÷ total de contactos del mes:**
- Media capacidad (750 contactos): **~$576 COP/lead**
- Plena capacidad (1.500 contactos): **~$290 COP/lead**

> Cuanto más se llena el stack, más barato el lead. **1 cliente = caro; 3+ = el costo por lead se desploma.**

## 4. Planes de venta propuestos

| Plan | Modalidad | Precio/mes | Cupo | Costo/lead (tú) |
|------|-----------|------------|------|------------------|
| Natural | Persona (rápido) | $149.000 (~$37) | 150 contactos | ~$155 |
| Negocio | Empresa (profundo) | $390.000 (~$98) | 150 leads | ~$190 |
| Growth | Empresa (profundo) | $790.000 (~$198) | 450 leads | ~$190 |
| Business | Empresa (profundo) | $1.900.000 (~$475) | 1.200 leads | ~$190 |

> Referencia de mercado: **Enginy** (plataforma casi idéntica) cobra desde **€799/mes (~$3,4M COP)** → hay amplio margen de precio por debajo del competidor.

## 5. Combinaciones que soporta el stack actual (respetando ~1.500 contactos)

| Combinación | Contactos | Stack | Ingreso/mes | Ganancia | Margen |
|-------------|-----------|-------|-------------|----------|--------|
| 8 Naturales (sin Apify) | 1.200 | $316.000 | $1.192.000 | $876.000 | ~73% |
| 1 Growth + 3 Negocios | 900 | $432.000 | $1.960.000 | $1.528.000 | ~78% |
| 1 Growth + 4 Negocios + 2 Naturales | 1.350 | $432.000 | $2.648.000 | $2.216.000 | ~84% |
| 1 Business | 1.200 | $432.000 | $1.900.000 | $1.468.000 | ~77% |

## 6. Conclusiones (del informe real)

1. Solo se pagan 3 plataformas: **$108/mes**. Todo lo demás es gratis.
2. El tope es **Hunter (~1.500 contactos verificados/mes)**.
3. Cada lead cuesta **~$155–190 COP marginal**; diluido baja a **~$290 COP** a plena capacidad.
4. El stack sostiene **~8 clientes pequeños o 3–4 Growth**, con margen **73–84%**.
5. Persona natural no usa Apify → arranca con stack de solo **$79/mes**.
6. **Palanca de margen:** enriquecer solo al **decisor principal** por empresa (1 contacto en vez de 3–4) **triplica** la capacidad de Hunter.

## 7. ⚠️ Lectura crítica del coach (lo que el informe no dice)

- **El límite es comercial, no técnico.** El sistema soporta ~$2,6M COP/mes de ingreso con el stack mínimo. El reto no es capacidad: es **conseguir y retener esos 3–8 clientes**.
- **El margen depende de QUIÉN paga el stack y QUIÉN cobra la venta.** Con margen 73–84% *para el dueño del negocio*. Bajo un esquema de **comisión del 15%**, tu parte sería una fracción pequeña (ver análisis en [`situacion-contractual-y-sociedad.md`](../../estrategia/situacion-contractual-y-sociedad.md) §3). No confundir el margen del negocio con tu ingreso.
- **Cuidado con el "costo cero" de Groq/Supabase/Modal:** es real a bajo volumen, pero si escalas, esas capas gratuitas tienen tope y empezarán a costar. Re-medir al crecer.
- **Hunter como cuello de botella = riesgo de dependencia.** Si Hunter sube precios o cambia cupos, tu economía unitaria se mueve. Tener plan B de verificación de correos.
