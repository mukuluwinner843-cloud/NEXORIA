# NEXORIA — Service de mise en page (Phase 1)

Ce dossier contient le moteur NEXORIA (Packs Standard et Excellence) emballé en
service web, prêt à être appelé depuis n8n à chaque nouvelle commande.

Tu n'as rien à coder. Ce guide te dit exactement où cliquer.

---

## 1. Ce que fait ce service

Tu lui envoies un texte brut + les informations de l'élève, il te renvoie le PDF fini.

- `POST /generate` — génère le PDF (Standard ou Excellence)
- `GET /health` — juste pour vérifier que le service est en ligne

Il ne gère pas encore : le Pack Premium (TFC/mémoires), le logo propre à chaque
école, ni le paiement. Ce sont les étapes suivantes.

---

## 2. Héberger le service (aucune ligne de commande compliquée)

Recommandation : **Railway** (railway.app) — simple, un plan gratuit suffisant
pour démarrer, puis quelques dollars/mois. Alternative équivalente : **Render**
(render.com).

Étapes avec Railway :

1. Crée un compte sur railway.app (connexion possible avec GitHub).
2. Mets ce dossier (`nexoria_service`) dans un dépôt GitHub :
   - Crée un compte GitHub si tu n'en as pas (github.com).
   - Crée un nouveau dépôt, par exemple `nexoria-service` — le plus fiable
     depuis un téléphone : va directement sur **github.com/new**.
   - Sur la page du dépôt créé, ouvre **github.com/TON-NOM-UTILISATEUR/nexoria-service/upload/main**
     (remplace par ton propre nom d'utilisateur), ou cherche le lien
     « uploading an existing file ».
   - Tous les fichiers de ce dossier sont volontairement à plat (aucun
     sous-dossier) : depuis ton téléphone, sélectionne-les tous en une seule
     fois dans le sélecteur de fichiers et envoie-les.
   - Clique **« Commit changes »**.
3. Sur Railway : "New Project" → "Deploy from GitHub repo" → choisis
   `nexoria-service`. Railway détecte le `Dockerfile` automatiquement et
   construit le service.
4. Dans l'onglet "Variables" du projet Railway, ajoute :
   - `NEXORIA_API_KEY` = une phrase secrète que tu inventes (ex :
     `nexoria-cle-secrete-2026-xyz`). C'est ce qui empêche n'importe qui sur
     internet d'utiliser ton service à ta place.
5. Railway te donne une URL publique du type
   `https://nexoria-service-production.up.railway.app`. C'est cette URL que
   n8n appellera.

Budget : le plan gratuit Railway (« Trial »/« Hobby ») suffit largement pour
commencer (quelques dollars de crédit offerts, puis ~5 $/mois si tu dépasses).

---

## 3. Tester que ça marche (sans coder)

Une fois déployé, ouvre cette adresse dans ton navigateur :
`https://TON-URL.up.railway.app/health`
Tu dois voir : `{"status":"ok"}`

Pour tester `/generate`, le plus simple est d'utiliser un outil comme
[Postman](https://www.postman.com) (gratuit, sans code) :

- Méthode : `POST`
- URL : `https://TON-URL.up.railway.app/generate`
- En-tête : `X-API-Key` = la clé que tu as choisie à l'étape 2
- Corps (JSON) :

```json
{
  "pack": "excellence",
  "meta": {
    "etablissement": "Complexe Scolaire Francisco Palau",
    "eleve": "Grâce Emmanuel Mbuyi",
    "classe": "6e Scientifique",
    "matiere": "Physique",
    "titulaire": "M. Jonathan Ilunga",
    "theme": "Étude des fluides et de leurs applications dans la vie quotidienne",
    "annee": "2026-2027",
    "date": "12 octobre 2026"
  },
  "corps_texte": "INTRODUCTION\n\nTexte de l'introduction...\n\nI. PREMIER TITRE\n\nTexte...\n\nCONCLUSION\n\nTexte de conclusion."
}
```

La réponse est directement le fichier PDF.

---

## 4. Brancher n8n

Dans n8n, un nœud **HTTP Request** :
- Method: POST
- URL: ton URL Railway + `/generate`
- Headers: `X-API-Key: ta-clé`
- Body: JSON, construit à partir de ce que le site a reçu (nom, classe,
  matière, texte du devoir...)
- Response format: File (pour récupérer le PDF en binaire)

Ce fichier binaire peut ensuite être branché directement sur le nœud WhatsApp
de n8n pour l'envoi automatique.

---

## 5. Limites actuelles (honnêtes) — à traiter dans les prochaines étapes

- **Format du texte attendu** : le moteur repère les titres au format
  `INTRODUCTION`, `I. TITRE`, `II. TITRE`... `CONCLUSION`. Si le site envoie
  un texte structuré différemment (ex. extrait automatiquement d'un PDF/Word
  envoyé par l'élève), il faudra un petit traitement avant (soit dans n8n,
  soit un appel à l'API Claude pour restructurer le texte).
- **Pas de logo par école** : toutes les couvertures sont génériques
  (NEXORIA seul, sans blason). Ajouter le blason d'une école précise est une
  amélioration simple à faire ensuite (envoyer une image en plus dans la
  requête).
- **Pack Premium non branché** : le moteur Premium (TFC/mémoires) existe en
  démonstration mais n'est pas encore automatisable — il attend une vraie
  structure de document (chapitres, sections) plutôt qu'un texte brut simple.
- **Une commande à la fois par instance** : le service traite les requêtes
  qui arrivent en série sur un seul conteneur. Pour plusieurs commandes
  simultanées, Railway peut lancer plusieurs instances automatiquement
  (réglage "Replicas" dans les paramètres du service) — à activer quand le
  volume le justifiera, pas nécessaire au départ.
