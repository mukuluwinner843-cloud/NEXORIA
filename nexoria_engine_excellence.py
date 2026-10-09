# -*- coding: utf-8 -*-
"""
NEXORIA — moteur Pack EXCELLENCE (devoir d'élève) — v1
Même chaîne que le Pack Standard (source -> structure -> corps -> sommaire -> couverture -> fusion),
mais avec le langage graphique Excellence du kit :
  - couverture : double cadre à coins ornés, blason couleur, filets or à losange, icônes + barre or,
  - sommaire : titre marine, filet or, repères or, filets crème,
  - corps : fond parchemin, filets or, lettrine or sur 3 lignes, puces losange or,
            énoncés en carte (barre or + fond crème).
Réutilise l'analyse du texte et la typographie française du moteur Standard.
"""
import re
import html
import sys
from nexoria_engine_standard import *          # parse_source, classify, fr, balance, STYLES, TocDoc, ...
from reportlab.platypus import Table, TableStyle, Flowable
from nexoria_tables import table_flowables, diagram_flowable

PARCHMENT = colors.HexColor("#F8F6F0")
GOLD = colors.HexColor("#B89252")        # corps de texte (charte)
GOLD_C = colors.HexColor("#B4924C")      # couverture / sommaire (scripts du kit)
NAVY = colors.HexColor("#16233F")
SEP_LINE = colors.HexColor("#E3D9C4")
TINT = colors.HexColor("#EFE8D8")
CHARBON = BLACK

GOLD_HEX = "#B89252"
TABLE_PALETTE_EXCELLENCE = {"text": CHARBON, "head_bg": TINT, "grid": SEP_LINE,
                           "grid_w": 0.75, "rule": GOLD}


# --------------------------------------------------------------------------------------
# CORPS
# --------------------------------------------------------------------------------------
def plain_typo(t):
    return re.sub(r" ([?!:;])", NBSP + r"\1", t)


def cp1252_ok(t):
    try:
        t.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


class GoldDropCap(Flowable):
    """Lettrine or sur N lignes, texte justifié qui l'enveloppe (logique du kit Excellence).
    Corrections : largeur de la lettrine mesurée sur la vraie lettre, espace insécable respecté,
    espace de 13 pt restitué sous le paragraphe."""

    def __init__(self, text, cap_lines=3, body_size=12, leading=18):
        Flowable.__init__(self)
        # élision (« L’être ») : l'apostrophe reste avec la lettrine au lieu de démarrer la 1re ligne
        n = 2 if len(text) > 1 and text[1] in "\u2019'" else 1
        self.first = text[:n]
        self.rest = plain_typo(text[n:].lstrip())
        self.cap_lines = cap_lines
        self.body_size = body_size
        self.leading = leading
        self.cap_size = leading * cap_lines * 0.86
        self.cap_w = stringWidth(self.first, "Serif-Bold", self.cap_size)
        self.indent = self.cap_w + 8
        self.spaceAfter = CFG.get("gap", 13)

    def wrap(self, aw, ah):
        self.aw = aw
        words = self.rest.split(" ")
        lines, i, n = [], 0, 0
        while i < len(words):
            limit = aw - self.indent if n < self.cap_lines else aw
            cur, cw = [], 0.0
            while i < len(words):
                ww = stringWidth(words[i] + " ", "Helvetica", self.body_size)
                if cur and cw + ww > limit:
                    break
                cur.append(words[i])
                cw += ww
                i += 1
            lines.append((cur, limit))
            n += 1
        self.lines = lines
        self.total_height = max(len(lines), self.cap_lines) * self.leading
        return (aw, self.total_height)

    def draw(self):
        c = self.canv
        c.setFillColor(GOLD)
        c.setFont("Serif-Bold", self.cap_size)
        c.drawString(0, self.total_height - self.cap_size * 0.86, self.first)
        c.setFont("Helvetica", self.body_size)
        c.setFillColor(CHARBON)
        y = self.total_height - self.leading * 0.82
        sp = stringWidth(" ", "Helvetica", self.body_size)
        for idx, (ws, limit) in enumerate(self.lines):
            x0 = self.indent if idx < self.cap_lines else 0
            last = idx == len(self.lines) - 1
            line = " ".join(ws)
            nat = stringWidth(line, "Helvetica", self.body_size)
            if not last and len(ws) > 1 and nat < limit:
                extra = (limit - nat) / (len(ws) - 1)
                x = x0
                for w in ws:
                    c.drawString(x, y, w)
                    x += stringWidth(w, "Helvetica", self.body_size) + sp + extra
            else:
                c.drawString(x0, y, line)
            y -= self.leading


