# Guión Maestro del Podcast: Dominando RACO de Principio a Fin (ESCOM - IPN)

**Título del Episodio:** RACO: De la Crisis de Cupos en el SAES a la Ingeniería de Capacidad Docente  
**Voz sugerida:** Locutor Técnico / Divulgador de Ingeniería de Software (`es-MX-JorgeNeural`)  
**Audiencia:** Presentación Ejecutiva, Defensa Técnica de Ingeniería y Acreditación de Servicio Social en la Escuela Superior de Cómputo del Instituto Politécnico Nacional.

---

## Introducción

Hola, ¿qué tal? Bienvenido a esta guía auditiva maestra sobre **RACO**, el **Optimizador de Capacidad Ajustada al Riesgo**, diseñado específicamente para la **Escuela Superior de Cómputo del Instituto Politécnico Nacional**.

Si estás escuchando este episodio, es porque quieres dominar al cien por ciento cada rincón de este sistema: desde el problema humano y administrativo que lo originó en los pasillos de ESCOM, pasando por cada botón, cada deslizador y cada pestaña de su interfaz gráfica, hasta llegar a las entrañas matemáticas de su motor algorítmico, su blindaje criptográfico y la estrategia exacta para defenderlo con éxito ante las jefaturas académicas.

Ponte cómodo, porque vamos a recorrer juntos los cuatro actos de esta obra de ingeniería de software aplicada.

---

## Acto Uno: El dolor real en ESCOM y la filosofía de cero invasión

Para entender por qué existe RACO, primero tenemos que situarnos en la realidad operativa de cada inicio de semestre en la Escuela Superior de Cómputo, durante las semanas críticas de reinscripciones y comisarías.

¿Qué ocurre tradicionalmente en las jefaturas de departamento académico y en la subdirección académica? Un escenario de alta presión y dolor operativo que podemos resumir en cuatro grandes síntomas:

Primero: **las filas interminables en ventanilla y la toma de decisiones a ciegas**. Cientos de estudiantes buscan lugar en materias clave mientras los jefes de departamento intentan cruzar manualmente tablas del Sistema de Administración Escolar, el famoso SAES, copiándolas a mano en hojas de cálculo improvisadas que tardan horas en actualizarse.

Segundo: **el fenómeno de los sobrecupos negativos**. Cuando se autorizan lugares adicionales por encima de la capacidad física de un salón, el SAES realiza una resta simple: cupo menos inscritos igual a disponibles. Eso provoca que en la columna de lugares disponibles aparezcan números negativos como menos uno, menos dos, menos tres o hasta menos cuatro. En un corte real de la Licenciatura en Ciencia de Datos, por ejemplo, vemos grupos de Cálculo Multivariable con treinta y seis de cupo, cuarenta inscritos y menos cuatro disponibles. Muchas herramientas convencionales fallan o rechazan estos valores negativos porque asumen que la disponibilidad nunca puede ser menor que cero.

Tercero: **los grupos zombi vespertinos y el desbalance entre turnos**. Mientras en el turno matutino hay asignaturas reventando con sobrecupo, en el turno vespertino suelen quedar grupos abiertos con apenas cinco, seis u ocho alumnos inscritos. Mantener abierto un grupo con seis estudiantes consume exactamente las mismas cuatro punto cinco horas docentes por semana que un grupo lleno, drenando el presupuesto de horas profesor que hace falta desesperadamente para abrir una sección donde sí hay fila de espera.

Y cuarto: **las tiras curriculares bloqueadas**. Para un alumno que necesita inscribir su semestre completo en un mismo turno, basta con que una o dos asignaturas del bloque agoten su cupo para que todo su horario se rompa, generando rezago escolar y cuellos de botella administrativos.

Ahora bien, ¿por qué nadie había automatizado esto antes dentro del SAES? Porque el SAES es una plataforma institucional cerrada en ASP punto NET. Intentar conectarse directamente a su base de datos, pedir permisos de administrador a nivel central en Zacatenco o programar robots que raspen la página con credenciales representa un riesgo de seguridad y una barrera burocrática de meses o años.

