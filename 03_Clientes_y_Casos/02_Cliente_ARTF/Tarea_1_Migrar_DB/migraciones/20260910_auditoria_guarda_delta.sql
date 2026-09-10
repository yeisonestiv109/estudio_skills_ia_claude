-- ============================================================================
-- 2026-09-10 · auditoria_cambios guarda el DELTA, no la fila completa
-- APLICADA en lrdtjsxtaadpgrzkchlw y verificada con una escritura real.
-- ============================================================================
--
-- QUE HACIA ANTES: en cada UPDATE guardaba `to_jsonb(old)` y `to_jsonb(new)`
-- ENTEROS, aunque ya calculaba `campos` con lo que de verdad habia cambiado.
--
-- MEDIDO sobre los 33.812 UPDATE ya registrados:
--   cambian 2,5 campos en promedio
--   jsonb hoy: 54 MB · con delta: 5.835 kB  ->  -89,5%
-- Verificado despues de aplicar, con una escritura real del smoke:
--   una fila de auditoria paso de ~1.724 bytes a 222  ->  -87%
--
-- ⚠️ POR QUE ESTO NO ES EL ARREGLO DE LA ALERTA DE DISK I/O, y conviene que
-- quede escrito para no volver a creerlo:
--   · `shared_buffers` son 224 MB y la base entera pesa 128 MB: cabe completa
--     en cache. No hay nada que desalojar.
--   · `auditoria_cambios` es data FRIA: 198.635 accesos a buffer contra
--     1.665.687.799 de `gestion_leads` (0,012% del trafico de cache).
--   · El disco son 2 GB y la base 128 MB. Tampoco hay presion de espacio.
-- El beneficio real es OTRO y es a futuro: cada UPDATE de `gestion_leads`
-- escribia ~1,7 kB de jsonb al WAL. Con el bot ya recibiendo leads reales
-- (24 el 10-sep, todos con origen_escritura='worker_ia'), esa escritura se
-- multiplica por turno. Bajarla 87% es menos WAL por transaccion.
--
-- EDGE CASES CONTEMPLADOS
--  1. `registro_id` se resuelve ANTES de recortar. Si se calculara despues, un
--     UPDATE que no toca la PK dejaria el delta sin la clave 'id' y la fila
--     entera caeria en 'sin_id' -- auditoria imposible de rastrear. Verificado:
--     la fila nueva trae el uuid correcto sin llevar 'id' en el delta.
--  2. INSERT y DELETE conservan la fila COMPLETA a proposito: son la linea base
--     con la que se reconstruye el historial a partir de los deltas.
--  3. Si lo unico que cambia es `updated_at`, no se escribe fila (igual que antes).
--  4. Las filas viejas conservan el jsonb completo. `campos` es el
--     discriminador: si sus claves coinciden con las de `datos_despues`, es un
--     delta; si `datos_despues` trae mas claves, es una fila del formato viejo.
--     Hoy no hay ningun consumidor (verificado con grep en el dashboard y en el
--     Worker), asi que no rompe a nadie.
--  5. Una columna nueva de la tabla auditada entra sola. Si la clave no existia
--     en `old`, el delta guarda JSON null, que es la semantica correcta.
--
-- REVERTIR: restaurar el cuerpo anterior (sin las dos lineas de jsonb_object_agg
-- y con el coalesce del registro_id en linea dentro del insert).
-- ============================================================================
create or replace function public.fn_auditar()
returns trigger
language plpgsql
security definer
set search_path to ''
as $function$
declare
  v_antes jsonb; v_despues jsonb; v_campos text[]; v_registro text;
begin
  v_antes   := case when tg_op = 'INSERT' then null else to_jsonb(old) end;
  v_despues := case when tg_op = 'DELETE' then null else to_jsonb(new) end;

  -- Se resuelve ANTES de recortar (ver edge case 1).
  -- usuario_roles no tiene columna 'id': PK compuesta, se cae a usuario_id.
  v_registro := coalesce(v_despues ->> 'id',         v_antes ->> 'id',
                         v_despues ->> 'usuario_id', v_antes ->> 'usuario_id',
                         'sin_id');

  if tg_op = 'UPDATE' then
    select array_agg(n.key order by n.key) into v_campos
    from jsonb_each(v_despues) n
    where n.value is distinct from (v_antes -> n.key) and n.key <> 'updated_at';
    if v_campos is null then return null; end if;

    v_antes   := (select jsonb_object_agg(k, v_antes   -> k) from unnest(v_campos) k);
    v_despues := (select jsonb_object_agg(k, v_despues -> k) from unnest(v_campos) k);
  end if;

  insert into public.auditoria_cambios
    (tabla, registro_id, operacion, campos, datos_antes, datos_despues, auth_uid)
  values (tg_table_name, v_registro, left(tg_op, 1), v_campos, v_antes, v_despues,
          public.fn_auth_uid());
  return null;
end $function$;
