# Bitácora de Decisiones — 12 de Julio de 2026
## Blindaje del Motor 2: decisiones técnicas fundamentales

Registro del *por qué* detrás de los mecanismos de resiliencia y precisión del Motor 2, deducido de la inspección del código y validado con pruebas de estrés E2E.

---

### Decisión 1: Transformación algorítmica de slugs en lugar de diccionario hardcodeado

**Contexto:** El LLM devolvía tecnologías que TheirStack no reconocía. La opción obvia era un mapa `{"AWS": "amazon-web-services", "GCP": "google-cloud-platform", ...}`.

**Decisión:** Rechazamos el diccionario. En su lugar: (1) forzamos al LLM a devolver el nombre oficial completo vía reglas de prompt y contrato Pydantic, y (2) convertimos con `t.lower().replace(" ", "-")`.

**Razón:** Un diccionario es deuda técnica infinita — habría que añadir una entrada por cada tecnología del mercado y mantenerla mientras el mercado evoluciona. La transformación algorítmica es cerrada: cubre todas las tecnologías presentes y futuras sin tocar código, siempre que el LLM cumpla su parte (nombre oficial completo). Repartimos la responsabilidad: comprensión semántica al LLM, conversión determinista al código.

**Evidencia:** Prueba 1 (`["AWS", "Microservicios"]`) → 0 empresas. Prueba 3, mismo ICP tras el fix (`["Amazon Web Services", "Python"]`) → 5 empresas. El cambio de comportamiento del LLM fue el factor decisivo.

**Riesgo residual reconocido:** si una tecnología tiene un slug que no sigue la convención `nombre.replace(" ", "-")` (ej. ".NET" → `dotnet`, no `.net`), la transformación fallará para ese caso. Es aceptable: son excepciones contadas y el costo de un lead perdido es bajo. Si se vuelve un patrón, se evaluará una capa de normalización mínima — no un diccionario completo.

---

### Decisión 2: Prohibir abstracciones en `anclaje_tecnologico`

**Contexto:** El LLM incluía "Microservicios", "ETL", "Cloud" como si fueran tecnologías.

**Decisión:** El contrato de dominio y el prompt prohíben explícitamente conceptos arquitectónicos, metodologías y procesos. Solo nombres propios de software/vendors.

**Razón:** Las APIs technográficas (TheirStack) indexan productos concretos, no conceptos. "Microservicios" no es buscable; "Kubernetes" o "Docker" sí. Permitir abstracciones garantizaba búsquedas vacías y contaminaba el `anclaje_tecnologico` que alimenta el scoring.

---

### Decisión 3: Evasión de WAF con headers de navegador, sin escalar a Playwright

**Contexto:** Cloudflare bloqueaba las peticiones de Wappalyzer y Google Alerts.

**Decisión:** Inyectar headers de Chrome real. NO escalamos a Playwright/navegador headless.

**Razón:** Playwright resuelve JS challenges pero pesa cientos de MB, ralentiza cada request y añade una dependencia frágil. Para el 80% de los WAFs básicos, un User-Agent legítimo basta. Cuando un dominio con protección avanzada bloquea igual (ej. `thefacilitiesgroup.com` en Prueba 3), aceptamos el `[]` y seguimos. El ROI de vencer un WAF agresivo por un lead individual es negativo — es la regla de oro aplicada a la infraestructura.

---

### Decisión 4: Backoff manual sin `tenacity` en los adaptadores de trigger

**Contexto:** Ya usamos `tenacity` en el `GroqICPAdapter` (Motor 1) para rate limits.

**Decisión:** En TheirStack y GitHub usamos un `for intento in range(3)` con `time.sleep(2)`, no `tenacity`.

**Razón:** El retry de trigger es trivial (2 reintentos, espera fija) y no justifica el overhead conceptual de configurar decoradores de tenacity con estrategias de wait inyectables. `tenacity` se reserva para el Motor 1, donde el manejo de rate limit del LLM es más crítico y sí se testea con estrategias de espera inyectables. Principio: usar la herramienta más simple que resuelva el problema real.

---

### Decisión 5: Contrato de error "nunca propagar al Core"

**Contexto:** El Motor 2 depende de 5 fuentes externas, cada una con su propio modo de fallo.

**Decisión:** Todo adaptador captura cualquier excepción y retorna `[]`. El Core nunca ve un error de red.

**Razón:** Aislamiento hexagonal estricto. El dominio no debe conocer HTTP, timeouts ni rate limits. Un fallo en SECOP no puede tumbar el descubrimiento de TheirStack ni el scoring de GitHub. Las pruebas E2E confirmaron 3 fallos de red simultáneos (SECOP 400, Wappalyzer WAF, TheirStack vacío) sin un solo crash. La resiliencia del pipeline completo es mayor que la de su fuente más débil.

---

### Decisión 6: Bug de double-encoding en SECOP (`%2525`)

**Contexto:** SECOP retornaba HTTP 400 en producción.

**Causa:** El `where_clause` tenía `like '%25{nombre}%25'`. Como `requests` codifica el `%` de `%25`, el wire recibía `%2525`, rompiendo el SoQL.

**Decisión:** Usar `%` literal en el string (`'%{nombre}%'`) y dejar que `requests` haga el encoding una sola vez.

**Lección:** No pre-codificar valores que la librería HTTP ya codifica. El double-encoding es un bug silencioso clásico: el código "parece" correcto (tiene el `%25` que uno ve en URLs) pero produce basura en el wire.

---
*Estas decisiones son la fuente de la verdad del comportamiento del Motor 2. Si un cambio futuro las contradice, debe justificarse aquí primero.*
