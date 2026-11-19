import csv
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from mantenimiento_ia.conocimiento import NIVEL
from portal.analisis import analizar
from portal.models import Caso, Estado, Evento


class Command(BaseCommand):
    help = ("Carga N reportes SIMULADOS (tomados de datos/reportes_simulados.csv, grupo prueba) repartidos en los "
            "últimos 30 días, con estados variados, para que el panel y el tablero tengan qué mostrar.")

    def add_arguments(self, parser):
        parser.add_argument("--cantidad", type=int, default=90)

    @transaction.atomic
    def handle(self, *args, cantidad, **options):
        usuarios = get_user_model().objects
        reportante = usuarios.filter(username="reportante_demo").first()
        personal = list(usuarios.filter(is_staff=True, is_active=True))
        if reportante is None or not personal:
            raise CommandError("Primero ejecuta: python manage.py preparar_demo")
        rng = random.Random(2026)
        with (settings.BASE_DIR / "datos/reportes_simulados.csv").open(encoding="utf-8-sig", newline="") as f:
            filas = [r for r in csv.DictReader(f) if r["grupo"] == "prueba" and r["texto"]]
        rng.shuffle(filas)
        ahora = timezone.now()
        creados = 0
        for fila in filas[:cantidad]:
            zona = fila["zona"] or "Pasillo principal"
            decision = analizar(fila["texto"], zona, fila["activo_id"], None, {})
            edad = rng.random() ** 1.6 * 29
            fecha = ahora - timedelta(days=edad, minutes=rng.randint(0, 600))
            sorteo = rng.random()
            antig = edad
            if antig < 2:
                estado = Estado.PENDIENTE if sorteo < .7 else Estado.INFORMACION
            elif sorteo < .22:
                estado = Estado.PENDIENTE
            elif sorteo < .38:
                estado = Estado.VALIDADO
            elif sorteo < .62:
                estado = Estado.ATENCION
            elif sorteo < .68:
                estado = Estado.INFORMACION
            else:
                estado = Estado.CERRADO
            responsable = None if estado in (Estado.PENDIENTE, Estado.INFORMACION) and sorteo < .5 else rng.choice(personal)
            if estado in (Estado.ATENCION, Estado.CERRADO) and responsable is None:
                responsable = rng.choice(personal)
            revisado = estado != Estado.PENDIENTE
            caso = Caso.objects.create(
                reportante=reportante, edificio=rng.choice(["Edificio académico", "Edificio de servicios"]),
                zona=zona, activo=fila["activo_id"], descripcion=fila["texto"], decision=decision,
                nivel=NIVEL[decision["prioridad"]], escalado=decision["escalamiento"] and estado != Estado.CERRADO,
                estado=estado, responsable=responsable,
                categoria_confirmada=decision["categoria"] if revisado else "",
                prioridad_confirmada=decision["prioridad"] if revisado else "",
                primera_revision=fecha + timedelta(hours=rng.uniform(.5, 30)) if revisado else None,
            )
            Caso.objects.filter(pk=caso.pk).update(creado=fecha)
            Evento.objects.create(caso=caso, autor=reportante, accion="Reporte simulado recibido")
            if revisado:
                Evento.objects.create(caso=caso, autor=responsable or personal[0], accion="Caso actualizado",
                                      nota="Revisión simulada.", cambios={"estado": ["Pendiente de revisión", Estado(estado).label]})
            creados += 1
        self.stdout.write(self.style.SUCCESS(f"{creados} reportes simulados cargados."))
