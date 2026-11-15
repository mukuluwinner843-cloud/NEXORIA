# NEXORIA — version 3.13 : mise en forme automatique

Principe : chaque règle est **typographique**. Aucune ne corrige l'orthographe, ne change un mot,
ne réécrit une phrase. Le fond de l'élève est intouché. Les corrections sont comptées (journal).

## Règles appliquées (les deux packs, tous les modèles)
Espaces
- espaces multiples réduits à une seule ;
- espaces en début et fin de ligne supprimés ;
- espace après une apostrophe (« l' analyse » -> « l'analyse », idem d', qu', n', s', j', c', m', t') ;
- espace parasite avant la virgule et le point supprimé.

Ponctuation française
- espace insécable avant ; ! ? et avant : (sauf heures et nombres : 10:30 et 3,5 restent intacts) ;
- espace ajoutée après , ; : quand elle manque (« mots,collés ») ;
- espace ajoutée après un point quand une phrase suivante commence sans espace ;
- parenthèses : pas d'espace collé à l'intérieur.

Guillemets et tirets
- guillemets droits "..." -> « ... » avec espaces insécables ;
- tiret entre espaces « - » -> tiret long « – » (tiret d'incise) ;
- trois points « ... » -> points de suspension « … ».

Répétitions
- mot grammatical répété (« le le », « de de », « et et »…) réduit à un seul.

Majuscules
- première lettre de chaque paragraphe en majuscule, y compris après un guillemet ou une parenthèse ;
  c'est la règle qui manquait dans certaines parties.

Lettrine (Excellence)
- la lettrine ne porte plus que la lettre : « L'analyse » ne produit plus un blanc entre « L' » et le mot ;
- pas de lettrine si le paragraphe commence par un guillemet, une parenthèse ou un chiffre (texte normal).

## Limites volontaires
- Pas de correction orthographique ni grammaticale : elle modifierait le fond.
- Pas d'ajout de point final : une phrase peut être incomplète dans le texte de l'élève, on la signale plutôt que de la modifier (à venir si tu le demandes).

## Technique
- Nouveau module `nexoria_mise_en_forme.py` (normaliser(texte) -> texte, journal), appelé dans `core._build`.
- `SERVICE_VERSION` = 3.13.
