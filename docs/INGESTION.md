# Catalogue Wikipédia et synchronisation

Le catalogue de départ reprend les pages du prototype. Ses nombres de langues, vues et associations de portails restent explicitement `prototype`, `verified=false` : ils ne sont pas présentés comme des mesures Wikipédia. Les arborescences restent des relations éditoriales distinctes des articles ; l’ingestion enrichit les vraies pages et ne transforme jamais une branche abstraite en carte.

## Utilisation locale

`WIKIMEDIA_USER_AGENT` doit porter un contact réel — URL de projet ou adresse — et jamais une identité fictive : la valeur est lue depuis `.env` (voir `.env.example`). Sans contact identifiable, l’edge Wikimedia refuse la requête, voir « Exigence de User-Agent » plus bas.

Depuis la racine du projet, après installation des dépendances :

```powershell
.venv\Scripts\python.exe scripts/import_catalogue.py sync --report data/ingestion-report.json
.venv\Scripts\python.exe scripts/import_catalogue.py sync --title 'Albert Einstein'
.venv\Scripts\python.exe scripts/import_catalogue.py status
.venv\Scripts\python.exe scripts/import_catalogue.py status --id 1
.venv\Scripts\python.exe scripts/import_catalogue.py sync --resume 1
```

`--month 2026-08` sélectionne un mois civil complet. Sans option, le mois précédent en UTC est utilisé, y compris au changement d’année. Les dates antérieures à juillet 2015 et les mois incomplets sont refusés. Une reprise conserve le mois et la sélection du travail original. `--title` sélectionne des cartes déjà présentes dans le catalogue relationnel ; ce n’est pas une recherche libre qui injecte des pages non contrôlées.

La commande retourne 0 après succès complet, 1 si des articles restent en échec ou en collision, 2 pour une configuration invalide et 130 après interruption clavier. Le rapport de chaque travail reste en base même sans fichier `--report`.

## Exécution automatique

### Étendre le catalogue

`scripts/load_catalogue.py chemin/vers/ensemble.json` ajoute un manifeste éditorial. Il suffit de fournir `cards: [{"title": "Marie Curie"}, ...]` et éventuellement `trees` au même format que `data/catalogue.json` (id, macro, parent_set, mother_title, branches avec id/title/description/base_pages/full_pages). Les titres déjà présents sont réutilisés. Les paramètres de statistiques, de portail et de vérification fournis dans ce fichier sont ignorés : **les nouvelles cartes sont désactivées jusqu’à une ingestion Wikimedia réussie**.

L’import est transactionnel et idempotent par empreinte du manifeste. Il rejette les références de feuilles absentes, les paliers vides ou chevauchants et une mère qui serait sa propre feuille. Réécrire un arbre existant est refusé : changer des objectifs déjà récompensés demande une migration éditoriale explicite. Cette commande permet d’ajouter des ensembles sans modifier le code ni réinitialiser les collections.

```powershell
.venv\Scripts\python.exe scripts/load_catalogue.py nouvel-ensemble.json
.venv\Scripts\python.exe scripts/import_catalogue.py sync
```

```powershell
.venv\Scripts\python.exe scripts/import_catalogue.py worker --interval 86400 --report data/ingestion-report.json
```

Ce processus effectue un travail immédiatement puis attend 24 heures après sa fin. Il reprend uniquement le dernier travail `running`, interrompu dans le même mois, qui couvre encore exactement le catalogue courant. Si une passe est terminée avec des erreurs, si de nouvelles cartes ont été ajoutées ou si un travail plus récent existe, il crée une nouvelle passe complète. Un ancien échec ou une collision permanente ne peut donc pas monopoliser les cycles ni empêcher l’actualisation des autres pages. La reprise manuelle `sync --resume ID` reste disponible pour réessayer uniquement les éléments inachevés du travail choisi. Il s’arrête avec Ctrl+C ; les articles déjà validés restent sauvegardés. `--max-runs 1` permet une seule exécution, utile pour vérifier l’intégration au Planificateur de tâches Windows. Une tâche planifiée ou cron peut simplement lancer la commande `sync` une fois par jour. Aucun service externe ni automatisation Codex n’est nécessaire, et le programme n’installe pas de tâche système à votre insu.

