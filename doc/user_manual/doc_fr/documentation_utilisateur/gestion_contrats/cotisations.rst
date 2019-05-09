Cotisations
===========

Ce document s'intéresse au comportement de **Coog** concernant le calcul, la
facturation, et le paiement des cotisations d'un contrat.

Calcul
------

Le calcul des tarifs est effectué lors de la souscription, puis lors de
certaines opérations lors de la vie du contrat. On parle de *Tarifs* dans le
sens où il ne s'agit pas des échéances du client (qui sont des *Cotisations*),
mais bien de tarifs théoriques rattachés aux différents éléments du contrat.

Concrètement, pour un contrat donné avec plusieurs risques assurés (personnes,
voitures, etc.), pour chaque garantie souscrite par un de ces risques
correspondra un *Tarif*, valide pendant une certaine période.

Dit autrement, un contrat souscrit le 01/01 aura un tarif (par exemple 100 €
par mois), qui évoluera suite à un avenant le 01/06 (il passera à 200 € par
mois).

Facturation
-----------

En général dès la souscription, puis régulièrement (en fonction des paramètres
de facturation choisis par l'assuré lors de la souscription), des *Quittances*
sont générés sur le contrat pour des périodes données.

Quittances
~~~~~~~~~~

Ces *Quittances* ont les caractéristiques suivantes :

- Elles *couvrent* une période (par exemple du 01/01 au 31/01). À l'exception
  des quittances de frais demandés dès la signature, ou de frais particuliers
  liés par exemple à une mise en demeure, toutes les quittances d'un contrat
  ont une date de début et une date de fin de couverture
- Il ne doit pas y avoir de « trous » dans les périodes. Autrement dit, il
  n'est pas normal (et **Coog** empêche) d'avoir une quittance allant du 01/01
  au 31/01, puis une autre du 01/03 au 31/03 sans rien entre les deux
- Les quittances dans **Coog** sont générées à l'état « Validé ». Elles ne sont
  pas modifiables manuellement mais ne sont pas comptabilisées
- Une quittance « Validée » peut ensuite être « Émise ». Une quittance émise
  génère des écritures comptables, et positionne la date de maturité sur la
  ligne comptable à payer du client. Autrement dit, c'est à partir de
  l'émission que l'on peut savoir quand on estime que le client est censé avoir
  payé la quittance
- Lors de la réception d'un paiement (chèque, prélèvement automatique, etc.),
  la quittance associée restera au statut « Émise » tant que le paiement n'aura
  pas été *réconcilié* avec la quittance. Cette opération est en général
  effectuée automatiquement par **Coog**, et ne nécessite une intervention
  manuelle que dans certains cas particuliers (réception d'un chèque
  antérieurement à la génération de la quittance, bascule d'un trop-perçu
  depuis un autre contrat, etc.). Une fois la réconciliation effectuée, la
  quittance passe à l'état « Payée », ce qui va potentiellement déclencher
  d'autres opérations (validation des commissions associées, etc.)

Il est important de noter qu'**une quittance n'est payée tant qu'elle est
réconciliée**. Autrement dit, la dé-réconciliation des lignes comptables
associées déclenchera systématiquement une rebascule vers l'état « Émise ».

Génération des quittances
~~~~~~~~~~~~~~~~~~~~~~~~~

La génération des quittances a lieu :

- En fonction du paramétrage, dès l'activation du contrat en fin de processus
- Automatiquement, par traitement batch, quelques jours précédent la fin de la
  dernière quittance générée sur un contrat donné (en fonction d'un
  paramétrage)
- Manuellement, via l'assistant « Génération des quittances » disponible sur le
  contrat

De même, l'émission des quittances peut avoir lieu :

- En fin de souscription
- Par les traitements batch, à la suite de la génération
- Manuellement, en déclenchant l'action « Émettre » disponible directement sur
  une quittance « Validée »

L'ensemble des quittances rattachées à un contrat peuvent être consultées via
la relation « Quittance » depuis un contrat.

Requittancement
~~~~~~~~~~~~~~~

En cas d'avenant, et en fonction de la nature de l'avenant, il est possible que
le contrat soit « Re-quittancé ». Au moment de l'application de l'avenant,
après le recalcul des *Tarifs* sur le contrat, toutes les quittances dont la
date de fin est postérieure à la date d'effet de l'avenant sont :

- Supprimées si elles étaient au statut « Validé »
- Annulées si elles étaient au statut « Émises »

Si des quittances étaient « Payées », elles sont avant toute chose
« dé-réconciliées », autrement dit l'argent qui servait à les payer est
« rendu » au client, ce qui déclenche un passage de la quittance à l'état
« Émise » afin qu'elles soient ensuite annulées.

Une fois ce nettoyage effectué, le contrat est re-quittancé pour prendre en
compte les modifications apportées par l'avenant. **Coog** va alors re-générer
toutes les quittances à partir de la denière quittance non-annulée (par exemple
pour un contrat avec un fractionnement mensuel, un avenant au 15/01 déclenchera
un re-quittancement à partir du 01/01) au statut « Validé ».

Les quittances dont la date de début est antérieure à la date du jour seront
alors « Émises », et l'argent disponible sur le compte du client suite à la
dé-réconciliation éventuelle des quittances précédemment « Payées » sera
utilisé pour payer le maximum de ces nouvelles quittances.

Paiement
--------

Comme expliqué rapidement ci-dessus, une quittance n'est réellement payée qu'à
partir du moment où les lignes comptables « à payer » sur le compte du client
sont réconciliées avec les lignes comptables de *rentrées d'argent*
(prélèvement, chèques, etc.).

Pour les cas où la réconciliation n'est pas effectuée automatiquement par
**Coog** (suite à des opérations manuelles, où bien en cas d'argent
*disponible* sur le compte du client suite à des dé-réconciliations manuelles),
il est possible de la déclencher manuellement via l'action « Letter les
comptes » disponible sur le souscripteur du contrat. À partir du moment où une
ligne de quittance du contrat est réconciliée (par cet assistant ou par
quelqu'autre moyen que ce soit), la quittance passera à l'état « Payé », et les
opérations liées à ce changement de statut seront effectuées.
