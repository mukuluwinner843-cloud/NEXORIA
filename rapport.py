# -*- coding: utf-8 -*-
"""Rapport PDF du registre NEXORIA (archive interne, avec noms : ne jamais publier)."""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OR = colors.HexColor("#B89252")
CH = colors.HexColor("#1C1C1C")

CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, leading=9, alignment=TA_LEFT, textColor=CH)
HEAD = ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white)
TITRE = ParagraphStyle("titre", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=CH)
SOUS = ParagraphStyle("sous", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#666666"))


def _esc(v):
    return (str(v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_report(data):
    """data = contenu du registre ({"documents": [...]}). Renvoie le PDF en octets."""
    docs = sorted(data.get("documents", []), key=lambda d: (str(d.get("date", "")), str(d.get("code", ""))))
    entetes = ["Date", "Élève", "Établissement", "Matière", "Encadreur", "Pack", "Code", "Statut"]
    lignes = [[Paragraph(e, HEAD) for e in entetes]]
    for d in docs:
        lignes.append([
            Paragraph(_esc(d.get("date")), CELL),
            Paragraph(_esc(d.get("eleve")), CELL),
            Paragraph(_esc(d.get("etablissement")), CELL),
            Paragraph(_esc(d.get("matiere")), CELL),
            Paragraph(_esc(d.get("encadreur") or d.get("titulaire")), CELL),
            Paragraph(_esc(d.get("pack")), CELL),
            Paragraph(_esc(d.get("code")), CELL),
            Paragraph(_esc(d.get("statut")), CELL),
        ])
    largeurs = [2.2 * cm, 4.6 * cm, 5.2 * cm, 3.2 * cm, 3.8 * cm, 1.8 * cm, 4.6 * cm, 3.6 * cm]
    tab = Table(lignes, colWidths=largeurs, repeatRows=1)
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CH),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, OR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F6F0")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    histoire = [
        Paragraph("NEXORIA — Registre des documents", TITRE),
        Spacer(1, 4),
        Paragraph("Généré le %s · %d document(s) · Document interne, ne pas publier." %
                  (datetime.now().strftime("%d/%m/%Y %H:%M"), len(docs)), SOUS),
        Spacer(1, 10),
    ]
    if not docs:
        histoire.append(Paragraph("Aucun document enregistré pour le moment.", SOUS))
    else:
        histoire.append(tab)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title="NEXORIA — Registre des documents", author="NEXORIA")
    doc.build(histoire)
    return buf.getvalue()
