"""
Logica compartida por los scripts de migracion/reconciliacion de ARTF
(migrate_crm.py, reconciliar_18ago.py, aplicar_correcciones_18ago.py,
importar_nuevos_18ago.py). Antes vivia duplicada en cada script -- eso fue
exactamente como paso el bug real del WhatsApp (corregido en un script,
seguia roto en otro) y el de Setter "Yeison"/"Yuli" (el diccionario de
nombres viejo no se actualizo en todos lados). Consolidado 19-ago-2026.

Cubierto por tests en tests/test_artf_common.py -- correr con
`.venv/bin/pytest 03_Clientes_y_Casos/02_Cliente_ARTF/Tarea_1_Migrar_DB/`
despues de cualquier cambio aca.
"""
import datetime as dt
import re

WHATSAPP_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
IG_PLACEHOLDER_VALUES = {"(pendiente)", "(sin asignar)", "-", "n/a", "na"}

FUENTE_MAP = {
    "dm directo": "ig_organico", "dm directo (lead previa)": "ig_organico",
    "dm personal": "ig_organico", "personal": "ig_organico",
    "instagram": "ig_organico", "instagramn": "ig_organico",
    "story share (orgánico)": "ig_organico", "story reply (orgánico)": "ig_organico",
    'ig ad - reel "camila"': "ig_ads", "referido": "referido",
    "whatapp": "whatsapp", "whatssap": "whatsapp", "whatsapp": "whatsapp",
    "manual_backfill": "otro", "test_curl": "otro",
}
FUENTE_DEFAULT = "otro"

ESTADO_MAP = {
    "lead nuevo - sin atender": "nuevo",
    "m1 enviado - esperando p1": "contactado", "m2 enviado - esperando dolor": "contactado",
    "m2 d - clarificación enviada": "contactado", "m3 enviado - esperando urgencia": "contactado",
    "m3 enviado - esperando respuesta": "contactado", "m4 enviado - esperando agendar": "contactado",
    "m4 enviado - esperando resp": "contactado", "m4 pitch + objeción 5 manejada": "contactado",
    "m4 pitch personalizado": "contactado", "m4 - objeción info": "contactado",
    "m5 enviado - esperando calendly": "contactado", "m5 enviado - esperando agendamiento": "contactado",
    "ghosteo - bump 1 enviado": "contactado",
    "handoff - otro": "calificado", "handoff - pregunta precio": "calificado",
    "aceptó llamada - pendiente datos": "calificado", "pendiente decisión": "calificado",
    "agendada - confirmada": "agendado", "agendada - sin datos": "agendado",
    "agendada - manual sábado 30 10:30 am": "agendado", "reprogramada": "agendado",
    "no show": "no_show", "ganado": "ganado", "perdido": "perdido",
    "descalificado - ingresos bajos": "descalificado", "descalificado - endeudamiento": "descalificado",
    "descalificado - sin urgencia": "descalificado",
    "desistió": "perdido",  # vocabulario nuevo detectado 18-ago-2026
}
ESTADO_DEFAULT = "nuevo"

# Orden real del embudo -- para distinguir "avanzo por trigger legitimo" de
# "esta atras / lateral" en la reconciliacion.
ESTADO_ORDEN = ["nuevo", "contactado", "calificado", "agendado", "no_show", "show_up",
                "oferta_presentada", "reservo_oferta_valientes", "ganado", "perdido",
                "descalificado", "nutricion"]

URGENCIA_MAP = {"ahora": "alta", "algun_dia": "baja"}

# Nombre tal como aparece en el Sheet -> nombre real del usuario en Supabase.
# "Yeison" es como el founder escribe su propio nombre en el Sheet; en
# Supabase su usuario se llama "Yeis". Bug real 18-ago-2026: el diccionario
# original (migrate_crm.py) solo conocia {Andrew, Gaby, Cata, Pipe} --
# cualquier setter/closer nuevo que se agregue a Supabase DEBE agregarse
# aca tambien, o sus leads quedaran con setter_id/closer_id = NULL en
# silencio (sin error visible) la proxima vez que se importe o reconcilie.
NOMBRE_SHEET_A_USUARIO = {
    "Andrew": "Andrew", "Gaby": "Gaby", "Cata": "Cata", "Pipe": "Pipe",
    "Yuli": "Yuli", "Yeison": "Yeis",
}
BOT_NOMBRES = {"Andrew"}

_SALARIO_SKIP = {"(pendiente)", "(no especificado)"}
_SALARIO_RANGO_RE = re.compile(r"^\$?\s*([\d.,]+)\s*(?:M)?\s*a\s*\$?\s*([\d.,]+)\s*M?\s*(COP)?\s*$", re.IGNORECASE)
_SALARIO_M_RE = re.compile(r"^\$?\s*([\d.,]+)\s*M\s*(COP)?\s*$", re.IGNORECASE)
_SALARIO_USD_RE = re.compile(r"^\$?\s*([\d.,]+)\s*USD\s*$", re.IGNORECASE)


def norm(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def norm_key(v):
    s = norm(v)
    return s.lower() if s else None


def to_iso(v):
    if isinstance(v, dt.datetime):
        return v.isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    return None


def sanitize_whatsapp(v):
    """Bug real encontrado 18-ago-2026: el Sheet guarda el numero de
    WhatsApp como float de Excel ('3023951842.0'). Si solo se quita el
    punto (no el '.0' completo), queda un cero de mas al final -- 198
    numeros de contacto reales quedaron mal guardados en la migracion
    original por esto. Ver test_sanitize_whatsapp_no_agrega_cero_de_mas."""
    s = norm(v)
    if not s:
        return None
    if s.endswith(".0"):
        s = s[:-2]
    digits = re.sub(r"[^0-9+]", "", s)
    if not digits.startswith("+"):
        digits = "+57" + digits.lstrip("0")
    return digits if WHATSAPP_RE.match(digits) else None


def sanitize_email(v):
    s = norm(v)
    if not s:
        return None
    return s if EMAIL_RE.match(s) else None


def sanitize_ig_handle(v):
    s = norm(v)
    if not s or s.lower() in IG_PLACEHOLDER_VALUES:
        return None
    return s


def parse_salario(raw):
    """(monto, currency) o (None, None)."""
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        return float(raw), "COP"
    s = str(raw).strip()
    if not s or s.lower() in _SALARIO_SKIP:
        return None, None
    m = _SALARIO_USD_RE.match(s)
    if m:
        return float(m.group(1).replace(",", "")), "USD"
    m = _SALARIO_RANGO_RE.match(s)
    if m:
        lo, hi = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        return round((lo + hi) / 2, 2) * 1_000_000, "COP"
    m = _SALARIO_M_RE.match(s)
    if m:
        return float(m.group(1).replace(",", "")) * 1_000_000, "COP"
    return None, None
