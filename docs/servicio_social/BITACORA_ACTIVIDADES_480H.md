# BITÁCORA TÉCNICA DE ACTIVIDADES DE SERVICIO SOCIAL (480 HORAS)

**Institución:** Instituto Politécnico Nacional (IPN)  
**Unidad Académica:** Escuela Superior de Cómputo (ESCOM)  
**Proyecto:** Desarrollo e Implementación del Sistema **RACO (*Risk-Adjusted Capacity Optimizer*)** para la Planeación y Optimización de Oferta Académica Docente  
**Total de Horas Acreditadas:** **480 horas** (6 Reportes Mensuales × 80 horas)  
**Repositorio de Evidencia Técnica:** `raco-escom` (`v1.2.1-hardened`)  

---

## Resumen Ejecutivo de Acreditación Horaria

| Reporte | Periodo | Eje Técnico Principal | Entregables Clave en Repositorio | Horas |
| :---: | :---: | :--- | :--- | :---: |
| **Mes 1** | Reporte 01 | Diagnóstico empírico del SAES, sobrecupos negativos y arquitectura base (**ADR-0001**) | `docs/arquitectura/RACO_Documento_Maestro_Tecnico.pdf`, `core/models.py` | **80 h** |
| **Mes 2** | Reporte 02 | Motor de ingesta y análisis léxico por portapapeles (`M`, `V`, `X`) | `core/parser.py`, `tests/test_parser.py` | **80 h** |
| **Mes 3** | Reporte 03 | Motor matemático de optimización con Cupo Blando ($\tau=2$) y blindaje (**ADR-0002**) | `core/rules.py`, `tests/test_rules.py` | **80 h** |
| **Mes 4** | Reporte 04 | Interfaz analítica en Streamlit, KPIs docentes y Semáforo de Tiras Curriculares | `app.py`, `core/validators.py` | **80 h** |
| **Mes 5** | Reporte 05 | Exportador ejecutivo a Excel (`.xlsx`) de 4 pestañas y sello criptográfico SHA-256 | `core/exporter.py`, `tests/test_exporter.py` | **80 h** |
| **Mes 6** | Reporte 06 | Validación con datos reales de Ciencia de Datos (42 tests), documentación E2E y despliegue | `docs/manual/MANUAL_DE_USUARIO.md`, `.html`, `docs/evidencias/` | **80 h** |
| **TOTAL** | **6 Meses** | **Ciclo Completo de Ingeniería de Software (SDLC)** | **Suite funcional 100% verificada** | **480 h** |

---

## Mes 1: Diagnóstico Empírico de Fallas en SAES y Diseño Arquitectónico (ADR-0001)
**Horas acumuladas en el mes:** 80 horas | **Total acumulado:** 80 / 480 horas

### Objetivo del Mes
Analizar la problemática operativa de las Jefaturas de Departamento Académico en ESCOM durante los periodos de inscripción y reinscripción en el SAES, documentar las anomalías de datos observadas en producción y diseñar una arquitectura de software de costo $0 y cero invasión institucional.

### Desglose de Actividades Realizadas
| Semana | Actividad Técnica | Horas |
| :---: | :--- | :---: |
| **Semana 1** | Levantamiento de requerimientos y análisis de reportes oficiales de *Ocupabilidad por Grupos* en el SAES (ASP.NET). Identificación de tiempos muertos en el vaciado manual hacia hojas de cálculo. | 20 h |
| **Semana 2** | Diagnóstico empírico de anomalías aritméticas en el SAES: registro de **sobrecupos con disponibilidad negativa (`-1` a `-4`)**, discrepancias entre $\text{Cupo} - \text{Inscritos} \neq \text{Disponibles}$, y heterogeneidad de capacidades entre aulas teóricas (`30–37`), laboratorios (`18`) y Trabajo Terminal (`250–255`). | 20 h |
| **Semana 3** | Redacción y validación del **ADR-0001 (*Architecture Decision Record 0001: Ingesta desacoplada vía Portapapeles Ctrl+C / Ctrl+V*)**, descartando el uso de *web scrapers* invasivos o conexiones directas a SQL Server para garantizar cumplimiento normativo y operación *zero-footprint*. | 20 h |
| **Semana 4** | Modelado del dominio con **Pydantic v2** (`core/models.py`): definición de estructuras inmutables (`frozen=True`), enumeradores de turno y acción (`ABRIR`, `CONSERVAR`, `CERRAR`), y validadores de integridad de entrada. | 20 h |

