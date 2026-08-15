"""
Carga la pestana "Activity Log" del Sheet (historial real de mensajes lead/bot,
7227 filas) hacia public.activity_log en Supabase. migrate_crm.py NUNCA lee esta
pestana -- por eso "Conversaciones" (metrica del scorecard) daba 0 en las vistas
pese a que el dato real existe.

Politica de mapeo (conservadora, ver conversacion 13-ago-2026 con el fundador):
  activity_log es APPEND-ONLY (no se puede corregir despues de insertar), y el
  vocabulario crudo de "Evento"/"Etapa Actual" del Sheet es interno del bot
  (javit_off_lead_capturado, M2_dolor_pregunta_enviada, etc.) sin correspondencia
  verificable 1:1 con el enum tipo_evento ni con estados_lead. En vez de adivinar
  esa correspondencia, se clasifica por EVIDENCIA de contenido:
    1. Hay "Ultimo msg bot"                    -> mensaje_bot
    2. Si no, hay "Ultimo msg lead"             -> mensaje_lead
    3. Si no, el evento crudo contiene "handoff"    -> handoff
    4. Si no, el evento crudo contiene "agenda"     -> agendamiento
    5. Cualquier otro caso (creacion, syncs de estado, descalificaciones, etc.)
       -> nota, con el evento/etapa crudos preservados en el summary. NUNCA se
       usa 'cambio_estado' (evitamos inventar estado_nuevo_id, que el check
       ck_al_cambio_estado exige para ese tipo).
  actor_tipo='sistema', origen_escritura='importacion' para toda la carga (no se
  adivina si cada evento puntual lo genero el bot o un humano).

Identidad: se enlaza por IG Handle (normalizado igual que migrate_crm.py) contra
clientes.ig_handle ya migrados. Filas sin IG Handle util, o cuyo handle no matchea
ningun cliente migrado, se DESCARTAN (reportadas como anomalia) -- no se inventa
el cliente destino.

Uso:
  python3 migrate_activity_log.py             # dry-run: solo valida y reporta
  python3 migrate_activity_log.py --write     # ejecuta la carga real
"""
import os
import re
import sys
import argparse
import datetime as dt
from collections import Counter

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

IG_PLACEHOLDER_VALUES = {"(pendiente)", "(sin asignar)", "-", "n/a", "na"}


def norm(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def sanitize_ig_handle(v):
    s = norm(v)
    if not s or s.lower() in IG_PLACEHOLDER_VALUES:
        return None
    return s


def ig_match_key(v):
    """Clave de comparación laxa: sin '@' inicial, minúsculas. El Sheet "CRM"
    casi siempre trae '@handle' y "Activity Log" casi nunca -- sin esto, el
    match caía a 689/7227 (9.5%); normalizado sube a 5715/5719 (99.9%),
    verificado contra los dos tabs reales antes de escribir este script."""
    s = sanitize_ig_handle(v)
    return s.lstrip("@").lower() if s else None


def to_iso(v):
    if isinstance(v, dt.datetime):
        return v.isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    return None


def load_log_rows():
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True)
    ws = wb["Activity Log"]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    out = []
    for r in rows:
        if r[0] is None and r[1] is None:
            continue
        out.append(dict(zip(header, r)))
    return out


def fetch_lookup(table, select, params_extra=None, page=1000):
    """PostgREST limita filas por respuesta (db-max-rows, ~1000) sin importar el
    'limit' pedido -- hay que paginar con Range headers (hallazgo documentado en
    05-validacion-migracion-datos-reales.md §7, repetido aquí porque se olvidó)."""
    out = []
    offset = 0
    while True:
        headers = {**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset + page - 1}"}
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers,
                          params={"select": select, **(params_extra or {})}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return out


