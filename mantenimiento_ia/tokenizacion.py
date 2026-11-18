# Palabras vacías (ya normalizadas, sin acentos). "no" y "sin" se conservan
# porque cambian el sentido de la descripción.
STOPWORDS = [
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a",
    "en", "y", "o", "que", "se", "por", "con", "para", "es", "esta", "estan",
    "lo", "le", "les", "su", "sus", "ya", "me", "mi", "nos", "hay", "muy",
    "como", "pero", "mas", "este", "esto", "eso", "ese", "fue", "son", "tiene",
    "tienen", "favor", "gracias", "hola", "buen", "dia", "reporta", "reporte",
]
TOKEN = r"(?u)\b[a-z][a-z0-9]+\b"
