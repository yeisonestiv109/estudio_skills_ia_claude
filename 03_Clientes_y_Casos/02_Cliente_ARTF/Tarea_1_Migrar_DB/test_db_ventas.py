import requests

ENV_PATH = ".env"
def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            if not line.strip() or line.startswith("#") or "=" not in line:
                continue
            k, v = line.strip().split("=", 1)
            env[k.strip()] = v.strip()
    return env

ENV = load_env(ENV_PATH)
HEADERS = {"apikey": ENV["SUPABASE_SERVICE_ROLE_KEY"], "Authorization": f"Bearer {ENV['SUPABASE_SERVICE_ROLE_KEY']}"}

def fetch_all(table, select="*"):
    out, offset, page = [], 0, 1000
    while True:
        r = requests.get(f"{ENV['SUPABASE_URL']}/rest/v1/{table}", headers=HEADERS,
                          params={"select": select, "limit": page, "offset": offset}, timeout=60)
        batch = r.json()
        out.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return out

ventas = fetch_all("ventas", "id,gestion_lead_id,monto_total,created_at,cliente_id")
clientes = fetch_all("clientes", "id,nombre")
cliente_map = {c['id']: c['nombre'] for c in clientes}

print("VENTAS EN DB:")
for v in ventas:
    c_id = v.get('cliente_id')
    nombre = cliente_map.get(c_id, 'Desconocido')
    print(f"Nombre: {nombre}, Total: {v.get('monto_total')}, Fecha DB: {v.get('created_at')}")