### Evidencias Generadas
* Especificación de Arquitectura y Documento Maestro (`docs/arquitectura/RACO_Documento_Maestro_Tecnico.pdf`).
* Contratos de datos inmutables en `core/models.py`.

---

## Mes 2: Construcción del Analizador Léxico Tolerante a Fallos (`core/parser.py`)
**Horas acumuladas en el mes:** 80 horas | **Total acumulado:** 160 / 480 horas

### Objetivo del Mes
Desarrollar el motor de ingesta capaz de transformar texto crudo copiado desde cualquier navegador web (Chrome, Edge, Firefox) sobre la vista de *Ocupabilidad Horario* del SAES en objetos tipados y validados, soportando la nomenclatura completa de grupos de ESCOM.

### Desglose de Actividades Realizadas
| Semana | Actividad Técnica | Horas |
| :---: | :--- | :---: |
| **Semana 1** | Diseño de expresiones regulares avanzadas en `core/parser.py` tolerantes tanto a separación por tabuladores (`\t`) como a múltiples espacios en blanco generados al copiar tablas HTML del SAES. | 20 h |
| **Semana 2** | Implementación del extractor de metadatos de grupo mediante el patrón `r"^(?P<semestre>[1-9])(?P<carrera>[A-Za-z]+)(?P<turno>[MVXmvx])\d+$"`, incorporando soporte para los turnos **Matutino (`M`)**, **Vespertino (`V`)** y **Mixto/Administrativo (`X`)**. | 20 h |
| **Semana 3** | Desarrollo del detector de discrepancias aritméticas del SAES (`alerta_discrepancia_saes`): captura de disponibilidad negativa (`-1` a `-4`) sin pérdida de datos y registro de auditoría cuando el cálculo reportado por SAES difiere de la resta real. | 20 h |
| **Semana 4** | Creación de la batería de pruebas unitarias en `tests/test_parser.py` cubriendo casos borde: encabezados repetidos, líneas vacías, nombres de asignaturas con acentos y caracteres especiales, sobrecupos negativos y grupos `7AX1` / `8AX1`. | 20 h |

### Evidencias Generadas
* Módulo `core/parser.py` con función `parse_saes_clipboard_text`.
* Suite de pruebas unitarias `tests/test_parser.py`.

---

## Mes 3: Motor Matemático de Optimización y Cupo Blando ADR-0002 (`core/rules.py`)
**Horas acumuladas en el mes:** 80 horas | **Total acumulado:** 240 / 480 horas

### Objetivo del Mes
Implementar el modelo matemático de optimización de capacidad docente bajo incertidumbre, sustituyendo el enfoque rígido de cupo fijo por el **Modelo de Capacidad Blanda (*Soft Capacity*) y Cupo Modal por Asignatura (ADR-0002)**.

