# Productividad, CRM y Automatización Personal

> Roadmap de trabajo (marcado por el fundador como **"después miremos"**). Aquí queda el framework inicial y los pendientes. Objetivo: gestionar clientes con orden, mantener el costo de herramientas cerca de **$0**, y automatizar tareas propias para ser más productivo. *No es exhaustivo todavía — se irá llenando.*

## 1. CRM propio (gestión de clientes y leads)

> Un CRM es donde registras prospectos, en qué etapa está cada uno y el siguiente paso. Sin esto, se pierden oportunidades (error clásico del freelance).

### 💡 Hallazgo clave: usa tu propio Prospector como CRM (dogfooding)

El Prospector **ya tiene un mini-CRM integrado** (tablas `crm_leads`/`crm_lead_notes`, apartado Kanban "Mis Leads / CRM"). Usarlo para gestionar tus propios prospectos tiene doble beneficio:

- Costo $0 (es tuyo) y te organiza.
- **Lo pruebas como usuario real** → detectas mejoras → mejor producto para vender. Es el mejor testimonio: "lo uso para mi propio negocio".

### Alternativas gratuitas (si necesitas algo aparte)

| Herramienta | Plan gratuito | Bueno para |
|-------------|---------------|------------|
| **HubSpot CRM Free** | Sí, robusto | CRM completo, pipeline visual, sin costo inicial |
| **Notion** | Sí | CRM + notas + documentos + base de conocimiento, todo en uno |
| **Trello** | Sí | Kanban simple de pipeline (prospecto → reunión → propuesta → cierre) |
| **Google Sheets** | Sí | Lo más simple para arrancar y medir el embudo |

> **Recomendación del coach:** arranca con **el Prospector (dogfooding) + una hoja simple del embudo**. No te compliques con un CRM pesado hasta tener volumen. Mide: contactos → respuestas → reuniones → cierres (las métricas del [Pilar 3](../docs/fundamentos/03-estrategia-ventas-prospeccion.md)).

## 2. Costo del sistema Prospector (objetivo: ~$0)

A bajo volumen, el Prospector puede operar **prácticamente en $0** apoyándose en las capas gratuitas de su stack (verificadas jun-2026, re-confirmadas jul-2026):

- **Tavily:** 1.000 créditos/mes gratis.
- **Groq (Llama 4 Scout):** tier gratuito (~30 req/min).
- **Supabase / Modal:** planes/free credits iniciales.
- **Hunter / Apollo:** cuotas gratuitas mensuales limitadas.

> ⚠️ **Disciplina (del doc de validación):** "gratis" se acaba al subir el volumen. La métrica a vigilar es el **costo por lead calificado**. Mientras uses el Prospector para ti y para demos, el costo es marginal; cuando lo uses para un cliente a escala, **mide el consumo real** antes de cotizar. Detalle en [validación de fuentes §6](../docs/validacion/validacion-fuentes.md).

**Acción pendiente:** correr 1 job real y anotar el consumo exacto (Tavily/Groq/Hunter) → cerrar el número de costo por lead.

## 3. Automatizar tus propias tareas (para ser más productivo)

La idea: aplicarte a ti mismo lo que les vendes a los clientes. Candidatos a automatizar:

| Tarea propia | Cómo automatizarla | Herramienta |
|--------------|--------------------|-------------|
| Seguimiento de leads (recordatorios) | Recordatorios automáticos por etapa | CRM (HubSpot/Prospector) |
| Generar borradores de propuestas/correos | Agente de IA con plantillas del repo | Kiro / Claude Code |
| Repurposing de contenido (1 post → varios) | Pipeline de IA | Agente + plantillas |
| Métricas semanales del embudo | Hoja que se actualiza sola / script | Sheets + script |
| Recordatorios de facturación / PILA | Calendario + automatización | Calendar + Zapier/Make |
| Flujos entre apps (form → CRM → email) | Conectores | **n8n** (open source, self-host = $0), Make/Zapier (free tier) |

> **Tu ventaja:** ya tienes el foso técnico (FastAPI, agentes). Automatizar lo tuyo es además **práctica + casos demostrables** para vender automatización a clientes.

## 4. Regla anti-distracción (coach)

No caigas en "montar herramientas" como forma de procrastinar. La prioridad real es **facturar** (Workana + clientes B2B). Automatiza solo lo que hoy te quita tiempo de vender o entregar. Todo lo demás, después.

## Pendientes de esta sección

- [ ] Decidir CRM definitivo (probar el Prospector como CRM 2 semanas).
- [ ] Medir consumo real del Prospector en 1 job → costo por lead.
- [ ] Elegir 1–2 tareas propias para automatizar primero (sugerido: seguimiento de leads + borradores de propuesta).
- [ ] Evaluar n8n self-hosted vs Make/Zapier free para flujos.
