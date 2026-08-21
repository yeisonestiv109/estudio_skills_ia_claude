# Manifiesto de Arquitectura — Estado del Negocio (State of the Union)

> **Propósito de este documento:** fotografía completa y portable de este
> ecosistema — estructura técnica y narrativa de negocio — para que cualquier
> persona o **cualquier asistente de IA** que lo lea por primera vez entienda
> qué estamos construyendo, por qué está organizado así, y cómo pensar dentro
> de este contexto sin inventar nada que no esté aquí.
>
> **Fecha de esta fotografía:** 21-ago-2026. Este documento es un snapshot, no
> una fuente de verdad viva — si algo aquí contradice `02_backlog_y_rocas.md`
> (el handoff activo) o el código real, **ganan esos**, no este manifiesto.
> Actualízalo cuando la fotografía envejezca demasiado; no lo trates como
> backlog.

---

## Parte I — Los Tres Pilares (estructura técnica)

El ecosistema vive bajo un único directorio padre,
`/home/estiv12/proyecto_negocio_doscaras/` ("las dos caras de la moneda" —
Inbound/Outbound), como **tres repositorios git hermanos e independientes**,
cada uno con su propio `graphify` (grafo de código) y su propia memoria de
Claude Code compartida vía `autoMemoryDirectory` (los cuatro puntos de entrada
— los 3 repos + el padre — leen y escriben la misma memoria).

### 1. La Línea Inbound — `artf-pipeline-app/`

**Qué es:** el código real, en producción, de **Inbound_AI_SDR** — un agente
comercial autónomo que atiende leads entrantes (IG DMs/WhatsApp) en menos de
60 segundos. Es el **frente activo** del negocio hoy. Cliente piloto: **ARTF**
(Andrés Resuelve Tus Finanzas). Stack: Next.js + Supabase/PostgreSQL.

```text
artf-pipeline-app/
├── CLAUDE.md / AGENTS.md / README.md
├── src/
│   ├── app/                    ← rutas Next.js: agenda/, agendar/, incidencias/,
│   │                              login/, metricas/, page.tsx
│   ├── components/             ← AgendaBoard, AppShell, MetricasBoard,
│   │                              NuevoLeadModal, PipelineBoard, LogoutButton
│   ├── lib/
│   │   ├── data/
│   │   ├── google/             ← integración Google Calendar
│   │   └── supabase/           ← cliente y queries a la base de datos
│   └── proxy.ts
├── supabase/migrations/        ← historial versionado de SQL (RLS, funciones
│                                  trigger, vistas) — la verdad del esquema real
├── e2e/                        ← Playwright (auth-and-panels.spec.ts) —
│                                  disciplina de verificación real, no solo tipos
├── scripts/                    ← diag-timeout, provision-user, verify-agenda,
│                                  verify-rls
├── graphify-out/                ← grafo de código (se regenera solo, hook Husky
│                                   post-commit/post-checkout)
└── .github/workflows/ci.yml
```

### 2. La Línea Outbound / Prospector — `outbound-prospector-app/`

**Qué es:** el código real de **Outbound_Prospector** ("El Prospector") — un
motor de prospección B2B en frío que descubre empresas por señales de mercado
(vacantes, funding, tecnografía) y orquesta campañas de correo personalizadas.
Arquitectura hexagonal estricta (Puertos y Adaptadores). Cliente piloto: TBBC
(Catalina Rúa). **Estado real: en pausa desde el 20-ago-2026, sin fecha de
retorno** — el código es real y maduro (476/480 tests verdes al momento de la
pausa), pero el foco del negocio se movió 100% a Inbound. Extraído el
20-ago-2026 desde donde vivía anidado dentro de `estudio_skills_ia_claude/`,
preservando su historia real de git (`git filter-repo`, no una copia).