Aquí es donde nace la primera gran decisión arquitectónica de RACO, documentada en el **ADR cero cero cero uno**: **Costo cero pesos y cero invasión al SAES**.

RACO no toca el servidor del SAES, no pide contraseñas, no instala programas espía y no cuesta un solo centavo en licencias. Funciona bajo un paradigma de ingesta desacoplada por portapapeles: el jefe de departamento abre su navegador como todos los días, selecciona con el ratón la tabla de ocupabilidad del SAES, presiona Control más C, va a RACO, presiona Control más V, y en menos de un segundo tiene el dictamen matemático completo. Así de simple, así de limpio y así de seguro.

---

## Acto Dos: Recorrido minucioso por la interfaz gráfica, paso a paso

Ahora imagina que tienes la pantalla de RACO frente a ti. Vamos a recorrer visualmente toda la interfaz, de izquierda a derecha y de arriba hacia abajo, para que conozcas de memoria qué hace cada control.

### Uno: La Barra Lateral Izquierda, o Sidebar de Control

En el costado izquierdo de la pantalla se concentra todo el panel de mando y parametrización. Está dividido en tres bloques muy claros:

El primer bloque se llama **Ingesta de Datos**. Aquí tienes un selector de radio con dos opciones para elegir el método de entrada:
* La primera opción, que viene seleccionada por defecto, es **Pegar desde SAES entre paréntesis Portapapeles**. Está pensada para el flujo inmediato de copiar y pegar desde el navegador.
* La segunda opción es **Subir archivo punto CSV o punto XLSX**, ideal cuando la jefatura ya guardó previamente un corte en archivo y desea cargarlo desde su computadora.

Justo debajo aparece el segundo bloque: **Parámetros de Optimización**. Aquí es donde ocurre la magia de simulación en tiempo real, porque cada vez que mueves un control, todo el tablero se recalcula al instante:

1. **El deslizador de Tolerancia de Sobrecupo, representado por la letra griega tau:** Va de cero a cinco alumnos y por defecto está calibrado en **dos**. ¿Qué significa tau igual a dos? Es el concepto de cupo blando. Significa que si un salón tiene cupo de treinta y cinco alumnos y la demanda es de treinta y seis o treinta y siete, le decimos al motor: no abras un grupo nuevo ni gastes otro profesor por uno o dos alumnos extra; absórbelos en el grupo actual. Solo cuando el excedente supere esa tolerancia tau, el sistema propondrá abrir una nueva sección.
2. **La casilla Forzar cupo uniforme global:** Por defecto viene desmarcada. Mientras está desmarcada, RACO es inteligente y calcula el **cupo modal** de cada materia por separado, respetando que cada asignatura tiene su propio tamaño típico de aula. Si el usuario marca esta casilla, se despliega un campo numérico para imponer un cupo único global, por ejemplo treinta y cinco alumnos parejo para todas las materias teóricas.
3. **El control numérico de Horas semanales frente a grupo por materia:** Permite indicar cuántas horas a la semana imparte clase un profesor por cada grupo abierto. Va de una a doce horas, permite decimales como cuatro punto cinco horas, que es el estándar en ESCOM, o cuatro horas cerradas, y sirve para traducir grupos propuestos en horas-profesor reales.
4. **El selector desplegable de Filtro de Turno:** Permite ver todos los turnos juntos, o filtrar exclusivamente el turno **M** Matutino, el turno **V** Vespertino, o el turno **X**, que corresponde al turno Mixto o Administrativo donde viven los grupos de Trabajo Terminal.
5. **La casilla de Habilitar Techo Presupuestal Global:** Si una jefatura tiene un límite estricto de grupos que puede abrir en todo el departamento, al activar esta casilla puede fijar el tope máximo permitido, y RACO advertirá si la demanda supera el techo presupuestal disponible.

Finalmente, al fondo de la barra lateral izquierda se encuentra la sección **Exportar Informe**, con el botón principal **Descargar Informe Técnico punto XLSX**. Este botón genera en memoria el libro oficial de Excel de cuatro pestañas con sello criptográfico, listo para descargarse con un solo clic.

