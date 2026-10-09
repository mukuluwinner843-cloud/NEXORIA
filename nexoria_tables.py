# -*- coding: utf-8 -*-
"""
NEXORIA — extension « tableaux et schémas »
=============================================
1. paragraphs_from_markdown() — un paragraphe logique par bloc séparé par une
   ligne vide, lignes internes recollées (annule l'habillage à ~80 colonnes
   d'un texte extrait de .docx).
2. extract_special_blocks() — repère les tableaux (« Tableau N — Titre » suivi
   de lignes « Col1| Col2 », ou un bloc de lignes « Col1| Col2 » sans légende)
   et les schémas simples (niveaux reliés par des flèches). Le reste passe
   inchangé à classify().
3. table_flowables() / diagram_flowable() — rendu sobre (Pack Standard) ou
   avec palette (Pack Excellence, via le paramètre palette/line_color).
"""
import re
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, KeepTogether, Flowable
from reportlab.pdfbase.pdfmetrics import stringWidth

BLACK = colors.HexColor("#1C1C1C")
GREY = colors.HexColor("#666666")
HEADER_BG = colors.HexColor("#ECECEC")
GRID = colors.HexColor("#B0B0B0")

TABLE_ROW_RE = re.compile(r"^(.{1,70}?)\s*\|\s*(.+)$")
TABLE_CAP_RE = re.compile(r"^Tableau\s+(\d+)\s*[\u2014\u2013\-]+\s*(.+)$", re.I)
SEPARATOR_RE = re.compile(r"^[\\\-\u2014\u2013\s]+$")


def paragraphs_from_markdown(raw):
    chunks = re.split(r"\n\s*\n", raw.strip())
    paras = []
    for c in chunks:
        line = " ".join(x.strip() for x in c.split("\n") if x.strip())
        line = line.replace("\\.", ".").replace("\\|", "|")
        if line and not SEPARATOR_RE.match(line):
            paras.append(line)
    return paras


def _is_short_label(p):
    return len(p) <= 70 and not (p.endswith(".") and len(p) > 40)


def extract_special_blocks(paras):
    out = []
    i, n = 0, len(paras)
    while i < n:
        p = paras[i]
        cap_m = TABLE_CAP_RE.match(p)
        nxt = paras[i + 1] if i + 1 < n else ""
        if cap_m and TABLE_ROW_RE.match(nxt):
            caption = "Tableau %s \u2014 %s" % (cap_m.group(1), cap_m.group(2))
            i += 1
            rows = []
            while i < n and TABLE_ROW_RE.match(paras[i]):
                m = TABLE_ROW_RE.match(paras[i])
                rows.append((m.group(1).strip(), m.group(2).strip()))
                i += 1
            out.append({"special": "table", "caption": caption, "rows": rows})
            continue
        if TABLE_ROW_RE.match(p) and not cap_m:
            j, rows = i, []
            while j < n and TABLE_ROW_RE.match(paras[j]):
                m = TABLE_ROW_RE.match(paras[j])
                rows.append((m.group(1).strip(), m.group(2).strip()))
                j += 1
            if len(rows) >= 2:
                out.append({"special": "table", "caption": None, "rows": rows})
                i = j
                continue
        if re.match(r"^Sch[ée]ma\b.*conseill", p, re.I):
            i += 1
            title = None
            if i < n and paras[i].endswith(":"):
                title = paras[i].rstrip(" :").strip()
                i += 1
            levels = []
            while i < n:
                q = paras[i]
                if q in ("\u2193", "->", "\u2192", "v"):
                    i += 1
                    continue
                if not _is_short_label(q):
                    break
                if re.search(r"\s[\u2014\u2013\-]{1,3}\s", q):
                    levels.append([x.strip() for x in re.split(r"\s[\u2014\u2013\-]{1,3}\s", q)])
                else:
                    levels.append(q)
                i += 1
            if levels:
                out.append({"special": "diagram", "title": title, "levels": levels})
            if i < n and re.match(r"^Ce (sch[ée]ma|diagramme|graphique|tableau)\b", paras[i], re.I):
                i += 1
            continue
        out.append(p)
        i += 1
    return out


