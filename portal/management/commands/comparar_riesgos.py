import csv
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand

from mantenimiento_ia import es_critico
from portal.analisis import analizar


class Command(BaseCommand):
    help = "Compara el portal con las decisiones históricas del conjunto externo de la segunda entrega."

    def handle(self, *args, **options):
        ruta = settings.BASE_DIR / "resultados/decisiones_externos.csv"
        estadisticas = {"Segunda entrega": Counter(), "Portal": Counter()}
        categorias_iguales = total = 0
        with ruta.open(encoding="utf-8", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                decision = analizar(
                    fila["texto"], fila["zona"], fila["activo_id"],
                    fila["foto_calidad"] != "sin_foto", {},
                )
                referencia = fila["critico_ref"] == "True"
                categorias_iguales += decision["categoria"] == fila["categoria_pred"]
                total += 1
                historico = es_critico(fila["prioridad_pred"], fila["escalamiento_pred"] == "True")
                actual = es_critico(decision["prioridad"], decision["escalamiento"])
                estadisticas["Segunda entrega"][referencia, historico] += 1
                estadisticas["Portal"][referencia, actual] += 1

        self.stdout.write(f"Categoría coincidente con la segunda entrega: {categorias_iguales}/{total}")
        for nombre, conteo in estadisticas.items():
            detectados = conteo[True, True]
            omitidos = conteo[True, False]
            falsas_alarmas = conteo[False, True]
            self.stdout.write(
                f"{nombre}: críticos detectados {detectados}/{detectados + omitidos}, "
                f"omitidos {omitidos}, falsas alarmas {falsas_alarmas}"
            )
        self.stdout.write("Comparación exploratoria. Algunos casos orientaron los ajustes del lexicón.")
