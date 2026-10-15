# -*- coding: utf-8 -*-
"""NEXORIA — langue du document (fr par défaut ; en = document entièrement en anglais).

Le moteur reste le même : seuls les libellés fixes (couverture, sommaire, en-tête,
numérotation des pages) et quelques règles typographiques françaises changent.
"""

LANG = {"current": "fr"}
FORMAT = {"current": "paragraphes"}  # "paragraphes" (standard) ou "enumeration" (listes/tableaux, sans lettrine)
FORMATS = ("paragraphes", "enumeration")

STRINGS = {
    "fr": {
        "toc": "SOMMAIRE", "toc_cont": "(suite)", "page_of": "Page %d sur %d",
        "school_year": "ANNÉE SCOLAIRE", "default_doc_word": "DEVOIR",
        "f_student": "ÉLÈVE", "f_class": "CLASSE", "f_subject": "MATIÈRE",
        "f_supervisor": "ENCADREUR", "f_date": "DATE DE REMISE",
        "tagline": "\u00ab L\u2019excellence ne s\u2019improvise pas. Elle s\u2019organise. \u00bb",
    },
    "en": {
        "toc": "CONTENTS", "toc_cont": "(cont.)", "page_of": "Page %d of %d",
        "school_year": "SCHOOL YEAR", "default_doc_word": "ASSIGNMENT",
        "f_student": "STUDENT", "f_class": "CLASS", "f_subject": "SUBJECT",
        "f_supervisor": "SUPERVISOR", "f_date": "SUBMISSION DATE",
        "tagline": "\u2018Excellence is not improvised. It is organised.\u2019",
    },
}


def set_lang(lang):
    if lang not in STRINGS:
        raise ValueError("lang doit être 'fr' ou 'en' (reçu : %r)" % lang)
    LANG["current"] = lang


def t(key):
    return STRINGS[LANG["current"]][key]


def is_en():
    return LANG["current"] == "en"


def set_format(fmt):
    if fmt not in FORMATS:
        raise ValueError("format doit être 'paragraphes' ou 'enumeration' (reçu : %r)" % fmt)
    FORMAT["current"] = fmt


def is_enum():
    return FORMAT["current"] == "enumeration"
