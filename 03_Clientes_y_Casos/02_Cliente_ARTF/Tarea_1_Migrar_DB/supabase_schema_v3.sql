-- ============================================================================
-- CRM "Andres Resuelve Tus Finanzas" · Esquema Supabase v3 (Production-Grade)
-- Refactor del ERD v2. Ejecutar de corrido en el SQL Editor de Supabase.
-- Convencion de dinero: (monto, currency_code, fx_rate_usd) — NUNCA en el nombre.
-- ============================================================================

begin;

create extension if not exists pgcrypto;
create extension if not exists citext;

-- Zona horaria de negocio. Se usa explicitamente en las vistas de reporte para
-- que el "dia" del scorecard no dependa del TZ de la sesion que consulta.
create or replace function public.fn_tz() returns text
language sql immutable parallel safe as $$ select 'America/Bogota' $$;

-- ---------------------------------------------------------------------------
-- 1. Tipos enumerados (reemplazan los `text` libres del v2)
-- ---------------------------------------------------------------------------
do $$
declare r record;
begin
  for r in select * from (values
    ('app_rol',          array['admin','setter','closer','analista','bot']),
    ('categoria_estado', array['nuevo','contactado','calificado','agendado','presentado','ganado','perdido','nutricion']),
    ('nivel_urgencia',   array['baja','media','alta','critica']),
    ('periodicidad',     array['mensual','quincenal','anual']),
    ('estado_reunion',   array['agendada','confirmada','realizada','no_show','cancelada','reprogramada']),
    ('forma_pago',       array['contado','cuotas','mixto','financiado_externo']),
    ('estado_venta',     array['activa','anulada','reembolso_parcial','reembolso_total']),
    ('tipo_ajuste',      array['reembolso','chargeback','descuento_posventa','correccion']),
    ('estado_cuota',     array['pendiente','parcial','pagada','vencida','incobrable']),
    ('tipo_producto',    array['core','low_ticket','upsell','otro']),
    ('origen_escritura', array['worker_ia','formulario_humano','importacion','api','manual_sql']),
    ('tipo_actor',       array['usuario','bot','sistema']),
    ('tipo_evento',      array['creacion','cambio_estado','asignacion','handoff','mensaje_lead',
                               'mensaje_bot','agendamiento','show_up','no_show','oferta','venta',
                               'pago','ajuste','nota'])
  ) as v(nombre, valores) loop
    if not exists (select 1 from pg_type where typname = r.nombre) then
      execute format('create type public.%I as enum (%s)', r.nombre,
        (select string_agg(quote_literal(x), ',') from unnest(r.valores) x));
    end if;
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- 2. Catalogos monetarios
--    El v2 codificaba la moneda en el nombre de columna (revenue_cop). Vender
--    un solo ticket en USD obligaba a migrar el esquema. Aqui se desacopla.
-- ---------------------------------------------------------------------------
create table if not exists public.monedas (
  code       char(3) primary key,
  nombre     text    not null,
  decimales  smallint not null default 2 check (decimales between 0 and 4),
  activo     boolean not null default true
);

create table if not exists public.tasas_cambio (
  id             bigint generated always as identity primary key,
  moneda_origen  char(3) not null references public.monedas(code),
  moneda_destino char(3) not null references public.monedas(code),
  fecha          date    not null,
  tasa           numeric(18,8) not null check (tasa > 0),
  fuente         text,
  created_at     timestamptz not null default now(),
  constraint uq_tasa_dia unique (moneda_origen, moneda_destino, fecha),
  constraint ck_tasa_distinta check (moneda_origen <> moneda_destino)
);
comment on table public.tasas_cambio is
  'FX historico. El monto_usd de VENTAS se congela con la tasa del dia de cierre.';

-- ---------------------------------------------------------------------------
-- 3. Usuarios y roles
--    Cambio de diseno: rol many-to-many. En el v2 `usuarios.rol text` impedia
--    que Andres sea CEO y closer a la vez, o que Gaby setee y cierre low ticket.
--    `auth_user_id` es NULLABLE a proposito: el Setter IA es un usuario sin
--    cuenta en auth.users (escribe con la service_role key).
-- ---------------------------------------------------------------------------
create table if not exists public.usuarios (
  id           uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique references auth.users(id) on delete set null,
  nombre       text not null check (length(btrim(nombre)) > 0),
  email        citext unique,
  es_bot       boolean not null default false,
  activo       boolean not null default true,
  version      integer not null default 1,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table if not exists public.usuario_roles (
  usuario_id uuid not null references public.usuarios(id) on delete cascade,
  rol        public.app_rol not null,
  primary key (usuario_id, rol)
);
create index if not exists ix_usuario_roles_rol on public.usuario_roles(rol);

-- ---------------------------------------------------------------------------
-- 4. Catalogos de negocio
-- ---------------------------------------------------------------------------

-- 4.1 Fuentes de adquisicion
create table if not exists public.fuentes (
  id         integer generated always as identity primary key,
  codigo     text not null unique check (codigo ~ '^[a-z0-9_]+$'),
  nombre     text not null,
  canal      text,                       -- instagram | whatsapp | referido | organico
  es_pagada  boolean not null default false,
  activo     boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 4.2 Productos. El scorecard ya discrimina Core / Low ticket / Producto 3 / 4.
--     Sin esta tabla, %Close Rate y AOV mezclan tickets de $5.25M con upsells.
create table if not exists public.productos (
  id              integer generated always as identity primary key,
  codigo          text not null unique check (codigo ~ '^[a-z0-9_]+$'),
  nombre          text not null,
  tipo            public.tipo_producto not null default 'core',
  precio_lista    numeric(14,2) check (precio_lista >= 0),
  currency_code   char(3) not null default 'COP' references public.monedas(code),
  duracion_dias   integer check (duracion_dias > 0),
  activo          boolean not null default true,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- 4.3 Estados del lead: catalogo + semantica de embudo explicita.
--     Los flags `cuenta_como_*` mueven la definicion de cada metrica del
--     scorecard desde formulas de Sheets hacia datos versionables.
create table if not exists public.estados_lead (
  id                     integer generated always as identity primary key,
  codigo                 text not null unique check (codigo ~ '^[a-z0-9_]+$'),
  nombre                 text not null,
  categoria              public.categoria_estado not null,
  orden                  smallint not null,
  es_terminal            boolean not null default false,
  es_ganado              boolean not null default false,
  cuenta_como_booking    boolean not null default false,
  cuenta_como_show_up    boolean not null default false,
  cuenta_como_oferta     boolean not null default false,
  activo                 boolean not null default true,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  constraint uq_estado_orden check (orden >= 0),
  constraint ck_ganado_es_terminal check (not es_ganado or es_terminal)
);
create unique index if not exists uq_estados_orden on public.estados_lead(orden);

-- 4.4 Maquina de estados. Whitelist de transiciones validas: el motor de
--     etapas deja de vivir en Apps Script y pasa a ser un invariante de la BD.
create table if not exists public.estado_transiciones (
  estado_origen_id  integer not null references public.estados_lead(id) on delete cascade,
  estado_destino_id integer not null references public.estados_lead(id) on delete cascade,
  requiere_rol      public.app_rol,
  primary key (estado_origen_id, estado_destino_id),
  constraint ck_transicion_distinta check (estado_origen_id <> estado_destino_id)
);

-- ---------------------------------------------------------------------------
-- 5. CLIENTES (la persona; identidad estable e independiente de la campana)
--    Cambios vs v2:
--      · salario: text -> numerico + moneda + periodicidad (requisito 3)
--      · palabra_clave_ad SE MUEVE a gestion_leads: es un atributo del evento
--        de adquisicion, no de la persona. Si el lead vuelve en la campana 2,
--        el v2 sobrescribia el dato de atribucion de la campana 1.
-- ---------------------------------------------------------------------------
create table if not exists public.clientes (
  id                  uuid primary key default gen_random_uuid(),
  manychat_id         text unique,
  nombre              text not null check (length(btrim(nombre)) > 0),
  ig_handle           citext,
  whatsapp_e164       text check (whatsapp_e164 ~ '^\+[1-9][0-9]{7,14}$'),
  correo              citext check (correo ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  profesion           text,
  salario_monto       numeric(14,2) check (salario_monto >= 0),
  salario_currency    char(3) references public.monedas(code),
  salario_periodicidad public.periodicidad,
  pais_iso2           char(2) check (pais_iso2 ~ '^[A-Z]{2}$'),
  notas               text,
  version             integer not null default 1,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  -- Si hay monto, la moneda y la periodicidad son obligatorias.
  constraint ck_salario_completo check (
    salario_monto is null
    or (salario_currency is not null and salario_periodicidad is not null)
  )
);
create unique index if not exists uq_clientes_whatsapp
  on public.clientes(whatsapp_e164) where whatsapp_e164 is not null;
create unique index if not exists uq_clientes_ig
  on public.clientes(ig_handle) where ig_handle is not null;
create index if not exists ix_clientes_created_at on public.clientes(created_at desc);
comment on column public.clientes.whatsapp_e164 is
  'Normalizado E.164 (+573001112233). Requisito para deduplicar 100 leads/dia.';

-- ---------------------------------------------------------------------------
-- 6. GESTION_LEADS (el proceso comercial; 1 cliente puede tener N historicos
--    pero SOLO UNO abierto a la vez — requisito 2)
-- ---------------------------------------------------------------------------
create table if not exists public.gestion_leads (
  id                  uuid primary key default gen_random_uuid(),
  cliente_id          uuid    not null references public.clientes(id) on delete restrict,
  setter_id           uuid    references public.usuarios(id) on delete restrict,
  closer_id           uuid    references public.usuarios(id) on delete restrict,
  fuente_id           integer not null references public.fuentes(id) on delete restrict,
  estado_id           integer not null references public.estados_lead(id) on delete restrict,
  producto_interes_id integer references public.productos(id) on delete restrict,

  palabra_clave_ad    text,
  campana             text,
  utm_source          text,
  utm_campaign        text,

  fecha_contacto      timestamptz not null default now(),
  fecha_atendido      timestamptz,
  fecha_calificacion  timestamptz,
  fecha_handoff       timestamptz,

  dolor               text,
  urgencia            public.nivel_urgencia,
  califica            boolean,
  handoff_razon       text,
  notas               text,

  -- Cierre del proceso. Lo escribe el trigger cuando el estado es terminal;
  -- es la columna que hace posible el unique index parcial.
  cerrado_at          timestamptz,

  -- Trazabilidad forense de la escritura (Worker IA vs Formulario humano)
  origen_escritura    public.origen_escritura not null default 'formulario_humano',
  updated_by          uuid references public.usuarios(id) on delete set null,

  version             integer not null default 1,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),

  constraint ck_gl_fechas_orden check (
    (fecha_atendido     is null or fecha_atendido     >= fecha_contacto) and
    (fecha_calificacion is null or fecha_calificacion >= fecha_contacto) and
    (fecha_handoff      is null or fecha_handoff      >= fecha_contacto) and
    (cerrado_at         is null or cerrado_at         >= fecha_contacto)
  ),
  -- No se puede hacer handoff sin closer asignado.
  -- (setter_id = closer_id se permite: Andres setea y cierra el mismo lead.)
  constraint ck_gl_handoff_closer check (fecha_handoff is null or closer_id is not null)
);

-- >>> REQUISITO 2: unicidad parcial. Un solo proceso abierto por cliente.
create unique index if not exists uq_gestion_abierta_por_cliente
  on public.gestion_leads(cliente_id) where cerrado_at is null;
comment on index public.uq_gestion_abierta_por_cliente is
  'Impide dos pipelines simultaneos del mismo cliente (doble comision, doble booking).';

-- Indices del Daily Metrics Scorecard (los rangos de fecha son el 90% del WHERE)
create index if not exists ix_gl_fecha_contacto      on public.gestion_leads(fecha_contacto desc);
create index if not exists ix_gl_estado              on public.gestion_leads(estado_id);
create index if not exists ix_gl_setter_fecha        on public.gestion_leads(setter_id, fecha_contacto desc);
create index if not exists ix_gl_closer_fecha        on public.gestion_leads(closer_id, fecha_contacto desc);
create index if not exists ix_gl_fuente_fecha        on public.gestion_leads(fuente_id, fecha_contacto desc);
create index if not exists ix_gl_cliente             on public.gestion_leads(cliente_id);
-- Tablero Kanban: solo interesan los procesos vivos (~cientos de filas de miles).
create index if not exists ix_gl_pipeline_abierto
  on public.gestion_leads(estado_id, fecha_contacto desc) where cerrado_at is null;
-- Cola del closer: leads calificados sin asignar.
create index if not exists ix_gl_cola_calificados
  on public.gestion_leads(fecha_calificacion) where califica and closer_id is null and cerrado_at is null;

-- ---------------------------------------------------------------------------
-- 7. REUNIONES (Bookings / Show Ups / Ofertas)
--    Cambio no solicitado: se agrega `oferta_presentada` y `monto_ofertado`.
--    En el CSV del scorecard, %Offer Rate reporta 0,00% en todos los meses
--    porque NINGUNA tabla registra si se hizo la oferta. La metrica existe en
--    el reporte pero no en el modelo de datos.
-- ---------------------------------------------------------------------------
create table if not exists public.reuniones (
  id                  uuid primary key default gen_random_uuid(),
  gestion_lead_id     uuid not null references public.gestion_leads(id) on delete restrict,
  closer_id           uuid references public.usuarios(id) on delete restrict,
  estado              public.estado_reunion not null default 'agendada',

  fecha_agendamiento  timestamptz not null default now(),  -- cuando se booked
  fecha_programada    timestamptz not null,                -- cuando es la llamada
  fecha_realizada     timestamptz,
  numero_intento      smallint not null default 1 check (numero_intento between 1 and 20),
  reprograma_a        uuid references public.reuniones(id) on delete set null,

  oferta_presentada   boolean not null default false,
  monto_ofertado      numeric(14,2) check (monto_ofertado >= 0),
  oferta_currency     char(3) references public.monedas(code),

  motivo_no_show      text,
  notas               text,
  origen_escritura    public.origen_escritura not null default 'formulario_humano',
  updated_by          uuid references public.usuarios(id) on delete set null,
  version             integer not null default 1,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),

  constraint ck_re_realizada_tiene_fecha check (
    (estado <> 'realizada') or fecha_realizada is not null
  ),
  constraint ck_re_fecha_realizada_orden check (
    fecha_realizada is null or fecha_realizada >= fecha_agendamiento
  ),
  constraint ck_re_oferta_requiere_show check (
    not oferta_presentada or estado = 'realizada'
  ),
  constraint ck_re_oferta_monto check (
    not oferta_presentada or (monto_ofertado is not null and oferta_currency is not null)
  )
);

-- REQUISITO 2 (segunda aplicacion): una sola reunion viva por proceso.
create unique index if not exists uq_reunion_activa_por_lead
  on public.reuniones(gestion_lead_id)
  where estado in ('agendada','confirmada');

create index if not exists ix_re_programada       on public.reuniones(fecha_programada desc);
create index if not exists ix_re_agendamiento     on public.reuniones(fecha_agendamiento desc);
create index if not exists ix_re_closer_programada on public.reuniones(closer_id, fecha_programada desc);
create index if not exists ix_re_lead             on public.reuniones(gestion_lead_id);
-- Show Up Rate: solo cuentan las que llegaron a la llamada.
create index if not exists ix_re_show_ups
  on public.reuniones(fecha_realizada desc) where estado = 'realizada';
-- Agenda del dia / recordatorios de confirmacion.
create index if not exists ix_re_pendientes
  on public.reuniones(fecha_programada) where estado in ('agendada','confirmada');

-- ---------------------------------------------------------------------------
-- 8. VENTAS — FUENTE DE VERDAD HISTORICA INMUTABLE (requisito 1)
--
--    Principio: una venta es un HECHO ocurrido en un instante. Nada de lo que
--    pase despues (reasignar el lead a otro closer, corregir el telefono del
--    cliente, renombrar el producto) puede alterar lo que se facturo ni a quien
--    se le paga la comision. Por eso:
--      a) Se DENORMALIZA a proposito: closer_id / setter_id / cliente_id /
--         producto_id / % de comision se copian aqui como SNAPSHOT.
--      b) UPDATE y DELETE estan bloqueados por trigger. Toda correccion es una
--         fila nueva en VENTA_AJUSTES (contabilidad de partida doble, no borron).
--      c) NO existe `upfront_cash`: eso es la cuota 0 en PAGOS_CUOTAS (req. 3).
--         El v2 guardaba revenue_cop y upfront_cash_cop en la misma fila que las
--         cuotas -> dos fuentes para el mismo saldo, garantia de descuadre.
-- ---------------------------------------------------------------------------
create table if not exists public.ventas (
  id                   uuid primary key default gen_random_uuid(),
  gestion_lead_id      uuid not null references public.gestion_leads(id) on delete restrict,
  reunion_id           uuid references public.reuniones(id) on delete restrict,

  -- ---- SNAPSHOT DE ATRIBUCION (inmutable, NO seguir el FK para reportar) ----
  cliente_id           uuid    not null references public.clientes(id) on delete restrict,
  closer_id            uuid    not null references public.usuarios(id) on delete restrict,
  setter_id            uuid    references public.usuarios(id) on delete restrict,
  fuente_id            integer not null references public.fuentes(id) on delete restrict,
  producto_id          integer not null references public.productos(id) on delete restrict,
  producto_nombre_snap text    not null,
  comision_closer_pct  numeric(5,2) not null default 0 check (comision_closer_pct between 0 and 100),
  comision_setter_pct  numeric(5,2) not null default 0 check (comision_setter_pct between 0 and 100),

  -- ---- DINERO: monto + moneda + FX congelado (requisito 3) ----
  fecha_venta          timestamptz not null default now(),
  monto_total          numeric(14,2) not null check (monto_total > 0),
  currency_code        char(3) not null references public.monedas(code),
  fx_rate_usd          numeric(18,8) check (fx_rate_usd > 0),
  monto_total_usd      numeric(14,2)
    generated always as (
      case when fx_rate_usd is not null then round(monto_total / fx_rate_usd, 2) end
    ) stored,

  forma_pago           public.forma_pago not null,
  num_cuotas_pactadas  smallint not null default 1 check (num_cuotas_pactadas between 1 and 60),
  fecha_inicio_programa date,
  fecha_fin_programa    date,

  contrato_url         text,
  notas                text,
  origen_escritura     public.origen_escritura not null default 'formulario_humano',
  created_by           uuid references public.usuarios(id) on delete set null,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),

  constraint ck_ve_programa_orden check (
    fecha_fin_programa is null or fecha_inicio_programa is null
    or fecha_fin_programa >= fecha_inicio_programa
  ),
  constraint ck_ve_comision_total check (comision_closer_pct + comision_setter_pct <= 100)
);