### Dos: El Área Central de Ingesta

Pasemos ahora al panel principal de la pantalla. En la parte superior vemos el título institucional: **RACO: Risk-Adjusted Capacity Optimizer**, acompañado del subtítulo de la Escuela Superior de Cómputo.

Debajo se encuentra un bloque desplegable llamado **Ingesta de datos SAES, Copiar diagonal Pegar**. Dentro de este bloque hay dos columnas:
* A la izquierda, una amplia **caja de texto** donde el usuario pega directamente con Control más V la tabla cruda copiada del SAES.
* A la derecha, la columna de **Acciones Rápidas** con dos botones fundamentales para una demostración en vivo:
  * El botón **Cargar Ejemplo SAES**, que inyecta automáticamente un lote realista con grupos de primer a séptimo semestre, incluyendo sobrecupos negativos, un laboratorio de dieciocho lugares y un grupo de Trabajo Terminal de doscientos cincuenta lugares.
  * Y el botón **Limpiar Entrada**, que vacía la memoria de sesión para comenzar un análisis nuevo desde cero.

En cuanto hay datos cargados, debajo del cuadro de ingesta aparece un **cintillo verde de confirmación** con una palomita que dice, por ejemplo: **Siete grupos procesados correctamente**, o **Noventa y cinco grupos procesados correctamente** cuando pegamos toda la carrera de Ciencia de Datos. Además, justo debajo hay un acordeón de ayuda rápida titulado **¿Cómo interpretar este informe?**, que explica en lenguaje llano el significado de cada color y cada acción para cualquier directivo.

### Tres: La Franja de Cinco KPIs Superiores

Antes de entrar a las tablas detalladas, RACO presenta una fila ejecutiva con **cinco tarjetas de indicadores clave de desempeño**, o KPIs, que resumen el estado de toda la corrida de un solo vistazo:

1. **Primera tarjeta: Grupos Actuales SAES.** Muestra el número total de grupos que existen hoy en el corte pegado.
2. **Segunda tarjeta: Grupos Propuestos.** Muestra cuántos grupos recomienda operar el modelo matemático de RACO.
3. **Tercera tarjeta: Grupos a Abrir más diagonal Cerrar menos.** Es el diferencial neto o Delta. Tiene configurada la semántica de color invertida en Streamlit: si el número es positivo, aparece en tono rojizo de alerta presupuestal porque implica abrir grupos adicionales y conseguir más profesores; si es negativo, indica ahorro o compactación de secciones subocupadas.
4. **Cuarta tarjeta: Alumnos Atendidos.** Muestra la relación entre alumnos asignados y matrícula total observada, por ejemplo ciento cuarenta y uno de ciento cuarenta y uno, con una insignia verde del **cien por ciento**. Esto refleja la invariante sagrada de RACO: la **política de cero rechazo estudiantil**. Ninguna optimización deja a un solo alumno inscrito fuera.
5. **Quinta tarjeta: Horas Docentes Requeridas.** Multiplica el total de grupos propuestos por las horas semanales configuradas en la barra lateral, mostrando por ejemplo treinta y dos horas por semana, e indicando en el delta cuántas horas docentes adicionales se necesitan o cuántas horas se ahorran respecto a la oferta original del SAES.

### Cuatro: Las Cuatro Pestañas de Análisis Profundo

Debajo de los KPIs se despliega el corazón analítico de la interfaz, organizado en **cuatro pestañas interactivas**:

#### Pestaña Uno: Resumen Directivo
Muestra la tabla **Consolidado por Materia y Turno**. Sus columnas son: Materia, Turno, Matrícula Observada, Grupos Actuales, Grupos Propuestos, Delta y Cupo Promedio.
Es la vista favorita de un Subdirector Académico porque condensa toda una carrera en unas cuantas filas. Aquí se ve claramente cómo una materia como *Álgebra Lineal* con treinta y siete alumnos para un cupo de treinta y seis, gracias a la tolerancia tau igual a dos, se queda en un solo grupo con Delta cero. En cambio, *Administración de Proyectos de TI* en turno vespertino, con treinta y nueve alumnos para un cupo de treinta y cinco, rebasa el umbral de treinta y siete y por tanto RACO propone subir de uno a dos grupos, marcando Delta igual a más uno y equilibrando el cupo promedio en diecinueve punto cinco alumnos por sección.

