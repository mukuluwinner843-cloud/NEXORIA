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
  defaut     : Helvetica (corps) + DejaVu Serif (titres)
  helvetica  : Helvetica partout
  times      : Times partout
  inter      : Inter partout
  montserrat : Montserrat partout
  futura     : Jost partout (esprit Futura, Futura elle-même n'est pas libre)
  garamond   : EB Garamond partout
Registre et polices : nexoria_polices.py (TTF dans fonts/).

Remarque : les sous-parties n'existent dans l'index que si le moteur les reconnaît comme titres
de niveau 2. Aujourd'hui l'index ne contient que les parties de niveau 1 : les modèles à
sous-parties affichent donc les parties seules tant qu'aucun niveau 2 n'est reconnu.
"""
import os
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as canvas_module

import nexoria_polices as P
import nexoria_engine_standard as std
import nexoria_engine_excellence as exc

W, H = A4
LEFT, RIGHT = std.MARGIN_SIDE, W - std.MARGIN_SIDE   # v3.12 : même grille que le corps et les en-têtes
TOP = H - 135          # première ligne de titre
BOTTOM = 45
SPAN = TOP - BOTTOM
NBSP = " "

MODELES = ("classique", "pilules", "numerote", "chiffres", "colonnes", "ligne",
           "geant", "cercle", "arc", "nomade", "dore")
POLICES_NOMS = P.POLICES_NOMS
POLICES = P.POLICES


def set_police(name):
    """Applique la police au corps (Standard + Excellence) ; les sommaires lisent P.F. Verrou requis."""
    if name not in P.POLICES:
        raise ValueError("police inconnue : %r" % name)
    P.apply(name, std.STYLES)
    return P.POLICES[name]


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
    if len(lines) > 1 and not re.search(r"\w", lines[-1]):   # ponctuation seule : on la rattache
        lines[-2] = lines[-2] + " " + lines.pop()
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
    return _wrap(g["chapter"].upper(), pol["sans_b"], 9.5, 190)


def _colonnes_span(g, pol):
    L = len(_colonnes_lines(g, pol))
    N = len(g["items"])
    return max((L - 1) * 12, (N - 1) * 14 if N else 0)


def _m_colonnes(g, pol):
    return 33 + _colonnes_span(g, pol)


# --- Modèle « ligne » : filet vertical or, numéro à gauche, titre à droite (sommaire éditorial)
X_LIGNE = 300          # position du filet vertical
X_TEXTE = 326          # début des titres (à droite du filet)


def _ligne_lines(g, pol):
    return _wrap(g["chapter"].upper(), pol["sans_b"], 10.5, RIGHT - X_TEXTE)


def _m_ligne(g, pol):
    L = len(_ligne_lines(g, pol))
    h = 4 + (L - 1) * 13 + 16
    if g["items"]:
        h += 3 + len(g["items"]) * 12
    return h + 16


def _d_ligne(c, g, y, P, pol):
    lines = _ligne_lines(g, pol)
    # numéro, aligné sur la première ligne du titre, à gauche du filet
    c.setFillColor(P["accent"])
    c.setFont(pol["serif_b"], 16)
    c.drawRightString(X_LIGNE - 14, y - 12, str(g["n"]))
    c.setFillColor(P["ink"])
    c.setFont(pol["sans_b"], 10.5)
    b = y - 12
    for line in lines:
        c.drawString(X_TEXTE, b, line)
        b -= 13
    if g["items"]:
        ib = b - 3
        for text, page in g["items"]:
            c.setFillColor(P["sub"])
            c.setFont(pol["sans"], 9)
            c.drawString(X_TEXTE, ib, text)
            c.setFillColor(P["ink"])
            c.setFont(pol["sans_b"], 9)
            c.drawRightString(RIGHT, ib, page)
            ib -= 12
    else:
        c.setFillColor(P["ink"])
        c.setFont(pol["sans_b"], 9)
        c.drawRightString(RIGHT, y - 12, g["page"])
    return y - _m_ligne(g, pol)


MEASURE = {
    "ligne": _m_ligne,
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
            if cur and used + h > _limite(modele, pages):
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
    font = pol["serif_b"] if modele in ("chiffres", "colonnes", "ligne", "arc", "dore") else pol["sans_b"]
    spaced = modele in ("pilules", "chiffres", "nomade", "cercle")
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
            c.drawString(262, ib, text)
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
    "ligne": _d_ligne,
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
        if modele == "arc" and pi == 0:
            _arc_titre(c, P, pol)
            y = TOP - ARC_OFFSET
        else:
            _titre(c, pi, modele, P, pol)
            y = TOP
        if modele == "ligne":
            c.setStrokeColor(P["accent"])
            c.setLineWidth(2.2)
            c.line(X_LIGNE, TOP + 8, X_LIGNE, BOTTOM)
        for g in pg:
            y = DRAW[modele](c, g, y, P, pol)
        c.showPage()
    c.save()
    return len(pages)


# ======================================================================================
# Modèles ajoutés (v3.16) : géant, cercle, arc, nomade, doré
# ======================================================================================
ARC_OFFSET = 110       # place prise par le titre en arc sur la première page


def _limite(modele, pages):
    """Hauteur utile de la page courante (la première page « arc » perd la place du titre courbe)."""
    return SPAN - (ARC_OFFSET if modele == "arc" and not pages else 0)


CERCLE_FILLS = ["#BDBDBD", "#9C9C9C", "#7D5A4A", "#3B2A22"]


# --- géant : grands numéros à gauche (01, 02…), titre en gras, sous-parties dessous
def _geant_lines(g, pol):
    return _wrap(g["chapter"].upper(), pol["sans_b"], 12, 300)


def _m_geant(g, pol):
    L = len(_geant_lines(g, pol))
    h = 14 * (L - 1) + 26 + (12 * len(g["items"]) + 4 if g["items"] else 0)
    return max(h, 44) + 18


def _d_geant(c, g, y, P, pol):
    lines = _geant_lines(g, pol)
    c.setFillColor(P["ink"])
    c.setFont(pol["sans_b"], 34)
    c.drawRightString(LEFT + 88, y - 34, "%02d" % g["n"])
    c.setFont(pol["sans_b"], 12)
    b = y - 22
    for line in lines:
        c.drawString(LEFT + 112, b, line)
        b -= 14
    if g["items"]:
        ib = y - 22 - 14 * (len(lines) - 1) - 16
        for text, page in g["items"]:
            c.setFillColor(P["sub"])
            c.setFont(pol["sans"], 9.5)
            c.drawString(LEFT + 112, ib, text)
            ib -= 12
    c.setFillColor(P["ink"])
    c.setFont(pol["sans_b"], 9)
    c.drawRightString(RIGHT, y - 22, g["page"])
    return y - _m_geant(g, pol)


# --- cercle : pastille numérotée colorée, titre accentué, sous-parties dessous
def _cercle_lines(g, pol):
    return _wrap(g["chapter"].upper(), pol["sans_b"], 13, 330)


def _m_cercle(g, pol):
    L = len(_cercle_lines(g, pol))
    h = 17 * (L - 1) + 22 + (6 + 13 * len(g["items"]) if g["items"] else 0)
    return max(h, 50) + 20


def _d_cercle(c, g, y, P, pol):
    lines = _cercle_lines(g, pol)
    cx, cy = LEFT + 24, y - 24
    c.setFillColor(colors.HexColor(CERCLE_FILLS[(g["n"] - 1) % len(CERCLE_FILLS)]))
    c.circle(cx, cy, 24, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(pol["sans_b"], 15)
    c.drawCentredString(cx, cy - 5.5, "%02d." % g["n"])
    c.setFillColor(P["accent"])
    c.setFont(pol["sans_b"], 13)
    b = y - 14
    for line in lines:
        c.drawString(LEFT + 62, b, line)
        b -= 17
    if g["items"]:
        ib = y - 14 - 17 * (len(lines) - 1) - 19
        for text, page in g["items"]:
            c.setFillColor(P["sub"])
            c.setFont(pol["sans"], 9.5)
            c.drawString(LEFT + 62, ib, text)
            ib -= 13
    c.setFillColor(P["ink"])
    c.setFont(pol["sans_b"], 9)
    c.drawRightString(RIGHT, y - 14, g["page"])
    return y - _m_cercle(g, pol)


# --- arc : numéros en serif dorée en quinconce, libellé « Titre — p. n » en serif
def _arc_tx(g):
    return LEFT + (62 if g["n"] % 2 == 1 else 178)


def _arc_lines(g, pol):
    return _wrap(g["chapter"] + " — p. " + g["page"], pol["serif"], 11, RIGHT - _arc_tx(g))


def _m_arc(g, pol):
    L = len(_arc_lines(g, pol))
    return 30 + 14 * (L - 1) + 22 + (13 * len(g["items"]) if g["items"] else 0)


def _d_arc(c, g, y, P, pol):
    xn = LEFT + (4 if g["n"] % 2 == 1 else 120)
    c.setFillColor(P["accent"])
    c.setFont(pol["serif_b"], 44)
    c.drawString(xn, y - 40, str(g["n"]))
    tx = _arc_tx(g)
    lines = _arc_lines(g, pol)
    c.setFillColor(P["ink"])
    c.setFont(pol["serif"], 11)
    b = y - 30
    for line in lines:
        c.drawString(tx, b, line)
        b -= 14
    if g["items"]:
        ib = y - 30 - 14 * (len(lines) - 1) - 18
        for text, page in g["items"]:
            c.setFillColor(P["sub"])
            c.setFont(pol["sans"], 9)
            c.drawString(tx, ib, text)
            ib -= 13
    return y - _m_arc(g, pol)


def _arc_titre(c, P, pol):
    """« SOMMAIRE » écrit le long d'un arc au sommet de la première page."""
    text = "SOMMAIRE"
    size = 26
    font = pol["sans_b"]
    cx, cy, R = W / 2, H - 300, 170
    total = stringWidth(text, font, size)
    span = total / R
    start = 3.14159265 / 2 + span / 2
    c.setFillColor(P["ink"])
    c.setFont(font, size)
    pos = 0.0
    for ch in text:
        w = stringWidth(ch, font, size)
        theta = start - (pos + w / 2) / R
        x, yy = cx + R * __import__("math").cos(theta), cy + R * __import__("math").sin(theta)
        c.saveState()
        c.translate(x, yy)
        c.rotate((theta - 3.14159265 / 2) * 180 / 3.14159265)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
        pos += w


# --- nomade : pastilles au contour fin, texte en capitales, sous-parties sous la pastille
def _nomade_lines(g, pol):
    return _wrap(g["chapter"].upper(), pol["sans"], 10.5, RIGHT - LEFT - 150)


def _m_nomade(g, pol):
    L = len(_nomade_lines(g, pol))
    ph = 24 + 12 * (L - 1)
    return ph + 14 + (11 * len(g["items"]) + 6 if g["items"] else 0)


def _d_nomade(c, g, y, P, pol):
    lines = _nomade_lines(g, pol)
    ph = 24 + 12 * (len(lines) - 1)
    yb = y - ph
    c.setStrokeColor(P["ink"])
    c.setLineWidth(0.8)
    c.roundRect(LEFT, yb, RIGHT - LEFT, ph, ph / 2, stroke=1, fill=0)
    c.setFillColor(P["ink"])
    c.setFont(pol["sans"], 10.5)
    base = yb + ph / 2 - 3.5 + (len(lines) - 1) * 6
    for line in lines:
        c.drawString(LEFT + 18, base, line)
        base -= 12
    pw, pg_h = 74, 18
    px, py = RIGHT - pw - 3, yb + ph / 2 - 9
    c.setFillColor(P["ink"])
    c.roundRect(px, py, pw, pg_h, pg_h / 2, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(pol["sans_b"], 7.5)
    c.drawCentredString(px + pw / 2, py + 5.3, "PAGE " + g["page"])
    if g["items"]:
        ib = yb - 12
        for text, page in g["items"]:
            c.setFillColor(P["sub"])
            c.setFont(pol["sans"], 8.5)
            c.drawString(LEFT + 18, ib, text)
            ib -= 11
    return y - _m_nomade(g, pol)


# --- doré : numéro doré serif, titre gras, sous-parties en ligne, filet entre les parties
def _dore_lines(g, pol):
    return _wrap(g["chapter"].upper(), pol["sans_b"], 12, RIGHT - LEFT - 110)


def _dore_sub(g, pol):
    if not g["items"]:
        return []
    return _wrap(" · ".join(t for t, _ in g["items"]), pol["sans"], 9, RIGHT - LEFT - 68)


def _m_dore(g, pol):
    L = len(_dore_lines(g, pol))
    S = len(_dore_sub(g, pol))
    return 40 + 15 * (L - 1) + (13 * S + 6 if S else 0)


def _d_dore(c, g, y, P, pol):
    lines = _dore_lines(g, pol)
    sub = _dore_sub(g, pol)
    c.setFillColor(P["accent"])
    c.setFont(pol["serif_b"], 26)
    c.drawString(LEFT, y - 26, "%02d" % g["n"])
    c.setFillColor(P["ink"])
    c.setFont(pol["sans_b"], 12)
    b = y - 18
    for line in lines:
        c.drawString(LEFT + 68, b, line)
        b -= 15
    c.setFillColor(P["accent"])
    c.setFont(pol["sans_b"], 9.5)
    c.drawRightString(RIGHT, y - 18, g["page"])
    if sub:
        sb = y - 18 - 15 * (len(lines) - 1) - 15
        c.setFillColor(P["sub"])
        c.setFont(pol["sans"], 9)
        for line in sub:
            c.drawString(LEFT + 68, sb, line)
            sb -= 13
    h = _m_dore(g, pol)
    c.setStrokeColor(P["rule"])
    c.setLineWidth(0.6)
    c.line(LEFT, y - h + 10, RIGHT, y - h + 10)
    return y - h


MEASURE.update({
    "geant": _m_geant,
    "cercle": _m_cercle,
    "arc": _m_arc,
    "nomade": _m_nomade,
    "dore": _m_dore,
})
DRAW.update({
    "geant": _d_geant,
    "cercle": _d_cercle,
    "arc": _d_arc,
    "nomade": _d_nomade,
    "dore": _d_dore,
})
