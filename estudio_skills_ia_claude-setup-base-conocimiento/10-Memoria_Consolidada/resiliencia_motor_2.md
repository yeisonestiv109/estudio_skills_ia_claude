# Resiliencia y Precisión del Motor 2 (Recolección de Señales)

Este documento consolida los mecanismos validados en producción (pruebas E2E del 12-Jul-2026) que hacen del Motor 2 una red de recolección robusta frente a entornos hostiles y a las alucinaciones del LLM.

---

## 1. Mecanismo Anti-Alucinaciones de Slugs Tecnológicos

**Problema resuelto:** El LLM (Motor 1) devolvía tecnologías en formatos que las APIs de terceros no reconocían, produciendo 0 resultados silenciosamente.

Dos modos de fallo detectados en pruebas:
1. **Siglas:** el LLM devolvía `"AWS"`, pero el slug canónico de TheirStack es `amazon-web-services`. `aws` no matcheaba nada.
2. **Abstracciones:** el LLM incluía `"Microservicios"`, `"ETL"`, `"Cloud"` — conceptos arquitectónicos que no existen como tecnología buscable.

**Solución en tres capas (sin diccionarios hardcodeados):**

| Capa | Ubicación | Regla |
|------|-----------|-------|
| 1. Contrato | `models.py` → `ManifiestoICP.anclaje_tecnologico` (Field description) | Exige nombres OFICIALES COMPLETOS, prohíbe siglas y abstracciones |
| 2. Prompt | `groq_adapter.py` → Regla #7 del system prompt | Instruye "AWS"→"Amazon Web Services", "GCP"→"Google Cloud Platform", con ejemplos |
| 3. Transformación | `theirstack_adapter.py` → `t.lower().replace(" ", "-")` | Convierte el nombre completo al slug kebab-case determinísticamente |

**Por qué NO usamos un diccionario `{"AWS": "amazon-web-services"}`:**
Un diccionario hardcodeado es deuda técnica que hay que mantener manualmente por cada tecnología nueva del mercado (miles, y crecen cada mes). La transformación algorítmica es matemáticamente cerrada: si el LLM garantiza el nombre oficial completo, entonces `nombre.lower().replace(" ", "-")` produce el slug canónico para CUALQUIER tecnología presente y futura — Snowflake→`snowflake`, Amazon Web Services→`amazon-web-services`, Google Cloud Platform→`google-cloud-platform` — sin tocar código. El LLM aporta la comprensión semántica (qué es el nombre oficial); el código aporta la conversión determinista.

**Evidencia (pruebas E2E):**
- Prueba 1: `["AWS", "Microservicios"]` → 0 empresas.
- Prueba 3 (mismo ICP tras el fix): `["Amazon Web Services", "Python"]` → 5 empresas descubiertas, 2 calificadas.

---

## 2. Evasión de Firewalls (WAF / Cloudflare)

**Problema resuelto:** `requests.get` con User-Agent no estándar (o el UA por defecto de feedparser) era bloqueado por Cloudflare, retornando HTTP 403/desconocido.

**Solución:** Todas las peticiones HTTP de scraping ligero envían headers de navegador real:
```python
{
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
}
```

- **Wappalyzer:** usa estos headers directamente en `requests.get`.
- **Google Alerts:** hace `requests.get(url, headers=...)` primero y pasa `response.text` a `feedparser.parse()`, en vez de dejar que feedparser haga la llamada con su UA delator. Si ese GET falla, cae al fallback de feedparser nativo.

**Límite honesto:** los headers de navegador evaden WAFs básicos, no protección Cloudflare avanzada (JS challenge, Turnstile). Cuando un dominio responde con HTTP desconocido pese a los headers (ej. `thefacilitiesgroup.com` en Prueba 3), el adaptador retorna `[]` sin romper el pipeline. No perseguimos esos dominios: el ROI de vencer un WAF agresivo por un solo lead es negativo.

---

## 3. Manejo de Rate Limits y Errores Transitorios (Backoff Manual)

**Problema resuelto:** APIs con rate limit (TheirStack 429, GitHub 403/429) o errores transitorios de servidor (5xx) tumbaban el proceso de descubrimiento.

**Solución — backoff manual sin dependencias (no usamos `tenacity` en estos adaptadores):**
```python
_REINTENTABLES = {429, 500, 502, 503, 504}
for intento in range(3):          # 1 llamada + 2 reintentos
    response = requests.<verb>(...)
    if response.status_code in _REINTENTABLES and intento < 2:
        time.sleep(2)
        continue
    ...
```

- Aplicado en `theirstack_adapter.py` y `github_adapter.py`.
- Toda excepción se captura → el adaptador retorna `[]`/`None`, nunca propaga al Core (cumple el contrato de `PuertoFuenteTriggers`).
- GitHub distingue 403 con `X-RateLimit-Remaining: 0` (rate limit real → no reintenta, retorna `[]`) de un 5xx transitorio (reintenta).

---

## 4. Contrato de Error Universal del Motor 2

**Invariante validada en producción:** ningún adaptador del Motor 2 propaga una excepción hacia el Core. Timeout, HTTP 4xx/5xx, SSL error, parseo fallido, ausencia de API key → todos retornan lista vacía con log. Las pruebas E2E confirmaron 3 fallos de red distintos (SECOP HTTP 400, Wappalyzer WAF, TheirStack sin resultados) sin un solo crash del orquestador.

---
*Consolidado el 12-Jul-2026 a partir de inspección de código y logs de pruebas E2E. Ver 20-Bitacora_Decisiones para el razonamiento de estas decisiones.*
