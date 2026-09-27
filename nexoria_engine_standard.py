# -*- coding: utf-8 -*-
"""
NEXORIA — moteur Pack STANDARD (devoir d'élève) — v1
Reprend les paramètres des scripts du kit (charte, marges, styles, sommaire Standard,
page de garde Standard) et les rend génériques : texte brut -> PDF complet.
Chaîne : source -> structure -> corps -> toc -> sommaire -> page de garde -> fusion.
"""
import re
import html
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, KeepTogether, CondPageBreak, PageBreak
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as canvas_module
from PIL import Image
from pypdf import PdfReader, PdfWriter

FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("Serif", FD + "DejaVuSerif.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Bold", FD + "DejaVuSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Italic", FD + "DejaVuSerif-Italic.ttf"))

W, H = A4
BLACK = colors.HexColor("#1C1C1C")
GREY = colors.HexColor("#666666")
LIGHT_GREY = colors.HexColor("#AFAFAF")
GREY_LINE = colors.HexColor("#CFCFCF")

BRAND_NAME = "NEXORIA"
MARGIN_TB = 70.9      # 2,5 cm
MARGIN_SIDE = 82
COVER_PAGES = 2       # page de garde + sommaire
NBSP = "\u00a0"

CFG = {"running": "", "gap": 13, "cover_pages": 2}

# --------------------------------------------------------------------------------------
# 1. LECTURE DE LA SOURCE
# --------------------------------------------------------------------------------------
META_KEYS = {
    "Établissement": "etab", "Nom de l’élève": "eleve", "Classe": "classe",
    "Année scolaire": "annee", "Matière": "matiere", "Titulaire": "titulaire",
    "Thème": "theme", "Travail demandé": "travail", "Date de remise": "date",
}


def parse_source(path):
    raw = open(path, encoding="utf-8").read()
    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    k = lines.index("INTRODUCTION")
    head, body = lines[:k], lines[k:]
    meta, title_block = {}, []
    for l in head:
        m = re.match(r"^([^:]{2,30}?)\s*:\s*(.+)$", l)
        if m and m.group(1) in META_KEYS:
            meta[META_KEYS[m.group(1)]] = m.group(2).strip()
        else:
            title_block.append(l)
    return meta, title_block, body


SECTION_WORDS = ("BIBLIOGRAPHIE", "RÉFÉRENCES", "ANNEXE")


def is_h1(l):
    if re.match(r"^[IVXLCDM]+\.\s+\S", l) and l == l.upper():
        return True
    return l in ("INTRODUCTION", "CONCLUSION") or (l == l.upper() and l.startswith(SECTION_WORDS))


def section_kind(h):
    if h.startswith(("BIBLIOGRAPHIE", "RÉFÉRENCES")):
        return "biblio"
    if h.startswith("ANNEXE"):
        return "annexe"
    return "body"


def is_formula(l):
    return " = " in l and len(l) <= 45 and not l.endswith(".")


def classify(lines):
    out = []
    sect = "body"
    for l in lines:
        prev = out[-1] if out else None
        after_colon = bool(prev) and prev["text"].endswith(":") and prev["kind"] == "p"
        if is_h1(l):
            k = "h1"
            sect = section_kind(l)
        elif sect == "biblio":
            k = "biblio"
        elif is_formula(l):
            k = "formula"
        elif after_colon and l[0].islower():
            k = "bullet"
        elif prev and prev["kind"] == "bullet" and l[0].islower():
            k = "bullet"
        elif after_colon and l[0].isupper():
            k = "statement"
        elif l.startswith("où "):
            k = "explain"
        else:
            k = "p"
        out.append({"kind": k, "text": l, "kwn": False, "sect": sect,
                    "newpage": k == "h1" and sect == "annexe", "nodc": sect == "annexe"})
        if after_colon and k in ("formula", "bullet", "statement"):
            prev["kwn"] = True
        if prev and prev["kind"] == "formula" and k == "explain":
            prev["kwn"] = True
    return out


