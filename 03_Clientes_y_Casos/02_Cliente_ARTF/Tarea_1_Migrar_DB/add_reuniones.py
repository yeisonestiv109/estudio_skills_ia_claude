"""
Carga incremental de `reuniones` para los gestion_leads ya insertados por
migrate_crm.py (append-only: no se puede reconstruir clientes/gestion_leads/
ventas desde cero una vez que hay ventas registradas). Empareja por
clientes.manychat_id, que es unico y se preservo en la carga original.
"""
import requests
from migrate_crm import (
    ESTADO_DEFAULT,
    ESTADO_MAP,
    HEADERS,
    SUPABASE_URL,
    batch_insert,
    load_crm_rows,
    norm_key,
    to_iso,
)


def fetch_all(table, select, extra_params=None, page=1000):
    """PostgREST caps rows per request (db-max-rows, often 1000) regardless of
    the requested `limit` -- must page with Range headers to get everything."""
    out = []
    offset = 0
    while True:
        headers = {**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset + page - 1}"}
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers,
                          params={"select": select, **(extra_params or {})}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return out


def main():
    crm_rows = load_crm_rows()

    clientes = fetch_all("clientes", "id,manychat_id", {"manychat_id": "not.is.null"})
    cliente_by_manychat = {c["manychat_id"]: c["id"] for c in clientes}
    print(f"clientes con manychat_id cargados: {len(cliente_by_manychat)}")

    leads = fetch_all("gestion_leads", "id,cliente_id,closer_id")
    lead_by_cliente = {g["cliente_id"]: g for g in leads}
    print(f"gestion_leads cargados: {len(lead_by_cliente)}")

    reuniones_existentes = fetch_all("reuniones", "gestion_lead_id")
    already_has_reunion = {row["gestion_lead_id"] for row in reuniones_existentes}

    reunion_rows = []
    sin_match = 0
    for row in crm_rows:
        manychat_id = row.get("ManyChat ID")
        manychat_id = str(manychat_id).strip() if manychat_id else None
        cliente_id = cliente_by_manychat.get(manychat_id) if manychat_id else None
        if not cliente_id:
            sin_match += 1
            continue
        lead = lead_by_cliente.get(cliente_id)
        if not lead or lead["id"] in already_has_reunion:
            continue

        fecha_programada = to_iso(row.get("Fecha Llamada Programada")) or to_iso(row.get("Fecha Agendamiento"))
        if not fecha_programada:
            continue
        fecha_agendamiento = (to_iso(row.get("Fecha Agendamiento"))
                               or to_iso(row.get("Fecha Llamada Programada")) or fecha_programada)
        fecha_realizada = to_iso(row.get("Fecha Llamada Realizada"))
        if fecha_realizada and fecha_realizada < fecha_agendamiento:
            fecha_agendamiento = fecha_realizada

        estado_raw = norm_key(row.get("Estado"))
        estado_cod = ESTADO_MAP.get(estado_raw, ESTADO_DEFAULT)
        if fecha_realizada:
            estado_re = "realizada"
        elif estado_cod == "no_show":
            estado_re = "no_show"
        elif estado_raw == "reprogramada":
            estado_re = "reprogramada"
        else:
            estado_re = "agendada"

        reunion_rows.append({
            "gestion_lead_id": lead["id"],
            "closer_id": lead.get("closer_id"),
            "estado": estado_re,
            "fecha_agendamiento": fecha_agendamiento,
            "fecha_programada": fecha_programada,
            "fecha_realizada": fecha_realizada,
            "origen_escritura": "importacion",
        })

    print(f"CRM rows sin match por manychat_id (omitidas): {sin_match}")
    print(f"Reuniones a insertar: {len(reunion_rows)}")
    if reunion_rows:
        inserted = batch_insert("reuniones", reunion_rows)
        print(f"Reuniones insertadas: {len(inserted)}")


if __name__ == "__main__":
    main()
