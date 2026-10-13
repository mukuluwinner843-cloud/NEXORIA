# NEXORIA moteur v3.6

## Corrigé (depuis v3.5)
- Titres coupés sur deux lignes dans le document source : la suite en capitales (« ADMINISTRATIF »)
  est recollée au titre, au lieu d'apparaître en majuscules isolées au début du paragraphe suivant.
  La même correction s'applique au sommaire (une seule entrée, sans troncature).

- Tableaux aplatis en texte (Excellence comme Standard) : chaque ligne « a| b » reste une ligne de tableau.

## Fichiers modifiés (à remplacer sur GitHub)
- nexoria_engine_standard.py (fonction classify)
- nexoria_tables.py (paragraphs_from_markdown)
- nexoria_engine_excellence.py et nexoria_sommaires.py : identiques à la v3.5

## Non corrigé
- Rendu du sommaire « colonnes » : à valider avec les maquettes de référence.

## v3.6.1
- nexoria_engine_standard.py : enregistrement des polices DejaVu tolérant aux fichiers absents.
  Si DejaVuSerif-Italic.ttf (ou -Bold) n'est pas présent sur le serveur, la version romaine est utilisée
  au lieu de faire planter le service au démarrage (correctif du TTFError sur Railway).
- Aucun autre changement. Le Dockerfile n'est pas modifié.
