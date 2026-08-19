"""
Aplica las correcciones confirmadas de reconciliacion_18ago.csv:
  1. Setter historico "Gaby" restaurado (excluye Arley Vivas -- accion real
     reciente de Yuli via el Pipeline, se deja aparte a proposito).
  2. Setter "Yuli" para Giojanna Cediel (el Sheet ya lo dice, DB no).
  3. Closer restaurado para los leads con Pipe/Cata en el Sheet.
  4. WhatsApp corregido (bug real: el Sheet guarda el numero como float,
     ".0" dejaba un cero de mas al sanitizar).
  5. Estado -> no_show, con logica consciente de `reuniones`:
       - si reuniones.estado ya dice 'no_show' -> solo falta empujar
         gestion_leads.estado_id (el trigger de INSERT nunca lo hizo porque
         la fila se inserto directo en 'no_show', no via una transicion).
       - si reuniones.estado sigue 'agendada'/'confirmada' -> se actualiza
         reuniones.estado (asi el trigger cascada solo, mismo mecanismo que
         el boton "Marcar resultado de reunion" del Pipeline).
       - si reuniones.estado dice 'realizada' (contradice el "No Show" del
         Sheet) -> CONFLICTO real de 3 vias, NO se toca, se reporta aparte.

NO toca palabra_clave_ad (la fuente real es activity_log, no la pestaña CRM
del Sheet -- decision explicita del founder).

Uso:
  .venv/bin/python3 aplicar_correcciones_18ago.py           # dry-run
  .venv/bin/python3 aplicar_correcciones_18ago.py --write   # aplica de verdad
"""
import argparse
import csv
import os
from collections import defaultdict

import requests
from artf_common import sanitize_whatsapp as sanitize_whatsapp_fixed

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "reconciliacion_18ago.csv")
ENV_PATH = os.path.join(HERE, ".env")

ARLEY_VIVAS_LEAD_ID = "8942b47a-5769-45f1-ac03-bb83dc4e42ff"  # excluido del fix de SETTER a proposito


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


def fetch_all(table, select, extra_params=None):
    out, offset, page = [], 0, 1000
    while True:
        params = {"select": select, "limit": page, "offset": offset}
        if extra_params:
            params.update(extra_params)
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=params, timeout=60)
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return out