# --------------------------------------------------------------------------------------
# 2. TYPOGRAPHIE FRANÇAISE
# --------------------------------------------------------------------------------------
STOP = {"de", "des", "du", "et", "la", "le", "les", "un", "une", "à", "au", "aux", "en",
        "dans", "sur", "par", "pour", "leurs", "leur", "son", "sa", "ses", "ou", "ni",
        "qui", "que", "ce", "cet", "cette", "d’", "l’"}


def balance(text, font, size, maxw):
    """Coupe un titre en 2 lignes équilibrées (sans finir une ligne sur un mot-outil)."""
    if stringWidth(text, font, size) <= maxw:
        return [text]
    words = text.split(" ")
    best = None
    for k in range(1, len(words)):
        l1, l2 = " ".join(words[:k]), " ".join(words[k:])
        w1, w2 = stringWidth(l1, font, size), stringWidth(l2, font, size)
        if w1 > maxw or w2 > maxw:
            continue
        last = words[k - 1].lower()
        pen = 10000 if (last in STOP or len(last) <= 2) else 0
        score = max(w1, w2) + pen
        if best is None or score < best[0]:
            best = (score, l1, l2)
    return [best[1], best[2]] if best else [text]


def nbsp_rules(t):
    t = re.sub(r" ([?!:;])", NBSP + r"\1", t)          # espace insécable avant ? ! : ;
    t = re.sub(r"(\d) (kg/m³|Pa\b)", r"\1" + NBSP + r"\2", t)
    return t


def wrap_glyphs(t):
    """Caractères absents de Helvetica (ex. lettres grecques) -> police Serif italique."""
    out = []
    for ch in t:
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            out.append('<font face="Serif-Italic">%s</font>' % ch)
    return "".join(out)


def italic_symbols(t):
    """Symboles physiques des lignes « où … » en italique (P, F, S, m, V, ρ, P0…)."""
    def repl(m):
        tok = m.group(0)
        tok = re.sub(r"^([A-Za-z])(\d)$", r"\1<sub>\2</sub>", tok)
        return '<font face="Serif-Italic">%s</font>' % tok
    pat = r"(?<=où )[A-Za-z]\d?(?= )|(?<=, )[A-Za-z]\d?(?= )|(?<= et )[A-Za-z]\d?(?= )"
    return re.sub(pat, repl, t)


def sup_rules(t):
    """Exposants Unicode (², ³) : non rendus par les polices de base -> balise <super>."""
    for ch, d in (("¹", "1"), ("²", "2"), ("³", "3")):
        t = t.replace(ch, "<super>%s</super>" % d)
    return t


def fr(text, explain=False):
    t = html.escape(text, quote=False)
    t = wrap_glyphs(t)
    t = nbsp_rules(t)
    t = sup_rules(t)
    if explain:
        t = italic_symbols(t)
    return t


def formula_markup(text):
    t = html.escape(text, quote=False)
    return re.sub(r"\b([A-Za-z])(\d)\b", r"\1<sub>\2</sub>", t)


# --------------------------------------------------------------------------------------
# 3. CORPS DE TEXTE (styles = kit Standard : noir & blanc)
# --------------------------------------------------------------------------------------
def _body_style(name, indent=False, kwn=False, **kw):
    base = dict(fontName="Helvetica", fontSize=12, leading=18, textColor=BLACK,
                alignment=TA_JUSTIFY, spaceAfter=13, allowOrphans=0, allowWidows=0,
                keepWithNext=1 if kwn else 0)
    if indent:
        base["firstLineIndent"] = 16
    base.update(kw)
    return ParagraphStyle(name, **base)


