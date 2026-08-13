# Agencia de IA — Repositorio Central

Este repositorio es la **fuente de la verdad** del negocio, estructurado bajo el marco operativo **EOS (Traction)** y dividido en dos grandes líneas de producto.

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
├── 02_Lineas_de_Producto/    ← CÓDIGO Y DOCUMENTACIÓN TÉCNICA
│   ├── Inbound_AI_SDR/       (Línea 1: Atención autónoma Inbound — scaffold vacío;
│   │   ├── docs/              el código real de ARTF hoy vive fuera del repo en
│   │   ├── src/                Cloudflare Workers/ManyChat; los docs y scripts de
│   │   └── tests/               migración están en 03_Clientes_y_Casos/02_Cliente_ARTF/)
│   │
│   └── Outbound_Prospector/  (Línea 2: Caza activa Outbound)
│       ├── docs/             (Arquitectura y flujos del Motor 1-4)
│       ├── src/               (Código Python, hexagonal)
│       ├── tests/             (Suite Pytest)
│       └── revision_manual/   (Cola de revisión manual persistente, human-in-the-loop)
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
