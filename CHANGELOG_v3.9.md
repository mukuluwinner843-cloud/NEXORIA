# NEXORIA service v3.9

## Cause corrigée : erreur 422 « aucun titre détecté » sur un texte bien écrit
- Un titre collé à la ligne suivante (sans ligne vide) était fondu dans le paragraphe : le moteur ne le voyait pas.
- Nouveau module nexoria_structure.py : reconnaît les titres explicites (INTRODUCTION, CONCLUSION, I. …,
  BIBLIOGRAPHIE), les titres en capitales, et les titres déduits du contexte (courts, sans ponctuation
  finale, suivis d'un paragraphe). Numérote les titres sans chiffre romain. Garde les lignes de tableau.
- Les titres déduits sont listés à part pour vérification. Les libellés d'interface (« SOMMAIRE »,
  « VÉRIFIER LE DOCUMENT », etc.) ne sont jamais pris pour des titres.
- Appliqué à la génération (core.py), à l'extraction (extract.py) et à la nouvelle route POST /structure.

## Panneau
- Analyse du texte par le service pendant la saisie : titres détectés, avis, bouton « Appliquer la mise en forme ».
- Repli local si le service est injoignable.

## Service
- Version 3.9 (/health, en-tête X-Service-Version).
- Route POST /structure : ne modifie aucun mot, seulement la mise en forme des titres et paragraphes.

## Limites
- Titres en phrase (« Les nouveaux métiers ») : non déduits, pour éviter les faux titres. Les mettre en capitales.
- Tableaux aplatis dans un PDF source : à corriger dans le document d'origine.
