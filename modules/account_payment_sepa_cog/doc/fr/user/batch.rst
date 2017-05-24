Batch de traitement des rejets [account.payment.fail]
=======================================================

Ce batch créé un message SEPA, y associe le message de rejet et traite les paiements
pour chaque fichier dans le répértoire spécifié en entrée.

- *Fréquence suggérée:* quotidienne
- *in*: Argument spécifiant le dossier d'entrée comportant les fichiers de rejet.
- *out*: Argument spécifiant le dossier de sortie qui comportera les fichiers de rejet
  traités.

**Les deux arguments in et out sont necessaires au batch pour fonctionner**


Batch de mise à jour des journaux de paiements SEPA  [``account.payment.journal.update.sepa``]
==============================================================================================

Description :
-------------

Mise à jour de la date de la dernière génération des prélèvements SEPA

Dépendances :
-------------
A lancer après le batch de traitements des groupes de paiements [``account.payment.group.process``]

Fréquence :
-----------
Pour chaque génération de bande de virement/prélèvement.

Paramètres d'entrée :
---------------------
 - Aucun

Parallélisation:
----------------
Non supportée

Exemple :
---------
``coog batch exec account.payment.journal.update.sepa 1``