def gold_initial(text, style):
    """Paragraphe d'une seule ligne : initiale or de 22 pt en ligne (espace sous le bloc restitué)."""
    first = html.escape(text[0], quote=False)
    rest = fr(text[1:].lstrip())
    h = '<font size="%d" face="Serif-Bold" color="%s">%s</font>%s' % (DC_SIZE, GOLD_HEX, first, rest)
    st = ParagraphStyle(style.name + "_gdc", parent=style,
                        spaceAfter=style.spaceAfter + (DC_SIZE - style.fontSize))
    return Paragraph(h, st)


def gold_rule(space_before=4, space_after=10, thickness=1.1):
    return HRFlowable(width="100%", thickness=thickness, color=GOLD,
                      spaceBefore=space_before, spaceAfter=space_after, hAlign="LEFT")


def on_page_excellence(canvas, doc):
    t = CFG["running"]
    canvas.saveState()
    canvas.setFillColor(PARCHMENT)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(CHARBON)
    canvas.drawString(MARGIN_SIDE, H - MARGIN_TB + 18, t)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1)
    canvas.line(MARGIN_SIDE, H - MARGIN_TB + 12, W - MARGIN_SIDE, H - MARGIN_TB + 12)
    canvas.setStrokeColor(GREY)
    canvas.setStrokeAlpha(0.35)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN_SIDE, MARGIN_TB - 18, W - MARGIN_SIDE, MARGIN_TB - 18)
    canvas.setStrokeAlpha(1)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN_SIDE, MARGIN_TB - 30, t)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawCentredString(W / 2, MARGIN_TB - 30, BRAND_NAME)
    canvas.restoreState()


def pull_quote(text, fw):
    st = ParagraphStyle("quote_x", fontName="Serif-Italic", fontSize=12, leading=17.5,
                        textColor=CHARBON, alignment=TA_LEFT)
    t = Table([[Paragraph(fr(text), st)]], colWidths=[fw], spaceBefore=4, spaceAfter=CFG.get("gap", 13))
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, 0), 2, GOLD),
        ("BACKGROUND", (0, 0), (0, 0), TINT),
        ("LEFTPADDING", (0, 0), (0, 0), 16), ("RIGHTPADDING", (0, 0), (0, 0), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def formula_card(text, fw):
    st = ParagraphStyle("formula_x", fontName="Serif-Italic", fontSize=13.5, leading=20,
                        textColor=CHARBON, alignment=TA_CENTER)
    card_w = 250
    t = Table([[Paragraph(formula_markup(text), st)]], colWidths=[card_w], spaceBefore=4, spaceAfter=10)
    t.hAlign = "CENTER"
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), TINT),
        ("LINEABOVE", (0, 0), (0, 0), 0.9, GOLD), ("LINEBELOW", (0, 0), (0, 0), 0.9, GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    t.keepWithNext = 1
    return t


def gold_bullet(text, last):
    st = STYLES["bullet_last" if last else "bullet"]
    return Paragraph('<font face="Serif" color="%s">&#9670;</font>&nbsp;&nbsp;%s' % (GOLD_HEX, fr(text)), st)


def build_body_excellence(blocks, out_pdf, running_title):
    CFG["running"] = running_title
    doc = TocDoc(out_pdf, pagesize=A4, leftMargin=MARGIN_SIDE, rightMargin=MARGIN_SIDE,
                 topMargin=MARGIN_TB, bottomMargin=MARGIN_TB)
    frame = Frame(MARGIN_SIDE, MARGIN_TB, W - 2 * MARGIN_SIDE, H - 2 * MARGIN_TB, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=on_page_excellence)])
    fw = W - 2 * MARGIN_SIDE

    story = []
    st = {"fresh": True}

    def body_style(kwn, indent):
        return STYLES[("body_indent" if indent else "body") + ("_kwn" if kwn else "")]

    def first_paragraph(text, kwn):
        """Lettrine or sur 2 ou 3 lignes selon la longueur réelle du paragraphe (kit) ;
        initiale or en ligne si le paragraphe tient sur 1 ligne. Corrige un déséquilibre
        visuel : une lettrine calée sur 3 lignes pour un paragraphe qui n'en fait que 2
        laisse un vide disproportionné sous la lettre."""
        if cp1252_ok(text) and "³" not in text and "²" not in text:
            dc = GoldDropCap(text, cap_lines=3)
            dc.wrap(fw, 10000)
            if len(dc.lines) == 2:
                dc = GoldDropCap(text, cap_lines=2)
                dc.wrap(fw, 10000)
                return dc, dc.total_height
            if len(dc.lines) >= 3:
                return dc, dc.total_height
        p = gold_initial(text, body_style(kwn, False))
        return p, 46

    i = 0
    while i < len(blocks):
        b = blocks[i]
        kind, text, kwn = b["kind"], b["text"], b["kwn"]
        if kind == "h1":
            heading = text.replace(" :", NBSP + ":")
            lines = balance(heading, "Serif-Bold", 15, fw)
            markup = "<br/>".join(html.escape(l, quote=False) for l in lines)
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            first, first_h = (None, 46)
            if nxt and nxt["kind"] == "p" and not nxt.get("nodc"):
                first, first_h = first_paragraph(nxt["text"], nxt["kwn"])
            # titre + filet + premier paragraphe restent ensemble (jamais de titre isolé en bas de page)
            story.append(PageBreak() if b.get("newpage") else CondPageBreak(21 + 19 * len(lines) + 8 + 15 + first_h))
            p = Paragraph(markup, STYLES["h1"])
            p.toc_text = text
            story.append(p)
            story.append(gold_rule())
            st["fresh"] = True
            if first is not None:
                story.append(first)
                st["fresh"] = False
                i += 1          # le paragraphe suivant est déjà posé
        elif kind == "p":
            story.append(Paragraph(fr(text), body_style(kwn, not st["fresh"])))
            st["fresh"] = False
        elif kind == "formula":
            story.append(formula_card(text, fw))
            st["fresh"] = True
        elif kind == "explain":
            story.append(Paragraph(fr(text, explain=True), body_style(False, False)))
            st["fresh"] = False
        elif kind == "bullet":
            last = not (i + 1 < len(blocks) and blocks[i + 1]["kind"] == "bullet")
            story.append(gold_bullet(text, last))
            st["fresh"] = last
        elif kind == "statement":
            story.append(pull_quote(text, fw))
            st["fresh"] = True
        elif kind == "biblio":
            story.append(Paragraph(fr(text), STYLES["biblio"]))
        elif kind == "table":
            d = b["data"]
            story.extend(table_flowables(d["caption"], d["rows"], fw, palette=TABLE_PALETTE_EXCELLENCE))
            st["fresh"] = True
        elif kind == "diagram":
            d = b["data"]
            story.extend(diagram_flowable(d["title"], d["levels"], line_color=GOLD, cap_color=GREY))
            st["fresh"] = True
        i += 1

    if is_complete(blocks):
        story.append(Spacer(1, 18))
        story.append(Paragraph("\u2014 Fin du document \u2014", STYLES["closing"]))
    doc.build(story, canvasmaker=NumberedCanvas)
    return doc.toc


