- **Données complémentaires :** Chaque garantie, chaque produit est unique, et
  utilise des données différentes pour calculer les primes, les prestations,
  l'éligibilité, etc... Les données complémentaires permettent de définir
  ces données via paramétrage. Elles peuvent être ajoutées au niveau du
  contrat, des garanties, ou des descripteurs de risque, et leurs valeurs
  seront renseignées sur le contrat, les garanties souscrites, ou bien les
  éléments couverts.

- **Utilisation des données complémentaires dans les règles :** Les données
  complémentaires définies dans le paramétrage sont rendues disponibles dans
  le moteur de règle, et leur valeur peut alors être utilisée lors du calcul
  du tarif, de l'éligibilité, etc...

- **Descripteur de risque :** L'assurance porte toujours sur une entité
  assurée. Qu'il s'agisse d'un tiers (prévoyance, santé), d'une voiture, voire
  d'une centrale nucléaire, il faut pouvoir définir qu'est-ce qui est assuré.
  Les descripteur de risque permet de décrire cette information, et est utilisé
  comme base lors de la souscription pour la saisie des données de risque.

- **Gestion des exclusions :** Ajoute la possibilité sur les garanties de
  définir des règles d'exclusion : telle garantie ne peut pas être souscrite en
  même temps que telle autre.

- **Règle des montants de couverture possible :** Permet de configurer sur une
  garantie les différentes valeurs possibles du montant de couverture lors
  de la souscription. Ces règles peuvent être simples (une liste simple, voire
  un algorithme avec min / max / pas) ou bien le résultat d'un calcul via le
  moteur de règles.

- **Sélection de la famille de garantie :** Permet de marquer une garantie
  comme étant rattachée à une famille d'assurance (prévoyance, santé, etc...)

- **Lien avec l'assureur :** Permet de rattacher une garantie à un assureur

- **Sélection des processus :** Permet d'indiquer les processus (ajoutés par le
  module ``process``) rattachés au produit.