def clasificar_evento(row):
    """Devuelve (tipo_evento, summary) siguiendo la politica conservadora del docstring."""
    evento_crudo = norm(row.get("Evento")) or ""
    etapa_actual = norm(row.get("Etapa Actual")) or ""
    etapa_anterior = norm(row.get("Etapa Anterior")) or ""
    summary_sheet = norm(row.get("Summary"))
    contexto = f"[{evento_crudo}] {etapa_anterior} -> {etapa_actual}".strip()

    if norm(row.get("Último msg bot")):
        return "mensaje_bot", summary_sheet or contexto
    if norm(row.get("Último msg lead")):
        return "mensaje_lead", summary_sheet or contexto
    low = evento_crudo.lower()
    if "handoff" in low:
        return "handoff", summary_sheet or contexto
    if "agenda" in low:
        return "agendamiento", summary_sheet or contexto
    return "nota", summary_sheet or contexto


def build_payloads(log_rows, ig_to_cliente, cliente_to_gl):
    anomalies = Counter()
    out = []
    for row in log_rows:
        ig = ig_match_key(row.get("IG Handle"))
        if not ig:
            anomalies["sin_ig_handle_descartada"] += 1
            continue
        cliente_id = ig_to_cliente.get(ig)
        if not cliente_id:
            anomalies["ig_handle_sin_cliente_migrado_descartada"] += 1
            continue

        ts = row.get("Timestamp")
        created_at = to_iso(ts)
        if not created_at:
            anomalies["timestamp_no_parseable_descartada"] += 1
            continue

        tipo_evento, summary = clasificar_evento(row)

        out.append({
            "cliente_id": cliente_id,
            "gestion_lead_id": cliente_to_gl.get(cliente_id),
            "evento": tipo_evento,
            "actor_tipo": "sistema",
            "origen_escritura": "importacion",
            "ultimo_msg_lead": norm(row.get("Último msg lead")),
            "ultimo_msg_bot": norm(row.get("Último msg bot")),
            "summary": summary,
            "created_at": created_at,
        })
        anomalies[f"tipo_evento:{tipo_evento}"] += 1
    return out, anomalies


def batch_insert(table, rows, chunk=500):
    inserted = 0
    for i in range(0, len(rows), chunk):
        chunk_rows = rows[i:i + chunk]
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                           headers={**HEADERS, "Prefer": "return=minimal"},
                           json=chunk_rows, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Insert failed on {table} chunk {i}: {r.status_code} {r.text[:2000]}")
        inserted += len(chunk_rows)
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Ejecuta la carga real (por defecto solo valida)")
    args = ap.parse_args()

    print(f"Leyendo {XLSX_PATH} (pestaña 'Activity Log') ...")
    log_rows = load_log_rows()
    print(f"  {len(log_rows)} filas leídas.")

    print("Consultando clientes/gestion_leads ya migrados en Supabase...")
    clientes = fetch_lookup("clientes", "id,ig_handle")
    ig_to_cliente = {ig_match_key(c["ig_handle"]): c["id"] for c in clientes if c.get("ig_handle")}
    gls = fetch_lookup("gestion_leads", "id,cliente_id")
    cliente_to_gl = {g["cliente_id"]: g["id"] for g in gls}
    print(f"  {len(ig_to_cliente)} clientes con ig_handle, {len(cliente_to_gl)} gestion_leads.")

    payloads, anomalies = build_payloads(log_rows, ig_to_cliente, cliente_to_gl)

    print()
    print("=" * 70)
    print("REPORTE DE VALIDACIÓN")
    print("=" * 70)
    print(f"Filas a insertar: {len(payloads)} de {len(log_rows)} leídas")
    for k, v in sorted(anomalies.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d}  {k}")

    if not args.write:
        print("\nModo dry-run: no se escribió nada. Corre con --write para ejecutar.")
        return

    print("\nInsertando en activity_log...")
    n = batch_insert("activity_log", payloads)
    print(f"  {n} filas insertadas.")


if __name__ == "__main__":
    main()
