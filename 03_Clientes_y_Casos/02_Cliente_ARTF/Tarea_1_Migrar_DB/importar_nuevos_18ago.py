"""
Importa a Supabase SOLO los leads del Sheet fresco (18-ago 6pm) que aun no
existen alla (por manychat_id) -- 167 esperados segun reconciliar_18ago.py.
Reusa EXACTAMENTE la misma logica de mapeo/sanitizado que migrate_crm.py,
con dos correcciones reales encontradas hoy:
  1. sanitize_whatsapp corregido (el Sheet guarda el numero como float;
     ".0" dejaba un cero de mas al limpiar solo el punto).
  2. Diccionario de Setter/Closer ampliado: la migracion original solo
     conocia {Andrew, Gaby, Cata, Pipe}. Hoy el Sheet ya tiene 12 leads con
     Setter="Yuli" y 14 con Setter="Yeison" (alias de "Yeis" en Supabase) --
     sin este fix, esos 26 leads habrian quedado con setter_id=NULL.

Uso:
  .venv/bin/python3 importar_nuevos_18ago.py            # dry-run
  .venv/bin/python3 importar_nuevos_18ago.py --write     # importa de verdad
"""
import argparse
import datetime as dt
import os
from collections import Counter

import openpyxl
import requests
from artf_common import (
    ESTADO_DEFAULT,
    ESTADO_MAP,
    FUENTE_DEFAULT,
    FUENTE_MAP,
    NOMBRE_SHEET_A_USUARIO,
    URGENCIA_MAP,
    norm,
    norm_key,
    parse_salario,
    sanitize_email,
    sanitize_ig_handle,
    sanitize_whatsapp,
    to_iso,
)

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(HERE, "CRM - Leads Campaña 1 Reconexión Financiera (18 de agosto 6 pm).xlsx")
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
HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}


def load_crm_rows():
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True)
    ws = wb["CRM"]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))[:32]
    out = []
    for r in rows:
        d = {header[i]: r[i] for i in range(32)}
        if all(v in (None, "") for v in d.values()):
            continue
        out.append(d)
    return out


def fetch_all(table, select):
    out, offset, page = [], 0, 1000
    while True:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS,
                          params={"select": select, "limit": page, "offset": offset}, timeout=60)
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return out


