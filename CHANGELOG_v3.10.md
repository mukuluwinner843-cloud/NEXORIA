# NEXORIA service v3.10 : coordination

## Nouveau : nexoria_coordination.py
- Contrôle de cohérence avant génération, décision automatique :
  - bloque : thème absent du texte (mots entiers, formes fléchies), texte vide, aucun titre, champ obligatoire vide ;
  - a_verifier : introduction ou conclusion absentes, titres déduits, tableaux, texte très court ou très long, titre en double ;
  - pret : aucun point.
- Aucun mot du devoir n'est modifié : seule la mise en forme des titres est reconstruite.

## Service
- POST /verifier : rapport complet sans génération (statut, erreurs, avertissements, titres, texte reformaté).
- POST /generate : refuse un devoir bloqué (HTTP 422, motif lisible), sauf si force=true (validation humaine).
- Version 3.10.

## Panneau
- Contrôle affiché avant génération (bloqué en rouge, à vérifier en orange).
- Case « Forcer la génération » pour les cas validés par un humain.

## Limites
- Les contrôles de cohérence sont des règles : ils détectent un thème absent, pas une erreur de fond.
- Le traitement par lots reste la file d'attente du panneau (40 documents maximum).
