from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from collections import Counter
from datetime import timedelta
from django.db import transaction
from django.db.models import Case, F, Q, Value, When
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from mantenimiento_ia import CATEGORIAS, PRIORIDADES
from mantenimiento_ia.conocimiento import NIVEL
from .analisis import analizar
from .forms import ReporteForm, RevisionForm
from .models import Caso, Estado, Evento


def casos_visibles(user):
    base = Caso.objects.select_related("reportante", "responsable", "duplicado_de")
    return base if user.is_staff else base.filter(reportante=user)


@login_required
def bandeja(request):
    base = casos_visibles(request.user)
    estado = request.GET.get("estado", "")
    consulta = request.GET.get("q", "").strip()[:100]
    prioridad = request.GET.get("prioridad", "")
    filas = base
    if estado in Estado.values:
        filas = filas.filter(estado=estado)
    elif estado == "sin_asignar" and request.user.is_staff:
        filas = filas.filter(responsable__isnull=True).exclude(estado=Estado.CERRADO)
    elif estado == "revision" and request.user.is_staff:
        filas = filas.filter(estado__in=[Estado.PENDIENTE, Estado.INFORMACION])
    elif estado == "escalados" and request.user.is_staff:
        filas = filas.filter(escalado=True).exclude(estado=Estado.CERRADO)
    if consulta:
        filas = filas.filter(
            Q(id__istartswith=consulta) | Q(descripcion__icontains=consulta) |
            Q(zona__icontains=consulta) | Q(activo__icontains=consulta) |
            Q(responsable__username__icontains=consulta) | Q(edificio__icontains=consulta)
        )
    if prioridad in NIVEL:
        filas = filas.filter(nivel=NIVEL[prioridad])
    if request.user.is_staff:
        cerrados = Case(When(estado=Estado.CERRADO, then=Value(1)), default=Value(0))
        filas = filas.order_by(cerrados, "-escalado", "-nivel", "creado")
    else:
        filas = filas.order_by("-creado")
    vista = "tablero" if request.GET.get("vista") == "tablero" else "lista"
    columnas = []
    if vista == "tablero":
        lista = list(filas[:150])
        for valor, etiqueta in Estado.choices:
            tarjetas = [c for c in lista if c.estado == valor]
            columnas.append({"valor": valor, "etiqueta": etiqueta, "casos": tarjetas[:30], "total": len(tarjetas),
                             "urgentes": sum(1 for c in tarjetas if c.escalado or c.nivel >= NIVEL["Alta"])})
    pagina = Paginator(filas, 20).get_page(request.GET.get("pagina"))
    abiertos = base.exclude(estado=Estado.CERRADO)
    return render(request, "portal/bandeja.html", {
        "vista": vista, "columnas": columnas,
        "pagina": pagina, "estados": Estado.choices, "prioridades": PRIORIDADES,
        "estado": estado, "prioridad": prioridad, "consulta": consulta,
        "revision": abiertos.filter(estado__in=[Estado.PENDIENTE, Estado.INFORMACION]).count(),
        "sin_asignar": abiertos.filter(responsable__isnull=True).count(),
        "escalados": abiertos.filter(escalado=True).count(),
        "atencion": abiertos.filter(estado=Estado.ATENCION).count(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def nuevo(request):
    form = ReporteForm(request.POST if request.method == "POST" else None,
                       request.FILES if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        caso = form.save(commit=False)
        caso.reportante = request.user
        previas = (
            Caso.objects.filter(edificio=caso.edificio, activo__iexact=caso.activo, duplicado_de__isnull=True)
            .values_list("creado", flat=True) if caso.activo else []
        )
        historial = {caso.activo: [timezone.localtime(fecha).date() for fecha in previas]}
        caso.decision = analizar(caso.descripcion, f"{caso.edificio} / {caso.zona}", caso.activo, caso.evidencia, historial)
        caso.nivel = NIVEL[caso.decision["prioridad"]]
        caso.escalado = caso.decision["escalamiento"]
        with transaction.atomic():
            caso.save()
            Evento.objects.create(caso=caso, autor=request.user, accion="Reporte recibido")
        messages.success(request, f"Reporte registrado. Tu folio es {caso.folio}.")
        return redirect("detalle", pk=caso.pk)
    return render(request, "portal/nuevo.html", {"form": form})


def candidatos_de(caso):
    if not caso.activo or caso.estado == Estado.CERRADO or caso.duplicado_de_id:
        return Caso.objects.none()
    return (Caso.objects.filter(edificio=caso.edificio, zona__iexact=caso.zona, activo__iexact=caso.activo,
                                 creado__lt=caso.creado, duplicado_de__isnull=True)
            .exclude(pk=caso.pk).exclude(estado=Estado.CERRADO).order_by("-creado")[:5])


@login_required
@require_http_methods(["GET", "POST"])
def detalle(request, pk):
    caso = get_object_or_404(casos_visibles(request.user), pk=pk)
    form = None
    if request.method == "POST" and not request.user.is_staff:
        return HttpResponseForbidden()
    if request.user.is_staff and caso.estado != Estado.CERRADO:
        form = RevisionForm(caso, request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            datos = form.cleaned_data
            cambios = {
                "categoria": [caso.categoria_confirmada, datos["categoria"]],
                "prioridad": [caso.prioridad, datos["prioridad"]],
                "estado": [caso.get_estado_display(), Estado(datos["estado"]).label],
                "responsable": [str(caso.responsable or ""), str(datos["responsable"] or "")],
            }
            with transaction.atomic():
                actualizado = Caso.objects.filter(pk=caso.pk, version=datos["version"], version__exact=caso.version).update(
                    estado=datos["estado"], categoria_confirmada=datos["categoria"],
                    prioridad_confirmada=datos["prioridad"], responsable=datos["responsable"],
                    nivel=NIVEL[datos["prioridad"]],
                    escalado=caso.escalado and datos["estado"] == Estado.INFORMACION,
                    primera_revision=caso.primera_revision or timezone.now(), version=caso.version + 1,
                )
                if actualizado:
                    Evento.objects.create(caso=caso, autor=request.user, accion="Caso actualizado",
                                          cambios={k: v for k, v in cambios.items() if v[0] != v[1]}, nota=datos["nota"])
            if actualizado:
                messages.success(request, "Se guardó la revisión del caso.")
            else:
                messages.error(request, "El caso cambió durante la revisión. Consulta el estado actual e inténtalo de nuevo.")
            return redirect("detalle", pk=caso.pk)
    return render(request, "portal/detalle.html", {
        "caso": caso, "form": form, "categoria_sugerida": CATEGORIAS.get(caso.decision["categoria"]),
        "categoria_confirmada": CATEGORIAS.get(caso.categoria_confirmada),
        "candidatos": candidatos_de(caso) if request.user.is_staff else [],
    })


@login_required
@require_http_methods(["POST"])
def vincular(request, pk, destino):
    if not request.user.is_staff:
        return HttpResponseForbidden()
    caso = get_object_or_404(Caso, pk=pk)
    principal = next((c for c in candidatos_de(caso) if c.pk == destino), None)
    if principal is None:
        messages.error(request, "El caso seleccionado ya no está disponible para vincular.")
        return redirect("detalle", pk=pk)
    with transaction.atomic():
        actualizado = Caso.objects.filter(pk=pk, duplicado_de__isnull=True, version=caso.version).update(
            duplicado_de=principal, version=F("version") + 1,
        )
        if actualizado:
            Evento.objects.create(caso=caso, autor=request.user, accion=f"Vinculado al caso {principal.folio}")
            Evento.objects.create(caso=principal, autor=request.user, accion=f"Reporte asociado {caso.folio}")
    messages.success(request, "Se vinculó el reporte." if actualizado else "El vínculo ya fue actualizado.")
    return redirect("detalle", pk=pk)


@login_required
def evidencia(request, pk):
    caso = get_object_or_404(casos_visibles(request.user), pk=pk)
    if not caso.evidencia or not caso.evidencia.storage.exists(caso.evidencia.name):
        raise Http404
    return FileResponse(caso.evidencia.open("rb"), as_attachment=True, filename=caso.evidencia.name.split("/")[-1])



@login_required
@require_http_methods(["POST"])
def ampliar(request, pk):
    caso = get_object_or_404(Caso, pk=pk, reportante=request.user)
    nota = request.POST.get("nota", "").strip()
    if not 1 <= len(nota) <= 1500:
        messages.error(request, "Escribe una aclaración de hasta 1500 caracteres.")
        return redirect("detalle", pk=pk)
    with transaction.atomic():
        actualizado = Caso.objects.filter(pk=pk, estado=Estado.INFORMACION, version=caso.version).update(
            estado=Estado.PENDIENTE, version=F("version") + 1,
        )
        if actualizado:
            Evento.objects.create(caso=caso, autor=request.user, accion="Información adicional recibida", nota=nota)
    if actualizado:
        messages.success(request, "Se agregó tu aclaración y el caso volvió a revisión.")
    else:
        messages.error(request, "El caso ya no está esperando información.")
    return redirect("detalle", pk=pk)


@login_required
def panel(request):
    """Resumen visual para el personal de mantenimiento."""
    if not request.user.is_staff:
        return redirect("bandeja")
    ahora = timezone.now()
    todos = list(Caso.objects.select_related("responsable").order_by("-creado"))
    abiertos = [c for c in todos if c.estado != Estado.CERRADO]
    cerrados = len(todos) - len(abiertos)
    prioridad = Counter(c.prioridad for c in abiertos)
    categorias = Counter(CATEGORIAS.get(c.categoria_confirmada or c.decision["categoria"], "Otra") for c in abiertos)
    estados = Counter(c.estado for c in todos)
    zonas = Counter(f"{c.zona}" for c in abiertos).most_common(6)
    dias = [(ahora - timedelta(days=i)).date() for i in range(13, -1, -1)]
    por_dia = Counter(timezone.localtime(c.creado).date() for c in todos)
    esc_dia = Counter(timezone.localtime(c.creado).date() for c in todos if c.escalado or c.nivel == NIVEL["Inmediata"])
    revisiones = sorted((c.primera_revision - c.creado).total_seconds() / 3600 for c in todos if c.primera_revision)
    mediana = revisiones[len(revisiones) // 2] if revisiones else None
    atencion = [c for c in abiertos if c.escalado or c.nivel >= NIVEL["Alta"]]
    atencion.sort(key=lambda c: (-int(c.escalado), -c.nivel, c.creado))
    datos = {
        "prioridad": {p: prioridad.get(p, 0) for p in reversed(PRIORIDADES)},
        "categorias": dict(categorias.most_common()),
        "dias": [d.strftime("%d %b") for d in dias],
        "creados": [por_dia.get(d, 0) for d in dias],
        "criticos": [esc_dia.get(d, 0) for d in dias],
        "zonas": {z: n for z, n in zonas},
        "estados": {label: estados.get(valor, 0) for valor, label in Estado.choices},
        "responsables": dict(Counter((str(c.responsable) if c.responsable else "Sin asignar") for c in abiertos).most_common(6)),
    }
    return render(request, "portal/panel.html", {
        "datos": datos, "total": len(todos), "abiertos": len(abiertos), "cerrados": cerrados,
        "tasa_cierre": round(100 * cerrados / len(todos)) if todos else 0,
        "escalados": sum(1 for c in abiertos if c.escalado),
        "sin_asignar": sum(1 for c in abiertos if c.responsable_id is None),
        "mediana_horas": None if mediana is None else round(mediana, 1),
        "antiguos": sum(1 for c in abiertos if (ahora - c.creado).days >= 15),
        "atencion": atencion[:6],
        "nuevos_hoy": por_dia.get(timezone.localtime(ahora).date(), 0),
    })