STYLES = {
    "h1": ParagraphStyle("H1TOC", fontName="Serif-Bold", fontSize=15, leading=19,
                         textColor=BLACK, spaceBefore=21, spaceAfter=8),
    "body": _body_style("body"),
    "body_kwn": _body_style("body_kwn", kwn=True),
    "body_indent": _body_style("body_indent", indent=True),
    "body_indent_kwn": _body_style("body_indent_kwn", indent=True, kwn=True),
    "formula": ParagraphStyle("formula", fontName="Serif-Italic", fontSize=13.5, leading=20,
                              textColor=BLACK, alignment=TA_CENTER, spaceBefore=4,
                              spaceAfter=10, keepWithNext=1),
    "quote": ParagraphStyle("quote", fontName="Serif-Italic", fontSize=12, leading=17.5,
                            textColor=BLACK, alignment=TA_LEFT, leftIndent=14,
                            spaceBefore=4, spaceAfter=13),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=12, leading=18,
                             textColor=BLACK, leftIndent=16, firstLineIndent=-16,
                             spaceAfter=6, alignment=TA_JUSTIFY, allowOrphans=0, allowWidows=0),
    "bullet_last": ParagraphStyle("bullet_last", fontName="Helvetica", fontSize=12, leading=18,
                                  textColor=BLACK, leftIndent=16, firstLineIndent=-16,
                                  spaceAfter=13, alignment=TA_JUSTIFY, allowOrphans=0, allowWidows=0),
    "biblio": ParagraphStyle("biblio", fontName="Helvetica", fontSize=10.5, leading=15,
                             textColor=BLACK, alignment=TA_LEFT, leftIndent=18,
                             firstLineIndent=-18, spaceAfter=9, allowOrphans=0, allowWidows=0),
    "closing": ParagraphStyle("closing", fontName="Helvetica", fontSize=9, leading=13,
                              textColor=GREY, alignment=TA_CENTER),
}


def plain_rule(space_before=4, space_after=10, thickness=0.8):
    return HRFlowable(width="100%", thickness=thickness, color=BLACK,
                      spaceBefore=space_before, spaceAfter=space_after, hAlign="LEFT")


DC_SIZE = 22


def simple_dropcap(text, style):
    """Lettrine simple du kit (initiale 22 pt en ligne). ReportLab cale la 1re ligne sur la
    taille de la lettrine : le bloc de texte descend de (22 - 12) = 10 pt dans sa boîte, ce qui
    mangeait l'espace sous le paragraphe. On le restitue ici (le kit d'origine l'ignorait)."""
    first = text[0]
    rest = fr(text[1:].lstrip())
    html_ = '<font size="%d" face="Serif-Bold">%s</font>%s' % (DC_SIZE, html.escape(first, quote=False), rest)
    dc_style = ParagraphStyle(style.name + "_dc", parent=style,
                              spaceAfter=style.spaceAfter + (DC_SIZE - style.fontSize))
    return Paragraph(html_, dc_style)


def on_page(canvas, doc):
    t = CFG["running"]
    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(BLACK)
    canvas.drawString(MARGIN_SIDE, H - MARGIN_TB + 18, t)
    canvas.setStrokeColor(BLACK)
    canvas.setLineWidth(0.8)
    canvas.line(MARGIN_SIDE, H - MARGIN_TB + 12, W - MARGIN_SIDE, H - MARGIN_TB + 12)
    canvas.setStrokeColor(GREY)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN_SIDE, MARGIN_TB - 18, W - MARGIN_SIDE, MARGIN_TB - 18)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN_SIDE, MARGIN_TB - 30, t)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawCentredString(W / 2, MARGIN_TB - 30, BRAND_NAME)
    canvas.restoreState()


class NumberedCanvas(canvas_module.Canvas):
    def __init__(self, *args, **kwargs):
        canvas_module.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.setFont("Helvetica", 8)
            self.setFillColor(GREY)
            self.drawRightString(W - MARGIN_SIDE, MARGIN_TB - 30,
                                 "Page %d sur %d" % (self._pageNumber + CFG["cover_pages"], total + CFG["cover_pages"]))
            canvas_module.Canvas.showPage(self)
        canvas_module.Canvas.save(self)