#### Pestaña Dos: Detalle Operativo por Grupo
Aquí bajamos del nivel macro al nivel micro, grupo por grupo. La tabla **Oferta Detallada por Grupo** muestra las columnas: Materia, Turno, Grupo ID, Acción, Inscritos Estimados, Cupo Asignado, Atípico diagonal Protegido y Justificación.
La columna **Acción** se ilumina con colores semánticos:
* **Verde para CONSERVAR:** grupos que se mantienen activos.
* **Azul para ABRIR:** nuevas secciones sugeridas por el motor, bautizadas automáticamente como `M-NUEVO-2` o `V-NUEVO-2`.
* **Rojo para CERRAR:** grupos zombi cuya escasa matrícula puede fusionarse sin problema en otra sección del mismo turno.

Pero lo más importante de esta segunda pestaña es la columna **Atípico diagonal Protegido**, que implementa el blindaje inteligente del **ADR cero cero cero dos**:
* Primero, **protege los laboratorios físicos**: si un grupo tiene un cupo menor o igual al sesenta por ciento del cupo modal, como un laboratorio de Química de dieciocho plazas, RACO respeta su límite físico de dieciocho y jamás intenta meterle treinta y cinco alumnos.
* Segundo, **protege los Macro-Grupos Administrativos de Trabajo Terminal**: en séptimo y octavo semestre existen grupos especiales como el `7AX1` o el `8AX1`, en turno mixto `X`, con cupos masivos de doscientos cincuenta o doscientos cincuenta y cinco lugares que sirven como contenedores administrativos para el registro de proyectos de titulación. En etapas tempranas, estos grupos suelen aparecer en el SAES con cero inscritos. Un algoritmo ingenuo diría: tiene cero inscritos, ciérralo. RACO, en cambio, detecta que pertenece al turno `X` o que su cupo es mayor o igual a cien, lo marca como **Atípico Protegido igual a Sí**, le coloca la justificación *"Macro-grupo administrativo diagonal Trabajo Terminal"* y jamás sugiere su cierre ni permite que ese número de doscientos cincuenta contamine el cálculo estadístico de las demás materias.

#### Pestaña Tres: Diagnóstico de Sobrecupo y Cierres
Esta pestaña filtra exclusivamente los focos rojos operativos para que el jefe de departamento no tenga que buscar agujas en un pajar:
* En la mitad superior lista los **Grupos con Sobrecupo Activo en SAES**, mostrando exactamente qué secciones tienen disponibilidad cero o negativa, como menos uno, menos dos o menos cuatro.
* En la mitad inferior lista los **Grupos Candidatos a Cierre o Fusión**, detallando cuántos lugares se liberan al compactar secciones subocupadas.
* Y si el SAES cometió algún error aritmético en su tabla de origen donde cupo menos inscritos no coincida con disponibles, aquí mismo se despliega una alerta amarilla de discrepancia para auditoría.

#### Pestaña Cuatro: Semáforo de Tiras Curriculares
Es una de las innovaciones más valiosas de RACO. Evalúa cada semestre completo del plan de estudios, de primero a octavo, y le asigna un color de semáforo:
* **Rojo, Tira Bloqueada:** cuando absolutamente todas las materias de ese semestre están saturadas o con sobrecupo negativo. Ningún alumno puede inscribir ese paquete curricular.
* **Amarillo, Tira en Riesgo:** cuando una o más materias del semestre ya agotaron sus lugares disponibles, e indica con nombre y apellido cuáles son las asignaturas cuello de botella que están trabando los horarios de ese semestre.
* **Verde, Tira Saludable:** cuando todas las asignaturas del semestre cuentan todavía con lugares disponibles.

---

## Acto Tres: El núcleo técnico, matemático y criptográfico bajo el capó

