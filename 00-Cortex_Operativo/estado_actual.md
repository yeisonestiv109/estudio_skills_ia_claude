# Handoff Diario y Estado Actual
**Fecha:** 17 de Julio de 2026
**Fase:** Motores 1 y 2 BLINDADOS (afinamiento post-piloto TBBC). Motor 3 y Motor 4 completados. → Objetivo: VALIDACIÓN MANUAL DE 2 LEADS + MOTOR 3 REAL.

---

## ✅ Estado del Pipeline

| Motor | Descripción | Estado |
|-------|-------------|--------|
| **Motor 1** | Descubrimiento Firmográfico de TAM (Exclusivo Apollo) | ✅ COMPLETADO — Refactorizado para firmografía pura |
| **Motor 2** | Triangulación de Señales (TheirStack, SECOP, Google, GitHub) + Waterfall Tamaño | ✅ COMPLETADO Y OPTIMIZADO — SECOP Full-Text ($q), RUES descartado |
| **Motor 3** | Pre-CRM + Enriquecimiento (Apollo → Hunter en cascada) | ✅ COMPLETADO — probado E2E (piloto LATAM) |
| **Motor 4** | Outbound RAG (Tavily + Groq redactor + Resend) | ✅ COMPLETADO — probado E2E (envío real a bandeja) |

**Suite de tests:** 460 tests en verde (verificado 22-Jul-2026 tras auditoría). `ruff` instalado y limpio.

---

## ✅ Auditoría Holística código↔documentación (22-Jul-2026)

Revisión cruzada exhaustiva entre `estado_actual.md` + `flujos_motor_1_y_2.md`
(y adaptadores relevantes en `tecnico/`) contra la implementación real de
`apollo_discovery_adapter.py`, `theirstack_adapter.py`, `secop_adapter.py`,
`PropuestaValorAdapter` y `sandbox_tbbc_real.py`. Se pidió explícitamente
"ningún cabo suelto ni suposiciones en el aire" antes del push a la rama
principal.

**Discrepancias encontradas y corregidas:**

1. **Bug real (código, no solo documentación):** `SecopSocrataAdapter`
   implementaba `PuertoEstimadorTamano` (campo `es_pyme`) desde la sesión
   anterior, documentado como "tercer origen del waterfall de tamaño", pero
   `evaluar_consenso_tamano()` en `sandbox_tbbc_real.py` nunca lo invocaba —
   solo usaba TheirStack + PropuestaValorAdapter. **Corregido:** se agregó
   el parámetro `adapter_secop` a la función y se instanció en `main()`.
2. **`.env.example` incompleto:** `GITHUB_TOKEN` (usado en `github_adapter.py`)
   y `SECOP_APP_TOKEN` (usado en `secop_adapter.py`) se leían del entorno en
   código real pero no estaban documentados en la plantilla pública.
   **Corregido:** ambos agregados con comentarios explicativos.
3. **`ScoringPolicy` fantasma:** `flujos_motor_1_y_2.md` describía una clase
   `ScoringPolicy` con pesos ponderados (30% dolor, 25% tecnología, etc.)
   como si fuera parte del flujo real del Motor 1. Nunca se materializó en
   código — los únicos gates reales son validadores Pydantic de
   `ManifiestoICP`. **Corregido:** diagrama Mermaid y tabla de pesos
   actualizados, marcados explícitamente como diseño histórico no
   implementado.
4. **Tabla de adaptadores del Motor 2 incompleta:** no incluía `GitHubAdapter`,
   que sí existe en código, está en `OrigenTrigger.GITHUB` y en
   `AdapterRoutingPolicy.CATEGORIAS_CON_GITHUB`. **Corregido:** fila y
   sección de documentación agregadas.
5. **Wappalyzer mal documentado:** la tabla decía `wappalyzer-next (Python +
   Playwright)`. El código real (`wappalyzer_adapter.py`) usa únicamente
   `requests` + `BeautifulSoup`, sin Playwright — Playwright es el fallback
   técnico de `PropuestaValorAdapter` (Capa 2 del Negative ICP), no de
   Wappalyzer. **Corregido.**
