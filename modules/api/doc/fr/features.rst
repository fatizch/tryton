- **APIs métier** : Par opposition aux APIs techniques existantes dans Tryton,
  les APIs métier ont pour objet de proposer une interface stable, indépendante
  du modèle technique de la base de données. Il s'agit principalement de
  définir une façon d'écrire des APIs, prévoyant dès le départ la gestion des
  problématiques d'extensibilité liées à la modularité
- **Droits d'accès** : Les APIs métier disposent de droits d'accès séparés des
  APIs techniques. Concrètement, elles seront systématiquement exécutées avec
  des droits illimités, il est donc important de s'assurer de qui y a accès
- **Erreurs structurées** : Dans une optique de communication avec d'autres
  systèmes, ces APIs ont beson de retourner des informations structurées plutôt
  qu'un texte simple en cas d'erreur. Les outils fourni permettent de
  centraliser la façon dont sont gérées les erreurs, et notamment de
  transformer des erreurs textuelles en erreur structurées
- **Validation des entrées / sorties** : Afin de disposer d'APIs robustes, il
  est indispensable de pouvoir décrire les entrées / sorties attendues. Pour ce
  faire, la gestion des JSON Schema est directement intégrée dans la
  description des APIs. Les paramètres doivent systématiquement valider un
  schéma (obligatoire), et les développeurs doivent s'assurer que les valeurs
  de retour sont cohérentes par rapport au schéma de sortie (qui sera
  communiqué aux développeurs utilisant ces APIs)
- **Auto description** : Chaque API métier est accompagnée d'une API la
  décrivant, permettant à n'importe quel système / développeur de connaître le
  fonctionnement attendu de l'API (entrées / sorties)
