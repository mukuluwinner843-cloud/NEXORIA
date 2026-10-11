# -*- coding: utf-8 -*-
"""
NEXORIA v3.4 — modèles de sommaire et choix de police
=====================================================
Modèles (paramètre « sommaire ») :
  classique : sommaire v3.3 (titre gras, filets, pages à droite) — par défaut
  pilules   : parties en pastilles arrondies, pastille noire « PAGE n »
  numerote  : parties numérotées dans un cadre arrondi, filet fin entre les lignes
  chiffres  : grand numéro en cercle, titre en serif, sous-parties en dessous
  colonnes  : titre de partie à gauche (repère vertical), sous-parties et pages en colonnes

Polices (paramètre « police ») : appliquées au corps du texte (Standard et Excellence)
et aux sommaires. La couverture garde ses polices de kit.
  defaut      : Helvetica + DejaVu Serif (v3.3)
  times       : Times (intégrée à PDF, aucune installation)
  helvetica   : Helvetica (intégrée à PDF)
  dejavu-sans : DejaVu Sans (fournie par fonts-dejavu-core)

Remarque : les sous-parties n'existent dans l'index que si le moteur les reconnaît comme titres
de niveau 2. Aujourd'hui l'index ne contient que les parties de niveau 1 : les modèles à
sous-parties affichent donc les parties seules tant qu'aucun niveau 2 n'est reconnu.
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as canvas_module

import nexoria_engine_standard as std
import nexoria_engine_excellence as exc

W, H = A4
LEFT, RIGHT = 69, 528
TOP = H - 135          # première ligne de titre
BOTTOM = 45
SPAN = TOP - BOTTOM
NBSP = " "

MODELES = ("classique", "pilules", "numerote", "chiffres", "colonnes")
POLICES_NOMS = ("defaut", "times", "helvetica", "dejavu-sans")

# --------------------------------------------------------------------------------------
# Polices
# --------------------------------------------------------------------------------------
_FD = "/usr/share/fonts/truetype/dejavu/"
try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", _FD + "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", _FD + "DejaVuSans-Bold.ttf"))
    DEJAVU_SANS_OK = True
except Exception:  # police absente : l'option dejavu-sans est alors refusée proprement
    DEJAVU_SANS_OK = False

POLICES = {
    "defaut": dict(sans="Helvetica", sans_b="Helvetica-Bold", serif="Serif",
                   serif_b="Serif-Bold", serif_i="Serif-Italic"),
    "times": dict(sans="Times-Roman", sans_b="Times-Bold", serif="Times-Roman",
                  serif_b="Times-Bold", serif_i="Times-Italic"),
    "helvetica": dict(sans="Helvetica", sans_b="Helvetica-Bold", serif="Helvetica",
                      serif_b="Helvetica-Bold", serif_i="Helvetica-Oblique"),
    "dejavu-sans": dict(sans="DejaVuSans", sans_b="DejaVuSans-Bold", serif="DejaVuSans",
                        serif_b="DejaVuSans-Bold", serif_i="DejaVuSans"),
}

# Rôle de chaque police de base du moteur (STYLES) -> rôle dans POLICES
_ROLE_OF = {"Helvetica": "sans", "Helvetica-Bold": "sans_b", "Serif": "serif",
            "Serif-Bold": "serif_b", "Serif-Italic": "serif_i"}
# Polices d'origine, mémorisées à l'import : chaque choix repart de là (pas de dérive).
_BASE_FONTS = {k: st.fontName for k, st in std.STYLES.items()}


def set_police(name):
    """Applique la police choisie au corps (STYLES). À appeler sous verrou (état global)."""
    if name not in POLICES:
        raise ValueError("police inconnue : %r" % name)
    if name == "dejavu-sans" and not DEJAVU_SANS_OK:
        raise ValueError("police dejavu-sans indisponible sur ce serveur")
    pol = POLICES[name]
    for k, st in std.STYLES.items():
        role = _ROLE_OF.get(_BASE_FONTS[k])
        if role:
            st.fontName = pol[role]
    return pol


# --------------------------------------------------------------------------------------
# Couleurs par pack
# --------------------------------------------------------------------------------------
PALETTES = {
    "standard": dict(ink=colors.HexColor("#1C1C1C"), sub=colors.HexColor("#333333"),
                     soft=colors.HexColor("#ECECEC"), rule=colors.HexColor("#CFCFCF"),
                     accent=colors.HexColor("#1C1C1C")),
    "excellence": dict(ink=colors.HexColor("#16233F"), sub=colors.HexColor("#3A3A3A"),
                       soft=colors.HexColor("#EFE8D8"), rule=colors.HexColor("#E3D9C4"),
                       accent=colors.HexColor("#B4924C")),
}


# --------------------------------------------------------------------------------------
# Données et pagination
# --------------------------------------------------------------------------------------
def _wrap(text, font, size, maxw):
    lines, cur = [], ""
    for w in text.split():
        cand = (cur + " " + w).strip()
        if not cur or stringWidth(cand, font, size) <= maxw:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def build_groups(entries, cover_pages):
    """Parties (niveau 0) avec leurs sous-parties (niveau 1), numérotées dans l'ordre."""
    groups = []
    for e in entries:
        text = e["text"].replace(NBSP, " ").strip()
        page = str(e["page"] + cover_pages)
        if e["level"] == 0:
            groups.append({"chapter": text, "page": page, "items": [], "n": len(groups) + 1})
        elif groups:
            groups[-1]["items"].append((text, page))
    return groups


