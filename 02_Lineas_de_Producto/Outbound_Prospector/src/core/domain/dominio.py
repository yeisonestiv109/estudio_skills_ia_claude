r"""
Utilidades de dominio (Core puro) — El Prospector.

REGLA DE ARQUITECTURA: pertenece al Core. Solo usa la librería estándar. No
importa nada externo (requests, groq, bs4, tldextract, etc.). Cualquier
adaptador que necesite derivar país desde un sufijo de dominio, o comparar
dos dominios por su nombre registrable, reusa estas funciones en vez de
reimplementar su propio parsing.

Contiene dos capacidades independientes pero relacionadas:

1. `pais_por_tld(dominio)` — heurística de país basada EXCLUSIVAMENTE en el
   ESTÁNDAR IANA de ccTLD (country-code Top Level Domains). NO es una lista
   de negocio ni un catálogo de empresas: es la tabla pública de códigos de
   país de la IANA, extensible. Solo afirma un país cuando el sufijo del
   dominio es INEQUÍVOCAMENTE de ese país; ante cualquier duda retorna None
   para que el waterfall geográfico siga consultando fuentes más caras (LLM).

2. `dominio_base(dominio)` / `mismo_dominio_base(a, b)` — normalización y
   comparación del dominio registrable (eTLD+1), usada por el github_adapter
   para verificar que una organización de GitHub realmente pertenece a la
   empresa (anti-colisión de nombre: "forbes.co" ≠ "forbes.com").

Criterio de diseño (por qué NO mapear el `.co` simple a Colombia):
    El ccTLD `.co` de Colombia se comercializa globalmente desde 2010 como
    dominio genérico (startups, "company", acortadores). Por eso `empresa.co`
    es AMBIGUO → None. En cambio los sufijos de segundo nivel colombianos
    (`.com.co`, `.gov.co`, `.edu.co`, `.org.co`, `.net.co`, `.mil.co`) sí son
    inequívocamente colombianos y se mapean a "CO".
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Tabla ccTLD estándar (IANA) → ISO 3166-1 Alpha-2 (mayúsculas).
# Solo se incluyen ccTLDs INEQUÍVOCOS (un ccTLD == un país). Se listan los
# relevantes de LATAM + algunos comunes de Europa/Norteamérica. La tabla es
# extensible: agregar un par aquí no cambia la lógica.
#
# NOTA: los gTLD genéricos (.com, .org, .net, .io, .dev, .app, .ai) y el `.co`
# simple NO están en esta tabla a propósito — son ambiguos (ver criterio de
# diseño en el docstring del módulo) y por tanto derivan en None.
# ---------------------------------------------------------------------------
_CCTLD_PAIS: dict[str, str] = {
    # LATAM
    "ve": "VE",  # Venezuela
    "mx": "MX",  # México
    "ar": "AR",  # Argentina
    "cl": "CL",  # Chile
    "pe": "PE",  # Perú
    "br": "BR",  # Brasil
    "ec": "EC",  # Ecuador
    "uy": "UY",  # Uruguay
    "bo": "BO",  # Bolivia
    "py": "PY",  # Paraguay
    "gt": "GT",  # Guatemala
    "cr": "CR",  # Costa Rica
    "pa": "PA",  # Panamá
    "do": "DO",  # República Dominicana
    "hn": "HN",  # Honduras
    "ni": "NI",  # Nicaragua
    "sv": "SV",  # El Salvador
    "cu": "CU",  # Cuba
    "pr": "PR",  # Puerto Rico
    # Europa comunes
    "es": "ES",  # España
    "fr": "FR",  # Francia
    "de": "DE",  # Alemania
    "it": "IT",  # Italia
    "pt": "PT",  # Portugal
    "uk": "GB",  # Reino Unido (ccTLD .uk → ISO 'GB', no 'UK')
    # Norteamérica comunes
    "us": "US",  # Estados Unidos
    "ca": "CA",  # Canadá
}

# ---------------------------------------------------------------------------
# Sufijos PÚBLICOS de segundo nivel INEQUÍVOCOS de país → ISO Alpha-2.
# Se evalúan ANTES que el ccTLD simple porque el último label por sí solo es
# ambiguo (ej. el `.co` de `empresa.com.co` NO debe leerse como el `.co`
# genérico). Incluye los colombianos exigidos + variantes `.com.XX` de LATAM
# y `.co.uk`, todos parte del estándar de espacios de nombres de cada NIC.
# ---------------------------------------------------------------------------
_SUFIJOS_SEGUNDO_NIVEL_PAIS: dict[str, str] = {
    # Colombia (inequívocos)
    "gov.co": "CO",
    "edu.co": "CO",
    "org.co": "CO",
    "com.co": "CO",
    "mil.co": "CO",
    "net.co": "CO",
    # Otros LATAM (segundo nivel .com.XX)
    "com.mx": "MX",
    "com.ar": "AR",
    "com.br": "BR",
    "com.pe": "PE",
    "com.ve": "VE",
    "com.ec": "EC",
    "com.uy": "UY",
    "com.bo": "BO",
    "com.py": "PY",
    "com.gt": "GT",
    "com.pa": "PA",
    "com.do": "DO",
    # Reino Unido
    "co.uk": "GB",
    "org.uk": "GB",
    "gov.uk": "GB",
}

# Conjunto de sufijos públicos multi-parte (para el cálculo de eTLD+1 en
# dominio_base). Es exactamente el conjunto de claves de la tabla de segundo
# nivel: un dominio que termina en uno de estos usa 3 labels de "base" real
# (nombre + sufijo de 2 partes), no 2.
_SUFIJOS_PUBLICOS_MULTIPARTE: frozenset[str] = frozenset(_SUFIJOS_SEGUNDO_NIVEL_PAIS)


def _normalizar_host(dominio: str | None) -> str | None:
    """
    Normaliza un dominio o URL a su host desnudo, en minúsculas: quita
    esquema (http/https), credenciales, puerto, ruta/query/fragmento, el
    prefijo `www.` y los puntos sobrantes. Retorna None si queda vacío.

    Ejemplos:
        "https://www.Forbes.com/co?x=1" → "forbes.com"
        "ACME.com."                     → "acme.com"
        "user@host.io:8080/path"        → "host.io"
    """
    if not dominio:
        return None
    host = dominio.strip().lower()
    # Quitar esquema.
    if "://" in host:
        host = host.split("://", 1)[1]
    # Quitar credenciales (user:pass@host).
    if "@" in host:
        host = host.split("@", 1)[1]
    # Quitar ruta/query/fragmento.
    for sep in ("/", "?", "#"):
        if sep in host:
            host = host.split(sep, 1)[0]
    # Quitar puerto.
    if ":" in host:
        host = host.split(":", 1)[0]
    # Quitar www. inicial y puntos de borde.
    host = host.strip(".")
    if host.startswith("www."):
        host = host[4:]
    host = host.strip(".")
    return host or None


def pais_por_tld(dominio: str) -> str | None:
    """
    Deriva el país ISO Alpha-2 (mayúsculas) de un dominio SOLO cuando su
    sufijo es INEQUÍVOCAMENTE de un país (estándar IANA de ccTLD). Ante
    cualquier ambigüedad retorna None.

    Reglas (en orden):
        1. Sufijos de segundo nivel inequívocos (`.com.co`, `.gov.co`,
           `.com.mx`, `.co.uk`, ...) → su país.
        2. ccTLD simple inequívoco (`.ve`→VE, `.mx`→MX, `.es`→ES, ...) → su país.
        3. gTLD genéricos (`.com`, `.org`, `.net`, `.io`, `.app`, `.dev`,
           `.ai`) y el `.co` SIMPLE → None (ambiguo, no se asume país).

    No lanza excepción. Determinista y puro (solo stdlib).
    """
    host = _normalizar_host(dominio)
    if not host or "." not in host:
        return None

    # 1. Sufijo de segundo nivel inequívoco (se evalúa primero: el último
    #    label aislado no basta — el `co` de `empresa.com.co` es Colombia,
    #    no el `.co` genérico).
    for sufijo, pais in _SUFIJOS_SEGUNDO_NIVEL_PAIS.items():
        if host == sufijo or host.endswith("." + sufijo):
            return pais

    # 2. ccTLD simple inequívoco.
    ultimo_label = host.rsplit(".", 1)[-1]
    return _CCTLD_PAIS.get(ultimo_label)


def dominio_base(dominio: str) -> str | None:
    """
    Retorna el dominio registrable (eTLD+1) normalizado de `dominio`, o None
    si no se puede derivar.

    - "https://www.forbes.com/co" → "forbes.com"
    - "sub.dept.acme.com.co"      → "acme.com.co" (respeta el sufijo público
                                     de 2 partes .com.co)
    - "acme.com"                  → "acme.com"

    Usado para comparar propiedad de dominio sin falsos positivos por
    subdominios ni por rutas.
    """
    host = _normalizar_host(dominio)
    if not host or "." not in host:
        return None

    # Si termina en un sufijo público multi-parte, el registrable son los 3
    # labels (nombre + sufijo de 2 partes).
    for sufijo in _SUFIJOS_PUBLICOS_MULTIPARTE:
        if host == sufijo:
            # El host ES solo el sufijo público: no hay nombre registrable.
            return None
        if host.endswith("." + sufijo):
            resto = host[: -(len(sufijo) + 1)]  # todo lo anterior a ".sufijo"
            nombre = resto.rsplit(".", 1)[-1]  # último label antes del sufijo
            if not nombre:
                return None
            return f"{nombre}.{sufijo}"

    # Caso general (sufijo de 1 parte): los últimos 2 labels.
    return ".".join(host.split(".")[-2:])


def mismo_dominio_base(dominio_a: str | None, dominio_b: str | None) -> bool:
    """
    True si ambos dominios comparten el MISMO dominio registrable (eTLD+1).
    Insensible a esquema, www, subdominios, puerto y ruta. Si cualquiera de
    los dos no es derivable (None/vacío/sin punto), retorna False.

    Ejemplos:
        mismo_dominio_base("https://www.acme.com/x", "acme.com")  → True
        mismo_dominio_base("forbes.co", "https://forbes.com")     → False
        mismo_dominio_base("blog.acme.com", "shop.acme.com")      → True
    """
    base_a = dominio_base(dominio_a) if dominio_a else None
    base_b = dominio_base(dominio_b) if dominio_b else None
    if base_a is None or base_b is None:
        return False
    return base_a == base_b
