# -*- coding: utf-8 -*-
"""
NEXORIA — reconstruction de la structure d'un devoir collé ou importé (v3.9)
===========================================================================
Beaucoup d'élèves ne mettent pas les titres en forme : ils collent un texte où
« INTRODUCTION », « I. … » ou une partie en capitales sont perdus au milieu d'un
paragraphe, ou séparés par un simple retour à la ligne.

Ce module reconstruit la structure à partir du contenu seul, sans rien réécrire :
  - chaque titre devient une ligne isolée, précédée et suivie d'une ligne vide ;
  - les lignes d'un même paragraphe sont recollées ;
  - les titres sans numéro reçoivent le prochain chiffre romain ;
  - les lignes de tableau (« a | b » ou « Tableau n — ») restent séparées.

Règle de prudence : un titre n'est déduit que s'il est court, sans ponctuation
finale, et suivi d'un vrai paragraphe. Chaque titre déduit (et non explicite)
est listé dans `titres_deduits` pour être vérifié.

Sortie de `reconstruire()` :
  texte       : texte reformaté, prêt pour paragraphs_from_markdown / le moteur ;
  titres      : titres retenus, dans l'ordre ;
  deduits     : titres déduits du contexte (à vérifier) ;
  avis        : avertissements lisibles.
"""
import re
import unicodedata

ROMAN_VALUES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"]
INTRO_KEYS = {"INTRODUCTION", "INTRODUCTION GENERALE"}
CONCL_KEYS = {"CONCLUSION", "CONCLUSION GENERALE"}
BIBLIO_WORDS = ("BIBLIOGRAPHIE", "REFERENCES", "ANNEXE")
END_PUNCT = (".", "!", "?", ";", ",", "»", "…")
ROMAN_RE = re.compile(r"^([IVXLC]{1,5})[.)]\s+(.+)$")
DECIMAL_RE = re.compile(r"^(\d{1,2})[.)]\s+(.+)$")
TABLE_CAP_RE = re.compile(r"^Tableau\s+\d+\s*[—–-]", re.I)
BULLET_RE = re.compile(r"^(?:[-•*]|\d+[.)])\s+")
# Libellés d'interface ou de mise en page : jamais des titres de section.
UI_LABELS = {"VERIFIER LE DOCUMENT", "VERIFICATION DU DOCUMENT", "SOMMAIRE", "TABLE DES MATIERES",
             "PAGE", "NEXORIA", "GEOGRAPHIE", "DEVOIR", "ELEVE", "MATIERE", "ENCADREUR", "CLASSE",
             "DATE DE REMISE", "ANNEE SCOLAIRE", "COMPLEXE SCOLAIRE", "FRANCISCO PALAU"}
SMALL_WORDS = {"de", "du", "des", "la", "le", "les", "et", "en", "d'", "l'", "a", "au", "aux", "un", "une", "sur", "dans", "par", "pour", "ou", "au"}


def _plain(s):
    """Majuscules sans accents, pour comparer."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.upper().replace("’", "'").strip()


def _letters(s):
    return [c for c in s if c.isalpha()]


def _is_all_caps(s):
    letters = _letters(s)
    return len(letters) >= 4 and all(c == c.upper() for c in letters)


def _clean_line(l):
    l = unicodedata.normalize("NFC", l).replace(" ", " ").replace(" ", " ")
    return re.sub(r"[ \t]{2,}", " ", l).strip()


def _explicit_heading(l):
    """Renvoie le titre normalisé si la ligne est clairement un titre, sinon None.
    Pas de titre si la ligne ressemble à une phrase ou à une ligne de tableau."""
    t = l.rstrip(":").strip()
    p = _plain(t)
    if p in INTRO_KEYS:
        return "INTRODUCTION"
    if p in CONCL_KEYS:
        return "CONCLUSION"
    if len(t) <= 90 and any(w in p for w in BIBLIO_WORDS) and _is_all_caps(t):
        return t.upper()
    m = ROMAN_RE.match(t)
    if m and _is_all_caps(m.group(2)) and len(t) <= 110:
        return "%s. %s" % (m.group(1).upper(), m.group(2).upper())
    return None


def _inferred_heading(line, prev_blank, next_line):
    """Titre déduit : seulement en capitales ou en titre court, suivi d'un paragraphe."""
    if prev_blank is False or not next_line:
        return False
    t = line.rstrip(":").strip()
    if _plain(t) in UI_LABELS or re.search(r"\bPAGE\s+\d+", t, re.I):
        return False
    if len(t) < 4 or len(t) > 90 or t.endswith(END_PUNCT) or TABLE_CAP_RE.match(t) or "|" in t:
        return False
    if BULLET_RE.match(t):
        return False
    words = t.split()
    if len(words) > 14:
        return False
    if _is_all_caps(t):
        return True
    if len(next_line) < 90 and not next_line.endswith(END_PUNCT):
        return False  # le « paragraphe » suivant est lui-même une ligne courte : ce n'est pas un corps
    content = [w for w in words if _plain(w).lower() not in SMALL_WORDS and len(w) > 2]
    if len(words) >= 2 and content and all(w[0].isupper() for w in content):
        return True
    return False