### Desglose de Actividades Realizadas
| Semana | Actividad Técnica | Horas |
| :---: | :--- | :---: |
| **Semana 1** | Formulación e implementación de la ecuación de grupos necesarios con tolerancia operativa $\tau$ (`calcular_grupos_necesarios`): $$K_{\text{prop}} = \left\lceil \frac{D}{C_{\text{base}} + \tau} \right\rceil$$ con $\tau = 2$ alumnos por defecto para evitar la apertura de grupos espurios por excedentes marginales de 1 o 2 estudiantes. | 20 h |
| **Semana 2** | Desarrollo del estimador estadístico `calcular_cupo_modal` en `core/rules.py`, determinando automáticamente la capacidad estándar de cada asignatura a partir de la moda de sus secciones activas y permitiendo *override* manual opcional. | 20 h |
| **Semana 3** | Programación del aislamiento y protección automática de **grupos atípicos y especiales**: (a) **Laboratorios** con cupo físico restringido ($C \le 0.6 \times C_{\text{modal}}$, ej. `18` lugares) y (b) **Macro-Grupos Administrativos de Trabajo Terminal** ($C \ge 100$ o `Turno.X`, ej. `250` y `255` plazas), impidiendo que sesguen la moda o sean cerrados por el algoritmo. | 20 h |
| **Semana 4** | Implementación de la política de **Cero Rechazo Estudiantil** (invariante $\sum \text{Inscritos Asignados} = \text{Demanda Observada}$) y verificación exhaustiva mediante `tests/test_rules.py`. | 20 h |

### Evidencias Generadas
* Motor algorítmico `core/rules.py` y validación de esquemas en `core/validators.py`.
* Pruebas matemáticas y de invariantes en `tests/test_rules.py`.

---

## Mes 4: Interfaz Visual Analítica en Streamlit y Semáforo de Tiras (`app.py`)
**Horas acumuladas en el mes:** 80 horas | **Total acumulado:** 320 / 480 horas

### Objetivo del Mes
Construir el tablero interactivo de usuario final en **Streamlit (`app.py`)** orientado a Jefes de Departamento y Subdirección Académica, integrando controles paramétricos en tiempo real, cálculo de horas docentes y diagnóstico de cuellos de botella por semestre.

### Desglose de Actividades Realizadas
| Semana | Actividad Técnica | Horas |
| :---: | :--- | :---: |
| **Semana 1** | Diseño de la arquitectura de estado en `st.session_state` para persistir los lotes ingeridos por portapapeles o archivo (`.csv`/`.xlsx`), incorporando botones de acción rápida (*Cargar Ejemplo SAES* y *Limpiar Entrada*). | 20 h |
| **Semana 2** | Construcción de la barra lateral de parámetros operativos: control deslizante de Tolerancia de Sobrecupo ($\tau \in [0, 5]$), conmutador de cupo modal vs. cupo uniforme, selector de **Horas Semanales Frente a Grupo** (`1.0` a `12.0` hrs/semana) y filtro de turno (`Todos`, `M`, `V`, `X`). | 20 h |
| **Semana 3** | Desarrollo de la franja de **5 KPIs Superiores** (Grupos Actuales, Grupos Propuestos, Delta Neto, Alumnos Atendidos al 100% y Horas Docentes Requeridas) y las vistas tabulares de *Resumen Directivo* y *Detalle Operativo por Grupo*. | 20 h |
| **Semana 4** | Implementación del algoritmo de **Semáforo de Tiras Curriculares por Semestre** (`diagnosticar_tiras_semestre`), clasificando cada bloque semestral en 🔴 *Tira Bloqueada*, 🟡 *Tira en Riesgo* o 🟢 *Tira Saludable* según la saturación de sus asignaturas. | 20 h |

### Evidencias Generadas
* Aplicación interactiva `app.py` con soporte completo de 1° a 8° semestre.
* Guía integrada de interpretación para usuarios directivos.

---

## Mes 5: Exportador Oficial a Excel y Auditoría Criptográfica SHA-256 (`core/exporter.py`)
**Horas acumuladas en el mes:** 80 horas | **Total acumulado:** 400 / 480 horas

### Objetivo del Mes
Diseñar e implementar el motor de generación de dictámenes técnicos en formato Microsoft Excel (`.xlsx`) en memoria (`BytesIO`), asegurando trazabilidad forense mediante un sello criptográfico **SHA-256** sobre los datos de entrada.