def _pilule_lines(g, pol):
    return _wrap(g["chapter"].upper(), pol["sans_b"], 9.5, 330)


def _m_pilules(g, pol):
    return 24 + (len(_pilule_lines(g, pol)) - 1) * 12 + 12


def _numerote_lines(g, pol):
    return _wrap(g["chapter"].upper(), pol["sans_b"], 10.5, 360)


def _m_numerote(g, pol):
    return 40 + (len(_numerote_lines(g, pol)) - 1) * 13


def _chiffres_lines(g, pol):
    return _wrap(g["chapter"], pol["serif_b"], 11.5, 300)


def _m_chiffres(g, pol):
    L = len(_chiffres_lines(g, pol))
    last = 11 + (L - 1) * 15
    if g["items"]:
        last += 16 + (len(g["items"]) - 1) * 13
    return max(32, last + 6) + 20


def _colonnes_lines(g, pol):
    return _wrap(g["chapter"].upper(), pol["sans_b"], 9.5, 140)


def _colonnes_span(g, pol):
    L = len(_colonnes_lines(g, pol))
    N = len(g["items"])
    return max((L - 1) * 12, (N - 1) * 14 if N else 0)


def _m_colonnes(g, pol):
    return 33 + _colonnes_span(g, pol)


MEASURE = {
    "pilules": _m_pilules,
    "numerote": _m_numerote,
    "chiffres": _m_chiffres,
    "colonnes": _m_colonnes,
}


def _split(g, modele, pol):
    """Une partie trop longue pour une page est coupée en « (suite) » : rien ne déborde."""
    m = MEASURE[modele]
    if m(g, pol) <= SPAN or not g["items"]:
        return [g]
    parts, items, first = [], list(g["items"]), True
    while items:
        k = len(items)
        while k > 1 and m({**g, "items": items[:k]}, pol) > SPAN:
            k -= 1
        chunk, items = items[:k], items[k:]
        if first:
            parts.append({**g, "items": chunk})
        else:
            parts.append({**g, "chapter": g["chapter"] + " (suite)", "page": chunk[0][1], "items": chunk})
        first = False
    return parts


def paginate(groups, modele, pol):
    m = MEASURE[modele]
    pages, cur, used = [], [], 0.0
    for g in groups:
        for part in _split(g, modele, pol):
            h = m(part, pol)
            if cur and used + h > SPAN:
                pages.append(cur)
                cur, used = [], 0.0
            cur.append(part)
            used += h
    if cur or not pages:
        pages.append(cur)
    return pages