# --------------------------------------------------------------------------------------
# SOMMAIRE EXCELLENCE (titre marine, filet or, repères or, filets crème + leaders)
# --------------------------------------------------------------------------------------
EXC_SOM = dict(
    title=NAVY,
    title_rule=GOLD_C,
    title_rule_w=1.3,
    chapter=NAVY,
    item=colors.HexColor("#3A3A3A"),
    page=NAVY,
    sep=SEP_LINE,
    sep_w=0.8,
    marker=GOLD_C,
    marker_w=2.2,
    leaders=True,          # points de conduite élégants (nouveau)
)


def build_sommaire_excellence(entries, out_pdf):
    """Sommaire Excellence : style premium + points de conduite + repères or."""
    return render_sommaire(entries, out_pdf, EXC_SOM)


# --------------------------------------------------------------------------------------
# COUVERTURE EXCELLENCE (école) : double cadre orné, filets or, icônes
# --------------------------------------------------------------------------------------
def render_cover_school_excellence(out_pdf, school_line1, school_line2, year_text, fields, theme_lines,
                                   kit_dir, doc_word="DEVOIR", crest_path=None):
    icons = {k: kit_dir + "icon_%s.png" % k for k in ("eleve", "classe", "matiere", "encadreur", "date")}
    logo_path = kit_dir + "nexoria_logo_transparent.png"
    c = canvas_module.Canvas(out_pdf, pagesize=A4)

    def Y(t):
        return H - t

    # ---- cadre : deux filets + coins ornés ----
    outer, inner, cs = 6.5, 13.5, 42
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.1)
    for d in (outer, inner):
        c.line(cs, H - d, W - cs, H - d)
        c.line(cs, d, W - cs, d)
        c.line(d, cs, d, H - cs)
        c.line(W - d, cs, W - d, H - cs)
    c.drawImage(kit_dir + "corner_fret_tl.png", 0, H - cs, cs, cs, mask="auto")
    c.drawImage(kit_dir + "corner_fret_tr.png", W - cs, H - cs, cs, cs, mask="auto")
    c.drawImage(kit_dir + "corner_fret_bl.png", 0, 0, cs, cs, mask="auto")
    c.drawImage(kit_dir + "corner_fret_br.png", W - cs, 0, cs, cs, mask="auto")

    def gold_rule_diamond(t, half_gap=8, half_len=140):
        y = Y(t)
        c.setStrokeColor(GOLD_C)
        c.setLineWidth(1)
        c.line(W / 2 - half_len, y, W / 2 - half_gap, y)
        c.line(W / 2 + half_gap, y, W / 2 + half_len, y)
        d = 4
        c.setFillColor(GOLD_C)
        p = c.beginPath()
        p.moveTo(W / 2, y + d)
        p.lineTo(W / 2 + d, y)
        p.lineTo(W / 2, y - d)
        p.lineTo(W / 2 - d, y)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    # ---- blason couleur (optionnel : dépend de l'école du client, pas du gabarit NEXORIA) ----
    if crest_path:
        im = Image.open(crest_path)
        cw, ch = im.size
        crest_h = 205
        crest_w = crest_h * cw / ch
        c.drawImage(crest_path, W / 2 - crest_w / 2, Y(22) - crest_h, width=crest_w, height=crest_h, mask="auto")

    c.setFillColor(NAVY)
    c.setFont("Helvetica", 11)
    c.drawCentredString(W / 2, Y(243), spaced(school_line1))
    c.setFont("Times-Bold", 26)
    c.drawCentredString(W / 2, Y(273), school_line2)
    gold_rule_diamond(285)

    c.setFillColor(NAVY)
    c.setFont("Times-Bold", 40)
    c.drawCentredString(W / 2, Y(347), doc_word)
    gold_rule_diamond(360, half_len=100)

    c.setFillColor(NAVY)
    c.setFont("Times-Italic", 13)
    ty = 384
    for line in theme_lines:
        c.drawCentredString(W / 2, Y(ty), line)
        ty += 17

    box_w, box_h, box_top = 218, 55.5, 414
    c.setStrokeColor(NAVY)
    c.setLineWidth(1)
    c.rect(W / 2 - box_w / 2, Y(box_top) - box_h, box_w, box_h)
    c.setFillColor(GREY)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, Y(box_top + 22), spaced("ANNÉE SCOLAIRE"))
    c.setFillColor(NAVY)
    c.setFont("Times-Bold", 17)
    c.drawCentredString(W / 2, Y(box_top + 45), year_text)

    # ---- champs : icône + barre or + libellé + valeur + filet or ----
    icon_x, icon_r, bar_x, label_x = 130, 15, 160, 178
    underline_end = W - (icon_x - icon_r)          # symétrique du bord gauche des icônes
    t0, step = 496, 42
    keys = ["eleve", "classe", "matiere", "encadreur", "date"]
    for i, (label, value) in enumerate(fields):
        t = t0 + step * i
        icon_cy_t = t + 7
        c.drawImage(icons[keys[i]], icon_x - icon_r, Y(icon_cy_t) - icon_r, width=icon_r * 2,
                    height=icon_r * 2, mask="auto")
        c.setStrokeColor(GOLD_C)
        c.setLineWidth(1.1)
        c.line(bar_x, Y(icon_cy_t) + 16, bar_x, Y(icon_cy_t) - 16)
        c.setFillColor(GREY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(label_x, Y(t), label)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(label_x, Y(t + 17), value)
        c.setStrokeColor(GOLD_C)
        c.setLineWidth(0.6)
        c.line(label_x, Y(t + 19), underline_end, Y(t + 19))

    # ---- séparateur, devise, logo ----
    dy = Y(708.5)
    c.setStrokeColor(GOLD_C)
    c.setLineWidth(1)
    c.line(W / 2 - 130, dy, W / 2 - 10, dy)
    c.line(W / 2 + 10, dy, W / 2 + 130, dy)
    c.setFillColor(NAVY)
    c.circle(W / 2, dy, 5, fill=1, stroke=0)
    c.setFont("Times-Italic", 11)
    c.drawCentredString(W / 2, Y(735), "\u00ab L\u2019excellence ne s\u2019improvise pas. Elle s\u2019organise. \u00bb")

    nim = Image.open(logo_path)
    nw, nh = nim.size
    fh = 58
    fw_ = fh * nw / nh
    c.drawImage(logo_path, W / 2 - fw_ / 2, Y(746) - fh, width=fw_, height=fh, mask="auto")

    c.showPage()
    c.save()
