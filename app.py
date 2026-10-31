# -*- coding: utf-8 -*-
"""
NEXORIA — service de mise en page (Phase 1 de l'automatisation)
=================================================================
Couche web fine au-dessus de core.py. C'est ce fichier que n8n appelle.

Entrée  : JSON avec les informations de l'élève + le texte brut du devoir.
Sortie  : le PDF fini (Standard ou Excellence), prêt à être renvoyé sur WhatsApp.

Sécurité minimale : une clé secrète partagée (variable d'environnement
NEXORIA_API_KEY), à passer dans l'en-tête HTTP  X-API-Key.
"""
import hmac
import os
import re
import unicodedata
from typing import Literal, Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

import json
import logging

import core
import nexoria_structure
import nexoria_coordination as coord
import extract
import rapport
import verification
import nexoria_sommaires as som

SERVICE_VERSION = "3.10"
MAX_CORPS = 300_000  # caractères : un devoir long reste très en dessous
log = logging.getLogger("nexoria")
logging.basicConfig(level=logging.INFO)

API_KEY = os.environ.get("NEXORIA_API_KEY")  # défini sur l'hébergeur, jamais écrit ici en dur


def check_key(x_api_key: Optional[str]):
    """Fermé par défaut : sans NEXORIA_API_KEY configurée sur l'hébergeur, le service refuse tout appel
    (au lieu de rester ouvert à tout le monde)."""
    if not API_KEY:
        raise HTTPException(503, "Service non configuré : NEXORIA_API_KEY absente sur l'hébergeur.")
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(401, "Clé API invalide ou manquante (en-tête X-API-Key).")


def safe_filename(*parts):
    """Nom de fichier ASCII sûr pour l'en-tête HTTP (un nom avec « ’ » ou un guillemet ferait planter la réponse)."""
    raw = "_".join(p for p in parts if p)
    ascii_ = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_).strip("_") or "document"


app = FastAPI(title="NEXORIA Layout Service", version=SERVICE_VERSION)

# Permet au panneau de génération (page HTML locale, ouverte depuis le téléphone)
# d'appeler ce service depuis un navigateur. Sans danger : tout appel doit de toute
# façon fournir la clé API secrète pour obtenir un résultat.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Verification-Code", "X-Verification-Url", "X-Service-Version"],
)


class Meta(BaseModel):
    etablissement: str = Field(..., max_length=150, examples=["Complexe Scolaire Francisco Palau"])
    eleve: str = Field(..., min_length=1, max_length=120)
    classe: str = Field("", max_length=60, description="Laisser vide si le niveau/la classe n'est pas précisé sur le document")
    matiere: str = Field(..., min_length=1, max_length=100)
    titulaire: str = Field(..., min_length=1, max_length=120, description="Nom de l'enseignant/encadreur")
    theme: str = Field(..., min_length=1, max_length=250, description="Titre ou thème du devoir")
    annee: str = Field(..., min_length=1, max_length=20, examples=["2026-2027"])
    date: str = Field(..., min_length=1, max_length=40, description="Date de remise, telle qu'à afficher")
    doc_word: str = Field("DEVOIR", max_length=40, description="Mot affiché en gros sur la couverture")


class GenerateRequest(BaseModel):
    pack: Literal["standard", "excellence"]
    meta: Meta
    corps_texte: str = Field(..., min_length=1, max_length=MAX_CORPS,
                             description="Texte brut du devoir : INTRODUCTION, I., II., ... CONCLUSION")
    sommaire: Literal["classique", "pilules", "numerote", "chiffres", "colonnes"] = Field(
        "classique", description="Modèle de sommaire (voir GET /modeles)")
    police: Literal["defaut", "times", "helvetica", "dejavu-sans"] = Field(
        "defaut", description="Police du corps de texte et des sommaires (voir GET /modeles)")
    force: bool = Field(False, description="Génère même si le contrôle bloque (validation humaine)")


@app.get("/health")
def health():
    return {"status": "ok", "version": SERVICE_VERSION}


@app.get("/modeles")
def modeles():
    """Choix proposés au panneau : modèles de sommaire et polices (sans clé : aucune donnée sensible)."""
    return {"sommaire": list(som.MODELES), "police": list(som.POLICES_NOMS)}