-- Una venta por proceso comercial. Un upsell abre su propio gestion_lead.
create unique index if not exists uq_venta_por_gestion on public.ventas(gestion_lead_id);
create index if not exists ix_ve_fecha        on public.ventas(fecha_venta desc);
create index if not exists ix_ve_closer_fecha on public.ventas(closer_id, fecha_venta desc);
create index if not exists ix_ve_setter_fecha on public.ventas(setter_id, fecha_venta desc);
create index if not exists ix_ve_producto     on public.ventas(producto_id, fecha_venta desc);
create index if not exists ix_ve_fuente       on public.ventas(fuente_id, fecha_venta desc);
create index if not exists ix_ve_cliente      on public.ventas(cliente_id);

-- ---------------------------------------------------------------------------
-- 8.1 VENTA_AJUSTES — el unico camino para "modificar" una venta.
--     Reembolsos, chargebacks y correcciones son filas con signo, nunca UPDATE.
-- ---------------------------------------------------------------------------
create table if not exists public.venta_ajustes (
  id            uuid primary key default gen_random_uuid(),
  venta_id      uuid not null references public.ventas(id) on delete restrict,
  tipo          public.tipo_ajuste not null,
  monto         numeric(14,2) not null check (monto <> 0),  -- negativo = resta
  currency_code char(3) not null references public.monedas(code),
  fecha_efecto  timestamptz not null default now(),
  motivo        text not null check (length(btrim(motivo)) > 0),
  autorizado_por uuid references public.usuarios(id) on delete set null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  constraint ck_aj_signo check (
    (tipo in ('reembolso','chargeback','descuento_posventa') and monto < 0)
    or (tipo = 'correccion')
  )
);
create index if not exists ix_aj_venta on public.venta_ajustes(venta_id);
create index if not exists ix_aj_fecha on public.venta_ajustes(fecha_efecto desc);

-- ---------------------------------------------------------------------------
-- 9. PAGOS_CUOTAS — plan de pagos normalizado (requisito 3)
--     numero_cuota = 0  ->  UPFRONT (cash collected el dia del cierre).
--     numero_cuota >= 1 ->  A/R proyectado.
--     Invariante: SUM(monto) == ventas.monto_total  (constraint trigger diferido)
-- ---------------------------------------------------------------------------
create table if not exists public.pagos_cuotas (
  id                uuid primary key default gen_random_uuid(),
  venta_id          uuid not null references public.ventas(id) on delete cascade,
  numero_cuota      smallint not null check (numero_cuota >= 0),
  es_upfront        boolean generated always as (numero_cuota = 0) stored,

  monto             numeric(14,2) not null check (monto >= 0),  -- 0 valido: venta 100% financiada
  currency_code     char(3) not null references public.monedas(code),
  monto_pagado      numeric(14,2) not null default 0 check (monto_pagado >= 0),

  fecha_programada  date not null,
  fecha_pagada      timestamptz,
  metodo_pago       text,
  referencia_pago   text,

  estado            public.estado_cuota not null default 'pendiente',
  version           integer not null default 1,
  origen_escritura  public.origen_escritura not null default 'formulario_humano',
  updated_by        uuid references public.usuarios(id) on delete set null,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  constraint uq_cuota_por_venta unique (venta_id, numero_cuota),
  constraint ck_pc_no_sobrepago  check (monto_pagado <= monto),
  constraint ck_pc_pagada_coherente check (
    (estado = 'pagada'  and monto_pagado = monto and fecha_pagada is not null) or
    (estado = 'parcial' and monto_pagado > 0 and monto_pagado < monto)         or
    (estado in ('pendiente','vencida','incobrable') and fecha_pagada is null)
  )
);
create index if not exists ix_pc_venta       on public.pagos_cuotas(venta_id);
create index if not exists ix_pc_programada  on public.pagos_cuotas(fecha_programada);
create index if not exists ix_pc_pagada      on public.pagos_cuotas(fecha_pagada desc) where fecha_pagada is not null;
-- Cobranza: A/R vivo. Es la consulta operativa mas frecuente despues del pipeline.
create index if not exists ix_pc_por_cobrar
  on public.pagos_cuotas(fecha_programada) where estado in ('pendiente','parcial','vencida');
create index if not exists ix_pc_upfront
  on public.pagos_cuotas(venta_id) where numero_cuota = 0;

comment on column public.ventas.fx_rate_usd is
  'Unidades de currency_code por 1 USD el dia del cierre (ej. 3950 COP/USD). Congelado.';
comment on column public.pagos_cuotas.numero_cuota is
  '0 = upfront (cash del dia del cierre). >=1 = cuota de A/R. Sin columnas duplicadas.';

-- ---------------------------------------------------------------------------
-- 10. GASTOS_MARKETING — sin esto, el scorecard NO puede calcular $CP-L, $CP-B,
--     CAC ni ROI. El ERD v2 no tenia donde vivir el AdSpend (15.4M COP acumulados
--     en el CSV) y esas metricas quedaban condenadas a Sheets a mano.
-- ---------------------------------------------------------------------------
create table if not exists public.gastos_marketing (
  id            bigint generated always as identity primary key,
  fecha         date not null,
  fuente_id     integer references public.fuentes(id) on delete restrict,
  campana       text,
  monto         numeric(14,2) not null check (monto >= 0),
  currency_code char(3) not null references public.monedas(code),
  fx_rate_usd   numeric(18,8) check (fx_rate_usd > 0),
  impresiones   bigint check (impresiones >= 0),
  clicks        bigint check (clicks >= 0),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  constraint uq_gasto_dia_campana unique (fecha, fuente_id, campana)
);
create index if not exists ix_gm_fecha on public.gastos_marketing(fecha desc);

-- ---------------------------------------------------------------------------
-- 11. ACTIVITY_LOG — trazabilidad forense (requisito 5)
--     Cambios vs v2: etapa_actual/etapa_anterior eran TEXT LIBRE. Un typo
--     ("Agendado " con espacio) rompia silenciosamente el conteo de etapas.
--     Ahora son FK estrictas a estados_lead. Tabla append-only.
-- ---------------------------------------------------------------------------
create table if not exists public.activity_log (
  id                 bigint generated always as identity primary key,
  cliente_id         uuid references public.clientes(id) on delete restrict,
  gestion_lead_id    uuid references public.gestion_leads(id) on delete restrict,
  reunion_id         uuid references public.reuniones(id) on delete restrict,
  venta_id           uuid references public.ventas(id) on delete restrict,

  evento             public.tipo_evento not null,
  estado_anterior_id integer references public.estados_lead(id) on delete restrict,
  estado_nuevo_id    integer references public.estados_lead(id) on delete restrict,

  actor_tipo         public.tipo_actor not null default 'usuario',
  actor_usuario_id   uuid references public.usuarios(id) on delete set null,
  origen_escritura   public.origen_escritura not null default 'formulario_humano',

  ultimo_msg_lead    text,
  ultimo_msg_bot     text,
  summary            text,
  payload            jsonb not null default '{}'::jsonb,
  created_at         timestamptz not null default now(),

  constraint ck_al_cambio_estado check (
    evento <> 'cambio_estado' or estado_nuevo_id is not null
  ),
  constraint ck_al_ancla check (
    cliente_id is not null or gestion_lead_id is not null or venta_id is not null
  )
);
create index if not exists ix_al_lead_fecha  on public.activity_log(gestion_lead_id, created_at desc);
create index if not exists ix_al_cliente     on public.activity_log(cliente_id, created_at desc);
create index if not exists ix_al_evento      on public.activity_log(evento, created_at desc);
-- BRIN: la tabla crece ~2k filas/dia (100 leads x eventos). Ordenada por tiempo
-- de forma natural, BRIN cuesta KB en vez de MB para los barridos por rango.
create index if not exists ix_al_created_brin on public.activity_log using brin(created_at);
create index if not exists ix_al_payload      on public.activity_log using gin(payload);
comment on table public.activity_log is
  'Append-only. A ~730k filas/ano, particionar por rango mensual cuando pase de 20M.';

-- ---------------------------------------------------------------------------
-- 12. AUDITORIA_CAMBIOS — diff a nivel fila para las tablas sensibles.
--     Responde "quien cambio el closer de este lead a las 3am" sin depender de
--     que la aplicacion se haya acordado de loguearlo.
-- ---------------------------------------------------------------------------
create table if not exists public.auditoria_cambios (
  id           bigint generated always as identity primary key,
  tabla        text not null,
  registro_id  text not null,
  operacion    char(1) not null check (operacion in ('I','U','D')),
  campos       text[],
  datos_antes  jsonb,
  datos_despues jsonb,
  db_role      text not null default current_user,
  auth_uid     uuid,
  created_at   timestamptz not null default now()
);
create index if not exists ix_au_tabla_reg  on public.auditoria_cambios(tabla, registro_id, created_at desc);
create index if not exists ix_au_created_brin on public.auditoria_cambios using brin(created_at);

