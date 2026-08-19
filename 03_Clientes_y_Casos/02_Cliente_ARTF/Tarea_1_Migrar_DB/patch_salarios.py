"""
Backfill de clientes.salario_monto/salario_currency/salario_periodicidad --
se omitio por error en la carga inicial (migrate_crm.py nunca mapeo la
columna "Salario" del Sheet). Como `clientes` ya tiene gestion_leads/ventas
dependientes (ventas es append-only), esto se aplica como UPDATE incremental,
no como re-carga completa.

Formatos reales encontrados en el Sheet (114 valores distintos, 255 filas):
  "$9M COP", "$7.5M", "$6.3M COP", 9000000.0 (ya numerico), "3000 USD",
  "$30M a 35M" (rango), "$9M papel / $6M neto" (compuesto, ambiguo),
  "(no especificado)".

Supuesto que se hace explicito (no esta en la fuente): cuando no se
especifica periodicidad, se asume 'mensual' -- coherente con que el playbook
de calificacion de ARTF pregunta ingreso MENSUAL, pero es una inferencia,
no un dato leido directamente del Sheet.
"""
import re

import requests
from add_reuniones import fetch_all
from migrate_crm import HEADERS, SUPABASE_URL, load_crm_rows

RANGO_RE = re.compile(r"^\$?\s*([\d.,]+)\s*(?:M)?\s*a\s*\$?\s*([\d.,]+)\s*M?\s*(COP)?\s*$", re.IGNORECASE)
MONTO_M_RE = re.compile(r"^\$?\s*([\d.,]+)\s*M\s*(COP)?\s*$", re.IGNORECASE)
MONTO_USD_RE = re.compile(r"^\$?\s*([\d.,]+)\s*USD\s*$", re.IGNORECASE)
SKIP_VALUES = {"(pendiente)", "(no especificado)"}


def parse_salario(raw):
    """Retorna (monto, currency) o (None, None) si no se pudo interpretar
    con confianza (mejor null que un numero inventado)."""
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        return float(raw), "COP"

    s = str(raw).strip()
    if not s or s.lower() in SKIP_VALUES:
        return None, None

    m = MONTO_USD_RE.match(s)
    if m:
        return float(m.group(1).replace(",", "")), "USD"

    m = RANGO_RE.match(s)
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", ""))
        return round((lo + hi) / 2, 2) * 1_000_000, "COP"

    m = MONTO_M_RE.match(s)
    if m:
        return float(m.group(1).replace(",", "")) * 1_000_000, "COP"

    return None, None  # compuestos ambiguos ("$9M papel / $6M neto"), typos sin "M", etc.


def main():
    crm_rows = load_crm_rows()
    clientes = fetch_all("clientes", "id,manychat_id")
    id_by_manychat = {c["manychat_id"]: c["id"] for c in clientes if c["manychat_id"]}

    updated, sin_match, sin_parsear = 0, 0, []
    for row in crm_rows:
        raw = row.get("Salario")
        if raw is None:
            continue
        monto, currency = parse_salario(raw)
        if monto is None:
            if str(raw).strip().lower() not in SKIP_VALUES:
                sin_parsear.append(raw)
            continue

        manychat_id = row.get("ManyChat ID")
        manychat_id = str(manychat_id).strip() if manychat_id else None
        cliente_id = id_by_manychat.get(manychat_id) if manychat_id else None
        if not cliente_id:
            sin_match += 1
            continue

        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/clientes",
            headers=HEADERS,
            params={"id": f"eq.{cliente_id}"},
            json={"salario_monto": monto, "salario_currency": currency, "salario_periodicidad": "mensual"},
            timeout=15,
        )
        if r.ok:
            updated += 1
        else:
            print(f"  ERROR patch {cliente_id}: {r.status_code} {r.text[:200]}")

    print(f"Clientes actualizados con salario_monto: {updated}")
    print(f"Sin match por manychat_id (no se pudo aplicar): {sin_match}")
    print(f"Valores sin parsear con confianza ({len(sin_parsear)}): {sin_parsear}")


if __name__ == "__main__":
    main()
