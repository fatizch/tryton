- **Paramétrage des frais :** Possibilité de définir des frais dans
  l'application. Ces frais sont rattachés à des produits (et éventuellement
  sur d'autres entités, réseau de distribution, apporteurs d'affaires...),
  et éventuellement dérogeables (selon le paramétrage) au niveau des contrats.

- **Paramétrage des règles de tarification :** Les produits / garanties peuvent
  avoir une liste de règles de tarification. Ces règles sont constituées de :

  - Une règle de calcul

  - Une fréquence de calcul. Cette fréquence indique quelle est l'unité de
    retournée par la règle. Par exemple, si la règle retourne "10" et que la
    fréquence est "Annuel", le tarif résultant est "10 € annuellement".

  - L'élément servant de base à la tarification. Dans ce module, les niveaux
    possibles sont "Contrat" et "Option". La règle sera calculée pour chaque
    élément correspondant sur le contrat en cours de tarification.

  A noter qu'il peut y avoir plusieurs règles, qui seront alors toutes
  évaluées en fonction du contexte.

- **Paramétrage des taxes :** A côté des règles de tarification, il est
  possible de spécifier les taxes qui s'appliquent sur le résultat des calculs
  de ces règles.

- **Premium date configuration :** List of dates for premium calculation. The contract start date is used by default but other dates could be added :
    * annually at the contract anniversary
    * annually at a custom date (January 1st for example)
    * with a relative duration from the contract start date (1 month after the contract start date for a free month for example)

- **Calcul des primes sur le contrat :** Le fait de recalculer le contrat
  déclenche un recalcul des primes du contrat. Ces primes sont les sorties
  brutes des règles de tarification, et sont utilisées dans le module
  **contract_insurance_invoice** pour générer les quittances du contrat.

- **Visualisation des primes :** Il est possible depuis le contrat de
  visualiser les primes calculées si le contrat est actif.
