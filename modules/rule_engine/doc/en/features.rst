- **Moteur de règle :** Permet de créer des règles via un macro-language
  simplifié. Lors de l'exécution de la règle, les symboles utilisés seront
  remplacés par les données métier correspondantes.

- **Règles récursives :** Il est possible depuis une règle d'appeler une autre
  règle. Cela permet de mutualiser au maximum le paramétrage entre les
  différentes lignes métier, ou des différentes garanties.

- **Utilisation de tables :** Les tables sont un moyen concis de créer du
  paramétrage. Il est possible depuis une règle de rechercher le résultat d'une
  table à partir de paramètres arbitraires, et de manipuler / utiliser la
  valeur résultante dans l'algorithme de la règle.

- **Paramètres de règles :** Certaines règles sont très souvent utilisées.
  Typiquement, une règle d'éligibilité basée sur l'âge de l'assuré en
  prévoyance ou en santé. Il est possible de définir un paramètre sur la règle
  (ex : l'âge maximum), qui sera demandé à chaque fois que la règle sera
  paramétrée sur une garantie.

- **Jeux d'essai :** Les algorithmes complexes (la tarification par exemple)
  sont difficiles à mettre à jour. Il est facile de faire une erreur
  d'inattention qui fausserait les résultats. Il est donc possible de créer
  des jeux d'essais sur une règle, lesquels permettent de stocker une
  configuration d'entrée, ainsi que le résultat attendu. Suite à une
  modification, il suffit d'exécuter ces jeux d'essai pour s'assurer que les
  résultats sont ceux attendus.

- **Mode debug :** Afin de comprendre ce qui se passe lors de l'exécution des
  règles, un mode debug permet au paramétreur de visualiser les différentes
  exécutions de la règle, avec tous les paramètres associés. Il est également
  possible de générer des jeux d'essai à partir de ces exécutions.
  Concrètement, cela permet au paramétreur :

  - D'exécuter des cas réels (nouvelle souscription)

  - De comprendre pourquoi le résultat ne correspond pas à celui attendu
    (typo dans l'algorithme)

  - De corriger, puis de retester

  - Une fois le résultat correct, de générer des jeux d'essais, afin de
    s'assurer des non-régressions ultérieures.

- **Règles pré-paramétrées :** Les règles les plus courantes peuvent être
  fournies par défaut dans *Coog*.