def batch_insert(table, rows, chunk=300):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    print("Leyendo Sheet fresco...")
    crm_rows = load_crm_rows()
    print(f"  {len(crm_rows)} filas totales en CRM.")

    print("Consultando manychat_ids ya existentes en Supabase...")
    clientes_existentes = {c["manychat_id"] for c in fetch_all("clientes", "manychat_id") if c["manychat_id"]}
    fuente_ids = {f["codigo"]: f["id"] for f in fetch_all("fuentes", "id,codigo")}
    estado_ids = {e["codigo"]: e["id"] for e in fetch_all("estados_lead", "id,codigo")}
    usuario_ids = {u["nombre"]: u["id"] for u in fetch_all("usuarios", "id,nombre")}

    nuevas = [
        row for row in crm_rows
        if norm(row.get("ManyChat ID")) and norm(row.get("ManyChat ID")) not in clientes_existentes
    ]
    print(f"  {len(nuevas)} leads nuevos a importar (con ManyChat ID, no en Supabase).")

    sin_mcid = [row for row in crm_rows if not norm(row.get("ManyChat ID"))]
    print(f"  {len(sin_mcid)} filas sin ManyChat ID -- NO se importan aqui (necesitan match manual).")

    anomalies = Counter()
    clientes, leads_meta = [], []

    for row in nuevas:
        nombre = norm(row.get("Nombre")) or f"(sin nombre #{row.get('#')})"
        manychat_id = norm(row.get("ManyChat ID"))
        ig_handle = sanitize_ig_handle(row.get("IG Handle"))
        whatsapp = sanitize_whatsapp(row.get("WhatsApp"))
        correo = sanitize_email(row.get("Correo"))
        salario_monto, salario_currency = parse_salario(row.get("Salario"))

        cliente = {
            "manychat_id": manychat_id, "nombre": nombre, "ig_handle": ig_handle,
            "whatsapp_e164": whatsapp, "correo": correo,
            "profesion": norm(row.get("Profesión")) if norm(row.get("Profesión")) != "(pendiente)" else None,
            "salario_monto": salario_monto, "salario_currency": salario_currency,
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

        setter_nombre_sheet = norm(row.get("Setter"))
        setter_nombre_real = NOMBRE_SHEET_A_USUARIO.get(setter_nombre_sheet) if setter_nombre_sheet else None
        setter_id = usuario_ids.get(setter_nombre_real) if setter_nombre_real else None
        if setter_nombre_sheet and not setter_nombre_real:
            anomalies[f"setter_no_mapeado:{setter_nombre_sheet}"] += 1

        closer_nombre_sheet = norm(row.get("Closer"))
        closer_nombre_real = NOMBRE_SHEET_A_USUARIO.get(closer_nombre_sheet) if closer_nombre_sheet else None
        closer_id = usuario_ids.get(closer_nombre_real) if closer_nombre_real else None
        if closer_nombre_sheet and not closer_nombre_real:
            anomalies[f"closer_no_mapeado:{closer_nombre_sheet}"] += 1

        urgencia_raw = norm_key(row.get("Urgencia"))
        urgencia = URGENCIA_MAP.get(urgencia_raw)
        if urgencia_raw and urgencia_raw not in URGENCIA_MAP:
            anomalies[f"urgencia_no_mapeada:{urgencia_raw}"] += 1

        califica_raw = norm(row.get("Califica"))
        califica = {"Sí": True, "No": False}.get(califica_raw)

        fecha_contacto_dt = row.get("Fecha Contacto") or dt.datetime.now()
        fecha_contacto = to_iso(fecha_contacto_dt) or dt.datetime.now(dt.UTC).isoformat()

        def clamp_after_contacto(v):
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
            "setter_id": setter_id, "closer_id": closer_id,
            "fuente_codigo": fuente_cod, "estado_codigo": estado_cod,
            "palabra_clave_ad": norm(row.get("Palabra clave (Ad)")),
            "fecha_contacto": fecha_contacto, "fecha_atendido": fecha_atendido,
            "fecha_handoff": fecha_handoff,
            "dolor": norm(row.get("Dolor")), "urgencia": urgencia, "califica": califica,
            "handoff_razon": norm(row.get("Handoff Razón")), "origen_escritura": "importacion",
        }

        clientes.append(cliente)
        leads_meta.append({"row": row, "estado_cod": estado_cod, "gestion_lead": gestion_lead})

    seen = Counter(c["manychat_id"] for c in clientes if c["manychat_id"])
    dups = {k: v for k, v in seen.items() if v > 1}
    if dups:
        anomalies["manychat_id_duplicado_en_este_lote"] = len(dups)

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

    print()
    print("=" * 70)
    print("REPORTE DE VALIDACION")
    print("=" * 70)
    print(f"Total a importar: {len(clientes)}")
    print(f"Con setter mapeado: {sum(1 for m in leads_meta if m['gestion_lead']['setter_id'])}")
    print(f"Con closer mapeado: {sum(1 for m in leads_meta if m['gestion_lead']['closer_id'])}")
    ganados = [m for m in leads_meta if m["estado_cod"] == "ganado"]
    print(f"En estado 'ganado' (generaran venta): {len(ganados)}")
    print()
    print("Anomalias:")
    if not anomalies:
        print("  (ninguna)")
    for k, v in sorted(anomalies.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d}  {k}")

    if not args.write:
        print("\nModo dry-run: no se escribio nada. Corre con --write para importar.")
        return

    print("\nInsertando clientes...")
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

    print("Insertando reuniones (si aplica)...")
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
            fecha_agendamiento = fecha_realizada
        if fecha_realizada:
            estado_re = "realizada"
        elif meta["estado_cod"] == "no_show":
            estado_re = "no_show"
        elif norm_key(row.get("Estado")) == "reprogramada":
            estado_re = "reprogramada"
        else:
            estado_re = "agendada"
        reunion_rows.append({
            "gestion_lead_id": lead_row["id"], "closer_id": lead_row.get("closer_id"),
            "estado": estado_re, "fecha_agendamiento": fecha_agendamiento,
            "fecha_programada": fecha_programada, "fecha_realizada": fecha_realizada,
            "origen_escritura": "importacion",
        })
    if reunion_rows:
        inserted_reuniones = batch_insert("reuniones", reunion_rows)
        print(f"  {len(inserted_reuniones)} reuniones insertadas.")
    else:
        print("  0 reuniones para insertar.")

    if ganados:
        print(f"\nADVERTENCIA: {len(ganados)} leads nuevos en estado 'ganado' -- revisar manualmente,")
        print("este script NO registra ventas automaticamente (a diferencia de migrate_crm.py),")
        print("por seguridad -- son datos financieros reales, mejor confirmarlos a mano.")
        for m in ganados:
            print(f"  - {m['row'].get('Nombre')} (ManyChat ID {m['row'].get('ManyChat ID')})")

    print("\nListo.")


if __name__ == "__main__":
    main()
