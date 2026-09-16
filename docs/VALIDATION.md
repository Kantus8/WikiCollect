# Vérification de la livraison

Vérification effectuée sur Windows, Python 3.14.3 et Node.js 24.14.0.

## Automatisation

`python -m pytest backend/tests -q` : **50 tests réussis** au dernier passage (voir l’incident d’environnement en fin de document).

- Taux exacts : les 10 000 valeurs de la roulette de rareté sont parcourues ; résultat 5 500/2 800/1 200/450/50.
- +1/s fractionnaire, cinq minutes exactes pour 300, plafond et recul d’horloge.
- Transactions et rollback lors d’une panne après débit ; requêtes concurrentes et clé d’idempotence.
- Vente unitaire/globale, dernier exemplaire conservé, crédits réels sous plafond.
- Tickets vrais portails, rejet de conversion invalide, absence de fallback hors portail.
- Brouillard des arbres et des feuilles, titres et métadonnées absents côté API.
- Deux paliers uniques, feuilles précises obtenues avant base, déblocage tardif de mère, doublons intra-pack correctement identifiés.
- Import borné, unique, local ; alias préservés après redirection.
- Pagination Wikimedia, validation d’article/portail, snapshots, reprise, collisions, erreurs HTTP et calcul déterministe de rareté.
- Extension du catalogue : imports répétables, cartes nouvelles désactivées avant vérification, refus de feuilles inconnues, dupliquées ou identiques à la mère.

Deux avertissements de dépréciation proviennent du TestClient Starlette et d’AnyIO ; aucun test en échec. Les tests utilisent des bases temporaires distinctes de la collection locale.

`npm run build --prefix frontend` : **compilation TypeScript stricte et build Vite réussis**.

## Navigateur réel

Parcours manuels contrôlés avec les outils du navigateur :

- Boutique, taux et réserve ; achat de quatre cartes et révélation.
- Collection conservée après fermeture et rechargement ; recherche « Saturne ».
- Vente d’un doublon rare : +75 Curiosité, exemplaire original conservé.
- Trois arbres masqués sans mère : aucun titre de carte mère révélé.
- Fiche article, texte de provenance et lien Wikipédia.
- Classeur à **390 × 844**, navigation mobile sans débordement horizontal visible.
- Sur base QA isolée, import d’un JSON contenant `lastUpdate` et `selectedOrganigram` ; champs legacy correctement filtrés.
- Import d’Einstein et de ses cinq feuilles d’origine : base et complète reconnues, crédit total de 550, macro-ensemble et set parent affichés ; autres feuilles `???` et autres arbres masqués.

Le lanceur Windows et l’arrêt ont été exécutés avec succès, puis le serveur a été relancé. La sauvegarde SQLite a produit une copie cohérente horodatée via l’API de backup.

## Synchronisation Wikimedia

Effectuée le **16 septembre 2026** (rapport : `data/ingestion-report.json`).

- **34/34 pages traitées, 0 échec**, statistiques du mois civil complet **2026-08**, politique `log-rank-v1`.
- **74 portails réels** validés et **217 associations carte–portail** enregistrées ; tickets et packs portail sont donc alimentés par des données vérifiées.
- Raretés issues des vues réelles : 16 communes, 10 rares, 5 épiques, 2 légendaires, 1 mythique.
- Attribution des images contrôlée par sondage (Saturne : NASA / JPL / Space Science Institute, domaine public).
- Un avertissement, conforme aux règles : l’image de la *Déclaration des droits de l’homme et du citoyen de 1789* est masquée faute de métadonnées d’attribution complètes.

Les échecs HTTP 403 des livraisons précédentes venaient du User-Agent par défaut, dépourvu de contact identifiable : l’edge Wikimedia (HAProxy) rejetait la requête avant l’API. Vérifié par comparaison directe — un User-Agent portant une URL de contact obtient 200 sur `fr.wikipedia.org/w/api.php` comme sur l’API pageviews, là où un User-Agent de navigateur générique reste refusé. Ce n’était pas un blocage d’adresse IP. Le rapport de l’échec initial reste conservé dans `data/ingestion-live-report.json`.

## Limites observées

- Les tests du pipeline utilisent des réponses simulées, et les tests des transactions utilisent SQLite. Il n’existe pas de validation live automatisée du catalogue ni des images distantes.
- La configuration Docker/PostgreSQL est fournie mais n’a pas été lancée ici. Pas de test de charge ni de prétention à une capacité de production mesurée.

## Incident d’environnement

Sur ce poste, `pytest backend/tests -q` a d’abord échoué avec **37 erreurs de setup** : `PermissionError [WinError 5]` sur `%TEMP%\pytest-of-Kantus`, dossier résiduel devenu illisible pour son propre compte — la lecture de sa liste de contrôle d’accès était elle-même refusée. Aucun rapport avec le code : seuls passaient les 13 tests n’ayant besoin d’aucun fichier temporaire. Après suppression du dossier depuis une console administrateur, pytest l’a recréé proprement et la suite repasse en entier. Contournement sans élévation, si le cas se reproduit : `PYTEST_DEBUG_TEMPROOT` pointé vers un dossier accessible, ou `--basetemp`.
