# -*- coding: utf-8 -*-
"""
NEXORIA v3.12 — registre des polices
====================================
Une seule source de vérité pour le corps du texte, les titres, les en-têtes, les pieds de page
et les sommaires (Standard et Excellence). La couverture garde ses polices de kit.

Options (paramètre « police ») :
  defaut     : Helvetica pour le corps, DejaVu Serif pour les titres (comportement v3.11)
  helvetica  : Helvetica partout (intégrée au PDF)
  times      : Times partout (intégrée au PDF)
  inter      : Inter partout (TTF fournie dans fonts/)
  montserrat : Montserrat partout (TTF fournie dans fonts/)
  futura     : Jost partout (TTF fournie dans fonts/) — Jost est une version libre dessinée
               dans l'esprit de Futura ; Futura elle-même n'est pas libre et n'est pas embarquée.
  garamond   : EB Garamond partout (TTF fournie dans fonts/)

Chaque option définit 6 rôles : sans, sans_b, sans_i (corps), serif, serif_b, serif_i (titres,
citations, formules). Pour les options à famille unique, serif == sans : le choix se voit partout.

État global : F est modifié par apply(). Appeler sous verrou (core.py le fait déjà).
"""
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

POLICES_NOMS = ("defaut", "helvetica", "times", "inter", "montserrat", "futura", "garamond")

# Familles TTF : nom interne -> fichiers (regular, bold, italic, bolditalic)
_TTF_FAMILLES = {
    "Inter": ("Inter-Regular.ttf", "Inter-Bold.ttf", "Inter-Italic.ttf", "Inter-BoldItalic.ttf"),
    "Montserrat": ("Montserrat-Regular.ttf", "Montserrat-Bold.ttf", "Montserrat-Italic.ttf",
                   "Montserrat-BoldItalic.ttf"),
    "Jost": ("Jost-Regular.ttf", "Jost-Bold.ttf", "Jost-Italic.ttf", "Jost-BoldItalic.ttf"),
    "Garamond": ("Garamond-Regular.ttf", "Garamond-Bold.ttf", "Garamond-Italic.ttf",
                 "Garamond-BoldItalic.ttf"),
}

_DISPONIBLE = {}  # nom d'option -> bool (police réellement chargeable sur ce serveur)


def _enregistrer_ttf():
    for fam, fichiers in _TTF_FAMILLES.items():
        noms = ["NX-%s" % fam, "NX-%s-Bold" % fam, "NX-%s-Italic" % fam, "NX-%s-BoldItalic" % fam]
        try:
            for nom, fichier in zip(noms, fichiers):
                pdfmetrics.registerFont(TTFont(nom, os.path.join(FONTS_DIR, fichier)))
            pdfmetrics.registerFontFamily(noms[0], normal=noms[0], bold=noms[1],
                                          italic=noms[2], boldItalic=noms[3])
            _DISPONIBLE[fam] = True
        except Exception:  # fichier absent : l'option concernée est refusée proprement
            _DISPONIBLE[fam] = False


_enregistrer_ttf()


def _famille_ttf(fam):
    p = "NX-%s" % fam
    return dict(sans=p, sans_b=p + "-Bold", sans_i=p + "-Italic",
                serif=p, serif_b=p + "-Bold", serif_i=p + "-Italic")


POLICES = {
    "defaut": dict(sans="Helvetica", sans_b="Helvetica-Bold", sans_i="Helvetica-Oblique",
                   serif="Serif", serif_b="Serif-Bold", serif_i="Serif-Italic"),
    "helvetica": dict(sans="Helvetica", sans_b="Helvetica-Bold", sans_i="Helvetica-Oblique",
                      serif="Helvetica", serif_b="Helvetica-Bold", serif_i="Helvetica-Oblique"),
    "times": dict(sans="Times-Roman", sans_b="Times-Bold", sans_i="Times-Italic",
                  serif="Times-Roman", serif_b="Times-Bold", serif_i="Times-Italic"),
    "inter": _famille_ttf("Inter"),
    "montserrat": _famille_ttf("Montserrat"),
    "futura": _famille_ttf("Jost"),
    "garamond": _famille_ttf("Garamond"),
}
_FAMILLE_DE = {"inter": "Inter", "montserrat": "Montserrat", "futura": "Jost", "garamond": "Garamond"}

# Polices de base du moteur Standard (STYLES) -> rôle
_ROLE_DE_BASE = {"Helvetica": "sans", "Helvetica-Bold": "sans_b", "Serif": "serif",
                 "Serif-Bold": "serif_b", "Serif-Italic": "serif_i"}

# Police active (rôle -> nom ReportLab). Initialisée sur « defaut ».
F = dict(POLICES["defaut"])
ACTIVE = "defaut"


def disponible(name):
    if name not in POLICES:
        return False
    if name in _FAMILLE_DE:
        return _DISPONIBLE.get(_FAMILLE_DE[name], False)
    return True


def face(role):
    """Nom de police pour une balise <font face=...> au moment du rendu."""
    return F[role]


def apply(name, styles):
    """Applique l'option au dictionnaire de styles ParagraphStyle (fontName) et à F.
    Chaque style part de sa police d'origine : pas de dérive entre deux générations."""
    global ACTIVE
    if name not in POLICES:
        raise ValueError("police inconnue : %r" % name)
    if not disponible(name):
        raise ValueError("police %s indisponible sur ce serveur" % name)
    pol = POLICES[name]
    for k, st in styles.items():
        base = _BASE_DE_STYLE.get(k, st.fontName)
        role = _ROLE_DE_BASE.get(base)
        if role:
            st.fontName = pol[role]
    F.clear()
    F.update(pol)
    ACTIVE = name
    return pol


# Fontname d'origine de chaque style du moteur Standard (mémorisé à l'import, avant tout apply)
_BASE_DE_STYLE = {}


def memoriser_styles(styles):
    for k, st in styles.items():
        _BASE_DE_STYLE[k] = st.fontName
