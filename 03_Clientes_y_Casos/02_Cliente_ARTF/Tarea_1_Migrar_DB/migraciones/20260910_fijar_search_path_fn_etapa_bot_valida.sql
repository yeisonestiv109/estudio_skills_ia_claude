-- ============================================================================
-- 2026-09-10 · search_path fijo en fn_etapa_bot_valida
-- APLICADA en lrdtjsxtaadpgrzkchlw y verificada con verificar.sh (20 etapas).
-- ============================================================================
--
-- La funcion se recreo el 7-sep-2026 para agregar la etapa
-- M2_VERIFICAR_CALCULO y quedo sin `set search_path`. Es lo UNICO que el linter
-- de seguridad de Supabase reporta en toda la base (lint 0011). Vive dentro de
-- un CHECK de `gestion_leads.etapa_bot`, o sea que corre con el search_path de
-- quien escriba la fila; fijarlo la vuelve independiente de eso.
--
-- Mismo cuerpo exacto, mismas 24 etapas. No cambia ningun comportamiento.
create or replace function public.fn_etapa_bot_valida(p_etapa text)
returns boolean
language sql
immutable
set search_path = ''
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
