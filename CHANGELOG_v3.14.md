# NEXORIA v3.14 — candidat (à valider avant mise en production)

## Corrections
- Listes sans puces : chaque élément « Titre : texte » devient une puce, y compris après le premier (Standard « - », Excellence « ◆ »).
- Sous-titres « 1.1 », « 1.2 »… : rendus en gras sur leur propre ligne, avec espace avant.
- Encadré « Repère… » : rendu dans un cadre à fond clair (Standard et Excellence).
- Paragraphes : une fin de phrase suivie d'une nouvelle phrase ouvre un nouveau paragraphe (plus de fusion dans le flux).
- Titres : un titre « I. », « 1.1 », « INTRODUCTION » ou « CONCLUSION » ne se fusionne plus avec le paragraphe qui suit.

## Contrôle
- `tests/controle_integrite.py TEXTE.txt` : génère les deux packs et vérifie 1) que chaque ligne source est présente dans le PDF, 2) que le code affiché et le code de l'URL sont identiques.

## Limites connues
- Un seul texte de test à ce jour : à rejouer sur un jeu d'au moins 20 textes (tableaux, accents, titres longs, citations) avant la production.
- Les lettres autour de l'écusson viennent de l'image du logo : elles ne sont pas corrigées par le moteur.
- Le texte produit n'est pas modifié sur le fond ; seules la mise en forme et la structure changent.
- Les codes générés en local ne sont vérifiables publiquement que s'ils sont enregistrés dans le registre de production.
