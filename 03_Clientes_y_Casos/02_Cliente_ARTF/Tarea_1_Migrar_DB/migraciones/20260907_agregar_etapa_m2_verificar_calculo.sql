-- ============================================================================
-- 2026-09-07 · Agrega la etapa M2_VERIFICAR_CALCULO
-- APLICADA en el proyecto lrdtjsxtaadpgrzkchlw y verificada con smoke_rpc.mjs.
-- ============================================================================
--
-- POR QUE: cuando el endeudamiento reportado supera el tope de su ingreso, el
-- bot ya no descalifica de una. Primero repregunta si la cuenta esta bien
-- hecha -- si sumo las cuotas mensuales o la deuda total, y si metio arriendo,
-- servicios o mercado, que son gastos fijos y NO son deudas. Ese turno
-- necesita su propia etapa para que el clasificador use el esquema correcto y
-- el router sepa que esta esperando una cifra corregida.
--
-- ES ADITIVA Y SEGURA: solo agrega un valor al conjunto aceptado, asi que
-- ninguna fila existente puede volverse invalida. Postgres no revalida las
-- filas ya escritas al reemplazar la funcion de un CHECK.
--
-- ⚠️ TRES SITIOS TIENEN QUE ESTAR DE ACUERDO sobre la lista de etapas:
--   1. este CHECK,
--   2. ESQUEMA_POR_ETAPA en worker_bot_setter_v42.js,
--   3. ETAPAS_QUE_ESCRIBE_EL_ROUTER en smoke_rpc.mjs.
-- Una etapa que falte en (1) revienta la escritura; en (2) apaga el LLM en
-- silencio (crisis y hostilidad dejan de evaluarse). Ya paso tres veces.
create or replace function public.fn_etapa_bot_valida(p_etapa text)
returns boolean
language sql
immutable
as $function$
  select p_etapa is null or p_etapa in (
    'M1_ENVIADO', 'M1_INGRESO_AMBIGUO', 'M1_RANGO_PREGUNTADO', 'M1_ACLARAR_REMANENTE',
    'M2_ENVIADO', 'M2_BORDERLINE', 'M2_NO_SABE', 'M2_VERIFICAR_CALCULO',
    'M3_ENVIADO', 'M3_RECONDUCIR',
    'M4_ENVIADO', 'M5_ENVIADO', 'M6_ENVIADO', 'M7_ENVIADO',
    'M7_ESPERANDO_VINCULO',
    'SIN_HORARIOS_ESPERANDO_FRANJA',
    'CIERRE_PRECALL', 'RETORNO_PREGUNTA',
    'BLINDAJE_ENVIADO', 'BLINDAJE_CERRADO',
    'DESCALIFICADO', 'HANDOFF',
    'M4_URGENCIA_REINTENTO', 'M5_PITCH_REINTENTO'
  )
$function$;
