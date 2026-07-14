# Validación de Fuentes y Lectura Crítica

Documento del coach. Aquí se separa lo que es **dato verificado**, lo que es **marco mental útil** y lo que es **opinión/hype**. Regla del proyecto: nada pasa a ejecución sin pasar por aquí. Última validación de base: **23-jun-2026**. Re-verificación: **4-jul-2026** (ver §8).

## Semáforo de validación

🟢 Verificado · 🟡 Útil pero con matices · 🔴 Riesgo / hype / requiere cuidado

## Estado consolidado (resumen ejecutivo)

| Bloque | Estado | Lectura |
|--------|--------|---------|
| Datos técnicos (Antigravity, Claude Opus 4.8, Next.js 16, stack del Prospector) | 🟢 Todo verificado | Confirmado con fuentes oficiales jun-2026, re-confirmado jul-2026 |
| Precios de APIs + costo por lead | 🟢 Resuelto | Tarifas unitarias verificadas; ver §6. Falta medir consumo real en una corrida |
| Versión Claude Opus 4.8 | 🟢 Confirmado | Lanzado 28-may-2026 |
| Marcos de negocio (Pareto, 3 reglas, Arquitecto Digital) | 🟢 Sólidos | Aplicar como filtros operativos |
| Habeas Data Colombia (Ley 1581) | 🔴 Riesgo real, no eliminable | Régimen de **consentimiento**, no de "interés legítimo". Ver §3 + §7 |
| Scraping LinkedIn / dropshipping "gratis" / "Stay Broke" | 🔴 Se mantienen en rojo a propósito | Son riesgos por naturaleza; tienen decisión documentada, no desaparecen |

> ⚠️ **Nota honesta del coach:** se pidió "todo en verde, nada por revisar". Lo verificable ya está en verde con fuentes. Pero hay rojos que **deben seguir rojos** porque el riesgo es real (legal, financiero). Pintarlos de verde sería la psicofancia que acordamos evitar. Lo que sí hicimos: cada rojo pasa de "pendiente" a "decisión tomada + mitigación documentada".

## 1. Datos técnicos (búsqueda web, jun-2026)

| Afirmación original | Veredicto | Detalle |
|---------------------|-----------|---------|
| Google Antigravity es un IDE agéntico con navegador integrado y "Manager" | 🟢 | Real. Preview público 18-nov-2025 junto a Gemini 3 Pro; fork de VS Code con editor + agent manager + terminal + navegador Chromium |
| Claude Code maneja 1M tokens de contexto | 🟢 con matiz | La ventana de 1M tokens es real. Matiz: "Claude Code" es la herramienta CLI; el modelo es Opus 4.x |
| "Modelo Opus 4.8" | 🟢 verificado | Confirmado: Claude Opus 4.8 lanzado el 28-may-2026. Opus 4.6/4.7 también vigentes. Regla: citar versión + fecha siempre |
| Next.js 16.2.6 + React 19 + Turbopack | 🟢 | Real. Next.js 16.2.6 estable (may-2026), Turbopack por defecto, React 19.2 |
| Kiro = desarrollo basado en especificaciones (spec-driven) | 🟢 | Correcto; es la plataforma donde se redacta este repositorio |
| ANI / AGI / ASI, LLM, API, sycophancy, vibe coding | 🟢 | Definiciones correctas y de uso estándar en la industria |
| Stack del Prospector (FastAPI, Supabase/Postgres, Modal, Groq, Llama 4 Scout, Apify, Hunter, Tavily) | 🟢 | Todas son tecnologías reales y combinables; arquitectura coherente. Precios unitarios en §6 |

## 2. Marcos de negocio

