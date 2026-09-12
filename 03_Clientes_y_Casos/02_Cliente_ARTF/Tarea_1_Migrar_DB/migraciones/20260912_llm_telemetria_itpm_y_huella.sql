-- ============================================================================
-- llm_telemetria: ITPM, huella de llave, organizacion y permisos (12-sep-2026)
-- ============================================================================
--
-- POR QUE. La tabla se diseño el 5-sep para vigilar OTPM (tokens de SALIDA por
-- minuto, 1000), que era el limite que rebotaba entonces. Desde el prompt en
-- XML el que rebota es ITPM: tokens de ENTRADA por minuto. Mensaje real de
-- Groq (12-sep): "on input tokens per minute (ITPM): Limit 7000, Used 4100,
-- Requested 5066". Cada clasificacion pide ~5.100: una organizacion aguanta
-- UNA por minuto. Un panel construido sobre OTPM se veria sano estando saturado.
--
-- Y dos llaves del pool resultaron ser de la MISMA organizacion (comparten
-- cupo, rotar entre ellas no suma nada). Solo se supo leyendo el texto del
-- error a mano. Ahora la organizacion se guarda sola.
--
-- QUE AGREGA (todo aditivo, nada se borra ni se renombra):
--   · itpm_consumido / itpm_limite_conocido: la ventana de un minuto de tokens
--     de entrada, contada por el Worker con `usage.prompt_tokens`.
--   · llave_huella: los ultimos 4 caracteres de la llave, para saber de que
--     cuenta viene cada alias. NUNCA la llave completa.
--   · organizacion: la que cita Groq en el 429. Dos alias con la misma
--     organizacion = un solo cupo.
--   · ultimo_limite_tipo / ultimo_limite_valor: que limite rebota (ITPM, OTPM,
--     RPM...) y su valor, LEIDO del error del proveedor. No se escribe a mano:
--     si Groq cambia el limite, la tabla se entera sola.
--   · tokens_entrada_total / tokens_salida_total / ultima_latencia_ms.
--
-- PERMISOS. La funcion es SECURITY DEFINER y tenia EXECUTE para PUBLIC (o sea
-- anon): con la llave publica cualquiera podia falsear la telemetria por RPC.
-- Solo la llama el Worker, con service_role. Se revoca el resto.
--
-- La firma cambia (parametros nuevos), asi que se DROPea la vieja antes de
-- crear la nueva: dejar las dos crearia una sobrecarga y PostgREST no sabria
-- cual llamar. Los llamadores usan parametros con nombre y los nuevos tienen
-- default, asi que el Worker viejo y smoke_rpc.mjs siguen funcionando.
-- ============================================================================

alter table public.llm_telemetria
  add column if not exists itpm_consumido       integer not null default 0,
  add column if not exists itpm_limite_conocido integer,
  add column if not exists llave_huella         text,
  add column if not exists organizacion         text,
  add column if not exists ultimo_limite_tipo   text,
  add column if not exists ultimo_limite_valor  integer,
  add column if not exists tokens_entrada_total bigint  not null default 0,
  add column if not exists tokens_salida_total  bigint  not null default 0,
  add column if not exists ultima_latencia_ms   integer;

comment on column public.llm_telemetria.llave_huella is
  'Ultimos 4 caracteres de la llave. Nunca se guarda la llave completa.';
comment on column public.llm_telemetria.organizacion is
  'Organizacion del proveedor, leida del mensaje de 429. Mismo valor en dos alias = cupo compartido.';
comment on column public.llm_telemetria.itpm_limite_conocido is
  'Limite de tokens de ENTRADA por minuto, leido del error del proveedor (no escrito a mano).';

drop function if exists public.fn_registrar_telemetria_llm(
  text, text, text, text, integer, integer, integer, text, integer, integer, text, text);

create function public.fn_registrar_telemetria_llm(
  p_proveedor          text,
  p_modelo             text,
  p_llave_alias        text    default 'principal',
  p_resultado          text    default 'ok',
  p_tokens_salida      integer default 0,
  p_limite_requests    integer default null,
  p_restantes_requests integer default null,
  p_reset_requests     text    default null,
  p_limite_tokens      integer default null,
  p_restantes_tokens   integer default null,
  p_reset_tokens       text    default null,
  p_detalle_error      text    default null,
  -- nuevos (12-sep-2026)
  p_tokens_entrada     integer default 0,
  p_llave_huella       text    default null,
  p_organizacion       text    default null,
  p_limite_tipo        text    default null,
  p_limite_valor       integer default null,
  p_latencia_ms        integer default null
)
returns void
language plpgsql
security definer
set search_path to ''
as $function$
declare
  v_alias     text := coalesce(p_llave_alias, 'principal');
  v_ventana   timestamptz;
  v_otpm      integer;
  v_itpm      integer;
  v_limite    text := upper(nullif(trim(p_limite_tipo), ''));
