# Vérification de la livraison

Vérification effectuée sur Windows, Python 3.14.3 et Node.js 24.14.0.

## Automatisation

`python -m pytest backend/tests -q` : **50 tests réussis** au dernier passage.

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

## Limites observées

- La véritable requête d’ingestion d’Albert Einstein reçoit **HTTP 403 de Wikimedia**. Le rapport est conservé ; zéro carte est déclarée vérifiée à tort. Les portails restent protégés jusqu’à validation réelle. Il n’existe pas de validation live du catalogue ni des images distantes dans cette livraison.
- Les tests du pipeline utilisent des réponses simulées, et les tests des transactions utilisent SQLite.
- La configuration Docker/PostgreSQL est fournie mais n’a pas été lancée ici. Pas de test de charge ni de prétention à une capacité de production mesurée.
