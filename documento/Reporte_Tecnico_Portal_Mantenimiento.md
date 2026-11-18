# Reporte técnico del sistema de mantenimiento de infraestructura

**Equipo 3 · UNACH · Referencia de piloto ETDA**

**Fecha de revisión · 18 de noviembre de 2026**

**Versión · Prototipo de segunda entrega con portal web local**

## 1. Descripción y objetivo

El sistema recibe reportes de fallas de infraestructura, analiza su descripción para sugerir categoría y prioridad preliminar, y permite al personal de mantenimiento revisar, asignar y documentar la atención de cada caso.

La solución combina aprendizaje automático supervisado para clasificar texto, conocimiento expresado mediante reglas y una aplicación web para gestionar el seguimiento. El registro original y las decisiones humanas se conservan en SQLite.

El contexto institucional es un piloto propuesto. Los edificios de demostración y los datos de entrenamiento son simulados. La validación con reportes institucionales autorizados sigue pendiente.

El objetivo es convertir observaciones dispersas en casos localizables y trazables, acompañados de una explicación de la prioridad y un responsable de atención.

## 2. Usuarios y permisos

| Usuario | Funciones |
|---|---|
| Reportante autenticado | Registrar incidencias, adjuntar evidencia, consultar sus propios folios e historial y responder solicitudes de información. |
| Personal de mantenimiento autenticado | Consultar todos los casos, filtrar, confirmar o corregir categoría y prioridad, asignar responsables, cambiar estados y vincular reportes. |

El rol operativo se identifica mediante is_staff de la cuenta Django. Los responsables seleccionables son usuarios activos con ese atributo. La preparación de cuentas se realiza mediante comandos y herramientas de Django.

## 3. Arquitectura y tecnologías

La aplicación tiene una arquitectura web centralizada. El navegador presenta la interfaz y envía solicitudes HTTP a Django. El servidor valida permisos y formularios, ejecuta el análisis y accede a SQLite.

    Navegador de escritorio o celular
        |
        v
    Django / autenticación / formularios / vistas
        |
        +--> Normalización --> Naive Bayes --> categoría y confianza
        +--> Señales y reglas --> prioridad, escalamiento y motivos
        +--> SQLite --> casos, usuarios y eventos
        +--> Almacenamiento local --> fotografías

| Capa | Implementación | Responsabilidad |
|---|---|---|
| Interfaz | Plantillas Django, HTML y CSS | Bandeja, captura, detalle e ingreso. |
| Interacción | JavaScript | Contador de descripción y vista previa de foto. |
| Aplicación | Python y Django | Validación, permisos y seguimiento. |
| Clasificación web | portal/analisis.py | Entrenamiento e inferencia de Naive Bayes. |
| Conocimiento | mantenimiento_ia/conocimiento.py | Categorías, señales y política de prioridad. |
| Razonamiento | mantenimiento_ia/reglas.py | Aplicación de reglas y generación de motivos. |
| Persistencia | ORM de Django y SQLite | Casos, decisiones, cuentas y bitácora. |
| Evaluación original | Scripts con scikit-learn | Comparación de técnicas de la segunda entrega. |

El portal utiliza una implementación de Naive Bayes en Python con biblioteca estándar para facilitar la ejecución de la aplicación web. El proyecto conserva su evaluación original basada en scikit-learn. La comprobación realizada encontró coincidencia de categorías entre ambas implementaciones en los 63 ejemplos externos incluidos.

## 4. Información capturada y modelo de datos

El formulario solicita edificio, zona y descripción. El activo y la fotografía son opcionales. La descripción admite hasta 2500 caracteres. La zona utiliza texto libre y el edificio se selecciona de un catálogo inicial de dos opciones ficticias.

La fotografía admite JPG o PNG y hasta 5 MiB. El servidor comprueba tamaño y cabecera binaria, y el navegador muestra una vista previa. Se conserva como archivo local y su descarga requiere permiso de acceso al caso. La comprobación de cabecera constituye una validación básica de formato.

| Entidad | Información principal |
|---|---|
| Usuario | Cuenta, autenticación y rol operativo. |
| Caso | UUID, reportante, fecha, edificio, zona, activo, descripción y evidencia. |
| Resultado del análisis | Categoría sugerida, confianza, prioridad preliminar, reglas, motivos y señales en un campo JSON del caso. |
| Revisión del caso | Categoría y prioridad confirmadas, responsable, estado, primera revisión y número de versión. |
| Evento | Caso, autor, fecha, acción, nota y valores anteriores y posteriores modificados. |
| Vínculo | Referencia desde un reporte hacia un caso anterior relacionado. |

