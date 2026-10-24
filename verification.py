"""NEXORIA — vérification des documents (v3.17).

Chaque document reçoit :
  - un code unique (NX-AAAA-MMJJ-PACK-XXXXXX) ;
  - une page « Certificat de vérification » en dernière page, séparée du texte ;
  - une entrée dans le registre (verifications.json) avec l'empreinte SHA-256 du PDF final.

Double vérification :
  1. le code et le QR code (papier ou numérique) → statut en ligne ;
  2. le fichier numérique → empreinte SHA-256 comparée au registre.
Le statut n'est jamais imprimé : il se lit en ligne, il reste à jour.
"""
import hashlib
import json
import os
import secrets
import tempfile
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FD = "/usr/share/fonts/truetype/dejavu/"
_RL = os.path.join(os.path.dirname(__import__("reportlab").__file__), "fonts") + os.sep
# Chaque police : DejaVu si présent (hébergeur), sinon Vera livrée avec ReportLab (toujours disponible)
_FONTS = [("Sans", ["DejaVuSans.ttf"], ["Vera.ttf"]),
          ("SansB", ["DejaVuSans-Bold.ttf"], ["VeraBd.ttf"]),
          ("SerifB", ["DejaVuSerif-Bold.ttf"], ["VeraBd.ttf"]),
          ("SerifI", ["DejaVuSerif-Italic.ttf"], ["VeraIt.ttf"])]
for _n, _dv, _vera in _FONTS:
    if _n in pdfmetrics.getRegisteredFontNames():
        continue
    for _path in [_FD + _dv[0], _RL + _vera[0]]:
        if os.path.exists(_path):
            pdfmetrics.registerFont(TTFont(_n, _path))
            break

VERIF_BASE = os.environ.get("NEXORIA_VERIF_BASE", "https://mukuluwinner843-cloud.github.io/nexoria-verif/")
# Registre : NEXORIA_REGISTRE si défini (ex. volume Railway : /data/verifications.json),
# sinon un fichier dans le dossier du service (effacé à chaque redéploiement sans volume).
REGISTRE = os.environ.get("NEXORIA_REGISTRE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "verifications.json")
OR = HexColor("#B89252"); CHAR = HexColor("#1C1C1C"); GRIS = HexColor("#666666"); PARCH = HexColor("#F8F6F0")
W, H = A4


def new_code(pack, meta, corps):
    """Code unique : date + pack + 6 caractères aléatoires liés au contenu."""
    now = datetime.now()
    raw = json.dumps(meta, sort_keys=True, ensure_ascii=False) + corps + secrets.token_hex(8)
    suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:6].upper()
    tag = "EXC" if pack == "excellence" else "STD"
    return f"NX-{now:%Y}-{now:%m%d}-{tag}-{suffix}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cert_page(path, code, pack, meta):
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle("NEXORIA - Certificat de vérification " + code)
    excellence = pack == "excellence"
    if excellence:
        c.setFillColor(PARCH); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setStrokeColor(OR if excellence else GRIS); c.setLineWidth(1.2)
    c.rect(1.4 * cm, 1.4 * cm, W - 2.8 * cm, H - 2.8 * cm, stroke=1, fill=0)
    c.setFillColor(GRIS); c.setFont("SansB", 9)
    c.drawCentredString(W / 2, H - 4.0 * cm, "C E R T I F I C A T   D E   V É R I F I C A T I O N")
    c.setFillColor(CHAR); c.setFont("SerifB", 22)
    c.drawCentredString(W / 2, H - 5.2 * cm, "Document NEXORIA")
    url = VERIF_BASE.rstrip("/") + "/?code=" + code
    size = 6.0 * cm
    q = qr.QrCodeWidget(url); b = q.getBounds()
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0]); d.add(q)
    renderPDF.draw(d, c, W / 2 - size / 2, H - 13.2 * cm)
    c.setFillColor(CHAR); c.setFont("SansB", 15)
    c.drawCentredString(W / 2, H - 14.4 * cm, code)
    c.setFillColor(GRIS); c.setFont("Sans", 9)
    lignes = [("Pack", "Excellence" if excellence else "Standard"),
              ("Document", meta.get("theme", "")), ("Date de remise", meta.get("date", ""))]
    y = H - 16.2 * cm
    for k, v in lignes:
        c.setFillColor(GRIS); c.setFont("Sans", 9.5); c.drawString(3.2 * cm, y, k)
        c.setFillColor(CHAR); c.setFont("SansB", 9.5); c.drawRightString(W - 3.2 * cm, y, str(v))
        c.setStrokeColor(OR if excellence else GRIS); c.setLineWidth(0.3)
        c.line(3.2 * cm, y - 0.3 * cm, W - 3.2 * cm, y - 0.3 * cm)
        y -= 0.8 * cm
    c.setFillColor(GRIS); c.setFont("SerifI", 10)
    c.drawCentredString(W / 2, 6.6 * cm, "Scannez le QR code, ou saisissez le code sur la page de vérification.")
    c.drawCentredString(W / 2, 6.0 * cm, "Le statut de validation est consulté en ligne et reste à jour.")
    c.drawCentredString(W / 2, 5.0 * cm, "Le fichier numérique peut aussi être vérifié par son empreinte.")
    c.setFont("Sans", 7.5); c.drawCentredString(W / 2, 3.2 * cm, url)
    c.showPage(); c.save()


def add_certificate(body_bytes: bytes, pack: str, code: str, meta: dict) -> bytes:
    """Ajoute la page de certificat après la fin du texte, sur sa propre page."""
    with tempfile.TemporaryDirectory() as d:
        cert = os.path.join(d, "cert.pdf")
        _cert_page(cert, code, pack, meta)
        writer = PdfWriter()
        for p in PdfReader(_bytes_io(body_bytes)).pages:
            writer.add_page(p)
        for p in PdfReader(cert).pages:
            writer.add_page(p)
        writer.add_metadata({"/Title": meta.get("theme", "NEXORIA"), "/Author": meta.get("eleve", "NEXORIA")})
        out = os.path.join(d, "final.pdf")
        with open(out, "wb") as f:
            writer.write(f)
        with open(out, "rb") as f:
            return f.read()


def _bytes_io(data):
    import io
    return io.BytesIO(data)


def register(code, pack, meta, final_bytes, registre=None):
    """Ajoute l'entrée au registre, statut « en_attente ». Ne remplace jamais une entrée existante."""
    path = registre or REGISTRE
    if not path:
        return None
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    entry = {"code": code, "pack": "Excellence" if pack == "excellence" else "Standard",
             "eleve": meta.get("eleve", ""), "classe": meta.get("classe", ""),
             "matiere": meta.get("matiere", ""), "encadreur": meta.get("titulaire", ""),
             "etablissement": meta.get("etablissement", ""),
             "document": meta.get("theme", ""), "date": meta.get("date", ""), "statut": "en_attente",
             "empreinte": sha256_bytes(final_bytes), "mis_a_jour": datetime.now().strftime("%Y-%m-%d")}
    data = {"documents": []}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    if any(x.get("code") == code for x in data.get("documents", [])):
        raise RuntimeError("code déjà présent dans le registre : " + code)
    data.setdefault("documents", []).append(entry)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return entry
