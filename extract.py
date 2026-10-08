# -*- coding: utf-8 -*-
"""
NEXORIA — extraction du texte d'un document déposé (.docx ou .pdf)
=====================================================================
Ce module LIT le texte existant du document, sans rien rédiger ni compléter.
Il renvoie :
  - le texte découpé en paragraphes (pour le moteur de mise en page) ;
  - la liste des titres que le moteur reconnaît ;
  - la liste des titres probables (style « Titre ») qu'il ne reconnaît PAS,
    pour que la personne qui valide puisse corriger avant la génération.
"""
import io
import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

import nexoria_engine_standard as std
from nexoria_tables import paragraphs_from_markdown

MAX_BYTES = 15 * 1024 * 1024
HEADING_STYLE_RE = re.compile(r"^(Heading|Titre)\s*\d*$", re.I)
PAGE_FOOTER_RE = re.compile(r"^Page \d+ sur \d+$")
TOC_STYLE_RE = re.compile(r"^(TOC|Table des mati)", re.I)
TOC_MARKER_RE = re.compile(r"^(SOMMAIRE|TABLE DES MATI\u00c8RES|TABLE DES MATIERES)$", re.I)
TRAILING_PAGE_RE = re.compile(r"\s\d+$")
END_PUNCT = (".", ":", "?", "!", "\u00bb")


class ExtractionError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def _cell_text(cell):
    return " ".join(p.text.strip() for p in cell.paragraphs if p.text.strip())


def docx_to_text(data):
    """Renvoie (texte, titres_suspects). Respecte l'ordre réel : paragraphes et tableaux."""
    try:
        doc = Document(io.BytesIO(data))
    except Exception:
        raise ExtractionError("Fichier Word illisible : format .docx attendu.", 422)

    blocks, suspects = [], []
    for child in doc.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            t = p.text.strip()
            if not t:
                continue
            style = (p.style.name or "") if p.style is not None else ""
            if TOC_STYLE_RE.match(style):
                continue  # table des matières générée par Word : elle sera refaite par NEXORIA
            blocks.append(t)
            if HEADING_STYLE_RE.match(style) and not std.is_h1(t):
                suspects.append(t)
        elif tag == "tbl":
            table = Table(child, doc)
            for row in table.rows:
                cells = [_cell_text(c) for c in row.cells]
                # une cellule fusionnée apparaît plusieurs fois : on ne la répète pas
                cells = [c for i, c in enumerate(cells) if i == 0 or c != cells[i - 1]]
                if any(cells):
                    blocks.append(" | ".join(cells))
    return "\n\n".join(blocks), suspects


def _drop_toc(lines):
    """Supprime le bloc « SOMMAIRE » d'un PDF : ses lignes portent des numéros de page
    et ne doivent pas être prises pour le corps du texte. Le corps commence au premier
    titre sans numéro de page en fin de ligne."""
    marks = [i for i, l in enumerate(lines) if TOC_MARKER_RE.match(l)]
    if not marks:
        return lines
    start = marks[0]
    body = None
    for j in range(start + 1, len(lines)):
        if std.is_h1(lines[j]) and not TRAILING_PAGE_RE.search(lines[j]):
            body = j
            break
    if body is None:
        return lines
    return lines[:start] + lines[body:]


def pdf_to_text(data):
    """Renvoie le texte d'un PDF à texte sélectionnable. Les PDF scannés ne sont pas gérés."""
    import pdfplumber
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_texts = [pg.extract_text() or "" for pg in pdf.pages]
    except Exception:
        raise ExtractionError("PDF illisible.", 422)

    lines = []
    for pt in page_texts:
        for l in pt.split("\n"):
            l = l.strip()
            if l and not PAGE_FOOTER_RE.match(l):
                lines.append(l)
    lines = _drop_toc(lines)
    if not lines:
        raise ExtractionError(
            "Aucun texte trouvé dans ce PDF : c'est probablement une photo ou un scan. "
            "Envoie plutôt le fichier Word (.docx) d'origine.", 422)

    # Les lignes d'un même paragraphe sont recollées ; un titre ou une fin de phrase ouvre un nouveau bloc.
    paras, cur = [], ""
    for l in lines:
        if std.is_h1(l):
            if cur:
                paras.append(cur)
                cur = ""
            paras.append(l)
            continue
        if cur and not cur.endswith(END_PUNCT):
            cur = cur + " " + l
        else:
            if cur:
                paras.append(cur)
            cur = l
    if cur:
        paras.append(cur)
    return "\n\n".join(paras)


def extract_document(filename, data):
    if not data:
        raise ExtractionError("Fichier vide.", 422)
    if len(data) > MAX_BYTES:
        raise ExtractionError("Fichier trop volumineux (15 Mo maximum).", 413)

    name = (filename or "").lower()
    if name.endswith(".docx"):
        text, suspects = docx_to_text(data)
    elif name.endswith(".pdf"):
        text, suspects = pdf_to_text(data), []
    else:
        raise ExtractionError("Format non pris en charge : .docx ou .pdf uniquement.", 415)

    paras = paragraphs_from_markdown(text)
    if not paras:
        raise ExtractionError("Aucun texte trouvé dans le document.", 422)

    titres = [p for p in paras if std.is_h1(p)]
    return {
        "corps_texte": "\n\n".join(paras),
        "titres": titres,
        "titres_non_reconnus": suspects,
        "nb_paragraphes": len(paras),
        "nb_caracteres": sum(len(p) for p in paras),
    }
