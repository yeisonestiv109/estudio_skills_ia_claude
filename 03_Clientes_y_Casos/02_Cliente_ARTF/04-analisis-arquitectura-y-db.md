# 04 · Análisis de Arquitectura y Selección de Base de Datos (ARTF)

> *Documento de análisis de la arquitectura inicial de Andrés Resuelve Tus Finanzas (ARTF) y el framework de decisión para la migración de la base de datos, elaborado por Yeison y Gabyota tras la entrega del Documento de Arquitectura RTF.*

## 1. Análisis de la Arquitectura Inicial (El Prototipo)

La arquitectura actual (basada en el documento de Javier) es un prototipo ingenioso que une el "Edge" (Cloudflare) con el entorno ofimático (Google Workspace). 

**Fortalezas del diseño actual:**
- **Serverless Edge (Cloudflare):** Mantener el Setter IA en Cloudflare Workers es una decisión brillante. Garantiza latencia mínima frente a los webhooks de ManyChat y auto-escalabilidad.
- **Desacoplamiento Inicial:** Usar el CRM como *Shared-Data* entre la IA (productor) y los humanos (consumidores) es el patrón correcto.
- **Reporting en Tiempo Real:** Las "Fórmulas Vivas" del DailyMetricsScorecard.gs permiten gobernar el negocio (EOS) sin latencia de ETLs.

**Riesgos Inminentes (Por qué debemos migrar):**
- **Fragilidad Concurrente:** Google Sheets y Apps Script (`LockService`) no están diseñados para ráfagas (bursts) de alta concurrencia. Si un reel se vuelve viral, cientos de webhooks de ManyChat golpearán el Worker simultáneamente. El Bridge en Apps Script encolará peticiones hasta alcanzar el límite de 6 minutos y empezará a tirar errores (pérdida de leads).
- **Límites de Crecimiento:** Con ~5,700 filas y columnas de la A a la AF llenas de `ARRAYFORMULA`, la degradación del rendimiento de Sheets es exponencial.
- **Colisiones Silenciosas:** El aislamiento por columnas es un parche; no hay verdadera integridad transaccional (ACID).

---

## 2. Dudas y Preguntas para el Arquitecto (Javier)

Antes de escribir la primera línea de código de la migración, necesitamos resolver estas dudas tácticas en nuestra próxima *Daily* o *L10*:

1. **Perfil de Ráfaga (Burst Traffic):** ¿Cuál ha sido el pico máximo histórico de leads por minuto (Webhooks de ManyChat)? Necesitamos este dato para dimensionar el *connection pooling* o las colas de la nueva base de datos.
2. **Complejidad Relacional vs. Plana:** Actualmente el esquema es plano (1 lead = 1 fila de A a AF). Al migrar a SQL, ¿debemos normalizar? (Ej. Separar el lead de sus *múltiples* interacciones o pagos), ¿o mantenemos el modelo de tabla plana ancha para facilitar los reportes del Scorecard?
3. **Requerimiento de "Tiempo Real" (Closer UI):** El equipo de Closers está acostumbrado a ver los datos actualizarse mágicamente en Google Sheets. En el nuevo Formulario Closer, ¿necesitan que los leads aparezcan en tiempo real (WebSockets/Suscripciones) o es suficiente con recargar/hacer polling cada X segundos?
4. **Política de Ecosistema:** ¿Existe alguna restricción técnica o de presupuesto para introducir un BaaS de terceros (ej. Supabase) o debemos mantener todo estrictamente en Cloudflare (ej. D1/Hyperdrive) + Google Workspace?

---

## 3. Framework de Decisión: Selección de Base de Datos (2026)

El reto principal de esta arquitectura es **conectar Cloudflare Workers (Edge) a una Base de Datos SQL sin agotar las conexiones TCP** durante una ráfaga de webhooks. Los Workers no mantienen estado entre ejecuciones, por lo que abrir una conexión TCP tradicional por cada webhook tumbaría cualquier base de datos normal.

