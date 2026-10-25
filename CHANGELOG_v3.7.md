# NEXORIA moteur v3.7

## Corrigé (depuis v3.6)
- Standard : texte aligné à gauche (plus de justification). Supprime les espaces élargis
  (« Ce phénomène donne    naissance    à ») ; même choix que l'Excellence depuis la v3.5.
  Les puces sont aussi alignées à gauche.
- Excellence : règle de lettrine unique. Plus d'initiale « en ligne » de taille variable
  pour les paragraphes d'une ligne (ils restent des paragraphes normaux). Plus de suppression
  de la lettrine pour les caractères hors cp1252 (œ, etc.).
  Lettrine sur 2 lignes ou 3 lignes selon la longueur, jamais de cas intermédiaire.
- Standard et Excellence : pas de lettrine si le paragraphe ouvre par un mot en capitales,
  pour ne jamais couper « LE BATEAU » en « L E BATEAU ».

## Vérifié
- Titre coupé sur deux lignes (« I. L'HÉRITAGE TERRITORIAL ET / ADMINISTRATIF ») : recollé, pas de mot
  orphelin en début de paragraphe (contrôle sur le texte du sommaire Marise).
- Sommaire et pagination inchangés.

## Non corrigé (dépend du texte source)
- Tableaux : si le document source est un texte aplati (lignes « Domaine Héritage… » sans séparateur),
  le moteur ne peut pas reconstruire la grille. Il faut un source structuré (.docx ou .pdf avec tableaux,
  ou une grille « a | b » par ligne).
- Titre du PDF (métadonnée) : repris du champ « thème » saisi ; à vérifier dans le formulaire.

## Fichiers modifiés (à remplacer sur GitHub)
- nexoria_engine_standard.py
- nexoria_engine_excellence.py
- CHANGELOG_v3.7.md