6. **Umbrales de SECOP inventados:** la documentación decía "ALTA: Contrato
   > COP 500M en últimos 45 días" — el código real (`_nivel_por_fecha()`)
   NO filtra por valor monetario, solo por antigüedad (≤180d = ALTA, 180-365d
   = MEDIA, >365d = BAJA). **Corregido** con los umbrales reales del código.
7. **Diagramas Mermaid desactualizados:** el flujo del Motor 2 decía "Empresa
   descubierta por TheirStack" (obsoleto desde que Apollo es el único
   discoverer); el mapa de dependencias de puertos seguía en v3.0 sin
   `ApolloDiscoveryAdapter`, `GitHubAdapter`, `PropuestaValorAdapter`, ni los
   puertos `PuertoDescubridorEmpresas`/`PuertoEstimadorTamano`/
   `PuertoClasificadorPropuestaValor`. **Corregido**, ambos diagramas
   actualizados a v6.0.
8. **Secciones existentes en código sin documentación formal:** el Paquete
   de Revisión Persistente (`PaqueteRevisionAdapter`) y los Reintentos
   Técnicos de Capa 2 (rutas alternas + fallback Playwright) solo se
   mencionaban de paso en este archivo. **Corregido:** se agregaron
   secciones dedicadas en `flujos_motor_1_y_2.md` con el comportamiento real
   del código.

**Verificación post-corrección:** batería completa de pytest ejecutada tras
el fix de código (conexión de SECOP al waterfall) — 460 tests verdes,
0 regresiones. `ruff` limpio en los archivos tocados.

**Nota sobre control de versiones:** este repositorio no tiene una rama
`main`. La rama principal real es `setup/base-conocimiento` (`origin/HEAD`
apunta a ella). El cierre de esta auditoría se hizo con push a esa rama.

---

## ✅ Qué se hizo en esta sesión (21-Jul-2026)

### Refactorización de Arquitectura de Descubrimiento (Motores 1 y 2)

**1. Separación Real de Discovery vs Señales:**
- **Problema:** TheirStack traía empresas por vacantes y Apollo por tamaño al mismo tiempo, ensuciando el TAM inicial.
- **Solución:** Motor 1 (Descubrimiento) ahora usa **exclusivamente Apollo** para armar el TAM basado 100% en firmografía. TheirStack pasó a ser exclusivamente una fuente de evaluación de señales del Motor 2.

**2. Optimización SECOP (Socrata) y Rechazo RUES:**
- **Problema:** SECOP fallaba por timeouts (10s+) al usar `LIKE '%nombre%'`. RUES era un candidato para extraer NIT.
- **Solución SECOP:** Migrado a búsqueda Full-Text (`$q`) bajando el tiempo a ~1s. Se inyectó extracción profunda: `urlproceso.url` (link directo), `es_pyme` (para waterfall de tamaño), y UNSPSC (filtro de TI).
- **Decisión RUES:** Rechazado como fuente automatizada debido a falta de APIs estables (payloads cifrados, scraping frágil). Se usará solo como link de consulta humana.

**3. Paquete de Revisión Persistente ("Human in the Loop"):**
- Se implementó `PaqueteRevisionAdapter` persistiendo datos en `pendientes.json`. En lugar de que el orquestador olvide las empresas dudosas, guarda la evidencia (HTML del homepage) y provee links de 1-clic para que el humano evalúe en segundos y persista su veredicto (`CONFIRMADO_PERMITIDO/EXCLUIDO`). Se agregaron reintentos técnicos con `/nosotros` y fallback a Playwright.

**Archivos modificados:**
- `src/adapters/discovery/apollo_discovery_adapter.py`, `src/adapters/triggers/secop_adapter.py`, `sandbox_tbbc_real.py`.
- **Tests: 460 tests en verde, 0 regresiones.**

### Motor 2 — Blindaje post-piloto TBBC (3 fallos corregidos)

**Contexto:** la corrida con batch=15 calificó a "Parcero" (parcero.digital) como lead válido. Auditoría manual del fundador reveló que es una agencia digital con HQ en Londres, UK — competidor directo y fuera de la geografía del ICP. Diagnóstico: 3 fallos simultáneos.

