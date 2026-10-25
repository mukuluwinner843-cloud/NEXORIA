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
# Un PDF produit par NEXORIA (renvoyé en entrée) porte sa couverture, son sommaire,
# un en-tête courant et un pied de page « NOM NEXORIA Page n sur N » : rien de tout cela n'est du texte.
# « GÉOGRAPHIE NEXORIA Page 2 sur 15 GÉOGRAPHIE » : pied de page (et en-tête répété) collé à une ligne de texte.
FOOTER_INLINE_RE = re.compile(
    r"(?:(?P<h>[A-ZÀ-Ý][A-ZÀ-Ý' -]{2,40}?)\s+)?NEXORIA\s+Page\s+\d+\s+sur\s+\d+(?:\s+(?P=h))?")
FIN_DOC_RE = re.compile(r"^[\u2014\u2013-]\s*Fin\s+du\s+document\s*[\u2014\u2013-]$", re.I)
INTRO_RE = re.compile(r"^INTRODUCTION$")
FIN_DOC_INLINE_RE = re.compile(r"[\u2014\u2013-]\s*Fin\s+du\s+document\s*[\u2014\u2013-]")
PREFIX_MARK_RE = re.compile(r"SOMMAIRE|NEXORIA|DEVOIR|ÉLÈVE|ELEVE", re.I)
END_PUNCT = (".", ":", "?", "!", "\u00bb")


import unicodedata

# Caractères invisibles ou de contrôle : ils cassent la mise en page (espaces fantômes, lettres
# « avalées ») sans rien apporter au texte. Les espaces insécables sont ramenées à des espaces
# normales : le moteur remet ses propres espaces insécables avant « : » et « ; ».
INVISIBLE_RE = re.compile("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u00ad\u200b-\u200d\u2060\ufeff]")
MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
TABLE_CAPTION_RE = re.compile(r"^Tableau\s+\d+\s*[\u2014\u2013-]", re.I)
INTRO_TITLE_RE = re.compile(r"^INTRODUCTION$", re.I)
CONCL_TITLE_RE = re.compile(r"^CONCLUSION$", re.I)


def nettoyer(texte):
    """Normalise le texte d'entrée (Unicode NFC, espaces, caractères invisibles). Ne change aucun mot."""
    t = unicodedata.normalize("NFC", texte or "")
    t = t.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\u00a0", " ").replace("\u202f", " ")
    t = INVISIBLE_RE.sub("", t)
    lines = [MULTI_SPACE_RE.sub(" ", l).strip() for l in t.split("\n")]
    t = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def diagnostics(paras, nb_car):
    """Avertissements lisibles avant génération. Ils n'empêchent pas la génération : ils signalent
    ce qui demande une vérification humaine (titres absents, tableaux aplatis, texte très court)."""
    avis = []
    titres = [p for p in paras if std.is_h1(p)]
    if not any(INTRO_TITLE_RE.match(t) for t in titres):
        avis.append("Aucune section INTRODUCTION reconnue : vérifie que le titre est écrit seul sur sa ligne.")
    if not any(CONCL_TITLE_RE.match(t) for t in titres):
        avis.append("Aucune section CONCLUSION reconnue : vérifie que le titre est écrit seul sur sa ligne.")
    if len(titres) < 2:
        avis.append("Moins de deux titres reconnus : le sommaire et la structure risquent d'être incomplets.")
    nb_tab = sum(1 for p in paras if TABLE_CAPTION_RE.match(p))
    if nb_tab:
        avis.append("%d tableau(x) détecté(s) : leur contenu peut apparaître en lignes de texte si le "
                    "document source n'a pas de vrai tableau (.docx). Vérifie avant de valider." % nb_tab)
    if nb_car < 800:
        avis.append("Texte très court (%d caractères) : vérifie qu'il s'agit bien du devoir complet." % nb_car)
    return avis


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


def _running_headers(page_lines):
    """En-têtes courants : une ligne courte en capitales qui revient en tête ou en pied de 3 pages ou plus."""
    counts = {}
    for pl in page_lines:
        for l in set(pl[:2] + pl[-2:]):
            if l.isupper() and len(l) <= 40:
                counts[l] = counts.get(l, 0) + 1
    return {l for l, c in counts.items() if c >= 3}


def _drop_before_body(lines):
    """Si ce qui précède l'INTRODUCTION est une couverture ou un sommaire (marques NEXORIA/SOMMAIRE),
    on repart de l'INTRODUCTION : couverture et sommaire seront refaits par le moteur."""
    for i, l in enumerate(lines):
        if INTRO_RE.match(l) and not TRAILING_PAGE_RE.search(l):
            prefix = lines[:i]
            if prefix and any(PREFIX_MARK_RE.search(x) for x in prefix):
                return lines[i:]
            return lines
    return lines


def pdf_to_text(data):
    """Renvoie le texte d'un PDF à texte sélectionnable. Les PDF scannés ne sont pas gérés."""
    import pdfplumber
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_texts = [pg.extract_text() or "" for pg in pdf.pages]
    except Exception:
        raise ExtractionError("PDF illisible.", 422)

    # Nettoyage page par page : un pied de page peut être coupé en deux lignes par l'extraction.
    page_lines = []
    for pt in page_texts:
        txt = "\n".join(l.strip() for l in pt.split("\n") if l.strip())
        txt = FOOTER_INLINE_RE.sub("", txt)
        txt = FIN_DOC_INLINE_RE.sub("", txt)
        page_lines.append([l.strip() for l in txt.split("\n") if l.strip()])
    headers = _running_headers(page_lines)
    lines = []
    for pl in page_lines:
        for l in pl:
            for h in headers:
                if l.startswith(h + " "):
                    l = l[len(h) + 1:].strip()
                elif l.endswith(" " + h):
                    l = l[: -len(h) - 1].strip()
            if not l or PAGE_FOOTER_RE.match(l) or FIN_DOC_RE.match(l) or l in headers:
                continue
            lines.append(l)
    lines = _drop_before_body(lines)
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


def _is_nexoria_pdf(data):
    """Un PDF dont le producteur est NEXORIA : un document déjà mis en page, à réinjecter avec prudence."""
    import pdfplumber
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "NEXORIA" in str((pdf.metadata or {}).get("Producer", "")).upper()
    except Exception:
        return False


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

    paras = paragraphs_from_markdown(nettoyer(text))
    if not paras:
        raise ExtractionError("Aucun texte trouvé dans le document.", 422)

    titres = [p for p in paras if std.is_h1(p)]
    result = {
        "corps_texte": "\n\n".join(paras),
        "titres": titres,
        "titres_non_reconnus": suspects,
        "nb_paragraphes": len(paras),
        "nb_caracteres": sum(len(p) for p in paras),
    }
    result["diagnostic"] = diagnostics(paras, result["nb_caracteres"])
    if name.endswith(".pdf") and _is_nexoria_pdf(data):
        result["avertissement"] = (
            "Ce PDF a été produit par NEXORIA. Les lettrines (première lettre des paragraphes) "
            "et certaines lettres peuvent être mal relues à l'extraction. Pour un résultat fiable, "
            "envoie le fichier Word (.docx) d'origine.")
    return result
