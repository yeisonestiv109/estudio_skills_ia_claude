# Directrices Globales — Segundo Cerebro

> Documento maestro/steering del sistema de gestión de negocio, proyectos y vida
> personal de Yeisiton, respaldado por NotebookLM. **No reemplaza ni duplica**
> [`01_Gobernanza_EOS/00_vision_y_principios.md`](../01_Gobernanza_EOS/00_vision_y_principios.md)
> (eso sigue siendo la fuente de verdad de visión/negocio) — este documento es la
> capa operativa de CÓMO se organiza y consulta el conocimiento del día a día.
>
> Auditoría del sistema de memoria mismo (hallazgos, señales de salud, y el
> índice del meta-manual reproducible para otros negocios) →
> [`guia_arquitectura_memoria.md`](guia_arquitectura_memoria.md).

## 1. Filosofía operativa — "Lo Aburrido es Oro"

- **Cero herramientas innecesarias.** No se instala ni propone un agente,
  dependencia o servidor MCP nuevo sin un problema de negocio real detrás. Toda
  herramienta nueva viene con la justificación de por qué es la solución más
  simple, no la más impresionante.
- **Predictibilidad sobre perfección.** Si algo se resuelve con un script de
  Python simple, se usa eso — no una feria de agentes.
- **MVP orientado a resultados.** Velocidad y efectividad priman; no se
  sobre-diseña para casos hipotéticos.
- **Protocolo de autocorrección.** Si una acción falla, el primer paso es
  diagnosticar contra estas directrices y contra
  [`01_Gobernanza_EOS/01_entorno_y_operacion.md`](../01_Gobernanza_EOS/01_entorno_y_operacion.md)
  (bugs de entorno ya conocidos) **antes** de pedirle ayuda al usuario.
- **Archivos particionados, nunca un documento gigante.** Un concepto vive en un
  solo archivo pequeño; los índices enlazan, no repiten prosa (misma regla que
  ya rige el código en
  [`estrategia-memoria.md`](../.kiro/steering/estrategia-memoria.md)).

## 2. Mapa de la estructura

Las carpetas nuevas se **fusionaron** con los árboles que ya existían para ARTF
y Prospector, en vez de duplicarlos (regla "un concepto, un lugar").

| Carpeta (ruta real) | Propósito | Notebook NotebookLM |
|---|---|---|
| `04_Segundo_Cerebro/Negocio_General/` | Operativa de negocio transversal (agenda, correo, admin) — no ligada a una línea/cliente | `PROPUESTO` — "Negocio General" |
| `04_Segundo_Cerebro/Desarrollo_Personal/` | Resúmenes de contenido de crecimiento personal | `PROPUESTO` — "Desarrollo Personal" |
| `01_Gobernanza_EOS/Reuniones_Audios_Negocio/` | Transcripciones de mentoría Javier/Catalina (cruza ambas líneas) | `PROPUESTO` — "Mentoría Javier/Catalina" |
| `outbound-prospector-app/docs/notebooklm/` (repo hermano, no `02_Lineas_de_Producto/` — extraído 20-ago-2026) | Contexto/estrategia de la línea Prospector para RAG | `PROPUESTO` — "Outbound Prospector — Contexto y Estrategia". **En pausa por decisión del fundador (21-ago-2026): no crear hasta reanudar el proyecto; al reanudarlo, este notebook es el Paso 1 obligatorio antes de tocar código.** |
| `03_Clientes_y_Casos/02_Cliente_ARTF/Reuniones_Audios/` | Transcripciones de reuniones de negocio ARTF | `IMPLEMENTADO` — "ARTF — Negocio y Reuniones" (`https://notebook.google.com/notebook/c9c609f7-cb64-4929-9273-f60a7f19857e`, 15-ago-2026) |
| *(ya existía)* — notebook técnico ARTF | Arquitectura/DB/esquema — **no** se mezcla con reuniones de negocio | `IMPLEMENTADO` — "ARTF: Arquitectura de Software y Sistema Operativo de Negocio" (`https://notebook.google.com/notebook/ae2ca639-f8f7-48b9-b5b8-526f5ace0a95`) |
| *(nuevo, sin carpeta de repo dedicada)* | Investigación UX/diseño (Deep Research) para el Formulario Closers | `IMPLEMENTADO` — "UX/Diseño — Deep Research" (`https://notebook.google.com/notebook/8614a750-e564-4c75-a189-af4e234ac714`) |
| *(nuevo, sin carpeta de repo dedicada)* | SOP real del setter + contexto de arquitectura actual (ManyChat/Worker/agenda) | `IMPLEMENTADO` — "ARTF — Arquitectura Actual y Rol Setter" (`https://notebook.google.com/notebook/e98171ed-cba6-4da6-9dfc-22cf40820a7f`) |

