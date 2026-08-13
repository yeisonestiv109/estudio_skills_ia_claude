"""
Auditoria columna-por-columna de nulos en las tablas pobladas por la
migracion, para distinguir "null correcto porque la fuente no tiene el dato"
de "null que deberia tener dato y no lo tiene" (bug de mapeo).
"""
from collections import Counter

from migrate_crm import SUPABASE_URL, HEADERS, load_crm_rows
from add_reuniones import fetch_all


def audit_table(table, columns):
    rows = fetch_all(table, ",".join(columns))
    total = len(rows)
    print(f"\n=== {table} (total filas: {total}) ===")
    for col in columns:
        non_null = sum(1 for r in rows if r.get(col) is not None)
        pct = (non_null / total * 100) if total else 0
        print(f"  {col:28s} {non_null:6d}/{total:<6d} ({pct:5.1f}%) con dato")
    return rows


def audit_source_columns(crm_rows, columns):
    print(f"\n=== Referencia: pestaña CRM del Sheet (total filas: {len(crm_rows)}) ===")
    for col in columns:
        non_null = sum(1 for r in crm_rows if r.get(col) not in (None, "", "(pendiente)"))
        print(f"  {col:28s} {non_null:6d}/{len(crm_rows):<6d} con dato real (excl. '(pendiente)')")


if __name__ == "__main__":
    crm_rows = load_crm_rows()

    audit_source_columns(crm_rows, [
        "Nombre", "IG Handle", "Setter", "Closer", "Fuente", "Profesión", "Salario",
        "Fecha Contacto", "Fecha Atendido", "Fecha Agendamiento", "Fecha Llamada Programada",
        "WhatsApp", "Correo", "Fecha Llamada Realizada", "Fecha Pago",
        "$ Upfront Cash COP", "Revenue COP", "Forma de pago", "Notas", "Dolor", "Urgencia",
        "Handoff Razón", "Califica", "ManyChat ID", "Palabra clave (Ad)",
        "Fecha inicio programa", "Fecha fin programa", "Fecha siguiente pago",
        "Monto siguiente pago", "Estado cuota",
    ])

    audit_table("clientes", [
        "manychat_id", "nombre", "ig_handle", "whatsapp_e164", "correo", "profesion",
        "salario_monto", "salario_currency", "salario_periodicidad", "pais_iso2", "notas",
    ])

    audit_table("gestion_leads", [
        "setter_id", "closer_id", "fuente_id", "estado_id", "producto_interes_id",
        "palabra_clave_ad", "campana", "utm_source", "utm_campaign",
        "fecha_contacto", "fecha_atendido", "fecha_calificacion", "fecha_handoff",
        "dolor", "urgencia", "califica", "handoff_razon", "notas", "cerrado_at",
    ])

    audit_table("reuniones", [
        "closer_id", "estado", "fecha_agendamiento", "fecha_programada", "fecha_realizada",
        "oferta_presentada", "monto_ofertado", "motivo_no_show", "notas",
    ])

    audit_table("ventas", [
        "reunion_id", "closer_id", "setter_id", "producto_id", "comision_closer_pct",
        "monto_total", "currency_code", "fx_rate_usd", "monto_total_usd", "forma_pago",
        "num_cuotas_pactadas", "fecha_inicio_programa", "fecha_fin_programa",
        "contrato_url", "notas",
    ])

    audit_table("pagos_cuotas", [
        "venta_id", "numero_cuota", "monto", "monto_pagado", "fecha_pagada",
        "metodo_pago", "referencia_pago", "estado",
    ])