class TocDoc(BaseDocTemplate):
    def __init__(self, *a, **k):
        BaseDocTemplate.__init__(self, *a, **k)
        self.toc = []

    def afterFlowable(self, f):
        def visit(fl):
            if isinstance(fl, KeepTogether):
                for c in fl._content:
                    visit(c)
            elif isinstance(fl, Paragraph) and fl.style.name == "H1TOC":
                self.toc.append({"level": 0, "text": getattr(fl, "toc_text", fl.getPlainText()),
                                 "page": self.page})
        visit(f)


def build_body(blocks, out_pdf, running_title):
    CFG["running"] = running_title
    doc = TocDoc(out_pdf, pagesize=A4, leftMargin=MARGIN_SIDE, rightMargin=MARGIN_SIDE,
                 topMargin=MARGIN_TB, bottomMargin=MARGIN_TB)
    frame = Frame(MARGIN_SIDE, MARGIN_TB, W - 2 * MARGIN_SIDE, H - 2 * MARGIN_TB, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=on_page)])
    fw = W - 2 * MARGIN_SIDE

    story = []
    st = {"fresh": True, "dc": False}

    def body_style(kwn, indent):
        return STYLES[("body_indent" if indent else "body") + ("_kwn" if kwn else "")]

    for i, b in enumerate(blocks):
        kind, text, kwn = b["kind"], b["text"], b["kwn"]
        if kind == "h1":
            plain = text
            heading = plain.replace(" :", NBSP + ":")
            lines = balance(heading, "Serif-Bold", 15, fw)
            markup = "<br/>".join(html.escape(l, quote=False) for l in lines)
            # place minimale pour éviter un titre isolé : espace avant + titre + filet + 2 lignes de texte
            story.append(PageBreak() if b.get("newpage") else CondPageBreak(21 + 19 * len(lines) + 8 + 15 + 46))
            p = Paragraph(markup, STYLES["h1"])
            p.toc_text = plain
            story.append(p)
            story.append(plain_rule())
            st["fresh"], st["dc"] = True, b.get("sect", "body") == "body"
        elif kind == "p":
            if st["dc"]:
                story.append(simple_dropcap(text, body_style(kwn, False)))
                st["dc"] = False
            else:
                story.append(Paragraph(fr(text), body_style(kwn, not st["fresh"])))
            st["fresh"] = False
        elif kind == "formula":
            story.append(Paragraph(formula_markup(text), STYLES["formula"]))
            st["fresh"], st["dc"] = True, False
        elif kind == "explain":
            story.append(Paragraph(fr(text, explain=True), body_style(False, False)))
            st["fresh"], st["dc"] = False, False
        elif kind == "bullet":
            last = not (i + 1 < len(blocks) and blocks[i + 1]["kind"] == "bullet")
            story.append(Paragraph("-&nbsp;&nbsp;" + fr(text),
                                   STYLES["bullet_last" if last else "bullet"]))
            st["fresh"], st["dc"] = last, False
        elif kind == "statement":
            story.append(Paragraph(fr(text), STYLES["quote"]))
            st["fresh"], st["dc"] = True, False
        elif kind == "biblio":
            story.append(Paragraph(fr(text), STYLES["biblio"]))

    if is_complete(blocks):
        story.append(Spacer(1, 18))
        story.append(Paragraph("\u2014 Fin du document \u2014", STYLES["closing"]))
    doc.build(story, canvasmaker=NumberedCanvas)
    return doc.toc


# --------------------------------------------------------------------------------------
# 4. SOMMAIRE (variante Standard : titre gras, filets gris, pages exactes)
# --------------------------------------------------------------------------------------
ROW_H = 20
SOM_TOP = H - 135          # 1re ligne de titre
SOM_BOTTOM = 45
RULE_RATIO = 16.5 / 40.0   # position du filet entre deux entrées (centré)


