# Bitácora de Decisiones — 22 de Julio de 2026
## Descubrimiento y Scoring de los Motores 1 y 2

> ⚠️ **ESTADO: INVESTIGACIÓN CONSOLIDADA — decisiones aún NO definidas.**
> Este documento registra (a) los fixes de raíz YA implementados en el Motor 2
> (precisión + scoring), (b) el resultado del run #2 del sandbox real de TBBC,
> y (c) la investigación empírica de descubrimiento contra APIs reales
> (Apollo / TheirStack / SECOP). Las **decisiones de arquitectura de
> descubrimiento** (Híbrido Multi-Fuente, reforma del Negative ICP) están
> **en evaluación** y requieren la aprobación explícita del fundador antes de
> tocar código. Nada de las secciones 4 y 5 debe interpretarse como decisión
> tomada.

---

### 1. Contexto — Fixes de raíz implementados en Motor 2 (precisión + scoring)

Se blindó el Motor 2 con siete fixes de raíz. **444 tests verdes, `ruff`
limpio en `src`.** (Estos cambios YA están en el working tree pero AÚN NO
commiteados al abrir esta bitácora.)

1. **`ScoreTriggerPolicy` reconciliada a la spec canónica v5.0** —
   puntos base `TIER_0=200 / TIER_1=100 / TIER_2=50 / TIER_3=0`, bonuses
   `+30` multi-origen y `+50` por cruce TIER_0 con otro origen, decay
   diferenciado CAUSA `90d` / EFECTO `45d`, umbral de calificación `150`.
   **Corrección estructural adicional:** agregación **mejor-por-origen** —
   solo el trigger de mayor puntaje de cada origen contribuye al score. Un
   origen ruidoso (p. ej. múltiples entradas RSS de Google Alerts) ya **no
   puede calificar un lead por sí solo** apilando señales del mismo origen.
   Hallazgo estructural: sin esta regla, el scoring premiaba el volumen de
   una única fuente en lugar de la corroboración multi-señal.

2. **TheirStack — "dos ejes de tiempo"** — el aging de una vacante
   (`now - date_posted ≥ 45d`) determina el **TIER** (≥45d ⇒ TIER_0, señal de
   fill-rate failure), mientras que la `fecha_evento` se fija en `now` para
   que el decay de EFECTO (45d) **no mate** una vacante que sigue abierta (es
   un estado continuo, fresco en cada re-observación).

3. **SECOP — ventana ALTA alineada al decay de CAUSA (90d)** — un contrato
   adjudicado se clasifica ALTA si fue firmado hace ≤90 días, de modo que un
   TIER_0 de SECOP (CAUSA) siempre puntúe dentro de su ventana de scoring.

4. **Google Alerts — verificación semántica por LLM** — fin de la "fábrica de
   falsos C-level": las entradas RSS se validan semánticamente antes de
   convertirse en trigger de alta confianza. **Degradación con gracia:** sin
   LLM disponible, la entrada cae a `TIER_3` (mera mención), **nunca** a un
   falso-alto. Complementa (no reemplaza) el filtro de co-ocurrencia y el
   techo de confianza para nombres cortos.

5. **GitHub — verificación de dominio de la organización** — se comprueba que
   la organización de GitHub pertenece realmente al dominio de la empresa
   candidata (anti-colisión: `forbes.com` global vs. Forbes Colombia). Evita
   atribuir repos de un homónimo a la empresa evaluada.

6. **Gate de tipo de organización** — gobierno, ONG, medios, educación y
   gremios se filtran vía la Capa 2 LLM ya existente (`PropuestaValorAdapter`),
   no son ICP y no deben avanzar al scoring de señales.

7. **Heurística de país por ccTLD (estándar IANA)** — se infiere el país a
   partir del dominio de nivel superior (p. ej. `.co`, `.mx`) **antes** del
   scraping caro, para descartar geografía fuera del ICP sin gastar recursos.

