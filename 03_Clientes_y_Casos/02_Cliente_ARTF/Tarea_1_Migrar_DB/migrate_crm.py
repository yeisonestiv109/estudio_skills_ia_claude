"""
Carga de datos reales del CRM (Google Sheets, exportado a xlsx) hacia el
esquema v3 de Supabase, para validar tablas/funciones/vistas/metricas con
volumen y desorden reales antes de la migracion de produccion.

Uso:
  python3 migrate_crm.py --dry-run   # solo valida y reporta, no escribe nada
  python3 migrate_crm.py --write     # ejecuta la carga real contra Supabase
"""
import os
import re
import sys
import argparse
import datetime as dt
from collections import Counter, defaultdict

import openpyxl
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(HERE, "Copia de CRM - Leads Campaña 1 Reconexión Financiera.xlsx")
ENV_PATH = os.path.join(HERE, ".env")


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env(ENV_PATH)
SUPABASE_URL = ENV["SUPABASE_URL"]
SERVICE_KEY = ENV["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Mapeos de datos crudos del Sheet -> vocabulario controlado del esquema v3
# ---------------------------------------------------------------------------

FUENTE_MAP = {
    "dm directo": "ig_organico",
    "dm directo (lead previa)": "ig_organico",
    "dm personal": "ig_organico",
    "personal": "ig_organico",
    "instagram": "ig_organico",
    "instagramn": "ig_organico",
    "story share (orgánico)": "ig_organico",
    "story reply (orgánico)": "ig_organico",
    'ig ad - reel "camila"': "ig_ads",
    "referido": "referido",
    "whatapp": "whatsapp",
    "whatssap": "whatsapp",
    "whatsapp": "whatsapp",
    "manual_backfill": "otro",
    "test_curl": "otro",
}
FUENTE_DEFAULT = "otro"

ESTADO_MAP = {
    "lead nuevo - sin atender": "nuevo",
    "m1 enviado - esperando p1": "contactado",
    "m2 enviado - esperando dolor": "contactado",
    "m2 d - clarificación enviada": "contactado",
    "m3 enviado - esperando urgencia": "contactado",
    "m3 enviado - esperando respuesta": "contactado",
    "m4 enviado - esperando agendar": "contactado",
    "m4 enviado - esperando resp": "contactado",
    "m4 pitch + objeción 5 manejada": "contactado",
    "m4 pitch personalizado": "contactado",
    "m4 - objeción info": "contactado",
    "m5 enviado - esperando calendly": "contactado",
    "m5 enviado - esperando agendamiento": "contactado",
    "ghosteo - bump 1 enviado": "contactado",
    "handoff - otro": "calificado",
    "handoff - pregunta precio": "calificado",
    "aceptó llamada - pendiente datos": "calificado",
    "pendiente decisión": "calificado",
    "agendada - confirmada": "agendado",
    "agendada - sin datos": "agendado",
    "agendada - manual sábado 30 10:30 am": "agendado",
    "reprogramada": "agendado",
    "no show": "no_show",
    "ganado": "ganado",
    "perdido": "perdido",
    "descalificado - ingresos bajos": "descalificado",
    "descalificado - endeudamiento": "descalificado",
    "descalificado - sin urgencia": "descalificado",
}
ESTADO_DEFAULT = "nuevo"

URGENCIA_MAP = {"ahora": "alta", "algun_dia": "baja"}

WHATSAPP_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SETTERS_CLOSERS_NOMBRES = {"Andrew", "Gaby", "Cata", "Pipe"}
BOT_NOMBRES = {"Andrew"}

PRODUCTO_CODIGO_VENTA = "core"


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
    return None  # valores no-fecha (ej. "No ha pagado") se descartan, no se adivinan


def sanitize_whatsapp(v):
    s = norm(v)
    if not s:
        return None
    digits = re.sub(r"[^0-9+]", "", s)
    if not digits.startswith("+"):
        digits = "+57" + digits.lstrip("0")  # Colombia por defecto si falta indicativo
    return digits if WHATSAPP_RE.match(digits) else None


def sanitize_email(v):
    s = norm(v)
    if not s:
        return None
    return s if EMAIL_RE.match(s) else None


IG_PLACEHOLDER_VALUES = {"(pendiente)", "(sin asignar)", "-", "n/a", "na"}

_SALARIO_SKIP = {"(pendiente)", "(no especificado)"}
_SALARIO_RANGO_RE = re.compile(r"^\$?\s*([\d.,]+)\s*(?:M)?\s*a\s*\$?\s*([\d.,]+)\s*M?\s*(COP)?\s*$", re.IGNORECASE)
_SALARIO_M_RE = re.compile(r"^\$?\s*([\d.,]+)\s*M\s*(COP)?\s*$", re.IGNORECASE)
_SALARIO_USD_RE = re.compile(r"^\$?\s*([\d.,]+)\s*USD\s*$", re.IGNORECASE)


def parse_salario(raw):
    """(monto, currency) o (None, None). Ver patch_salarios.py para el detalle
    de formatos reales encontrados en el Sheet. Periodicidad se asume 'mensual'
    (supuesto explicito, el Sheet no la especifica) por quien llame a esto."""
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


def sanitize_ig_handle(v):
    s = norm(v)
    if not s or s.lower() in IG_PLACEHOLDER_VALUES:
        return None
    return s


def load_crm_rows():
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True)
    ws = wb["CRM"]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))[:32]
    out = []
    for r in rows:
        d = {header[i]: r[i] for i in range(32)}
        if d.get("Nombre") is None and d.get("#") is None:
            continue
        out.append(d)
    return out


