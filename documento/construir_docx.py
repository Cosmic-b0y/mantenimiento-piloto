#!/usr/bin/env python3
"""
Genera la versión Word (.docx) editable del documento a partir del MISMO
contenido que construir_pdf.py (mismos textos, tablas, figuras y cifras).
"""
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak,
                                Paragraph as RLParagraph, Preformatted, Spacer,
                                Table as RLTable)
from reportlab.platypus.tableofcontents import TableOfContents

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "documento"))
import construir_pdf as CP

AZUL, VERDE, GRIS = "1B2A41", "1F6F78", "5B6770"
ALINEA = {0: WD_ALIGN_PARAGRAPH.LEFT, 1: WD_ALIGN_PARAGRAPH.CENTER, 2: WD_ALIGN_PARAGRAPH.RIGHT, 4: WD_ALIGN_PARAGRAPH.JUSTIFY}
TMP = BASE / "documento" / "_docx_tmp"
TMP.mkdir(exist_ok=True)


def color_hex(c):
    try:
        return "%02X%02X%02X" % tuple(int(v * 255) for v in (c.red, c.green, c.blue))
    except Exception:
        return None


def sombrear(celda_o_parrafo_pr, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill)
    celda_o_parrafo_pr.append(shd)


def hipervinculo(parrafo, url, texto, tam):
    r_id = parrafo.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), r_id)
    r = OxmlElement("w:r"); rpr = OxmlElement("w:rPr")
    for tag, val in (("w:color", VERDE), ("w:u", "single")):
        e = OxmlElement(tag); e.set(qn("w:val"), val); rpr.append(e)
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(tam * 2))); rpr.append(sz)
    r.append(rpr); t = OxmlElement("w:t"); t.text = texto; t.set(qn("xml:space"), "preserve"); r.append(t)
    h.append(r); parrafo._p.append(h)


class Marcado(HTMLParser):
    """Convierte el marcado de ReportLab (<b>, <i>, <u>, <br/>, <a>) en runs de Word."""

    def __init__(self, parrafo, tam, color, negrita, cursiva, fuente):
        super().__init__(convert_charrefs=True)
        self.p, self.tam, self.color, self.fuente = parrafo, tam, color, fuente
        self.b, self.i, self.u, self.href = negrita, cursiva, False, None

    def handle_starttag(self, tag, attrs):
        if tag == "b": self.b = True
        elif tag == "i": self.i = True
        elif tag == "u": self.u = True
        elif tag == "br": self.p.add_run().add_break()
        elif tag == "a": self.href = dict(attrs).get("href")

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag == "b": self.b = False
        elif tag == "i": self.i = False
        elif tag == "u": self.u = False
        elif tag == "a": self.href = None

    def handle_data(self, data):
        if not data:
            return
        if self.href:
            hipervinculo(self.p, self.href, data, self.tam); return
        r = self.p.add_run(data)
        r.bold, r.italic, r.underline = self.b, self.i, self.u
        r.font.size = Pt(self.tam); r.font.name = self.fuente
        if self.color:
            r.font.color.rgb = RGBColor.from_string(self.color)


def escribir_marcado(parrafo, texto, estilo, tam=None, color=None):
    fn = estilo.fontName
    negrita, cursiva = fn.endswith("-B") or fn.endswith("-BI"), fn.endswith("-I") or fn.endswith("-BI")
    fuente = "Consolas" if fn == "Mono" else "Arial"
    col = color if color is not None else color_hex(estilo.textColor)
    if col == "000000":
        col = None
    Marcado(parrafo, tam or estilo.fontSize, col, negrita, cursiva, fuente).feed(texto)


def formato_parrafo(p, estilo, despues=None):
    pf = p.paragraph_format
    pf.alignment = ALINEA.get(estilo.alignment, WD_ALIGN_PARAGRAPH.LEFT)
    pf.space_before = Pt(estilo.spaceBefore); pf.space_after = Pt(estilo.spaceAfter if despues is None else despues)
    if estilo.leftIndent:
        pf.left_indent = Pt(estilo.leftIndent)
    if estilo.firstLineIndent:
        pf.first_line_indent = Pt(estilo.firstLineIndent)
    pf.line_spacing = 1.12


def parrafo(doc, fl):
    st = fl.style
    if st.name in ("h1", "h2"):
        p = doc.add_heading(level=1 if st.name == "h1" else 2)
        escribir_marcado(p, fl.text, st)
        return
    p = doc.add_paragraph()
    escribir_marcado(p, fl.text, st)
    formato_parrafo(p, st)


