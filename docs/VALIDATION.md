# Vérification de la livraison

Vérification effectuée sur Windows, Python 3.14.3 et Node.js 24.14.0.

## Automatisation

`python scripts/test.py` : **70 tests réussis** le 17 septembre 2026. Le lanceur utilise un répertoire temporaire neuf dans le projet pour éviter l’incident Windows décrit en fin de document.

- Taux exacts : les 10 000 valeurs de la roulette de rareté sont parcourues ; résultat 5 500/2 800/1 200/450/50.
- +1/s fractionnaire, cinq minutes exactes pour 300, plafond et recul d’horloge.
- Transactions et rollback lors d’une panne après débit ; requêtes concurrentes et clé d’idempotence.
- Vente unitaire/globale, dernier exemplaire conservé, crédits réels sous plafond.
- Tickets vrais portails, rejet de conversion invalide, absence de fallback hors portail.
- Brouillard des arbres et des feuilles, titres et métadonnées absents côté API.
- Deux paliers uniques, feuilles précises obtenues avant base, déblocage tardif de mère, doublons intra-pack correctement identifiés.
- Import borné, unique, local ; alias préservés après redirection.
- Sauvegarde JSON v2 : restauration du solde, des exemplaires, des tickets, du nombre de packs et des récompenses déjà attribuées, sans nouveau versement ; rollback des reçus invalides.
- Pagination Wikimedia, validation d’article/portail, snapshots, reprise, collisions, erreurs HTTP et calcul déterministe de rareté.
- Worker : reprise uniquement d’un import interrompu du mois courant couvrant le catalogue actuel ; un ancien échec ou un catalogue modifié déclenche un nouvel import complet.
- Extension du catalogue : imports répétables, cartes nouvelles désactivées avant vérification, refus de feuilles inconnues, dupliquées ou identiques à la mère.
- Extension livrée : 218 cartes, puis regroupement `editorial-regroup-v1` en 17 collections de 6 à 22 pages, 215 feuilles conservées, reçus des branches retirées archivés dans le journal et Curiosité déjà gagnée intacte.
- Métadonnées d’image Wikimedia mal formées traitées comme un avertissement récupérable, sans interrompre une synchronisation.

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

Le 17 septembre, contrôle dans le navigateur après compilation : boutique fonctionnelle, portail Physique disponible, 34/34 pages vérifiées et nouveaux libellés de restauration/export visibles. Aucun achat n’a été effectué dans la partie locale pendant ce contrôle.

## Synchronisation Wikimedia

Dernière synchronisation complète effectuée le **17 septembre 2026** (rapport : `data/ingestion-report.json`).

- **218/218 pages traitées, 0 échec**, statistiques du mois civil complet **2026-08**, politique `log-rank-v1`.
- **258 portails réels** validés et **1 632 associations carte–portail** enregistrées ; tickets et packs portail sont donc alimentés par des données vérifiées.
- Raretés issues des vues réelles : 107 communes, 65 rares, 31 épiques, 12 légendaires, 3 mythiques.
- Attribution des images contrôlée par sondage (Saturne : NASA / JPL / Space Science Institute, domaine public).
- Onze avertissements, conformes aux règles : les images sans attribution complète (ou aux métadonnées mal formées) sont masquées, tandis que leurs cartes restent actives.

Nouvelle requête réelle le **17 septembre 2026**, avec le User-Agent par défaut désormais configuré dans le code : *Albert Einstein*, page 7856, 236 langues, 36 274 vues pour août 2026 et 23 portails validés. Ce contrôle n’a pas modifié la base locale.

Un parcours API sur une copie isolée de la base synchronisée a également vérifié l’achat d’une carte du portail Physique contre un ticket, la conversion d’un doublon en ticket et une restauration JSON v2 sans perte du compteur de packs ni nouveau crédit de palier.

Les échecs HTTP 403 des livraisons précédentes venaient du User-Agent par défaut, dépourvu de contact identifiable : l’edge Wikimedia (HAProxy) rejetait la requête avant l’API. Vérifié par comparaison directe — un User-Agent portant une URL de contact obtient 200 sur `fr.wikipedia.org/w/api.php` comme sur l’API pageviews, là où un User-Agent de navigateur générique reste refusé. Ce n’était pas un blocage d’adresse IP. Le rapport de l’échec initial reste conservé dans `data/ingestion-live-report.json`.

## Limites observées

- Les tests du pipeline utilisent des réponses simulées, et les tests des transactions utilisent SQLite. Il n’existe pas de validation live automatisée du catalogue ni des images distantes.
- La configuration Docker/PostgreSQL est fournie mais n’a pas été lancée ici. Pas de test de charge ni de prétention à une capacité de production mesurée.

## Incident d’environnement

Sur ce poste, `pytest backend/tests -q` a d’abord échoué avec **37 erreurs de setup** : `PermissionError [WinError 5]` sur `%TEMP%\pytest-of-Kantus`, dossier résiduel devenu illisible pour son propre compte — la lecture de sa liste de contrôle d’accès était elle-même refusée. Aucun rapport avec le code : seuls passaient les 13 tests n’ayant besoin d’aucun fichier temporaire. Après suppression du dossier depuis une console administrateur, pytest l’avait recréé proprement. Le problème s’est reproduit le 17 septembre ; le lanceur `python scripts/test.py` l’évite sans élévation, sans suppression de dossiers existants et sans modification des permissions Windows.
