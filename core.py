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
}
KNOWN_CRESTS_EXCELLENCE = {
    "francisco palau": "crest_transparent.png",
    "gianelli": "crest_gianelli.png",
}


# Le moteur garde des réglages globaux (polices, compteurs de pages) : une seule génération à la fois.
_RENDER_LOCK = threading.Lock()


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
    missing = [k for k in REQUIRED_META if not str(meta.get(k, "")).strip()]
    if missing:
        raise GenerationError("Champs manquants dans meta : " + ", ".join(missing))


def build_pdf(pack: str, meta: dict, corps_texte: str,
              sommaire: str = "classique", police: str = "defaut") -> bytes:
    if pack not in ("standard", "excellence"):
        raise GenerationError("pack doit être 'standard' ou 'excellence' (reçu : %r)" % pack)
    if sommaire not in som.MODELES:
        raise GenerationError("sommaire doit être l'un de : %s (reçu : %r)" % (", ".join(som.MODELES), sommaire))
    if police not in som.POLICES_NOMS:
        raise GenerationError("police doit être l'une de : %s (reçu : %r)" % (", ".join(som.POLICES_NOMS), police))
    validate_meta(meta)
    with _RENDER_LOCK:
        return _build(pack, meta, corps_texte, sommaire, police)


def _build(pack, meta, corps_texte, sommaire, police):
    try:
        som.set_police(police)
    except ValueError as e:
        raise GenerationError(str(e))

    paras = paragraphs_from_markdown(corps_texte)
    if not paras:
        raise GenerationError("corps_texte est vide")
    pre = extract_special_blocks(paras)
    blocks = std.classify(pre)
    if not any(b["kind"] == "h1" for b in blocks):
        raise GenerationError(
            "Structure non reconnue : aucun titre détecté (INTRODUCTION, I., II., ... "
            "CONCLUSION). On ne devine pas une mise en page sans structure claire.", 422)

    doc_word = meta.get("doc_word") or "DEVOIR"
    line1, line2 = split_school_line(meta["etablissement"])
    year = re.sub(r"\s*[-\u2013\u2014]\s*", " \u2013 ", meta["annee"])
    fields = [("\u00c9L\u00c8VE", meta["eleve"].upper())]
    if str(meta.get("classe", "")).strip():
        fields.append(("CLASSE", meta["classe"].upper()))
    fields += [
        ("MATI\u00c8RE", meta["matiere"].upper()),
        ("ENCADREUR", meta["titulaire"].upper()),
        ("DATE DE REMISE", meta["date"]),
    ]

    with tempfile.TemporaryDirectory() as d:
        body_pdf = os.path.join(d, "body.pdf")
        som_pdf = os.path.join(d, "som.pdf")
        cover_pdf = os.path.join(d, "cover.pdf")
        final_pdf = os.path.join(d, "final.pdf")
        want_sommaire = std.needs_sommaire(blocks)
        n_som = som.page_count(blocks, sommaire, pack, police) if want_sommaire else 0
        std.CFG["cover_pages"] = 1 + n_som
        parts = [cover_pdf]

        if pack == "standard":
            theme_lines = std.balance(meta["theme"], "Times-Italic", 13, 330)
            toc, _gap, _tries = std.build_balanced(std.build_body, blocks, body_pdf, meta["matiere"].upper())
            if want_sommaire:
                som.render(toc, som_pdf, sommaire, pack, police, std.CFG["cover_pages"])
                parts.append(som_pdf)
            std.render_cover_school_standard(
                cover_pdf, line1, line2, year, fields, theme_lines,
                crest_path=find_crest(meta["etablissement"], KNOWN_CRESTS),
                logo_path=os.path.join(ASSETS, "nexoria_logo_grey.png"),
                doc_word=doc_word,
            )
        else:
            theme_lines = exc.balance(meta["theme"], "Times-Italic", 13, 330)
            toc, _gap, _tries = exc.build_balanced(exc.build_body_excellence, blocks, body_pdf, meta["matiere"].upper())
            if want_sommaire:
                som.render(toc, som_pdf, sommaire, pack, police, std.CFG["cover_pages"])
                parts.append(som_pdf)
            exc.render_cover_school_excellence(
                cover_pdf, line1, line2, year, fields, theme_lines,
                kit_dir=ASSETS + "/",
                doc_word=doc_word,
                crest_path=find_crest(meta["etablissement"], KNOWN_CRESTS_EXCELLENCE),
            )

        parts.append(body_pdf)
        std.merge(parts, final_pdf, title=meta["theme"], author=meta["eleve"], pack=pack)
        with open(final_pdf, "rb") as f:
            body = f.read()

    # Certificat de vérification : page finale, code unique, QR, inscription au registre
    code = verification.new_code(pack, meta, corps_texte)
    final = verification.add_certificate(body, pack, code, meta)
    verification.register(code, pack, meta, final)
    return final
