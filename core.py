# -*- coding: utf-8 -*-
"""
NEXORIA — logique de génération (indépendante du framework web)
==================================================================
Séparée de app.py pour deux raisons :
1. Elle peut être testée seule, sans serveur web, avec de simples dictionnaires Python.
2. Si demain le canal change (plus de webhook direct, plus n8n), cette partie ne bouge pas.

build_pdf() est LA fonction qui compte : elle refait exactement la chaîne validée
manuellement pendant les tests (texte brut -> structure -> corps -> sommaire ->
couverture -> fusion), pour les packs Standard et Excellence.
"""
import os
import re
import tempfile

import nexoria_engine_standard as std
import nexoria_engine_excellence as exc

ASSETS = os.path.dirname(__file__)  # tous les fichiers sont désormais côte à côte, à plat

REQUIRED_META = ["etablissement", "eleve", "classe", "matiere", "titulaire", "theme", "annee", "date"]


class GenerationError(Exception):
    """Erreur métier (entrée invalide) — distincte d'un bug interne."""
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def split_school_line(etablissement: str):
    m = re.match(r"^(Complexe Scolaire|Institut(?:\s+Sup[ée]rieur)?|Lyc[ée]e|Coll[eè]ge)\s+(.+)$",
                etablissement, re.I)
    if m:
        return m.group(1).upper(), m.group(2).upper()
    return "", etablissement.upper()


def validate_meta(meta: dict):
    missing = [k for k in REQUIRED_META if not str(meta.get(k, "")).strip()]
    if missing:
        raise GenerationError("Champs manquants dans meta : " + ", ".join(missing))


def build_pdf(pack: str, meta: dict, corps_texte: str) -> bytes:
    if pack not in ("standard", "excellence"):
        raise GenerationError("pack doit être 'standard' ou 'excellence' (reçu : %r)" % pack)
    validate_meta(meta)

    body_lines = [l.strip() for l in corps_texte.split("\n") if l.strip()]
    if not body_lines:
        raise GenerationError("corps_texte est vide")
    blocks = std.classify(body_lines)
    if not any(b["kind"] == "h1" for b in blocks):
        raise GenerationError(
            "Structure non reconnue : aucun titre détecté (INTRODUCTION, I., II., ... "
            "CONCLUSION). On ne devine pas une mise en page sans structure claire.", 422)

    doc_word = meta.get("doc_word") or "DEVOIR"
    line1, line2 = split_school_line(meta["etablissement"])
    year = re.sub(r"\s*[-\u2013\u2014]\s*", " \u2013 ", meta["annee"])
    fields = [
        ("\u00c9L\u00c8VE", meta["eleve"].upper()),
        ("CLASSE", meta["classe"].upper()),
        ("MATI\u00c8RE", meta["matiere"].upper()),
        ("ENCADREUR", meta["titulaire"].upper()),
        ("DATE DE REMISE", meta["date"]),
    ]

    with tempfile.TemporaryDirectory() as d:
        body_pdf = os.path.join(d, "body.pdf")
        som_pdf = os.path.join(d, "som.pdf")
        cover_pdf = os.path.join(d, "cover.pdf")
        final_pdf = os.path.join(d, "final.pdf")

        if pack == "standard":
            theme_lines = std.balance(meta["theme"], "Times-Italic", 13, 330)
            toc, _gap, _tries = std.build_balanced(std.build_body, blocks, body_pdf, meta["matiere"].upper())
            std.build_sommaire(toc, som_pdf)
            std.render_cover_school_standard(
                cover_pdf, line1, line2, year, fields, theme_lines,
                crest_path=None,
                logo_path=os.path.join(ASSETS, "nexoria_logo_grey.png"),
                doc_word=doc_word,
            )
        else:
            theme_lines = exc.balance(meta["theme"], "Times-Italic", 13, 330)
            toc, _gap, _tries = exc.build_balanced(exc.build_body_excellence, blocks, body_pdf, meta["matiere"].upper())
            exc.build_sommaire_excellence(toc, som_pdf)
            exc.render_cover_school_excellence(
                cover_pdf, line1, line2, year, fields, theme_lines,
                kit_dir=ASSETS + "/",
                doc_word=doc_word,
                crest_path=None,
            )

        std.merge([cover_pdf, som_pdf, body_pdf], final_pdf, title=meta["theme"], author=meta["eleve"])
        with open(final_pdf, "rb") as f:
            return f.read()
