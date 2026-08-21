# Contexto del Proyecto — Índice de Memoria (siempre activo)

> Este archivo es el **índice ligero de contexto** que Kiro/Antigravity cargan en cada sesión. Solo lo esencial y punteros al detalle. **No dupliques contenido extenso aquí.**

## Quién somos

Una agencia de **AI RevOps & Automatización de Ingresos** cofundada por:
- **Yeison Estiven Delgado Ordoñez** — AI Software Engineer (Agentic Systems & Backend). Trabaja en **WSL2 (Ubuntu)**; rutas Linux `/home/estiv12/...`. Stack: Python/uv, FastAPI, LangGraph, Supabase, Node.js/fnm. IDE: Kiro + Antigravity CLI (`agy`).
- **Yulieth Gabriela Jaramillo** — Cofundadora (Estrategia Operativa & Negocio). **No usa WSL**. No asumir paridad de entorno.

## Política de comportamiento (no negociable)

1. **Antipsicofancia estricta.** Cuestiona hipótesis, expone riesgos, exige validación de datos (fuente + fecha). Si no hay datos, lo dices; **no inventas**.
2. **Arquitecto Digital.** Vendemos **resultados**, no horas. Toda propuesta conecta con las 3 Reglas de Oro: ganar dinero · ahorrar tiempo · ahorrar dinero.
3. **Marco legal LATAM:** Habeas Data (Ley 1581/2012) en scraping y cold email. Respetar ToS de APIs.

## La Propuesta de Valor Central

**AI SDR & SPEED-TO-LEAD CON REVENUE DATA CORE** — sistema de orquestación de ingresos para negocios B2B y mentores High-Ticket.

### Las dos líneas de producto (las dos caras de la moneda)

| | Línea 1 — Inbound AI SDR | Línea 2 — Outbound Prospector |
|---|---|---|
| **Estado** | 🟢 **FRENTE ACTIVO** | 🔵 En incubación |
| **Qué hace** | Atiende leads inbound (<60s) en WhatsApp/IG, califica y agenda | Descubre prospectos B2B fríos por señales de mercado (trigger-based) |
| **Cliente piloto** | **ARTF** (Andrés Resuelve Tus Finanzas) | **TBBC** (Catalina Rúa) |
| **Mentores** | Catalina Rúa + Javier | Catalina Rúa |
| **Código vive en** | `02_Lineas_de_Producto/Inbound_AI_SDR/` | `02_Lineas_de_Producto/Outbound_Prospector/` |

**Fotografía completa y narrativa (para compartir con otras IAs/personas)** →
[`05_estado_del_negocio_manifiesto.md`](../../01_Gobernanza_EOS/05_estado_del_negocio_manifiesto.md).

## Mapa de memoria (a dónde ir según la tarea)

### Gobernanza y estrategia
- Visión, propuesta de valor, perfiles de fundadores → [`01_Gobernanza_EOS/00_vision_y_principios.md`](../../01_Gobernanza_EOS/00_vision_y_principios.md)
- Entorno técnico (WSL2, fnm, uv, hooks, MCP) → [`01_Gobernanza_EOS/01_entorno_y_operacion.md`](../../01_Gobernanza_EOS/01_entorno_y_operacion.md)
- **Backlog activo y Rocas EOS (leer al iniciar sesión)** → [`01_Gobernanza_EOS/02_backlog_y_rocas.md`](../../01_Gobernanza_EOS/02_backlog_y_rocas.md)
- Protocolos de comunicación IA / prompting XML → [`01_Gobernanza_EOS/03_protocolos_comunicacion.md`](../../01_Gobernanza_EOS/03_protocolos_comunicacion.md)

### Línea 1 — Inbound AI SDR (frente activo)
- Código y docs → `02_Lineas_de_Producto/Inbound_AI_SDR/`
- Cliente activo ARTF → `03_Clientes_y_Casos/02_Cliente_ARTF/`
  - Contexto y arquitectura técnica → `04-analisis-arquitectura-y-db.md`
  - EOS del cliente → `03-contexto-artf-eos.md`

### Línea 2 — Outbound Prospector (⏸️ en pausa, ver `02_backlog_y_rocas.md`)
- Código y docs completos → repo hermano `outbound-prospector-app/` (extraído el
  20-ago-2026; `02_Lineas_de_Producto/Outbound_Prospector/` ya no existe en este repo)
- Metodología de ventas (5 módulos) → `outbound-prospector-app/docs/metodologia_ventas_5_modulos.md`
- **Al reanudar:** Paso 1 obligatorio antes de tocar código es configurar su
  notebook de NotebookLM (`PROPUESTO` → `IMPLEMENTADO`, ver
  `directrices_globales.md`) — decisión del fundador, 21-ago-2026.
- Cliente TBBC → `03_Clientes_y_Casos/01_Cliente_TBBC/`
  - Playbooks M4/M5 → `01-playbook-m4-entrevista.md` · `02-playbook-m5-relacion.md`

## Reglas operativas siempre presentes

- **Regla del 20%:** las 2-3 tareas que mueven la aguja van primero. El resto se elimina o pospone.
- **Validar antes de escalar:** nada entra en producción masiva sin prueba manual o a baja escala.
- **Código fuente de verdad:** si la memoria contradice el código, gana el código y se corrige la memoria.
- **Stack:** Python/uv · FastAPI · Supabase · LangGraph/LangChain · Cloudflare Workers · ManyChat.
- **IDE:** Kiro (specs/steering/hooks) + Antigravity CLI `agy` (agentes/ejecución). Correr siempre en WSL2.

## Regla de mantenimiento

Cuando un tema gane profundidad, **muévelo a su subarchivo** y deja aquí solo el enlace. Este archivo debe caber cómodamente en contexto.
