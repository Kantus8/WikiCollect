# Corrections éditoriales du catalogue initial

Chaque carte représente une page individuelle, jamais une ligne synthétique « naissance », « découvertes » ou une branche. Les branches restent des relations éditoriales dans des tables séparées.

Les quatre intitulés abrégés du prototype n’apportaient pas une preuve de l’existence d’articles Wikipédia distincts pour ces numéros de la Déclaration. Ils sont remplacés par quatre pages dont le contenu a été consulté sur Wikipédia le 16 septembre 2026 :

| Ancien libellé importé | Page individuelle utilisée |
|---|---|
| Article 1er... | [Égalité devant la loi](https://fr.wikipedia.org/wiki/%C3%89galit%C3%A9_devant_la_loi) |
| Article 2... | [Droit naturel](https://fr.wikipedia.org/wiki/Droit_naturel) |
| Article 4... | [Liberté](https://fr.wikipedia.org/wiki/Libert%C3%A9) |
| Article 11... | [Liberté d’expression](https://fr.wikipedia.org/wiki/Libert%C3%A9_d%27expression) |

La branche devient « Droits fondamentaux & Libertés » : base = Liberté + Droit naturel ; complète = base + Égalité devant la loi + Liberté d’expression. Ces quatre cartes correspondent chacune à leur propre URL encyclopédique. Les anciens libellés restent des alias d’import. Une correction initiale conserve les identifiants des cartes déjà créées dans cette version de développement ; elle ne réécrit jamais une carte validée par l’API Wikimedia.

Les anciennes statistiques, extraits et portails des libellés abrégés ne leur ont **pas** été attribués : ces quatre cartes sont parties de langues/vues à zéro avec provenance `editorial-pending`, en attendant la collecte automatique — consulter une page ne remplace pas une collecte de métriques datées. La synchronisation du 16 septembre 2026 a depuis abouti : toutes quatre sont `verified`, avec des métriques réelles de provenance `wikimedia:fr:all-access:user` (Liberté 105 langues / 1 559 vues, Droit naturel 68 / 1 065, Liberté d’expression 99 / 1 021, Égalité devant la loi 45 / 294, sur le mois 2026-08).

Les autres valeurs du prototype avaient été conservées avec provenance `prototype`, sans les présenter comme récentes ou mesurées ; la même synchronisation les a toutes remplacées par des métriques mesurées, et les 34 cartes portent désormais la provenance `wikimedia:fr:all-access:user`. L’ingestion résout également les redirections, dont « E=mc2 », et conserve les anciens titres dans `card_aliases`. Le catalogue reste de 34 cartes, trois mères et sept branches.

Les macro-ensembles et sets parents sont des catégories de jeu éditoriales, pas des cartes ni des pages Wikipédia. Une carte peut appartenir à plusieurs ensembles, mais ses appartenances et ses branches enfants sont toujours stockées et affichées séparément.