**Por qué no es 1:1 forzado carpeta↔notebook:** un notebook de NotebookLM rinde
mejor cuando sus fuentes son temáticamente coherentes (mejor grounding de RAG).
Mezclar SQL/triggers con conversaciones de mentoría en el mismo notebook diluye
las respuestas de ambos. Por eso ARTF tiene dos notebooks (técnico ya existente
+ negocio `PROPUESTO`), no uno solo por cliente.

**Estado de los notebooks:** se usa el mismo tri-estado que ya define
`estrategia-memoria.md` para el código — `PROPUESTO` (documentado aquí, no
creado en NotebookLM todavía) → `IMPLEMENTADO` (existe en NotebookLM +
registrado en la librería local vía `add_notebook`). Un notebook `PROPUESTO` se
crea recién cuando llega el primer archivo real a su carpeta — no se crean
cuadernos vacíos de antemano.

## 3. Protocolo de memoria particionada

Extiende, sin duplicar, lo ya establecido para el código en
[`estrategia-memoria.md`](../.kiro/steering/estrategia-memoria.md) y
[`03_protocolos_comunicacion.md`](../01_Gobernanza_EOS/03_protocolos_comunicacion.md):

- **Jerarquía de verdad también aplica aquí:** si un `.md` de una carpeta de
  arriba contradice lo que ya está en `02_backlog_y_rocas.md` o en el código,
  gana `02_backlog_y_rocas.md`/código — se corrige el `.md`, nunca al revés.
- **Un concepto, un lugar.** Antes de crear un archivo nuevo en cualquiera de
  estas carpetas, verificar que el tema no viva ya en `docs/`, en
  `03_Clientes_y_Casos/<Cliente>/`, o en `01_Gobernanza_EOS/`. Si existe, se
  enlaza desde ahí, no se copia.
- **Verificar antes de escribir.** Igual que con el código: no se afirma nada
  sobre negocio/proyectos en estos archivos sin fuente (transcripción real,
  decisión confirmada) — si no está verificado, se marca "sin confirmar".

## 4. Stack tecnológico

Fuente canónica del entorno técnico:
[`01_Gobernanza_EOS/01_entorno_y_operacion.md`](../01_Gobernanza_EOS/01_entorno_y_operacion.md)
(WSL2, Node vía `fnm`, Python vía `uv`, Kiro, git + `gh`) — no se repite aquí.

Lo nuevo específico de este sistema:

- **Obsidian** como vault de lectura/edición de todas las carpetas de este
  documento (vault ya abierto en la raíz del repo, `estudio_skills_ia_claude/.obsidian/`).
- **MCP `notebooklm`** (`PleasePrompto/notebooklm-mcp`, scope `user`, ya
  conectado) — consulta (`ask_question`) y alimentación (`add_source`) de los
  cuadernos de la tabla de arriba. Bugs conocidos y protocolo de verificación
  documentados en `01_entorno_y_operacion.md`, sección "MCP — NotebookLM" — leer
  ahí antes de usar `setup_auth`/`cleanup_data`.

## 5. Roadmap Fase 2 — `PROPUESTO`, no ejecutar todavía

Registro de intención únicamente; sin diseño técnico hasta que el usuario dé luz
verde explícita a esta fase:

- Lectura y organización de agenda y correo.
- Script diario automatizado de noticias de tecnología/sector, con filtro
  crítico anti-ruido publicitario.
- Reglas de `.gitignore` estrictas y completas para credenciales, APIs y datos
  personales (más allá del parche mínimo ya aplicado en esta fase para las
  carpetas de audio — ver `.gitignore` del repo).

## 6. Secuencia acordada

1. **Fase 1 (esto, ✅ completada 14-ago-2026):** estructura de carpetas +
   este documento.
2. **Resolver los 4 gaps de negocio de ARTF** (Juan Manuel sin fecha de pago,
   133 leads sin ManyChat ID, periodicidad del salario, decisión sobre "Oferta
   de Valientes" — ver `01_Gobernanza_EOS/02_backlog_y_rocas.md`) usando el
   audio/notebook que suba el usuario con las respuestas de Javier/Catalina.
3. **Ejecutar el trabajo técnico de ARTF** que esos gaps desbloqueen.
4. **Fase 2** — diseño técnico real de agenda/correo, noticias diarias y
   gitignore completo.
