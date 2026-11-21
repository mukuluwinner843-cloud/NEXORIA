# -*- coding: utf-8 -*-
"""
NEXORIA v3.13 — mise en forme automatique (typographie française)
=================================================================
Règles PURELY TYPOGRAPHIQUES appliquées au texte source avant la génération (les deux packs).
Aucune règle ne corrige l'orthographe, ne change un mot ni ne réécrit une phrase : le fond de
l'élève est intouché. Chaque règle renvoie le nombre de corrections faites (journal).

Ordre : espaces -> apostrophes -> ponctuation -> guillemets -> tirets -> répétitions -> initiales.
"""
import re

LETTRE = "A-Za-zÀ-ÖØ-öø-ÿŒœÆæ"
ELISION = r"l|d|qu|n|s|j|c|m|t|lorsqu|puisqu|jusqu|quoiqu|presqu"
ARTICLES = r"le|la|les|de|des|du|un|une|et|à|au|aux|en|que|qui|ce|se|ne"
NBSP = " "


def _sub(regle, motif, repl, t, journal, flags=0):
    t, n = re.subn(motif, repl, t, flags=flags)
    if n:
        journal.append((regle, n))
    return t


# Blocs produits par NEXORIA lui-même (certificat), collés par erreur dans le texte de l'élève
MARQUEURS_CERTIFICAT = ("nexoria-verif", "Scannez le QR code", "Le statut de validation est consulté",
                        "Le fichier numérique peut aussi être vérifié", "CERTIFICAT DE VÉRIFICATION",
                        "C E R T I F I C A T")


def _majuscule_initiale(ligne):
    """Met en majuscule la première lettre du paragraphe, après d'éventuels guillemets/parenthèses.
    Ne touche pas aux URL, adresses ou codes (https://…, www…, nom@domaine)."""
    if re.match(r"\s*[\(«\"']*\S*(://|www\.|@)", ligne):
        return ligne, False
    i = 0
    while i < len(ligne) and ligne[i] in "  «\"'(‘“[-–":
        i += 1
    if i < len(ligne) and ligne[i].islower():
        return ligne[:i] + ligne[i].upper() + ligne[i + 1:], True
    return ligne, False


def normaliser(texte):
    """Retourne (texte_normalise, journal) ; journal = [(regle, nombre), ...]."""
    journal = []
    t = (texte or "").replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")

    # 0. Bloc de certificat copié depuis un PDF généré : ce n'est pas le travail de l'élève
    lignes_ok, retires = [], 0
    for ligne in t.split("\n"):
        if any(m in ligne for m in MARQUEURS_CERTIFICAT):
            retires += 1
            continue
        lignes_ok.append(ligne)
    t = "\n".join(lignes_ok)
    if retires:
        journal.append(("bloc de certificat copié retiré", retires))

    # 1. Espaces : doubles, en bord de ligne, espaces insécables parasites
    t = _sub("espaces multiples", r"[ ]{2,}", " ", t, journal)
    t = _sub("espaces en bord de ligne", r"(?m)^[ ]+|[ ]+$", "", t, journal)
    t = _sub("espace après apostrophe", r"\b(%s)(['’]) +(?=[%s])" % (ELISION, LETTRE),
             r"\1'", t, journal, flags=re.I)
    t = _sub("espace parasite avant ponctuation forte", r"[  ]+(?=[.,])", "", t, journal)

    # 2. Ponctuation française : espace insécable avant ; ! ? et « ... » ; espace manquante après , ; :
    t = _sub("espace avant ; ! ?", r"[  ]*([;!?])", NBSP + r"\1", t, journal)
    t = _sub("espace avant :", r"(?<=[%s\)])[  ]*(:)(?=\s|$)" % LETTRE, NBSP + r"\1", t, journal)
    t = _sub("espace manquante après , ; :", r"(?<=[%s]{2})([,;:])(?=[%s])" % (LETTRE, LETTRE), r"\1 ", t, journal)
    t = _sub("espace manquante après point", r"(?<=[a-zà-ÿ]{2})\.(?=[A-ZÀ-Ý])", ". ", t, journal)
    t = _sub("espace dans parenthèses", r"\( +", "(", t, journal)
    t = _sub("espace avant parenthèse fermante", r" +\)", ")", t, journal)

    # 3. Guillemets : "..." -> « ... » (espaces insécables à l'intérieur)
    def guillemets(m):
        return "«" + NBSP + m.group(1).strip() + NBSP + "»"
    t, n = re.subn(r'"([^"\n]+)"', guillemets, t)
    if n:
        journal.append(("guillemets droits -> « »", n))
    t = _sub("espace après «", r"«[  ]*", "«" + NBSP, t, journal)
    t = _sub("espace avant »", r"[  ]*»", NBSP + "»", t, journal)

    # 4. Tirets et points de suspension
    t = _sub("tiret d'incise", r"(?<=\S) - (?=\S)", " – ", t, journal)
    t = _sub("points de suspension", r"\.\.\.", "…", t, journal)

    # 5. Répétitions de mots grammaticaux (« le le » -> « le »), hors « nous nous » etc.
    for _ in range(2):
        t = _sub("mot répété", r"\b(%s) \1\b" % ARTICLES, r"\1", t, journal, flags=re.I)

    # 6. Majuscule initiale de chaque paragraphe (lignes non vides, hors tableaux)
    lignes, n = [], 0
    for ligne in t.split("\n"):
        if ligne.strip() and not ligne.lstrip().startswith("|"):
            ligne, ok = _majuscule_initiale(ligne)
            n += ok
        lignes.append(ligne)
    t = "\n".join(lignes)
    if n:
        journal.append(("majuscule initiale ajoutée", n))

    return t, journal


def resume(journal):
    if not journal:
        return "Aucune correction typographique nécessaire."
    return "; ".join("%s : %d" % (r, n) for r, n in journal)
