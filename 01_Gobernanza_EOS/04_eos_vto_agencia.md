# EOS en Nuestra Agencia — Framework Operativo

> Documento maestro de implementación del Entrepreneurial Operating System (EOS/Traction) en la Agencia de AI RevOps.
> Basado en el libro Traction de Gino Wickman. **Este documento es el V/TO (Vision/Traction Organizer) de la agencia.**

---

## 0. Por qué EOS (y por qué ahora)

Usamos EOS porque es el mismo lenguaje que usan nuestros clientes activos (ARTF lo opera con L10, Scorecard y Rocas). No tendría sentido venderle a un cliente un sistema de gestión que nosotros mismos no aplicamos. Además, resuelve exactamente las 5 frustraciones que sentimos ahora como equipo fundador: falta de sistema, dificultad para priorizar, y ausencia de métricas claras de tracción.

> **Regla de adopción:** No implementamos EOS de golpe. Empezamos con las 3 herramientas de mayor impacto ahora mismo: **V/TO (Visión)**, **Scorecard (Datos)** y **Rocas (Tracción)**. El resto se suma conforme el equipo crece.

---

## 1. V/TO — Vision/Traction Organizer

### 1.1 Valores Centrales (ADN del equipo)

Principios atemporales. Si alguien no los vive, no encaja.

| # | Valor | Lo que significa en práctica |
|---|-------|------------------------------|
| 1 | **Antipsicofancia** | Decimos la verdad aunque incomode. Cuestionamos supuestos, exponemos riesgos, no aplaudimos por aplaudir. |
| 2 | **Precisión antes que velocidad** | No inventamos datos ni estrategias sin fuente. Si no lo sabemos, lo decimos y lo investigamos. |
| 3 | **Resultados, no tareas** | Todo entregable conecta con las 3 Reglas de Oro (ganar dinero · ahorrar tiempo · ahorrar dinero). Nunca vendemos horas. |
| 4 | **Ejecución sobre perfección** | MVP limpio > arquitectura perfecta que no llega. Validamos en vivo antes de escalar. |
| 5 | **Aprendizaje perpetuo** | El mercado siempre sabe más que nosotros. Primero escuchamos, luego recomendamos. |

### 1.2 Enfoque Central (Core Focus)

**Propósito:** Ayudar a negocios de High-Ticket y B2B a tapar la fuga de ingresos causada por la lentitud humana en el ciclo de ventas, usando IA y datos bien estructurados.

**Nuestro nicho (lo que hacemos mejor que nadie):** Implementar sistemas de IA que convierten el caos operativo de ventas en procesos medibles, rápidos y escalables — sin crear dos problemas nuevos.

> ⚠️ **Síndrome del objeto brillante:** cualquier oportunidad que no encaje en este nicho (e-commerce, chatbots genéricos, automatización de marketing sin conexión a ventas) se declina o se pospone.

### 1.3 Meta a 10 años (BHAG)

> "Ser la firma de referencia en LATAM para la implementación de sistemas de AI RevOps en negocios High-Ticket, con al menos 50 clientes activos y un producto SaaS propio que genere MRR sostenible."

### 1.4 Estrategia de Marketing

- **Mercado objetivo ("La Lista"):** Mentores, consultores e infoproductores High-Ticket (ticket ≥ $1,000 USD) en LATAM que tienen entre 3 y 15 personas en su equipo de ventas y usan herramientas de gestión artesanales (Sheets, WhatsApp, notas).
- **Los 3 Únicos (diferenciadores):**
  1. Implementamos el sistema completo, no solo la parte técnica — entendemos el negocio primero.
  2. Dejamos el sistema documentado, versionado y con el equipo del cliente capacitado.
  3. Somos los únicos que conectan el AI SDR con el Revenue Data Core (Scorecard EOS) desde el día 1.
- **Proceso probado:** Diagnóstico → Arquitectura → Migración → Integración IA → Entrenamiento.
- **Garantía (en construcción):** Definir una garantía de ROI medible en las primeras 8 semanas de implementación.

### 1.5 Panorama a 3 años (Dec 2028)

- Al menos **3 clientes activos** con sistema implementado y en producción.
- **MRR de mantenimiento/soporte** cubriendo los gastos operativos de la agencia.
- **Producto Inbound AI SDR** validado con ARTF y replicable a nuevos clientes sin partir de cero.
- Yeison con portafolio técnico público (LinkedIn + GitHub) que demuestre implementaciones reales.
- Yulieth Gabriela liderando los procesos de onboarding y retención de clientes.

### 1.6 Plan a 1 año (objetivos 2026)

1. **Completar la implementación con ARTF** (migración BD + Formulario Closer + AI SDR estable en producción).
2. **Validar la propuesta de valor** con 1 cliente adicional más allá de ARTF (referido o frío).
3. **Documentar el "Playbook de Implementación"** reproducible para no empezar de cero en cada cliente.
4. **Definir el nombre y marca de la agencia.**
5. **Cerrar el V/TO completo** (en este momento está en construcción; iterar en cada reunión L10).

### 1.7 Rocas Trimestrales (Q3 2026 — ago/sep/oct)

