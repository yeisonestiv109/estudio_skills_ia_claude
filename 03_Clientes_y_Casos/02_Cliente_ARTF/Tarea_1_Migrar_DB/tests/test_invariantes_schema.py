"""
Tests deterministas de invariantes de SEGURIDAD contra la base real de
Supabase (proyecto lrdtjsxtaadpgrzkchlw). Nacieron de 2 regresiones reales
que el propio agente introdujo el 18-ago-2026 sin darse cuenta:

  1. `CREATE OR REPLACE VIEW` no preserva `security_invoker=true` si no se
     repite explicitamente -- recrear una vista para agregar una columna
     apago el RLS en silencio (cualquier usuario veia TODA la tabla).
  2. Postgres/Supabase otorga EXECUTE a `anon` (y a `PUBLIC`, del cual
     `anon` hereda) por defecto en funciones NUEVAS -- si no se revoca a
     mano, queda expuesto a cualquiera con la llave publica. Esto llego a
     afectar `fn_registrar_venta` (crear ventas falsas), encontrado y
     corregido el mismo 19-ago-2026 gracias a este mismo test.

Correr DESPUES de cualquier migracion (CREATE VIEW, CREATE FUNCTION) para
atrapar esta clase de bug antes de que alguien mas lo encuentre por accidente.

Requiere el .env de esta carpeta (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY).
Llama a la funcion fn_diagnostico_seguridad() (solo accesible por
service_role -- ver migracion homonima), nunca corre SQL crudo desde aca.
"""
import os

import pytest
import requests

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env():
    env = {}
    with open(os.path.join(HERE, ".env")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


@pytest.fixture(scope="module")
def diagnostico():
    env = _load_env()
    headers = {
        "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {env['SUPABASE_SERVICE_ROLE_KEY']}",
    }
    r = requests.post(f"{env['SUPABASE_URL']}/rest/v1/rpc/fn_diagnostico_seguridad",
                       headers=headers, json={}, timeout=30)
    r.raise_for_status()
    return r.json()


# 19-ago-2026: las 11 funciones de TRIGGER que antes tenian EXECUTE de
# PUBLIC (heredado por `anon`/`authenticated`, no explotable via API porque
# PostgREST no expone funciones que retornan `trigger` como RPC callable,
# pero igual quedaba de sobra) se revocaron explicitamente con
# `REVOKE EXECUTE ... FROM PUBLIC` -- el REVOKE inicial a `anon,
# authenticated` directamente no bastaba, el grant real vivia en PUBLIC.
# Verificado en vivo que los triggers siguen disparando con normalidad
# despues del revoke (UPDATE real + fila nueva en auditoria_cambios).
# Este set queda vacio a proposito: si CUALQUIER funcion vuelve a aparecer
# aca (via un futuro `CREATE OR REPLACE FUNCTION` que resetea grants, el
# mismo patron que ya paso 3 veces en este proyecto), es una regresion
# real -- debe fallar el test, no pasar en silencio.
TRIGGERS_CON_ANON_ACEPTADOS = set()

# vw_embudo_diario es un agregado de TODA la empresa por diseno (funnel/
# revenue cruzando todos los closers/setters) -- security_invoker=true la
# rompería en silencio para no-admins (numeros incompletos, no un bloqueo
# limpio) en vez de arreglarla. Protegida hoy solo a nivel de app
# (AppShell.tsx gatea /metricas a isAdmin), no a nivel de base -- decision
# de diseño pendiente con el founder, no un descuido a corregir aca.
# vw_scorecard_check_resumen y vw_ventas_neto SI se corrigieron (19-ago-2026,
# mismo patron por fila que el resto del esquema) -- si vuelven a aparecer
# aca, es una regresion real.
VISTAS_SIN_INVOKER_ACEPTADAS_TEMPORALMENTE = {
    "vw_embudo_diario",
}


def test_ninguna_tabla_publica_sin_rls(diagnostico):
    assert diagnostico["tablas_publicas_sin_rls"] == []


def test_solo_las_vistas_ya_conocidas_carecen_de_security_invoker(diagnostico):
    """Si esto falla con una vista NUEVA (no en la lista de aceptadas), es
    una regresion real -- probablemente un CREATE OR REPLACE VIEW reciente
    que olvido repetir `with (security_invoker = true)`."""
    encontradas = set(diagnostico["vistas_sin_security_invoker"])
    nuevas = encontradas - VISTAS_SIN_INVOKER_ACEPTADAS_TEMPORALMENTE
    assert not nuevas, f"Vistas NUEVAS sin security_invoker (regresion real): {nuevas}"


def test_ninguna_funcion_security_definer_callable_tiene_anon(diagnostico):
    """Falla si CUALQUIER funcion que no sea un trigger conocido tiene
    EXECUTE otorgado a `anon`. Esto es lo que habria atrapado el hueco real
    de fn_registrar_venta (creaba ventas falsas, callable con la llave
    publica) antes de que llegara a produccion."""
    encontradas = set(diagnostico["funciones_security_definer_con_anon"])
    inesperadas = encontradas - TRIGGERS_CON_ANON_ACEPTADOS
    assert not inesperadas, (
        f"Funciones SECURITY DEFINER callables con acceso de anon (regresion real, "
        f"revisar si son explotables via API): {inesperadas}"
    )


def test_ninguna_funcion_trigger_tiene_authenticated(diagnostico):
    """19-ago-2026: ninguna funcion que retorna `trigger` deberia tener
    EXECUTE otorgado a `authenticated` (ni a nadie -- los triggers no lo
    necesitan, Postgres los invoca directo sin pasar por el chequeo de
    EXECUTE del rol que dispara el INSERT/UPDATE/DELETE, verificado en vivo).
    Si aparece algo aca es la misma clase de regresion de siempre: un
    `CREATE OR REPLACE FUNCTION` que reseteo los grants a su default
    (PUBLIC), sin que nadie lo revocara de nuevo."""
    encontradas = set(diagnostico["funciones_trigger_con_authenticated"])
    assert not encontradas, (
        f"Funciones TRIGGER con EXECUTE de authenticated (regresion real, "
        f"revisar si un CREATE OR REPLACE reseteo los grants): {encontradas}"
    )