**Falla 1 — Fail-Open en PropuestaValorAdapter (Negative ICP):**
- Causa: si el scraping de homepage fallaba (SPA sin SSR), el adaptador retornaba `None` y el orquestador lo interpretaba como "sin evidencia de competencia" → `PERMITIDO` automático.
- Fix: fallback de scraper a `<title>` + `<meta name="description">` cuando body visible < 100 chars. Tri-estado explícito (`es_vendor_it`: True/False/None). `None` → `PENDIENTE_REVISIÓN_MANUAL` (fail-closed). Nuevo campo `pais_hq` en el prompt del LLM + método `pais_hq()` público en el adaptador.

**Falla 2 — Bug del default silencioso de país en TheirStackAdapter:**
- Causa: `pais = empresa_data.get("country_code", "CO") or "CO"` mentía activamente cuando TheirStack no reportaba el país.
- Fix: eliminado el default. Se usa `PAIS_DESCONOCIDO = "XX"` (constante del Core, ISO 3166-1 reservado). Nueva política pura `PoliticaValidacionGeografica` en `policies.py`.

**Falla 3 — Falsos positivos en Google Alerts por nombres genéricos:**
- Causa: "Parcero" es una palabra coloquial del español colombiano → noticias de fútbol pasaban el filtro de substring match.
- Fix: filtro de co-ocurrencia semántica (glosario de vocabulario de negocio) en `google_alerts_adapter.py`. Techo de confianza `BAJA` para nombres de empresa ≤8 caracteres.

**Corrida de validación post-blindaje (batch=15):**
- 3 excluidas por competencia: Periferia IT Group, Parcero, Hitss Colombia.
- 2 pendientes revisión manual: Itaú, Keralty (SPAs opacas, fail-closed correcto).
- 4 descartadas por tamaño ENTERPRISE: Altipal, Seguros Bolívar, Berlitz, PwC.
- **2 califican para Motor 3: Cielito (cielito.co), Colsubsidio.**
- Tasa de calificación bruta: 15.4%.

**Archivos modificados:**
- `src/core/domain/models.py` — `PAIS_DESCONOCIDO`, `EstimacionTamano`, `EstadoConsensoTamano`, `ResultadoExclusionCompetidor` (+`PENDIENTE_REVISION_MANUAL`), `EstadoValidacionGeografica`, `OrigenTrigger.PROPUESTA_VALOR`
- `src/core/domain/policies.py` — `PoliticaCorroboracionTamano`, `PoliticaExclusionCompetidores`, `PoliticaValidacionGeografica` (nueva)
- `src/core/ports/interfaces.py` — `PuertoEstimadorTamano`, `PuertoClasificadorPropuestaValor` (nuevos)
- `src/adapters/triggers/propuesta_valor_adapter.py` — implementación completa con `pais_hq`, fallback meta tags, caché por instancia
- `src/adapters/triggers/theirstack_adapter.py` — bugfix país + `PuertoEstimadorTamano`
- `src/adapters/triggers/google_alerts_adapter.py` — co-ocurrencia semántica + techo de confianza
- `sandbox_tbbc_real.py` — orquestador con fail-closed completo y 5 banners de estado
- Tests: +28 nuevos en `test_domain_models.py`, `test_propuesta_valor_adapter.py`, `test_triggers_adapters.py`
- **275 tests verdes, 0 regresiones, ruff limpio.**

---
## 🔄 En Evolución (18/19-Jul-2026): Pivote hacia "Signal-Based Selling"

