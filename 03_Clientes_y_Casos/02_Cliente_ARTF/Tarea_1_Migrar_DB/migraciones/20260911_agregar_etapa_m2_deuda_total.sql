-- ============================================================================
-- 2026-09-11 · Etapa M2_DEUDA_TOTAL
-- APLICADA en lrdtjsxtaadpgrzkchlw y verificada (21 etapas en verificar.sh).
-- ============================================================================
--
-- POR QUE: bug reportado en vivo. Un lead dio una cifra de deuda enorme y el
-- clasificador lo leyo como RESISTENCIA a dar el dato (Objecion 6). No era
-- resistencia: habia sumado el SALDO TOTAL de sus creditos en vez de la cuota
-- que paga al mes. Es el error de cuentas mas comun del embudo, y castigarlo
-- como si el lead estuviera ocultando algo quema un lead que si califica.
--
-- Ahora, cuando la cifra no cabe como cuota mensual (se lleva el ingreso
-- entero), el bot lo aclara con el copy del fundador y espera la cifra buena.
-- Ese turno necesita su propia etapa para que el clasificador use el esquema
-- correcto y el router sepa que esta esperando una correccion.
--
-- Aditiva: solo agrega un valor al conjunto aceptado, ninguna fila existente
-- puede volverse invalida.
--
-- ⚠️ TRES SITIOS TIENEN QUE ESTAR DE ACUERDO sobre la lista de etapas:
--   1. este CHECK,
--   2. ESQUEMA_POR_ETAPA en worker_bot_setter_v42.js,
--   3. ETAPAS_QUE_ESCRIBE_EL_ROUTER en smoke_rpc.mjs.
-- Una etapa que falte en (1) revienta la escritura; en (2) apaga el LLM en
-- silencio y deja de evaluarse crisis/hostilidad. Ya paso tres veces.
create or replace function public.fn_etapa_bot_valida(p_etapa text)
returns boolean
language sql
immutable
set search_path = ''
as $function$
  select p_etapa is null or p_etapa in (
    'M1_ENVIADO', 'M1_INGRESO_AMBIGUO', 'M1_RANGO_PREGUNTADO', 'M1_ACLARAR_REMANENTE',
    'M2_ENVIADO', 'M2_BORDERLINE', 'M2_NO_SABE', 'M2_VERIFICAR_CALCULO', 'M2_DEUDA_TOTAL',
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
