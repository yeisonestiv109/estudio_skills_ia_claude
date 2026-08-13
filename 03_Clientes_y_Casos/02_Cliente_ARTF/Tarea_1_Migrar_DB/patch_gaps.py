"""
Backfill de dos gaps reales encontrados en la auditoria de nulos:

1. gestion_leads.notas -- la columna "Notas" del Sheet (notas de PROCESO/
   interaccion, ej. "Setter envio M1...") solo se escribio en clientes.notas
   durante la carga inicial. Semanticamente pertenece tambien (o mas) a
   gestion_leads.notas. gestion_leads NO es append-only, se puede UPDATE.

2. pagos_cuotas.metodo_pago -- fn_registrar_venta no acepta metodo_pago como
   parametro, asi que la cuota 0 (upfront) de cada venta se creo sin ese dato
   aunque el Sheet lo tenia ("transferencia", "WHOP", etc). pagos_cuotas
   tampoco es append-only, se puede UPDATE. (ventas.reunion_id, en cambio,
   NO se puede backfillear: ventas es append-only y ya se registraron sin
   ese vinculo -- queda documentado como gap permanente de esta corrida.)
"""
import re
import requests

from migrate_crm import SUPABASE_URL, HEADERS, load_crm_rows, norm
from add_reuniones import fetch_all

METODO_PAGO_MAP = {
    "transferencia": "transferencia",
    "trasnferencia llave": "transferencia",
    "whop": "WHOP",
}


def normalize_metodo_pago(raw):
    if raw is None or isinstance(raw, (int, float)):
        return None
    s = str(raw).strip().lower()
    return METODO_PAGO_MAP.get(s)


def patch_gestion_leads_notas():
    crm_rows = load_crm_rows()
    clientes = fetch_all("clientes", "id,manychat_id")
    id_by_manychat = {c["manychat_id"]: c["id"] for c in clientes if c["manychat_id"]}
    leads = fetch_all("gestion_leads", "id,cliente_id,notas")
    lead_by_cliente = {g["cliente_id"]: g for g in leads}

    updated, sin_match, ya_tenia = 0, 0, 0
    for row in crm_rows:
        notas = norm(row.get("Notas"))
        if not notas:
            continue
        manychat_id = row.get("ManyChat ID")
        manychat_id = str(manychat_id).strip() if manychat_id else None
        cliente_id = id_by_manychat.get(manychat_id) if manychat_id else None
        if not cliente_id:
            sin_match += 1
            continue
        lead = lead_by_cliente.get(cliente_id)
        if not lead:
            continue
        if lead.get("notas"):
            ya_tenia += 1
            continue
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/gestion_leads", headers=HEADERS,
                            params={"id": f"eq.{lead['id']}"}, json={"notas": notas}, timeout=15)
        if r.ok:
            updated += 1
        else:
            print(f"  ERROR patch gestion_leads {lead['id']}: {r.status_code} {r.text[:200]}")

    print(f"gestion_leads.notas actualizados: {updated}")
    print(f"  sin match por manychat_id: {sin_match}, ya tenian valor: {ya_tenia}")


def patch_metodo_pago():
    crm_rows = load_crm_rows()
    clientes = fetch_all("clientes", "id,manychat_id")
    id_by_manychat = {c["manychat_id"]: c["id"] for c in clientes if c["manychat_id"]}
    leads = fetch_all("gestion_leads", "id,cliente_id")
    lead_id_by_cliente = {g["cliente_id"]: g["id"] for g in leads}
    ventas = fetch_all("ventas", "id,gestion_lead_id")
    venta_by_lead = {v["gestion_lead_id"]: v["id"] for v in ventas}

    updated, sin_mapeo = 0, []
    for row in crm_rows:
        metodo = normalize_metodo_pago(row.get("Forma de pago"))
        if not metodo:
            if row.get("Forma de pago") not in (None, "(pendiente)"):
                sin_mapeo.append(row.get("Forma de pago"))
            continue
        manychat_id = row.get("ManyChat ID")
        manychat_id = str(manychat_id).strip() if manychat_id else None
        cliente_id = id_by_manychat.get(manychat_id) if manychat_id else None
        lead_id = lead_id_by_cliente.get(cliente_id) if cliente_id else None
        venta_id = venta_by_lead.get(lead_id) if lead_id else None
        if not venta_id:
            continue
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/pagos_cuotas", headers=HEADERS,
                            params={"venta_id": f"eq.{venta_id}", "numero_cuota": "eq.0"},
                            json={"metodo_pago": metodo}, timeout=15)
        if r.ok:
            updated += 1
        else:
            print(f"  ERROR patch pagos_cuotas venta={venta_id}: {r.status_code} {r.text[:200]}")

    print(f"pagos_cuotas.metodo_pago actualizados: {updated}")
    print(f"  valores de 'Forma de pago' sin mapeo limpio (dejados como estaban): {sin_mapeo}")


if __name__ == "__main__":
    patch_gestion_leads_notas()
    print()
    patch_metodo_pago()