def _split_lines(texte):
    raw = unicodedata.normalize("NFC", texte or "").replace("\r\n", "\n").replace("\r", "\n")
    return [_clean_line(l) for l in raw.split("\n")]


def reconstruire(texte):
    lines = _split_lines(texte)
    n = len(lines)
    blocks = []          # liste de (kind, text, deduit)
    buf = []             # lignes du paragraphe en cours
    deduits = []

    def flush():
        if buf:
            blocks.append(("p", " ".join(buf), False))
            buf.clear()

    prev_blank = True
    for i, l in enumerate(lines):
        if not l:
            flush()
            prev_blank = True
            continue
        nxt = next((x for x in lines[i + 1:] if x), "")
        exp = _explicit_heading(l)
        if exp:
            flush()
            blocks.append(("h", exp, False))
        elif _inferred_heading(l, prev_blank, nxt):
            flush()
            blocks.append(("h", l.rstrip(":").strip(), True))
            deduits.append(l.rstrip(":").strip())
        elif "|" in l or TABLE_CAP_RE.match(l) or BULLET_RE.match(l):
            flush()
            blocks.append(("line", l, False))
        else:
            buf.append(l)
        prev_blank = False
    flush()

    # Numérotation : les titres de section sans chiffre romain reçoivent le suivant.
    out_titles, used = [], 0
    fixed = []
    fixed_prev_text = ""
    for kind, text, ded in blocks:
        if kind == "h" and text not in ("INTRODUCTION", "CONCLUSION") and not any(text.startswith(w) for w in BIBLIO_WORDS) and not _plain(text).startswith(tuple(BIBLIO_WORDS)):
            m = ROMAN_RE.match(text)
            if not m:
                if used < len(ROMAN_VALUES):
                    text = "%s. %s" % (ROMAN_VALUES[used], text)
                used += 1
            else:
                used += 1
        if kind == "h":
            out_titles.append(text)
        fixed.append((kind, text, ded))

    # Assemblage : une ligne vide entre tous les blocs (format attendu par le moteur).
    # Les lignes d'un tableau restent consécutives (un simple saut de ligne) ; le reste est séparé
    # par une ligne vide.
    texte_out = ""
    prev_kind = None
    for kind, text, ded in fixed:
        if not texte_out:
            texte_out = text
        elif kind == "line" and prev_kind == "line" and ("|" in text) and ("|" in fixed_prev_text):
            texte_out += "\n" + text
        else:
            texte_out += "\n\n" + text
        prev_kind, fixed_prev_text = kind, text

    avis = []
    if not out_titles:
        avis.append("Aucun titre reconnu, même après analyse : écris chaque titre seul sur sa ligne "
                    "(ex. « INTRODUCTION », « I. TITRE ») ou laisse une ligne vide avant et après.")
    if deduits:
        avis.append("%d titre(s) déduit(s) du contexte, sans mise en forme d'origine : à vérifier : %s"
                    % (len(deduits), " / ".join(deduits)))
    if not any(t == "INTRODUCTION" for t in out_titles):
        avis.append("Aucune INTRODUCTION reconnue.")
    if not any(t == "CONCLUSION" for t in out_titles):
        avis.append("Aucune CONCLUSION reconnue.")
    return {"texte": texte_out, "titres": out_titles, "deduits": deduits, "avis": avis}
