# 📋 Checklist de Pendientes (Dashboard único)

> Tablero único de tareas abiertas, consolidado de todo el repo. Última actualización: **4-jul-2026**.
> Estado: ✅ hecho · ⏳ en curso / esperando · 🔴 abierto / sin empezar · 🟡 requiere tercero.

## 🔥 Prioridad ALTA (mueven ingresos esta semana)

| Estado | Pendiente | Detalle / dónde |
|--------|-----------|-----------------|
| ⏳ | **Catalina / Prospector — avanzar la oportunidad** | Clienta potencial. Ya hubo 1 reunión + prueba genérica; **ICP pendiente**. Aplicar Módulos 4 y 5. Ver [`proyectos/catalina-prospector/`](../proyectos/catalina-prospector/README.md) |
| 🔴 | **Correr job de prueba con datos públicos de TBBC** | Para afinar el Prospector (triggers/geo-fit/copy) y medir costo por lead ANTES de re-reunirse con Catalina. Ver [contexto-cliente](../proyectos/catalina-prospector/00-contexto-cliente.md) |
| 🔴 | **Definir pricing del Prospector para Catalina** | Sin costo por lead medido, cotizar es adivinar. Para el piloto: **precio cerrado**, no por lead. Ver [`costo-por-lead.md`](../docs/tecnico/costo-por-lead.md) |
| ⏳ | **Workana — esperar validación de la cuenta** | Membresía pagada. Una vez activa, empezar a postular. Ver [`workana/canal-workana.md`](workana/canal-workana.md) |
| 🔴 | **Workana — aplicar cambios al perfil** | Cambiar título, agregar el Prospector, subir tarifa, pegar "Sobre mí", sumar proyectos. Ver [`workana/perfil-workana-analisis.md`](workana/perfil-workana-analisis.md) |

## 🔥🔥 CRÍTICO — Situación contractual y sociedad (nuevo, 4-jul-2026)

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ✅ | **Contrato recibido y analizado** | Cláusulas clave en [`situacion-contractual-y-sociedad.md`](situacion-contractual-y-sociedad.md) §2. Hallazgo: **la IP del Prospector es de la contratante (cláusula 8ª)** |
| 🔴 | **Definir tu producto propio como build NUEVO e independiente** | No puedes vender el Prospector de la contratante. Vía B = producto nuevo, arquitectura propia, nombre nuevo, respetando confidencialidad (7ª, 2 años). Guía técnica: [`arquitectura-y-paradigmas.md`](../docs/tecnico/arquitectura-y-paradigmas.md) |
| ⏳ | **ECC — evaluado (cherry-pick)** | Tiene **adaptador Kiro** (`./install.sh`). Instalar SELECTIVO: steering base + skills backend/python + hooks quality-gate/tests/security. Ver [`evaluacion-ecc.md`](../docs/tecnico/evaluacion-ecc.md) |
| 🔴 | **Conectar MCPs del build** | Supabase/Postgres + Context7 + (Tavily/Playwright por fase) para que los agentes tengan herramientas. Ver [`kiro-guia-practica.md`](../docs/tecnico/kiro-guia-practica.md) §4 |
| 🔴 | **Activar automatizaciones (hooks) de Kiro** | quality-gate + tests-on-save + secret-scan + extract-patterns. Ver [`kiro-guia-practica.md`](../docs/tecnico/kiro-guia-practica.md) §3 |
| 🟡 | **Abogado laboral — reclamar pago incompleto** | Terminación sin aviso de 15 días (incumple 3ª) + pago incompleto → te deben honorarios causados. ¿"Contrato realidad"? |
| ✅ | **Catalina — situación legal aclarada** | Contacto propio (Popayán), NO cliente de la contratante → cláusula 9ª N/A. Vía libre con build independiente (cláusula 7ª) |
| 🔴 | **Decidir sobre la oferta del 15%** | Coherente con que el IP es de ellos, pero economía pobre (techo ~$300–400k COP/mes). Recomendación: **A (producto propio) + D (cobrar lo adeudado)**. Ver análisis |

## 🟡 Requieren un tercero (no resoluble por IA)

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| 🟡 | **Sesión con un contador** | Confirmar IVA (no responsable bajo 3.500 UVT ≈ COP $183,3M), RST sí/no, flujo de exportación de servicios, y valor oficial de UVT 2026. Ver [`facturacion-y-contratos-colombia.md`](facturacion-y-contratos-colombia.md) |
| 🟡 | **Asesoría legal Habeas Data** | Para prospección B2B a escala (Ley 1581/2012 + Ley 1266/2008 + Decreto 1377/2013; autoridad: SIC). Ver [validación §7](../docs/validacion/validacion-fuentes.md) |
| 🟡 | **Abogado IP/comercial — límites del build independiente** | IP ya resuelto (es de la contratante). Pregunta abierta: ¿qué tan distinto debe ser tu nuevo build para no rozar confidencialidad (cláusula 7ª, 2 años)? Ver [`situacion-contractual-y-sociedad.md`](situacion-contractual-y-sociedad.md) |
| ✅ | **Costo por lead — RESUELTO con datos reales** | ~$155–190 COP marginal, ~$290 COP a plena capacidad; stack $108/mes; tope Hunter ~1.500 contactos. Ver [`costo-por-lead.md`](../docs/tecnico/costo-por-lead.md) |

