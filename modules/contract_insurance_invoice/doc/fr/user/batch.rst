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

Batch de requittancement manuel de contrats [``contract.rebill.batch``]
=======================================================================

Ce batch est essentiellement destiné à la reprise de contrats suite à des
erreurs de gestion, des données incomplètes ou erronnées en entrée d'une
migration, ou d'une évolution rétroactive du paramétrage.

**Ce batch a un déclenchement manuel, et ne dépend pas d'autres batchs**

- *Fréquence suggérée* : quand nécessaire
- *Paramètres* :

  - *filepath* : le chemin vers le fichier csv contenant la liste des contrats
    à traiter, ainsi que les dates de début du requittancement. Le format
    attendu pour les dates est ``YYYY-mm-dd``. Ex :

    .. code-block::

        CTR000001;2020-04-10
        CTR000009;2019-06-25

  - *post* / *no-post* : permet de déclencher l'émission automatique (ou pas)
    des quittances concernées
  - *reconcile* / *no-reconcile* : dans le cas où l'émission automatique est
    activée, permet d'effectuer une réconciliation sur les contrats

:Attention: **Si le batch est lancé avec *post*, il n'est pas possible de le
            paralléliser. En cas de gros volumes, il est recommandé de lancer
            avec *no-post*, et de laisser passer le batch d'émission du plan
            batch pour émettre les quittances passées**