El folio visible utiliza ocho caracteres hexadecimales del UUID. Las rutas internas utilizan el UUID completo. El historial conserva el reporte original y las correcciones posteriores.

## 5. Funcionamiento de la inteligencia artificial

### 5.1 Clasificación supervisada

Naive Bayes multinomial aprende frecuencias de palabras y parejas de palabras en reportes etiquetados. Sugiere una de siete categorías.

| Categoría | Elementos representativos |
|---|---|
| Humedad | Filtraciones, goteras y humedad visible. |
| Eléctrico | Contactos, luminarias y apagadores. |
| Puertas | Cerraduras, ventanas y bisagras. |
| Pisos | Losetas, rampas y circulaciones. |
| Muros | Paredes, plafones y acabados. |
| Sanitario | Tuberías, lavabos y drenaje. |
| Mobiliario | Repisas, mesas y mobiliario fijo. |

El procesamiento convierte a minúsculas, elimina acentos y signos y expande abreviaturas. Extrae palabras de al menos dos caracteres, elimina palabras vacías y construye unigramas y bigramas después del filtrado.

El entrenamiento cuenta documentos por categoría y términos por categoría. El suavizado alfa y el umbral de revisión se leen de resultados/metricas.json. Para cada categoría se calcula la siguiente puntuación.

    puntuación(c) = log P(c) + suma de frecuencia(t, reporte) × log P(t | c)

    P(t | c) = (frecuencia(t, c) + alfa) /
               (total de términos de c + alfa × tamaño del vocabulario)

Se elige la categoría con mayor puntuación. La confianza visible se obtiene normalizando las puntuaciones y redondeando a porcentaje. La correspondencia entre esa cifra y la frecuencia real de acierto requiere calibración.

El modelo se construye en la primera llamada al análisis y se conserva en caché por proceso. Al reiniciar se reconstruye desde los archivos.

### 5.2 Datos utilizados

La segunda entrega contiene 1400 reportes simulados, con 1052 de entrenamiento y 348 de prueba. Incluye además 63 ejemplos externos redactados fuera del generador y 640 registros de historial simulado.

El portal aprende únicamente de las filas marcadas como entrenamiento. Los ejemplos externos permiten estudiar cambios de vocabulario dentro del experimento académico.

### 5.3 Señales y razonamiento mediante reglas

El detector reconoce patrones mediante expresiones regulares. Busca señales de agua, presencia eléctrica, riesgo eléctrico, desprendimiento, indicios estructurales, circulación afectada, pérdida de servicio y deterioro estético.

El motor combina señales, categoría sugerida e historial. La prioridad base es Media. Cuando aplican varias reglas, conserva la mayor prioridad y registra los motivos.

| Regla | Comportamiento |
|---|---|
| R1 | Agua combinada con presencia eléctrica propone Inmediata y escalamiento. |
| R2 | Desprendimientos e indicios potencialmente estructurales solicitan valoración especializada. |
| R3 | Confianza inferior al umbral activa revisión. El portal añade comprobaciones puntuales de vocabulario desconocido y determinadas frases vagas. |
| R7 | Solicita información ante datos incompletos o descripción corta. El formulario previene parte de estas entradas. |
| R9 | Al menos dos incidencias previas del mismo activo en 90 días elevan un nivel cuando la prioridad es inferior a Alta. |
| R10 | Afectación a circulación o evacuación propone al menos Alta. |
| R11 | Riesgo eléctrico directo propone Inmediata y escalamiento. |
| R12 | Señales de pérdida de servicio proponen al menos Alta. |

El lexicón del portal amplía expresiones como «chispitas», «agüita» y «caen pedacitos». También restringe patrones ambiguos de «sin tapa» y «se cayó».

La integración web de otras reglas requiere precisión al describirla. Los vínculos se confirman manualmente entre candidatos de mismo edificio, zona y activo. La prioridad Baja se confirma en el formulario y cambiar prioridad requiere nota. El seguimiento se consulta en bandeja e historial. La categoría declarada por el reportante queda fuera de los campos actuales de captura, por lo que R8 carece de esa entrada en el recorrido web.

### 5.4 Supervisión y alcance del aprendizaje

Todos los casos nuevos pasan a Pendiente de revisión. El responsable confirma o corrige la sugerencia desde el detalle.

Las fotografías se conservan para revisión humana. Las correcciones se guardan en la bitácora y pueden servir para preparar un futuro conjunto etiquetado tras revisión del equipo.

