# Agencia de IA — Repositorio Central

Este repositorio es la **fuente de la verdad** del negocio, estructurado bajo el marco operativo **EOS (Traction)** y dividido en dos grandes líneas de producto.

> 📖 **¿Primera vez aquí (humano o IA)?** Lee
> [`01_Gobernanza_EOS/05_estado_del_negocio_manifiesto.md`](01_Gobernanza_EOS/05_estado_del_negocio_manifiesto.md)
> primero — la fotografía completa: estructura de los 3 pilares + la historia
> de cómo llegamos aquí y hacia dónde vamos. Este README es solo el índice de
> navegación.

## Estructura de Navegación

```text
.
├── README.md                 ← Índice maestro
├── AGENTS.md                 ← Reglas de sistema para agentes de IA
├── CLAUDE.md
│
├── 01_Gobernanza_EOS/        ← ESTRATEGIA, REGLAS Y BACKLOG
│   ├── 00_vision_y_principios.md   (Mentalidad, las 3 reglas de oro, perfiles de fundadores)
│   ├── 01_entorno_y_operacion.md   (Reglas técnicas, perfiles de Kiro/Antigravity)
│   ├── 02_backlog_y_rocas.md       (Issues List EOS: pendientes y bitácora de decisiones — LEER PRIMERO)
│   ├── 03_protocolos_comunicacion.md (Prompting XML, antipsicofancia)
│   └── 04_eos_vto_agencia.md       (V/TO — Vision/Traction Organizer de la agencia)
│
├── 02_Lineas_de_Producto/    ← DOCUMENTACIÓN/ARQUITECTURA (el código real ya NO vive aquí, ver abajo)
│   ├── Inbound_AI_SDR/       (Línea 1: docs; código real de ARTF en artf-pipeline-app/,
│   │   └── docs/               repo hermano — ver 03_Clientes_y_Casos/02_Cliente_ARTF/)
│   │
│   └── Outbound_Prospector/  (Línea 2: docs — Arquitectura y flujos del Motor 1-4;
│       └── docs/               código real en outbound-prospector-app/, repo hermano,
│                                extraído el 20-ago-2026 preservando su historia de git)
│
├── (repos hermanos, mismo padre proyecto_negocio_doscaras/, cada uno con su propio graphify)
│   ├── artf-pipeline-app/        ← código real Inbound_AI_SDR (Next.js, cliente ARTF)
│   └── outbound-prospector-app/  ← código real Outbound_Prospector (Python, cliente TBBC)
│
├── 03_Clientes_y_Casos/      ← OPERACIÓN Y LABORATORIOS
│   ├── 01_Cliente_TBBC/        (Catalina Rúa — piloto Outbound Prospector)
│   └── 02_Cliente_ARTF/        (Andrés Resuelve Tus Finanzas — análisis de arquitectura,
│                                 migración de CRM a Supabase, contexto EOS del cliente)
│
└── .kiro/                    ← Configuración de Entorno Kiro
```

## Protocolo Anti-Confusión (EOS)

1. **La verdad del código vive en `02_Lineas_de_Producto`**. Si un documento en `docs/` contradice a `src/`, el código gana.
2. Todo nuevo problema, idea técnica o decisión de arquitectura debe registrarse en `01_Gobernanza_EOS/02_backlog_y_rocas.md` como un **Issue/Roca**.
3. **El enfoque de la Agencia:** Vendemos **resultados** (ganar dinero, ahorrar tiempo, ahorrar dinero), no vendemos horas ni "scripts". 
