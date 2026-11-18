from getpass import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mantenimiento_ia.conocimiento import NIVEL
from portal.analisis import analizar
from portal.models import Caso, Evento


class Command(BaseCommand):
    help = "Crea las cuentas locales del piloto y tres reportes simulados."

    @transaction.atomic
    def handle(self, *args, **options):
        usuarios = get_user_model().objects
        cuentas = {"reportante_demo": False, "mantenimiento_demo": True}
        for nombre, interno in cuentas.items():
            usuario = usuarios.filter(username=nombre).first()
            if usuario:
                if usuario.is_staff != interno:
                    raise CommandError(f"La cuenta {nombre} tiene un rol distinto al esperado.")
                continue
            clave = getpass(f"Contraseña local para {nombre} (mínimo 8 caracteres): ")
            if len(clave) < 8:
                raise CommandError("Usa una contraseña de al menos 8 caracteres.")
            usuarios.create_user(username=nombre, password=clave, is_staff=interno)

        reportante = usuarios.get(username="reportante_demo")
        ejemplos = [
            ("Aula 204", "ELE-204", "El apagador de la entrada saca chispitas cuando se enciende."),
            ("Pasillo principal", "PIS-PB", "La loseta está levantada junto a la entrada y la gente tropieza."),
            ("Aula 203", "", "La pintura de la pared está descarapelada junto a la ventana."),
        ]
        for zona, activo, descripcion in ejemplos:
            if Caso.objects.filter(reportante=reportante, zona=zona, descripcion=descripcion).exists():
                continue
            decision = analizar(descripcion, zona, activo, None, {})
            caso = Caso.objects.create(
                reportante=reportante, edificio="Edificio académico", zona=zona, activo=activo,
                descripcion=descripcion, decision=decision, nivel=NIVEL[decision["prioridad"]],
                escalado=decision["escalamiento"],
            )
            Evento.objects.create(caso=caso, autor=reportante, accion="Reporte simulado recibido")
        self.stdout.write(self.style.SUCCESS("Demo lista. Cuentas: reportante_demo y mantenimiento_demo."))