def som_chapter_lines(text, limit=58):
    if len(text) <= limit:
        return [text]
    lines, cur = [], ""
    for w in text.split():
        if len((cur + " " + w).strip()) <= limit:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def som_groups(entries, cover_pages):
    groups = []
    for e in entries:
        page = e["page"] + cover_pages
        if e["level"] == 0:
            groups.append({"chapter": e["text"].replace(NBSP, " "), "items": [], "solo_page": str(page)})
        else:
            groups[-1]["items"].append((e["text"], str(page)))
            groups[-1]["solo_page"] = None
    for g in groups:
        g["clines"] = som_chapter_lines(g["chapter"])
    return groups


def som_layout(groups, s_default=40.0, s_min=30.0):
    """Sommaire adaptatif : espacement normal (40 pt) ; resserré jusqu'à 30 pt si nécessaire ;
    au-delà, le sommaire continue sur une 2e page. Jamais de débordement."""
    span = SOM_TOP - SOM_BOTTOM
    hs = [ROW_H * (len(g["clines"]) + len(g["items"]) - 1) for g in groups]
    n = len(groups)
    if n == 0:
        return [[]], s_default
    s_max = (span - sum(hs)) / (max(n - 1, 0) + RULE_RATIO)
    if s_max >= s_min:
        return [groups], min(s_default, s_max)
    s = s_default
    a = RULE_RATIO * s
    pages, cur, sh = [], [], 0.0
    for g, h in zip(groups, hs):
        ext = sh + h + len(cur) * s + a
        if cur and ext > span:
            pages.append(cur)
            cur, sh = [], 0.0
        cur.append(g)
        sh += h
    pages.append(cur)
    return pages, s


def sommaire_pages(blocks):
    """Nombre de pages de sommaire, connu AVANT de composer le corps (pour numéroter les pages)."""
    entries = [{"level": 0, "text": b["text"], "page": 0} for b in blocks if b["kind"] == "h1"]
    pages, _ = som_layout(som_groups(entries, 0))
    return len(pages)


STD_SOM = dict(title=BLACK, title_rule=BLACK, title_rule_w=1.0, chapter=BLACK,
               item=colors.HexColor("#333333"), page=BLACK, sep=GREY_LINE, sep_w=0.7, marker=None, marker_w=0)


def render_sommaire(entries, out_pdf, style):
    groups = som_groups(entries, CFG["cover_pages"])
    pages, s = som_layout(groups)
    a = RULE_RATIO * s
    c = canvas_module.Canvas(out_pdf, pagesize=A4)
    left_x, text_x, page_x = 69, 243, 528
    for pi, pg in enumerate(pages):
        c.setFillColor(style["title"])
        c.setFont("Helvetica-Bold", 28)
        c.drawString(left_x, H - 90, "SOMMAIRE")
        if pi > 0:
            c.setFont("Helvetica", 11)
            c.setFillColor(GREY)
            c.drawString(left_x + stringWidth("SOMMAIRE", "Helvetica-Bold", 28) + 10, H - 90, "(suite)")
        c.setStrokeColor(style["title_rule"])
        c.setLineWidth(style["title_rule_w"])
        c.line(left_x, H - 100, page_x, H - 100)
        y = SOM_TOP
        for g in pg:
            cl = g["clines"]
            if style["marker"] is not None:
                c.setStrokeColor(style["marker"])
                c.setLineWidth(style["marker_w"])
                c.line(left_x - 14, y + 4, left_x - 14, y - ROW_H * (len(cl) - 1) - 10)
            c.setFillColor(style["chapter"])
            c.setFont("Helvetica-Bold", 11)
            cy = y
            for line in cl:
                c.drawString(left_x, cy, line)
                if g["solo_page"] and line == cl[-1]:
                    c.drawRightString(page_x, cy, g["solo_page"])
                cy -= ROW_H
            iy = cy
            c.setFont("Helvetica", 10.5)
            for text, page in g["items"]:
                c.setFillColor(style["item"])
                c.drawString(text_x, iy, text)
                c.setFillColor(style["page"])
                c.setFont("Helvetica-Bold", 10.5)
                c.drawRightString(page_x, iy, page)
                c.setFont("Helvetica", 10.5)
                iy -= ROW_H
            last_baseline = y - ROW_H * (len(cl) + len(g["items"]) - 1)
            rule_y = last_baseline - a
            c.setStrokeColor(style["sep"])
            c.setLineWidth(style["sep_w"])
            c.line(left_x, rule_y, page_x, rule_y)
            y = rule_y - (s - a)
        c.showPage()
    c.save()
    return len(pages)


