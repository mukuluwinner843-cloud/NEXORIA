"""NEXORIA — mode MÉMOIRE (v1) : page de garde universitaire et liminaires.

Ne touche pas au moteur des devoirs. Produit deux PDF que core.py place avant le sommaire et le corps :
- la page de garde (en-tête officiel sur 7 lignes, titre, auteur, grade, diplôme, option, directeur, année) ;
- les liminaires : In Memoriam, Dédicace, Remerciements, Liste des abréviations (triée).
"""
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.pdfgen import canvas as canvas_module
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.units import mm

W, H = A4
BLACK = colors.HexColor("#1a1a1a")
GOLD = colors.HexColor("#A27C42")

ENTETE_MEMOIRE_DEFAUT = [
    "RÉPUBLIQUE DÉMOCRATIQUE DU CONGO",
    "MINISTÈRE DE L'ENSEIGNEMENT SUPÉRIEUR ET UNIVERSITAIRE",
    "UNIVERSITÉ DE KINSHASA",
    "FACULTÉ DE DROIT",
    "DÉPARTEMENT DE DROIT ÉCONOMIQUE ET SOCIAL",
    "B.P. 204 Kinshasa XI",
    "KINSHASA / LEMBA",
]


def _lignes(valeurs, defaut):
    """Renvoie exactement 7 lignes d'en-tête ; une ligne vide est conservée (espace)."""
    base = list(valeurs or defaut)
    base += [""] * (7 - len(base))
    return base[:7]


def render_cover_memoire(out_pdf, entete, titre, auteur, grade, diplome, option, directeur, annee,
                         qr_url=None, code_qr=None):
    """Page de garde : en-tête centré, titre encadré, mentions, année."""
    lignes = _lignes(entete, ENTETE_MEMOIRE_DEFAUT)
    c = canvas_module.Canvas(out_pdf, pagesize=A4)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.rect(24, 24, W - 48, H - 48)

    # En-tête officiel : 3 premières lignes en gras, suivantes plus petites
    y = H - 60
    for i, t in enumerate(lignes):
        if not t.strip():
            y -= 9
            continue
        if i < 2:
            c.setFont("Times-Bold", 11.5)
        else:
            c.setFont("Times-Roman", 10.5)
        c.setFillColor(BLACK)
        c.drawCentredString(W / 2, y, t)
        y -= 16 if i < 2 else 14

    # Titre encadré
    y -= 40
    c.setFont("Times-Bold", 17)
    c.drawCentredString(W / 2, y, "MÉMOIRE DE FIN D'ÉTUDES")
    y -= 14
    c.setStrokeColor(GOLD)
    c.line(W / 2 - 120, y, W / 2 + 120, y)
    y -= 26
    titre_lignes = _decouper(titre, "Times-Italic", 14, W - 200)
    box_top = y + 14
    y -= 20
    c.setFont("Times-Italic", 14)
    c.setFillColor(BLACK)
    for t in titre_lignes:
        c.drawCentredString(W / 2, y, t)
        y -= 19
    box_bottom = y - 4
    c.setStrokeColor(BLACK)
    c.rect(100, box_bottom, W - 200, box_top - box_bottom)

    # Mentions
    y = box_bottom - 46
    mentions = [
        ("Présenté par", auteur),
        ("Grade", grade),
        ("Diplôme visé", diplome),
        ("Option", option),
        ("Sous la direction de", directeur),
    ]
    for label, val in mentions:
        if not (val or "").strip():
            continue
        c.setFont("Times-Roman", 10.5)
        c.setFillColor(colors.HexColor("#5a5a5a"))
        c.drawCentredString(W / 2, y, label.upper())
        y -= 15
        c.setFont("Times-Bold", 13)
        c.setFillColor(BLACK)
        c.drawCentredString(W / 2, y, val.strip())
        y -= 26

    # Année académique
    c.setStrokeColor(BLACK)
    c.rect(W / 2 - 110, 118, 220, 36)
    c.setFont("Times-Roman", 9)
    c.drawCentredString(W / 2, 140, "ANNÉE ACADÉMIQUE")
    c.setFont("Times-Bold", 13)
    c.drawCentredString(W / 2, 124, annee.replace("–", "-").replace("—", "-"))

    if qr_url and code_qr:
        from reportlab.graphics.barcode import qr as qrmod
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        q = qrmod.QrCodeWidget(qr_url)
        b = q.getBounds()
        size = 70
        d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
        d.add(q)
        renderPDF.draw(d, c, W - 130, 60)
        c.setFont("Times-Roman", 6.5)
        c.setFillColor(colors.HexColor("#5a5a5a"))
        c.drawCentredString(W - 95, 52, code_qr)
    c.showPage()
    c.save()