**Qué teníamos:** El Motor 1 y 2 dependían fuertemente de una sola señal ("Vacantes publicadas") extraída mediante TheirStack para descubrir y calificar prospectos.
**Cómo buscamos:** Realizamos una investigación web profunda cruzando metodologías de ventas B2B, libros referentes (Predictable Revenue, SHiFT!, Spear Selling) y tácticas de Account-Based Sales Development (ABSD).
**Qué encontramos:** Depender exclusivamente de vacantes crea ceguera (single-signal dependency). Las vacantes son útiles, pero carecen del vector "Urgencia" si no se evalúa su *aging* (días abierta). Existen señales más fuertes (Tier 0 y Tier 1) como victorias de contratos en SECOP o cambios de liderazgo.
**A qué hemos llegado (Temporal):** Se está reestructurando la estrategia hacia una **Orquestación Multi-Señal**. 
- **Tier 0 (Sangrado Activo):** Contratos ganados sin equipo (SECOP) o vacantes antiguas (>45 días).
- **Tier 1 (Reorganización):** Nuevo CTO/Líder técnico (<90 días).
- **Tier 2/3 (Contexto):** M&A, adopción cloud, tamaño de empresa (TAM Base usando Apollo/InfobelPRO).

**Siguiente acción táctica:** Ingestar literatura especializada (SHiFT!, Predictable Revenue, Spear Selling, Fanatical Prospecting) usando un modelo de largo contexto (NotebookLM) para extraer las lógicas matemáticas de Scoring y plasmarlas en el Motor 2.

---

## 🔜 PRÓXIMO PASO / SIGUIENTE SESIÓN

1. **Validación manual de los 2 leads calificados (BLOQUEANTE antes de Motor 3):**
   - **Colsubsidio:** verificar qué división exactamente está buscando desarrolladores. ¿Construcción de plataforma interna o modernización de legacy? Si es válido → enriquecer con Motor 3.
   - **Cielito (cielito.co):** verificar que es empresa tech (startup o empresa armando equipo in-house), no la marca de alimentos "Cielito Lindo". Si es válido → enriquecer con Motor 3.
   
2. **Decisión pendiente del fundador:** ¿Ajustar el ICP a solo SME (50-200) descartando MID_MARKET también? Actualmente Colsubsidio pasa por ser MID_MARKET. Si el cliente quiere enfocarse solo en SME, hay que actualizar el filtro de `TamanoEmpresa` en el sandbox.

3. **Motor 3 real (bloqueado hasta validación manual de leads):** enriquecer contactos de los leads calificados con Apollo → Hunter.

4. **Orquestador FastAPI y Webhook de rebotes:** cerrar los bloqueos técnicos pendientes (ver tabla de entorno técnico).

## ⚠️ Bloqueos Pendientes (documentados, no resolubles por IA)

### Motor 3 — Pre-CRM + Enriquecimiento (COMPLETADO)
- **Spec** `tecnico/prospector-m3-m4-design.md` — `PuertoEnriquecedorContactos` (firma stateless `enriquecer(empresa, cargos)`), cascada Apollo→Hunter, `PoliticaMapeoEstadoCorreo` (ubicada en capa de adaptador para no filtrar semántica de proveedor al Core), `UmbralCalidadDecisor` (`confianza_dato >= 0.7` + `estado_correo in {VERIFICADO, INFERIDO}`).
- **Incidente real y fix:** Apollo depreció el endpoint directo `/v1/mixed_people/search` (error 422). `ApolloClient` se reescribió al flujo de 2 pasos: `api_search` (descubre IDs) → `/people/match` (extrae email). Confirmado en código y en tests verdes.
- **Piloto LATAM ejecutado con datos reales** (`sandbox_piloto_latam_m3.py`, n=5: Bancolombia, Rappi, Platzi, Addi, Merqueo): 80% tasa de resolución Apollo, 9 decisores, 8 aptos para M4, **costo estimado $0.17 USD/decisor apto** (umbral: <$1.00 ✅). Corte de costo validado en vivo (Merqueo: 0 perfiles → Hunter no se invocó).
- **Hallazgo crítico del piloto:** Rappi devolvió 5 decisores, 4 con cargo "VP of Engineering" — riesgo real de spray-and-pray. Este hallazgo definió el primer requisito de diseño del Motor 4.
- **Advertencia vigente:** el piloto fue n=5 sobre empresas grandes/conocidas (sesgo de muestra hacia el mejor caso de cobertura de Apollo). El KPI dual de aprobación real (§3.5 de la spec) exige además bounce rate real <2%, que **no se cerró en este piloto** — solo se mide enviando correos reales y contando rebotes (ver Motor 4).