def _wrap(text, font, size, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if stringWidth(t, font, size) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def table_flowables(caption, rows, fw, palette=None):
    pal = palette or {"text": BLACK, "head_bg": HEADER_BG, "grid": GRID, "grid_w": 0.6, "rule": None}
    cap_style = ParagraphStyle("tbl_cap", fontName="Helvetica-Bold", fontSize=10.5,
                               leading=14, textColor=pal["text"], spaceAfter=6)
    head_style = ParagraphStyle("tbl_head", fontName="Helvetica-Bold", fontSize=10,
                                leading=13, textColor=pal["text"])
    cell_style = ParagraphStyle("tbl_cell", fontName="Helvetica", fontSize=10,
                                leading=13.5, textColor=pal["text"])
    col0 = max(1.15 * 72, fw * 0.30)
    col1 = fw - col0
    data = [[Paragraph(rows[0][0], head_style), Paragraph(rows[0][1], head_style)]]
    for a, b in rows[1:]:
        data.append([Paragraph(a, cell_style), Paragraph(b, cell_style)])
    t = Table(data, colWidths=[col0, col1], repeatRows=1)
    style = [
        ("GRID", (0, 0), (-1, -1), pal["grid_w"], pal["grid"]),
        ("BACKGROUND", (0, 0), (-1, 0), pal["head_bg"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]
    if pal.get("rule"):
        style += [("LINEABOVE", (0, 0), (-1, 0), 1.1, pal["rule"]),
                 ("LINEBELOW", (0, 0), (-1, 0), 1.1, pal["rule"])]
    t.setStyle(TableStyle(style))
    flow = [Paragraph(caption, cap_style), t] if caption else [t]
    if len(rows) <= 7:
        return [KeepTogether(flow), Spacer(1, 12)]
    return flow + [Spacer(1, 12)]


class OrgChart(Flowable):
    def __init__(self, levels, caption=None, line_color=None, cap_color=None):
        Flowable.__init__(self)
        self.levels = levels
        self.caption = caption
        self.box_h = 30
        self.gap_v = 24
        self.line_color = line_color or BLACK
        self.cap_color = cap_color or GREY

    def wrap(self, aw, ah):
        self.aw = aw
        cap_h = 18 if self.caption else 6
        self.total_h = cap_h + len(self.levels) * self.box_h + (len(self.levels) - 1) * self.gap_v
        return (aw, self.total_h)

    def draw(self):
        c = self.canv
        y = self.total_h
        if self.caption:
            c.setFont("Helvetica-Oblique", 9.5)
            c.setFillColor(self.cap_color)
            c.drawCentredString(self.aw / 2, y - 11, self.caption)
            y -= 18
        else:
            y -= 6
        centers = []
        for level in self.levels:
            items = level if isinstance(level, list) else [level]
            gap = 16
            max_total = min(self.aw, 380)
            box_w = (max_total - gap * (len(items) - 1)) / len(items)
            x0 = (self.aw - (box_w * len(items) + gap * (len(items) - 1))) / 2
            top = y - self.box_h
            row_c = []
            for j, label in enumerate(items):
                x = x0 + j * (box_w + gap)
                c.setStrokeColor(self.line_color)
                c.setLineWidth(0.9)
                c.setFillColor(colors.white)
                c.roundRect(x, top, box_w, self.box_h, 4, stroke=1, fill=1)
                c.setFillColor(BLACK)
                c.setFont("Helvetica", 9)
                lines = _wrap(label, "Helvetica", 9, box_w - 10)[:2]
                ty = top + self.box_h / 2 + (len(lines) - 1) * 5.5
                for l in lines:
                    c.drawCentredString(x + box_w / 2, ty, l)
                    ty -= 11
                row_c.append(x + box_w / 2)
            centers.append((top, row_c))
            y = top - self.gap_v
        for i in range(len(centers) - 1):
            top_cur, rc_cur = centers[i]
            top_next, rc_next = centers[i + 1]
            cx = sum(rc_cur) / len(rc_cur)
            y1, y2 = top_cur, top_next + self.box_h
            c.setStrokeColor(self.line_color)
            c.setLineWidth(1)
            c.line(cx, y1, cx, y2 + 7)
            c.line(cx - 4, y2 + 11, cx, y2 + 7)
            c.line(cx + 4, y2 + 11, cx, y2 + 7)


def diagram_flowable(title, levels, line_color=None, cap_color=None):
    return [KeepTogether([OrgChart(levels, caption=title, line_color=line_color,
                                   cap_color=cap_color)]), Spacer(1, 12)]
