-- ===========================================================================
-- TELEMETRIA DE TRAZAS DEL BOT V4.2 (11-sep-2026)  [APLICADA]
--
-- QUE ES: una fila por PASO (span) de cada turno del bot, siguiendo las
-- convenciones semanticas de OpenTelemetry para GenAI. Un turno = un trace_id;
-- dentro viven los spans (webhook, estado, LLM, router, verificador, escritura).
--
-- POR QUE UNA TABLA NUEVA Y NO `llm_telemetria`: esa otra mide SALUD DE CUOTA
-- (limites, 429, llaves) y es agregada, una fila por llave. Esta mide el VIAJE
-- de un mensaje concreto. Son preguntas distintas: "¿me queda cupo?" vs "¿por
-- que este lead recibio ese mensaje?".
--
-- COSTO: el Worker inserta UNA sola vez por turno (todos los spans en lote,
-- dentro de ctx.waitUntil). No agrega latencia a la respuesta de ManyChat.
--
-- ⚠️ DATOS PERSONALES: `attributes` puede llevar fragmentos del mensaje del
-- lead. Por eso: RLS cerrada (solo service_role), texto truncado en el Worker
-- y purga automatica a los 30 dias (fn_purgar_telemetry_spans).
--
-- NO SE INSTALA pg_cron a proposito: agregar una extension a una base
-- compartida de produccion es un riesgo innecesario. El Worker llama a la
-- funcion de purga de forma oportunista (~1% de los turnos, en background).
-- ===========================================================================

create table if not exists public.telemetry_spans (
  id             bigint generated always as identity primary key,

  -- Arbol de la traza (OTel). Un turno completo comparte trace_id.
  trace_id       text        not null,
  span_id        text        not null,
  parent_span_id text,

  -- Donde ocurrio. Ej: MANYCHAT_WEBHOOK, GROQ_CLASIFICADOR, ROUTER_FSM...
  node_name      text        not null,

  -- OK = termino bien · ERROR = fallo · FALLBACK = degradado pero respondio
  -- PENDING = el span abrio y no cerro (el turno murio a mitad).
  status         text        not null default 'OK'
                 check (status in ('OK', 'ERROR', 'FALLBACK', 'PENDING')),

  started_at     timestamptz not null default now(),
  ended_at       timestamptz,
  duration_ms    integer,

  -- Contexto del negocio: permite agrupar por lead sin cruzar tablas.
  manychat_id     text,
  gestion_lead_id uuid,
  etapa_bot       text,

  -- llm.model, llm.usage.*, user.intent, error.message, etc.
  attributes     jsonb       not null default '{}'::jsonb,

  created_at     timestamptz not null default now()
);

comment on table public.telemetry_spans is
  'Trazas OpenTelemetry del bot V4.2: una fila por paso de cada turno. '
  'La escribe el Worker en lote via ctx.waitUntil (cero latencia). '
  'Contiene datos personales truncados: RLS cerrada y purga a 30 dias.';

-- Los dos accesos reales del dashboard: "lo ultimo que paso" y "esta traza".
create index if not exists idx_telemetry_spans_recientes on public.telemetry_spans (created_at desc);
create index if not exists idx_telemetry_spans_trace     on public.telemetry_spans (trace_id, started_at);
-- Para la purga y para mirar el historial de un lead puntual.
create index if not exists idx_telemetry_spans_lead      on public.telemetry_spans (gestion_lead_id)
  where gestion_lead_id is not null;

-- ---------------------------------------------------------------------------
-- SEGURIDAD: cerrada por defecto. Sin politicas = nadie pasa por PostgREST.
-- El Worker escribe con service_role (salta RLS) y el dashboard local lee con
-- service_role tambien. anon/authenticated NO tienen nada que hacer aqui.
-- ---------------------------------------------------------------------------
alter table public.telemetry_spans enable row level security;

revoke all on public.telemetry_spans from anon, authenticated;
grant select, insert on public.telemetry_spans to service_role;

-- ---------------------------------------------------------------------------
-- REALTIME: el dashboard se entera del INSERT por WebSocket, sin polling.
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'telemetry_spans'
  ) then
    alter publication supabase_realtime add table public.telemetry_spans;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- PURGA (Habeas Data).
-- ---------------------------------------------------------------------------
create or replace function public.fn_purgar_telemetry_spans(p_dias integer default 30)
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare n integer;
begin
  delete from public.telemetry_spans
   where created_at < now() - make_interval(days => greatest(p_dias, 1));
  get diagnostics n = row_count;
  return n;
end;
$$;

comment on function public.fn_purgar_telemetry_spans(integer) is
  'Borra trazas mas viejas que N dias (30 por defecto). La llama el Worker de '
  'forma oportunista. La telemetria lleva texto de leads: no se conserva indefinidamente.';

revoke all on function public.fn_purgar_telemetry_spans(integer) from anon, authenticated;
grant execute on function public.fn_purgar_telemetry_spans(integer) to service_role;