```text
outbound-prospector-app/
├── CLAUDE.md
├── src/
│   ├── core/
│   │   ├── domain/              ← models.py, policies.py (ScoreTriggerPolicy,
│   │   │                           reglas puras de negocio)
│   │   └── ports/                ← interfaces.py (ABCs — el contrato hexagonal)
│   └── adapters/
│       ├── discovery/ enrichment/ llm/ outbound/ revision_manual/ triggers/
├── tests/                        ← 14 archivos, 476/480 verdes a la fecha de pausa
├── docs/
│   ├── modelos_dominio_core.md, flujos_motor_1_y_2.md,
│   │   resumen_ejecutivo_arquitectura.md, metodologia_ventas_5_modulos.md,
│   │   analisis_cruzado_mercado.md, resiliencia_motor_2.md,
│   │   contexto_clientes_y_oportunidades.md
│   ├── tecnico/                  ← diseño M1-M4, stack, costo por lead, hacks
│   ├── validacion/validacion-fuentes.md  ← incl. §7 Habeas Data (bloqueo legal
│   │                                        real, no resoluble por IA)
│   ├── notebooklm/README.md      ← convención de fuentes para su notebook
│   │                                (PROPUESTO, no creado — ver Parte II)
│   └── guia_configuracion_memoria_ia.md  ← plantilla genérica histórica,
│                                            NO la estructura vigente de este repo
├── sandbox_*.py                  ← pilotos E2E manuales (motor1, motor2,
│                                    motor4, LATAM M3, TBBC real)
└── revision_manual/pendientes.json
```

### 3. El Core / `estudio_skills_ia_claude/` — el Segundo Cerebro

**Qué es:** la **base de conocimiento y gobernanza** de todo el negocio — no
tiene código de producto (eso vive en los dos repos hermanos de arriba). Es la
"fuente de la verdad" que consolida mentalidad, estrategia, memoria, historia
de decisiones y contexto de clientes, para que fundadores **y cualquier agente
de IA** operen con el mismo contexto sin reinventarlo cada sesión.

```text
estudio_skills_ia_claude/
├── AGENTS.md / CLAUDE.md / README.md   ← ritual de arranque de sesión, mapa
│                                          de navegación
├── 01_Gobernanza_EOS/                  ← EL CENTRO DE MANDO
│   ├── 00_vision_y_principios.md       (mentalidad, 3 Reglas de Oro, perfiles
│   │                                     de los fundadores)
│   ├── 01_entorno_y_operacion.md       (entorno técnico, protocolo NotebookLM,
│   │                                     historia de reestructuración,
│   │                                     visión Kiro+Antigravity)
│   ├── 02_backlog_y_rocas.md           (★ LEER PRIMERO EN CADA SESIÓN — handoff
│   │                                     vivo, Rocas EOS, bitácora de decisiones
│   │                                     append-only)
│   ├── 03_protocolos_comunicacion.md   (cómo se le habla a la IA: XML,
│   │                                     antipsicofancia, context engineering)
│   ├── 04_eos_vto_agencia.md           (V/TO: BHAG a 10 años, panorama a 3,
│   │                                     plan a 1, Scorecard, Rocas trimestrales)
│   ├── 05_estado_del_negocio_manifiesto.md  ← ESTE DOCUMENTO
│   └── Reuniones_Audios_Negocio/       (transcripciones cruzando ambas líneas;
│                                          notebook PROPUESTO)
├── 02_Lineas_de_Producto/              ← solo DOCS de arquitectura, no código
│   └── Inbound_AI_SDR/docs/            (contratos/flujos de Inbound; el código
│                                          real vive en artf-pipeline-app/)
│       (Outbound_Prospector/ eliminado 21-ago-2026 — solo quedaba caché de
│        antes de su extracción; sus docs viven 100% en outbound-prospector-app/)
├── 03_Clientes_y_Casos/                ← LABORATORIOS B2B REALES
│   ├── 01_Cliente_TBBC/                (Catalina Rúa + Javier — origen de la
│   │                                     relación, el trueque, ICP de TBBC)
│   └── 02_Cliente_ARTF/                (Andrés — arquitectura, migración de
│       ├── Tarea_1_Migrar_DB/            CRM a Supabase, EOS del cliente,
│       ├── Reuniones_Audios/             Scripts Worker/AppScript, PDFs de
│       └── Scrips_Worker_and_AppScript/  arquitectura)
├── 04_Segundo_Cerebro/                 ← operativa transversal + meta-memoria
│   ├── directrices_globales.md         (filosofía "Lo Aburrido es Oro", mapa
│   │                                     completo de notebooks NotebookLM)
│   ├── guia_arquitectura_memoria.md    (auditoría de memoria 21-ago-2026 +
│   │                                     índice del meta-manual reproducible)
│   ├── Negocio_General/                (agenda, correo, admin — táctico)
│   └── Desarrollo_Personal/            (crecimiento personal de Yeisiton)
├── .kiro/                              ← IDE Kiro: specs/, steering/ (carga
│                                          automática), skills/, hooks/, history/
│                                          (architecture_ledger.md — decisiones
│                                          técnicas append-only)
├── .agents/                            ← Antigravity CLI (integración futura,
│                                          ver 01_entorno_y_operacion.md)
└── graphify-out/                       ← grafo de código de este repo
```