def _decouper(texte, police, taille, largeur_max):
    """Coupe un texte en lignes qui tiennent dans largeur_max (en points)."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    mots = (texte or "").split()
    lignes, cur = [], ""
    for m in mots:
        essai = (cur + " " + m).strip()
        if stringWidth(essai, police, taille) <= largeur_max:
            cur = essai
        else:
            if cur:
                lignes.append(cur)
            cur = m
    if cur:
        lignes.append(cur)
    return lignes or [""]


def _styles():
    base = dict(fontName="Times-Roman", fontSize=12, leading=18, textColor=BLACK)
    return {
        "titre": ParagraphStyle("titre", fontName="Times-Bold", fontSize=15, leading=20,
                                alignment=TA_CENTER, spaceAfter=18, textColor=BLACK),
        "corps": ParagraphStyle("corps", alignment=TA_JUSTIFY, spaceAfter=10, firstLineIndent=18, **base),
        "signature": ParagraphStyle("signature", alignment=TA_LEFT, spaceBefore=14, fontName="Times-Bold",
                                    fontSize=12, leading=18, textColor=BLACK),
        "abr": ParagraphStyle("abr", fontName="Times-Roman", fontSize=11, leading=15, textColor=BLACK),
    }


def _paragraphes(texte):
    """Découpe sur les lignes vides ; chaque bloc est un paragraphe."""
    blocs = [b.strip() for b in (texte or "").replace("\r\n", "\n").split("\n\n")]
    return [b.replace("\n", " ") for b in blocs if b]


def _section(titre_txt, texte, st, signature=None):
    flow = [Paragraph(escape(titre_txt.upper()), st["titre"])]
    paras = _paragraphes(texte)
    for i, p in enumerate(paras):
        if signature and i == len(paras) - 1 and p.strip() == signature.strip():
            flow.append(Paragraph(escape(p), st["signature"]))
        else:
            flow.append(Paragraph(escape(p), st["corps"]))
    flow.append(PageBreak())
    return flow


def _abreviations(texte):
    """Lignes « SIGLE : définition », triées sans tenir compte de la casse."""
    entrees = []
    for ligne in (texte or "").splitlines():
        if ":" not in ligne:
            continue
        sigle, _, definition = ligne.partition(":")
        if sigle.strip() and definition.strip():
            entrees.append((sigle.strip(), definition.strip()))
    entrees.sort(key=lambda x: x[0].lower())
    return entrees


def render_liminaires(out_pdf, inmemoriam, dedicace, remerciements, abreviations, signature_remerciements=None):
    """Écrit les liminaires dans out_pdf. Renvoie le nombre de pages."""
    st = _styles()
    flow = []
    if (inmemoriam or "").strip():
        flow += _section("In Memoriam", inmemoriam, st)
    if (dedicace or "").strip():
        flow += _section("Dédicace", dedicace, st)
    if (remerciements or "").strip():
        flow += _section("Remerciements", remerciements, st, signature=signature_remerciements)
    entrees = _abreviations(abreviations)
    if entrees:
        flow.append(Paragraph("LISTE DES ABRÉVIATIONS", st["titre"]))
        data = [[Paragraph("<b>%s</b>" % escape(s), st["abr"]), Paragraph(escape(d), st["abr"])] for s, d in entrees]
        t = Table(data, colWidths=[28 * mm, 130 * mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.2, colors.HexColor("#cfc8bb")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(t)
    if not flow:
        # Rien à écrire : un PDF vide d'une page est remplacé par l'absence de fichier (géré par l'appelant)
        return 0
    doc = SimpleDocTemplate(out_pdf, pagesize=A4, leftMargin=30 * mm, rightMargin=30 * mm,
                            topMargin=30 * mm, bottomMargin=30 * mm)
    doc.build(flow)
    from pypdf import PdfReader
    return len(PdfReader(out_pdf).pages)