def fetch_lookup(table, select="*"):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS,
                      params={"select": select, "limit": "1000"}, timeout=30)
    r.raise_for_status()
    return r.json()


def ensure_usuarios():
    existing = {u["nombre"]: u["id"] for u in fetch_lookup("usuarios", "id,nombre")}
    to_create = [
        {"nombre": n, "es_bot": n in BOT_NOMBRES}
        for n in SETTERS_CLOSERS_NOMBRES if n not in existing
    ]
    if to_create:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/usuarios", headers={**HEADERS, "Prefer": "return=representation"},
                           json=to_create, timeout=30)
        r.raise_for_status()
        for u in r.json():
            existing[u["nombre"]] = u["id"]
    return existing


def batch_insert(table, rows, chunk=500):
    inserted = []
    for i in range(0, len(rows), chunk):
        chunk_rows = rows[i:i + chunk]
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                           headers={**HEADERS, "Prefer": "return=representation"},
                           json=chunk_rows, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Insert failed on {table} chunk {i}: {r.status_code} {r.text[:2000]}")
        inserted.extend(r.json())
    return inserted


def call_rpc(fn_name, payload):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}", headers=HEADERS, json=payload, timeout=30)
    return r


def build_payloads(crm_rows, fuente_ids, estado_ids, usuario_ids):
    anomalies = Counter()
    clientes, leads_meta = [], []

    for idx, row in enumerate(crm_rows):
        nombre = norm(row.get("Nombre")) or f"(sin nombre #{row.get('#')})"
        manychat_id = norm(row.get("ManyChat ID"))
        ig_handle = sanitize_ig_handle(row.get("IG Handle"))
        whatsapp = sanitize_whatsapp(row.get("WhatsApp"))
        if row.get("WhatsApp") and not whatsapp:
            anomalies["whatsapp_invalido_descartado"] += 1
        correo = sanitize_email(row.get("Correo"))
        if row.get("Correo") and not correo:
            anomalies["correo_invalido_descartado"] += 1

        salario_monto, salario_currency = parse_salario(row.get("Salario"))

        cliente = {
            "manychat_id": manychat_id,
            "nombre": nombre,
            "ig_handle": ig_handle,
            "whatsapp_e164": whatsapp,
            "correo": correo,
            "profesion": norm(row.get("Profesión")) if norm(row.get("Profesión")) != "(pendiente)" else None,
            "salario_monto": salario_monto,
            "salario_currency": salario_currency,
            "salario_periodicidad": "mensual" if salario_monto is not None else None,
            "notas": norm(row.get("Notas")),
        }

        fuente_raw = norm_key(row.get("Fuente"))
        fuente_cod = FUENTE_MAP.get(fuente_raw, FUENTE_DEFAULT)
        if fuente_raw and fuente_raw not in FUENTE_MAP:
            anomalies[f"fuente_no_mapeada:{fuente_raw}"] += 1

        estado_raw = norm_key(row.get("Estado"))
        estado_cod = ESTADO_MAP.get(estado_raw, ESTADO_DEFAULT)
        if estado_raw and estado_raw not in ESTADO_MAP:
            anomalies[f"estado_no_mapeado:{estado_raw}"] += 1

        setter_nombre = norm(row.get("Setter"))
        setter_id = usuario_ids.get(setter_nombre)
        closer_nombre = norm(row.get("Closer"))
        closer_id = usuario_ids.get(closer_nombre)

        urgencia_raw = norm_key(row.get("Urgencia"))
        urgencia = URGENCIA_MAP.get(urgencia_raw)
        if urgencia_raw and urgencia_raw not in URGENCIA_MAP:
            anomalies[f"urgencia_no_mapeada:{urgencia_raw}"] += 1

        califica_raw = norm(row.get("Califica"))
        califica = {"Sí": True, "No": False}.get(califica_raw)

        fecha_contacto_dt = row.get("Fecha Contacto") or dt.datetime.now()
        fecha_contacto = to_iso(fecha_contacto_dt) or dt.datetime.now(dt.timezone.utc).isoformat()

        def clamp_after_contacto(v):
            # ck_gl_fechas_orden exige fecha_X >= fecha_contacto. En la fuente real,
            # "Fecha Atendido" a veces queda milisegundos ANTES de "Fecha Contacto"
            # (dos eventos casi simultaneos registrados por sistemas distintos) --
            # se ajusta al piso en vez de descartar el dato.
            if not isinstance(v, (dt.datetime, dt.date)):
                return None
            iso = to_iso(v)
            if isinstance(v, dt.datetime) and isinstance(fecha_contacto_dt, dt.datetime) and v < fecha_contacto_dt:
                anomalies["fecha_atendido_antes_de_contacto_ajustada"] += 1
                return fecha_contacto
            return iso

        fecha_atendido = clamp_after_contacto(row.get("Fecha Atendido"))
        fecha_handoff = fecha_atendido if estado_cod in (
            "calificado", "agendado", "no_show", "ganado", "perdido", "descalificado") and closer_id else None

        gestion_lead = {
            "setter_id": setter_id,
            "closer_id": closer_id,
            "fuente_codigo": fuente_cod,
            "estado_codigo": estado_cod,
            "palabra_clave_ad": norm(row.get("Palabra clave (Ad)")),
            "fecha_contacto": fecha_contacto,
            "fecha_atendido": fecha_atendido,
            "fecha_handoff": fecha_handoff,
            "dolor": norm(row.get("Dolor")),
            "urgencia": urgencia,
            "califica": califica,
            "handoff_razon": norm(row.get("Handoff Razón")),
            "origen_escritura": "importacion",
        }

        clientes.append(cliente)
        leads_meta.append({"row": row, "estado_cod": estado_cod, "gestion_lead": gestion_lead})

    # deteccion de manychat_id duplicado (violaria el unique constraint)
    seen = Counter(c["manychat_id"] for c in clientes if c["manychat_id"])
    dups = {k: v for k, v in seen.items() if v > 1}
    if dups:
        anomalies["manychat_id_duplicado"] = len(dups)

    # ig_handle y whatsapp_e164 tienen unique index parcial: dos leads del mismo
    # contacto real (re-contactado en otra fecha) violarian el constraint si se
    # insertan como clientes separados. Se conserva el valor en la 1a ocurrencia
    # y se limpia en las siguientes -- el registro del lead en si NO se pierde,
    # solo su identificador de deduplicacion, para no bloquear la carga.
    seen_ig, seen_wa = set(), set()
    for c in clientes:
        if c["ig_handle"]:
            key = c["ig_handle"].lower()
            if key in seen_ig:
                anomalies["ig_handle_repetido_limpiado"] += 1
                c["ig_handle"] = None
            else:
                seen_ig.add(key)
        if c["whatsapp_e164"]:
            if c["whatsapp_e164"] in seen_wa:
                anomalies["whatsapp_repetido_limpiado"] += 1
                c["whatsapp_e164"] = None
            else:
                seen_wa.add(c["whatsapp_e164"])

    return clientes, leads_meta, anomalies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Ejecuta la carga real (por defecto solo valida)")
    args = ap.parse_args()

    print(f"Leyendo {XLSX_PATH} ...")
    crm_rows = load_crm_rows()
    print(f"  {len(crm_rows)} filas de lead leídas de la pestaña CRM.")

    print("Consultando catálogos en Supabase (fuentes, estados_lead, usuarios)...")
    fuente_ids = {f["codigo"]: f["id"] for f in fetch_lookup("fuentes", "id,codigo")}
    estado_ids = {e["codigo"]: e["id"] for e in fetch_lookup("estados_lead", "id,codigo")}
    producto_ids = {p["codigo"]: p["id"] for p in fetch_lookup("productos", "id,codigo")}

    if args.write:
        usuario_ids = ensure_usuarios()
    else:
        usuario_ids = {u["nombre"]: u["id"] for u in fetch_lookup("usuarios", "id,nombre")}
        for n in SETTERS_CLOSERS_NOMBRES:
            usuario_ids.setdefault(n, "PENDIENTE-CREAR")

    clientes, leads_meta, anomalies = build_payloads(crm_rows, fuente_ids, estado_ids, usuario_ids)

    print()
    print("=" * 70)
    print("REPORTE DE VALIDACIÓN (mapeo crudo -> esquema v3)")
    print("=" * 70)
    print(f"Total leads a migrar: {len(clientes)}")
    print(f"Con ManyChat ID: {sum(1 for c in clientes if c['manychat_id'])}")
    print(f"Con WhatsApp válido: {sum(1 for c in clientes if c['whatsapp_e164'])}")
    print(f"Con correo válido: {sum(1 for c in clientes if c['correo'])}")
    ganados = [m for m in leads_meta if m["estado_cod"] == "ganado"]
    print(f"Leads en estado 'ganado' (generarán venta vía fn_registrar_venta): {len(ganados)}")
    print()
    print("Anomalías / valores no mapeados detectados:")
    if not anomalies:
        print("  (ninguna)")
    for k, v in sorted(anomalies.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d}  {k}")

    if not args.write:
        print()
        print("Modo --dry-run: no se escribió nada en Supabase. Corre con --write para ejecutar la carga.")
        return

    print()
    print("Insertando clientes...")
    inserted_clientes = batch_insert("clientes", clientes)
    print(f"  {len(inserted_clientes)} clientes insertados.")

    print("Insertando gestion_leads...")
    gl_rows = []
    for cli, meta in zip(inserted_clientes, leads_meta):
        gl = dict(meta["gestion_lead"])
        gl["cliente_id"] = cli["id"]
        gl["fuente_id"] = fuente_ids[gl.pop("fuente_codigo")]
        gl["estado_id"] = estado_ids[gl.pop("estado_codigo")]
        gl_rows.append(gl)
    inserted_leads = batch_insert("gestion_leads", gl_rows)
    print(f"  {len(inserted_leads)} gestion_leads insertados.")

    print("Insertando reuniones (Fecha Agendamiento / Llamada Programada / Realizada)...")
    reunion_rows = []
    for lead_row, meta in zip(inserted_leads, leads_meta):
        row = meta["row"]
        fecha_programada = to_iso(row.get("Fecha Llamada Programada")) or to_iso(row.get("Fecha Agendamiento"))
        if not fecha_programada:
            continue
        fecha_agendamiento = (to_iso(row.get("Fecha Agendamiento"))
                               or to_iso(row.get("Fecha Llamada Programada")) or fecha_programada)
        fecha_realizada = to_iso(row.get("Fecha Llamada Realizada"))
        if fecha_realizada and fecha_realizada < fecha_agendamiento:
            fecha_agendamiento = fecha_realizada  # misma logica de piso que en gestion_leads
        if fecha_realizada:
            estado_re = "realizada"
        elif meta["estado_cod"] == "no_show":
            estado_re = "no_show"
        elif norm_key(row.get("Estado")) == "reprogramada":
            estado_re = "reprogramada"
        else:
            estado_re = "agendada"
        reunion_rows.append({
            "gestion_lead_id": lead_row["id"],
            "closer_id": lead_row.get("closer_id"),
            "estado": estado_re,
            "fecha_agendamiento": fecha_agendamiento,
            "fecha_programada": fecha_programada,
            "fecha_realizada": fecha_realizada,
            "origen_escritura": "importacion",
        })
    if reunion_rows:
        inserted_reuniones = batch_insert("reuniones", reunion_rows)
        print(f"  {len(inserted_reuniones)} reuniones insertadas.")
    else:
        print("  0 reuniones para insertar.")

    print("Registrando ventas de leads 'ganado' vía fn_registrar_venta RPC...")
    ventas_ok, ventas_err = 0, []
    producto_core_id = producto_ids[PRODUCTO_CODIGO_VENTA]
    for lead_row, meta in zip(inserted_leads, leads_meta):
        if meta["estado_cod"] != "ganado":
            continue
        row = meta["row"]
        revenue = row.get("Revenue COP")
        upfront = row.get("$ Upfront Cash COP") or 0
        if not revenue or revenue <= 0:
            ventas_err.append((row.get("Nombre"), "sin Revenue COP válido"))
            continue
        if not lead_row.get("closer_id"):
            ventas_err.append((row.get("Nombre"), "sin closer asignado"))
            continue
        fecha_venta = to_iso(row.get("Fecha Pago"))
        if not fecha_venta:
            ventas_err.append((row.get("Nombre"), f"Fecha Pago no parseable: {row.get('Fecha Pago')!r}"))
            continue
        num_cuotas = 1 if upfront >= revenue * 0.999 else 2
        payload = {
            "p_gestion_lead_id": lead_row["id"],
            "p_producto_id": producto_core_id,
            "p_monto_total": revenue,
            "p_currency_code": "COP",
            "p_upfront": upfront,
            "p_num_cuotas": num_cuotas,
            "p_fecha_venta": fecha_venta,
        }
        resp = call_rpc("fn_registrar_venta", payload)
        if resp.ok:
            ventas_ok += 1
        else:
            ventas_err.append((row.get("Nombre"), resp.text[:300]))

    print(f"  Ventas registradas OK: {ventas_ok}")
    if ventas_err:
        print(f"  Ventas con error ({len(ventas_err)}):")
        for nombre, err in ventas_err:
            print(f"    - {nombre}: {err}")


if __name__ == "__main__":
    main()
