- **Fonctionnalité d'export / import de données :** Cette fonctionnalité permet
  de faciliter les échanges de données entre différentes bases de données (cas
  d'utilisation typique : report de paramétrage entre base de recette et base
  de production). Elle sert également de base pour les formats d'échanges
  via web-services.

- **Export groupé :** Afin de faciliter la création d'exports consistants, il
  est possible de créer des ensembles de données à exporter, et de sauvegarder
  ces ensembles.

- **Encapsulation de jeux d'essais :** Ce module fournit les outils permettant
  de facilement créer des jeux d'essai à lancer sur des bases vierges pour
  ajouter les données de base (paramétrage comptable par défaut, banques,
  etc...).
  Cette fonctionnalité supporte la hiérarchisation des jeux d'essai, ainsi que
  la possibilité de détecter si un jeu d'essai doit être relancé ou ignoré.

- **Encapsulation des tests unitaires :** Il est possible en utilisant le
  framework de tests unitaires de ce module de définir des dépendances entre
  tests unitaires, ce qui permet de limiter les copier-coller entre les tests.

- **Erreurs fonctionnelles :** S'il y a 4 erreurs fonctionnelles sur un
  écran, il est plus intéressant d'afficher les 4 erreurs en une seule fois
  plutôt que de n'en voir qu'une, de la corriger, puis de voir les autres.

- **Labels :** Ajoute la possibilité de *marquer* les modèles, utile dans le
  paramétrage pour facilement filtrer et retrouver des données précises.

- **Evènements :** Outils permettant de gérer des notifications d'évènements
  dans le code afin de brancher certains actions si souhaité. Ces actions
  sont définies dans d'autres modules, et peuvent aller de la simple écriture
  de log à une notification d'un web-service extérieur. Chaque action sur
  des objets métiers peut être dotée d'un filtre (une expression Pyson) pour
  déterminer plus précisément quels objets doivent être traités.

- **Framework de batchs :** Ajout d'un framework de batchs, permettant de
  disposer d'une structure unifiée pour écrire / manipuler des batchs.
  Cette structure supporte la gestion des codes retours, des outils d'aide à
  l'écriture, la gestion du multiprocess (en utilisant celery), ainsi que
  du failover (relance des batchs en erreur, isolation des contrats /
  quittances problématiques).

- **Support de la connexion future / passée :** Associé à une modification du
  client, il est possible de se connecter dans le futur / passé, ce qui permet
  lors d'une recette typiquement de passer des traitements à des dates futures
  si nécessaire.

- **Outils de manipulation de date :** Mise à disposition des développeurs
  d'outils de manipulation de dates. Typiquement, calculs d'intervals,
  incrément / décrement d'une date, formatage, etc...

- **Outils de manipulation des chaînes de caractère :** Ajout de fonctions de
  manipulations de chaînes de caractères. Formatage, standardisation, etc...

- **Outils tryton :** Ajout de méthodes permettant de simplement évaluer des
  domaines, des expressions pyson, de manipuler des listes versionnées, etc...

- **Historisation manuelle** : Possibilité via l'interface de Coog de définir
  que certains modèles doivent être historisés. Une mise à jour des modules
  est nécessaire pour que la modification soit prise en compte. Quoi qu'il
  arrive, la dé-historisation d'un modèle ne supprimera pas la table associée
  afin d'éviter tout risque de perte de données accidentelle. En outre, les
  modèles dont l'historisation est "hardcodée" ne pourront être modifiés.

- **Détails configurables** : Ajout d'un Mixin permettant d'ajouter des détails
  configurables sur des modèles. Les détails sont paramétrés par modèle
  directement dans l'application.