def codigo(doc, lineas, ancho_in=6.9):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    fijar_anchos(t, [ancho_in * 72])
    c = t.cell(0, 0)
    sombrear(c._tc.get_or_add_tcPr(), "F6F8F9")
    c.paragraphs[0].text = ""
    for k, linea in enumerate(lineas):
        p = c.paragraphs[0] if k == 0 else c.add_paragraph()
        p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.0
        r = p.add_run(linea if linea else " ")
        r.font.name = "Consolas"; r.font.size = Pt(7.2); r.font.color.rgb = RGBColor.from_string(AZUL)
    bordes(t, "C9D3D6")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def bordes(t, color):
    tbl = t._tbl
    tblPr = tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{lado}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), color)
        b.append(e)
    tblPr.append(b)


def fijar_anchos(t, anchos_pt):
    """Anchos fijos de columna (Word y LibreOffice) y márgenes internos de celda."""
    tblPr = t._tbl.tblPr
    total = int(sum(anchos_pt) * 20)
    w = OxmlElement("w:tblW"); w.set(qn("w:w"), str(total)); w.set(qn("w:type"), "dxa"); tblPr.append(w)
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
    mar = OxmlElement("w:tblCellMar")
    for lado, v in (("top", 40), ("left", 80), ("bottom", 40), ("right", 80)):
        e = OxmlElement(f"w:{lado}"); e.set(qn("w:w"), str(v)); e.set(qn("w:type"), "dxa"); mar.append(e)
    tblPr.append(mar)
    grid = t._tbl.tblGrid
    for j, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(int(anchos_pt[j] * 20)))
    for fila in t.rows:
        for j, c in enumerate(fila.cells):
            c.width = Pt(anchos_pt[j])


def imagen(doc, ruta, ancho_pt, parrafo_destino=None):
    p = parrafo_destino or doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(ruta), width=Pt(ancho_pt))
    return p


def tabla(doc, fl):
    filas = fl._cellvalues
    nf, nc = len(filas), len(filas[0])
    anchos = fl._colWidths
    # bloques de una celda: código o nota
    if nf == 1 and nc == 1:
        v = filas[0][0]
        v = v[0] if isinstance(v, list) else v
        if isinstance(v, Preformatted):
            codigo(doc, v.lines); return
        if isinstance(v, RLParagraph):
            t = doc.add_table(rows=1, cols=1); fijar_anchos(t, [6.9 * 72]); c = t.cell(0, 0)
            sombrear(c._tc.get_or_add_tcPr(), "E6F0F1")
            p = c.paragraphs[0]; escribir_marcado(p, v.text, v.style)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            return
    # tabla de imágenes (matrices de confusión)
    if any(isinstance(c, RLImage) for c in filas[0]):
        t = doc.add_table(rows=1, cols=nc)
        fijar_anchos(t, list(anchos))
        for j, c in enumerate(filas[0]):
            imagen(doc, c.filename, c.drawWidth, t.cell(0, j).paragraphs[0])
        return
    t = doc.add_table(rows=nf, cols=nc)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    bordes(t, "C9D3D6")
    if anchos and all(anchos):
        fijar_anchos(t, list(anchos))
    cab = isinstance(filas[0][0], RLParagraph) and filas[0][0].style.name in ("cellh", "smallh")
    for i, fila in enumerate(filas):
        tr = t.rows[i]
        if i == 0 and cab:
            trPr = tr._tr.get_or_add_trPr(); h = OxmlElement("w:tblHeader"); h.set(qn("w:val"), "true"); trPr.append(h)
        for j, v in enumerate(fila):
            c = t.cell(i, j)
            if anchos and anchos[j]:
                c.width = Pt(anchos[j])
            tcPr = c._tc.get_or_add_tcPr()
            if i == 0 and cab:
                sombrear(tcPr, AZUL)
            elif (i % 2 == 0) == cab:
                sombrear(tcPr, "F3F6F7")
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.0
            if isinstance(v, RLParagraph):
                escribir_marcado(p, v.text, v.style, color="FFFFFF" if (i == 0 and cab) else None)
            elif v is not None:
                p.add_run(str(v)).font.size = Pt(8)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def indice(doc):
    p = doc.add_paragraph()
    r = p.add_run()
    for tipo, texto in (("begin", None), (None, 'TOC \\o "1-1" \\h \\z \\u'), ("separate", None)):
        if tipo:
            f = OxmlElement("w:fldChar"); f.set(qn("w:fldCharType"), tipo)
            if tipo == "begin":
                f.set(qn("w:dirty"), "true")
            r._r.append(f)
        else:
            it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = texto; r._r.append(it)
    r2 = p.add_run("Índice: en Word, clic derecho aquí → Actualizar campo (o F9) para mostrar los números de página.")
    r2.italic = True; r2.font.size = Pt(9); r2.font.color.rgb = RGBColor.from_string(GRIS)
    r3 = p.add_run(); f = OxmlElement("w:fldChar"); f.set(qn("w:fldCharType"), "end"); r3._r.append(f)
    # Lista estática de apartados (visible aunque no se actualice el campo)
    for fl in HISTORIA:
        if isinstance(fl, RLParagraph) and fl.style.name == "h1":
            q = doc.add_paragraph(fl.getPlainText()); q.paragraph_format.space_after = Pt(2)
            for run in q.runs:
                run.font.size = Pt(10.5); run.font.name = "Arial"


