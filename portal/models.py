import uuid

from django.conf import settings
from django.db import models


class Estado(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente de revisión"
    INFORMACION = "informacion", "Falta información"
    VALIDADO = "validado", "Validado"
    ATENCION = "atencion", "En atención"
    CERRADO = "cerrado", "Cerrado"


class Caso(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reportante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reportes")
    edificio = models.CharField(max_length=100)
    zona = models.CharField(max_length=100)
    activo = models.CharField(max_length=60, blank=True)
    descripcion = models.TextField()
    evidencia = models.FileField(upload_to="reportes/%Y/%m", blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    decision = models.JSONField()
    nivel = models.PositiveSmallIntegerField(default=1)
    escalado = models.BooleanField(default=False)
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.PENDIENTE)
    categoria_confirmada = models.CharField(max_length=25, blank=True)
    prioridad_confirmada = models.CharField(max_length=15, blank=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="casos_asignados")
    primera_revision = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=0)
    duplicado_de = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="reportes_vinculados")

    @property
    def folio(self):
        return str(self.id).split("-")[0].upper()

    @property
    def prioridad(self):
        return self.prioridad_confirmada or self.decision["prioridad"]


class Evento(models.Model):
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="bitacora")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=100)
    nota = models.TextField(blank=True)
    cambios = models.JSONField(default=dict)

    class Meta:
        ordering = ("-fecha", "-id")