def classique_layout(groups):
    """Sommaire classique : une page si possible (v3.3). Sinon les parties sont réparties
    également entre les pages, pour ne jamais laisser une page « (suite) » avec une seule ligne."""
    pages, s = std.som_layout(groups)
    if len(pages) <= 1:
        return pages, s
    n = len(groups)
    s2 = std.som_layout.__defaults__[1]  # s_min (30 pt)
    for k in range(2, n + 1):
        size = -(-n // k)
        chunks = [groups[i:i + size] for i in range(0, n, size)]
        if len(chunks) != k:
            continue
        ok = True
        for c in chunks:
            used = sum(std.ROW_H * (len(g["clines"]) + len(g["items"]) - 1) for g in c)
            if used + (len(c) - 1) * s2 + std.RULE_RATIO * s2 > std.SOM_TOP - std.SOM_BOTTOM:
                ok = False
                break
        if ok:
            return chunks, s2
    return pages, s


def page_count(blocks, modele, pack, police):
    """Nombre de pages de sommaire, connu AVANT de composer le corps (pour numéroter les pages).
    Calculé sur les titres de niveau 1 : c'est exactement ce que l'index du corps renvoie."""
    entries = [{"level": 0, "text": b["text"], "page": 0} for b in blocks if b["kind"] == "h1"]
    if modele == "classique":
        pages, _ = classique_layout(std.som_groups(entries, 0))
        return len(pages)
    pol = POLICES[police]
    return len(paginate(build_groups(entries, 0), modele, pol))


# --------------------------------------------------------------------------------------
# Dessin
# --------------------------------------------------------------------------------------
def _titre(c, pi, modele, P, pol):
    font = pol["serif_b"] if modele in ("chiffres", "colonnes") else pol["sans_b"]
    spaced = modele in ("pilules", "chiffres")
    t = c.beginText(LEFT, H - 90)
    t.setFont(font, 26)
    t.setCharSpace(5 if spaced else 0)
    t.setFillColor(P["ink"])
    t.textOut("SOMMAIRE")
    t.setCharSpace(0)          # l'interlettrage ne doit pas rester actif pour le reste de la page
    c.drawText(t)
    if pi > 0:
        c.setFont(pol["sans"], 11)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawString(LEFT + stringWidth("SOMMAIRE", font, 26) + 40, H - 90, "(suite)")
    c.setStrokeColor(P["accent"])
    c.setLineWidth(0.9)
    c.line(LEFT, H - 100, RIGHT, H - 100)


def _d_pilules(c, g, y, P, pol):
    lines = _pilule_lines(g, pol)
    h = 24 + (len(lines) - 1) * 12
    yb = y - h
    c.setStrokeColor(P["accent"])
    c.setLineWidth(0.8)
    c.setFillColor(colors.white)
    c.roundRect(LEFT, yb, RIGHT - LEFT, h, h / 2, stroke=1, fill=0)
    c.setFillColor(P["ink"])
    c.setFont(pol["sans_b"], 9.5)
    base = yb + h / 2 - 3.2 + (len(lines) - 1) * 6
    for line in lines:
        c.drawString(LEFT + 18, base, line)
        base -= 12
    pw, ph = 66, 16
    px = RIGHT - pw - 4
    py = yb + h / 2 - 8
    c.setFillColor(P["ink"])
    c.roundRect(px, py, pw, ph, ph / 2, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(pol["sans_b"], 7.5)
    c.drawCentredString(px + pw / 2, py + 5.3, "PAGE " + g["page"])
    return y - _m_pilules(g, pol)


def _d_numerote(c, g, y, P, pol):
    lines = _numerote_lines(g, pol)
    yb = y - 22
    c.setStrokeColor(P["accent"])
    c.setLineWidth(0.8)
    c.setFillColor(colors.white)
    c.roundRect(LEFT, yb, 22, 22, 4, stroke=1, fill=1)
    c.setFillColor(P["ink"])
    c.setFont(pol["sans_b"], 9)
    c.drawCentredString(LEFT + 11, yb + 7.5, str(g["n"]))
    c.setFont(pol["sans_b"], 10.5)
    base = yb + 7.5
    for line in lines:
        c.drawString(LEFT + 38, base, line)
        base -= 13
    c.setFont(pol["sans_b"], 10)
    c.drawRightString(RIGHT, yb + 7.5, g["page"])
    rule_y = y - 31 - (len(lines) - 1) * 13
    c.setStrokeColor(P["rule"])
    c.setLineWidth(0.6)
    c.line(LEFT, rule_y, RIGHT, rule_y)
    return y - _m_numerote(g, pol)


def _d_chiffres(c, g, y, P, pol):
    lines = _chiffres_lines(g, pol)
    cx, cy = LEFT + 16, y - 16
    c.setFillColor(P["soft"])
    c.circle(cx, cy, 16, stroke=0, fill=1)
    c.setFillColor(P["ink"])
    c.setFont(pol["serif_b"], 11)
    c.drawCentredString(cx, cy - 4, "%02d." % g["n"])
    c.setFont(pol["serif_b"], 11.5)
    base = y - 11
    for line in lines:
        c.drawString(LEFT + 46, base, line)
        base -= 15
    c.setFillColor(P["accent"])
    c.setFont(pol["sans_b"], 9)
    c.drawRightString(RIGHT, y - 11, g["page"])
    if g["items"]:
        ib = y - 11 - (len(lines) - 1) * 15 - 16
        for text, page in g["items"]:
            c.setFillColor(P["sub"])
            c.setFont(pol["sans"], 9)
            c.drawString(LEFT + 46, ib, text)
            c.setFillColor(P["accent"])
            c.setFont(pol["sans_b"], 9)
            c.drawRightString(RIGHT, ib, page)
            ib -= 13
    return y - _m_chiffres(g, pol)


def _d_colonnes(c, g, y, P, pol):
    lines = _colonnes_lines(g, pol)
    span = _colonnes_span(g, pol)
    c.setStrokeColor(P["accent"])
    c.setLineWidth(2)
    c.line(LEFT - 14, y - 2, LEFT - 14, y - 10 - span - 2)
    c.setFillColor(P["ink"])
    c.setFont(pol["sans_b"], 9.5)
    b = y - 10
    for line in lines:
        c.drawString(LEFT, b, line)
        b -= 12
    if g["items"]:
        ib = y - 10
        for text, page in g["items"]:
            c.setFillColor(P["sub"])
            c.setFont(pol["sans"], 9.5)
            c.drawString(243, ib, text)
            c.setFillColor(P["ink"])
            c.setFont(pol["sans_b"], 9.5)
            c.drawRightString(RIGHT, ib, page)
            ib -= 14
    else:
        c.setFillColor(P["ink"])
        c.setFont(pol["sans_b"], 9.5)
        c.drawRightString(RIGHT, y - 10, g["page"])
    c.setStrokeColor(P["rule"])
    c.setLineWidth(0.6)
    c.line(LEFT, y - 19 - span, RIGHT, y - 19 - span)
    return y - _m_colonnes(g, pol)


DRAW = {
    "pilules": _d_pilules,
    "numerote": _d_numerote,
    "chiffres": _d_chiffres,
    "colonnes": _d_colonnes,
}


def _render_classique(entries, out_pdf, pack, pol, cover_pages):
    """Modèle classique : même géométrie et même espacement adaptatif que la v3.3, polices au choix."""
    style = exc.EXC_SOM if pack == "excellence" else std.STD_SOM
    groups = std.som_groups(entries, cover_pages)
    pages, s = classique_layout(groups)
    a = std.RULE_RATIO * s
    c = canvas_module.Canvas(out_pdf, pagesize=A4)
    left_x, text_x, page_x = LEFT, 243, RIGHT
    use_leaders = style.get("leaders", False)
    for pi, pg in enumerate(pages):
        c.setFillColor(style["title"])
        c.setFont(pol["sans_b"], 28)
        c.drawString(left_x, H - 90, "SOMMAIRE")
        if pi > 0:
            c.setFont(pol["sans"], 11)
            c.setFillColor(colors.HexColor("#666666"))
            c.drawString(left_x + stringWidth("SOMMAIRE", pol["sans_b"], 28) + 10, H - 90, "(suite)")
        c.setStrokeColor(style["title_rule"])
        c.setLineWidth(style["title_rule_w"])
        c.line(left_x, H - 100, page_x, H - 100)
        y = std.SOM_TOP
        for g in pg:
            cl = g["clines"]
            if style.get("marker") is not None:
                c.setStrokeColor(style["marker"])
                c.setLineWidth(style["marker_w"])
                c.line(left_x - 14, y + 4, left_x - 14, y - std.ROW_H * (len(cl) - 1) - 10)
            c.setFillColor(style["chapter"])
            c.setFont(pol["sans_b"], 11)
            cy = y
            for line in cl:
                c.drawString(left_x, cy, line)
                if g["solo_page"] and line == cl[-1]:
                    if use_leaders:
                        tw = stringWidth(line, pol["sans_b"], 11)
                        std._draw_leaders(c, left_x + tw + 8, page_x - 22, cy, colors.HexColor("#C8C0B0"))
                    c.setFillColor(style["page"])
                    c.drawRightString(page_x, cy, g["solo_page"])
                    c.setFillColor(style["chapter"])
                cy -= std.ROW_H
            iy = cy
            for text, page in g["items"]:
                c.setFont(pol["sans"], 10.5)
                c.setFillColor(style["item"])
                c.drawString(text_x, iy, text)
                if use_leaders:
                    tw = stringWidth(text, pol["sans"], 10.5)
                    std._draw_leaders(c, text_x + tw + 6, page_x - 22, iy, colors.HexColor("#D0C8B8"))
                c.setFillColor(style["page"])
                c.setFont(pol["sans_b"], 10.5)
                c.drawRightString(page_x, iy, page)
                iy -= std.ROW_H
            last_baseline = y - std.ROW_H * (len(cl) + len(g["items"]) - 1)
            rule_y = last_baseline - a
            c.setStrokeColor(style["sep"])
            c.setLineWidth(style["sep_w"])
            c.line(left_x, rule_y, page_x, rule_y)
            y = rule_y - (s - a)
        c.showPage()
    c.save()
    return len(pages)


def render(entries, out_pdf, modele, pack, police, cover_pages):
    """Point d'entrée : dessine le sommaire choisi. Les polices doivent être appliquées (set_police)."""
    if modele not in MODELES:
        raise ValueError("modèle de sommaire inconnu : %r" % modele)
    pol = POLICES[police]
    if modele == "classique":
        return _render_classique(entries, out_pdf, pack, pol, cover_pages)
    P = PALETTES[pack]
    groups = build_groups(entries, cover_pages)
    pages = paginate(groups, modele, pol)
    c = canvas_module.Canvas(out_pdf, pagesize=A4)
    for pi, pg in enumerate(pages):
        _titre(c, pi, modele, P, pol)
        y = TOP
        for g in pg:
            y = DRAW[modele](c, g, y, P, pol)
        c.showPage()
    c.save()
    return len(pages)