Si durante una revisión técnica te preguntan: *"Muy bonita la pantalla, pero ¿cómo está construido por dentro y por qué podemos confiar en sus números?"*, aquí tienes los cinco pilares de ingeniería de software que respaldan a RACO.

### Pilar Uno: La Fórmula Matemática de Punto de Quiebre con Cupo Blando
En el módulo `core/rules.py`, la cantidad de grupos propuestos para los grupos regulares de una asignatura en un turno dado no se calcula dividiendo rígidamente entre el cupo nominal, sino aplicando la ecuación del **ADR cero cero cero dos**:

El número de grupos propuestos es igual a la función techo, o redondeo hacia arriba al entero inmediato, de la **demanda observada de alumnos regulares dividida entre la suma del cupo base más la tolerancia tau**.

Es decir: si la demanda es de treinta y siete alumnos, el cupo base es treinta y cinco y la tolerancia tau es dos, dividimos treinta y siete entre treinta y cinco más dos, que es treinta y siete entre treinta y siete, igual a uno punto cero. El techo de uno punto cero es **un solo grupo**. Pero en cuanto llega el alumno número treinta y ocho, treinta y ocho entre treinta y siete da uno punto cero dos, y la función techo salta inmediatamente a **dos grupos**, repartiendo la matrícula de forma equitativa en diecinueve y diecinueve alumnos por salón.

### Pilar Dos: Estimación Estadística del Cupo Modal
¿De dónde sale el cupo base de cada materia si nadie lo escribe a mano? De la función `calcular_cupo_modal`. RACO inspecciona todos los grupos existentes de esa asignatura, filtra los grupos atípicos para evitar sesgos, y calcula la **moda estadística** de sus capacidades. Si existe un empate multimodal, desempata eligiendo el cupo mayor para no inflar artificialmente la necesidad de grupos. Y si el usuario desea sobreescribir ese valor desde la interfaz, el parámetro `override_cupo` toma precedencia limpia.

### Pilar Tres: Arquitectura Inmutable con Pydantic versión dos y Sanitización
En `core/models.py` y `core/validators.py`, todos los modelos de datos —como `GrupoInput`, `OptimizacionGrupo` y `ResumenMateria`— están construidos sobre **Pydantic versión dos** con la directiva `frozen=True`. Esto significa que los objetos son **inmutables**: una vez que un registro del SAES entra y es validado, ninguna función posterior puede alterar accidentalmente sus valores en memoria. Además, el exportador incluye sanitización activa contra ataques de inyección de fórmulas en hojas de cálculo, neutralizando cualquier texto malicioso que comience con signos de igual, más, menos o arroba.

### Pilar Cuatro: Cuarenta y dos pruebas automatizadas en Pytest
La confiabilidad del motor no depende de la fe, sino de una suite rigurosa de **cuarenta y dos pruebas unitarias y de integración** ejecutadas con `pytest`, divididas en tres archivos: `test_parser.py`, `test_rules.py` y `test_exporter.py`. Estas pruebas verifican desde expresiones regulares con tabuladores y espacios mezclados, hasta casos extremos de sobrecupo, protección de laboratorios, preservación de grupos de Trabajo Terminal en turno `X`, y pruebas con el corte real completo de noventa y cinco grupos de la Licenciatura en Ciencia de Datos. Las cuarenta y dos pruebas pasan al cien por ciento en verde.

### Pilar Cinco: Trazabilidad Forense con Hash Criptográfico SHA-256
Cuando descargas el dictamen en Excel desde `core/exporter.py`, la primera pestaña se titula **Carátula y Supuestos** y lleva el encabezado institucional *"INFORME TÉCNICO DE APOYO - PLANIFICACIÓN DE CAPACIDAD DOCENTE"*.
En la fila diecisiete de esa carátula se imprime un código hexadecimal de sesenta y cuatro caracteres: el **Sello Digital de Integridad SHA-256**.
Antes de calcular este hash, RACO normaliza los saltos de línea de Windows y Linux y elimina espacios espurios al final del texto. De esta manera, si dos jefes de departamento procesan el mismo corte del SAES en distintas computadoras, obtendrán exactamente el mismo sello criptográfico SHA-256. Esto garantiza que nadie manipuló ni maquilló un solo número entre la salida del SAES y la mesa donde se toman las decisiones académicas.