## 🛒 Canal Etsy — productos digitales (nuevo, 5-jul-2026)

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ✅ | **Nicho Etsy elegido y validado** | Sistema financiero STR/Airbnb en Google Sheets (multi-propiedad + fiscal). Ver [`etsy/producto-01-short-term-rental.md`](etsy/producto-01-short-term-rental.md) |
| ✅ | **Validación de mercado** | Precios $16–25 reales, valor "sustituir software $10–50/mes", KPIs (ADR/Occupancy/RevPAR) y ángulo fiscal Schedule E confirmados. Volumen exacto sin dato duro (paywall) — inferido |
| ⏳ | **Confirmar blueprint del producto #1** | Features, estilo (Minimalista Ejecutivo), precio ~$17–19. Falta OK del fundador |
| 🔴 | **Kiro entrega spec de fórmulas + CSV base** | Todas las pestañas (Dashboard, Bookings, Expenses, P&L, Tax, bonus) |
| 🔴 | **Montar Sheet + mockups + listing (título/13 tags/descripción + disclaimers)** | Incluir disclaimer fiscal y de marca Airbnb (riesgo trademark) |

## ⚖️ Repo del prospector construido bajo contrato (alerta IP)

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ⚠️ | **`ia_lead_prospector` = IP de la contratante** | Clonado como referencia. **NO reutilizar** su código/arquitectura/SOPs para el build nuevo ni para Catalina (cláusulas 7ª y 8ª). Ver [`situacion-contractual-y-sociedad.md`](situacion-contractual-y-sociedad.md) |

## 🏷️ Marca / Identidad

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ⏳ | **Elegir nombre del emprendimiento** | El fundador definirá "en estos días". Top candidatos en [`marca-naming.md`](marca-naming.md) |
| ⏳ | **Naming — RESET (Ronda 5)** | El fundador rechazó todos los candidatos (Rondas 1–4). Pendiente: responder las 6 preguntas de dirección para una Ronda 6 dirigida. Ver [`marca-naming.md`](marca-naming.md) Ronda 5 |
| 🔴 | **Validar el nombre elegido** | 3 chequeos: dominio (.ai/.com/.co) + marca (SIC) + handles de redes. Kiro puede correr la verificación web cuando haya 2–3 finalistas |
| 🔴 | **Definir perfil de Yulieth + nombre de marca** | Para completar [`presentacion-fundadores.md`](../docs/fundamentos/presentacion-fundadores.md) (espacio `[ ]`) |
| 🔴 | **Pulir prueba social pública** | LinkedIn + GitHub con casos visibles (el Prospector). Ver [validación §5](../docs/validacion/validacion-fuentes.md) |

## ⚙️ Producto / Operación

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| 🔴 | **Medir consumo real del Prospector en 1 job** | (Duplica el 🟡 de arriba: es el número que desbloquea el pricing) |
| 🔴 | **Decidir CRM (probar el Prospector como CRM)** | Dogfooding 2 semanas + hoja de embudo. Ver [`productividad-y-automatizacion.md`](productividad-y-automatizacion.md) |
| 🔴 | **Automatizar 1–2 tareas propias** | Sugerido: seguimiento de leads + borradores de propuesta |
| 🔴 | **Verificar geo-fit del "Modo Rápido"** | Cambio reciente (v3.14) con riesgo de falsos positivos. Ver [`prospector.md`](../docs/tecnico/prospector.md) §8 |

## 📚 Base de conocimiento

| Estado | Pendiente | Detalle |
|--------|-----------|---------|
| ✅ | 4 pilares + 5 Módulos del Vendedor Híbrido | [`docs/fundamentos/`](../docs/fundamentos/00-vision-y-enfoque.md) |
| ✅ | Perfil del fundador + presentación de fundadores | [`perfil-fundador.md`](../docs/fundamentos/perfil-fundador.md) |
| ✅ | Documentos técnicos (Prospector, stack SDLC, hacks de IA, modelo de costo por lead) | [`docs/tecnico/`](../docs/tecnico/prospector.md) |
| ✅ | Validación de fuentes (re-verificada jul-2026) | [`validacion-fuentes.md`](../docs/validacion/validacion-fuentes.md) |
| ✅ | Estrategia completa (Workana, facturación, hoja de ruta, naming, propósitos) | `estrategia/` |
| 🔴 | `docs/fuentes/` — PDFs/guías originales | Aún sin subir al repo (opcional; el contenido ya está sintetizado) |

## ✅ Hitos ya cerrados (resumen)

- Base de conocimiento consolidada y validada (4 pilares + técnico + validación + estrategia).
- Marca del antiguo empleador retirada del repo; producto renombrado a **el Prospector**.
- Re-verificación web jul-2026: precios de APIs, marco tributario y legal confirmados; naming re-analizado.
- Naming: técnicas + lista negra verificada + top candidatos + Ronda 3 crítica.
- Presentación de fundadores + 2 casos de éxito.

---

> **Regla del coach:** este checklist se revisa cada semana. La prioridad SIEMPRE es lo que mueve ingresos (Catalina/Prospector + Workana). Lo demás se ordena debajo.
>
> 📌 *Nota de contexto: el proyecto SEO de TBBC lo maneja el fundador aparte, fuera de este repo. Aquí "Catalina" figura como clienta potencial del Prospector para su otro emprendimiento.*
