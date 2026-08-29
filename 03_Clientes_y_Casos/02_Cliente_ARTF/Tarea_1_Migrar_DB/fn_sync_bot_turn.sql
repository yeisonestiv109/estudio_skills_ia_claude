-- ===========================================================================
-- 22. BRIDGE EN VIVO: Worker Cloudflare ("Andrew", antes "Javit") -> Supabase
-- ===========================================================================
-- APLICADO Y VALIDADO en staging (lrdtjsxtaadpgrzkchlw) el 15-ago-2026 con
-- datos de prueba (manychat_id TEST_BRIDGE_001..005, ver detalle de pruebas
-- en la bitacora 02_backlog_y_rocas.md). Version final tras 4 iteraciones:
--   1. Bug real: los nombres de columna de RETURNS TABLE (cliente_id,
--      gestion_lead_id) chocaban con columnas reales -> "column reference
--      ambiguous". Fix: prefijo out_ en las 4 columnas de salida.
--   2. Bug real: fn_avanzar_estado solo permite UN salto legal a la vez. Un
--      lead nuevo cuyo PRIMER turno ya es un handoff de crisis emocional
--      necesita 'nuevo'->'contactado'->'nutricion' (2 saltos), no uno solo.
--      Fix: si el salto directo falla, se intenta un salto intermedio via
--      'contactado' y se reintenta el destino real.
--   3. Bug real: el constraint ck_gl_handoff_closer exige closer_id no nulo
--      cuando fecha_handoff no es null. El bot nunca asigna closer, asi que
--      fecha_handoff se dejo de tocar en esta funcion por completo (ese
--      campo es "cuando se entrego a UN CLOSER", no "cuando el bot marco
--      para revision humana" -- mismo criterio que ya usaba migrate_crm.py).
--   4. Hallazgo de seguridad real (via mcp Supabase get_advisors): a pesar
--      del REVOKE incluido en una migracion anterior, `anon`/`authenticated`
--      seguian con EXECUTE sobre la funcion (verificado contra
--      information_schema.role_routine_grants, no contra el cache del
--      linter). Corregido con un REVOKE explicito final, reverificado.
--   5. Bug real (encontrado probando el Worker de captura real vía Postman,
--      NO en las pruebas sinteticas anteriores): el salto intermedio del
--      punto 2 se intentaba SIEMPRE que fn_avanzar_estado devolvia false --
--      pero false tambien significa "ya estaba en el destino" (caso normal
--      de una captura pasiva nueva: destino='nuevo', el lead recien creado
--      YA esta en 'nuevo'). Sin distinguir los dos casos, un lead nuevo se
--      empujaba a 'contactado' por error -- y como NADA transiciona de
--      vuelta a 'nuevo' en estado_transiciones, quedaba atascado sin forma
--      de corregirse solo. Fix: comparar el codigo actual contra el destino
--      ANTES de intentar cualquier salto; si ya coinciden, no se hace nada.
--   6. Bug CRITICO real (29-ago-2026, encontrado ANTES de abrir la puerta de
--      ManyChat para captura total de la conversacion -- no en produccion,
--      pero a un paso de estarlo): el `else 'nuevo'` del paso 4 corria para
--      CUALQUIER llamada sin p_etapa_bot -- exactamente el caso del worker
--      pasivo nuevo (setter-bridge-supabase), que nunca lo manda. Y
--      'agendado' -> 'nuevo' SI esta en estado_transiciones (existe a
--      proposito para "Devolver a Nuevo" del dashboard), asi que
--      fn_avanzar_estado(v_gestion_id, 'nuevo') tenia exito: CUALQUIER
--      mensaje ("gracias", lo que sea) de un lead YA agendado lo regresaba a
--      'nuevo' en silencio. Verificado el bug y el fix contra un lead
--      agendado real (manychat_id 611122479) con BEGIN/ROLLBACK antes de
--      aplicar. Fix: sin señal de etapa, el destino es "quedarse donde
--      esta" (v_estado_actual_cod), nunca 'nuevo' fijo -- se reordeno el
--      calculo de v_estado_actual_cod ANTES del CASE del paso 4 para poder
--      usarlo como fallback seguro.
--
-- Fundamentado contra datos reales (sesion 15-ago-2026, NO se asumio nada):
--   - Sheet real "Copia de CRM - Leads Campaña 1 Reconexión Financiera.xlsx"
--     (6.136 filas, el mismo que ya valido migrate_crm.py).
--   - Esquema EN VIVO del staging inspeccionado por MCP antes de escribir
--     esta funcion: triggers trg_gl_motor/fn_motor_etapas (valida
--     transiciones + gestiona cerrado_at solo), trg_gl_log/fn_log_gestion
--     (ya escribe activity_log automatico para creacion/cambio_estado/
--     asignacion), trg_touch/fn_touch_versioned (version/updated_at
--     automaticos), indice parcial unico uq_gestion_abierta_por_cliente
--     (cliente_id) WHERE cerrado_at IS NULL, constraint ck_gl_handoff_closer.
--
-- Mapeo etapa(bot) -> estado(codigo), validado contra el ESTADO_MAP ya usado
-- y corrido por migrate_crm.py + decisiones explicitas del fundador para los
-- 3 casos de Handoff sin precedente en los 6.136 leads historicos:
--   Inicial/JavitOff                                -> nuevo
--   M1,M2,M2.D,M3,M3.B,M4,M5                          -> contactado
--   M5.B,M5.C                                         -> agendado
--   Descalificado (cualquier motivo)                  -> descalificado
--   Handoff (cualquier razon) EXCEPTO crisis_emocional,
--     AgendaManual_1, AgendaManual_2                  -> calificado
--   Handoff razon=crisis_emocional                    -> nutricion
-- Estados posteriores a "agendado" (show_up, oferta_presentada,
-- reservo_oferta_valientes, ganado, perdido, no_show) quedan FUERA del
-- bridge: el bot nunca llega ahi; los gestiona un humano via el dashboard.
--
-- Simplificacion explicita: requiere p_manychat_id (el Worker ya corta antes
-- de llamar aqui si no hay manychat_subscriber_id resuelto, ver
-- hasNoResolvedContext() en worker_cloudflare.md) -- no se busca por
-- ig_handle como fallback, a diferencia del Apps Script actual.
create or replace function public.fn_sync_bot_turn(
  p_manychat_id      text,
  p_nombre           text,
  p_ig_handle        text default null,
  p_fuente_raw       text default null,
  p_profesion        text default null,
  p_salario_monto    numeric default null,
  p_dolor            text default null,
  p_urgencia_raw     text default null,   -- 'ahora' | 'algun_dia' | null (vocabulario del Worker)
  p_califica         boolean default null,
  p_handoff_humano   boolean default false,
  p_handoff_razon    text default null,
  p_etapa_bot        text default null,   -- M1..M5.C, Descalificado, Handoff, AgendaManual_1/2, JavitOff
  p_summary          text default null,
  p_ultimo_msg_lead  text default null,
  p_ultimo_msg_bot   text default null
) returns table(out_cliente_id uuid, out_gestion_lead_id uuid, out_estado_codigo text, out_avanzo boolean)
language plpgsql
security definer
set search_path to ''
as $$
declare
  v_bot_id              uuid;
  v_cliente_id          uuid;
  v_gestion_id          uuid;
  v_estado_actual_id    integer;
  v_estado_actual_cod   text;
  v_fuente_cod          text;
  v_fuente_id           integer;
  v_estado_destino_cod  text;
  v_urgencia            public.nivel_urgencia;
  v_avanzo              boolean := false;
  v_ig_handle           text;
begin
  if p_manychat_id is null or btrim(p_manychat_id) = '' then
    raise exception 'fn_sync_bot_turn: p_manychat_id es obligatorio.';
  end if;

  select id into v_bot_id from public.usuarios where nombre = 'Andrew' and es_bot limit 1;
  if v_bot_id is null then
    raise exception 'fn_sync_bot_turn: no existe usuario bot "Andrew" (es_bot=true) en usuarios.';
  end if;

  -- 1. Upsert de clientes -- SOLO columnas propiedad del bot. whatsapp_e164,
  --    correo y pais_iso2 nunca se tocan aqui (son manuales del closer);
  --    al omitirlas del UPDATE quedan intactas si el cliente ya existia
  --    (verificado con prueba real: no-clobber confirmado).
  v_ig_handle := nullif(btrim(lower(regexp_replace(coalesce(p_ig_handle, ''), '^@', ''))), '');

  insert into public.clientes
    (manychat_id, nombre, ig_handle, profesion, salario_monto,
     salario_currency, salario_periodicidad, notas)
  values
    (p_manychat_id,
     coalesce(nullif(btrim(p_nombre), ''), 'Lead ' || p_manychat_id),
     v_ig_handle, nullif(btrim(p_profesion), ''), p_salario_monto,
     case when p_salario_monto is not null then 'COP' end,
     case when p_salario_monto is not null then 'mensual'::public.periodicidad end,
     nullif(btrim(p_summary), ''))
  on conflict (manychat_id) do update
     set nombre                = coalesce(nullif(btrim(excluded.nombre), ''), public.clientes.nombre),
         ig_handle             = coalesce(excluded.ig_handle, public.clientes.ig_handle),
         profesion             = coalesce(excluded.profesion, public.clientes.profesion),
         salario_monto         = coalesce(excluded.salario_monto, public.clientes.salario_monto),
         salario_currency      = coalesce(excluded.salario_currency, public.clientes.salario_currency),
         salario_periodicidad  = coalesce(excluded.salario_periodicidad, public.clientes.salario_periodicidad),
         notas                 = coalesce(excluded.notas, public.clientes.notas)
  returning id into v_cliente_id;

  -- 2. fuente_codigo -- mismo mapeo ya validado por FUENTE_MAP de migrate_crm.py.
  v_fuente_cod := case lower(btrim(coalesce(p_fuente_raw, '')))
    when 'dm directo' then 'ig_organico'
    when 'dm directo (lead previa)' then 'ig_organico'
    when 'dm personal' then 'ig_organico'
    when 'personal' then 'ig_organico'
    when 'instagram' then 'ig_organico'
    when 'instagramn' then 'ig_organico'
    when 'story share (organico)' then 'ig_organico'
    when 'story reply (organico)' then 'ig_organico'
    when 'referido' then 'referido'
    when 'whatapp' then 'whatsapp'
    when 'whatssap' then 'whatsapp'
    when 'whatsapp' then 'whatsapp'
    else 'otro'
  end;
  select id into v_fuente_id from public.fuentes where codigo = v_fuente_cod;

  -- 3. urgencia -- mismo mapeo ya validado por URGENCIA_MAP de migrate_crm.py.
  v_urgencia := case p_urgencia_raw
    when 'ahora' then 'alta'::public.nivel_urgencia
    when 'algun_dia' then 'baja'::public.nivel_urgencia
    else null
  end;

  -- 4. estado_codigo destino -- mapeo etapa(bot)->estado validado sesion 15-ago-2026
  --    (ver comentario de cabecera de este archivo para el detalle completo).
  --    Se resuelve v_estado_actual_cod ANTES del CASE (bug #6, 29-ago-2026,
  --    ver cabecera) para poder usarlo como fallback seguro: sin señal de
  --    etapa (captura pasiva, p_etapa_bot null), el destino es "quedarse
  --    donde esta", nunca 'nuevo' fijo -- eso regresaba leads reales
  --    (agendado/calificado/contactado) hacia atras en cuanto mandaban
  --    cualquier mensaje de seguimiento.
  select codigo into v_estado_actual_cod from public.estados_lead where id = v_estado_actual_id;

  v_estado_destino_cod := case
    when p_handoff_humano and p_handoff_razon = 'crisis_emocional' then 'nutricion'
    when p_handoff_humano then 'calificado'
    when p_etapa_bot in ('AgendaManual_1', 'AgendaManual_2') then 'calificado'
    when p_etapa_bot = 'Descalificado' then 'descalificado'
    when p_etapa_bot in ('M5.B', 'M5.C') then 'agendado'
    when p_etapa_bot in ('M1', 'M2', 'M2.D', 'M3', 'M3.B', 'M4', 'M5') then 'contactado'
    else v_estado_actual_cod  -- sin señal reconocible: nunca se mueve el lead, ni adelante ni atras.
  end;

  -- 5. find-or-create gestion_leads: el intento MAS RECIENTE de este cliente.
  --    Si esta abierto (cerrado_at is null) se actualiza en el sitio. Si esta
  --    cerrado (venta perdida/descalificado/nutricion de un ciclo anterior) se
  --    REABRE via fn_avanzar_estado en el paso 6 (las transiciones
  --    'perdido/descalificado/nutricion -> contactado' ya existen en
  --    estado_transiciones, probado con TEST_BRIDGE_004) en vez de crear una
  --    fila paralela -- el indice parcial unico uq_gestion_abierta_por_cliente
  --    solo permite UNA fila abierta por cliente a la vez.
  select id, estado_id
    into v_gestion_id, v_estado_actual_id
    from public.gestion_leads
   where cliente_id = v_cliente_id
   order by fecha_contacto desc
   limit 1
   for update;

  if v_gestion_id is null then
    insert into public.gestion_leads
      (cliente_id, setter_id, fuente_id, estado_id, fecha_contacto, fecha_atendido,
       dolor, urgencia, califica, handoff_razon, origen_escritura, updated_by)
    values
      (v_cliente_id, v_bot_id, v_fuente_id,
       (select id from public.estados_lead where codigo = 'nuevo'),
       now(), now(), nullif(btrim(p_dolor), ''), v_urgencia, p_califica,
       nullif(btrim(p_handoff_razon), ''), 'worker_ia', v_bot_id)
    returning id, estado_id into v_gestion_id, v_estado_actual_id;
  else
    -- fecha_handoff NO se toca aqui: ck_gl_handoff_closer exige closer_id no
    -- nulo cuando fecha_handoff no es null (verificado en vivo con error real
    -- 23514), y el bot nunca asigna closer. Ese campo significa "cuando se
    -- entrego a UN CLOSER especifico", no "cuando el bot marco para revision
    -- humana" -- lo fijara la funcion que asigne closer, fuera de este bridge.
    update public.gestion_leads
       set dolor           = coalesce(nullif(btrim(p_dolor), ''), dolor),
           urgencia         = coalesce(v_urgencia, urgencia),
           califica         = coalesce(p_califica, califica),
           handoff_razon    = coalesce(nullif(btrim(p_handoff_razon), ''), handoff_razon),
           fecha_atendido   = now(),
           setter_id        = coalesce(setter_id, v_bot_id),
           origen_escritura = 'worker_ia',
           updated_by       = v_bot_id
     where id = v_gestion_id;
  end if;

  -- 6. Avance de estado -- SIEMPRE via fn_avanzar_estado (ya existe, ya valida
  --    transiciones legales contra estado_transiciones, y NO fuerza si un
  --    humano ya movio el lead a algo que la transicion automatica no cubre:
  --    "el estado registrado por un humano gana sobre la inferencia
  --    automatica", ver su propio comentario). fn_avanzar_estado solo permite
  --    UN salto a la vez: si el destino no es alcanzable directo desde el
  --    estado actual (ej. un lead recien creado en 'nuevo' cuyo PRIMER turno
  --    ya es un handoff de crisis emocional: 'nuevo'->'nutricion' NO es
  --    transicion directa, solo 'contactado'->'nutricion' lo es), se intenta
  --    UN salto intermedio via 'contactado' -- el unico intermedio que hace
  --    falta, porque desde 'contactado' SI son legales directamente
  --    'calificado','agendado','nutricion','descalificado'. Si el salto
  --    intermedio tampoco aplica (lead ya en estado terminal o mas avanzado
  --    por accion humana), fn_avanzar_estado vuelve a no-opear en silencio.
  --    avanzo=false es normal (mismo estado que ya tenia) -- no es un error.
  --    IMPORTANTE (bug #5, ver cabecera): se compara el codigo actual contra
  --    el destino ANTES de intentar nada -- si ya coinciden (ej. captura
  --    pasiva nueva, destino='nuevo', recien insertado en 'nuevo'), NO se
  --    intenta ningun salto. Sin esto, un lead nuevo se empujaba a
  --    'contactado' por error y quedaba atascado ahi para siempre.
  --    (v_estado_actual_cod ya se calculo en el paso 4, antes del CASE --
  --    bug #6, no se recalcula acá de nuevo.)
  if v_estado_actual_cod = v_estado_destino_cod then
    v_avanzo := false;
  else
    v_avanzo := public.fn_avanzar_estado(v_gestion_id, v_estado_destino_cod);
    if not v_avanzo and v_estado_destino_cod <> 'contactado' then
      perform public.fn_avanzar_estado(v_gestion_id, 'contactado');
      v_avanzo := public.fn_avanzar_estado(v_gestion_id, v_estado_destino_cod);
    end if;
  end if;

  select estado_id into v_estado_actual_id from public.gestion_leads where id = v_gestion_id;

  -- 7. Log de la conversacion -- SEPARADO del log automatico de trg_gl_log/
  --    fn_log_gestion (ese ya escribe 'creacion'/'cambio_estado'/'asignacion'
  --    en los pasos 5 y 6 de esta misma funcion). Este insert agrega el
  --    CONTENIDO del turno (mensajes + resumen) que el trigger automatico no
  --    conoce -- sin esto se pierde el texto de cada turno del bot.
  insert into public.activity_log
    (cliente_id, gestion_lead_id, evento, estado_nuevo_id, actor_tipo, actor_usuario_id,
     origen_escritura, ultimo_msg_lead, ultimo_msg_bot, summary)
  values
    (v_cliente_id, v_gestion_id,
     case when p_handoff_humano then 'handoff'::public.tipo_evento else 'mensaje_bot'::public.tipo_evento end,
     v_estado_actual_id, 'bot'::public.tipo_actor, v_bot_id, 'worker_ia',
     nullif(btrim(p_ultimo_msg_lead), ''), nullif(btrim(p_ultimo_msg_bot), ''),
     nullif(btrim(p_summary), ''));

  return query
    select v_cliente_id, v_gestion_id,
           (select codigo from public.estados_lead where id = v_estado_actual_id),
           v_avanzo;
end;
$$;

comment on function public.fn_sync_bot_turn is
  'Bridge en vivo Worker Cloudflare (Andrew) -> Supabase, una llamada por '
  'turno de conversacion. Reemplaza syncToCRM()/Apps Script/Google Sheet '
  'para trafico en vivo. Solo llamable con la service_role key.';

-- IMPORTANTE: el REVOKE debe reafirmarse despues de cualquier CREATE OR
-- REPLACE futuro sobre esta funcion -- se detecto empiricamente (via mcp
-- Supabase get_advisors + information_schema.role_routine_grants, no
-- asumido) que anon/authenticated quedaban con EXECUTE pese a un REVOKE en
-- una migracion previa. Reverificar con la consulta de abajo tras cualquier
-- cambio:
--   select grantee, privilege_type from information_schema.role_routine_grants
--   where routine_schema='public' and routine_name='fn_sync_bot_turn';
revoke execute on function public.fn_sync_bot_turn(
  text, text, text, text, text, numeric, text, text, boolean, boolean, text, text, text, text, text
) from public, anon, authenticated;

grant execute on function public.fn_sync_bot_turn(
  text, text, text, text, text, numeric, text, text, boolean, boolean, text, text, text, text, text
) to service_role;