begin
  select ventana_inicio, otpm_consumido, itpm_consumido
    into v_ventana, v_otpm, v_itpm
    from public.llm_telemetria
   where proveedor = p_proveedor and modelo = p_modelo and llave_alias = v_alias;

  -- Ventana de un minuto: si vencio, se reinicia el conteo de las dos.
  if v_ventana is null or v_ventana < now() - interval '1 minute' then
    v_ventana := now();
    v_otpm := 0;
    v_itpm := 0;
  end if;

  insert into public.llm_telemetria as t (
    proveedor, modelo, llave_alias,
    limite_requests, restantes_requests, reset_requests,
    limite_tokens, restantes_tokens, reset_tokens,
    otpm_consumido, itpm_consumido, ventana_inicio,
    llamadas_ok, llamadas_429, llamadas_error,
    ultimo_429_at, ultimo_error, actualizado_at,
    llave_huella, organizacion, ultimo_limite_tipo, ultimo_limite_valor,
    itpm_limite_conocido, otpm_limite_conocido,
    tokens_entrada_total, tokens_salida_total, ultima_latencia_ms
  ) values (
    p_proveedor, p_modelo, v_alias,
    p_limite_requests, p_restantes_requests, p_reset_requests,
    p_limite_tokens, p_restantes_tokens, p_reset_tokens,
    v_otpm + coalesce(p_tokens_salida, 0), v_itpm + coalesce(p_tokens_entrada, 0), v_ventana,
    case when p_resultado = 'ok' then 1 else 0 end,
    case when p_resultado = '429' then 1 else 0 end,
    case when p_resultado = 'error' then 1 else 0 end,
    case when p_resultado = '429' then now() else null end,
    nullif(left(coalesce(p_detalle_error, ''), 400), ''),
    now(),
    nullif(left(coalesce(p_llave_huella, ''), 4), ''), p_organizacion, v_limite, p_limite_valor,
    case when v_limite = 'ITPM' then p_limite_valor end,
    coalesce(case when v_limite = 'OTPM' then p_limite_valor end, 1000),
    coalesce(p_tokens_entrada, 0), coalesce(p_tokens_salida, 0), p_latencia_ms
  )
  on conflict (proveedor, modelo, llave_alias) do update set
    limite_requests      = coalesce(excluded.limite_requests, t.limite_requests),
    restantes_requests   = coalesce(excluded.restantes_requests, t.restantes_requests),
    reset_requests       = coalesce(excluded.reset_requests, t.reset_requests),
    limite_tokens        = coalesce(excluded.limite_tokens, t.limite_tokens),
    restantes_tokens     = coalesce(excluded.restantes_tokens, t.restantes_tokens),
    reset_tokens         = coalesce(excluded.reset_tokens, t.reset_tokens),
    otpm_consumido       = excluded.otpm_consumido,
    itpm_consumido       = excluded.itpm_consumido,
    ventana_inicio       = excluded.ventana_inicio,
    llamadas_ok          = t.llamadas_ok    + excluded.llamadas_ok,
    llamadas_429         = t.llamadas_429   + excluded.llamadas_429,
    llamadas_error       = t.llamadas_error + excluded.llamadas_error,
    ultimo_429_at        = coalesce(excluded.ultimo_429_at, t.ultimo_429_at),
    ultimo_error         = coalesce(excluded.ultimo_error, t.ultimo_error),
    actualizado_at       = now(),
    -- La huella cambia si se rota la llave detras del alias: manda la ultima.
    llave_huella         = coalesce(excluded.llave_huella, t.llave_huella),
    organizacion         = coalesce(excluded.organizacion, t.organizacion),
    ultimo_limite_tipo   = coalesce(excluded.ultimo_limite_tipo, t.ultimo_limite_tipo),
    ultimo_limite_valor  = coalesce(excluded.ultimo_limite_valor, t.ultimo_limite_valor),
    itpm_limite_conocido = coalesce(case when v_limite = 'ITPM' then p_limite_valor end, t.itpm_limite_conocido),
    otpm_limite_conocido = coalesce(case when v_limite = 'OTPM' then p_limite_valor end, t.otpm_limite_conocido),
    tokens_entrada_total = t.tokens_entrada_total + excluded.tokens_entrada_total,
    tokens_salida_total  = t.tokens_salida_total  + excluded.tokens_salida_total,
    ultima_latencia_ms   = coalesce(excluded.ultima_latencia_ms, t.ultima_latencia_ms);
end;
$function$;

-- Minimo privilegio: solo el Worker (service_role) registra telemetria.
revoke all on function public.fn_registrar_telemetria_llm(
  text, text, text, text, integer, integer, integer, text, integer, integer, text, text,
  integer, text, text, text, integer, integer) from public, anon, authenticated;
grant execute on function public.fn_registrar_telemetria_llm(
  text, text, text, text, integer, integer, integer, text, integer, integer, text, text,
  integer, text, text, text, integer, integer) to service_role;
