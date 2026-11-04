# NEXORIA service v3.11 : accès professeur par QR code

## Nouveau : acces.py
- Un devoir peut être mis à disposition d'un enseignant (élève absent) par un lien à usage limité.
- Jeton de 256 bits ; seule son empreinte SHA-256 est enregistrée.
- Limites par défaut : 7 jours, 5 ouvertures ; révocation à tout moment.
- Réponse identique pour un jeton inconnu, expiré, révoqué ou épuisé.
- Conservation : 90 jours, puis suppression automatique du PDF et de l'entrée.
- Journal minimal : date et nombre d'ouvertures. Pas d'adresse IP, pas d'identité du consultant.

## Service
- POST /generate : paramètre creer_acces. Renvoie X-Acces-Url et X-Acces-Id.
- GET /d/{jeton} : ouvre le devoir. Aucune clé API requise. Cache désactivé, non indexable.
- GET /acces : liste sans jetons (authentifiée).
- POST /acces/{id}/revoquer : révocation (authentifiée).
- Variables : NEXORIA_STOCKAGE (dossier des PDF), NEXORIA_ACCES (registre des accès), NEXORIA_PUBLIC_URL.

## Panneau
- Case « Créer un accès professeur » ; bloc dédié avec QR, lien, copie et révocation.
- Avertissement affiché : ne pas imprimer ni publier le QR.

## Prérequis de déploiement
- Monter un volume persistant sur /data et régler NEXORIA_STOCKAGE=/data/devoirs et NEXORIA_ACCES=/data/acces.json.
  Sans volume, les PDF et les accès sont perdus à chaque redéploiement.

## Limites
- Pas de limitation de débit sur /d/{jeton} : à ajouter si le lien est attaqué.
- Le QR contient un lien : une personne qui reçoit le QR peut l'ouvrir jusqu'à épuisement ou expiration.
