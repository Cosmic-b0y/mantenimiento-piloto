from django import forms
from django.contrib.auth import get_user_model

from mantenimiento_ia import CATEGORIAS, PRIORIDADES
from .models import Caso, Estado


class ReporteForm(forms.ModelForm):
    edificio = forms.ChoiceField(choices=[
        ("", "Selecciona un edificio"), ("Edificio académico", "Edificio académico"),
        ("Edificio de servicios", "Edificio de servicios"),
    ])
    zona = forms.CharField(label="Zona o aula", max_length=100,
                           widget=forms.TextInput(attrs={"placeholder": "Ej. Aula 204"}))
    activo = forms.CharField(label="Código del activo (opcional)", max_length=60, required=False)
    descripcion = forms.CharField(
        label="¿Qué observaste?", max_length=2500,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Ej. El apagador de la entrada saca chispitas."}),
    )
    evidencia = forms.FileField(label="Fotografía (opcional)", required=False,
                               widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"}))

    class Meta:
        model = Caso
        fields = ("edificio", "zona", "activo", "descripcion", "evidencia")

    def clean_evidencia(self):
        foto = self.cleaned_data["evidencia"]
        if foto:
            if foto.size > 5 * 1024 * 1024:
                raise forms.ValidationError("La foto debe pesar 5 MB o menos.")
            cabecera = foto.read(8)
            foto.seek(0)
            if not (cabecera.startswith(b"\xff\xd8\xff") or cabecera == b"\x89PNG\r\n\x1a\n"):
                raise forms.ValidationError("Adjunta una foto JPG o PNG.")
            foto.name = "evidencia.jpg" if cabecera.startswith(b"\xff") else "evidencia.png"
        return foto


TRANSICIONES = {
    Estado.PENDIENTE: (Estado.INFORMACION, Estado.VALIDADO),
    Estado.INFORMACION: (Estado.INFORMACION, Estado.VALIDADO),
    Estado.VALIDADO: (Estado.INFORMACION, Estado.VALIDADO, Estado.ATENCION),
    Estado.ATENCION: (Estado.ATENCION, Estado.CERRADO),
    Estado.CERRADO: (),
}


class RevisionForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput, min_value=0)
    categoria = forms.ChoiceField(label="Categoría confirmada", choices=CATEGORIAS.items())
    prioridad = forms.ChoiceField(label="Prioridad confirmada", choices=[(p, p) for p in PRIORIDADES])
    responsable = forms.ModelChoiceField(
        label="Responsable", queryset=get_user_model().objects.none(), required=False,
        empty_label="Sin asignar",
    )
    estado = forms.ChoiceField(label="Actualizar estado")
    nota = forms.CharField(label="Nota de revisión o atención", max_length=1500, required=False,
                           widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, caso, *args, **kwargs):
        initial = {
            "version": caso.version,
            "categoria": caso.categoria_confirmada or caso.decision["categoria"],
            "prioridad": caso.prioridad,
            "responsable": caso.responsable_id,
            "estado": Estado.VALIDADO if caso.estado in (Estado.PENDIENTE, Estado.INFORMACION) else caso.estado,
        }
        super().__init__(*args, initial=initial, **kwargs)
        self.caso = caso
        self.fields["responsable"].queryset = get_user_model().objects.filter(is_staff=True, is_active=True).order_by("username")
        self.fields["estado"].choices = [(estado, estado.label) for estado in TRANSICIONES[caso.estado]]

    def clean(self):
        datos = super().clean()
        estado, nota = datos.get("estado"), datos.get("nota")
        if estado in (Estado.INFORMACION, Estado.CERRADO) and not nota:
            self.add_error("nota", "Describe qué información falta o qué atención se realizó.")
        if estado in (Estado.ATENCION, Estado.CERRADO) and not datos.get("responsable"):
            self.add_error("responsable", "Asigna un responsable para continuar.")
        if datos.get("prioridad") != self.caso.prioridad and not nota:
            self.add_error("nota", "Indica el motivo del cambio de prioridad.")
        return datos