| Idea | Veredicto | Lectura del coach |
|------|-----------|-------------------|
| Regla 80/20 (Pareto) | 🟢 | Principio sólido y medible. Aplicar a priorización semanal |
| 3 reglas de oro (ganar dinero / ahorrar tiempo / ahorrar dinero) | 🟢 | Excelente filtro de propuestas B2B. Cuantificar siempre |
| 4 áreas de la empresa | 🟢 | Marco clásico y correcto para evitar cuellos de botella |
| Arquitecto Digital vs Freelancer | 🟢 | Posicionamiento de valor real. Es el núcleo de nuestra diferenciación |
| SAR/RAS (atención selectiva) | 🟡 | Neurociencia real, pero no es "manifestación". Sirve por enfoque + acción, no por "atracción" |
| Consultoría de IA como modelo top | 🟡 | De acuerdo, pero exige credibilidad/casos. Por eso arrancamos con freelance para construir prueba social |
| Generación de leads con IA (el Prospector) | 🟡 | Rentable pero commoditizable. Defender con nicho + calidad, no con "tenemos scraper" |
| E-commerce / Dropshipping "sin inversión" | 🔴 | Engañoso: requiere capital fuerte en ads y márgenes finos. No es "gratis". Se mantiene rojo |
| "Stay Broke" (descapitalizarse a propósito) | 🔴 | Peligroso para quien necesita caja. Versión sana: fondo de emergencia primero, reinvertir solo excedente. Se mantiene rojo |
| "Capítulo solitario" | 🟡 | Hay verdad (cambian los círculos), pero no romantizar el aislamiento; buscar tribu sana |

## 3. Riesgos legales y operativos (atención prioritaria)

| Riesgo | Veredicto | Acción mínima / decisión |
|--------|-----------|--------------------------|
| Scraping de LinkedIn (Apify `google-search-scraper`) | 🔴 | Puede violar ToS → bloqueo de cuentas. Decisión: usar solo datos públicos de resultados de búsqueda, sin login ni simulación de sesión; tener fuentes alternativas (Apollo) y no depender de una sola técnica |
| Habeas Data (Ley 1581/2012, Colombia) — **CORREGIDO** | 🔴 | ⚠️ Corrección: Colombia NO usa "interés legítimo" como base legal (eso es GDPR europeo). La Ley 1581/2012 exige **consentimiento previo, expreso e informado**, y la SIC sanciona. Detalle y mitigación en §7 |
| Cold email | 🟡 | Incluir identificación, motivo y opción de baja; no comprar listas dudosas; cuidar reputación de dominio (SPF/DKIM/DMARC) |
| Dependencia de muchas APIs de pago | 🟡 → 🟢 en proceso | Métrica unitaria = costo por lead calificado. Tarifas ya verificadas (§6); falta medir consumo real de UNA corrida para cerrar el número |
| Sycophancy de la IA en decisiones | 🟡 | Pedir siempre a la IA contras/críticas; verificar datos con fuentes. Este documento es ejemplo de esa disciplina |

## 4. Pendientes de validación — ESTADO ACTUALIZADO

- ✅ **Precios/límites de las APIs** (Tavily, Apollo, Hunter, Groq, Apify). Resuelto. Tarifas verificadas en §6 (re-confirmadas jul-2026).
- ✅ **Versión y disponibilidad de Opus 4.8.** Confirmado: GA desde 28-may-2026.
- 🟡 **Asesoría legal Habeas Data para prospección B2B en Colombia.** Sigue abierto: requiere abogado real (no IA). Marco de mitigación documentado en §7.
- 🔴 **Medir el consumo real de una corrida del Prospector** (créditos Tavily + CU Apify + créditos Hunter/Apollo + tokens Groq por job) para confirmar el costo por lead estimado en §6. **No resoluble por IA:** exige correr un job real.

## 5. Credibilidad del perfil del fundador (lectura crítica)

