# -*- coding: utf-8 -*-
"""
NEXORIA — logique de génération (indépendante du framework web)
==================================================================
build_pdf() refait la chaîne validée manuellement pendant les tests :
texte brut -> structure (titres, tableaux, schémas) -> corps -> sommaire
(si utile) -> couverture (avec blason si l'établissement est reconnu) ->
fusion, pour les packs Standard et Excellence.
"""
import os
import re
import tempfile
import threading

import verification
import nexoria_engine_standard as std
import nexoria_structure
import nexoria_memoire as mem
import nexoria_mise_en_forme as mef
import nexoria_engine_excellence as exc
import nexoria_sommaires as som
from nexoria_tables import paragraphs_from_markdown, extract_special_blocks

ASSETS = os.path.dirname(__file__)

# "classe" n'est pas toujours connue (ex. document reçu sans niveau précisé) :
# jamais inventée, simplement absente de la couverture si absente ici.
REQUIRED_META = ["etablissement", "eleve", "matiere", "titulaire", "theme", "annee", "date"]

# Établissements dont NEXORIA a le blason officiel : correspondance par mot-clé
# dans le nom donné (insensible à la casse). À étendre au fur et à mesure des
# partenariats — aucun blason n'est affiché pour un établissement non reconnu.
KNOWN_CRESTS = {
    "francisco palau": "crest_grey.png",
    "gianelli": "crest_gianelli.png",
    "les oscars": "crest_oscars_grey.png",
    "mont amba": "crest_monta_grey.png",
}
KNOWN_CRESTS_EXCELLENCE = {
    "francisco palau": "crest_transparent.png",
    "gianelli": "crest_gianelli.png",
    "les oscars": "crest_oscars.png",
    "mont amba": "crest_monta.png",
}


# Le moteur garde des réglages globaux (polices, compteurs de pages) : une seule génération à la fois.
_RENDER_LOCK = threading.Lock()
_TLS = threading.local()


def last_code():
    """Code de vérification du dernier document généré dans ce thread."""
    return getattr(_TLS, "code", None)


class GenerationError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def split_school_line(etablissement: str):
    m = re.match(r"^(Complexe Scolaire|Institut(?:\s+Sup[ée]rieur)?|Lyc[ée]e|Coll[eè]ge)\s+(.+)$",
                etablissement, re.I)
    if m:
        return m.group(1).upper(), m.group(2).upper()
    return "", etablissement.upper()


def find_crest(etablissement: str, mapping: dict):
    low = etablissement.lower()
    for key, fname in mapping.items():
        if key in low:
            return os.path.join(ASSETS, fname)
    return None


def validate_meta(meta: dict):
    requis = [k for k in REQUIRED_META if not (k == "eleve" and meta.get("membres"))]   # v3.16 : TP de groupe
    missing = [k for k in requis if not str(meta.get(k, "")).strip()]
    if missing:
        raise GenerationError("Champs manquants dans meta : " + ", ".join(missing))


ENTETE_GROUPE_DEFAUT = ["République Démocratique du Congo", "Ministère de l\u2019Éducation nationale et nouvelle citoyenneté"]


def _membres_groupe(valeur):
    """v3.16 : accepte une liste ou un texte (un nom par ligne ou par virgule). « A et B » = deux noms."""
    if not valeur:
        return []
    if isinstance(valeur, str):
        morceaux = re.split(r"[\n,;]+", valeur)
    else:
        morceaux = list(valeur)
    noms = []
    for m in morceaux:
        for n in re.split(r"\s+et\s+", str(m).strip(), flags=re.I):
            n = n.strip()
            if n:
                noms.append(n)
    return noms


def build_pdf(pack: str, meta: dict, corps_texte: str,
              sommaire: str = "classique", police: str = "defaut") -> bytes:
    if pack not in ("standard", "excellence"):
        raise GenerationError("pack doit être 'standard' ou 'excellence' (reçu : %r)" % pack)
    if sommaire not in som.MODELES:
        raise GenerationError("sommaire doit être l'un de : %s (reçu : %r)" % (", ".join(som.MODELES), sommaire))
    if police not in som.POLICES_NOMS:
        raise GenerationError("police doit être l'une de : %s (reçu : %r)" % (", ".join(som.POLICES_NOMS), police))
    if meta.get("type") == "memoire":
        meta = _preparer_memoire(meta)
    validate_meta(meta)
    with _RENDER_LOCK:
        return _build(pack, meta, corps_texte, sommaire, police)


