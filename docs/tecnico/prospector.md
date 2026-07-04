# Prospector — Arquitectura Técnica y Manual de Operación

- **Versión de producción:** 3.14.0
- **Autoría:** Desarrollo propio del fundador (backend/IA) & Antigravity AI
- **Tipo:** Plataforma B2B de inteligencia comercial y prospección autónoma (**Vía B — producto propio**)

> Este documento es la referencia técnica del producto. Para la estrategia de negocio que lo rodea, ver `/estrategia`. Para advertencias legales de prospección, ver [`../fundamentos/03-estrategia-ventas-prospeccion.md`](../fundamentos/03-estrategia-ventas-prospeccion.md).

## 1. Introducción

**Prospector** es una plataforma de inteligencia comercial y prospección autónoma B2B, orientada al sector logístico y de ciencias de la vida. Usa un motor **RAG** (Generación Aumentada por Recuperación) cognitivo y multi-agente para:

- Descubrir prospectos corporativos.
- Rastrear hitos de crecimiento recientes en tiempo real (**triggers**).
- Identificar tomadores de decisión en LinkedIn.
- Enriquecer datos de contacto corporativos.
- Generar secuencias hiper-personalizadas de correo frío orientadas al dolor operacional.

## 2. Stack tecnológico

Filosofía **headless, serverless y de alta concurrencia**.

```
Frontend (Next.js 16 / React 19)
   - Dashboard ejecutivo con distribución de leads
   - Gestión en tiempo real del progreso de Jobs
   - Editor interactivo de copys / Aprobación manual
        │ (API HTTPS / JSON JWT)
        ▼
Backend FastAPI (Orquestador Core)
   - Uvicorn (puerto 8000), FastAPI Router
   - BackgroundTasks para subprocesos locales (.venv)
   - Endpoint interno de telemetría de Jobs
        ├──────────────► Pipeline de Prospección (Python 3)
        │                  - scripts/main.py        (orquestador)
        │                  - scripts/news_scraper.py (cognitive search planner)
        │                  - scripts/lead_scraper.py (Apify + Hunter.io)
        │                  - scripts/validator.py    (RAG & Llama-4-Scout audit)
        │
        └──────────────► Modal Container (serverless, 2GB RAM, autoescalable)
                              │
                              ▼
                 Data Cluster (Cloud Supabase - PostgreSQL)
                   - Tablas: leads, jobs_status, saved_queries,
                     user_profiles, crm_leads, crm_lead_notes
                   - Row Level Security (RLS) activo
```

### Componentes críticos

| Capa | Tecnología |
|------|------------|
| **Frontend** | Next.js 16.2.6 (React 19, Turbopack) + TailwindCSS v4 + Radix UI + Recharts |
| **Backend** | FastAPI 0.115 + Uvicorn (auth, persistencia de consultas, webhooks de telemetría) |
| **Serverless** | Modal (`modal_app.py`): autoescalado hasta 10 contenedores, timeout 900s, 2GB RAM |
| **Data** | Cloud Supabase (PostgreSQL 17.6) con RLS estricto |
| **Inferencia** | Rotador determinista de claves Groq por hash de empresa → Llama 4 Scout (`meta-llama/llama-4-scout-17b-16e-instruct`) |

> ✅ **Validación:** Next.js 16.2.6 + React 19.2 + Turbopack es un stack real y vigente (release estable may-2026). El resto del stack (FastAPI, Supabase/Postgres, Modal, Groq, Llama 4 Scout, Apify, Hunter.io, Tavily) son tecnologías existentes y coherentes entre sí.

## 3. Catálogo de base de datos (Supabase = estado único de la verdad)

### Enums

- `user_role` (RBAC): `admin`, `client`
- `job_state`: `queued`, `processing`, `completed`, `failed`

### Tabla `jobs_status` (RLS habilitado)

Registro de ejecución y progreso de procesos asíncronos.

| Columna | Tipo | Null | Descripción |
|---------|------|------|-------------|
| `job_id` | uuid | NOT NULL | PK, identificador de ejecución |
| `user_id` | uuid | NOT NULL | Propietario del job |
| `status` | job_state | NOT NULL | Estado actual |
| `progress_percentage` | integer | NOT NULL | 0–100 |
| `current_phase` | varchar | NOT NULL | Fase en tiempo real (vía webhook) |
| `error_message` | text | NULL | Detalle si `failed` |
| `created_at` | timestamptz | NOT NULL | Creación |
| `updated_at` | timestamptz | NOT NULL | Última actualización |