-- ===========================================================================
-- 13. FUNCIONES Y TRIGGERS
-- ===========================================================================

-- 13.0 Helpers de identidad. auth.uid() es NULL cuando escribe la service_role
--      (el Worker de IA), asi que se envuelve para no romper triggers.
create or replace function public.fn_auth_uid() returns uuid
language plpgsql stable security definer set search_path = '' as $$
begin
  return auth.uid();
exception when others then
  return null;
end $$;

create or replace function public.fn_usuario_id() returns uuid
language sql stable security definer set search_path = '' as $$
  select u.id from public.usuarios u
  where u.auth_user_id = public.fn_auth_uid() and u.activo
$$;

create or replace function public.fn_tiene_rol(p_rol public.app_rol) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.usuario_roles r
    join public.usuarios u on u.id = r.usuario_id
    where u.auth_user_id = public.fn_auth_uid() and u.activo and r.rol = p_rol
  )
$$;

create or replace function public.fn_es_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select public.fn_tiene_rol('admin') or public.fn_tiene_rol('analista')
$$;

-- ---------------------------------------------------------------------------
-- 13.1 OPTIMISTIC LOCKING (requisito 4)
--      Contrato con la aplicacion:
--        UPDATE ... SET version = <version_leida>, <campos...> WHERE id = ...
--      · Si otro actor escribio entremedio, la version del registro ya subio y
--        la que envia el cliente queda desfasada -> se aborta con SQLSTATE
--        40001, que PostgREST devuelve como HTTP 409. El Formulario lo traduce
--        a "otro usuario edito este lead, recarga".
--      · Advertencia honesta: si el cliente OMITE la columna version, PostgREST
--        no la incluye en el UPDATE y NEW.version = OLD.version, indistinguible
--        de una escritura limpia. La proteccion exige que el cliente ENVIE la
--        version que leyo. Es obligatorio en el Formulario y en el Worker IA.
-- ---------------------------------------------------------------------------

-- Para catalogos y tablas sin control de concurrencia.
create or replace function public.fn_touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.created_at := old.created_at;   -- created_at es inmutable
  new.updated_at := now();
  return new;
end $$;

-- Para tablas con columna `version`.
create or replace function public.fn_touch_versioned() returns trigger
language plpgsql as $$
begin
  new.created_at := old.created_at;
  new.updated_at := now();

  if new.version is distinct from old.version then
    raise exception
      'CONFLICTO_CONCURRENCIA en %.% (id=%): version enviada %, version actual %',
      tg_table_schema, tg_table_name, old.id, new.version, old.version
      using errcode = '40001',
            hint = 'Recarga el registro y reintenta la escritura.';
  end if;

  new.version := old.version + 1;
  return new;
end $$;

-- ---------------------------------------------------------------------------
-- 13.2 INMUTABILIDAD DE VENTAS (requisito 1)
-- ---------------------------------------------------------------------------
create or replace function public.fn_append_only() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception
      '% es append-only: DELETE prohibido. Registra un ajuste en venta_ajustes.',
      tg_table_name using errcode = '42501';
  end if;
  raise exception
    '% es inmutable: UPDATE prohibido (intento sobre id=%). '
    'Las correcciones se registran como fila nueva en venta_ajustes.',
    tg_table_name, old.id using errcode = '42501';
end $$;

-- ---------------------------------------------------------------------------
-- 13.3 INVARIANTE DEL PLAN DE PAGOS (requisito 3)
--      SUM(cuotas) = venta.monto_total, existe cuota 0, misma moneda.
--      Constraint trigger DIFERIDO: permite insertar venta + cuotas en una
--      sola transaccion sin violar el invariante a mitad de camino.
-- ---------------------------------------------------------------------------
create or replace function public.fn_check_plan_pagos(p_venta uuid) returns void
language plpgsql as $$
declare
  v_total numeric; v_cur char(3); v_plan numeric; v_n integer; v_tiene_upfront boolean;
begin
  select monto_total, currency_code into v_total, v_cur
  from public.ventas where id = p_venta;
  if not found then return; end if;

  select coalesce(sum(monto), 0), count(*), coalesce(bool_or(numero_cuota = 0), false)
    into v_plan, v_n, v_tiene_upfront
  from public.pagos_cuotas where venta_id = p_venta;

  if v_n = 0 or not v_tiene_upfront then
    raise exception
      'Venta % sin cuota 0 (upfront). Toda venta necesita su plan de pagos, '
      'aunque el upfront sea 100%% del contrato.', p_venta using errcode = '23514';
  end if;
  if v_plan <> v_total then
    raise exception
      'DESCUADRE venta %: plan de pagos = %, monto_total = %. Diferencia = %.',
      p_venta, v_plan, v_total, (v_total - v_plan) using errcode = '23514';
  end if;
  if exists (select 1 from public.pagos_cuotas
             where venta_id = p_venta and currency_code <> v_cur) then
    raise exception 'Venta %: hay cuotas en moneda distinta a la venta (%).',
      p_venta, v_cur using errcode = '23514';
  end if;
end $$;

create or replace function public.fn_trg_plan_pagos_cuotas() returns trigger
language plpgsql as $$
begin
  perform public.fn_check_plan_pagos(coalesce(new.venta_id, old.venta_id));
  return null;
end $$;

create or replace function public.fn_trg_plan_pagos_venta() returns trigger
language plpgsql as $$
begin
  perform public.fn_check_plan_pagos(new.id);
  return null;
end $$;

-- ---------------------------------------------------------------------------
-- 13.4 MOTOR DE ETAPAS EN POSTGRES (criterio de experto)
--      En el v2 esto vivia en Apps Script (etapaDeLead_). Un motor de estados
--      en la capa de aplicacion solo es valido si TODA escritura pasa por ahi;
--      con dos escritores (Worker IA + Formulario) mas importaciones manuales,
--      eso es falso. Aqui la maquina de estados es un invariante de la BD:
--      valida la transicion y sincroniza cerrado_at (que alimenta el unique
--      index parcial del requisito 2).
-- ---------------------------------------------------------------------------
create or replace function public.fn_motor_etapas() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_terminal boolean;
  v_rol      public.app_rol;
begin
  if tg_op = 'UPDATE' and new.estado_id is distinct from old.estado_id then
    select t.requiere_rol into v_rol
    from public.estado_transiciones t
    where t.estado_origen_id = old.estado_id
      and t.estado_destino_id = new.estado_id;

    if not found then
      raise exception 'TRANSICION_INVALIDA: % -> % (gestion_lead %)',
        (select codigo from public.estados_lead where id = old.estado_id),
        (select codigo from public.estados_lead where id = new.estado_id),
        old.id
        using errcode = '23514',
              hint = 'Transiciones permitidas en public.estado_transiciones.';
    end if;

    -- Transiciones sensibles (ej. -> ganado) pueden exigir un rol concreto.
    if v_rol is not null
       and public.fn_auth_uid() is not null
       and not public.fn_es_admin()
       and not public.fn_tiene_rol(v_rol) then
      raise exception 'La transicion a "%" requiere el rol %',
        (select codigo from public.estados_lead where id = new.estado_id), v_rol
        using errcode = '42501';
    end if;
  end if;

  select es_terminal into v_terminal from public.estados_lead where id = new.estado_id;
  if v_terminal then
    new.cerrado_at := coalesce(new.cerrado_at, now());
  else
    new.cerrado_at := null;   -- reapertura: vuelve a competir por el unique parcial
  end if;
  return new;
end $$;

-- Avance automatico de etapa disparado por hechos (reunion creada, venta creada).
-- SECURITY DEFINER: un setter que agenda debe poder mover el estado de un lead
-- que ya esta en manos del closer. Se revoca EXECUTE a `authenticated` al final
-- del script para que no sea un bypass del motor llamable desde el cliente.
-- FOR UPDATE serializa Worker IA contra Formulario humano sobre la misma fila.
create or replace function public.fn_avanzar_estado(p_gestion uuid, p_codigo text)
returns boolean language plpgsql security definer set search_path = '' as $$
declare v_destino integer; v_actual integer;
begin
  select id into v_destino from public.estados_lead where codigo = p_codigo and activo;
  if v_destino is null then return false; end if;

  select estado_id into v_actual from public.gestion_leads where id = p_gestion for update;
  if v_actual is null or v_actual = v_destino then return false; end if;

  -- Si la transicion no esta en la whitelist NO se fuerza: el estado registrado
  -- por un humano gana sobre la inferencia automatica.
  if not exists (select 1 from public.estado_transiciones
                 where estado_origen_id = v_actual and estado_destino_id = v_destino) then
    return false;
  end if;

  update public.gestion_leads
     set estado_id = v_destino, version = version
   where id = p_gestion;
  return true;
end $$;

create or replace function public.fn_reunion_mueve_etapa() returns trigger
language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    perform public.fn_avanzar_estado(new.gestion_lead_id, 'agendado');
  elsif new.estado is distinct from old.estado then
    if new.estado = 'realizada'  then perform public.fn_avanzar_estado(new.gestion_lead_id, 'show_up'); end if;
    if new.estado = 'no_show'    then perform public.fn_avanzar_estado(new.gestion_lead_id, 'no_show'); end if;
  end if;
  if new.oferta_presentada and (tg_op = 'INSERT' or not old.oferta_presentada) then
    perform public.fn_avanzar_estado(new.gestion_lead_id, 'oferta_presentada');
  end if;
  return null;
end $$;

create or replace function public.fn_venta_cierra_lead() returns trigger
language plpgsql as $$
begin
  perform public.fn_avanzar_estado(new.gestion_lead_id, 'ganado');
  return null;
end $$;

-- ---------------------------------------------------------------------------
-- 13.5 ACTIVITY_LOG automatico con FK estrictas (requisito 5)
-- ---------------------------------------------------------------------------
create or replace function public.fn_log_gestion() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    insert into public.activity_log
      (cliente_id, gestion_lead_id, evento, estado_nuevo_id,
       actor_tipo, actor_usuario_id, origen_escritura, summary)
    values (new.cliente_id, new.id, 'creacion', new.estado_id,
            case when new.origen_escritura = 'worker_ia' then 'bot' else 'usuario' end,
            coalesce(new.updated_by, public.fn_usuario_id()), new.origen_escritura,
            'Lead creado en pipeline');
    return null;
  end if;

  if new.estado_id is distinct from old.estado_id then
    insert into public.activity_log
      (cliente_id, gestion_lead_id, evento, estado_anterior_id, estado_nuevo_id,
       actor_tipo, actor_usuario_id, origen_escritura, summary)
    values (new.cliente_id, new.id, 'cambio_estado', old.estado_id, new.estado_id,
            case when new.origen_escritura = 'worker_ia' then 'bot' else 'usuario' end,
            coalesce(new.updated_by, public.fn_usuario_id()), new.origen_escritura,
            format('Etapa %s -> %s',
              (select codigo from public.estados_lead where id = old.estado_id),
              (select codigo from public.estados_lead where id = new.estado_id)));
  end if;

  if new.closer_id is distinct from old.closer_id then
    insert into public.activity_log
      (cliente_id, gestion_lead_id, evento, estado_nuevo_id, actor_tipo,
       actor_usuario_id, origen_escritura, summary, payload)
    values (new.cliente_id, new.id, 'asignacion', new.estado_id, 'usuario',
            coalesce(new.updated_by, public.fn_usuario_id()), new.origen_escritura,
            'Reasignacion de closer',
            jsonb_build_object('closer_anterior', old.closer_id, 'closer_nuevo', new.closer_id));
  end if;
  return null;
end $$;

create or replace function public.fn_log_venta() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.activity_log
    (cliente_id, gestion_lead_id, reunion_id, venta_id, evento,
     actor_tipo, actor_usuario_id, origen_escritura, summary, payload)
  values (new.cliente_id, new.gestion_lead_id, new.reunion_id, new.id, 'venta',
          'usuario', coalesce(new.created_by, public.fn_usuario_id()), new.origen_escritura,
          format('Venta cerrada por %s %s', new.monto_total, new.currency_code),
          jsonb_build_object('monto_total', new.monto_total,
                             'currency_code', new.currency_code,
                             'closer_id', new.closer_id,
                             'producto', new.producto_nombre_snap));
  return null;
end $$;

create or replace function public.fn_log_pago() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'UPDATE' and new.monto_pagado <= old.monto_pagado then return null; end if;
  insert into public.activity_log
    (cliente_id, gestion_lead_id, venta_id, evento, actor_tipo,
     actor_usuario_id, origen_escritura, summary, payload)
  select v.cliente_id, v.gestion_lead_id, v.id, 'pago', 'usuario',
         coalesce(new.updated_by, public.fn_usuario_id()), new.origen_escritura,
         format('Cuota %s: %s %s', new.numero_cuota, new.monto_pagado, new.currency_code),
         jsonb_build_object('numero_cuota', new.numero_cuota,
                            'es_upfront', new.numero_cuota = 0,
                            'monto_pagado', new.monto_pagado,
                            'estado', new.estado)
  from public.ventas v where v.id = new.venta_id;
  return null;
end $$;

