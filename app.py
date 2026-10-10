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
import os
from typing import Literal, Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

import core
import extract

API_KEY = os.environ.get("NEXORIA_API_KEY")  # défini sur l'hébergeur, jamais écrit ici en dur

app = FastAPI(title="NEXORIA Layout Service", version="1.0")

# Permet au panneau de génération (page HTML locale, ouverte depuis le téléphone)
# d'appeler ce service depuis un navigateur. Sans danger : tout appel doit de toute
# façon fournir la clé API secrète pour obtenir un résultat.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate(req: GenerateRequest, x_api_key: Optional[str] = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "Clé API invalide ou manquante (en-tête X-API-Key).")
    try:
        pdf_bytes = core.build_pdf(req.pack, req.meta.model_dump(), req.corps_texte)
    except core.GenerationError as e:
        raise HTTPException(e.status_code, str(e))
    filename = "%s_%s_%s.pdf" % (req.meta.doc_word, req.meta.eleve.replace(" ", "_"), req.pack.upper())
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % filename})


@app.post("/extract")
async def extract_document(file: UploadFile = File(...), x_api_key: Optional[str] = Header(None)):
    """Lit un .docx ou .pdf déposé et renvoie son texte + la liste des titres reconnus.
    Ne rédige et ne complète rien : le texte renvoyé est celui du document."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "Clé API invalide ou manquante (en-tête X-API-Key).")
    data = await file.read()
    try:
        return extract.extract_document(file.filename, data)
    except extract.ExtractionError as e:
        raise HTTPException(e.status_code, str(e))