Tras una investigación exhaustiva de las opciones vigentes para arquitecturas Edge-Serverless, estos son los candidatos:

### Opción A: Supabase (PostgreSQL BaaS) — **[RECOMENDADA]**
- **Cómo funciona aquí:** En lugar de TCP, Cloudflare Workers se comunica con Supabase a través de su API HTTP (PostgREST). Esto hace que la conexión sea **stateless** y elimina por completo el riesgo de agotar conexiones (Connection Exhaustion) durante ráfagas virales.
- **Ventaja para el Closer UI:** Tiene *Realtime* (WebSockets) nativo. Podemos hacer que el Formulario Closer reaccione en vivo cada vez que la IA actualiza un lead, imitando la magia de Google Sheets.
- **Ventaja para el EOS Scorecard:** Al ser Postgres puro, podemos crear Vistas SQL materializadas que reemplacen las pesadas `ARRAYFORMULA` de Sheets, entregando métricas instantáneas para la reunión L10.
- **Riesgo:** Es un ecosistema grande (trae Auth, Storage, etc.). Si solo queremos una DB, podría sentirse *overkill*, pero nos ahorra construir un backend entero para el Closer UI.

### Opción B: Neon (Serverless Postgres) + Cloudflare Hyperdrive
- **Cómo funciona aquí:** Neon es una base de datos Postgres que escala a cero. Para usarla desde Cloudflare Workers sin explotar las conexiones, obligatoriamente debemos enrutar el tráfico a través de **Cloudflare Hyperdrive** (un pooler de conexiones global de Cloudflare).
- **Ventajas:** Es Postgres puro. Permite usar ORMs tradicionales (como Drizzle o Prisma) dentro del Worker con latencia casi nula, ya que Hyperdrive mantiene las conexiones TCP "calientes" en el Edge.
- **Riesgos:** No tiene WebSockets nativos para el Formulario Closer (tendríamos que construir un sistema de polling o usar Pusher/Ably). Mayor complejidad de configuración inicial de infraestructura.

### Opción C: Turso (libSQL / SQLite for the Edge)
- **Cómo funciona aquí:** Es la base de datos reina del Edge. Funciona por HTTP de forma nativa e incluso permite incrustar réplicas directamente en el Worker.
- **Ventajas:** Latencia sub-milissegundo, arquitectura súper ligera, cero problemas de concurrencia de conexiones.
- **Riesgos:** Es SQLite, no Postgres. Carece de algunas funciones analíticas avanzadas, JSONB robusto y vistas complejas que podríamos necesitar para recrear el *DailyMetricsScorecard.gs*. Tampoco tiene tiempo real nativo para la UI.

### Opción D: Cloudflare D1 (SQLite Nativo de Cloudflare)
- **Ventajas:** Todo queda dentro de Cloudflare. Cero configuración, *bindings* nativos en el Worker.
- **Riesgos:** Arquitectura *Single-Writer*. Si 100 webhooks intentan escribir al mismo milisegundo, SQLite bloqueará la base de datos (Write Locks) causando encolamiento y latencia. No es ideal para ráfagas de alta concurrencia de ManyChat.

## 4. Conclusión y Recomendación Arquitectónica

**La recomendación técnica es migrar a SUPABASE.**

**¿Por qué?**
1. Resuelve el problema de la ráfaga de ManyChat elegantemente gracias a su API REST (PostgREST), evitando colapsar por conexiones TCP.
2. Su funcionalidad *Realtime* nos permite construir el Formulario Closer (HTML/JS) casi sin backend, manteniendo la experiencia "en vivo" a la que los Closers están acostumbrados en Sheets.
3. El potente motor PostgreSQL nos permitirá migrar la lógica pesada del *Daily Metrics Scorecard* desde Apps Script hacia Vistas SQL limpias y eficientes.
4. Su capa de seguridad (RLS - Row Level Security) permite que el Formulario Closer consulte la base de datos directamente y de forma segura, reduciendo las piezas móviles del sistema.
