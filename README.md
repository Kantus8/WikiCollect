# Wikidex

Jeu de cartes encyclopédiques local : React + TypeScript, API FastAPI, base relationnelle SQLAlchemy/SQLite. PostgreSQL et conteneurs sont prévus pour un déploiement ultérieur.

## Jouer

Double-cliquer sur **`Lancer Wikidex.cmd`**, puis ouvrir **http://localhost:8000**. Le lanceur démarre le serveur en arrière-plan et ouvre le navigateur. **`Arreter Wikidex.cmd`** arrête uniquement le serveur lancé par ce projet. La collection est conservée.

Python **3.11+** et Node.js **22.12+** sont requis à l’installation. Les dépendances et l’interface compilée sont déjà installées dans ce workspace. Après un clone, le lanceur les installe automatiquement ; une connexion Internet est nécessaire pour cette première installation. Les images et les polices distantes ont des remplacements locaux quand le réseau est indisponible.

Le serveur écoute uniquement l’interface locale. Utiliser toujours le même hôte (`localhost`) et le même navigateur pour retrouver la partie : le cookie HttpOnly identifie le joueur. Effacer ce cookie crée une nouvelle partie ; l’ancienne reste en base. Exporter régulièrement la collection depuis **Préférences & sauvegarde**.

## Ce qui est livré

- Boutique : boosters de 4 cartes, révélation individuelle ou groupée, taux exacts affichés.
- Classeur : recherche, filtre de rareté, détails et lien vers chaque article.
- Arbres : macro-ensemble → set parent → carte mère → branches → pages terminales ; inconnues masquées aussi dans les réponses API.
- Bourse : vente unitaire/en bloc, choix parmi les portails vérifiés, tickets et packs ciblés.
- Journal, son facultatif, interface mobile et navigation clavier.
- 21 tables relationnelles avec contraintes, index, inventaire, transactions, récompenses uniques, historique de statistiques et reprise d’ingestion.
- Import unique de l’ancien prototype, export JSON, sauvegarde cohérente de la base SQLite.

## Règles conservées

| Règle | Valeur |
|---|---|
| Curiosité passive | **1,0/s**, sans multiplicateur ni clicker, y compris hors ligne |
| Booster standard | **300**, **4 cartes**, une nouvelle dépense finançable toutes les **5 min** |
| Plafond de réserve | **3 000**, également pour ventes et récompenses |
| Commune / Rare / Épique / Légendaire / Mythique | **55 / 28 / 12 / 4,5 / 0,5 %** par carte |
| Valeur d’un doublon | **30 / 75 / 150 / 300 / 600** |
| Bonus de branche | **150** base + **400** complète, chacun une seule fois |
| Ticket Portail | **1 doublon → 1 ticket → 1 carte** du portail, sans coût Curiosité |
| Départ | **600** Curiosité + **1** ticket Physique |

La complétion complète exige les pages larges **et** les pages précises. Les récompenses sont rattrapées à l’obtention de la mère ; aucune étape de son arbre n’est signalée avant cela. Un pack est débité et ses cartes sont sauvegardées dans la même transaction avant l’animation. Rejouer la même requête avec sa clé d’idempotence ne dépense rien de plus.

La rareté est calculée à partir d’un score logarithmique de langues et de vues, avec classement déterministe du catalogue. Les parts de cartes par rareté sont distinctes des probabilités de tirage. Un booster standard est refusé sans débit si une rareté manque. Les packs portail renormalisent les poids uniquement parmi les raretés présentes dans leur portail ; leurs taux spécifiques sont affichés.

## État des données

Le jeu démarre avec **34 cartes, 3 arbres, 7 branches**. Quatre références abrégées de la DDHC ont été remplacées par des pages individuelles consultables : voir [les corrections du catalogue](docs/CATALOGUE.md).

**Le catalogue est synchronisé et vérifié : 34/34 pages, 0 échec** (synchronisation du 16 septembre 2026, statistiques du mois civil complet 2026-08, politique de classement `log-rank-v1`). Le rapport durable est conservé dans `data/ingestion-report.json`. Les raretés sont calculées sur des vues réelles et se répartissent en 16 communes, 10 rares, 5 épiques, 2 légendaires et 1 mythique. **74 portails réels et 217 associations carte–portail** sont validés : conversion en tickets et ouverture de portails sont donc opérationnelles. L’avertissement de statistiques provisoires disparaît de l’interface dès que toutes les pages sont vérifiées.

Un seul avertissement subsiste : l’image de la *Déclaration des droits de l’homme et du citoyen de 1789* est masquée, ses métadonnées d’attribution étant incomplètes. C’est le comportement attendu — aucune image n’est affichée sans auteur ni licence.

Les tests, eux, continuent d’utiliser des réponses Wikimedia simulées : ils valident le pipeline, ils ne constituent pas une validation live du catalogue.

