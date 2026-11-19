"""Filtros de presentación: resaltado de las palabras que activaron señales y
explicación breve de cada regla del motor."""
import unicodedata

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

REGLAS = {
    "R1": ("Agua + elemento eléctrico", "Hay agua o humedad cerca de algo eléctrico: prioridad Inmediata y escalamiento."),
    "R2": ("Desprendimiento o indicio estructural", "Algo cayó, puede caer o hay una grieta preocupante: requiere inspección especializada."),
    "R3": ("Baja confianza o foto ilegible", "El clasificador no está seguro o la foto no sirve: una persona debe revisar."),
    "R4": ("Posible duplicado", "Mismo activo y reporte parecido en pocos días: conviene vincular los casos."),
    "R5": ("Solo estético", "El responsable confirmó que es únicamente apariencia: prioridad Baja."),
    "R7": ("Datos mínimos incompletos", "Falta la zona o la descripción es muy corta: se pide completar."),
    "R8": ("Categoría en conflicto", "La categoría declarada es distinta de la que sugiere el sistema."),
    "R9": ("Reincidencia", "El mismo activo ya tuvo 2 o más incidencias en 90 días: sube un nivel."),
    "R10": ("Afecta la circulación", "Puede provocar caídas o bloquear el paso o la evacuación: prioridad Alta."),
    "R11": ("Riesgo eléctrico directo", "Chispas, humo, descargas o cables expuestos: prioridad Inmediata y escalamiento."),
    "R12": ("Pérdida de servicio", "Un espacio completo queda sin luz, agua o uso: prioridad Alta."),
}
ETIQUETA_SENAL = {
    "agua": "Agua / humedad", "electrico": "Elemento eléctrico", "riesgo_electrico": "Riesgo eléctrico",
    "desprendimiento": "Desprendimiento", "estructural": "Indicio estructural", "circulacion": "Circulación",
    "sin_servicio": "Sin servicio", "estetico": "Estético",
}
CLASE_SENAL = {
    "riesgo_electrico": "crit", "desprendimiento": "crit", "estructural": "crit", "agua": "warn",
    "electrico": "info", "circulacion": "warn", "sin_servicio": "warn", "estetico": "calm",
}


def _plano(texto):
    """Misma longitud que el original: minúscula y sin acento, carácter a carácter."""
    salida = []
    for ch in texto:
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if unicodedata.category(c) != "Mn").lower()
        salida.append(base[:1] if base else " ")
    return "".join(salida)


@register.filter
def resaltar(texto, evidencia):
    """Marca en el texto original las palabras que activaron señales."""
    texto = texto or ""
    if not isinstance(evidencia, dict):
        return escape(texto)
    plano = _plano(texto)
    marcas = []  # (inicio, fin, senal)
    for senal, terminos in evidencia.items():
        if senal.endswith("_negada") or senal not in ETIQUETA_SENAL:
            continue
        for termino in set(terminos):
            termino = termino.strip()
            if len(termino) < 3:
                continue
            inicio = plano.find(termino)
            while inicio != -1:
                fin = inicio + len(termino)
                while fin < len(plano) and plano[fin].isalnum():
                    fin += 1
                while inicio > 0 and plano[inicio - 1].isalnum():
                    inicio -= 1
                marcas.append((inicio, fin, senal))
                inicio = plano.find(termino, fin)
    marcas.sort()
    resultado, cursor = [], 0
    for ini, fin, senal in marcas:
        if ini < cursor:
            continue
        resultado.append(escape(texto[cursor:ini]))
        resultado.append(
            f'<mark class="sig {CLASE_SENAL.get(senal, "info")}" title="{escape(ETIQUETA_SENAL[senal])}">'
            f"{escape(texto[ini:fin])}</mark>"
        )
        cursor = fin
    resultado.append(escape(texto[cursor:]))
    return mark_safe("".join(resultado))


@register.simple_tag
def regla(codigo):
    titulo, detalle = REGLAS.get(codigo, (codigo, ""))
    return mark_safe(f'<span class="rule-chip" tabindex="0" data-tip="{escape(detalle)}"><b>{escape(codigo)}</b> {escape(titulo)}</span>')


@register.filter
def senales_activas(evidencia):
    if not isinstance(evidencia, dict):
        return []
    return [(CLASE_SENAL.get(s, "info"), ETIQUETA_SENAL[s]) for s in evidencia if s in ETIQUETA_SENAL]


@register.filter
def pasos(estado):
    """Línea de avance del caso: lista de (etiqueta, clase)."""
    orden = [("pendiente", "Recibido"), ("validado", "Validado"), ("atencion", "En atención"), ("cerrado", "Cerrado")]
    equivalencia = {"informacion": "pendiente"}
    actual = equivalencia.get(estado, estado)
    indice = next((i for i, (k, _) in enumerate(orden) if k == actual), 0)
    return [(etq, "done" if i < indice else "now" if i == indice else "todo") for i, (_, etq) in enumerate(orden)]


@register.filter
def inicial(valor):
    return str(valor or "?")[:1].upper()
