Module Premium
==============

Ce module ajoute le nécessaire permettant de tarifer les produits / garanties
paramétrées. Il ajoute l'onglet "Données de tarification" sur ces entités. Cet
onglet permet de renseigner les éléments suivants :

 * Une liste de règles de tarification. Ces règles sont constituées de :

   - Une règle de calcul

   - Une fréquence de calcul. Cette fréquence indique quelle est l'unité de
     retournée par la règle. Par exemple, si la règle retourne "10" et que la
     fréquence est "Annuel", le tarif résultant est "10 € annuellement".

   - L'élément servant de base à la tarification. Dans ce module, les niveaux
     possibles sont "Contrat" et "Option". La règle sera calculée pour chaque
     élément correspondant sur le contrat en cours de tarification.

   A noter qu'il peut y avoir plusieurs règles, qui seront alors toutes
   évaluées en fonction du contexte.

 * Une liste de frais. Ces frais seront utilisés pour initialiser les frais au
   niveau du contrat. Ceux-ci serviront ensuite au calcul final.

 * Une liste de taxes à appliquer sur les montant calculés par les règles de
   tarification.

Il est également possible sur le contrat de calculer et stocker les
éléments de tarification dépendant du produit et des garanties soucrites. La
méthode de calcul des primes sur le contrat génère pour chaque élément assuré /
garantie sur le contrat les tarifs correspondant, tarifs qui sont par la suite
stockés dans des objets dediés.

Il est également possible de manipuler les frais renseignés sur les
garanties pour les appliquer au contrat courant. Ces frais sont librement
modifiables si leur configuration le permet. Les modifications sont prises en
compte lors du calcul des primes du contrat.
