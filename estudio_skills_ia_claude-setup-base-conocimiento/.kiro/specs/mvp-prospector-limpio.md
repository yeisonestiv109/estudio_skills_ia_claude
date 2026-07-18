# Especificación del MVP — El Nuevo Prospector Propio (Clean Room)
*ID de Spec: spec-mvp-prospector-001*  
*Fecha: 5-jul-2026*  
*Estado: Pendiente de aprobación*

Este documento establece la **fuente de la verdad técnica y funcional** para construir el nuevo motor de prospección B2B independiente de Yeison. Se diseña bajo el principio de **Clean Room** para asegurar el aislamiento de propiedad intelectual frente a la contratante anterior.

---

## 1. Objetivos del MVP (Enfoque en el ROI)

El sistema debe resolver las siguientes necesidades de negocio alineadas con las **3 Reglas de Oro**:
1. **Ganar dinero (Valor del Piloto):** Entregar a Catalina Rúa prospectos hiper-calificados y listos para contactar.
2. **Ahorrar dinero (Margen Operativo):** Mantener un costo marginal menor a **$190 COP** por lead calificado.
3. **Ahorrar tiempo (Automatización):** Reducir a minutos el proceso manual de prospección y redacción de copys en frío.

---

## 2. Requisitos Funcionales Esenciales (Flujo de Prospección)

El MVP implementará un único flujo lineal y determinista para evitar sobre-ingeniería técnica en esta fase de validación comercial:

```mermaid
graph LR
    ICP[1. Definición ICP] --> Discovery[2. Búsqueda Empresas]
    Discovery --> Triggers[3. Extracción Triggers]
    Triggers --> Decisor[4. Identificar Decisor]
    Decisor --> Email[5. Email & Verificar]
    Email --> Copy[6. Copywriter RAG]
```

### Casos de Uso del MVP:
1. **Definición de Campaña e ICP:** El usuario define el perfil del cliente ideal (Industria, Región, Cargos Objetivo y Dolor Operacional).
2. **Descubrimiento de Empresas (Company Discovery):** Buscar en la web hasta 15 empresas reales que cumplan con el perfil.
3. **Búsqueda de Triggers Operacionales:** Identificar hitos de crecimiento, cambios regulatorios o problemas recientes de cada empresa (2025/2026).
4. **Identificación de Tomadores de Decisión:** Encontrar el cargo objetivo (ej. *Director de Operaciones*, *VP de Supply Chain*) en LinkedIn mediante consultas estructuradas de búsqueda.
5. **Enriquecimiento y Verificación de Email:** Obtener el email corporativo directo usando un adaptador verificado (Hunter/Apollo) para mitigar rebotes.
6. **Redacción de Copy RAG:** Generar una secuencia de correo frío en español (máx. 150 palabras) conectando directamente el trigger operacional con la solución propuesta, incluyendo disclaimer de Habeas Data y opt-out.

---

## 3. Criterios de Aceptación Técnicos & Legales (Clean Room)

Para cumplir con el marco de seguridad y confidencialidad exigido por la situación contractual anterior:

### A. Aislamiento de Código e Infraestructura (Clean Room)
* **Cero Reutilización:** Queda estrictamente prohibido usar cualquier fragmento de código, plantillas de base de datos o prompts del repositorio de la contratante (`ia_lead_prospector`).
* **Arquitectura de Dominio Aislada:** La lógica del pipeline se desacopla mediante puertos abstractos. Las llamadas a las APIs externas (Tavily, Hunter, Groq) se implementarán en adaptadores independientes.
* **Base de Datos Propia:** Se diseñará un esquema de base de datos nuevo en Supabase con RLS, estructurando la información del job y de los leads de forma única.

### B. Cumplimiento Legal (Habeas Data)
* **Datos Corporativos:** El sistema priorizará correos corporativos y bases de datos públicas de personas jurídicas.
* **Opción de Baja:** Todo correo generado incluirá una cláusula de baja (opt-out) explícita y transparente.

---

## 4. Plan de Tareas del MVP

- [ ] **Tarea 1:** Definir y documentar el esquema de base de datos propio para Supabase.
- [ ] **Tarea 2:** Implementar la lógica del dominio puro (clases de entidad: `Job`, `Lead`, `Trigger`).
- [ ] **Tarea 3:** Desarrollar los puertos y adaptadores para la integración con APIs externas (Tavily Search y Hunter.io).
- [ ] **Tarea 4:** Programar el orquestador del pipeline lineal y el manejo de reintentos por job.
- [ ] **Tarea 5:** Correr el job de prueba con datos públicos de TBBC para medir y validar el costo por lead exacto.
- [ ] **Tarea 6:** Integrar el piloto de Catalina Rúa una vez definido su ICP comercial.
