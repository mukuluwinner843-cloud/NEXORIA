# -*- coding: utf-8 -*-
"""NEXORIA — contrôle qualité automatique du PDF généré (v3.16).

Après chaque rendu, le moteur relit le PDF produit et vérifie que :
  - le sommaire est présent dès qu'il y a des titres de partie ;
  - chaque paragraphe et chaque ligne de tableau du texte source apparaît bien dans le PDF
    (détecte les troncatures silencieuses, comme une liste coupée en plein milieu) ;
  - la première lettre de chaque paragraphe garde sa casse d'origine (majuscule reste majuscule) ;
  - les numéros de page du sommaire correspondent aux pages réelles des titres.

Les contrôles ne modifient jamais le contenu : ils rapportent des anomalies. Le résultat est
renvoyé dans un rapport ; le service l'expose dans les en-têtes HTTP (X-Nexoria-QA).
"""
import io
import re
import unicodedata

from pypdf import PdfReader


def _norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def pdf_pages_text(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [(p.extract_text() or "") for p in reader.pages]


def source_units(corps_texte):
    """Unités de texte source à retrouver dans le PDF : paragraphes et lignes de tableau."""
    units = []
    for raw in re.split(r"\n\s*\n", corps_texte.strip()):
        lines = [x.strip() for x in raw.split("\n") if x.strip()]
        for ln in lines:
            if re.fullmatch(r"\|?[\s|:\-]+\|?", ln):
                continue  # séparateur de tableau
            if ln.startswith("|"):
                cells = [c.strip() for c in ln.strip("|").split("|")]
                units.append(("row", " ".join(c for c in cells if c)))
            else:
                units.append(("para", ln))
    return units


def check(pdf_bytes, corps_texte, summary_expected=True):
    """Retourne un rapport : {'ok': bool, 'issues': [codes], 'details': [texte]}."""
    issues, details = [], []
    pages = pdf_pages_text(pdf_bytes)
    full = "\n".join(pages)
    full_n = _norm(full)

    # 1. sommaire présent
    has_toc = any(re.search(r"\b(SOMMAIRE|CONTENTS)\b", p) for p in pages[:3])
    if summary_expected and not has_toc:
        issues.append("sommaire_absent")
        details.append("Aucun sommaire trouvé dans les premières pages.")

    # 2. contenu complet : chaque unité source doit apparaître dans le PDF
    missing = []
    for kind, txt in source_units(corps_texte):
        key = _norm(txt)[:40]
        if len(key) >= 8 and key not in full_n:
            missing.append(txt[:60])
    if missing:
        issues.append("contenu_manquant")
        details.append("%d passage(s) introuvable(s) dans le PDF, par ex. : %s" % (len(missing), " | ".join(missing[:3])))

    # 3. casse de la première lettre : chaque paragraphe commençant par une majuscule doit garder
    #    cette majuscule (on compare les 25 premiers caractères alphabétiques)
    case_bad = []
    raw_pdf = re.sub(r"\s", "", full)
    for kind, txt in source_units(corps_texte):
        if kind != "para" or not txt[:1].isalpha() or not txt[:1].isupper():
            continue
        head = re.sub(r"\s", "", txt)[:20]
        if len(head) < 10 or head in raw_pdf:
            continue
        if head[0].lower() + head[1:] in raw_pdf:   # la majuscule initiale a disparu
            case_bad.append(txt[:40])
    if case_bad:
        issues.append("casse_premiere_lettre")
        details.append("Première lettre non conservée pour : %s" % " | ".join(case_bad[:3]))

    # 4. numéros de page du sommaire vs pages réelles des titres de partie
    if has_toc:
        toc_idx = next(i for i, p in enumerate(pages[:3]) if re.search(r"\b(SOMMAIRE|CONTENTS)\b", p))
        titles = [txt for kind, txt in source_units(corps_texte)
                  if kind == "para" and re.match(r"^(INTRODUCTION|CONCLUSION|[IVX]+\.\s|CONTENTS)", txt)]
        bad = []
        for t in titles:
            key = _norm(t)[:30]
            real = next((i + 1 for i, p in enumerate(pages) if i > toc_idx and key in _norm(p)), None)
            listed = None
            for line in pages[toc_idx].split("\n"):
                if key and key in _norm(line):
                    nums = re.findall(r"\b(\d{1,3})\b", line)
                    if nums:
                        listed = int(nums[-1])
            if real and listed and real != listed:
                bad.append("%s (sommaire %d, réel %d)" % (t[:30], listed, real))
        if bad:
            issues.append("pages_sommaire_decalees")
            details.append("Pages décalées : " + " ; ".join(bad[:4]))

    return {"ok": not issues, "issues": issues, "details": details, "pages": len(pages)}
