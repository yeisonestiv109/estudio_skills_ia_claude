# Guía Definitiva: Arquitectura de Memoria para IA (Obsidian + Graphify)
**Propósito:** Eliminar los errores de *Rate Limit* (Too many requests) y darle al agente de IA (Kiro / Claude) un contexto infinito y estructurado usando Obsidian como estado y Graphify como mapa neuronal.

---

## FASE 1: La Estructura de Carpetas en Obsidian (Patrón "LLM Wiki")
Olvídate de Obsidian como un bloc de notas. Configúralo como una base de datos para la IA. Ve a tu bóveda (vault) de Obsidian y crea exactamente esta estructura de carpetas:

```text
📁 Boveda_Proyecto/
 ├── 📁 00-Contexto/        # (El cerebro a corto plazo) Aquí va el Handoff diario.
 ├── 📁 10-Fuentes_Raw/     # (El basurero) PDFs, transcripciones, extractos de web sueltos.
 ├── 📁 20-Wiki_Conceptos/  # (La verdad) Notas atómicas, sintetizadas y limpias.
 ├── 📁 40-Sistema/         # Logs, plantillas y el archivo CLAUDE.md.
 └── 📁 50-Media/           # Imágenes y diagramas.
```
*Regla de Oro:* Kiro **NUNCA** debe leer la carpeta `10-Fuentes_Raw` de golpe. Kiro lee el `00-Contexto/` para saber en qué están trabajando hoy, y busca en `20-Wiki_Conceptos/` si necesita recordar un concepto (como el "Abismo Junior").

---

## FASE 2: Metadatos y el Archivo Maestro (CLAUDE.md)
Para que la IA no tenga que leer todo el texto de una nota buscando de qué trata, usa **YAML Frontmatter** en la primera línea de TODAS tus notas en Obsidian. 

**1. Plantilla obligatoria para tus notas:**
```yaml
---
tipo: concepto
estado: consolidado
tags: [arquitectura, motor-2]
fecha: 2026-07-09
---
# Título de tu nota...
```

**2. Crea el archivo `CLAUDE.md` en la raíz de tu proyecto:**
Este es el archivo más importante. Cuando Kiro/Claude se despierte, leerá esto primero.
Crea un archivo llamado `CLAUDE.md` (junto a tu package.json o raíz) con este contenido:
```markdown
# Reglas de Interacción para Kiro/Claude
1. Eres el arquitecto de "El Prospector".
2. **Uso de Memoria:** Nunca busques a ciegas. Si necesitas contexto sobre el mercado o decisiones pasadas, busca en la carpeta de Obsidian `/20-Wiki_Conceptos/` usando los metadatos (ej. tags).
3. **Protocolo Handoff:** Al final de nuestra sesión, TE ORDENARÉ crear un "Handoff". Escribirás un resumen de 3 viñetas en `/00-Contexto/estado_actual.md` detallando qué código hiciste y qué quedó pendiente.
4. **Mapa de Código:** Antes de editar múltiples archivos de código, lee el archivo `graph.json` generado por Graphify.
```

---

## FASE 3: Instalación de Graphify (El Mapa Neuronal del Código)
Graphify usa *Tree-sitter* para leer tu código localmente y crear un mapa. Esto evita que Kiro tenga que leer archivos crudos enormes.

**Paso 1: Instalación (Abre tu terminal de Windows / PowerShell)**
La forma más limpia de instalar la herramienta oficial en Python es mediante `uv` (o `pip`):
```bash
# Opción recomendada si tienes pip instalado:
pip install graphifyy
# (Nota: El paquete oficial lleva doble 'y' al final)
```

**Paso 2: Registrarlo con la IA**
Ejecuta este comando en la terminal para que configure los hooks necesarios:
```bash
graphify install
```

**Paso 3: Generar el Grafo (El paso mágico)**
Ve a la carpeta raíz de tu código (donde están tus carpetas y archivos `.py` o `.ts`) y ejecuta:
```bash
graphify .
```
*(Si tienes carpetas que no quieres escanear como `node_modules`, crea un archivo `.graphifyignore` antes).*

---

## FASE 4: Corroboración (¿Cómo saber que quedó perfecto?)
Antes de poner a Kiro a tirar código, valida que el ecosistema funciona:

1. **Prueba de Graphify:** Ve a la raíz de tu proyecto. Graphify debió haber creado una carpeta llamada `graphify-out/`. Ábrela. Dale doble clic al archivo `graph.html`. Si se abre un mapa interactivo en tu navegador con bolitas (nodos) conectando tus archivos de código, **Graphify funcionó a la perfección**. Kiro leerá el archivo `graph.json` que está ahí mismo.
2. **Prueba de Obsidian (Amnesia Cero):** Abre un chat COMPLETAMENTE NUEVO en Kiro. Dile exactamente esto: 
   > *"Kiro, lee el archivo `00-Contexto/estado_actual.md` y mi archivo `CLAUDE.md`. Dime en qué nos quedamos ayer."*
   Si Kiro te responde perfectamente sin gastar miles de tokens y sin errores de *Rate Limit*, has configurado el sistema de IA más potente posible para 2026.