### Motor 4 — Outbound RAG (COMPLETADO)
- **Spec** `tecnico/prospector-m4-design.md` — `PoliticaSeleccionMejorDecisor` (1 decisor por empresa, resuelve el caso Rappi), puertos `PuertoContextoRAG`/`PuertoRedactorOutbound`/`PuertoEnvioCorreo`, `PoliticaRegistroRebote` (lazo de retroalimentación que cierra el KPI pendiente de M3), fronteras Legal (Habeas Data) y de Reputación (Modo Borrador HITL). Decisiones cerradas por el Architect: dedup estricta 1/empresa, proveedor Resend, pacing 20 envíos/día, arranque solo con cohorte `VERIFICADO`.
- **Core materializado:** `PaqueteOutbound`, `Mensaje`, `ContextoRAG`, `EstadoMensaje`, `ResultadoEnvio` en `models.py`; 3 puertos en `interfaces.py`; 4 políticas puras en `policies.py` (`PoliticaRedaccionOutbound` queda como abstracción, sin materializar).
- **Adaptadores** en `src/adapters/outbound/`: `TavilyContextoAdapter`, `GroqRedactorAdapter` (modelo actualizado a `llama-3.3-70b-versatile` tras baja del modelo anterior), `ResendEnvioAdapter` + función pura desacoplada `procesar_webhook_rebote()` (el controlador HTTP que la invoque queda pendiente — ver Próximo Paso).
- **Piloto E2E a producción real** (`sandbox_motor_4_outbound.py`): con los decisores de Rappi (4 VPs + 1 CTO) y Platzi, `PoliticaSeleccionMejorDecisor` descartó los 4 VPs y seleccionó a Leandro Reox; Tavily recuperó contexto; Groq redactó el mensaje con gancho de trigger y opción de baja (Habeas Data); tras Modo Borrador y aprobación explícita (`APROBAR_Y_ENVIAR`), Resend entregó con éxito a una bandeja de Gmail real de control.
- **Nota de honestidad sobre el alcance de esta prueba:** confirma que la cadena Tavily→Groq→Resend funciona end-to-end y que el correo llega. **No confirma bounce rate** (un envío exitoso a un correo de control no es una muestra de rebotes) ni el cumplimiento legal real de Habeas Data (pendiente de abogado, ver bloqueo abajo). No usar este resultado como "M4 validado para escala".

### Suite de tests
- 107 → **208 tests en verde** (verificado con corrida real 15-Jul-2026): +31 enriquecimiento (M3), +30 Core M4, +27 adaptadores outbound (M4).

---

## ✅ Qué se hizo en sesión anterior (15-Jul-2026)

### Motor 3 — Pre-CRM + Enriquecimiento (sesión anterior)

1. **Blindar El Prospector (Frente 1 - TBBC):** ~~Es la prioridad absoluta.~~ **COMPLETADO (17-Jul-2026).** Ver sección anterior.
2. **Investigación Paralela (Frente 2):** Iniciar la investigación de arquitectura para automatización de WhatsApp y chats de atención (segunda empresa).
3. **Orquestador Principal y Webhook:** Cerrar los bloqueos técnicos pendientes del Motor 3 y 4 (orquestación y webhook de rebotes de Resend).

> **Estado al 17-Jul-2026:** el punto 1 está cerrado. Los puntos 2 y 3 quedan diferidos hasta validar los leads del sandbox real.

## ⚠️ Bloqueos Pendientes (documentados, no resolubles por IA)

**Habeas Data (Ley 1581) — YA NO ES TEÓRICO.** El código ahora procesa y ha enviado correos a PII real (nombres y direcciones de decisores reales del piloto de M3/M4). El compliance real requiere asesoría legal con abogado real antes de cualquier envío a escala. Ver `10-Memoria_Consolidada/validacion/validacion-fuentes.md` §7. **Este bloqueo se activa formalmente ahora que existe envío real, no solo diseño.**