def build_sommaire(entries, out_pdf):
    return render_sommaire(entries, out_pdf, STD_SOM)


# --------------------------------------------------------------------------------------
# 5. PAGE DE GARDE STANDARD (école) — géométrie du kit, 3 chevauchements corrigés
# --------------------------------------------------------------------------------------
def spaced(s):
    return "   ".join(" ".join(w) for w in s.split())


def render_cover_school_standard(out_pdf, school_line1, school_line2, year_text, fields,
                                 theme_lines, crest_path, logo_path, doc_word="DEVOIR"):
    c = canvas_module.Canvas(out_pdf, pagesize=A4)

    def Y(t):  # t = distance depuis le haut de la page
        return H - t

    m = 24
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.rect(m, m, W - 2 * m, H - 2 * m)

    def rule(t, half):
        c.setStrokeColor(LIGHT_GREY)
        c.setLineWidth(0.8)
        c.line(W / 2 - half, Y(t), W / 2 + half, Y(t))

    # blason : détaché du cadre (dans le kit, il touchait le filet supérieur)
    if crest_path:
        im = Image.open(crest_path)
        cw, ch = im.size
        crest_h = 186
        crest_w = crest_h * cw / ch
        c.drawImage(crest_path, W / 2 - crest_w / 2, Y(40) - crest_h, width=crest_w,
                    height=crest_h, mask="auto")

    c.setFillColor(BLACK)
    c.setFont("Helvetica", 11)
    c.drawCentredString(W / 2, Y(243), spaced(school_line1))
    c.setFont("Times-Bold", 26)
    c.drawCentredString(W / 2, Y(273), school_line2)
    rule(285, 140)

    c.setFont("Times-Bold", 40)
    c.drawCentredString(W / 2, Y(347), doc_word)
    rule(360, 100)

    # thème du devoir (présent dans le texte source, absent du gabarit d'origine)
    c.setFont("Times-Italic", 13)
    ty = 384
    for line in theme_lines:
        c.drawCentredString(W / 2, Y(ty), line)
        ty += 17

    box_w, box_h, box_top = 218, 55.5, 414
    c.setStrokeColor(BLACK)
    c.setLineWidth(1)
    c.rect(W / 2 - box_w / 2, Y(box_top) - box_h, box_w, box_h)
    c.setFillColor(GREY)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, Y(box_top + 22), spaced("ANNÉE SCOLAIRE"))
    c.setFillColor(BLACK)
    c.setFont("Times-Bold", 17)
    c.drawCentredString(W / 2, Y(box_top + 45), year_text)

    label_x = 130
    underline_end = W - label_x          # symétrique : le kit s'arrêtait sur le cadre
    t0, step = 496, 42
    for i, (label, value) in enumerate(fields):
        t = t0 + step * i
        c.setFillColor(GREY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(label_x, Y(t), label)
        c.setFillColor(BLACK)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(label_x, Y(t + 17), value)
        c.setStrokeColor(LIGHT_GREY)
        c.setLineWidth(0.6)
        c.line(label_x, Y(t + 19), underline_end, Y(t + 19))

    c.setStrokeColor(LIGHT_GREY)
    c.setLineWidth(0.8)
    c.line(W / 2 - 130, Y(708.5), W / 2 + 130, Y(708.5))
    c.setFillColor(BLACK)
    c.setFont("Times-Italic", 11)
    c.drawCentredString(W / 2, Y(735), "\u00ab L\u2019excellence ne s\u2019improvise pas. Elle s\u2019organise. \u00bb")

    # logo NEXORIA : remonté pour rester à l'intérieur du cadre (il le chevauchait)
    nim = Image.open(logo_path)
    nw, nh = nim.size
    fh = 52
    fw_ = fh * nw / nh
    c.drawImage(logo_path, W / 2 - fw_ / 2, Y(746) - fh, width=fw_, height=fh, mask="auto")

    c.showPage()
    c.save()


# --------------------------------------------------------------------------------------
# 6. FUSION + MÉTADONNÉES
# --------------------------------------------------------------------------------------
def merge(parts, out_pdf, title, author):
    w = PdfWriter()
    for p in parts:
        for page in PdfReader(p).pages:
            w.add_page(page)
    w.add_metadata({"/Title": title, "/Author": author, "/Creator": "NEXORIA",
                    "/Producer": "NEXORIA — Pack Standard"})
    with open(out_pdf, "wb") as f:
        w.write(f)


# --------------------------------------------------------------------------------------
# 7. FIN DE DOCUMENT, ÉQUILIBRAGE DE LA DERNIÈRE PAGE, RAPPORT DE REVUE
# --------------------------------------------------------------------------------------
def is_complete(blocks):
    """Le document est considéré comme terminé s'il se ferme sur une conclusion, une bibliographie
    ou des annexes. Sinon on n'affiche PAS « Fin du document » (texte peut-être incomplet)."""
    h1 = [b for b in blocks if b["kind"] == "h1"]
    return bool(h1) and (h1[-1]["text"].startswith("CONCLUSION") or h1[-1].get("sect") in ("biblio", "annexe"))


def review_report(blocks):
    h1 = [b["text"] for b in blocks if b["kind"] == "h1"]
    notes = []
    if not any(t.startswith("CONCLUSION") for t in h1):
        notes.append("REQUIRES_REVIEW : aucune CONCLUSION détectée (texte peut-être incomplet)")
    if not any(section_kind(t) == "biblio" for t in h1):
        notes.append("INFO : aucune bibliographie fournie (rien n'a été inventé)")
    if not any(section_kind(t) == "annexe" for t in h1):
        notes.append("INFO : aucune annexe fournie")
    return notes


def set_gap(g):
    """Espace entre paragraphes (13 pt de référence) : seul réglage autorisé pour équilibrer les pages."""
    CFG["gap"] = g
    for k in ("body", "body_kwn", "body_indent", "body_indent_kwn", "bullet_last", "quote"):
        STYLES[k].spaceAfter = g


def last_page_fill(pdf_path):
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        ws = pdf.pages[-1].crop((0, MARGIN_TB - 2, W, H - MARGIN_TB + 2)).extract_words()
        if not ws:
            return n, 0.0
        return n, (max(w["bottom"] for w in ws) - MARGIN_TB) / (H - 2 * MARGIN_TB)


def build_balanced(builder, blocks, out_pdf, running, min_fill=0.35,
                   gaps=(13, 12.5, 13.5, 12, 14, 11.5, 14.5)):
    """Évite une dernière page presque vide (« page orpheline ») sans rien ajouter ni agrandir le texte :
    on ne fait varier que l'espace entre paragraphes (±1,5 pt autour de 13 pt), uniformément sur tout le document."""
    tries = []
    for g in gaps:
        set_gap(g)
        toc = builder(blocks, out_pdf, running)
        n, fill = last_page_fill(out_pdf)
        tries.append((g, n, round(fill, 2)))
        if n <= 1 or fill >= min_fill:
            return toc, g, tries
    set_gap(13)
    toc = builder(blocks, out_pdf, running)
    return toc, 13, tries
