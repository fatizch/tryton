Batch de création des bordereaux de commissions [``commission.invoice.create``]
===============================================================================

Description :
-------------
Pour tous les courtiers ou les assureurs qui ont des commissions payables avant
la date de traitement, un bordereau sera généré avec un statut brouillon.


Dépendances :
-------------
Suppose que les quittances du mois précédent ont été payées (le batch de validation des paiements [account.payment.acknowlege] doit avoir tourné).

Fréquence :
-----------
A lancer dans le plan batch faisant suite au dernier jour ouvré du mois à la fréquence de paiement des commissions.


Paramètres d'entrée :
---------------------
- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
   Dernier jour du mois précédent

- ``agent_type (agent, principal)`` [obligatoire]
   ``agent`` : seul les bordereaux courtiers seront générés

   ``principal`` : seul les bordereaux assureurs seront générés. Ne pas utiliser cette option si le module commission_insurer est installé.

Filtres :
---------
Va chercher toutes les commissions :

- dont l'origine a été réputée payée à une date inférieure ou égale à la date de traitement
- non encore rattachées à un bordereau de commission
- dont le type (agent_type) correspond au paramètre d'entrée.

Parallélisation:
----------------
Supportée

Exemple :
---------
``coog batch exec commission.invoice.create 2 --agent_type=agent --treatment_date=YYYY-MM-31``



Batch d'émission des bordereaux de commissions [``commission.invoice.post``]
============================================================================


Description :
-------------
Fait passer tous les bordereaux du statut *Validé* au statut *Emis* et créé les lignes de
mouvements comptables correspondantes.

Dépendances :
-------------
A lancer après et dans la foulée du batch de création des bordereaux de commissions [commission.invoice.create]

Fréquence :
-----------
La même que le batch de création des bordereaux de commissions [commission.invoice.create]

Paramètres d'entrée :
---------------------

- ``agent_type (agent, principal)`` [obligatoire]
   ``agent`` : seul les bordereaux courtiers seront émis

   ``principal`` : seuls les bordereaux assureurs seront émis. Ne pas utiliser cette option si le module commission_insurer est installé.

- ``with_draft (True, False)``
   Si cette option est passée, le batch prendra également les bordereaux qui sont à l'état *Brouillon*

Filtres :
---------
Va chercher tous les bordereaux dont :

- le statut est à l'état *Validé* (et *Brouillon* si l'option with_draft est activée)
- dont le type (agent_type) correspond au paramètre d'entrée

Parallélisation:
----------------
Non supportée

Exemple :
---------
``coog batch exec commission.invoice.post 1 --agent_type=agent --with_draft=True``
