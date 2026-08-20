import openpyxl

wb = openpyxl.load_workbook(
    "CRM - Leads Campaña 1 Reconexión Financiera (18 de agosto 6 pm).xlsx",
    data_only=True,
    read_only=True,
)
ws_crm = wb["CRM"]
crm_rows = ws_crm.iter_rows(values_only=True)
header_crm = list(next(crm_rows))
for row in crm_rows:
    d = {header_crm[i]: row[i] for i in range(32)}
    if d.get("Nombre") and "Juan Manuel" in str(d["Nombre"]):
        print(f"Nombre: {d.get('Nombre')}")
        print(f"Estado: {d.get('Estado')}")
        print(f"Revenue COP: {d.get('Revenue COP')}")
        print(f"Upfront: {d.get('$ Upfront Cash COP')}")
        print(f"Fecha Pago: {d.get('Fecha Pago')}")
        print(f"Closer: {d.get('Closer')}")