El cálculo actual se realiza localmente con frecuencias y reglas. Acciones como alertar_area_competente expresan recomendaciones registradas por el motor. El escalamiento se muestra en la interfaz. El envío de correos o mensajes requiere una integración posterior.

## 6. Recorrido operativo

1. El reportante inicia sesión y completa ubicación, descripción y evidencia opcional.
2. El servidor valida los datos y consulta antecedentes del activo en el mismo edificio.
3. El clasificador propone categoría y confianza.
4. El detector identifica señales y las reglas producen prioridad, escalamiento y motivos.
5. El servidor guarda el caso y el primer evento.
6. El reportante recibe un folio y consulta el detalle.
7. Mantenimiento revisa, corrige y asigna.
8. Si falta información, registra una solicitud y el reportante añade una aclaración.
9. El caso avanza a En atención y se cierra con una nota del trabajo realizado.

    Pendiente de revisión --> Validado --> En atención --> Cerrado
              |                  |
              v                  v
        Falta información <------+
              |
              +--> Aclaración --> Pendiente de revisión

El formulario exige nota al pedir información, cerrar o cambiar prioridad. Exige responsable al pasar a En atención o Cerrado. Los casos cerrados mantienen consulta e historial.

Las aclaraciones se almacenan como eventos y regresan el caso a revisión. La sugerencia original se conserva, y el responsable interpreta la nueva información.

## 7. Ejemplo y limitación observada

Para «El apagador de la entrada saca chispitas cuando se enciende», el detector reconoce la raíz chisp y activa R11. Propone prioridad Inmediata y escalamiento.

En la demo inspeccionada, el clasificador sugirió Humedad para ese texto. La categoría también aportó contexto que activó R1. Así, la detección de una señal pertinente puede coexistir con errores de categoría, área sugerida y parte de la explicación.

Corregir ese acoplamiento y evaluar las categorías con nuevas redacciones es una prioridad. El responsable dispone de los campos necesarios para confirmar la categoría eléctrica y registrar la decisión.

## 8. Interfaz y experiencia de uso

La bandeja presenta contadores de escalamientos por revisar, revisión pendiente, casos sin asignar y casos en atención. Se calculan sobre casos abiertos visibles y sirven de acceso a filtros.

Para mantenimiento, el orden coloca abiertos antes que cerrados, después escalamientos pendientes, prioridad descendente y antigüedad. Para reportantes se muestran primero los más recientes.

La búsqueda admite folio, descripción, ubicación, activo o responsable. Los filtros seleccionan estado y prioridad. Cada página contiene hasta 20 resultados.

En escritorio se muestra una tabla. En celular se transforma en tarjetas. El detalle organiza reporte, análisis, revisión e historial. El formulario agrupa ubicación y descripción y presenta contador y vista previa de imagen.

Se adaptaron patrones documentados de MaintainX para colas de trabajo, UpKeep para organizar el detalle y Fiix para indicadores accionables.

## 9. Acceso e integridad

Las vistas requieren autenticación. El reportante accede a sus propios registros y el personal de mantenimiento al conjunto completo. La evidencia utiliza el mismo control de permisos.

Django proporciona sesiones y protección CSRF. Las revisiones actualizan caso y evento en una transacción de base de datos.

El número de versión detecta cambios concurrentes al revisar. Si la versión cambió mientras el formulario estaba abierto, la aplicación solicita consultar el estado actual antes de volver a guardar.

El vínculo mantiene cada reporte como registro independiente con evidencia, estado y alerta. Los casos relacionados pueden consultarse entre sí y continúan teniendo seguimiento individual.

La configuración está orientada a ejecución local, con SQLite, hosts de localhost y depuración habilitada por defecto. La publicación requiere configurar secretos, HTTPS, servidor, respaldos y acceso.

## 10. Verificación y resultados

El 18 de noviembre de 2026 se repitieron las cuatro pruebas de portal/tests.py y la comparación exploratoria comparar_riesgos. Las cuatro pruebas finalizaron correctamente.

| Prueba | Evidencia comprobada |
|---|---|
| Flujo crítico | R11, acceso limitado, orden de bandeja, validación, atención, nota obligatoria de cierre y bitácora. |
| Vínculo | Relación con conservación de descripción y escalamiento del reporte vinculado. |
| Aclaración | Solicitud, respuesta y retorno a revisión con conservación de alerta. |
| Ambigüedad | Dos ejemplos de caída de persona y coladera sin tapa evitan escalamiento por esos patrones. |