def campo_pagina(parrafo):
    r = parrafo.add_run()
    for tipo, texto in (("begin", None), (None, "PAGE"), ("end", None)):
        if tipo:
            f = OxmlElement("w:fldChar"); f.set(qn("w:fldCharType"), tipo); r._r.append(f)
        else:
            it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = texto; r._r.append(it)


def emitir(doc, fl):
    if isinstance(fl, KeepTogether):
        for x in fl._content:
            emitir(doc, x)
    elif isinstance(fl, TableOfContents):
        indice(doc)
    elif isinstance(fl, RLParagraph):
        parrafo(doc, fl)
    elif isinstance(fl, RLTable):
        tabla(doc, fl)
    elif isinstance(fl, RLImage):
        imagen(doc, fl.filename, fl.drawWidth)
    elif isinstance(fl, Drawing):
        import subprocess
        from reportlab.graphics import renderPDF
        renderPDF.drawToFile(fl, str(TMP / "diagrama_flujo.pdf"))
        subprocess.run(["pdftoppm", "-r", "220", "-png", "-singlefile", str(TMP / "diagrama_flujo.pdf"),
                        str(TMP / "diagrama_flujo")], check=True)
        ruta = TMP / "diagrama_flujo.png"
        imagen(doc, ruta, fl.width)
    elif isinstance(fl, PageBreak):
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    elif isinstance(fl, Spacer):
        if fl.height >= 14:
            doc.add_paragraph().paragraph_format.space_after = Pt(fl.height / 2)


def main():
    global HISTORIA
    HISTORIA = CP.construir()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.left_margin = sec.right_margin = Inches(0.8)
    sec.top_margin, sec.bottom_margin = Inches(0.8), Inches(0.8)
    normal = doc.styles["Normal"]; normal.font.name = "Arial"; normal.font.size = Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    for nombre, tam, antes in (("Heading 1", 15, 12), ("Heading 2", 11.5, 8)):
        s = doc.styles[nombre]; s.font.name = "Arial"; s.font.size = Pt(tam); s.font.bold = True
        s.font.color.rgb = RGBColor.from_string(AZUL)
        s.element.rPr.rFonts.set(qn("w:asciiTheme"), "") if False else None
        rf = s.element.rPr.rFonts
        for att in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(att), "Arial")
        for att in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rf.get(qn(att)) is not None:
                del rf.attrib[qn(att)]
        s.paragraph_format.space_before = Pt(antes); s.paragraph_format.space_after = Pt(6)
    # encabezado y pie
    hp = sec.header.paragraphs[0]; hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hr = hp.add_run("UNACH  |  INTELIGENCIA ARTIFICIAL  |  EQUIPO 3"); hr.font.size = Pt(7.5); hr.font.color.rgb = RGBColor.from_string(GRIS)
    fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fr = fp.add_run("Proyecto integrador · Segunda entrega  |  "); fr.font.size = Pt(7.5); fr.font.color.rgb = RGBColor.from_string(GRIS)
    campo_pagina(fp)
    for fl in HISTORIA:
        emitir(doc, fl)
    salida = BASE / "documento" / "Proyecto_Integrador_IA_Equipo3_Segunda_Entrega.docx"
    doc.core_properties.title = "Proyecto integrador IA · Segunda entrega · Equipo 3"
    doc.core_properties.author = "Equipo 3 · UNACH ETDA"
    doc.save(salida)
    print("DOCX:", salida)


if __name__ == "__main__":
    main()
