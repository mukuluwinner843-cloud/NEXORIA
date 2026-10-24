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

import core
import extract
import rapport
import verification
import nexoria_sommaires as som

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


app = FastAPI(title="NEXORIA Layout Service", version="1.0")

# Permet au panneau de génération (page HTML locale, ouverte depuis le téléphone)
# d'appeler ce service depuis un navigateur. Sans danger : tout appel doit de toute
# façon fournir la clé API secrète pour obtenir un résultat.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Verification-Code", "X-Verification-Url"],
)


class Meta(BaseModel):
    etablissement: str = Field(..., examples=["Complexe Scolaire Francisco Palau"])
    eleve: str
    classe: str = Field("", description="Laisser vide si le niveau/la classe n'est pas précisé sur le document")
    matiere: str
    titulaire: str = Field(..., description="Nom de l'enseignant/encadreur")
    theme: str = Field(..., description="Titre ou thème du devoir")
    annee: str = Field(..., examples=["2026-2027"])
    date: str = Field(..., description="Date de remise, telle qu'à afficher")
    doc_word: str = Field("DEVOIR", description="Mot affiché en gros sur la couverture")


class GenerateRequest(BaseModel):
    pack: Literal["standard", "excellence"]
    meta: Meta
    corps_texte: str = Field(..., description="Texte brut du devoir : INTRODUCTION, I., II., ... CONCLUSION")
    sommaire: Literal["classique", "pilules", "numerote", "chiffres", "colonnes"] = Field(
        "classique", description="Modèle de sommaire (voir GET /modeles)")
    police: Literal["defaut", "times", "helvetica", "dejavu-sans"] = Field(
        "defaut", description="Police du corps de texte et des sommaires (voir GET /modeles)")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/modeles")
def modeles():
    """Choix proposés au panneau : modèles de sommaire et polices (sans clé : aucune donnée sensible)."""
    return {"sommaire": list(som.MODELES), "police": list(som.POLICES_NOMS)}


@app.post("/generate")
def generate(req: GenerateRequest, x_api_key: Optional[str] = Header(None)):
    check_key(x_api_key)
    try:
        pdf_bytes = core.build_pdf(req.pack, req.meta.model_dump(), req.corps_texte,
                                   sommaire=req.sommaire, police=req.police)
    except core.GenerationError as e:
        raise HTTPException(e.status_code, str(e))
    filename = safe_filename(req.meta.doc_word, req.meta.eleve, req.pack.upper()) + ".pdf"
    code = core.last_code() or ""
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % filename,
                             "X-Verification-Code": code,
                             "X-Verification-Url": verification.VERIF_BASE + "?code=" + code})


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