---

## Parte II — La Historia

### Cómo empezó todo

Yeison Estiven Delgado Ordoñez ("Yeisiton") y Yulieth Gabriela Jaramillo
("Gabyota") son los cofundadores de una agencia de IA emergente todavía sin
nombre de marca definido (issue abierto en el V/TO). Yeisiton es el
desarrollador principal — backend, sistemas agénticos, arquitectura — y
Gabyota lidera la estrategia operativa y el encaje producto-mercado. Su
posicionamiento: **"Arquitectos Digitales con foso técnico real"** — venden
resultados medibles (ganar dinero, ahorrar tiempo, ahorrar dinero — las **3
Reglas de Oro** que gobiernan toda decisión de negocio en este repo), no
horas ni scripts sueltos.

Yeisiton conoció a **Catalina Rúa** y **Luis Javier Suarez Meza** en un evento
de emprendimiento en Popayán. La primera propuesta — mejorar la web de su
empresa, **TBBC** — se archivó. En una reunión posterior se les presentó **El
Prospector**, el motor de prospección B2B que hoy vive en
`outbound-prospector-app/`, y ahí nació el interés real: una **alianza
estratégica de trueque** — Yeisiton (+ Gabyota) construyen infraestructura
tecnológica de IA a cambio de que Catalina y Javier (quien colabora con
Sandler Colombia, la franquicia de entrenamiento en ventas número 1 del mundo)
les transfieran metodología comercial (**Método Sandler**) para escalar su
propia agencia de $0 a $10k USD/mes.

### El giro que explica los "dos frentes" — y por qué uno está pausado

TBBC (Frente 1) necesitaba **encontrar** leads fríos — encaja con Outbound
Prospector. Pero Catalina y Javier manejan una **segunda empresa** con el
problema inverso: abundancia de leads, cuello de botella en atenderlos. Esa
segunda empresa es **ARTF (Andrés Resuelve Tus Finanzas)** — Javier es su
Arquitecto de Ops e IA, Catalina su Estrategia Comercial y Closer, junto al
fundador/visionario Andrés. ARTF crece explosivamente desde mayo de 2026
(50-100 leads/día por Instagram DM) bajo un prototipo "de plastilina" (Meta
Ads → ManyChat → Google Sheets) que ya llegó a su límite de escala.

Ese cuello de botella encaja exactamente con la otra mitad de la moneda:
**Inbound AI SDR**. Cuando el Frente 1 (TBBC) se pausó, el trueque completo
se reaplicó al Frente 2 (ARTF) sin romperse — sigue siendo la misma relación
Yeisiton+Gabyota ↔ Catalina+Javier, solo que ejecutada sobre la empresa donde
el problema de negocio era resoluble *ahora*. Es la razón real detrás del
nombre del directorio padre, **"las dos caras de la moneda"**: no son dos
clientes desconectados, son **una sola relación de trueque aplicada a dos
problemas espejo** (encontrar leads vs. gestionar leads) dentro del universo
de las mismas dos personas.

Esto también explica por qué Outbound sigue vivo en el repo pese a estar
pausado: el código es real (476/480 tests), la relación con TBBC no se cerró,
solo se congeló — "queda en reserva para seguir trabajándolo y validándolo más
adelante" (palabras del propio acuerdo documentado). Por eso la directriz
vigente es clara: **cuando se reanude, el Paso 1 es su notebook de NotebookLM,
antes que una sola línea de código.**

### El rol profundo de `estudio_skills_ia_claude` — el Segundo Cerebro

No es documentación de acompañamiento — es el **sistema operativo del
negocio**. Tres cosas viven ahí que no viven en ningún otro lugar:

1. **El marco EOS/Traction completo** (V/TO, Scorecard, Rocas trimestrales,
   Pulso L10 semanal) — la misma metodología que ARTF opera con su propio
   cliente, aplicada primero a sí mismos ("no tendría sentido venderle a un
   cliente un sistema que nosotros mismos no aplicamos", `04_eos_vto_agencia.md`).
2. **La memoria y su gobernanza** — no solo los `.md` de contexto, sino el
   *protocolo* que los mantiene honestos: jerarquía de verdad explícita
   (código > backlog > docs de línea > bitácora > visión > memoria de Claude),
   disciplina de verificación antes de escribir, y — desde el 21-ago-2026 —
   una auditoría formal de ese mismo sistema de memoria
   (`04_Segundo_Cerebro/guia_arquitectura_memoria.md`), que encontró y corrigió
   7 puntos de drift real (rutas muertas, un MCP configurado y nunca usado, un
   notebook duplicado, un bug de terceros diagnosticado hasta la causa raíz).
3. **El registro histórico append-only** — `architecture_ledger.md` (decisiones
   técnicas, 7 entradas desde 7-jul-2026) y la "BITÁCORA DE DECISIONES
   HISTÓRICAS" dentro de `02_backlog_y_rocas.md`. Nada se reescribe; todo se
   añade con fecha. Es la diferencia entre "documentación" (que se queda
   desactualizada) y una **bitácora viva que sabe cuándo miente**.

En otras palabras: los dos repos de código son *qué* se construye. Este repo
es *por qué* se construye así, *quién* decide, y *cómo* una IA nueva se pone
al día sin que un humano tenga que repetir el contexto cada vez.

### Cómo se conectan las tres piezas — el modelo de negocio

```
   Catalina + Javier (TBBC, "segunda empresa" = ARTF)
              │  trueque: tecnología ⇄ metodología Sandler
              ▼
   Yeisiton + Gabyota (agencia de IA emergente, sin nombre aún)
              │
              │  construyen ────────────────────────────────┐
              ▼                                              ▼
   Inbound_AI_SDR (artf-pipeline-app/)          Outbound_Prospector (outbound-prospector-app/)
   🟢 frente activo · cliente ARTF               🔵 en pausa · cliente TBBC
   "gestionar abundancia de leads"                "encontrar leads escasos"
              │                                              │
              └──────────────────┬───────────────────────────┘
                                  ▼
                estudio_skills_ia_claude/ (Segundo Cerebro)
        gobierna ambas líneas bajo el mismo EOS, la misma
        jerarquía de verdad, la misma memoria compartida —
        y es la fuente que cualquier IA (Claude, Kiro,
        Antigravity) debe leer antes de actuar.
```

La propuesta de valor que se vende hacia afuera —**AI SDR & Speed-to-Lead con
Revenue Data Core**— es un sistema de orquestación de ingresos para negocios
B2B y de mentoría High-Ticket en LATAM. ARTF es el **laboratorio real** donde
esa propuesta se está validando con facturación en juego, no en teoría; TBBC
es el frente hermano que valida la mitad complementaria (adquisición fría) en
cuanto haya ancho de banda para retomarlo.

### Adónde queremos llegar

Del V/TO (`04_eos_vto_agencia.md`, sección viva, en construcción):

- **BHAG a 10 años:** ser la firma de referencia en LATAM para sistemas de AI
  RevOps en negocios High-Ticket, con al menos 50 clientes activos y un
  producto SaaS propio con MRR sostenible.
- **A 3 años (dic-2028):** al menos 3 clientes activos en producción, MRR de
  mantenimiento cubriendo los gastos operativos, el producto Inbound AI SDR
  validado con ARTF y replicable sin partir de cero.
- **A 1 año (2026):** completar ARTF (migración BD + Formulario Closer + AI
  SDR estable), validar la propuesta con 1 cliente adicional más allá de ARTF,
  documentar un "Playbook de Implementación" reproducible, **definir el nombre
  y marca de la agencia** (todavía pendiente), y cerrar el V/TO completo.
- **Rocas del trimestre actual (Q3 2026):** decisión de BD de ARTF aprobada
  por Javier, migración de datos a Supabase completa, Formulario Closer v1 en
  producción, Scorecard propio de la agencia funcionando.

**Lo que sigue abierto, honestamente (issues reales del V/TO, no maquillados):**
sin nombre de marca todavía; el propio EOS de la agencia sigue en
construcción; la propuesta de Inbound AI SDR aún no está validada con factura
fuera de ARTF; Outbound Prospector sigue pausado sin fecha de retorno. Nada de
esto se resuelve inventando una respuesta — se resuelve ejecutando, con la
misma disciplina de "no inventes datos" que rige el resto de este workspace.

---

*Documento vivo pero de bajo cambio — actualízalo cuando la fotografía envejezca
(cambio de fase EOS, cierre/reapertura de un frente, definición del nombre de
marca), no en cada sesión. Fuente primaria de cada afirmación: los documentos
citados inline arriba, todos dentro de este mismo repo.*