### Desglose de Actividades Realizadas
| Semana | Actividad Técnica | Horas |
| :---: | :--- | :---: |
| **Semana 1** | Desarrollo de `generar_dictamen_excel` en `core/exporter.py` utilizando `openpyxl` con estilos institucionales IPN (azul marino `#002B49`, tipografía estandarizada, bordes finos y autoajuste dinámico de ancho de columnas). | 20 h |
| **Semana 2** | Construcción de las **4 pestañas oficiales del libro Excel**: (1) `Carátula y Supuestos`, (2) `Resumen Directivo`, (3) `Detalle por Grupo` con formato condicional semántico (`ABRIR`, `CONSERVAR`, `CERRAR`), y (4) `Semáforo de Tiras`. | 20 h |
| **Semana 3** | Implementación del cálculo determinista del **Sello Digital SHA-256** (`calcular_hash_entrada`), normalizando saltos de línea (`\r\n` $\to$ `\n`) y espacios espurios para garantizar que el mismo corte del SAES produzca idéntica huella criptográfica en cualquier sistema operativo. | 20 h |
| **Semana 4** | Incorporación de metadatos de honestidad institucional (título *"INFORME TÉCNICO DE APOYO - PLANIFICACIÓN DE CAPACIDAD DOCENTE"*, supuestos explícitos del modelo y nota de descargo normativo) y pruebas automatizadas en `tests/test_exporter.py`. | 20 h |

### Evidencias Generadas
* Módulo exportador `core/exporter.py`.
* Suite de pruebas de integridad de exportación y hash `tests/test_exporter.py`.

---

## Mes 6: Validación con Datos Reales (Ciencia de Datos), Documentación E2E y Despliegue
**Horas acumuladas en el mes:** 80 horas | **Total acumulado:** 480 / 480 horas

### Objetivo del Mes
Ejecutar las pruebas integrales del sistema utilizando cortes oficiales del SAES de la **Licenciatura en Ciencia de Datos (ESCOM)**, blindar la calidad del código mediante auditoría colegiada, elaborar la documentación institucional y dejar el repositorio listo para operación en la nube y local.

### Desglose de Actividades Realizadas
| Semana | Actividad Técnica | Horas |
| :---: | :--- | :---: |
| **Semana 1** | Pruebas de estrés y validación con el reporte oficial del SAES de la *Licenciatura en Ciencia de Datos* (`docs/evidencias/SAES_Reporte_Ocupabilidad_LCD_Oficial.pdf`), verificando los 42 casos de prueba automatizados en `pytest` (100% en verde). | 20 h |
| **Semana 2** | Ejecución del paquete de blindaje técnico post-auditoría (`v1.2.1-hardened`): validación estricta de esquemas en subida de archivos, sanitización contra *CSV/Excel Formula Injection* (`=`, `+`, `-`, `@`), y soporte decimal en horas docentes. | 20 h |
| **Semana 3** | Elaboración del **Resumen Ejecutivo para Jefaturas y Academias** (`docs/ejecutivo/RACO_Resumen_Ejecutivo_Academias.pdf`) y captura de las 8 evidencias visuales del flujo operativo E2E (`docs/manual/img/`). | 20 h |
| **Semana 4** | Redacción del **Manual de Usuario E2E** en formatos Markdown (`docs/manual/MANUAL_DE_USUARIO.md`) y HTML imprimible con diseño institucional IPN (`docs/manual/MANUAL_DE_USUARIO.html`), integración de esta bitácora de 480 horas y liberación final en GitHub (`main`). | 20 h |

### Evidencias Generadas
* 42 pruebas automatizadas pasando al 100% (`pytest`).
* Documentación institucional completa en `docs/arquitectura/`, `docs/ejecutivo/`, `docs/evidencias/`, `docs/manual/` y `docs/servicio_social/`.

---

**Fin de la Bitácora Técnica — Total Acreditado: 480 Horas de Servicio Social en Ingeniería de Software (ESCOM - IPN).**