**RLS:** insert/select/update solo donde `auth.uid() = user_id`.

### Tabla `leads` (RLS habilitado)

Output final del enriquecimiento y auditoría RAG.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | bigint | PK secuencial |
| `created_at` | timestamptz | Fecha de prospección |
| `nombre_lead` | text | Nombre del prospecto (o "Contacto Pendiente") |
| `empresa` | text | Compañía prospectada |
| `cargo` | text | Cargo extraído de LinkedIn |
| `linkedin_url` | text | Perfil de LinkedIn |
| `email` | text | Correo directo (enriquecido por Hunter.io) |
| `telefono` | text | Teléfono corporativo |
| `url_noticia` | text | Noticia gatilladora (trigger) |
| `trigger_noticia` | text | Resumen conceptual de la noticia |
| `mensaje_generado` | text | Correo hiper-personalizado del LLM |
| `es_calificado` | boolean | Bandera de aprobación comercial |
| `razonamiento_filtro` | text | Justificación de 3 puntos (Fase 2) |
| `user_id` | uuid | Propietario |
| `job_id` | uuid | Job origen |

**RLS:** `client_isolation_policy` (`auth.uid() = user_id`) + `admin_read_all_policy` (rol admin lee todo para auditoría).

## 4. Pipeline de prospección (4 scripts en cascada)

Todos implementan **delays preventivos (pacing)** para eludir rate limits de Groq y Tavily. **Aislamiento por job:** `scripts/runtime_paths.py` hace que todos los artefactos vivan en `.tmp/job_{job_id}/`, evitando que corridas concurrentes/consecutivas compartan estado.

### A. `scripts/main.py` — Orquestador central

- **Fase 0 (Pre-flight Cognitive Intent Parser):** Llama 4 Scout extrae un manifiesto cognitivo (`optimized_search_tokens`, `target_industry_core`, `b2b_buying_trigger_context`, `rigorous_pain_framework`, `target_market_region`), guardado en `.tmp/job_{job_id}/active_runtime_context.json` bajo `extracted_intent`.
- **Company Discovery:** Tavily Search descubre 15–20 empresas reales del perfil objetivo.
- **Blacklist:** filtra contra `exclusion_list` del payload del usuario.
- **Multihilo:** ThreadPoolExecutor con 3 hilos; por empresa ejecuta news → lead → validator.
- **Idempotencia:** si la empresa ya tiene registros para ese `job_id` en Supabase, la salta (evita sobreconsumo de APIs en reanudaciones).
- **Telemetría:** invoca `/api/v1/internal/update-job/{job_id}` para actualizar fase y % (10→100).

### B. `scripts/news_scraper.py` — Cognitive Search & News

- **Fase 1 (Query Planner):** genera 3 consultas dirigidas: (1) expansión (sedes/contrataciones/proyectos), (2) regulatoria/dolor (ej. INVIMA BPM, suministro), (3) social/comercial (hitos/disrupciones).
- **Scraping:** Tavily Search + Tavily Extract para limpiar HTML a texto.
- **Filtrado semántico:** Llama 4 Scout asigna score de relevancia; exige trigger válido 2025/2026 alineado al mercado; descarta contenido genérico.
- **Salida:** `.tmp/job_{job_id}/news_{company}.json` (trigger nulo si no hay noticia válida).

### C. `scripts/lead_scraper.py` — Lead Discoverer & Enrichment

- **LinkedIn:** consultas dirigidas por cargo (ej. "VP Supply Chain LATAM") vía Apify `google-search-scraper` para URLs de perfiles públicos.
- **Cortafuegos determinista** (Python, antes de APIs de pago): `is_valid_human_role` (descarta no-humanos/páginas corporativas) + mismatch check (título/nombre vs empresa).
- **Resolución de dominio verificada:** Clearbit → Tavily, con verificación de que el dominio pertenece a la empresa; descarta data-brokers (ZoomInfo, LeadIQ, EMIS, RocketReach, Crunchbase). Enriquecimiento en cascada Apollo → Hunter.io (verificados) y, solo como último recurso, patrón `nombre.apellido@dominio` marcado como inferido. Sin dominio confiable → sin email (anti-rebote).
- **Fallback "Contacto Pendiente":** si hay trigger válido pero no se halló decisor, crea registro con cargo "Prospección Manual Pendiente" para asignación manual en el frontend.
- **Salida:** `.tmp/job_{job_id}/leads_{company}.json` con `email_source` (apollo/hunter/pattern_inferred) y bandera `email_verified`.

### D. `scripts/validator.py` — RAG Auditor & Copywriter