-- ---------------------------------------------------------------------------
-- 13.6 AISLAMIENTO DE COLUMNAS POR ROL (requisito 4)
--      Reemplaza el "fingerprint + LockService" de Apps Script (D4 del doc de
--      arquitectura). RLS controla QUE FILAS ve cada rol; este trigger controla
--      QUE COLUMNAS puede escribir. Postgres no tiene column-level security
--      combinable con RLS de forma practica via PostgREST, asi que se resuelve
--      con un trigger que compara el diff real de la fila.
-- ---------------------------------------------------------------------------
create or replace function public.fn_columnas_por_rol() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_comunes text[] := array['estado_id','notas','updated_at','version','updated_by','origen_escritura','cerrado_at'];
  v_setter  text[] := array['setter_id','dolor','urgencia','califica','fecha_atendido',
                            'fecha_calificacion','handoff_razon','fecha_handoff','fuente_id',
                            'palabra_clave_ad','campana','utm_source','utm_campaign',
                            'producto_interes_id','closer_id'];
  v_closer  text[] := array['closer_id','producto_interes_id','fecha_atendido'];
  v_permitidas text[] := array[]::text[];
  v_invasoras  text[];
begin
  -- Escrituras de la service_role (Worker IA, Bridge, migraciones) no tienen
  -- JWT de usuario: se auditan pero no se restringen por columna.
  if public.fn_auth_uid() is null or public.fn_es_admin() then
    return new;
  end if;

  if public.fn_tiene_rol('setter') then v_permitidas := v_permitidas || v_setter; end if;
  if public.fn_tiene_rol('closer') then v_permitidas := v_permitidas || v_closer; end if;
  if cardinality(v_permitidas) = 0 then
    raise exception 'Usuario sin rol operativo no puede modificar gestion_leads.'
      using errcode = '42501';
  end if;
  v_permitidas := v_permitidas || v_comunes;

  select array_agg(n.key order by n.key) into v_invasoras
  from jsonb_each(to_jsonb(new)) n
  where n.value is distinct from (to_jsonb(old) -> n.key)
    and not (n.key = any (v_permitidas));

  if v_invasoras is not null then
    raise exception 'Rol sin permiso de escritura sobre: %', array_to_string(v_invasoras, ', ')
      using errcode = '42501',
            hint = 'Setter y Closer escriben columnas disjuntas por diseno.';
  end if;
  return new;
end $$;

-- ---------------------------------------------------------------------------
-- 13.7 Estado derivado de la cuota. Elimina el estado_cuota escrito a mano
--      (fuente clasica de "cuota pagada con monto_pagado = 0").
-- ---------------------------------------------------------------------------
create or replace function public.fn_sync_estado_cuota() returns trigger
language plpgsql as $$
begin
  if new.estado = 'incobrable' then
    new.fecha_pagada := null;
    return new;
  end if;
  if new.monto_pagado >= new.monto then
    new.estado := 'pagada';
    new.fecha_pagada := coalesce(new.fecha_pagada, now());
  elsif new.monto_pagado > 0 then
    new.estado := 'parcial';
  elsif new.fecha_programada < (now() at time zone public.fn_tz())::date then
    new.estado := 'vencida';
    new.fecha_pagada := null;
  else
    new.estado := 'pendiente';
    new.fecha_pagada := null;
  end if;
  return new;
end $$;

-- ---------------------------------------------------------------------------
-- 13.8 Auditoria generica fila-a-fila
-- ---------------------------------------------------------------------------
create or replace function public.fn_auditar() returns trigger
language plpgsql security definer set search_path = '' as $$
declare v_antes jsonb; v_despues jsonb; v_campos text[];
begin
  v_antes   := case when tg_op = 'INSERT' then null else to_jsonb(old) end;
  v_despues := case when tg_op = 'DELETE' then null else to_jsonb(new) end;
  if tg_op = 'UPDATE' then
    select array_agg(n.key order by n.key) into v_campos
    from jsonb_each(v_despues) n
    where n.value is distinct from (v_antes -> n.key) and n.key <> 'updated_at';
    if v_campos is null then return null; end if;
  end if;
  insert into public.auditoria_cambios
    (tabla, registro_id, operacion, campos, datos_antes, datos_despues, auth_uid)
  values (tg_table_name,
          -- usuario_roles no tiene columna id (PK compuesta): se cae al PK real.
          coalesce(v_despues ->> 'id',       v_antes ->> 'id',
                   v_despues ->> 'usuario_id', v_antes ->> 'usuario_id',
                   'sin_id'),
          left(tg_op, 1), v_campos, v_antes, v_despues, public.fn_auth_uid());
  return null;
end $$;

