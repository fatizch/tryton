Batch de création des quittances [``contract.invoice.create``]
==============================================================

Pour tous les contrats au statut "actif", crée les quittances dont la date de
début est inférieure ou égale à la date de traitement et leur donne le statut
"validé".

- *Fréquence suggérée:* quotidienne
- *Date de traitement à fournir:* date du jour


Batch de numérotation des quittances [``contract.invoice.set_number``]
======================================================================

Attribut un numéro à toutes les quittances validées dont la date de
début est inférieure ou égale à la date de traitement.

**Ce batch doit tourner avant le batch d'émission.**
**Ce batch doit avoir un job_size de 0.**

- *Fréquence suggérée:* quotidienne
- *Date de traitement à fournir:* date du jour


Batch d'émission des quittances [``contract.invoice.post``]
===========================================================

Fait passer toutes les quittances validées dont la date de début est
inférieure ou égale à la date de traitement au statut "émises" et crée
les lignes de mouvements correspondantes.

**Ce batch doit tourner après le batch de numérotation**

- *Fréquence suggérée:* quotidienne
- *Date de traitement à fournir:* date du jour


Batch de numérotation en masse des quittances [``contract.invoice.bulk_set_number``]
====================================================================================

Une alternative au batch de numérotation des quittances s'appuyant sur la base de donnée
pour améliorer les temps de traitement. Il attribut un numéro à toutes les quittances
validées dont la date de début est inférieure ou égale à la date de traitement.

**Ce batch doit tourner avant le batch d'émission**
**Ce batch doit avoir un job_size de 1.**
**Ce batch n'est pas parallélisable, un seul worker doit être lancé.**

- *Fréquence suggérée:* quotidienne
- *Date de traitement à fournir:* date du jour
