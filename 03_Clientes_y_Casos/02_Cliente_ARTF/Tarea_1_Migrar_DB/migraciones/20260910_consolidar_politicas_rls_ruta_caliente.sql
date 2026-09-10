-- ============================================================================
-- 2026-09-10 · Consolidar políticas RLS duplicadas en la ruta caliente
-- ============================================================================
--
-- ⚠️ ESTA MIGRACIÓN NO CREA NINGÚN ÍNDICE, Y ESO ES A PROPÓSITO.
--
-- Se abrió una alerta de "Disk I/O Budget" de Supabase con la hipótesis de que
-- había Full Table Scans en las vistas del dashboard por índices faltantes. La
-- auditoría contra las estadísticas de la propia base dice que no:
--
--   1. El linter de Supabase reporta CERO claves foráneas sin índice. Lo que sí
--      reporta son 34 índices que NUNCA se han usado. Sobran, no faltan.
--
--   2. Las lecturas no llegan a disco. En 47 días de estadísticas:
--        gestion_leads      333 bloques de disco vs 1.665.687.799 de caché (0,000% de fallo)
--        usuarios             5 bloques de disco vs 1.437.724.027 de caché (0,000% de fallo)
--      La base entera leyó ~94 MB de disco en 47 días. Un índice acelera
--      lecturas que van a disco; acá ya no van. Crear índices nuevos sólo
--      habría sumado escritura en cada INSERT/UPDATE y más disco ocupado, o
--      sea lo contrario de proteger el presupuesto de IOPS.
--
--   3. Las escrituras son mínimas: 61.629 inserts y ~41.000 updates en 47 días.
--
-- LO QUE SÍ SE ARREGLA ACÁ, y es un hallazgo del propio linter (lint 0006,
-- "Multiple Permissive Policies", 25 casos): `usuarios` y `usuario_roles` son
-- las tablas más consultadas de toda la base -- las tocan TODAS las funciones
-- de RLS (fn_es_admin, fn_usuario_id, fn_tiene_rol) -- y cada SELECT sobre
-- ellas evalúa DOS políticas permisivas en vez de una.
--
-- Postgres evalúa todas las políticas permisivas y las une con OR. Como
-- `pol_*_read` ya es USING (true) para `authenticated`, la política de admin
-- NO puede habilitar una sola fila que la otra no haya habilitado ya: para
-- SELECT es trabajo puro sin efecto. Se la restringe a los comandos de
-- escritura, donde sí decide.
--
-- NO CAMBIA QUIÉN VE QUÉ. La condición de lectura sigue siendo exactamente
-- `true` para `authenticated`, igual que antes de esta migración. Lo único que
-- cambia es cuántas veces se evalúa. En `usuarios` el UPDATE también queda con
-- una sola política, porque `pol_usuarios_self` ya contiene `OR fn_es_admin()`
-- -- la de admin era redundante ahí también.
--
-- SI HAY QUE REVERTIRLA: volver a crear las dos políticas como FOR ALL con
-- USING/WITH CHECK `(select fn_es_admin())`, que es como estaban.
-- ============================================================================

begin;

-- ---------------------------------------------------------------------------
-- usuarios
-- ---------------------------------------------------------------------------
drop policy if exists pol_usuarios_admin on public.usuarios;

-- El UPDATE lo cubre `pol_usuarios_self`, que ya incluye `OR fn_es_admin()`.
-- Acá sólo quedan INSERT y DELETE, que antes venían del FOR ALL.
create policy pol_usuarios_admin_insert on public.usuarios
  for insert to authenticated
  with check ((select public.fn_es_admin()));

create policy pol_usuarios_admin_delete on public.usuarios
  for delete to authenticated
  using ((select public.fn_es_admin()));

-- ---------------------------------------------------------------------------
-- usuario_roles
-- ---------------------------------------------------------------------------
drop policy if exists pol_roles_admin on public.usuario_roles;

create policy pol_roles_admin_insert on public.usuario_roles
  for insert to authenticated
  with check ((select public.fn_es_admin()));

create policy pol_roles_admin_update on public.usuario_roles
  for update to authenticated
  using ((select public.fn_es_admin()))
  with check ((select public.fn_es_admin()));

create policy pol_roles_admin_delete on public.usuario_roles
  for delete to authenticated
  using ((select public.fn_es_admin()));

commit;