**Decisión/estado:** IMPLEMENTADO y verificado (444 verdes). Es la base de
precisión sobre la que se apoya el resto de la investigación.

---

### 2. Resultado del run #2 (sandbox real de TBBC)

Corrida completa del sandbox real. **Embudo observado:**

| Etapa | Cantidad | Nota |
|---|---|---|
| Descubiertas (Apollo) | 50 | población inicial |
| Excluidas por "competencia" | 17 | **muchas MAL clasificadas** |
| Descartadas por tipo de organización | 8 | **correcto** |
| A revisión manual | 5 | fallos técnicos de scraping |
| Analizadas a fondo | 20 | |
| **Calificadas** | **0** | ningún lead superó el umbral |

- **Falsos positivos de exclusión (17):** Tecnoaguas, mayoristas, colegios,
  empresas de defensa — arrastradas por el heurístico de nombre `"tecnolog"`
  de la Capa 1 del Negative ICP. Ninguna es competidor real.
- **Descartes correctos por tipo (8):** Blu Radio (medios), Agencia Nacional
  Digital (gobierno), 6 colegios (educación) — el gate de tipo de organización
  funcionó como se esperaba.
- **Revisión manual (5):** fallos técnicos de scraping (SPAs opacas), no
  ambigüedad semántica real.

**Diagnóstico:** los filtros de precisión **funcionan**; el cuello de botella
es el **DESCUBRIMIENTO**. Apollo, con la query actual, trae la **población
equivocada**: las empresas no son software real, no tienen señales, y **no
hubo ni un solo trigger de TheirStack**. Refinar más el scoring no cambia el
resultado si la fuente de descubrimiento no entrega ICP.

---

### 3. Investigación empírica (probe de solo-lectura contra APIs reales)

Sonda de solo-lectura contra las APIs reales para entender por qué el
descubrimiento falla y qué palancas existen. Hallazgos fieles:

**Apollo (plan free):**
- `industry` viene **vacío** (es campo de pago), pero `naics_codes` está
  **SIEMPRE poblado** (observados: `541511`, `541512`, `511210/513210`,
  `518210`).
- Keyword en español `"tecnología"` → ~3-4/10 son software real; keyword en
  inglés `"software development"` → ~8/10. Un **post-filtro determinista por
  NAICS de software** deja ~76% limpio automáticamente.
- `organization_industry_tag_ids` **funciona en free** (HTTP 200); solo el
  technographic `currently_using_...` es de pago (HTTP 422).
- `estimated_num_employees` viene **vacío** en free.

**TheirStack:**
- La query actual (solo tecnología + país) trae basura (BBVA, Makro).
- La query **refinada** con `min/max_employee_count` (51/200) +
  `job_title_or` `[backend, developer, software, devops]` → **10/10 en ICP**,
  con `employee_count` y aging visibles. TheirStack sirve como **descubridor
  por señal** cuando se le dan filtros de tamaño y cargo.

**SECOP:**
- El descubrimiento por categoría UNSPSC de TI es **técnicamente viable**,
  pero los adjudicatarios resultan ser **personas naturales** → **NO sirve
  como descubridor**. Se mantiene únicamente como **señal de scoring**
  (CAUSA / TIER_0 cuando la empresa candidata ya está identificada).

**Estado:** investigación registrada. No implica cambio de código aún.

---

### 4. Propuesta EN EVALUACIÓN (NO decidida): Descubrimiento Híbrido Multi-Fuente (Opción C)

> No decidido. Requiere aprobación del fundador.

Unir dos descubridores complementarios y deduplicar por dominio:
- **Apollo** como TAM firmográfico, **mejorado** con keyword en inglés +
  post-filtro NAICS determinista de software.
- **TheirStack** como **descubridor por señal**, con filtros de tamaño
  (`51-200`) + cargo técnico.