-- ===========================================================================
-- 14. CABLEADO DE TRIGGERS
-- ===========================================================================
do $$
declare t text;
begin
  -- updated_at en todas las tablas mutables (requisito 5)
  foreach t in array array['fuentes','productos','estados_lead','gastos_marketing','venta_ajustes'] loop
    execute format('drop trigger if exists trg_touch on public.%I', t);
    execute format('create trigger trg_touch before update on public.%I
                    for each row execute function public.fn_touch_updated_at()', t);
  end loop;

  -- Tablas con optimistic locking
  foreach t in array array['usuarios','clientes','gestion_leads','reuniones','pagos_cuotas'] loop
    execute format('drop trigger if exists trg_touch on public.%I', t);
    execute format('create trigger trg_touch before update on public.%I
                    for each row execute function public.fn_touch_versioned()', t);
  end loop;

  -- Auditoria forense
  foreach t in array array['gestion_leads','ventas','pagos_cuotas','venta_ajustes','usuarios','usuario_roles'] loop
    execute format('drop trigger if exists trg_auditar on public.%I', t);
    execute format('create trigger trg_auditar after insert or update or delete on public.%I
                    for each row execute function public.fn_auditar()', t);
  end loop;
end $$;

-- VENTAS: inmutable (requisito 1)
drop trigger if exists trg_ventas_inmutable on public.ventas;
create trigger trg_ventas_inmutable
  before update or delete on public.ventas
  for each row execute function public.fn_append_only();

-- ACTIVITY_LOG: append-only
drop trigger if exists trg_log_inmutable on public.activity_log;
create trigger trg_log_inmutable
  before update or delete on public.activity_log
  for each row execute function public.fn_append_only();

-- Motor de etapas + aislamiento por rol en GESTION_LEADS
drop trigger if exists trg_gl_columnas on public.gestion_leads;
create trigger trg_gl_columnas before update on public.gestion_leads
  for each row execute function public.fn_columnas_por_rol();

drop trigger if exists trg_gl_motor on public.gestion_leads;
create trigger trg_gl_motor before insert or update on public.gestion_leads
  for each row execute function public.fn_motor_etapas();

drop trigger if exists trg_gl_log on public.gestion_leads;
create trigger trg_gl_log after insert or update on public.gestion_leads
  for each row execute function public.fn_log_gestion();

-- Hechos que mueven la etapa
drop trigger if exists trg_re_etapa on public.reuniones;
create trigger trg_re_etapa after insert or update on public.reuniones
  for each row execute function public.fn_reunion_mueve_etapa();

drop trigger if exists trg_ve_etapa on public.ventas;
create trigger trg_ve_etapa after insert on public.ventas
  for each row execute function public.fn_venta_cierra_lead();

drop trigger if exists trg_ve_log on public.ventas;
create trigger trg_ve_log after insert on public.ventas
  for each row execute function public.fn_log_venta();

-- Cuotas
drop trigger if exists trg_pc_estado on public.pagos_cuotas;
create trigger trg_pc_estado before insert or update on public.pagos_cuotas
  for each row execute function public.fn_sync_estado_cuota();

drop trigger if exists trg_pc_log on public.pagos_cuotas;
create trigger trg_pc_log after insert or update on public.pagos_cuotas
  for each row execute function public.fn_log_pago();

-- Invariante del plan de pagos (DIFERIDO al COMMIT)
drop trigger if exists trg_pc_plan on public.pagos_cuotas;
create constraint trigger trg_pc_plan
  after insert or update or delete on public.pagos_cuotas
  deferrable initially deferred
  for each row execute function public.fn_trg_plan_pagos_cuotas();

drop trigger if exists trg_ve_plan on public.ventas;
create constraint trigger trg_ve_plan
  after insert on public.ventas
  deferrable initially deferred
  for each row execute function public.fn_trg_plan_pagos_venta();

-- ===========================================================================
-- 15. ROW LEVEL SECURITY (requisito 4)
--
--   Matriz de proteccion:
--   ┌──────────────────┬─────────┬──────────────────────┬──────────────────────┐
--   │ Tabla            │ Admin   │ Setter               │ Closer               │
--   ├──────────────────┼─────────┼──────────────────────┼──────────────────────┤
--   │ clientes         │ RW      │ RW (los que trabaja) │ R (los que trabaja)  │
--   │ gestion_leads    │ RW      │ RW donde setter_id=el│ RW donde closer_id=el│
--   │ reuniones        │ RW      │ R de sus leads       │ RW donde closer_id=el│
--   │ ventas           │ RW ins  │ R de sus leads       │ INSERT + R propias   │
--   │ pagos_cuotas     │ RW      │ -                    │ R/U de sus ventas    │
--   │ venta_ajustes    │ RW      │ -                    │ R                    │
--   │ activity_log     │ R       │ R de sus leads       │ R de sus leads       │
--   │ auditoria_cambios│ R       │ -                    │ -                    │
--   │ gastos_marketing │ RW      │ -                    │ -                    │
--   │ catalogos        │ RW      │ R                    │ R                    │
--   └──────────────────┴─────────┴──────────────────────┴──────────────────────┘
--   Nota: la service_role del Worker IA hace BYPASSRLS. Su trazabilidad no
--   depende de RLS sino de origen_escritura + auditoria_cambios.
-- ===========================================================================
alter table public.usuarios          enable row level security;
alter table public.usuario_roles     enable row level security;
alter table public.clientes          enable row level security;
alter table public.gestion_leads     enable row level security;
alter table public.reuniones         enable row level security;
alter table public.ventas            enable row level security;
alter table public.venta_ajustes     enable row level security;
alter table public.pagos_cuotas      enable row level security;
alter table public.activity_log      enable row level security;
alter table public.auditoria_cambios enable row level security;
alter table public.gastos_marketing  enable row level security;
alter table public.monedas           enable row level security;
alter table public.tasas_cambio      enable row level security;
alter table public.fuentes           enable row level security;
alter table public.productos         enable row level security;
alter table public.estados_lead      enable row level security;
alter table public.estado_transiciones enable row level security;

-- 15.0 Idempotencia: el script debe poder re-ejecutarse. CREATE POLICY no
--      acepta IF NOT EXISTS, asi que se limpian primero las policies del schema.
do $$
declare p record;
begin
  for p in select policyname, tablename from pg_policies where schemaname = 'public' loop
    execute format('drop policy if exists %I on public.%I', p.policyname, p.tablename);
  end loop;
end $$;

-- 15.1 Catalogos: lectura para todo autenticado, escritura solo admin.
do $$
declare t text;
begin
  foreach t in array array['monedas','tasas_cambio','fuentes','productos',
                           'estados_lead','estado_transiciones'] loop
    execute format('drop policy if exists pol_%s_read on public.%I', t, t);
    execute format('create policy pol_%s_read on public.%I for select to authenticated using (true)', t, t);
    execute format('drop policy if exists pol_%s_admin on public.%I', t, t);
    execute format('create policy pol_%s_admin on public.%I for all to authenticated
                    using (public.fn_es_admin()) with check (public.fn_es_admin())', t, t);
  end loop;
end $$;

-- 15.2 Usuarios: cada quien se ve a si mismo; el equipo se ve para asignaciones.
create policy pol_usuarios_read on public.usuarios
  for select to authenticated using (true);
create policy pol_usuarios_self on public.usuarios
  for update to authenticated
  using (auth_user_id = public.fn_auth_uid() or public.fn_es_admin())
  with check (auth_user_id = public.fn_auth_uid() or public.fn_es_admin());
create policy pol_usuarios_admin on public.usuarios
  for all to authenticated using (public.fn_es_admin()) with check (public.fn_es_admin());

create policy pol_roles_read on public.usuario_roles
  for select to authenticated using (true);
create policy pol_roles_admin on public.usuario_roles
  for all to authenticated using (public.fn_es_admin()) with check (public.fn_es_admin());

-- 15.3 Predicado central: "este lead es mio".
create or replace function public.fn_lead_es_mio(p_gestion uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.gestion_leads g
    where g.id = p_gestion
      and (public.fn_es_admin()
           or g.setter_id = public.fn_usuario_id()
           or g.closer_id = public.fn_usuario_id())
  )
$$;

-- 15.4 GESTION_LEADS. Los setters ven la cola sin asignar (para tomarla);
--      los closers solo ven lo suyo mas lo calificado sin closer (cola de handoff).
create policy pol_gl_select on public.gestion_leads
  for select to authenticated using (
    public.fn_es_admin()
    or setter_id = public.fn_usuario_id()
    or closer_id = public.fn_usuario_id()
    or (public.fn_tiene_rol('setter') and setter_id is null)
    or (public.fn_tiene_rol('closer') and closer_id is null and califica is true)
  );

create policy pol_gl_insert on public.gestion_leads
  for insert to authenticated with check (
    public.fn_es_admin() or public.fn_tiene_rol('setter')
  );

create policy pol_gl_update on public.gestion_leads
  for update to authenticated
  using (
    public.fn_es_admin()
    or setter_id = public.fn_usuario_id()
    or closer_id = public.fn_usuario_id()
    or (public.fn_tiene_rol('setter') and setter_id is null)
    or (public.fn_tiene_rol('closer') and closer_id is null and califica is true)
  )
  with check (
    public.fn_es_admin()
    or setter_id = public.fn_usuario_id()
    or closer_id = public.fn_usuario_id()
  );
-- Sin policy de DELETE: nadie borra pipeline. Se cierra con estado terminal.

-- 15.5 CLIENTES. Se ven solo los que el usuario esta trabajando.
create policy pol_cli_select on public.clientes
  for select to authenticated using (
    public.fn_es_admin()
    or exists (
      select 1 from public.gestion_leads g
      where g.cliente_id = clientes.id
        and (g.setter_id = public.fn_usuario_id() or g.closer_id = public.fn_usuario_id())
    )
  );
create policy pol_cli_insert on public.clientes
  for insert to authenticated with check (
    public.fn_es_admin() or public.fn_tiene_rol('setter')
  );
create policy pol_cli_update on public.clientes
  for update to authenticated
  using (
    public.fn_es_admin()
    or exists (
      select 1 from public.gestion_leads g
      where g.cliente_id = clientes.id
        and g.setter_id = public.fn_usuario_id()
        and g.cerrado_at is null
    )
  )
  with check (true);

-- 15.6 REUNIONES: el closer manda; el setter mira.
create policy pol_re_select on public.reuniones
  for select to authenticated using (public.fn_lead_es_mio(gestion_lead_id));
create policy pol_re_insert on public.reuniones
  for insert to authenticated with check (
    public.fn_lead_es_mio(gestion_lead_id)
    and (public.fn_es_admin() or public.fn_tiene_rol('closer') or public.fn_tiene_rol('setter'))
  );
create policy pol_re_update on public.reuniones
  for update to authenticated
  using (public.fn_es_admin() or closer_id = public.fn_usuario_id())
  with check (public.fn_es_admin() or closer_id = public.fn_usuario_id());

-- 15.7 VENTAS: INSERT + SELECT. UPDATE/DELETE ya estan bloqueados por trigger;
--      la ausencia de policy los bloquea tambien a nivel RLS (defensa en capas).
create policy pol_ve_select on public.ventas
  for select to authenticated using (
    public.fn_es_admin()
    or closer_id = public.fn_usuario_id()
    or setter_id = public.fn_usuario_id()
  );
create policy pol_ve_insert on public.ventas
  for insert to authenticated with check (
    public.fn_es_admin()
    or (public.fn_tiene_rol('closer') and closer_id = public.fn_usuario_id())
  );

create policy pol_aj_select on public.venta_ajustes
  for select to authenticated using (
    public.fn_es_admin()
    or exists (select 1 from public.ventas v where v.id = venta_id
               and (v.closer_id = public.fn_usuario_id() or v.setter_id = public.fn_usuario_id()))
  );
create policy pol_aj_admin on public.venta_ajustes
  for all to authenticated using (public.fn_es_admin()) with check (public.fn_es_admin());

-- 15.8 PAGOS_CUOTAS: dinero. El closer marca cobros de sus ventas; nadie mas.
create policy pol_pc_select on public.pagos_cuotas
  for select to authenticated using (
    public.fn_es_admin()
    or exists (select 1 from public.ventas v where v.id = venta_id
               and (v.closer_id = public.fn_usuario_id() or v.setter_id = public.fn_usuario_id()))
  );
create policy pol_pc_insert on public.pagos_cuotas
  for insert to authenticated with check (
    public.fn_es_admin()
    or exists (select 1 from public.ventas v where v.id = venta_id
               and v.closer_id = public.fn_usuario_id())
  );
create policy pol_pc_update on public.pagos_cuotas
  for update to authenticated
  using (
    public.fn_es_admin()
    or exists (select 1 from public.ventas v where v.id = venta_id
               and v.closer_id = public.fn_usuario_id())
  )
  with check (true);

-- 15.9 Logs: lectura acotada, escritura solo por triggers (security definer).
create policy pol_al_select on public.activity_log
  for select to authenticated using (
    public.fn_es_admin()
    or (gestion_lead_id is not null and public.fn_lead_es_mio(gestion_lead_id))
  );
create policy pol_au_select on public.auditoria_cambios
  for select to authenticated using (public.fn_es_admin());
create policy pol_gm_admin on public.gastos_marketing
  for all to authenticated using (public.fn_es_admin()) with check (public.fn_es_admin());

-- ===========================================================================
-- 16. SEEDS DE CATALOGO
--     Obligatorios: sin estados_lead + estado_transiciones el motor no arranca.
-- ===========================================================================
insert into public.monedas (code, nombre, decimales) values
  ('COP','Peso colombiano',2), ('USD','Dolar estadounidense',2), ('EUR','Euro',2)
on conflict (code) do nothing;

insert into public.fuentes (codigo, nombre, canal, es_pagada) values
  ('ig_ads',    'Instagram Ads',      'instagram', true),
  ('ig_organico','Instagram organico','instagram', false),
  ('referido',  'Referido',           'referido',  false),
  ('whatsapp',  'WhatsApp directo',   'whatsapp',  false),
  ('otro',      'Otro',                null,       false)
on conflict (codigo) do nothing;

insert into public.productos (codigo, nombre, tipo, precio_lista, currency_code, duracion_dias) values
  ('core',       'Core Program',       'core',       5250000, 'COP', 180),
  ('low_ticket', 'Low Ticket Program', 'low_ticket',  500000, 'COP',  60)
on conflict (codigo) do nothing;

insert into public.estados_lead
  (codigo, nombre, categoria, orden, es_terminal, es_ganado,
   cuenta_como_booking, cuenta_como_show_up, cuenta_como_oferta) values
  ('nuevo',             'Nuevo',              'nuevo',      10, false, false, false, false, false),
  ('contactado',        'Contactado',         'contactado', 20, false, false, false, false, false),
  ('calificado',        'Calificado (SQL)',   'calificado', 30, false, false, false, false, false),
  ('agendado',          'Agendado',           'agendado',   40, false, false, true,  false, false),
  ('no_show',           'No Show',            'agendado',   45, false, false, true,  false, false),
  ('show_up',           'Show Up',            'presentado', 50, false, false, true,  true,  false),
  ('oferta_presentada', 'Oferta Presentada',  'presentado', 60, false, false, true,  true,  true),
  ('ganado',            'Ganado (Venta)',     'ganado',     70, true,  true,  true,  true,  true),
  ('perdido',           'Perdido',            'perdido',    80, true,  false, false, false, false),
  ('descalificado',     'Descalificado',      'perdido',    85, true,  false, false, false, false),
  ('nutricion',         'En nutricion',       'nutricion',  90, true,  false, false, false, false)
on conflict (codigo) do nothing;

-- Maquina de estados. Avance normal + retrocesos legitimos + salidas terminales.
insert into public.estado_transiciones (estado_origen_id, estado_destino_id)
select o.id, d.id
from (values
  ('nuevo','contactado'), ('nuevo','descalificado'), ('nuevo','perdido'),
  ('contactado','calificado'), ('contactado','descalificado'),
  ('contactado','nutricion'), ('contactado','perdido'), ('contactado','agendado'),
  ('calificado','agendado'), ('calificado','nutricion'), ('calificado','perdido'),
  ('calificado','descalificado'),
  ('agendado','show_up'), ('agendado','no_show'), ('agendado','perdido'),
  ('agendado','calificado'),
  ('no_show','agendado'), ('no_show','nutricion'), ('no_show','perdido'),
  ('show_up','oferta_presentada'), ('show_up','ganado'),
  ('show_up','perdido'), ('show_up','nutricion'), ('show_up','agendado'),
  ('oferta_presentada','ganado'), ('oferta_presentada','perdido'),
  ('oferta_presentada','nutricion'), ('oferta_presentada','agendado'),
  -- Reapertura controlada desde estados terminales no-ganados.
  ('nutricion','contactado'), ('nutricion','calificado'), ('nutricion','agendado'),
  ('perdido','contactado'), ('perdido','nutricion'),
  ('descalificado','contactado')
) as tr(origen, destino)
join public.estados_lead o on o.codigo = tr.origen
join public.estados_lead d on d.codigo = tr.destino
on conflict do nothing;

-- ===========================================================================
-- 17. RPC TRANSACCIONAL: registrar venta + plan de pagos atomicamente.
--     El upfront ES la cuota 0. La app nunca inserta ventas "sueltas": eso
--     dispararia el constraint diferido del plan de pagos al hacer COMMIT.
-- ===========================================================================
create or replace function public.fn_registrar_venta(
  p_gestion_lead_id  uuid,
  p_producto_id      integer,
  p_monto_total      numeric,
  p_currency_code    char(3),
  p_upfront          numeric,
  p_num_cuotas       smallint default 1,
  p_fecha_venta      timestamptz default now(),
  p_reunion_id       uuid default null,
  p_fx_rate_usd      numeric default null,
  p_comision_closer_pct numeric default 0,
  p_comision_setter_pct numeric default 0,
  p_dia_cuota        smallint default 30
) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
  v_gl      public.gestion_leads%rowtype;
  v_prod    public.productos%rowtype;
  v_venta   uuid;
  v_resto   numeric;
  v_cuota   numeric;
  v_ajuste  numeric;
  i         integer;
begin
  select * into v_gl from public.gestion_leads where id = p_gestion_lead_id for update;
  if not found then raise exception 'gestion_lead % inexistente', p_gestion_lead_id; end if;

  -- SECURITY DEFINER bypasea RLS: la autorizacion se valida aqui a mano.
  -- Sin esta guarda, cualquier authenticated podria facturar sobre leads ajenos.
  if public.fn_auth_uid() is not null
     and not public.fn_es_admin()
     and v_gl.closer_id is distinct from public.fn_usuario_id() then
    raise exception 'No autorizado: solo el closer asignado (o un admin) cierra este lead.'
      using errcode = '42501';
  end if;

  if v_gl.closer_id is null then
    raise exception 'No se puede registrar venta sin closer asignado (gestion_lead %). '
                    'La atribucion de comision quedaria indefinida.', p_gestion_lead_id;
  end if;
  if p_upfront < 0 or p_upfront > p_monto_total then
    raise exception 'Upfront % invalido para un total de %', p_upfront, p_monto_total;
  end if;
  if p_num_cuotas < 1 then raise exception 'num_cuotas debe ser >= 1'; end if;
  if p_upfront = 0 and p_num_cuotas = 1 then
    raise exception 'Venta sin upfront y sin cuotas: no hay plan de pagos posible.';
  end if;

  select * into v_prod from public.productos where id = p_producto_id;
  if not found then raise exception 'producto % inexistente', p_producto_id; end if;

  insert into public.ventas (
    gestion_lead_id, reunion_id, cliente_id, closer_id, setter_id, fuente_id,
    producto_id, producto_nombre_snap, comision_closer_pct, comision_setter_pct,
    fecha_venta, monto_total, currency_code, fx_rate_usd,
    forma_pago, num_cuotas_pactadas, fecha_inicio_programa, fecha_fin_programa,
    origen_escritura, created_by
  ) values (
    v_gl.id, p_reunion_id, v_gl.cliente_id, v_gl.closer_id, v_gl.setter_id, v_gl.fuente_id,
    v_prod.id, v_prod.nombre, p_comision_closer_pct, p_comision_setter_pct,
    p_fecha_venta, p_monto_total, p_currency_code,
    coalesce(p_fx_rate_usd, (select tasa from public.tasas_cambio
                             where moneda_origen = p_currency_code and moneda_destino = 'USD'
                               and fecha <= p_fecha_venta::date
                             order by fecha desc limit 1)),
    case when p_upfront >= p_monto_total then 'contado'
         when p_upfront = 0 then 'cuotas' else 'mixto' end,
    p_num_cuotas,
    (p_fecha_venta at time zone public.fn_tz())::date,
    (p_fecha_venta at time zone public.fn_tz())::date + coalesce(v_prod.duracion_dias, 180),
    'formulario_humano', v_gl.closer_id
  ) returning id into v_venta;

  -- Cuota 0 = upfront. Siempre existe, incluso si es 0 (venta 100% financiada):
  -- su presencia es lo que hace que el A/R y el cash tengan la misma raiz.
  insert into public.pagos_cuotas
    (venta_id, numero_cuota, monto, currency_code, monto_pagado,
     fecha_programada, fecha_pagada, estado)
  values (v_venta, 0, p_upfront, p_currency_code, p_upfront,
          (p_fecha_venta at time zone public.fn_tz())::date,
          case when p_upfront > 0 then p_fecha_venta end,
          'pagada');

  -- Saldo repartido en cuotas 1..N-1. La ultima absorbe el redondeo para que
  -- SUM(cuotas) = monto_total EXACTO (el constraint diferido no perdona centavos).
  v_resto := p_monto_total - p_upfront;
  if p_num_cuotas > 1 and v_resto > 0 then
    v_cuota := round(v_resto / (p_num_cuotas - 1), 2);
    for i in 1 .. (p_num_cuotas - 1) loop
      v_ajuste := case when i = p_num_cuotas - 1
                       then v_resto - (v_cuota * (p_num_cuotas - 2)) else v_cuota end;
      insert into public.pagos_cuotas
        (venta_id, numero_cuota, monto, currency_code, fecha_programada, estado)
      values (v_venta, i, v_ajuste, p_currency_code,
              (p_fecha_venta at time zone public.fn_tz())::date + (i * p_dia_cuota),
              'pendiente');
    end loop;
  elsif v_resto > 0 then
    raise exception 'Saldo de % sin cuotas donde alojarlo. Aumenta p_num_cuotas.', v_resto;
  end if;

  return v_venta;
end $$;

comment on function public.fn_registrar_venta is
  'Unico punto de entrada para cerrar ventas. Garantiza venta + plan de pagos en una transaccion.';

-- ===========================================================================
-- 18. VISTAS
--     security_invoker = on: las vistas RESPETAN el RLS de quien consulta.
--     Sin esto, cualquier setter leeria el revenue completo de la empresa a
--     traves de la vista (agujero clasico de RLS en Supabase).
-- ===========================================================================

-- 18.1 Venta con su dinero real (neto de ajustes) y su cash cobrado.
create or replace view public.vw_ventas_neto
with (security_invoker = on) as
select
  v.id                    as venta_id,
  v.gestion_lead_id,
  v.cliente_id,
  v.closer_id,
  v.setter_id,
  v.producto_id,
  v.producto_nombre_snap,
  v.fuente_id,
  v.fecha_venta,
  (v.fecha_venta at time zone public.fn_tz())::date as fecha_venta_local,
  v.currency_code,
  v.monto_total                                        as revenue_bruto,
  coalesce(aj.total_ajustes, 0)                        as ajustes,
  v.monto_total + coalesce(aj.total_ajustes, 0)        as revenue_neto,
  coalesce(pc.upfront_programado, 0)                   as upfront_programado,
  coalesce(pc.upfront_cobrado, 0)                      as upfront_cobrado,
  coalesce(pc.plan_total, 0)                           as plan_total,
  coalesce(pc.cash_cobrado, 0)                         as cash_cobrado,
  coalesce(pc.ar_pendiente, 0)                         as ar_pendiente,
  coalesce(pc.ar_vencido, 0)                           as ar_vencido,
  v.comision_closer_pct,
  round((v.monto_total + coalesce(aj.total_ajustes,0)) * v.comision_closer_pct / 100, 2) as comision_closer,
  round((v.monto_total + coalesce(aj.total_ajustes,0)) * v.comision_setter_pct / 100, 2) as comision_setter
from public.ventas v
left join lateral (
  select sum(a.monto) as total_ajustes
  from public.venta_ajustes a where a.venta_id = v.id
) aj on true
left join lateral (
  select
    sum(p.monto)                                                     as plan_total,
    sum(p.monto_pagado)                                              as cash_cobrado,
    sum(p.monto) filter (where p.numero_cuota = 0)                   as upfront_programado,
    sum(p.monto_pagado) filter (where p.numero_cuota = 0)            as upfront_cobrado,
    sum(p.monto - p.monto_pagado) filter (where p.estado <> 'incobrable') as ar_pendiente,
    sum(p.monto - p.monto_pagado) filter (where p.estado = 'vencida')     as ar_vencido
  from public.pagos_cuotas p where p.venta_id = v.id
) pc on true;

-- 18.2 Embudo diario. Un solo pase por dia con todas las metricas del EOS.
create or replace view public.vw_embudo_diario
with (security_invoker = on) as
with dias as (
  select generate_series(
    least(
      coalesce((select min(fecha_contacto at time zone public.fn_tz())::date from public.gestion_leads),
               current_date),
      current_date - 90),
    current_date, interval '1 day')::date as dia
),
leads as (
  select (fecha_contacto at time zone public.fn_tz())::date as dia,
         count(*) as leads,
         count(*) filter (where califica) as calificados
  from public.gestion_leads group by 1
),
book as (
  select (fecha_agendamiento at time zone public.fn_tz())::date as dia,
         count(*) as bookings
  from public.reuniones group by 1
),
shows as (
  select (fecha_realizada at time zone public.fn_tz())::date as dia,
         count(*) filter (where estado = 'realizada')      as show_ups,
         count(*) filter (where oferta_presentada)         as ofertas
  from public.reuniones where fecha_realizada is not null group by 1
),
noshow as (
  select (fecha_programada at time zone public.fn_tz())::date as dia,
         count(*) as no_shows
  from public.reuniones where estado = 'no_show' group by 1
),
vtas as (
  select fecha_venta_local as dia,
         count(*)                as ventas,
         sum(revenue_neto)       as revenue,
         sum(upfront_cobrado)    as upfront,
         sum(revenue_neto - upfront_cobrado) as ar_nuevo
  from public.vw_ventas_neto group by 1
),
cash as (
  select (fecha_pagada at time zone public.fn_tz())::date as dia,
         sum(monto_pagado)                                   as cash_total,
         sum(monto_pagado) filter (where numero_cuota > 0)   as cash_cuotas
  from public.pagos_cuotas where fecha_pagada is not null group by 1
),
spend as (
  select fecha as dia, sum(monto) as adspend from public.gastos_marketing group by 1
)
select
  d.dia,
  coalesce(l.leads, 0)        as leads,
  coalesce(l.calificados, 0)  as leads_calificados,
  coalesce(b.bookings, 0)     as bookings,
  coalesce(s.show_ups, 0)     as show_ups,
  coalesce(ns.no_shows, 0)    as no_shows,
  coalesce(s.ofertas, 0)      as ofertas,
  coalesce(v.ventas, 0)       as ventas,
  coalesce(v.revenue, 0)      as revenue,
  coalesce(v.upfront, 0)      as cash_upfront,
  coalesce(v.ar_nuevo, 0)     as ar_nuevo,
  coalesce(c.cash_total, 0)   as cash_collected_total,
  coalesce(c.cash_cuotas, 0)  as cash_cuotas,
  coalesce(sp.adspend, 0)     as adspend,
  -- Ratios del scorecard. NULLIF evita el #DIV/0! que hoy ensucia el Sheet.
  round(coalesce(b.bookings,0)::numeric  / nullif(l.leads, 0)    * 100, 2) as pct_booking_rate,
  round(coalesce(s.show_ups,0)::numeric  / nullif(b.bookings, 0) * 100, 2) as pct_show_up_rate,
  round(coalesce(s.ofertas,0)::numeric   / nullif(s.show_ups, 0) * 100, 2) as pct_offer_rate,
  round(coalesce(v.ventas,0)::numeric    / nullif(s.show_ups, 0) * 100, 2) as pct_close_rate,
  round(coalesce(v.upfront,0)            / nullif(v.revenue, 0)  * 100, 2) as pct_fecc_uf,
  round(coalesce(sp.adspend,0)           / nullif(l.leads, 0),      0)     as cp_lead,
  round(coalesce(sp.adspend,0)           / nullif(b.bookings, 0),   0)     as cp_booking,
  round(coalesce(sp.adspend,0)           / nullif(v.ventas, 0),     0)     as cac,
  round(coalesce(v.revenue,0)            / nullif(sp.adspend, 0),   2)     as roi_revenue,
  round(coalesce(v.revenue,0)            / nullif(v.ventas, 0),     0)     as aov_revenue
from dias d
left join leads l  on l.dia  = d.dia
left join book  b  on b.dia  = d.dia
left join shows s  on s.dia  = d.dia
left join noshow ns on ns.dia = d.dia
left join vtas  v  on v.dia  = d.dia
left join cash  c  on c.dia  = d.dia
left join spend sp on sp.dia = d.dia;

comment on view public.vw_embudo_diario is
  'Reemplaza la pestana Daily Metrics v2. Un solo SELECT, sin formulas posicionales.';

-- 18.3 Pipeline operativo (lo que ve el tablero Kanban del Formulario)
create or replace view public.vw_pipeline
with (security_invoker = on) as
select
  g.id as gestion_lead_id,
  c.nombre as cliente, c.whatsapp_e164, c.ig_handle,
  e.codigo as estado, e.nombre as estado_nombre, e.categoria, e.orden,
  f.nombre as fuente,
  us.nombre as setter, uc.nombre as closer,
  g.califica, g.urgencia, g.dolor,
  g.fecha_contacto, g.fecha_atendido, g.fecha_calificacion, g.cerrado_at,
  round(extract(epoch from (coalesce(g.fecha_atendido, now()) - g.fecha_contacto))/3600, 1)
    as horas_hasta_primer_contacto,
  round(extract(epoch from (now() - g.updated_at))/3600, 1) as horas_sin_actividad,
  r.fecha_programada as proxima_llamada,
  r.estado as estado_reunion,
  g.version
from public.gestion_leads g
join public.clientes c      on c.id = g.cliente_id
join public.estados_lead e  on e.id = g.estado_id
join public.fuentes f       on f.id = g.fuente_id
left join public.usuarios us on us.id = g.setter_id
left join public.usuarios uc on uc.id = g.closer_id
left join lateral (
  select fecha_programada, estado from public.reuniones
  where gestion_lead_id = g.id and estado in ('agendada','confirmada')
  order by fecha_programada limit 1
) r on true
where g.cerrado_at is null;

-- ===========================================================================
-- 18.4 vw_scorecard_check — AUDITORIA DE COHERENCIA EN TIEMPO REAL
--
--   Responde una sola pregunta por fila: "¿este numero del scorecard es
--   confiable?". Cada fila es una ASERCION con severidad. Si no hay filas con
--   severidad ERROR, los numeros del L10 semanal se pueden defender.
--
--   Uso:  select * from vw_scorecard_check where severidad = 'ERROR';
-- ===========================================================================
create or replace view public.vw_scorecard_check
with (security_invoker = on) as

-- A. DINERO: el plan de pagos no cuadra con el monto de la venta.
select
  'ERROR'::text                                   as severidad,
  'descuadre_plan_pagos'::text                    as chequeo,
  'ventas'::text                                  as entidad,
  v.venta_id::text                                as entidad_id,
  format('Venta %s: revenue %s pero plan de pagos suma %s (dif %s %s)',
         v.venta_id, v.revenue_bruto, v.plan_total,
         v.revenue_bruto - v.plan_total, v.currency_code)          as detalle,
  v.revenue_bruto                                 as valor_esperado,
  v.plan_total                                    as valor_real,
  v.fecha_venta_local                             as fecha_ref
from public.vw_ventas_neto v
where v.plan_total <> v.revenue_bruto

union all
-- B. DINERO: cash cobrado mayor al revenue neto (sobrecobro / doble registro).
select 'ERROR', 'sobrecobro', 'ventas', v.venta_id::text,
       format('Venta %s: cash cobrado %s > revenue neto %s',
              v.venta_id, v.cash_cobrado, v.revenue_neto),
       v.revenue_neto, v.cash_cobrado, v.fecha_venta_local
from public.vw_ventas_neto v
where v.cash_cobrado > v.revenue_neto

union all
-- C. ESTADO: hay venta pero el lead no quedo en un estado ganado.
--    Este es EL descuadre clasico entre el CRM y el Global de Sheets.
select 'ERROR', 'venta_sin_estado_ganado', 'gestion_leads', g.id::text,
       format('Lead %s tiene venta registrada pero su estado es "%s"', g.id, e.codigo),
       null, null, (v.fecha_venta at time zone public.fn_tz())::date
from public.ventas v
join public.gestion_leads g on g.id = v.gestion_lead_id
join public.estados_lead e  on e.id = g.estado_id
where not e.es_ganado

union all
-- D. ESTADO: lead marcado como ganado sin venta que lo respalde.
select 'ERROR', 'ganado_sin_venta', 'gestion_leads', g.id::text,
       format('Lead %s en estado ganado sin fila en VENTAS. Revenue fantasma.', g.id),
       null, null, (g.cerrado_at at time zone public.fn_tz())::date
from public.gestion_leads g
join public.estados_lead e on e.id = g.estado_id
where e.es_ganado
  and not exists (select 1 from public.ventas v where v.gestion_lead_id = g.id)

union all
-- E. ATRIBUCION: el closer de la venta ya no es el closer del lead.
--    NO es un error: es exactamente lo que la inmutabilidad debe preservar.
--    Se reporta como INFO para que el pago de comisiones sea explicable.
select 'INFO', 'atribucion_divergente', 'ventas', v.id::text,
       format('Venta %s atribuida a %s; el lead hoy esta asignado a %s. '
              'La comision sigue al snapshot (correcto).',
              v.id, uc.nombre, coalesce(ug.nombre, 'nadie')),
       null, null, (v.fecha_venta at time zone public.fn_tz())::date
from public.ventas v
join public.gestion_leads g on g.id = v.gestion_lead_id
join public.usuarios uc on uc.id = v.closer_id
left join public.usuarios ug on ug.id = g.closer_id
where g.closer_id is distinct from v.closer_id

union all
-- F. EMBUDO: ventas > show ups en el dia (imposible: no se vende sin llamada).
select 'ERROR', 'ventas_exceden_show_ups', 'scorecard', d.dia::text,
       format('%s: %s ventas contra %s show ups. El embudo esta roto o falta registrar reuniones.',
              d.dia, d.ventas, d.show_ups),
       d.show_ups, d.ventas, d.dia
from public.vw_embudo_diario d
where d.ventas > d.show_ups

union all
-- G. EMBUDO: bookings > leads en el dia.
select 'WARN', 'bookings_exceden_leads', 'scorecard', d.dia::text,
       format('%s: %s bookings contra %s leads nuevos (posible booking de lead viejo, verificar)',
              d.dia, d.bookings, d.leads),
       d.leads, d.bookings, d.dia
from public.vw_embudo_diario d
where d.bookings > d.leads and d.leads > 0

union all
-- H. INTEGRIDAD: reunion realizada sin fecha real (rompe el Show Up Rate).
select 'ERROR', 'show_up_sin_fecha', 'reuniones', r.id::text,
       format('Reunion %s marcada realizada sin fecha_realizada', r.id),
       null, null, (r.fecha_programada at time zone public.fn_tz())::date
from public.reuniones r
where r.estado = 'realizada' and r.fecha_realizada is null

union all
-- I. INTEGRIDAD: reuniones agendadas que ya pasaron y nadie cerro.
--    Cada una es un show up o un no show sin contabilizar.
select 'WARN', 'reunion_vencida_sin_resolver', 'reuniones', r.id::text,
       format('Reunion %s programada el %s sigue en estado "%s". Show Up Rate subestimado.',
              r.id, to_char(r.fecha_programada at time zone public.fn_tz(), 'YYYY-MM-DD HH24:MI'),
              r.estado),
       null, null, (r.fecha_programada at time zone public.fn_tz())::date
from public.reuniones r
where r.estado in ('agendada','confirmada')
  and r.fecha_programada < now() - interval '24 hours'

union all
-- J. COBRANZA: cuota vencida sin marcar (A/R inflado en el reporte).
select 'WARN', 'cuota_vencida_sin_marcar', 'pagos_cuotas', p.id::text,
       format('Cuota %s de la venta %s vencio el %s y sigue en "%s" (%s %s pendientes)',
              p.numero_cuota, p.venta_id, p.fecha_programada, p.estado,
              p.monto - p.monto_pagado, p.currency_code),
       p.monto, p.monto_pagado, p.fecha_programada
from public.pagos_cuotas p
where p.estado in ('pendiente','parcial')
  and p.fecha_programada < (now() at time zone public.fn_tz())::date

union all
-- K. DATOS: venta sin FX -> el consolidado en USD la ignora silenciosamente.
select 'WARN', 'venta_sin_fx', 'ventas', v.id::text,
       format('Venta %s en %s sin fx_rate_usd. Excluida del consolidado USD.',
              v.id, v.currency_code),
       null, null, (v.fecha_venta at time zone public.fn_tz())::date
from public.ventas v
where v.fx_rate_usd is null

union all
-- L. DATOS: leads huerfanos de closer con reunion encima.
select 'WARN', 'reunion_sin_closer', 'reuniones', r.id::text,
       format('Reunion %s sin closer_id: la venta que salga de aqui no tendra atribucion.', r.id),
       null, null, (r.fecha_programada at time zone public.fn_tz())::date
from public.reuniones r
where r.closer_id is null and r.estado in ('agendada','confirmada','realizada')

union all
-- M. HIGIENE: clientes duplicados por correo. WhatsApp e ig_handle ya tienen
--    unique index parcial; el correo no, porque llega sucio desde ManyChat.
select 'WARN', 'posible_cliente_duplicado', 'clientes',
       (array_agg(c.id order by c.created_at))[1]::text,
       format('%s clientes comparten el correo %s', count(*), c.correo),
       null, count(*), max((c.created_at at time zone public.fn_tz())::date)
from public.clientes c
where c.correo is not null
group by c.correo
having count(*) > 1;

comment on view public.vw_scorecard_check is
  'Auditoria en vivo. Cero filas con severidad ERROR = los numeros del L10 son defendibles.';

-- 18.5 Resumen ejecutivo del check (para semaforo en el dashboard)
create or replace view public.vw_scorecard_check_resumen
with (security_invoker = on) as
select severidad, chequeo, count(*) as incidencias, max(fecha_ref) as ultima_fecha
from public.vw_scorecard_check
group by severidad, chequeo
order by case severidad when 'ERROR' then 1 when 'WARN' then 2 else 3 end, incidencias desc;

-- ===========================================================================
-- 19. PERMISOS
--   Regla: `anon` no toca nada (los leads entran por la service_role del
--   Worker, no por el cliente anonimo). `authenticated` lee todo lo que su RLS
--   le permita y escribe solo en las tablas operativas.
-- ===========================================================================
grant usage on schema public to authenticated, service_role;
revoke all on schema public from anon;

grant select on all tables in schema public to authenticated;
grant insert, update on public.clientes, public.gestion_leads,
                        public.reuniones, public.pagos_cuotas to authenticated;
grant insert on public.ventas to authenticated;   -- UPDATE/DELETE: prohibidos

grant execute on all functions in schema public to authenticated;
-- Funciones internas del motor: no deben ser invocables como RPC desde el
-- cliente, porque son SECURITY DEFINER y saltarian RLS.
revoke execute on function public.fn_avanzar_estado(uuid, text)  from authenticated, anon;
revoke execute on function public.fn_check_plan_pagos(uuid)      from authenticated, anon;
revoke all     on all tables    in schema public from anon;
revoke all     on all functions in schema public from anon;

analyze;

commit;

-- ===========================================================================
-- 20. VERIFICACION POST-DEPLOY (ejecutar por separado, fuera de la transaccion)
-- ===========================================================================
-- select * from public.vw_scorecard_check_resumen;
-- select count(*) from pg_policies where schemaname = 'public';
-- select relname, relrowsecurity from pg_class
--   where relnamespace = 'public'::regnamespace and relkind = 'r' and not relrowsecurity;

-- ===========================================================================
-- 21. MIGRACION 15-ago-2026 -- resolucion gaps de negocio con Javier/Catalina
--     (notebook "ARTF - Negocio y Reuniones"). Aplicada en vivo a staging
--     (lrdtjsxtaadpgrzkchlw) como dos migraciones separadas via MCP Supabase;
--     documentada aqui integra para que un deploy limpio reproduzca el mismo
--     estado. Detalle de la decision -> 01_Gobernanza_EOS/02_backlog_y_rocas.md,
--     sesion 15-ago-2026.
-- ===========================================================================

-- 21.1 vw_scorecard_check: chequeo N, cliente_sin_manychat_id (WARN).
--      Gap historico aceptado (no se inventa manychat_id). Redefine la vista
--      completa (A-M identicas a la seccion 18.4 + N nueva) -- ver ahi el
--      detalle de cada chequeo A-M, no repetido aqui.
create or replace view public.vw_scorecard_check
with (security_invoker = on) as
select 'ERROR'::text as severidad, 'descuadre_plan_pagos'::text as chequeo,
       'ventas'::text as entidad, v.venta_id::text as entidad_id,
       format('Venta %s: revenue %s pero plan de pagos suma %s (dif %s %s)',
              v.venta_id, v.revenue_bruto, v.plan_total,
              v.revenue_bruto - v.plan_total, v.currency_code),
       v.revenue_bruto, v.plan_total, v.fecha_venta_local
from public.vw_ventas_neto v where v.plan_total <> v.revenue_bruto
union all
select 'ERROR', 'sobrecobro', 'ventas', v.venta_id::text,
       format('Venta %s: cash cobrado %s > revenue neto %s',
              v.venta_id, v.cash_cobrado, v.revenue_neto),
       v.revenue_neto, v.cash_cobrado, v.fecha_venta_local
from public.vw_ventas_neto v where v.cash_cobrado > v.revenue_neto
union all
select 'ERROR', 'venta_sin_estado_ganado', 'gestion_leads', g.id::text,
       format('Lead %s tiene venta registrada pero su estado es "%s"', g.id, e.codigo),
       null, null, (v.fecha_venta at time zone public.fn_tz())::date
from public.ventas v
join public.gestion_leads g on g.id = v.gestion_lead_id
join public.estados_lead e  on e.id = g.estado_id
where not e.es_ganado
union all
select 'ERROR', 'ganado_sin_venta', 'gestion_leads', g.id::text,
       format('Lead %s en estado ganado sin fila en VENTAS. Revenue fantasma.', g.id),
       null, null, (g.cerrado_at at time zone public.fn_tz())::date
from public.gestion_leads g
join public.estados_lead e on e.id = g.estado_id
where e.es_ganado and not exists (select 1 from public.ventas v where v.gestion_lead_id = g.id)
union all
select 'INFO', 'atribucion_divergente', 'ventas', v.id::text,
       format('Venta %s atribuida a %s; el lead hoy esta asignado a %s. '
              'La comision sigue al snapshot (correcto).',
              v.id, uc.nombre, coalesce(ug.nombre, 'nadie')),
       null, null, (v.fecha_venta at time zone public.fn_tz())::date
from public.ventas v
join public.gestion_leads g on g.id = v.gestion_lead_id
join public.usuarios uc on uc.id = v.closer_id
left join public.usuarios ug on ug.id = g.closer_id
where g.closer_id is distinct from v.closer_id
union all
select 'ERROR', 'ventas_exceden_show_ups', 'scorecard', d.dia::text,
       format('%s: %s ventas contra %s show ups. El embudo esta roto o falta registrar reuniones.',
              d.dia, d.ventas, d.show_ups),
       d.show_ups, d.ventas, d.dia
from public.vw_embudo_diario d where d.ventas > d.show_ups
union all
select 'WARN', 'bookings_exceden_leads', 'scorecard', d.dia::text,
       format('%s: %s bookings contra %s leads nuevos (posible booking de lead viejo, verificar)',
              d.dia, d.bookings, d.leads),
       d.leads, d.bookings, d.dia
from public.vw_embudo_diario d where d.bookings > d.leads and d.leads > 0
union all
select 'ERROR', 'show_up_sin_fecha', 'reuniones', r.id::text,
       format('Reunion %s marcada realizada sin fecha_realizada', r.id),
       null, null, (r.fecha_programada at time zone public.fn_tz())::date
from public.reuniones r where r.estado = 'realizada' and r.fecha_realizada is null
union all
select 'WARN', 'reunion_vencida_sin_resolver', 'reuniones', r.id::text,
       format('Reunion %s programada el %s sigue en estado "%s". Show Up Rate subestimado.',
              r.id, to_char(r.fecha_programada at time zone public.fn_tz(), 'YYYY-MM-DD HH24:MI'), r.estado),
       null, null, (r.fecha_programada at time zone public.fn_tz())::date
from public.reuniones r
where r.estado in ('agendada','confirmada') and r.fecha_programada < now() - interval '24 hours'
union all
select 'WARN', 'cuota_vencida_sin_marcar', 'pagos_cuotas', p.id::text,
       format('Cuota %s de la venta %s vencio el %s y sigue en "%s" (%s %s pendientes)',
              p.numero_cuota, p.venta_id, p.fecha_programada, p.estado,
              p.monto - p.monto_pagado, p.currency_code),
       p.monto, p.monto_pagado, p.fecha_programada
from public.pagos_cuotas p
where p.estado in ('pendiente','parcial') and p.fecha_programada < (now() at time zone public.fn_tz())::date
union all
select 'WARN', 'venta_sin_fx', 'ventas', v.id::text,
       format('Venta %s en %s sin fx_rate_usd. Excluida del consolidado USD.', v.id, v.currency_code),
       null, null, (v.fecha_venta at time zone public.fn_tz())::date
from public.ventas v where v.fx_rate_usd is null
union all
select 'WARN', 'reunion_sin_closer', 'reuniones', r.id::text,
       format('Reunion %s sin closer_id: la venta que salga de aqui no tendra atribucion.', r.id),
       null, null, (r.fecha_programada at time zone public.fn_tz())::date
from public.reuniones r where r.closer_id is null and r.estado in ('agendada','confirmada','realizada')
union all
select 'WARN', 'posible_cliente_duplicado', 'clientes', (array_agg(c.id order by c.created_at))[1]::text,
       format('%s clientes comparten el correo %s', count(*), c.correo),
       null, count(*), max((c.created_at at time zone public.fn_tz())::date)
from public.clientes c where c.correo is not null group by c.correo having count(*) > 1
union all
-- N. IDENTIDAD: cliente sin manychat_id -> no cruza con reuniones/salario.
--    Gap historico ACEPTADO (decision Javier/Catalina, 15-ago-2026): leads de
--    las primeras semanas de integracion ManyChat (ya resuelto en el flujo
--    actual). Se deja NULL a proposito -- nunca se inventa un manychat_id.
select 'WARN', 'cliente_sin_manychat_id', 'clientes', c.id::text,
       format('Cliente %s sin manychat_id: no cruza con reuniones/salario. Gap historico aceptado.', c.id),
       null, null, (c.created_at at time zone public.fn_tz())::date
from public.clientes c where c.manychat_id is null;

comment on view public.vw_scorecard_check is
  'Auditoria en vivo. Cero filas con severidad ERROR = los numeros del L10 son defendibles. '
  'WARN cliente_sin_manychat_id es un gap historico aceptado, no bloquea produccion.';

-- 21.2 Oferta de Valientes (OFV): cuota inicial menor al 50% para separar
--      cupo del programa Core. Un lead en OFV NO se considera "Ganado" hasta
--      completar el 50% -- por eso NO puede modelarse via fn_registrar_venta
--      (trg_ve_etapa lo marcaria ganado prematuramente). Tabla propia (permite
--      multiples abonos parciales antes de llegar al 50%, ver audio) + estado
--      intermedio, reusando fn_avanzar_estado (mismo patron que fn_venta_cierra_lead).
insert into public.estados_lead
  (codigo, nombre, categoria, orden, es_terminal, es_ganado,
   cuenta_como_booking, cuenta_como_show_up, cuenta_como_oferta) values
  ('reservo_oferta_valientes', 'Reservó con Oferta de Valientes', 'presentado', 65,
   false, false, true, true, true)
on conflict (codigo) do nothing;

insert into public.estado_transiciones (estado_origen_id, estado_destino_id)
select o.id, d.id
from (values
  ('show_up','reservo_oferta_valientes'),
  ('oferta_presentada','reservo_oferta_valientes'),
  ('reservo_oferta_valientes','ganado'),
  ('reservo_oferta_valientes','perdido'),
  ('reservo_oferta_valientes','nutricion')
) as tr(origen, destino)
join public.estados_lead o on o.codigo = tr.origen
join public.estados_lead d on d.codigo = tr.destino
on conflict do nothing;

create table if not exists public.depositos_reserva (
  id                 uuid primary key default gen_random_uuid(),
  gestion_lead_id    uuid not null references public.gestion_leads(id),
  monto              numeric not null check (monto > 0),
  currency_code      char(3) not null references public.monedas(code),
  fecha              timestamptz not null default now(),
  notas              text,
  created_by         uuid references public.usuarios(id),
  created_at         timestamptz not null default now()
);
create index if not exists ix_depositos_reserva_lead on public.depositos_reserva(gestion_lead_id);

alter table public.depositos_reserva enable row level security;

create policy pol_dr_select on public.depositos_reserva
  for select to authenticated using (
    public.fn_es_admin()
    or exists (select 1 from public.gestion_leads g where g.id = gestion_lead_id
               and (g.closer_id = public.fn_usuario_id() or g.setter_id = public.fn_usuario_id()))
  );
create policy pol_dr_insert on public.depositos_reserva
  for insert to authenticated with check (
    public.fn_es_admin()
    or exists (select 1 from public.gestion_leads g where g.id = gestion_lead_id
               and g.closer_id = public.fn_usuario_id())
  );

comment on table public.depositos_reserva is
  'Abonos de "Oferta de Valientes" -- cuota inicial menor al 50% que reserva '
  'el cupo del programa. NO es una venta (fn_registrar_venta/ventas se usa '
  'solo cuando se completa el 50% real). Puede haber varias filas por lead '
  '(pagos parciales acumulados antes de llegar al 50%).';

create or replace function public.fn_deposito_reserva_mueve_etapa() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform public.fn_avanzar_estado(new.gestion_lead_id, 'reservo_oferta_valientes');
  return null;
end $$;

drop trigger if exists trg_dr_etapa on public.depositos_reserva;
create trigger trg_dr_etapa
  after insert on public.depositos_reserva
  for each row execute function public.fn_deposito_reserva_mueve_etapa();

-- 21.3 Fix: depositos_reserva se creo DESPUES del GRANT original de la
--      seccion 19 ("grant select on all tables..."), asi que no lo hereda.
--      Sin esto las policies RLS de 21.2 nunca se evaluan.
grant select, insert on public.depositos_reserva to authenticated;
revoke all on public.depositos_reserva from anon;

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
  v_estado_destino_cod := case
    when p_handoff_humano and p_handoff_razon = 'crisis_emocional' then 'nutricion'
    when p_handoff_humano then 'calificado'
    when p_etapa_bot in ('AgendaManual_1', 'AgendaManual_2') then 'calificado'
    when p_etapa_bot = 'Descalificado' then 'descalificado'
    when p_etapa_bot in ('M5.B', 'M5.C') then 'agendado'
    when p_etapa_bot in ('M1', 'M2', 'M2.D', 'M3', 'M3.B', 'M4', 'M5') then 'contactado'
    else 'nuevo'  -- Inicial, JavitOff, o cualquier valor no reconocido: nunca se asume calificacion.
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
  v_avanzo := public.fn_avanzar_estado(v_gestion_id, v_estado_destino_cod);
  if not v_avanzo and v_estado_destino_cod <> 'contactado' then
    perform public.fn_avanzar_estado(v_gestion_id, 'contactado');
    v_avanzo := public.fn_avanzar_estado(v_gestion_id, v_estado_destino_cod);
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

-- ===========================================================================
-- 23. Mecanismo generico de "incidente de revision manual" + primer caso
--     real (Marisol Tupaz). Ver fn_sync_bot_turn.sql / bitacora 15-ago-2026
--     para el detalle de por que se necesito esto (Estado "Desistió" del
--     Sheet con dinero real de por medio, sin info suficiente para resolver
--     automaticamente ni con reglas ya definidas).
-- ===========================================================================
-- Cualquier gestion_leads.notas que empiece con "INCIDENTE_REVISION:" pasa
-- a aparecer en vw_scorecard_check (severidad WARN, chequeo
-- 'requiere_revision_manual') automaticamente -- mecanismo reusable, no
-- requiere tabla/columna nueva por cada caso ambiguo futuro.
create or replace view public.vw_scorecard_check as
 SELECT 'ERROR'::text AS severidad, 'descuadre_plan_pagos'::text AS chequeo, 'ventas'::text AS entidad,
    v.venta_id::text AS entidad_id,
    format('Venta %s: revenue %s pero plan de pagos suma %s (dif %s %s)'::text, v.venta_id, v.revenue_bruto, v.plan_total, v.revenue_bruto - v.plan_total, v.currency_code) AS detalle,
    v.revenue_bruto AS valor_esperado, v.plan_total AS valor_real, v.fecha_venta_local AS fecha_ref
   FROM vw_ventas_neto v WHERE v.plan_total <> v.revenue_bruto
UNION ALL
 SELECT 'ERROR'::text, 'sobrecobro'::text, 'ventas'::text, v.venta_id::text,
    format('Venta %s: cash cobrado %s > revenue neto %s'::text, v.venta_id, v.cash_cobrado, v.revenue_neto),
    v.revenue_neto, v.cash_cobrado, v.fecha_venta_local
   FROM vw_ventas_neto v WHERE v.cash_cobrado > v.revenue_neto
UNION ALL
 SELECT 'ERROR'::text, 'venta_sin_estado_ganado'::text, 'gestion_leads'::text, g.id::text,
    format('Lead %s tiene venta registrada pero su estado es "%s"'::text, g.id, e.codigo),
    NULL::numeric, NULL::numeric, (v.fecha_venta AT TIME ZONE fn_tz())::date
   FROM ventas v JOIN gestion_leads g ON g.id = v.gestion_lead_id JOIN estados_lead e ON e.id = g.estado_id
  WHERE NOT e.es_ganado
UNION ALL
 SELECT 'ERROR'::text, 'ganado_sin_venta'::text, 'gestion_leads'::text, g.id::text,
    format('Lead %s en estado ganado sin fila en VENTAS. Revenue fantasma.'::text, g.id),
    NULL::numeric, NULL::numeric, (g.cerrado_at AT TIME ZONE fn_tz())::date
   FROM gestion_leads g JOIN estados_lead e ON e.id = g.estado_id
  WHERE e.es_ganado AND NOT (EXISTS (SELECT 1 FROM ventas v WHERE v.gestion_lead_id = g.id))
UNION ALL
 SELECT 'INFO'::text, 'atribucion_divergente'::text, 'ventas'::text, v.id::text,
    format('Venta %s atribuida a %s; el lead hoy esta asignado a %s. La comision sigue al snapshot (correcto).'::text, v.id, uc.nombre, COALESCE(ug.nombre, 'nadie'::text)),
    NULL::numeric, NULL::numeric, (v.fecha_venta AT TIME ZONE fn_tz())::date
   FROM ventas v JOIN gestion_leads g ON g.id = v.gestion_lead_id JOIN usuarios uc ON uc.id = v.closer_id
     LEFT JOIN usuarios ug ON ug.id = g.closer_id
  WHERE g.closer_id IS DISTINCT FROM v.closer_id
UNION ALL
 SELECT 'ERROR'::text, 'ventas_exceden_show_ups'::text, 'scorecard'::text, d.dia::text,
    format('%s: %s ventas contra %s show ups. El embudo esta roto o falta registrar reuniones.'::text, d.dia, d.ventas, d.show_ups),
    d.show_ups, d.ventas, d.dia
   FROM vw_embudo_diario d WHERE d.ventas > d.show_ups
UNION ALL
 SELECT 'WARN'::text, 'bookings_exceden_leads'::text, 'scorecard'::text, d.dia::text,
    format('%s: %s bookings contra %s leads nuevos (posible booking de lead viejo, verificar)'::text, d.dia, d.bookings, d.leads),
    d.leads, d.bookings, d.dia
   FROM vw_embudo_diario d WHERE d.bookings > d.leads AND d.leads > 0
UNION ALL
 SELECT 'ERROR'::text, 'show_up_sin_fecha'::text, 'reuniones'::text, r.id::text,
    format('Reunion %s marcada realizada sin fecha_realizada'::text, r.id),
    NULL::numeric, NULL::numeric, (r.fecha_programada AT TIME ZONE fn_tz())::date
   FROM reuniones r WHERE r.estado = 'realizada'::estado_reunion AND r.fecha_realizada IS NULL
UNION ALL
 SELECT 'WARN'::text, 'reunion_vencida_sin_resolver'::text, 'reuniones'::text, r.id::text,
    format('Reunion %s programada el %s sigue en estado "%s". Show Up Rate subestimado.'::text, r.id, to_char((r.fecha_programada AT TIME ZONE fn_tz()), 'YYYY-MM-DD HH24:MI'::text), r.estado),
    NULL::numeric, NULL::numeric, (r.fecha_programada AT TIME ZONE fn_tz())::date
   FROM reuniones r
  WHERE (r.estado = ANY (ARRAY['agendada'::estado_reunion, 'confirmada'::estado_reunion])) AND r.fecha_programada < (now() - '24:00:00'::interval)
UNION ALL
 SELECT 'WARN'::text, 'cuota_vencida_sin_marcar'::text, 'pagos_cuotas'::text, p.id::text,
    format('Cuota %s de la venta %s vencio el %s y sigue en "%s" (%s %s pendientes)'::text, p.numero_cuota, p.venta_id, p.fecha_programada, p.estado, p.monto - p.monto_pagado, p.currency_code),
    p.monto, p.monto_pagado, p.fecha_programada
   FROM pagos_cuotas p
  WHERE (p.estado = ANY (ARRAY['pendiente'::estado_cuota, 'parcial'::estado_cuota])) AND p.fecha_programada < (now() AT TIME ZONE fn_tz())::date
UNION ALL
 SELECT 'WARN'::text, 'venta_sin_fx'::text, 'ventas'::text, v.id::text,
    format('Venta %s en %s sin fx_rate_usd. Excluida del consolidado USD.'::text, v.id, v.currency_code),
    NULL::numeric, NULL::numeric, (v.fecha_venta AT TIME ZONE fn_tz())::date
   FROM ventas v WHERE v.fx_rate_usd IS NULL
UNION ALL
 SELECT 'WARN'::text, 'reunion_sin_closer'::text, 'reuniones'::text, r.id::text,
    format('Reunion %s sin closer_id: la venta que salga de aqui no tendra atribucion.'::text, r.id),
    NULL::numeric, NULL::numeric, (r.fecha_programada AT TIME ZONE fn_tz())::date
   FROM reuniones r
  WHERE r.closer_id IS NULL AND (r.estado = ANY (ARRAY['agendada'::estado_reunion, 'confirmada'::estado_reunion, 'realizada'::estado_reunion]))
UNION ALL
 SELECT 'WARN'::text, 'posible_cliente_duplicado'::text, 'clientes'::text, (array_agg(c.id ORDER BY c.created_at))[1]::text,
    format('%s clientes comparten el correo %s'::text, count(*), c.correo),
    NULL::numeric, count(*), max((c.created_at AT TIME ZONE fn_tz())::date)
   FROM clientes c WHERE c.correo IS NOT NULL GROUP BY c.correo HAVING count(*) > 1
UNION ALL
 SELECT 'WARN'::text, 'cliente_sin_manychat_id'::text, 'clientes'::text, c.id::text,
    format('Cliente %s sin manychat_id: no cruza con reuniones/salario. Gap historico aceptado.'::text, c.id),
    NULL::numeric, NULL::numeric, (c.created_at AT TIME ZONE fn_tz())::date
   FROM clientes c WHERE c.manychat_id IS NULL
UNION ALL
 SELECT 'WARN'::text, 'requiere_revision_manual'::text, 'gestion_leads'::text, g.id::text,
    g.notas, NULL::numeric, NULL::numeric, (g.updated_at AT TIME ZONE fn_tz())::date
   FROM gestion_leads g WHERE g.notas ILIKE 'INCIDENTE_REVISION:%';

comment on view public.vw_scorecard_check is
  'Auditoria en vivo. Incluye el chequeo generico requiere_revision_manual: '
  'cualquier gestion_leads.notas que empiece con "INCIDENTE_REVISION:" '
  'aparece aqui automaticamente -- mecanismo reusable para flaggear casos '
  'ambiguos para revision humana por rol, sin inventar tablas nuevas cada '
  'vez. Primer uso: Marisol Tupaz (15-ago-2026, ver bitacora).';

-- ===========================================================================
-- 24. FIX real sobre fn_sync_bot_turn (§22), encontrado probando el Worker
--     de captura nuevo vía Postman (15-ago-2026, no en las pruebas
--     sintéticas anteriores): el salto intermedio vía 'contactado' se
--     intentaba SIEMPRE que fn_avanzar_estado devolvía false, sin distinguir
--     "ya estaba en el destino" (caso normal de una captura pasiva nueva,
--     destino='nuevo') de "salto ilegal, necesita intermedio". Un lead nuevo
--     se empujaba a 'contactado' por error y quedaba atascado ahí para
--     siempre (nada transiciona de vuelta a 'nuevo'). Fix: comparar el
--     código actual contra el destino ANTES de intentar cualquier salto.
--     Ver fn_sync_bot_turn.sql para el archivo completo actualizado.
create or replace function public.fn_sync_bot_turn(
  p_manychat_id      text,
  p_nombre           text,
  p_ig_handle        text default null,
  p_fuente_raw       text default null,
  p_profesion        text default null,
  p_salario_monto    numeric default null,
  p_dolor            text default null,
  p_urgencia_raw     text default null,
  p_califica         boolean default null,
  p_handoff_humano   boolean default false,
  p_handoff_razon    text default null,
  p_etapa_bot        text default null,
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

  v_urgencia := case p_urgencia_raw
    when 'ahora' then 'alta'::public.nivel_urgencia
    when 'algun_dia' then 'baja'::public.nivel_urgencia
    else null
  end;

  v_estado_destino_cod := case
    when p_handoff_humano and p_handoff_razon = 'crisis_emocional' then 'nutricion'
    when p_handoff_humano then 'calificado'
    when p_etapa_bot in ('AgendaManual_1', 'AgendaManual_2') then 'calificado'
    when p_etapa_bot = 'Descalificado' then 'descalificado'
    when p_etapa_bot in ('M5.B', 'M5.C') then 'agendado'
    when p_etapa_bot in ('M1', 'M2', 'M2.D', 'M3', 'M3.B', 'M4', 'M5') then 'contactado'
    else 'nuevo'
  end;

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

  select codigo into v_estado_actual_cod from public.estados_lead where id = v_estado_actual_id;

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
