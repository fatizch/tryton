Mise en demeure
===============

La *Mise en demeure* est à bien différencier de la *gestion des rejets de
prélèvement*. En effet, le paramétrage de ces rejets a pour objet de gérer le
fait que le mode de paiement ne fonctionne pas, et cherche donc principalement
à prévenir le gestionnaire et le client du problème.

A contrario, le processus de *Mise en demeure* cherche à adresser le fait qu'un
client n'a pas payé ses cotisations, et les impacts que cela peut avoir sur son
contrat et sa couverture. Il est indépendant de la notion de prélèvement dans
le sens où :

- Un contrat qui n'est pas prélevé mais payé par chèques peut être mis en
  demeure
- Un contrat en prélèvement qui n'a jamais eu de rejet peut être mis en demeure

Dans les faits, en général le processus de mise en demeure suivra rapidement un
rejet de prélèvement non traité.

Principe
--------

Le paramétrage des processus de mise en demeure permet beaucoup de flexibilité,
ce document correspondra à un exemple « classique » que l'on retrouve chez de
nombreux clients, et qui est proposé par défaut avec **Coog**.

La *Mise en demeure* de **Coog** se présente comme suit :

- Une quittance est considérée comme impayée à partir du moment où sa date de
  base (en général la date de prélèvement, cf infra pour les détails) est
  passée
- La quittance (et le contrat associé) vont passer par différentes étapes en
  fonction du paramétrage du processus de relance pour le produit associé
- Ce processus se conclut en général par la résiliation du contrat

Dans le cas où plusieurs quittances sont impayées sur un contrat donné, chacune
suit sont processus propre (autrement dit, chacune a un « compteur »
indépendant). Toutefois, seul le processus le plus avancé sera rattaché au
contrat.

Le processus de mise en demeure lié à une quittance est automatiquement terminé
dès lors que cette quittance est payée. Le contrat redevient alors « normal »,
sauf si au moins une autre quittance est toujours mise en demeure.

Date de base
------------

Dans **Coog**, par défaut, une quittance est réputée due à partir de sa date de
valeur (ou de la date du jour si elle est dans le passée). Concrètement, pour
une quittance commençant le 01/03, la date à laquelle le client est censé avoir
payé est :

- Le 01/03 si la quittance a été émise avant le 01/03
- La date d'émission si elle l'a été après

Dans le cas d'un fonctionnement par prélèvements automatiques, et en fonction
du paramétrage, cette date peut être décalée à la date de prélèvement attendue.
Par exemple, dans le cas précédent, si le contrat spécifie que les prélèvements
auront lieu le 5 du mois, la date sera le 5 du mois suivant l'émission de la
quittance.

À partir du moment où cette date est passée, le contrat apparaîtra *impayé*
dans **Coog**, et le statut de la mise en demeure sera visible lors de sa
consultation.

Cette date sert de date de base pour le processus de mise en demeure, dont les
étapes sont définies via un nombre de jours écoulés à partir de cette date de
base.

Relance
-------

En général une vingtaine de jours après le passage de la date de base, dans le
cas d'un contrat payé manuellement (i.e. pas par prélèvement), un courrier sera
généré et envoyé au client (courrier physique ou email, selon le paramétrage).

La raison pour laquelle ce comportement n'est en général pas appliqué aux
contrats prélevés automatiquement est qu'en cas de rejet de prélèvement on
souhaite en général ré-essayer au moins une fois automatiquement, ce qui en
général amène au-delà des 20 jours.

Mise en demeure
---------------

Déclenchée quarante jours après la date de base, il s'agit de l'envoi d'un
courrier ayant valeur légale, notifiant le client de sa *Mise en demeure*.

Cette étape a en générale une importance particulière, parce qu'elle définit la
nouvelle date de base pour les étapes suivantes. Concrètement, si pour une
raison quelconque elle est déclenchée quelques jours trop tard, les étapes
suivantes seront décalées d'autant, du fait de sa signification légale
particulière.

Suspension du contrat
---------------------

L'étape suivante, trente jours après la mise en demeure, consiste en la
suspension du contrat. Le processus par défaut de **Coog** ne prévoit pas
d'envoi de document à cette étape, mais cela peut facilement être ajouté par
paramétrage.

L'opération principale effectuée à ce moment est la suspension du contrat pour
le motif « Mis en demeure ». Cela va notamment suspendre le quittancement du
contrat, et le contrat apparaîtra dans des points d'entrée dédiés pour
faciliter la gestion.

En fonction des modules installés et du paramétrage, les garanties rattachées
au contrat sont suspendues, et ne donneront pas lieu au paiement de prestations
sur la période pendant laquelle le contrat est suspendu.

Résiliation du contrat
----------------------

En général dix jours plus tard, le contrat est résilié automatiquement par
**Coog**, pour le motif « Résiliation contentieuse ».

Il y a trois dates d'effet possibles pour la résiliation (à paramétrer) :

- À la date de d'effet de la relance, autrement dit dix jours (en fonction du
  paramétrage) après la suspension
- À la dernière quittance payée, l'assuré sera considéré comme non-couvert
  après la date de fin de la dernière quittance payée. Ce paramétrage laisse le
  contrat « propre », dans le sens où toutes les quittances correspondant à sa
  période de validité sont payées, le compte client est équilibré
- À la dernière quittance émise. Dans ce cas, le contrat sera résilié, mais les
  quittances non payées seront toujours dues, et le solde du contrat sera non
  nul. Cela permet de choisir une gestion comptable différente pour les
  quittances correspondant à la période d'impayés

Il y a un cas particulier pour les cas où le paramétrage spécifie la dernière
quittance payée, et où aucune quittance n'a été payée. Dans ce cas, le contrat
passe automatiquement en *Sans-effet*, **Coog** considère qu'il n'a jamais eu
d'effet étant donné qu'il n'a pas été « validé » par le paiement d'une
quittance par le client.