- **∪ (unión) deduplicada por dominio.**
- **SECOP / Google Alerts / GitHub** permanecen como **scoring**, no como
  descubridores.

**Alternativas consideradas:** (A) seguir solo con Apollo + query en español
(status quo — produjo 0 calificadas); (B) solo TheirStack por señal (pierde
el TAM firmográfico frío). La Opción C está alineada con la doctrina
**multi-señal** de la literatura (evitar single-signal dependency).

**Consecuencias si se adopta:** más cobertura de ICP real, pero mayor
complejidad de orquestación y deduplicación; costo de API a revisar.

---

### 5. Propuesta EN EVALUACIÓN (NO decidida): reforma del Negative ICP

> No decidido. Origen: propuesta del fundador.

- **Eliminar** el heurístico de nombre `"tecnolog"` (Capa 1) — falsos
  positivos demostrados en el run #2 (Tecnoaguas, etc.).
- **Hard-exclude solo** para competidor directo **confirmado por LLM**
  (Capa 2).
- **Ante duda:** marcar / nurturing en vez de descartar.

**Razonamiento del fundador:** una empresa que "parece competencia" por el
nombre puede en realidad tener señales de dolor y ser un buen lead; no debe
descartarse solo porque el nombre lo sugiera. La precisión del descarte debe
recaer en la evidencia semántica (LLM sobre la homepage), no en una
subcadena del nombre.

**Consecuencia si se adopta:** menos falsos positivos de exclusión, a costa
de más llamadas a la Capa 2 LLM (más costo por candidato ambiguo).

---

### 6. Cruce con el reporte consolidado externo (validación de alineación)

Contraste de nuestra arquitectura contra un reporte consolidado externo de
estrategia de prospección.

**ALINEADOS en:**
- Jerarquía de Tiers 0/1/2/3.
- Regla de Oro (cruce de ≥2 vectores de señal).
- Descarte de señales >90 días.
- "Buscar ventanas, no empresas".
- Apollo / InfobelPRO como TAM base de Tier-3.
- Foco en Motores 1-2 primero (Motor 4 después).

**Nuance que NUESTRO trabajo empírico AÑADE (y el reporte teórico no tiene):**
- SECOP **no es descubridor** (adjudicatarios personas naturales).
- Apollo free requiere **post-filtro NAICS** para limpiar la población.
- TheirStack requiere **filtros de tamaño + cargo** para no traer basura.

**MEJORAS que el reporte aporta y AÚN no tenemos:**
- (a) **Pesos de trigger dependientes del subsector** (hoy son fijos).
- (b) Libro nuevo *The Sales Development Playbook* (Trish Bertuzzi) para una
  matriz **Fit × Intent**.
- (c) Roles **SDR / AE** (Predictable Revenue) — son proceso comercial, no
  parte del motor técnico.

**Conclusión:** vamos bien encaminados, sin divergencia de fondo. El aporte
empírico refina el marco teórico con restricciones reales de las APIs.

---

### 7. Preguntas abiertas (pendientes de decisión del fundador)

1. **NAICS de software definitivos** — propuesta: prefijos `5415`,
   `5112/5132`, `5182`. ¿Se confirma este conjunto?
2. **Aging Tier-0** — ¿45 días o 45-60 días?
3. **Info real de TBBC** (web / LinkedIn) para afinar el keyword de industria
   y la definición operativa de "competidor directo".
4. ¿Se **implementa el Híbrido C** (Apollo ∪ TheirStack, dedup por dominio)?
5. ¿Se aprueba la **reforma del Negative ICP** (eliminar heurístico de nombre)?

---
*Investigación consolidada el 22-Jul-2026. Este documento es registro de
hallazgos y propuestas, no de decisiones cerradas. Cualquier cambio de código
derivado de las secciones 4 y 5 debe pasar primero por la aprobación explícita
del fundador y quedar registrado como decisión en una entrada posterior.*
