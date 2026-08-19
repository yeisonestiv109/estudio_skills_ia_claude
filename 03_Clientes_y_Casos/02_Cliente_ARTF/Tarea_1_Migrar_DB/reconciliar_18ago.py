"""
Reconciliacion determinista: Sheet fresco (18-ago 6pm) vs estado real en
Supabase. SOLO LECTURA -- no escribe nada en la base ni en el Sheet. Reusa
EXACTAMENTE los mismos diccionarios de mapeo y sanitizadores que
migrate_crm.py (la migracion original), para comparar manzanas con manzanas.

Uso: .venv/bin/python3 reconciliar_18ago.py
Salida: reporte por consola + reconciliacion_18ago.csv con el detalle fila
por fila de cada discrepancia encontrada.
"""
import csv
import os
from collections import Counter

import openpyxl
import requests
from artf_common import (
    ESTADO_MAP,
    ESTADO_ORDEN,
    NOMBRE_SHEET_A_USUARIO,
    URGENCIA_MAP,
    norm,
    norm_key,
    sanitize_whatsapp,
)

SETTERS_CLOSERS_NOMBRES = set(NOMBRE_SHEET_A_USUARIO.keys())

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(HERE, "CRM - Leads Campaña 1 Reconexión Financiera (18 de agosto 6 pm).xlsx")
ENV_PATH = os.path.join(HERE, ".env")
OUT_CSV = os.path.join(HERE, "reconciliacion_18ago.csv")


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
HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}

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