Un verrou système de fichier empêche deux commandes de synchronisation dans le même workspace. Il est libéré même après un arrêt brutal. En déploiement, conserver **un seul worker** pour la même base : le verrou local ne coordonne pas plusieurs machines. `DATABASE_URL` choisit SQLite par défaut ou PostgreSQL comme pour le serveur.

## Validation et provenance

1. L’API Action MediaWiki résout la normalisation et les redirections. Il faut un `pageid` positif, une page existante et l’espace principal `ns=0`. Une carte conserve son identifiant interne même si son titre canonique change.
2. Toutes les continuations `langlinks` et `categories` sont lues. `languages` représente le nombre de versions linguistiques distinctes, français inclus. Les interwikis génériques externes ne sont pas comptés comme des langues.
3. Les seuls candidats portails sont les catégories d’association `Catégorie:Portail:…/Articles liés`. Chaque candidat est ensuite validé comme vraie page de l’espace `ns=100`. Une catégorie thématique ordinaire n’est jamais convertie en portail. Les liens validés portent `CardPortal.verified=true`.
4. Les vues viennent de l’API officielle Wikimedia Pageviews, pour **Wikipédia francophone, tous les modes d’accès, lecteurs (`user`)**, au mois complet choisi. Ce ne sont pas les vues cumulées de toutes les langues. Les vues des anciens titres de redirection ne sont pas ajoutées à celles du titre canonique.
5. Extrait introductif en texte brut et miniature viennent de MediaWiki. `imageinfo` apporte page du fichier, auteur/attribution et licence ; en cas de métadonnées incomplètes, l’image est masquée et le rapport le signale. Le client affiche le texte comme texte, jamais comme HTML exécutable.

Un succès enregistre les données courantes et un `PopularitySnapshot` unique par carte/mois/source (`wikimedia:fr:all-access:user`). Relancer le même mois actualise ce snapshot ; un autre mois crée un historique. L’heure réelle de collecte est conservée. Le score du snapshot suit la politique versionnée du travail.

Une réponse HTTP en erreur ou un jeu de données mensuel absent **n’est pas transformé en zéro** : les dernières données restent intactes et l’article est marqué en échec dans le travail. Une page explicitement supprimée ou extérieure à l’espace des articles est désactivée ; ses inventaires, identifiants et références d’arbre restent conservés. Ses associations de portails sont retirées et elle ne participe plus aux tirages.

Deux titres qui convergent vers la même page canonique provoquent une collision `blocked`, avec l’identifiant de la carte existante dans le rapport. L’alias est désactivé ; aucune fusion de collections et récompenses n’est faite silencieusement. Une réconciliation éditoriale des références est alors nécessaire avant reprise. Un arbre contenant une page invalidée peut donc devenir impossible à terminer tant que son contenu n’est pas corrigé.

## Popularité et rareté

Politique publiée `log-rank-v1` dans `backend/wikidex/popularity.py` :

```text
score = 0,45 × ln(1 + langues) + 0,55 × ln(1 + vues_mensuelles)
```

Les cartes actives sont triées par score croissant, puis titre pour départager les égalités. La répartition du catalogue réserve une carte dans chacune des cinq raretés, puis distribue le reste selon les parts **50 / 30 / 14 / 5 / 1 %**, avec la méthode des plus grands restes. Cela conserve cinq groupes non vides dès que le catalogue possède au moins cinq cartes. Les cartes les plus populaires reçoivent les raretés les plus élevées. Moins de cinq cartes ne permet pas cinq groupes ; la boutique standard doit rester indisponible si une rareté manque.

Les **probabilités de booster sont séparées** de cette répartition de population : **55 / 28 / 12 / 4,5 / 0,5 %**. Aucune rareté n’est choisie aléatoirement lors de l’ingestion. La reclassification s’effectue à la fin d’un travail, et peut déplacer une carte si ses mesures ou la composition du catalogue changent. Les cartes encore non vérifiées conservent temporairement les valeurs de prototype dans ce classement et restent visiblement étiquetées comme telles.

