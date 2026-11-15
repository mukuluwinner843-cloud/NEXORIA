# NEXORIA — version 3.12

## Polices (corrigé)
- Le choix de police change désormais réellement le PDF : corps, titres, en-têtes, pieds de page, tableaux, schémas et sommaires suivent la même police.
- Nouveau registre `nexoria_polices.py` (source unique) ; fichiers TTF dans `fonts/` (Inter, Montserrat, Jost, EB Garamond, licence OFL).
- Options : `defaut`, `helvetica`, `times`, `inter`, `montserrat`, `futura`, `garamond`.
- `futura` = Jost (équivalent libre dessiné dans l'esprit de Futura ; Futura elle-même n'est pas libre et n'est pas embarquée).
- `dejavu-sans` retirée (remplacée par les options ci-dessus). L'API refuse désormais toute valeur hors liste (422).
- La couverture et le certificat de vérification gardent leurs polices de kit.

## Pack Excellence : première lettre
- Première lettre du paragraphe mise en majuscule (paragraphes et lettrine) : une initiale minuscule n'est plus produite.

## Markdown inline
- `**gras**` et `*italique*` sont convertis en gras et italique (les astérisques ne restent plus dans le PDF).

## Sommaires
- Vérifiés sur 30 parties, sommaire sur plusieurs pages, 5 modèles, 2 packs : 0 écart entre numéros annoncés et pages réelles.
- Les sommaires utilisent désormais le registre de polices commun.

## Technique
- `SERVICE_VERSION` = 3.12 ; `/modeles` renvoie les 7 polices.
- Panneau : liste des polices mise à jour.

## Alignement (grille unique)
- Une seule grille pour tout le corps : en-têtes, filets, texte et sommaire partagent les mêmes bords (82 pt à gauche, 513 pt à droite, mesurés dans le PDF).
- Suppression du retrait interne de 6 pt des cadres de texte (le texte était en retrait par rapport aux filets des titres).
- Sommaire recalé sur la même grille (il débordait de 13 pt de chaque côté).

## Pages de garde
- Pas de modèles de couverture multiples dans cette version : une seule couverture par pack. Centrage des titres vérifié (écart 0 pt).
