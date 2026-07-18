# Perfil Profesional · Enfoque en Emprendimiento Tecnológico

**Fuente de la verdad** del proyecto de vida en negocios y emprendimiento de Yeison. Consolida mentalidad, principios de valor, estrategia de ventas, conocimiento técnico y planes de ejecución, para que el fundador y cualquier agente de IA trabajen con el mismo contexto.

## Tesis del proyecto

Usar la IA como **vehículo** para resolver problemas de alto valor a empresas, posicionándonos como **Arquitectos Digitales** (vendemos resultados, no tareas). Modelo de **dos velocidades**: el freelance financia y da experiencia (corto plazo); los proyectos B2B (ej. el Prospector) construyen el patrimonio (medio-largo plazo).

## Mapa del repositorio (estructura de Poda Sináptica)

```
.
├── README.md                         ← estás aquí (índice / fuente de la verdad)
├── AGENTS.md                         ← guía corta para agentes de IA
├── CLAUDE.md                         ← reglas de comportamiento del agente
│
├── 00-Cortex_Operativo/              ← MEMORIA DE TRABAJO (leer primero)
│   └── estado_actual.md              ← handoff diario + objetivo de hoy
│
├── 01-Fundamentos_Estrategia/        ← ADN del proyecto (estrategia + fundamentos)
│   ├── 00-vision-y-enfoque.md · 01-mentalidad · 02-principios-valor
│   ├── 03-estrategia-ventas-prospeccion.md  ← 5 Módulos del Vendedor Híbrido
│   ├── 04-ia-conceptos-y-modelos-negocio.md · perfil-fundador · presentacion-fundadores
│   ├── reglas-del-juego · propositos-y-mentores · hoja-de-ruta-freelance-a-b2b
│   ├── facturacion-y-contratos-colombia · modelo-agencia-ia-unipersonal
│   ├── productividad-y-automatizacion · situacion-contractual-y-sociedad
│   ├── marca-naming · pendientes-checklist.md  ← 📋 dashboard de tareas
│
├── 02-Protocolos_Comunicacion_IA/    ← estándar de prompts XML + antipsicofancia
│   └── guia_prompting_xml.md
│
├── 10-Memoria_Consolidada/           ← NEOCÓRTEX TÉCNICO (fuente de verdad para código)
│   ├── modelos_dominio_core.md       ← contratos Pydantic del Core (Motores 1-2)
│   ├── flujos_motor_1_y_2.md         ← flujo Enrutador Dinámico + Cascada de Triggers
│   ├── resiliencia_motor_2.md        ← anti-alucinaciones, WAF, retries
│   ├── analisis_cruzado_mercado.md · contexto_clientes_y_oportunidades.md
│   ├── resumen_ejecutivo_arquitectura.md · guia_configuracion_memoria_ia.md
│   ├── tecnico/                      ← diseño técnico consolidado (incl. diseño Motores)
│   │   ├── prospector-m1-m2-design.md · arquitectura-y-paradigmas.md
│   │   ├── stack-sdlc-ia.md · stack-y-orquestacion.md · costo-por-lead.md
│   │   ├── evaluacion-ecc.md · hacks-agentes-ia.md · kiro-guia-practica.md
│   ├── validacion/
│   │   └── validacion-fuentes.md     ← precios de APIs + Habeas Data verificados
│   └── proyecto-catalina/            ← PRIMERA OPORTUNIDAD B2B (cliente Catalina Rúa)
│       ├── README.md · 00-contexto-cliente.md
│       ├── 01-playbook-m4-entrevista.md · 02-playbook-m5-relacion.md
│
├── 20-Bitacora_Decisiones/           ← HIPOCAMPO (registro del porqué de las decisiones)
│   └── 2026-07-12-blindaje-motor-2.md
│
├── 99-Archivo_Muerto/                ← EL OLVIDO (no leer; borradores viejos)
│
├── src/ · tests/                     ← código del Prospector (Motores 1-2 completos)
└── .kiro/                            ← skills, hooks, steering, specs, settings, graphify
```

## Por dónde empezar

1. Lee `00-Cortex_Operativo/estado_actual.md` — el estado de hoy y el objetivo.
2. Interioriza el ADN en `01-Fundamentos_Estrategia/` (visión, reglas, 5 Módulos de venta).
3. Para escribir código, la única fuente de verdad es `10-Memoria_Consolidada/` — contratos en `modelos_dominio_core.md` y flujos en `flujos_motor_1_y_2.md`.
4. Diseño técnico ampliado en `10-Memoria_Consolidada/tecnico/` (incluye `prospector-m1-m2-design.md`).
5. Datos de mercado y legal verificados en `10-Memoria_Consolidada/validacion/validacion-fuentes.md`.
6. La oportunidad B2B viva está en `10-Memoria_Consolidada/proyecto-catalina/`.

> **Nota (12-jul-2026):** las carpetas raíz `docs/`, `estrategia/` y `proyectos/` fueron consolidadas dentro de la estructura numerada. Los duplicados se descartaron (recuperables vía historial de git). La estructura numerada (00/01/02/10/20/99) es la única canónica.

## Principios operativos

- Validar antes de afirmar (citar fuentes y fecha).
- Ser crítico, no complaciente (evitar la sycophancy de la IA).
- Vender resultados, no tareas (3 reglas de oro + Arquitecto Digital).
- Respetar el marco legal (Habeas Data Ley 1581/2012 en scraping y cold email).

## Estado

- ✅ Base de conocimiento consolidada y validada (jun-2026, re-verificada 4-jul-2026): 4 pilares + técnico + validación + estrategia.
- ✅ 5 Módulos del Vendedor Híbrido, facturación (Colombia) y hacks de IA incorporados.
- 🧹 **Purga greenfield (7-jul-2026):** el repo se enfocó exclusivamente en el **Prospector Vía B**. Se removieron los canales Vía A (Workana, Etsy, guía freelance) y el doc `prospector.md` (IP de la contratante). Recuperable vía historial de git.
- ✅ Cabina de Mando documentada: entorno, Skills y Hooks nativos + MCP (ver `.kiro/settings/environment_setup.md`).
- ⏳ Tareas abiertas centralizadas en el [Checklist de Pendientes](estrategia/pendientes-checklist.md). Prioridad: avanzar **Catalina/Prospector** y el build del producto.
