# 03 · Contexto del Proyecto: Andrés Resuelve Tus Finanzas (ARTF)

> *Fuente de verdad sobre el Frente 2: Inbound AI SDR y la alianza estratégica de mentoría con Javier y Catalina.*

## 1. Naturaleza de la Alianza (El Intercambio)

El proyecto actual funciona bajo un esquema de intercambio de valor (duración inicial: 1 mes):
- **El Brazo Tecnológico (Yeison y Gaby):** Aportan su expertise en Backend y Sistemas Agénticos para profesionalizar y escalar la infraestructura tecnológica de ARTF (la empresa de Javier, Catalina y Andrés).
- **La Mentoría de Negocio (Javier y Catalina):** A cambio, asesoran a Yeison y Gaby en la estructuración de su propia agencia de IA, definiendo su oferta comercial (que abarcará tanto Inbound/AI SDR como Outbound/El Prospector) y su modelo de negocio para salir al mercado.

## 2. El Cliente: Andrés Resuelve Tus Finanzas (ARTF)

- **Modelo de Negocio:** Infoproductos y mentoría financiera B2C (High-Ticket).
- **Tracción:** Crecimiento explosivo desde mayo de 2026. Escalando en la ruta de $0 a $10K USD/mes.
- **Flujo de Leads:** 50 a 100 leads diarios entrantes a través de DMs de Instagram (tráfico orgánico y Meta Ads).
- **El Dolor (Cuello de Botella):** La gestión manual de los leads causa pérdida de ventas por falta de inmediatez y saturación operativa.

## 3. Marco Operativo de Negocio (Metodología EOS / Traction)

ARTF opera rigurosamente bajo el sistema EOS (*Entrepreneurial Operating System*):
- **Gobernanza:** Foco en los 6 componentes (Visión, Personas, Datos, Problemas, Procesos y Tracción).
- **Datos (Scorecard):** Decisiones basadas en el *Daily Metrics Scorecard* (costo por lead, ROI, etc.).
- **Tracción:** Trabajo enfocado en "Rocas" (prioridades a 90 días) y reuniones semanales tácticas (Pulso L10).
- **Metodología de Desarrollo:** Sprints semanales con reuniones *Daily* de 15 minutos.

## 4. Roles del Equipo ARTF

- **Visionario / Experto:** Andrés (Pipe)
- **Estrategia Comercial:** Catalina
- **Arquitecto de Ops e IA:** Javier
- **Setters:** Gaby (Humana) + Setter IA (Bot)
- **Closers:** Catalina, Pipe y Andrés
- **Ingeniería / Desarrollo:** Yeison y Gabyota

## 5. Arquitectura Técnica (Situación Actual vs. Reto)

Javier construyó un prototipo funcional ("con plastilina") que demostró la viabilidad, pero que ha llegado a su límite de escala y debe ser profesionalizado.

**Stack Actual (El Prototipo):**
1. **Captación:** Meta Ads / Instagram → ManyChat (actúa como mediador antibaneo).
2. **Setter IA (Bot):** Alojado en un Cloudflare Worker. Usa un LLM (prompted con el playbook de ventas) para pre-calificar.
3. **CRM (Cuello de botella):** Pestaña de Google Sheets con >5,700 registros. Insostenible a esta escala.
4. **Bridge (Conector):** Script en Google Apps Script que escribe los leads desde Cloudflare a Sheets.
5. **Formulario Closer:** Web app ligera para que los vendedores lean/actualicen datos sin entrar al Sheets.

**El Objetivo Técnico Inmediato:**
Transicionar de scripts frágiles (Google Sheets, Apps Script) a una arquitectura de software formal, escalable y robusta. 
*Nota: Se está a la espera del Documento de Arquitectura RTF (basado en Views & Beyond) por parte de Javier para iniciar el diseño de la nueva infraestructura.*