### Resynchroniser

Wikimedia **exige un User-Agent portant un contact identifiable** ; sans lui, son edge répond HTTP 403 (politique robots) avant même d’atteindre l’API — c’est la cause du blocage rencontré lors des premières livraisons, et non une restriction d’adresse IP. Renseigner `WIKIMEDIA_USER_AGENT` dans `.env` (voir `.env.example`) avec une URL de projet ou une adresse réelle. Le pipeline traite redirections, langues, portails, statistiques du dernier mois civil complet, attribution des images, reprises, délais et erreurs. Il n’installe aucune tâche système automatiquement.

```powershell
.venv\Scripts\python.exe scripts/import_catalogue.py sync --report data/ingestion-report.json
# Mise à jour autonome tant que ce processus reste lancé :
.venv\Scripts\python.exe scripts/import_catalogue.py worker --interval 86400
```

[Documentation détaillée de l’ingestion](docs/INGESTION.md).

Pour ajouter de nouvelles pages et de nouveaux arbres, importer un manifeste avec `scripts/load_catalogue.py nouvel-ensemble.json`, puis synchroniser. Les nouveaux articles sont exclus des boosters tant que Wikipédia ne les a pas validés. Un arbre déjà en jeu n’est jamais réécrit silencieusement.

## Développer et tester

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix frontend

# API (terminal 1)
.venv\Scripts\python.exe -m uvicorn backend.wikidex.api:app --reload --host 127.0.0.1 --port 8000
# Interface avec proxy /api (terminal 2)
npm run dev --prefix frontend

# Vérifications
.venv\Scripts\python.exe -m pytest backend/tests -q
npm run build --prefix frontend
```

La documentation HTTP se trouve sur **http://localhost:8000/docs**. En version compilée, FastAPI sert `frontend/dist` et l’API sur la même origine. Après une modification frontend, reconstruire ; après une modification Python, relancer le serveur. `--reload` le fait automatiquement en développement.

## Sauvegarder

```powershell
.venv\Scripts\python.exe scripts/backup.py
```

Ce script utilise l’API de sauvegarde SQLite et prend en compte le journal WAL. Les copies horodatées vont dans `data/backups`. Pour restaurer une copie complète, arrêter le serveur et tout worker, sauvegarder les fichiers actuels, puis restaurer la copie en tant que `data/wikidex.sqlite3` sans anciens fichiers `-wal`/`-shm`. Le JSON de collection s’importe sur une partie vierge ; il ne constitue pas une sauvegarde intégrale des sessions/journaux.

## Déploiement ultérieur

Copier `.env.example` vers `.env`, adapter `DATABASE_URL`, les hôtes et les origines. Le lanceur et le worker chargent `.env` ; une commande uvicorn manuelle doit recevoir `--env-file .env`.

Une composition PostgreSQL est fournie : définir `POSTGRES_PASSWORD` dans `.env` puis `docker compose up --build -d`. Le port publié reste local. Le worker optionnel se lance avec `docker compose --profile sync up -d ingestion`. Docker/PostgreSQL sont préparés, **pas validés en exécution dans cette livraison**.

Avant exposition publique : HTTPS derrière un reverse proxy, `COOKIE_SECURE=1`, origines/hôtes exacts, `ENABLE_LEGACY_IMPORT=0`, comptes et récupération de session, limitation de débit, stratégie de migrations et supervision. Le serveur local utilise des sessions anonymes persistantes ; il ne prétend pas offrir une gestion de comptes multi-appareils.

[Architecture et schéma relationnel](docs/ARCHITECTURE.md) · [Ingestion et provenance](docs/INGESTION.md) · [Vérifications](docs/VALIDATION.md).

## Organisation

```text
frontend/src/components/   Cartes, modales, ouverture et audio
frontend/src/pages/        Boutique, classeur, arbres, bourse, journal
frontend/src/api.ts        Requêtes et reprise avec même clé d’idempotence
backend/wikidex/models.py  Schéma relationnel
backend/wikidex/db.py      Initialisation et catalogue versionné
backend/wikidex/game.py    Règles et transactions de jeu
backend/wikidex/api.py     Sessions, validation et routes HTTP
backend/wikidex/ingestion.py  Client Wikimedia et reprise durable
backend/wikidex/popularity.py Score et classement déterministe
backend/tests/            Régressions de gameplay et ingestion
data/catalogue.json       Catalogue éditorial de départ
scripts/                  Lancement, arrêt, ingestion, sauvegarde
```

Les textes encyclopédiques sont liés à leur article source et attribués à Wikipédia sous CC BY-SA. Les images conservent leur propre licence ; l’ingestion fournit auteur, licence et page du fichier, ou masque une image dont l’attribution manque.