def patch(table, filtro, body):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=filtro, json=body, timeout=30)
    if not r.ok:
        raise RuntimeError(f"PATCH {table} {filtro} -> {r.status_code} {r.text[:300]}")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    usuarios = {u["nombre"]: u["id"] for u in fetch_all("usuarios", "id,nombre")}
    gaby_id, yuli_id = usuarios["Gaby"], usuarios["Yuli"]
    pipe_id, cata_id = usuarios["Pipe"], usuarios["Cata"]
    estado_id_por_codigo = {e["codigo"]: e["id"] for e in fetch_all("estados_lead", "id,codigo")}
    no_show_id = estado_id_por_codigo["no_show"]

    rows = list(csv.DictReader(open(CSV_PATH)))

    setter_gaby_ids, setter_yuli_ids = [], []
    closer_fixes = defaultdict(list)
    whatsapp_fixes = []
    estado_no_show_ids = []
    estado_otro_fixes = defaultdict(list)  # estado_cod destino -> [lead_id,...] (perdido, calificado, etc.)

    for row in rows:
        cat, lead_id = row["categoria"], row["gestion_lead_id"]
        if cat == "SETTER_DIFERENTE":
            if lead_id == ARLEY_VIVAS_LEAD_ID:
                continue
            if row["valor_sheet"] == "Gaby":
                setter_gaby_ids.append(lead_id)
            elif row["valor_sheet"] == "Yuli":
                setter_yuli_ids.append(lead_id)
        elif cat == "CLOSER_DIFERENTE":
            nombre = row["valor_sheet"]
            cid = pipe_id if nombre == "Pipe" else (cata_id if nombre == "Cata" else None)
            if cid:
                closer_fixes[cid].append(lead_id)
        elif cat == "CONTACTO_DIFERENTE" and row["campo"] == "whatsapp":
            nuevo = sanitize_whatsapp_fixed(row["valor_sheet"])
            if nuevo:
                whatsapp_fixes.append((lead_id, nuevo))
        elif cat == "ESTADO_DIFERENTE":
            if row["valor_sheet"] == "no_show":
                estado_no_show_ids.append(lead_id)
            elif row["valor_sheet"] in estado_id_por_codigo:
                estado_otro_fixes[row["valor_sheet"]].append(lead_id)

    # Consulta el estado REAL de la reunion vinculada para decidir el mecanismo
    reuniones = fetch_all("reuniones", "id,gestion_lead_id,estado",
                           {"gestion_lead_id": f"in.({','.join(estado_no_show_ids)})"}) if estado_no_show_ids else []
    reunion_por_lead = {r["gestion_lead_id"]: r for r in reuniones}

    avanzar_lead_directo = []   # reuniones ya dice no_show, solo falta empujar gestion_leads
    actualizar_reunion = []     # reuniones sigue agendada/confirmada -> se actualiza y cascada
    conflicto_realizada = []    # reuniones dice realizada, Sheet dice No Show -- NO TOCAR

    for lead_id in estado_no_show_ids:
        r = reunion_por_lead.get(lead_id)
        if r is None:
            avanzar_lead_directo.append(lead_id)  # sin reunion vinculada, se avanza directo
        elif r["estado"] == "no_show":
            avanzar_lead_directo.append(lead_id)
        elif r["estado"] in ("agendada", "confirmada"):
            actualizar_reunion.append(r["id"])
        elif r["estado"] == "realizada":
            conflicto_realizada.append(lead_id)

    print("Plan de correccion:")
    print(f"  Setter -> Gaby (historico):        {len(setter_gaby_ids)} leads")
    print(f"  Setter -> Yuli:                     {len(setter_yuli_ids)} leads")
    for cid, ids in closer_fixes.items():
        nombre = "Pipe" if cid == pipe_id else "Cata"
        print(f"  Closer -> {nombre}: {len(ids)} leads")
    print(f"  WhatsApp corregido:                 {len(whatsapp_fixes)} leads")
    print(f"  Estado: avanzar gestion_leads directo (reunion ya en no_show): {len(avanzar_lead_directo)}")
    print(f"  Estado: actualizar reunion (sigue agendada/confirmada):        {len(actualizar_reunion)}")
    print(f"  Estado: CONFLICTO 3-vias (reunion='realizada', Sheet='No Show') -- NO SE TOCA: "
          f"{len(conflicto_realizada)}")
    for cod, ids in estado_otro_fixes.items():
        print(f"  Estado -> {cod}: {len(ids)} leads")
    if conflicto_realizada:
        print("    IDs en conflicto (revisar a mano):")
        for lid in conflicto_realizada:
            print(f"      {lid}")

    if not args.write:
        print("\nModo dry-run: nada se escribio. Corre con --write para aplicar.")
        return

    leads_all = fetch_all("gestion_leads", "id,cliente_id")
    cliente_id_por_lead = {lead_row["id"]: lead_row["cliente_id"] for lead_row in leads_all}

    if setter_gaby_ids:
        patch("gestion_leads", {"id": f"in.({','.join(setter_gaby_ids)})"},
              {"setter_id": gaby_id, "updated_by": gaby_id})
        print(f"OK setter->Gaby: {len(setter_gaby_ids)}")

    if setter_yuli_ids:
        patch("gestion_leads", {"id": f"in.({','.join(setter_yuli_ids)})"},
              {"setter_id": yuli_id, "updated_by": yuli_id})
        print(f"OK setter->Yuli: {len(setter_yuli_ids)}")

    for cid, ids in closer_fixes.items():
        patch("gestion_leads", {"id": f"in.({','.join(ids)})"}, {"closer_id": cid})
        print(f"OK closer->{cid}: {len(ids)}")

    n_wa = 0
    for lead_id, nuevo_wa in whatsapp_fixes:
        cid = cliente_id_por_lead.get(lead_id)
        if not cid:
            continue
        patch("clientes", {"id": f"eq.{cid}"}, {"whatsapp_e164": nuevo_wa})
        n_wa += 1
    print(f"OK whatsapp corregido: {n_wa}")

    if avanzar_lead_directo:
        patch("gestion_leads", {"id": f"in.({','.join(avanzar_lead_directo)})"}, {"estado_id": no_show_id})
        print(f"OK estado->no_show (directo): {len(avanzar_lead_directo)}")

    if actualizar_reunion:
        patch("reuniones", {"id": f"in.({','.join(actualizar_reunion)})"}, {"estado": "no_show"})
        print(f"OK reunion->no_show (cascada via trigger): {len(actualizar_reunion)}")

    for cod, ids in estado_otro_fixes.items():
        try:
            patch("gestion_leads", {"id": f"in.({','.join(ids)})"}, {"estado_id": estado_id_por_codigo[cod]})
            print(f"OK estado->{cod}: {len(ids)}")
        except RuntimeError as e:
            print(f"ERROR estado->{cod} (transicion invalida para alguno de estos leads, revisar a mano): {e}")

    print("\nListo.")


if __name__ == "__main__":
    main()