---

## Acto Cuatro: Estrategia ganadora para la presentación del martes y acreditación de las 480 horas

Para cerrar este recorrido, repasemos cómo articular todo este trabajo el próximo martes frente al profesor y cómo se conecta directamente con la liberación de tus **cuatrocientas ochenta horas de Servicio Social**.

### La narrativa de la demostración en vivo
Cuando presentes RACO el martes, no empieces hablando de líneas de código; empieza mostrando el dolor real y la velocidad de respuesta:
1. Muestra primero el PDF oficial de **Ocupabilidad por Grupos de la Licenciatura en Ciencia de Datos** extraído del SAES. Señala con el dedo los números negativos de menos cuatro en Cálculo Multivariable y los grupos de Trabajo Terminal con cupo de doscientos cincuenta y cinco.
2. Enseguida, pasa a la interfaz de RACO, pega los datos en vivo —o presiona el botón **Cargar Ejemplo SAES**—, y deja que el cintillo verde y los cinco KPIs aparezcan en menos de un segundo.
3. Muévele en vivo al deslizador de **Tolerancia tau** en la barra lateral de dos a cero y luego de regreso a dos, para que el profesor vea con sus propios ojos cómo cambian instantáneamente los grupos propuestos y las horas docentes requeridas.
4. Recorre rápidamente las pestañas mostrando cómo RACO protege automáticamente los laboratorios de dieciocho lugares y el grupo `7AX1` de Trabajo Terminal, y cómo el **Semáforo de Tiras** detecta al instante qué semestres tienen la tira curricular bloqueada en rojo o en riesgo en amarillo.
5. Finalmente, haz clic en **Descargar Informe Técnico punto XLSX**, abre el archivo de Excel y muestra la carátula azul marino del IPN con los supuestos del modelo y el **sello criptográfico SHA-256**.

### El respaldo documental de las 480 horas de Servicio Social
Todo el repositorio de GitHub está estructurado como un expediente de ingeniería de software de nivel profesional que respalda de forma transparente tus **seis reportes mensuales de ochenta horas cada uno**, sumando las **cuatrocientas ochenta horas reglamentarias**:
* **Mes uno, ochenta horas:** Diagnóstico empírico de anomalías en el SAES, documentación del ADR cero cero cero uno y modelado de datos en Pydantic.
* **Mes dos, ochenta horas:** Construcción del analizador léxico en `core/parser.py` con soporte para turnos Matutino, Vespertino y Mixto `X`.
* **Mes tres, ochenta horas:** Implementación del motor matemático en `core/rules.py` con cupo blando tau igual a dos, cupo modal y aislamiento de laboratorios y Trabajo Terminal bajo el ADR cero cero cero dos.
* **Mes cuatro, ochenta horas:** Desarrollo del tablero interactivo en Streamlit dentro de `app.py` y el algoritmo del Semáforo de Tiras Curriculares.
* **Mes cinco, ochenta horas:** Programación del motor exportador a Excel de cuatro pestañas en `core/exporter.py` con firma criptográfica SHA-256.
* **Mes seis, ochenta horas:** Validación integral con las cuarenta y dos pruebas automatizadas en Pytest sobre datos reales de Ciencia de Datos, redacción del Manual de Usuario End-to-End con capturas reales y puesta en producción.

### Conclusión
RACO demuestra que con buena arquitectura, rigor matemático y conocimiento profundo de nuestra escuela, es posible resolver un problema crítico del Instituto Politécnico Nacional en segundos, sin gastar presupuesto público y con calidad de software de primer nivel.

Escucha esta guía tantas veces como necesites antes del martes. Conoces el problema, dominas cada pantalla, entiendes cada ecuación y tienes todas las pruebas en verde. ¡Mucho éxito en tu presentación en ESCOM!