Durante la mejora de interfaz se verificaron en Edge ingreso, detalle, filtro de escalamientos, contador y vista previa. Se inspeccionaron capturas de escritorio y celular y se comprobó ausencia de desbordamiento horizontal en bandeja y formulario a 390 píxeles.

La comparación utiliza los 63 ejemplos externos ya incluidos.

| Indicador | Segunda entrega | Portal actual |
|---|---|---|
| Críticos detectados | 5 de 15 | 9 de 15 |
| Recall de críticos | 33.3 % | 60.0 % |
| Críticos omitidos | 10 | 6 |
| Falsas alarmas críticas | 4 | 2 |
| Categorías coincidentes entre implementaciones | Referencia histórica | 63 de 63 |

El código define crítico como prioridad Inmediata o escalamiento. Las anotaciones son parte de los datos simulados y requieren revisión del equipo.

Algunos ejemplos orientaron los cambios del lexicón. Esta comparación describe el comportamiento en casos conocidos. La generalización requiere un conjunto nuevo reservado para evaluación. Los seis críticos omitidos señalan una necesidad concreta de mejora.

Las pruebas verifican escenarios determinados. Quedan pendientes pruebas de carga, accesibilidad completa, restauración de respaldos y concurrencia del vínculo.

## 11. Mejoras priorizadas

| Prioridad | Acción | Resultado esperado |
|---|---|---|
| 1 | Etiquetar casos nuevos y analizar los críticos omitidos. | Evaluación independiente de sensibilidad y falsas alarmas. |
| 2 | Mejorar categoría y dependencia entre categoría y señales. | Áreas sugeridas y explicaciones coherentes. |
| 3 | Calibrar confianza y ampliar la detección de descripciones insuficientes. | Revisión mejor sustentada en incertidumbre. |
| 4 | Integrar aclaraciones al análisis conservando resultados previos y versión del modelo. | Seguimiento de cambios de sugerencia. |
| 5 | Validar catálogo institucional y fortalecer validación de imágenes. | Ubicaciones uniformes y evidencia mejor gestionada. |
| 6 | Validar concurrencia, respaldos y configuración de despliegue. | Preparación para un piloto autorizado. |
| 7 | Incorporar QR, avisos y exportación. | Captura y seguimiento más ágiles. |
| 8 | Evaluar clasificación visual con fotografías autorizadas y etiquetadas. | Componente visual complementario medido. |

## 12. Reproducción

Desde la carpeta del proyecto, con el entorno Python activo, se ejecutan los siguientes comandos.

    python -m pip install -r requirements-web.txt
    python manage.py migrate
    python manage.py preparar_demo
    python manage.py runserver 127.0.0.1:8013

    python manage.py test portal
    python manage.py comparar_riesgos

preparar_demo solicita contraseña para cada cuenta nueva y conserva las existentes. El portal se abre en http://127.0.0.1:8013/.

El análisis depende de datos/reportes_simulados.csv y resultados/metricas.json, que deben conservarse con el código.

## 13. Fuentes técnicas

La documentación se basa en inspección del código y resultados de verificación.

| Fuente local | Información contrastada |
|---|---|
| portal/analisis.py | Entrenamiento, inferencia y lexicón del portal. |
| mantenimiento_ia/conocimiento.py y reglas.py | Categorías, señales y reglas. |
| portal/models.py | Persistencia, relaciones y eventos. |
| portal/forms.py | Captura, validaciones y transiciones. |
| portal/views.py | Permisos, búsqueda, revisión, vínculos y aclaraciones. |
| portal/settings.py | Configuración de ejecución local. |
| portal/templates/ y portal/static/ | Interfaz y comportamiento en navegador. |
| portal/tests.py | Pruebas automatizadas. |
| portal/management/commands/comparar_riesgos.py | Comparación reproducible. |
| resultados/metricas.json y decisiones_externos.csv | Parámetros y resultados históricos. |
| datos/metadatos_generacion.json | Procedencia simulada. |

Referencias de interfaz consultadas en la mejora del portal.

- MaintainX. [Organización de trabajo móvil](https://help.getmaintainx.com/getting-started-new-users/mobile-app-overview).
- UpKeep. [Consulta y gestión de órdenes de trabajo](https://help.onupkeep.com/en/articles/15545270-how-to-view-and-process-work-orders-on-web-new).
- Fiix. [Panel de órdenes activas](https://helpdesk.fiixsoftware.com/hc/en-us/articles/11605028180116-Active-work-orders-dashboard).

El informe describe el estado local inspeccionado con la fecha de corte indicada. Las mejoras propuestas requieren implementación y verificación posterior.