def _preparer_memoire(meta):
    """Mode MÉMOIRE : renseigne les champs communs du moteur à partir des champs du mémoire.
    Les champs propres au mémoire (titre, auteur, grade, directeur...) restent dans meta pour la page de garde."""
    m = dict(meta)
    m["etablissement"] = m.get("etablissement") or "Université de Kinshasa"
    m["eleve"] = m.get("auteur") or m.get("eleve") or "Auteur"
    m["matiere"] = m.get("option") or "Mémoire"
    m["titulaire"] = m.get("directeur") or "Directeur"
    m["theme"] = m.get("titre") or m.get("theme") or "Mémoire"
    m["annee"] = m.get("annee") or "2025-2026"
    m["date"] = m.get("date") or m["annee"]
    m["doc_word"] = "MÉMOIRE"
    return m


def _build(pack, meta, corps_texte, sommaire, police):
    try:
        som.set_police(police)
    except ValueError as e:
        raise GenerationError(str(e))

    # v3.13 : mise en forme typographique (sans toucher au fond)
    corps_texte, _journal_mef = mef.normaliser(corps_texte)

    # v3.9 : reconstruction de la structure à partir du contenu (titres collés, sans retour de paragraphe)
    rec = nexoria_structure.reconstruire(corps_texte)
    if not rec["titres"]:
        raise GenerationError(
            "Structure non reconnue : aucun titre trouvé, même après analyse. Écris chaque titre seul sur "
            "sa ligne (ex. « INTRODUCTION », « I. TITRE ») ou laisse une ligne vide avant et après.", 422)
    paras = paragraphs_from_markdown(rec["texte"])
    if not paras:
        raise GenerationError("corps_texte est vide")
    pre = extract_special_blocks(paras)
    blocks = std.classify(pre)
    if not any(b["kind"] == "h1" for b in blocks):
        raise GenerationError(
            "Structure non reconnue après analyse. Vérifie les titres (chaque titre seul sur sa ligne).", 422)

    doc_word = meta.get("doc_word") or "DEVOIR"
    line1, line2 = split_school_line(meta["etablissement"])
    # v3.15.1 : l'année s'écrit comme saisie, avec un trait d'union (2026-2027)
    year = re.sub(r"\s*[\u2013\u2014-]\s*", "-", meta["annee"])
    membres = _membres_groupe(meta.get("membres"))
    if membres:
        # v3.16 : TP de groupe — noms seuls, cours et titulaire, sans champ « élève » ni classe
        doc_word = meta.get("doc_word") or "TP"
        fields = [("COURS", meta["matiere"].upper()),
                  ("TITULAIRE", meta["titulaire"].upper()),
                  ("DATE DE REMISE", meta["date"])]
    else:
        fields = [("\u00c9L\u00c8VE", meta["eleve"].upper())]
        if str(meta.get("classe", "")).strip():
            fields.append(("CLASSE", meta["classe"].upper()))
        fields += [
            ("MATI\u00c8RE", meta["matiere"].upper()),
            ("ENCADREUR", meta["titulaire"].upper()),
            ("DATE DE REMISE", meta["date"]),
        ]

    # v3.13 : code de vérification calculé une fois, avant la couverture (QR) et réutilisé dans le certificat
    code = verification.new_code(pack, meta, corps_texte)
    qr_url = verification.VERIF_BASE.rstrip("/") + "/?code=" + code

    with tempfile.TemporaryDirectory() as d:
        body_pdf = os.path.join(d, "body.pdf")
        som_pdf = os.path.join(d, "som.pdf")
        cover_pdf = os.path.join(d, "cover.pdf")
        final_pdf = os.path.join(d, "final.pdf")
        want_sommaire = std.needs_sommaire(blocks)
        n_som = som.page_count(blocks, sommaire, pack, police) if want_sommaire else 0
        memoire = meta.get("type") == "memoire"
        lim_pdf = os.path.join(d, "lim.pdf")
        n_lim = 0
        if memoire:
            n_lim = mem.render_liminaires(lim_pdf, meta.get("inmemoriam"), meta.get("dedicace"),
                                          meta.get("remerciements"), meta.get("abreviations"),
                                          signature_remerciements=meta.get("signature_remerciements"))
        std.CFG["cover_pages"] = 1 + n_lim + n_som
        parts = [cover_pdf]

        if pack == "standard":
            theme_lines = std.balance(meta["theme"], "Serif-Italic", 13, 330)
            toc, _gap, _tries = std.build_balanced(std.build_body, blocks, body_pdf, meta["matiere"].upper())
            if want_sommaire:
                som.render(toc, som_pdf, sommaire, pack, police, std.CFG["cover_pages"])
                parts.append(som_pdf)
            if memoire:
                mem.render_cover_memoire(cover_pdf, meta.get("entete"), meta.get("titre") or meta["theme"],
                                         meta.get("auteur", ""), meta.get("grade", ""), meta.get("diplome", ""),
                                         meta.get("option", ""), meta.get("directeur", ""), year,
                                         qr_url=qr_url, code_qr=code)
            elif membres:
                # v3.17 : couverture TP de groupe, ordre exigé par l'école
                entete = meta.get("entete") or ENTETE_GROUPE_DEFAUT
                cours = meta["matiere"].strip()
                cours = cours[:1].upper() + cours[1:]
                std.render_cover_groupe_standard(
                    cover_pdf, entete, line1, line2, theme_lines, membres, meta["titulaire"].strip(), cours,
                    year, crest_path=find_crest(meta["etablissement"], KNOWN_CRESTS), date_remise=meta.get("date", "").strip() or None,
                    logo_path=os.path.join(ASSETS, "nexoria_logo_grey.png"),
                    qr_url=qr_url, code_qr=code,
                )
            else:
                std.render_cover_school_standard(
                    cover_pdf, line1, line2, year, fields, theme_lines,
                    crest_path=find_crest(meta["etablissement"], KNOWN_CRESTS),
                    logo_path=os.path.join(ASSETS, "nexoria_logo_grey.png"),
                    doc_word=doc_word, qr_url=qr_url, code_qr=code,
                )
        else:
            theme_lines = exc.balance(meta["theme"], "Serif-Italic", 13, 330)
            toc, _gap, _tries = exc.build_balanced(exc.build_body_excellence, blocks, body_pdf, meta["matiere"].upper())
            if want_sommaire:
                som.render(toc, som_pdf, sommaire, pack, police, std.CFG["cover_pages"])
                parts.append(som_pdf)
            if memoire:
                mem.render_cover_memoire(cover_pdf, meta.get("entete"), meta.get("titre") or meta["theme"],
                                         meta.get("auteur", ""), meta.get("grade", ""), meta.get("diplome", ""),
                                         meta.get("option", ""), meta.get("directeur", ""), year,
                                         qr_url=qr_url, code_qr=code)
            elif membres:
                entete = meta.get("entete") or ENTETE_GROUPE_DEFAUT
                cours = meta["matiere"].strip()
                cours = cours[:1].upper() + cours[1:]
                exc.render_cover_groupe_excellence(
                    cover_pdf, entete, line1, line2, theme_lines, membres, meta["titulaire"].strip(), cours,
                    year, kit_dir=ASSETS + "/", date_remise=meta.get("date", "").strip() or None,
                    crest_path=find_crest(meta["etablissement"], KNOWN_CRESTS_EXCELLENCE),
                    qr_url=qr_url, code_qr=code,
                )
            else:
                exc.render_cover_school_excellence(
                    cover_pdf, line1, line2, year, fields, theme_lines,
                    kit_dir=ASSETS + "/",
                    doc_word=doc_word,
                    crest_path=find_crest(meta["etablissement"], KNOWN_CRESTS_EXCELLENCE),
                    qr_url=qr_url, code_qr=code,
                )

        if n_lim:
            parts.insert(1, lim_pdf)  # couverture, liminaires, sommaire, corps
        parts.append(body_pdf)
        std.merge(parts, final_pdf, title=meta["theme"], author=meta.get("eleve") or ", ".join(membres or []) or "NEXORIA", pack=pack)
        with open(final_pdf, "rb") as f:
            body = f.read()

    # Certificat de vérification : page finale, code unique, QR, inscription au registre
    _TLS.code = code
    final = verification.add_certificate(body, pack, code, meta)
    verification.register(code, pack, meta, final)
    return final