- **Fase 2 (Rigorous Pain Framework):** inserta el manifiesto de dolor en el prompt.
- **Cortocircuito:** leads pre-descalificados se guardan con `es_calificado = false` sin llamar al LLM.
- **Auditoría cruzada (3 pilares):** (1) hecho noticioso detonante 2025/2026; (2) impacto operativo deductivo (ej. INVIMA, cadena de frío); (3) encaje del rol del decisor.
- **Copy en frío:** correo hiper-personalizado en español, máx. 150 palabras, sin tono spam.
- **Persistencia:** inserción directa en `leads` (calificados, "Contacto Pendiente", descartes).

## 5. Conexión Backend ↔ Modal ↔ Supabase

- **Modal (`modal_app.py`):** empaqueta el backend en Debian Slim, instala `requirements.txt`, hereda secretos de entorno (`SUPABASE_URL`, `TAVILY_API_KEY`, `HUNTER_API_KEY`, etc.) como secretos de Modal; inyecta `GROQ_API_KEY_1..9` para rotación stateless; hasta 10 instancias.
- **Telemetría:** FastAPI corre BackgroundTasks → `main.py`; este actualiza vía `PATCH /api/v1/internal/update-job/{job_id}` para que Next.js muestre fase y % en vivo.
- **RLS:** el frontend consulta con `@supabase/supabase-js`; Postgres valida el JWT contra `user_id`, garantizando aislamiento multi-tenant del 100%.

## 6. Comandos de ejecución y pruebas locales

```bash
# Setup
python -m venv .venv
source .venv/Scripts/activate   # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
# Configurar .env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TAVILY_API_KEY, HUNTER_API_KEY, ...

# Backend local
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Probar pipeline directo
python scripts/main.py \
  --payload_path .tmp/dynamic_form_payload.json \
  --user_id <UUID_USUARIO> \
  --job_id <UUID_JOB>

# Desplegar a Modal
modal setup
modal deploy modal_app.py
```

El despliegue genera una URL pública SSL de Modal. El frontend Next.js debe apuntar `NEXT_PUBLIC_BACKEND_API_URL` a esa dirección de producción.

## 7. Changelog

- **3.14.0** — Aislamiento por `job_id` (`scripts/runtime_paths.py`, todo bajo `.tmp/job_{job_id}/`); dominios de email confiables anti-rebote (`_domain_matches_company`, blacklist de data-brokers); Modo Rápido con post-filtro geográfico por país y limpieza de nombre/cargo; geo-fit estricto en Modo Profundo.
- **3.13.0** — Dos modos: Rápido (Express, `POST /api/v1/prospect/fast`, Apollo→Tavily+Hunter, `scripts/fast_search.py` + `compute_fast_match`) y Profundo (pipeline de señales intacto); UX estilo Enginy (input en lenguaje natural + toggle de modo).
- **3.12.0** — Motor de scoring ICP FIT + INTENT (0–100), tier A/B/C/D, `scripts/scoring.py`, determinismo `temperature=0.1`, 3 consultas Tavily multi-ángulo, distinción email verificado vs inferido. Migración `db/migrations/002_lead_scoring_and_email_verification.sql`.
- **3.11.0** — Fix `.gitignore` (`/lib/`), guardado de consultas con versionado (`PUT/DELETE /api/v1/queries/{id}`), mini-CRM (`crm_leads`/`crm_lead_notes`, Kanban), hardening CORS. Migración `db/migrations/001_saved_queries_versioning_and_crm.sql`.

## 8. Notas del coach (lectura crítica de producto)

- **Diferenciación:** la generación de leads con IA es commoditizable (ver [Pilar 4](../fundamentos/04-ia-conceptos-y-modelos-negocio.md)). La defensa del Prospector es el **nicho** (logística + ciencias de la vida) y la **calidad del trigger + copy**, no el scraping en sí. Doblar la apuesta ahí.
- **Riesgo legal:** scraping de LinkedIn (Apify) y cold email deben cumplir Habeas Data (Ley 1581/2012) y ToS. Documentar base legal por campaña. Ver [Pilar 3](../fundamentos/03-estrategia-ventas-prospeccion.md).
- **Riesgo de dependencia:** muchas APIs de pago (Tavily, Apollo, Hunter, Groq, Apify). Vigilar el **costo por lead calificado** como métrica unitaria clave de rentabilidad.
- **Verificación pendiente:** confirmar que el "Modo Rápido" no degrade la calidad del geo-fit (es el cambio más reciente y el de mayor riesgo de falsos positivos).
