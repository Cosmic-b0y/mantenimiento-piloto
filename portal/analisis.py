import csv
import json
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache

from django.conf import settings
from django.utils import timezone

from mantenimiento_ia.conocimiento import LEXICON, detectar_senales, normalizar
from mantenimiento_ia.reglas import MotorReglas
from mantenimiento_ia.tokenizacion import STOPWORDS, TOKEN


LEXICON_PILOTO = {
    **LEXICON,
    "agua": LEXICON["agua"] + r"|\baguita\b",
    "riesgo_electrico": (
        LEXICON["riesgo_electrico"].replace("chispa|chispe", "chisp").replace("|sin tapa", "")
        + r"|se (?:le )?ven los fusibles|(?:contacto|apagador|tablero) sin tapa"
    ),
    "desprendimiento": (
        LEXICON["desprendimiento"].replace("se cayo|se cae\\b|caerse|", "")
        + r"|caen pedacit|(?:plafon|losa|techo|muro|repisa|anaquel) se ca(?:yo|e)\b"
    ),
}
PALABRAS_VACIAS = frozenset(STOPWORDS)


def terminos(texto):
    palabras = [p for p in re.findall(TOKEN, normalizar(texto)) if p not in PALABRAS_VACIAS]
    return palabras + [f"{a} {b}" for a, b in zip(palabras, palabras[1:])]


@lru_cache(maxsize=1)
def entrenar():
    """Naive Bayes multinomial con los mismos n-gramas, alfa y grupos del prototipo."""
    base = settings.BASE_DIR
    metricas = json.loads((base / "resultados/metricas.json").read_text(encoding="utf-8"))
    alfa = metricas["seleccion"]["alpha_nb"]
    umbral = metricas["umbral"]["valor"]
    documentos = Counter()
    frecuencias = defaultdict(Counter)
    vocabulario = set()
    with (base / "datos/reportes_simulados.csv").open(encoding="utf-8-sig", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            if fila["grupo"] != "entrenamiento":
                continue
            categoria = fila["categoria_ref"]
            tokens = terminos(fila["texto"])
            documentos[categoria] += 1
            frecuencias[categoria].update(tokens)
            vocabulario.update(tokens)
    total_documentos = sum(documentos.values())
    parametros = {
        categoria: (
            math.log(documentos[categoria] / total_documentos),
            math.log(sum(frecuencias[categoria].values()) + alfa * len(vocabulario)),
        )
        for categoria in sorted(documentos)
    }
    return parametros, frecuencias, vocabulario, alfa, umbral


def analizar(descripcion, zona, activo, foto, historial):
    parametros, frecuencias, vocabulario, alfa, umbral = entrenar()
    tokens = Counter(t for t in terminos(descripcion) if t in vocabulario)
    puntuaciones = {
        categoria: prior + sum(
            n * (math.log(frecuencias[categoria][t] + alfa) - denominador)
            for t, n in tokens.items()
        )
        for categoria, (prior, denominador) in parametros.items()
    }
    categoria = max(puntuaciones, key=puntuaciones.get)
    mejor = puntuaciones[categoria]
    confianza = 1 / sum(math.exp(p - mejor) for p in puntuaciones.values())
    senales = detectar_senales(descripcion, lexicon=LEXICON_PILOTO)
    decision = MotorReglas(umbral, historial).decidir(
        {"texto": descripcion, "zona": zona, "activo_id": activo, "fecha": timezone.localdate(),
         "foto_calidad": "adjunta" if foto else "sin_foto"},
        categoria, confianza, senales["flags"],
    )
    if not tokens or normalizar(descripcion) in {"esta danado por favor revisen", "esta danado revisen"}:
        decision["reglas"] = sorted(set(decision["reglas"]) | {"R3"})
        decision["motivos_revision"].append("Descripción sin suficiente detalle identificable")
        decision["revision_humana"] = True
    decision["evidencia_textual"] = senales["evidencia"]
    decision["confianza"] = round(confianza * 100)
    return decision