**Bounce rate real del Motor 3 sin medir.** El piloto de M3 solo cerró el KPI de costo ($0.17 < $1.00 ✅). El KPI de calidad (<2% bounce) sigue abierto — depende del webhook de Resend (ver Próximo Paso #2).

**Muestra del piloto LATAM sesgada.** n=5 sobre empresas grandes/conocidas no es representativo del ICP real (SME 50-200 desconocidas). El caveat de caída de precisión 10-20 puntos fuera de US sigue sin validar con una muestra representativa.

---

## Estado del Entorno Técnico

| Componente | Estado |
|---|---|
| `.venv` Python 3.12 + dependencias pineadas | ✅ |
| 275 tests pytest | ✅ verdes (verificado 17-Jul-2026) |
| `ruff` linter/formatter | ✅ limpio en todos los archivos tocados el 17-Jul |
| Graphify `graph.json` (420 nodos, 12-Jul) | ✅ construido — no regenerado tras M3/M4/blindaje, considerar refrescar |
| 7 hooks Kiro (4 manuales + 3 automáticos) | ✅ cableados |
| `INTERES_LEGITIMO` eliminado del dominio | ✅ |
| Specs M1-M4 sincronizadas con código | ✅ actualizadas 17-Jul-2026 |
| Webhook de rebotes de Resend | ⬜ pendiente (función pura lista, falta el controlador HTTP) |
| Orquestador/API principal | ⬜ pendiente (solo sandboxes hoy) |

---

## 📅 Historial de Sesiones

| Fecha | Acción | Versión |
|---|---|---|
| 2026-07-09 | Validación sector tech LATAM. Arquitectura hexagonal inicial. | v1.0 |
| 2026-07-11 | 12 vulnerabilidades Pydantic cerradas. Motor 1 como Enrutador Dinámico. LUZ VERDE. | v3.0 |
| 2026-07-12 | Core Python materializado. GroqICPAdapter + Discovery dual-mode + EstadoEmpresa. | v3.1 |
| 2026-07-12 | 5 adaptadores Motor 2 completos. Pruebas E2E exitosas. | v3.2 |
| 2026-07-12 | Fix Habeas Data. Memoria consolidada. Graphify activo. 7 hooks. Entorno supercargado. | v3.3 |
| 2026-07-15 | **Motor 3 completado: spec, Core, adaptadores Apollo→Hunter (fix flujo 2 pasos), piloto LATAM ($0.17/decisor). Motor 4 completado: spec, Core, adaptadores Tavily/Groq/Resend, `PoliticaSeleccionMejorDecisor` (fix caso Rappi). Piloto E2E con envío real a bandeja de control exitoso. 208 tests verdes.** | v4.0 |
| 2026-07-17 | **Blindaje Motor 2 (3 fallos del caso Parcero/UK corregidos). Sandbox TBBC batch=15: 2 leads calificados (Cielito, Colsubsidio). 275 tests verdes (+28 nuevos, 0 regresiones).** | v4.1 |
| 2026-07-21 | **Refactor Discovery (M1 = Apollo puro). Optimización SECOP ($q full-text, `es_pyme`, URL). RUES rechazado. Paquete de revisión persistente `pendientes.json` + Fallback Playwright. 460 tests verdes.** | v4.2 |
| 2026-07-22 | **Auditoría Holística código↔documentación. Fix real: `SecopSocrataAdapter.estimar_tamano()` estaba implementado pero desconectado del waterfall de tamaño — conectado en `sandbox_tbbc_real.py` (ahora 3 orígenes: TheirStack, PropuestaValorAdapter, SECOP). `.env.example` actualizado con `GITHUB_TOKEN`/`SECOP_APP_TOKEN` (existían en código, faltaban en la plantilla). `flujos_motor_1_y_2.md` corregido: `ScoringPolicy` marcado como diseño histórico nunca implementado, tabla de adaptadores completada con `GitHubAdapter`, Wappalyzer corregido (no usa Playwright — eso es `PropuestaValorAdapter`), umbrales SECOP corregidos a solo antigüedad (sin montos COP inventados), diagramas Mermaid actualizados (Apollo como discoverer, 3er origen SECOP en waterfall, mapa de puertos v6.0 con Apollo/GitHub/PropuestaValorAdapter). 460 tests verdes tras la corrección, 0 regresiones.** | v4.3 |