@app.post("/generate")
def generate(req: GenerateRequest, x_api_key: Optional[str] = Header(None)):
    check_key(x_api_key)
    # v3.10 : contrôle de cohérence avant génération (thème/contenu, titres, texte vide)
    verif = coord.verifier(req.meta.model_dump(), req.corps_texte)
    if not coord.decider(verif, force=req.force):
        raise HTTPException(422, "Génération bloquée : " + " ".join(verif["erreurs"]))
    try:
        pdf_bytes = core.build_pdf(req.pack, req.meta.model_dump(), req.corps_texte,
                                   sommaire=req.sommaire, police=req.police)
    except core.GenerationError as e:
        raise HTTPException(e.status_code, str(e))
    except Exception:
        # Une erreur interne ne doit jamais faire tomber le service : on journalise, on répond proprement.
        log.exception("échec de génération (pack=%s)", req.pack)
        raise HTTPException(500, "Erreur interne de mise en page. Réessaie ; si cela persiste, envoie le texte au support.")
    filename = safe_filename(req.meta.doc_word, req.meta.eleve, req.pack.upper()) + ".pdf"
    code = core.last_code() or ""
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % filename,
                             "X-Verification-Code": code,
                             "X-Verification-Url": verification.VERIF_BASE + "?code=" + code,
                             "X-Service-Version": SERVICE_VERSION})


def _registre():
    path = verification.REGISTRE
    if not path or not os.path.exists(path):
        return {"documents": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_CHAMPS_PUBLICS = ["code", "pack", "document", "date", "statut", "empreinte", "mis_a_jour"]


@app.get("/registre/public")
def registre_public(x_api_key: Optional[str] = Header(None)):
    """Version publiable (sans nom d'élève) : à téléverser sur le dépôt nexoria-verif."""
    check_key(x_api_key)
    docs = [{c: d.get(c, "") for c in _CHAMPS_PUBLICS} for d in _registre().get("documents", [])]
    body = json.dumps({"documents": docs}, ensure_ascii=False, indent=2)
    return Response(content=body, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="verifications.json"'})


@app.get("/registre/complet")
def registre_complet(x_api_key: Optional[str] = Header(None)):
    """Sauvegarde complète (avec noms, classes, écoles) : archive privée, ne pas publier."""
    check_key(x_api_key)
    body = json.dumps(_registre(), ensure_ascii=False, indent=2)
    return Response(content=body, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="registre_complet_nexoria.json"'})


@app.get("/rapport")
def rapport_pdf(x_api_key: Optional[str] = Header(None)):
    """Rapport PDF de tous les documents générés (archive et remise aux clients)."""
    check_key(x_api_key)
    pdf = rapport.build_report(_registre())
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="rapport_nexoria.pdf"'})


@app.post("/extract")
async def extract_document(file: UploadFile = File(...), x_api_key: Optional[str] = Header(None)):
    """Lit un .docx ou .pdf déposé et renvoie son texte + la liste des titres reconnus.
    Ne rédige et ne complète rien : le texte renvoyé est celui du document."""
    check_key(x_api_key)
    data = await file.read()
    try:
        return extract.extract_document(file.filename, data)
    except extract.ExtractionError as e:
        raise HTTPException(e.status_code, str(e))


class StructureRequest(BaseModel):
    texte: str = Field(..., min_length=1, max_length=MAX_CORPS)


@app.post("/structure")
def structure(req: StructureRequest, x_api_key: Optional[str] = Header(None)):
    """Analyse le texte collé : titres reconnus, titres déduits (à vérifier), texte reformaté.
    Ne modifie aucun mot : seulement la mise en forme des titres et des paragraphes."""
    check_key(x_api_key)
    return nexoria_structure.reconstruire(req.texte)


class VerifierRequest(BaseModel):
    meta: Meta
    corps_texte: str = Field(..., max_length=MAX_CORPS)


@app.post("/verifier")
def verifier_route(req: VerifierRequest, x_api_key: Optional[str] = Header(None)):
    """Contrôle de cohérence sans génération : statut (pret / a_verifier / bloque), erreurs, avertissements,
    titres reconnus et texte reformaté. Aucun mot n'est modifié."""
    check_key(x_api_key)
    return coord.verifier(req.meta.model_dump(), req.corps_texte)
