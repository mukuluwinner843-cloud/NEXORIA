# NEXORIA service v3.8

## Panneau de génération (panneau_generation.html) : refonte
- Interface sobre en une colonne, sections numérotées, mode sombre automatique.
- Barre d'action fixe en bas (« Mettre en file » / « Générer ») : utilisable au pouce sur téléphone.
- Analyse du texte avant génération : nombre de mots, titres reconnus, INTRODUCTION et CONCLUSION
  vérifiés, tableaux détectés (signal d'un tableau aplati).
- File d'attente sur l'appareil : sans connexion ou à la demande, le devoir est gardé en file et
  envoyé dès que la connexion revient (ou via « Envoyer la file »). La clé API n'est jamais stockée
  dans la file.
- La section « Connexion et clé » s'ouvre tout seul si la clé est absente.

## Extraction (extract.py)
- Nettoyage du texte avant analyse : caractères invisibles, espaces insécables, retours à la ligne.
- Diagnostics renvoyés avec chaque extraction (champ « diagnostic ») : INTRODUCTION / CONCLUSION absentes,
  peu de titres, tableaux détectés, texte très court.

## Service (app.py)
- Version unique : 3.8 (champ « version » dans /health, en-tête X-Service-Version).
- Limites d'entrée : texte 300 000 caractères maximum, champs de couverture bornés.
- Erreur interne : journalisée et renvoyée proprement (HTTP 500), le service ne tombe plus.

## Limites connues (inchangées)
- Tableaux aplatis dans un PDF source : à corriger dans le document d'origine (.docx).
- La génération du PDF reste côté serveur : le navigateur ne peut pas produire le PDF hors connexion.

## Fichiers à remplacer sur GitHub
- app.py, extract.py, panneau_generation.html, CHANGELOG_v3.8.md
