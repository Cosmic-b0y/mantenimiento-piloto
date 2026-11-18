# Mantenimiento Piloto · Equipo 3

Prototipo del **Sistema Inteligente para Monitoreo, Clasificación y Priorización del Mantenimiento de Infraestructura** (caso UNACH, referencia piloto ETDA).

> Todos los datos son **simulados** o redactados fuera del generador; no son reportes reales de la UNACH ni de ETDA.
> Ninguna salida es un dictamen técnico: el prototipo propone una **prioridad preliminar** sujeta a revisión humana.

Repositorio: https://github.com/Cosmic-b0y/mantenimiento-piloto

Portal local de captura, clasificación, revisión y seguimiento de mantenimiento. Incluye el prototipo y los resultados de la segunda entrega. Para usar la aplicación web, sigue la sección **Portal web del piloto** con Python 3.10 o superior.

Base original de la segunda entrega: https://github.com/Cosmic-b0y/entrega2_EQ3_codigo

## Componentes
- **Clasificador de categoría**: Naive Bayes multinomial sobre la descripción (comparado con regresión logística TF-IDF y una línea base de palabras clave).
- **Motor de reglas** R1–R12: combina categoría, confianza, señales de riesgo del texto, calidad de la foto e historial para proponer prioridad (Inmediata/Alta/Media/Baja), escalamiento y revisión humana.
- **Agente** (`AgenteMantenimiento`): percibir → interpretar → decidir → actuar → retroalimentar, más panel de casos abiertos (R6).

## Reproducir
```bash
pip install -r requirements.txt
python generador_datos.py           # datos/ (semilla 2026)
python evaluar.py                   # resultados/metricas.json, figuras, pruebas
python demo_consola.py              # demostración
python demo_consola.py --texto "el contacto echa chispas" --zona "Aula 101"
python demo_consola.py --interactivo
python documento/construir_notebook.py   # reejecuta el notebook
python documento/construir_pdf.py        # reconstruye el PDF desde resultados/
python documento/generar_capturas.py     # ejecuta y genera capturas PNG
python documento/verificar_cifras.py     # comprueba cada cifra del PDF
```
Probado con Python 3.13 y las versiones de `requirements.txt`. Con otras versiones de scikit-learn las cifras pueden variar ligeramente.

## Estructura
| Ruta | Contenido |
|---|---|
| `generador_datos.py` | Escenarios, plantillas, ruido, historial y referencia simulada |
| `mantenimiento_ia/conocimiento.py` | Taxonomía, normalización, lexicón de señales, política de prioridad |
| `mantenimiento_ia/clasificador.py` | Naive Bayes, regresión logística, palabras clave, explicación |
| `mantenimiento_ia/reglas.py` | Motor de reglas |
| `mantenimiento_ia/agente.py` | Agente y ciclo completo |
| `evaluar.py` | Protocolo de evaluación (partición por plantilla, casos externos, umbral sin datos de prueba) |
| `pruebas_definidas.json` | Resultados esperados escritos antes de ejecutar |
| `prototipo_mantenimiento_EQ3.ipynb` | Notebook ejecutado |
| `datos/` | Reportes simulados, historial, casos externos, metadatos |
| `resultados/` | Métricas, decisiones por reporte, pruebas, figuras, salida de la demo |
| `documento/` | PDF, scripts que lo generan y verificación de cifras |

## Portal web del piloto

La aplicación usa Django y una base SQLite local. Incluye acceso de reportantes y personal de mantenimiento, captura de evidencia, revisión, asignación, confirmación de vínculos y bitácora. Los edificios y reportes de la demo son ficticios.

Desde la carpeta de este proyecto, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py preparar_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8013
```

Abre http://127.0.0.1:8013/. El comando de demo pide una contraseña para cada cuenta al crearla. Entra como `reportante_demo` para capturar y consultar tus folios, o como `mantenimiento_demo` para revisar y asignar casos. El ejemplo de Aula 204 activa R11 por «saca chispitas».

Para verificar el flujo:

```powershell
.\.venv\Scripts\python.exe manage.py test portal
```

El portal aplica Naive Bayes multinomial con los n-gramas, alfa y datos de entrenamiento de la segunda entrega, mediante una implementación en Python que evita instalar la pila científica para la demo. Reutiliza el motor de reglas y aplica un lexicón específico del piloto. Los scripts originales conservan su lexicón y dependencias de evaluación. Las mejoras del lexicón requieren evaluación en casos nuevos con etiquetas de referencia. El portal adjunta imágenes como evidencia para revisión humana.

Para repetir la comparación exploratoria con las decisiones históricas:

```powershell
.\.venv\Scripts\python.exe manage.py comparar_riesgos
```

En los 63 ejemplos incluidos, el portal coincide en las 63 categorías, detecta 9 de 15 críticos frente a 5 de 15 y genera 2 falsas alarmas frente a 4. Algunos ejemplos orientaron los ajustes, así que estas cifras sirven para verificar el cambio en esos casos. La validación con un conjunto nuevo sigue pendiente.