| Punto | Veredicto | Acción |
|-------|-----------|--------|
| Fechas de experiencia solapadas siendo estudiante | 🟡 | Enmarcar honestamente como roles freelance/contract/part-time concurrentes. Solapamientos sin contexto generan dudas |
| Discurso "no necesito saber programar, para eso está la IA" vs. CV de ingeniería real | 🟡 | Reconciliar: el activo fuerte es el foso técnico + visión de negocio. No subvalorar la ingeniería con el discurso de "vibe coder" |
| Prueba social pública (LinkedIn/GitHub, casos) | 🔴 pendiente | Pulir perfiles y publicar demos/casos (el Prospector como caso estrella) sin exponer datos de clientes. Sin prueba social, el posicionamiento premium no se sostiene |

## 6. Precios de APIs verificados y costo por lead (jun-2026, re-verificado jul-2026)

Tarifas unitarias confirmadas vía páginas oficiales y comparativas. *Contenido reformulado para cumplir licencias; enlaces a la fuente.* Los planes cambian: re-verificar antes de cada decisión de presupuesto.

| Servicio | Tarifa unitaria verificada | Plan de entrada | Fuente |
|----------|-----------------------------|-----------------|--------|
| **Tavily** (Search) | Búsqueda básica = 1 crédito; avanzada = 2 créditos | Gratis 1.000 créditos/mes (sin tarjeta), luego pago por uso | [docs](https://docs.tavily.com/documentation/api-credits) |
| **Groq** (Llama 4 Scout 17B) | ~$0.11 / 1M tokens entrada · ~$0.34 / 1M tokens salida | Tier gratis ~30 req/min | [Groq](https://groq.com/pricing) |
| **Apify** (scrapers) | ~$0.20 por compute unit (CU); migrando a pago por evento | Pago por uso | [Apify](https://apify.com/pricing) |
| **Hunter.io** (email) | Verificar = 0.5 crédito/email | Gratis; Starter $34/mes anual ($49 mensual) | [cleanlist](https://www.cleanlist.ai/blog/2026-03-19-hunter-pricing-guide) |
| **Apollo.io** (contactos) | Export email = 1 crédito; teléfono = 5–8 créditos | Gratis 10 export/mes; Basic $49, Pro $79, Org $119/usuario/mes (anual) | [cleanlist](https://www.cleanlist.ai/blog/2026-03-19-apollo-pricing-guide) |

> ⚠️ **Costo oculto que el coach subraya:** varios análisis coinciden en que el costo real de Apollo/Hunter corre **2–3× por encima** del precio de lista una vez sumas overages de créditos y verificación. Presupuesta con ese colchón.

### Modelo de costo por lead (estimación, pendiente de medición real)

Por empresa procesada, el Prospector consume aproximadamente:

- **Tavily:** descubrimiento (3 consultas) + noticias (3 consultas + 3 extracts) → del orden de 10–15 créditos.
- **Groq (Llama 4 Scout):** varias llamadas por fases; al ser tan barato (~$0.11/$0.34 por 1M), el costo por empresa es de centavos (típicamente < $0.02).
- **Apify:** una corrida de búsqueda → fracción de CU → unos centavos.
- **Hunter/Apollo:** 1 crédito de email por contacto válido (+5–8 si se pide teléfono en Apollo).

**Orden de magnitud estimado:** el costo variable por empresa procesada está dominado por Tavily + enriquecimiento; si ~1 de cada 4–5 empresas produce un lead calificado, el costo variable por lead calificado cae en una banda baja (pocos dólares o menos). A esto hay que sumar el **piso fijo mensual** de suscripciones (Hunter desde ~$34, Apollo desde ~$49). Sin volumen, el costo fijo por lead es alto; con volumen, baja rápido.

> ✅ **Acción para cerrar este punto en verde duro:** correr UN job real del Prospector y leer el consumo exacto (créditos Tavily, CU Apify, créditos Hunter/Apollo, tokens Groq). Con ese dato se reemplaza la estimación por el número real de costo por lead calificado.

## 7. Habeas Data Colombia — marco de mitigación (NO es asesoría legal)

Corrección crítica al doc anterior. **No soy abogado; esto es un marco operativo** para reducir riesgo mientras se consigue asesoría legal real (sigue como pendiente en §4).

**El hecho verificado (re-confirmado jul-2026):** la Ley 1581 de 2012 exige **autorización previa, expresa e informada** del titular antes de recolectar o tratar sus datos personales; la autoridad que vigila y sanciona es la **Superintendencia de Industria y Comercio (SIC)**. El marco se complementa con la Ley 1266 de 2008 y el Decreto reglamentario 1377 de 2013. Fuentes: [recordinglaw](https://recordinglaw.com/world-laws/world-data-privacy-laws/colombia-data-privacy-laws) · [clym.io](https://clym.io/regulations/colombia-law-1581). *Contenido reformulado para cumplir licencias.*

**Por qué importa para el Prospector:** el modelo recolecta nombre, cargo, email y a veces teléfono de personas (decisores). Aunque sea contexto B2B, eso son **datos personales** bajo la ley colombiana. El concepto europeo de "interés legítimo" (GDPR) **no** es una base legal equivalente en Colombia.

**Mitigaciones operativas** (reducen riesgo, no lo eliminan):

- Priorizar datos de contacto corporativos/genéricos (`info@empresa`, líneas públicas) sobre datos de una persona identificada.
- En cada cold email: identificación clara del remitente, motivo y un canal de baja (opt-out) funcional.
- Atender de inmediato solicitudes de conocer, actualizar, rectificar y suprimir datos (derechos del titular).
- Mantener una **política de tratamiento de datos** publicada y evaluar si aplica el registro de bases de datos ante la SIC.
- No revender ni compartir las listas con terceros.
- Conseguir concepto de un **abogado de protección de datos** antes de operar a escala o con clientes que exijan cumplimiento.

> 🔴 Este punto **se queda en rojo a propósito**. Es el riesgo más subestimado del modelo de prospección. La mitigación lo hace operable con bajo perfil, pero el cierre real exige abogado.

## 8. Re-verificación 4-jul-2026 (actualización de este documento)

Se re-corrieron las validaciones web clave. Resultado: **los datos de junio se sostienen.** Detalle:

- **APIs:** Tavily (1.000 créditos gratis/mes, sin tarjeta) ✅; Groq Llama 4 Scout ($0.11 in / $0.34 out) ✅; Apollo (free 10 export/mes; $49/$79/$119 anual; email 1 crédito, teléfono 5–8; costo real 2–3×) ✅; Hunter (Starter $34 anual / $49 mensual; verificación 0.5 crédito) ✅. Sin cambios materiales.
- **Tributario:** UVT 2026 = **COP $52.374** (confirmado por RSM/Bloomberg). ⚠️ Aparece dispersión menor en fuentes secundarias (una cita $52.347, otra $49.799); usar $52.374 y **confirmar con contador**. IVA general 19% estable. Umbral no responsable de IVA 3.500 UVT y renta 0% hasta 1.090 UVT: vigentes.
- **Legal:** Habeas Data (Ley 1581/2012 + Ley 1266/2008 + Decreto 1377/2013): consentimiento previo/expreso/informado, SIC como autoridad. Sin cambios; sigue 🔴.
- **Naming (nuevo hallazgo):** al validar el favorito **"Cierzo"** aparecieron **colisiones fonéticas en el mismo espacio**: **"Cizo"** (perfil corporativo *cizo1*, "AI product engineering + business process automation") es casi homófono y compite en IA/automatización; también existen **"Ciergo"** (plataforma de experiencia de residentes) y **"Ciertech"** (dev Odoo). → Riesgo de confusión de marca. Detalle en [`../../estrategia/marca-naming.md`](../../estrategia/marca-naming.md) §Ronda 3.

## Metodología

Validación vía búsqueda web sobre fuentes oficiales/documentación (Anthropic, Next.js, Groq, Tavily, Apify, Hunter, Apollo, SIC, DIAN/RSM) y cruce de múltiples resultados. *Contenido de fuentes externas reformulado y resumido para cumplir restricciones de licencia; se citan los enlaces originales.*
