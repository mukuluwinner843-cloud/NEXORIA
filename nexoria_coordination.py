# -*- coding: utf-8 -*-
"""
NEXORIA — coordination d'un devoir (v3.10)
==========================================
Enchaîne les contrôles avant génération et décide, sans intervention humaine
pour les cas clairs :

  bloque   : une erreur empêche la génération (ex. thème absent du texte) ;
  a_verifier : des avertissements demandent un regard humain ;
  pret     : aucun blocage, la génération peut se faire.

Principes :
  - déterministe : mêmes entrées, mêmes décisions, testable ;
  - aucun mot n'est modifié : seule la mise en forme des titres est reconstruite ;
  - une décision « bloque » peut être forcée par un humain (force=True), jamais par le code.
"""
import re
import unicodedata

import nexoria_structure as structure

STOP = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "en", "au", "aux", "a", "est", "sont",
    "dans", "sur", "par", "pour", "avec", "sans", "que", "qui", "quoi", "quel", "quelle", "quels", "quelles",
    "ce", "cette", "ces", "son", "sa", "ses", "leur", "leurs", "il", "elle", "on", "nous", "vous", "ils",
    "elles", "plus", "moins", "tres", "comment", "pourquoi", "quand", "donc", "mais", "ainsi", "aussi",
    "the", "and", "of", "to", "in", "is", "are", "for", "with",
}
MIN_WORDS = 120
MAX_WORDS = 6000


def _norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().replace("’", "'")


def _present(mot, tokens):
    """Mot entier, ou forme fléchie d'un mot assez long (ex. « intelligence » / « intelligences »).
    Pas de recherche par sous-chaîne : « mort » ne doit pas trouver « mortalité »."""
    if mot in tokens:
        return True
    if len(mot) >= 6:
        return any(t.startswith(mot) and len(t) - len(mot) <= 2 for t in tokens)
    return False


def _keywords(theme):
    words = re.findall(r"[a-z0-9]+", _norm(theme))
    return [w for w in words if len(w) >= 4 and w not in STOP]


def verifier(meta, texte):
    """Contrôles de cohérence. Renvoie un dict : statut, erreurs, avertissements, titres, texte reconstruit."""
    erreurs, avis = [], []

    for champ, libelle in [("eleve", "élève"), ("matiere", "matière"), ("titulaire", "encadreur"),
                           ("theme", "thème"), ("annee", "année scolaire"), ("date", "date de remise")]:
        if not str(meta.get(champ, "")).strip():
            erreurs.append("Champ obligatoire vide : %s." % libelle)

    if not (texte or "").strip():
        erreurs.append("Le texte du devoir est vide.")
        return _resultat("bloque", erreurs, avis, [], "", False)

    rec = structure.reconstruire(texte)
    titres = rec["titres"]
    texte_rec = rec["texte"]

    if not titres:
        erreurs.append("Aucun titre trouvé, même après analyse (INTRODUCTION, I., II., CONCLUSION).")

    # Cohérence thème / contenu : le sujet de la couverture doit se retrouver dans le texte.
    mots_theme = _keywords(meta.get("theme", ""))
    tokens = set(re.findall(r"[a-z0-9]+", _norm(texte)))
    if mots_theme:
        trouves = [w for w in mots_theme if _present(w, tokens)]
        if not trouves:
            erreurs.append("Le thème « %s » n'apparaît dans aucun mot du texte : vérifie que le bon devoir est collé "
                           "(couverture et contenu semblent différents)." % meta.get("theme", ""))
        elif len(trouves) == 1 and len(mots_theme) >= 3:
            avis.append("Le thème n'est que peu retrouvé dans le texte (« %s ») : vérifie la cohérence."
                        % trouves[0])

    nb_mots = len(texte.split())
    if nb_mots < MIN_WORDS:
        avis.append("Texte court (%d mots) : vérifie qu'il s'agit du devoir complet." % nb_mots)
    if nb_mots > MAX_WORDS:
        avis.append("Texte long (%d mots) : vérifie qu'il ne contient pas plusieurs devoirs." % nb_mots)

    if not any(t == "INTRODUCTION" for t in titres):
        avis.append("Pas d'INTRODUCTION reconnue.")
    if not any(t == "CONCLUSION" for t in titres):
        avis.append("Pas de CONCLUSION reconnue.")
    if rec["deduits"]:
        avis.append("%d titre(s) déduit(s) sans mise en forme d'origine : à vérifier (%s)."
                    % (len(rec["deduits"]), " / ".join(rec["deduits"])))
    nb_tab = len(re.findall(r"(?m)^Tableau\s+\d+\s*[—–-]", texte))
    if nb_tab:
        avis.append("%d tableau(x) : vérifie qu'ils ne sont pas aplatis en lignes de texte." % nb_tab)
    doublons = {t for t in titres if titres.count(t) > 1}
    if doublons:
        avis.append("Titre en double : %s." % " / ".join(sorted(doublons)))

    statut = "bloque" if erreurs else ("a_verifier" if avis else "pret")
    return _resultat(statut, erreurs, avis, titres, texte_rec, True)


def _resultat(statut, erreurs, avis, titres, texte_rec, structure_ok):
    return {"statut": statut, "erreurs": erreurs, "avertissements": avis,
            "titres": titres, "texte_reconstruit": texte_rec, "structure_ok": structure_ok}


def decider(res, force=False):
    """Peut-on générer ? « bloque » ne passe que si un humain le force."""
    if res["statut"] == "bloque":
        return force and res["structure_ok"] and bool(res["texte_reconstruit"])
    return True