def main():
    print(f"Leyendo Sheet fresco: {XLSX_PATH}")
    crm_rows = load_crm_rows()
    print(f"  {len(crm_rows)} filas reales en la pestaña CRM (18-ago 6pm).")

    print("Descargando estado actual de Supabase (paginado)...")
    usuarios = {u["nombre"]: u["id"] for u in fetch_all("usuarios", "id,nombre")}
    clientes = fetch_all("clientes", "id,manychat_id,nombre,ig_handle,whatsapp_e164,correo,notas")
    leads = fetch_all(
        "gestion_leads",
        "id,cliente_id,setter_id,closer_id,estado_id,dolor,urgencia,califica,"
        "handoff_razon,palabra_clave_ad,notas,origen_escritura,updated_at,cerrado_at",
    )
    estados = {e["id"]: e["codigo"] for e in fetch_all("estados_lead", "id,codigo")}
    print(f"  {len(clientes)} clientes, {len(leads)} gestion_leads, {len(usuarios)} usuarios.")

    clientes_by_mcid = {c["manychat_id"]: c for c in clientes if c["manychat_id"]}
    leads_by_cliente_id = {}
    for lead_row in leads:
        leads_by_cliente_id.setdefault(lead_row["cliente_id"], []).append(lead_row)

    filas_csv = []
    contadores = Counter()
    valores_no_mapeados = Counter()
    sheet_mcids_vistos = set()

    for row in crm_rows:
        nombre = norm(row.get("Nombre")) or f"(sin nombre #{row.get('#')})"
        mcid = norm(row.get("ManyChat ID"))

        if not mcid:
            contadores["sheet_sin_manychat_id"] += 1
            continue
        sheet_mcids_vistos.add(mcid)

        cli = clientes_by_mcid.get(mcid)
        if not cli:
            contadores["nuevo_en_sheet_falta_en_supabase"] += 1
            filas_csv.append({
                "categoria": "FALTA_MIGRAR", "manychat_id": mcid, "nombre": nombre,
                "campo": "-", "valor_sheet": "-", "valor_supabase": "(no existe)",
                "gestion_lead_id": "", "origen_escritura": "", "updated_at": "",
            })
            continue

        leads_del_cliente = leads_by_cliente_id.get(cli["id"], [])
        if not leads_del_cliente:
            contadores["cliente_sin_gestion_lead"] += 1
            filas_csv.append({
                "categoria": "CLIENTE_SIN_LEAD", "manychat_id": mcid, "nombre": nombre,
                "campo": "-", "valor_sheet": "-", "valor_supabase": "(clientes existe, gestion_leads no)",
                "gestion_lead_id": "", "origen_escritura": "", "updated_at": "",
            })
            continue
        # el mas reciente por updated_at, mismo criterio que fn_sync_bot_turn
        lead = sorted(leads_del_cliente, key=lambda lr: lr["updated_at"] or "", reverse=True)[0]

        def flag(campo, valor_sheet, valor_db, severidad="MISMATCH"):
            contadores[f"{severidad}:{campo}"] += 1
            filas_csv.append({
                "categoria": severidad, "manychat_id": mcid, "nombre": nombre, "campo": campo,
                "valor_sheet": valor_sheet, "valor_supabase": valor_db,
                "gestion_lead_id": lead["id"], "origen_escritura": lead["origen_escritura"],
                "updated_at": lead["updated_at"],
            })

        # --- Setter ---
        setter_sheet = norm(row.get("Setter"))
        setter_id_esperado = usuarios.get(setter_sheet) if setter_sheet else None
        if setter_sheet and setter_sheet not in SETTERS_CLOSERS_NOMBRES:
            valores_no_mapeados[f"setter_desconocido:{setter_sheet}"] += 1
        if setter_id_esperado and setter_id_esperado != lead["setter_id"]:
            flag("setter", setter_sheet, lead["setter_id"], "SETTER_DIFERENTE")

        # --- Closer ---
        closer_sheet = norm(row.get("Closer"))
        closer_id_esperado = usuarios.get(closer_sheet) if closer_sheet else None
        if closer_sheet and closer_sheet not in SETTERS_CLOSERS_NOMBRES:
            valores_no_mapeados[f"closer_desconocido:{closer_sheet}"] += 1
        if closer_id_esperado and closer_id_esperado != lead["closer_id"]:
            flag("closer", closer_sheet, lead["closer_id"], "CLOSER_DIFERENTE")
        elif closer_id_esperado is None and closer_sheet is None and lead["closer_id"] is not None:
            pass  # DB tiene closer que el Sheet no registra -- normal (asignado despues, via Pipeline)

        # --- Estado ---
        estado_raw = norm_key(row.get("Estado"))
        estado_cod_sheet = ESTADO_MAP.get(estado_raw) if estado_raw else None
        if estado_raw and estado_raw not in ESTADO_MAP:
            valores_no_mapeados[f"estado_desconocido:{estado_raw}"] += 1
        estado_cod_db = estados.get(lead["estado_id"])
        if estado_cod_sheet and estado_cod_db and estado_cod_sheet != estado_cod_db:
            try:
                idx_sheet = ESTADO_ORDEN.index(estado_cod_sheet)
                idx_db = ESTADO_ORDEN.index(estado_cod_db)
                sev = "ESTADO_AVANZO_OK" if idx_db > idx_sheet else "ESTADO_DIFERENTE"
            except ValueError:
                sev = "ESTADO_DIFERENTE"
            flag("estado", estado_cod_sheet, estado_cod_db, sev)

        # --- Urgencia ---
        urg_raw = norm_key(row.get("Urgencia"))
        urg_sheet = URGENCIA_MAP.get(urg_raw) if urg_raw else None
        if urg_raw and urg_raw not in URGENCIA_MAP:
            valores_no_mapeados[f"urgencia_desconocida:{urg_raw}"] += 1
        if urg_sheet and urg_sheet != lead["urgencia"]:
            flag("urgencia", urg_sheet, lead["urgencia"], "URGENCIA_DIFERENTE")

        # --- Califica ---
        calif_raw = norm(row.get("Califica"))
        calif_sheet = {"Sí": True, "No": False}.get(calif_raw) if calif_raw else None
        if calif_sheet is not None and calif_sheet != lead["califica"]:
            flag("califica", calif_sheet, lead["califica"], "CALIFICA_DIFERENTE")

        # --- Handoff razon ---
        hr_sheet = norm(row.get("Handoff Razón"))
        if hr_sheet and hr_sheet != lead["handoff_razon"]:
            flag("handoff_razon", hr_sheet, lead["handoff_razon"], "HANDOFF_DIFERENTE")

        # --- Palabra clave (Ad) ---
        pk_sheet = norm(row.get("Palabra clave (Ad)"))
        if pk_sheet and pk_sheet != lead["palabra_clave_ad"]:
            flag("palabra_clave_ad", pk_sheet, lead["palabra_clave_ad"], "PALABRA_CLAVE_DIFERENTE")

        # --- Contacto: whatsapp / correo (clientes) ---
        wa_sheet_raw = row.get("WhatsApp")
        wa_sheet_normalizado = sanitize_whatsapp(wa_sheet_raw) if wa_sheet_raw else None
        if wa_sheet_normalizado and cli["whatsapp_e164"] and wa_sheet_normalizado != cli["whatsapp_e164"]:
            flag("whatsapp", norm(wa_sheet_raw), cli["whatsapp_e164"], "CONTACTO_DIFERENTE")
        co_sheet = norm(row.get("Correo"))
        if co_sheet and cli["correo"] and co_sheet.lower() != (cli["correo"] or "").lower():
            flag("correo", co_sheet, cli["correo"], "CONTACTO_DIFERENTE")

    # Leads en Supabase con manychat_id que YA NO aparece en el Sheet fresco
    faltantes_en_sheet = [mc for mc in clientes_by_mcid if mc not in sheet_mcids_vistos]

    print()
    print("=" * 78)
    print("REPORTE DE RECONCILIACION -- Sheet 18-ago 6pm vs Supabase (solo lectura)")
    print("=" * 78)
    for k, v in sorted(contadores.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d}  {k}")
    print()
    print(f"  ManyChat IDs en Supabase que ya NO están en el Sheet fresco: {len(faltantes_en_sheet)}")
    print()
    print("Valores crudos del Sheet SIN mapeo conocido (revisar si el vocabulario cambió):")
    if not valores_no_mapeados:
        print("  (ninguno)")
    for k, v in sorted(valores_no_mapeados.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d}  {k}")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["categoria", "manychat_id", "nombre", "campo",
                                           "valor_sheet", "valor_supabase", "gestion_lead_id",
                                           "origen_escritura", "updated_at"])
        w.writeheader()
        w.writerows(filas_csv)
    print()
    print(f"Detalle completo ({len(filas_csv)} filas) escrito en: {OUT_CSV}")


if __name__ == "__main__":
    main()