Un ticket ne peut être obtenu depuis une association de portail non vérifiée. Un pack portail ne pioche que dans les cartes vérifiées, actives et associées à ce portail. S’il n’existe aucune carte éligible, il échoue sans consommer le ticket ; aucun repli sur le catalogue général n’est permis.

## Réseau, reprise et limites

Les requêtes HTTP sont séquentielles, limitées par défaut à une toutes les 0,5 seconde, avec délai réseau de 20 secondes et `maxlag=5`. Les erreurs transitoires (réseau, 429, 500/502/503/504, `maxlag`) ont trois nouvelles tentatives, attente exponentielle et respect de `Retry-After`. Un délai demandé supérieur à cinq minutes reporte l’article à une reprise ultérieure. Les erreurs définitives 4xx sont signalées immédiatement. Les portails sont vérifiés par groupes de 50 et mis en cache dans le processus.

Chaque article et son point de reprise sont validés dans la même transaction. Les éléments de travail vivent dans la table relationnelle `ingestion_items`, indexée par travail/état : chaque checkpoint met à jour une seule ligne et les compteurs du travail, sans réécrire une longue liste JSON. La lecture des éléments à traiter se fait par lots de 100. Le réseau est consulté en dehors des transactions de base de données. Un arrêt ne réclame donc pas de refaire les articles terminés. Les snapshots uniques rendent les reprises idempotentes. Les écritures de jeu restent transactionnelles indépendamment de l’ingestion.

Le catalogue, ses relations et son historique sont relationnels. Le travail reste volontairement un seul worker local ; le passage à des millions d’articles demande ingestion par lots depuis les dumps Wikimedia et une file de travail distribuée. L’API publique n’est pas destinée à répliquer Wikipédia par requêtes individuelles.

### Exigence de User-Agent

Le contact public du dépôt `https://github.com/Kantus8/WikiCollect` est désormais fourni par défaut dans le client, l’exemple d’environnement et Docker. `WIKIMEDIA_USER_AGENT` et `--user-agent` peuvent le remplacer. GitHub n’est pas un proxy de données : les endpoints restent ceux de Wikimedia. Le 17 septembre 2026, une nouvelle vérification avec ce défaut, sans écrire dans la base, a récupéré Albert Einstein (`pageid=7856`), les vues 2026-08 et ses 23 associations à des portails.

L’edge Wikimedia (HAProxy) refuse toute requête dont le User-Agent ne comporte pas de contact identifiable, et renvoie **HTTP 403** avec un message de politique robots — avant même que l’API soit atteinte. Le cas a été constaté puis levé ici :

- Le 16 septembre 2026, un premier essai sur **Albert Einstein** a reçu ce 403 avec l’en-tête par défaut, dépourvu de contact. Le travail n° 1 et `data/ingestion-live-report.json` conservent cet échec.
- Le même jour, avec un User-Agent portant l’URL du projet, `fr.wikipedia.org/w/api.php` et l’API pageviews répondent **200**, et la synchronisation complète a réussi : **34/34 pages, 0 échec**, rapport dans `data/ingestion-report.json`.

Ce n’est donc pas une restriction d’adresse IP : un User-Agent de navigateur générique, sans contact, reste lui aussi refusé. Les tests automatisés couvrent en complément pagination, redirections, validation, erreurs, collisions, invalidation et reprise.

## Documentation officielle utilisée

- [MediaWiki : propriétés et continuations](https://www.mediawiki.org/wiki/API:Properties).
- [MediaWiki : bonnes pratiques, User-Agent et requêtes séquentielles](https://www.mediawiki.org/wiki/API:Etiquette).
- [MediaWiki : maxlag et Retry-After](https://www.mediawiki.org/wiki/Manual:Maxlag_parameter).
- [Wikimedia Analytics : vues par page](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html).
- [MediaWiki : imageinfo](https://www.mediawiki.org/wiki/API:Imageinfo) et [métadonnées d’attribution](https://www.mediawiki.org/wiki/Extension:CommonsMetadata).
