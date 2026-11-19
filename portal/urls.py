from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.bandeja, name="bandeja"),
    path("panel/", views.panel, name="panel"),
    path("ingresar/", LoginView.as_view(), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("reportar/", views.nuevo, name="nuevo"),
    path("casos/<uuid:pk>/", views.detalle, name="detalle"),
    path("casos/<uuid:pk>/ampliar/", views.ampliar, name="ampliar"),
    path("casos/<uuid:pk>/evidencia/", views.evidencia, name="evidencia"),
    path("casos/<uuid:pk>/vincular/<uuid:destino>/", views.vincular, name="vincular"),
]
