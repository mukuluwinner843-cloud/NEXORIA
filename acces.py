# -*- coding: utf-8 -*-
"""
NEXORIA — accès au devoir par QR code (v3.11)
==============================================
Permet à un professeur d'obtenir le devoir d'un élève absent, en scannant un QR code
reçu séparément (jamais imprimé sur le document).

Garanties :
  - le jeton fait 256 bits ; seul son empreinte SHA-256 est enregistrée, jamais le jeton ;
  - durée de validité et nombre d'ouvertures limités ; révocation possible à tout moment ;
  - réponse identique pour un jeton inconnu, expiré ou révoqué (pas d'indice pour un attaquant) ;
  - PDF conservé dans un dossier privé, supprimé automatiquement après la durée de conservation ;
  - journal minimal : date et nombre d'ouvertures, sans adresse IP ni nom du consultant.
"""
import hashlib
import json
import os
import secrets
import threading
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
STOCKAGE = os.environ.get("NEXORIA_STOCKAGE", os.path.join(BASE, "data", "devoirs"))
REGISTRE_ACCES = os.environ.get("NEXORIA_ACCES", os.path.join(BASE, "data", "acces.json"))
DUREE_JOURS = 7
MAX_OUVERTURES = 5
CONSERVATION_JOURS = 90

_VERROU = threading.Lock()


class AccesIndisponible(Exception):
    """Réponse générique : jeton inconnu, expiré, révoqué ou épuisé."""


def _maintenant():
    return datetime.now()


def _empreinte(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _charger():
    if not os.path.exists(REGISTRE_ACCES):
        return {"acces": []}
    with open(REGISTRE_ACCES, encoding="utf-8") as f:
        return json.load(f)


def _ecrire(data):
    os.makedirs(os.path.dirname(REGISTRE_ACCES), exist_ok=True)
    tmp = REGISTRE_ACCES + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REGISTRE_ACCES)


def _chemin_pdf(acces_id):
    if not acces_id.isalnum():
        raise AccesIndisponible()
    return os.path.join(STOCKAGE, acces_id + ".pdf")


def purger(maintenant=None):
    """Supprime les PDF et les entrées au-delà de la durée de conservation."""
    maintenant = maintenant or _maintenant()
    limite = maintenant - timedelta(days=CONSERVATION_JOURS)
    with _VERROU:
        data = _charger()
        gardes = []
        for a in data["acces"]:
            cree = datetime.fromisoformat(a["cree"])
            if cree < limite:
                try:
                    os.remove(_chemin_pdf(a["id"]))
                except (OSError, AccesIndisponible):
                    pass
            else:
                gardes.append(a)
        if len(gardes) != len(data["acces"]):
            data["acces"] = gardes
            _ecrire(data)


def creer(pdf_bytes, meta, code, jours=DUREE_JOURS, max_ouvertures=MAX_OUVERTURES):
    """Enregistre le PDF et renvoie (id, jeton). Le jeton n'est affiché qu'une fois, à la création."""
    purger()
    acces_id = secrets.token_hex(8)
    token = secrets.token_urlsafe(32)
    maintenant = _maintenant()
    os.makedirs(STOCKAGE, exist_ok=True)
    with open(_chemin_pdf(acces_id), "wb") as f:
        f.write(pdf_bytes)
    entree = {
        "id": acces_id,
        "empreinte_jeton": _empreinte(token),
        "code_document": code,
        "eleve": meta.get("eleve", ""),
        "matiere": meta.get("matiere", ""),
        "theme": meta.get("theme", ""),
        "cree": maintenant.isoformat(timespec="seconds"),
        "expire": (maintenant + timedelta(days=jours)).isoformat(timespec="seconds"),
        "max_ouvertures": max_ouvertures,
        "ouvertures": [],
        "revoque": False,
    }
    with _VERROU:
        data = _charger()
        data["acces"].append(entree)
        _ecrire(data)
    return acces_id, token


def ouvrir(token):
    """Renvoie les octets du PDF si le jeton est valide, et enregistre l'ouverture."""
    if not token or len(token) < 20:
        raise AccesIndisponible()
    h = _empreinte(token)
    maintenant = _maintenant()
    with _VERROU:
        data = _charger()
        for a in data["acces"]:
            if secrets.compare_digest(a["empreinte_jeton"], h):
                if a["revoque"]:
                    raise AccesIndisponible()
                if maintenant > datetime.fromisoformat(a["expire"]):
                    raise AccesIndisponible()
                if len(a["ouvertures"]) >= a["max_ouvertures"]:
                    raise AccesIndisponible()
                try:
                    with open(_chemin_pdf(a["id"]), "rb") as f:
                        contenu = f.read()
                except OSError:
                    raise AccesIndisponible()
                a["ouvertures"].append(maintenant.isoformat(timespec="seconds"))
                _ecrire(data)
                return contenu, a["code_document"]
    raise AccesIndisponible()


def revoquer(acces_id):
    with _VERROU:
        data = _charger()
        for a in data["acces"]:
            if a["id"] == acces_id:
                a["revoque"] = True
                _ecrire(data)
                return True
    return False


def lister():
    """Liste sans jeton ni empreinte : pour le panneau, côté personne authentifiée."""
    out = []
    for a in _charger()["acces"]:
        out.append({k: a[k] for k in ("id", "eleve", "matiere", "theme", "cree", "expire",
                                      "revoque", "code_document")} |
                   {"ouvertures": len(a["ouvertures"]), "max_ouvertures": a["max_ouvertures"]})
    return out
