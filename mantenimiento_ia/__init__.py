"""Componentes del prototipo de mantenimiento."""
from .conocimiento import (CATEGORIAS, LISTA_CATEGORIAS, PRIORIDADES, detectar_senales,
                           es_critico, normalizar, politica_prioridad)
from .reglas import MotorReglas


def __getattr__(nombre):
    if nombre == "AgenteMantenimiento":
        from .agente import AgenteMantenimiento
        return AgenteMantenimiento
    if nombre in {"ClasificadorPalabrasClave", "crear_naive_bayes",
                  "crear_regresion_logistica", "explicar_naive_bayes"}:
        from . import clasificador
        return getattr(clasificador, nombre)
    raise AttributeError(nombre)