| # | Roca | Dueño | Resultado esperado |
|---|------|-------|-------------------|
| 1 | **Decisión de BD de ARTF aprobada por Javier** | Yeison | Reunión de alineación técnica hecha, Supabase aprobado o alternativa seleccionada |
| 2 | **Migración datos ARTF a Supabase** | Yeison | CRM migrado, Worker apunta a Supabase, Sheets se convierte en backup |
| 3 | **Formulario Closer v1 en producción** | Yeison + Gabriela | El equipo de ARTF opera con el nuevo formulario web sin regresar a Sheets |
| 4 | **Scorecard de la agencia funcionando** | Gabriela | Tenemos nuestras propias métricas semanales (ver sección Scorecard) |

### 1.8 Lista de Problemas (Issues List actual)

*(Registrar aquí los obstáculos reales, no los que creemos que podríamos tener)*

- [ ] No tenemos nombre de marca definido → limita el posicionamiento y la credibilidad.
- [ ] El EOS de la agencia está en construcción → sin Scorecard propio no podemos medir si avanzamos.
- [ ] La propuesta de valor de Inbound AI SDR aún no está validada con factura → ARTF es el primer laboratorio.
- [ ] La línea Outbound Prospector (TBBC) está en pausa sin fecha de retorno → consume atención mental.

---

## 2. Scorecard de la Agencia (Datos)

> Máximo 10 indicadores. Son **adelantados** (predicen el futuro), no históricos. Se revisan cada lunes en el Pulso L10.

| Métrica | Frecuencia | Meta (semana) | Dueño |
|---------|-----------|----------------|-------|
| Horas de trabajo técnico dedicadas a ARTF | Semanal | ≥ 10h | Yeison |
| Número de funcionalidades de ARTF desplegadas en producción | Semanal | ≥ 1/semana | Yeison |
| Issues (preguntas técnicas) resueltas con Javier/Catalina | Semanal | ≥ 1 cerrada | Gabriela |
| Contactos de prospección nuevos para la agencia | Semanal | ≥ 3 | Gabriela |
| Propuestas enviadas a potenciales clientes | Mensual | ≥ 1 | Ambos |

> **Nota:** estas métricas son un punto de partida. Se ajustan en la primera reunión L10 conjunta.

---

## 3. Estructura del Equipo (Personas)

### El Visionario y el Integrador

En EOS toda empresa tiene un **Visionario** (ideas, relaciones, cultura, visión grande) y un **Integrador** (el que ejecuta, armoniza y hace que las cosas pasen). En esta etapa temprana, ambos fundadores asumen ambos roles, pero es importante identificar hacia dónde va cada uno a medida que crece.

| Rol EOS | Persona | Fortaleza primaria |
|---------|---------|-------------------|
| **Visionario** (tendencia) | Yeison | Arquitectura técnica, detección de oportunidades de producto, relaciones con clientes técnicos |
| **Integradora** (tendencia) | Yulieth Gabriela | Estructura de procesos, onboarding de clientes, retención y seguimiento de acuerdos |

### Cuadro de Responsabilidad (simplificado — etapa 0→1)

| Función | Responsable | 3 Resultados Clave |
|---------|-------------|-------------------|
| **Delivery / Implementación técnica** | Yeison | Sistema funcionando, tests en verde, documentación actualizada |
| **Ventas y relaciones con clientes** | Gabriela | Contactos activos, propuestas enviadas, clientes satisfechos |
| **Administración / Operación** | Gabriela | Backlog actualizado, Scorecard llenado, Issues cerrados |

---

## 4. Pulso de Reuniones — L10 Semanal (formato)

> Objetivo: que la reunión termine con calificación 10/10 de efectividad por parte de ambos fundadores.

**Frecuencia:** Lunes, 60 minutos. **Agenda fija (no negociable):**

| Segmento | Duración | Qué se hace |
|----------|----------|-------------|
| Check-in (Segmento personal) | 5 min | Cada uno comparte: "¿Cómo llego a esta reunión?" |
| Scorecard | 5 min | Revisar métricas. Marcar ✅ o ❌. Los ❌ van a la Issues List |
| Rocas | 5 min | ¿Cómo van las Rocas del trimestre? En curso / En riesgo / Completada |
| Titulares (clientes/equipo) | 5 min | Novedades de clientes y del equipo. Sin resolver — solo reportar |
| To-Do List de la semana pasada | 5 min | ¿Qué prometimos hacer? ¿Lo hicimos? |
| IDS (Identificar, Discutir, Solucionar) | 35 min | Resolver los 2-3 issues más importantes de la semana |
| Calificación de la reunión (1–10) | Opcional | Feedback rápido al final |

**Regla del IDS:** el mayor tiempo va a **Identificar** la causa raíz (no el síntoma). Una vez identificada, se Discute brevemente (sin repetir) y se Soluciona con una tarea concreta con dueño y fecha.

---

## 5. Implementación por Fases (no se absorbe todo de golpe)

| Fase | Cuándo | Qué implementar |
|------|--------|----------------|
| **Fase 0 (hoy)** | Ago 2026 | V/TO borrador, Scorecard básico, Rocas Q3, L10 semanal |
| **Fase 1** | Oct 2026 | People Analyzer simple, Issues List activa, To-Do List en cada L10 |
| **Fase 2** | Ene 2027 | Documentar el primer proceso (Proceso de Implementación de cliente) |
| **Fase 3** | 2027+ | Expandir el equipo con filtro GWC y Cuadro de Responsabilidad completo |

> **Regla de oro de adopción EOS:** "No podemos avanzar más rápido de lo que la empresa puede absorber." Empezamos simple y añadimos capas.
