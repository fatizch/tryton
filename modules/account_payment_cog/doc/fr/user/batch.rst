Batch de création de paiements [``account.payment.create``]
===========================================================

Description :
-------------

Crée des paiements au statut *Approuvé* à partir de lignes de mouvements comptables.

Dépendances :
-------------
A lancer après le batch d'émission des quittances [``contract.invoice.post``]

Fréquence :
-----------
Quotidienne pour étaler la charge de création de paiement sur chaque jour du mois.

A minima pour chaque génération de bande de virement/prélèvement.

Paramètres d'entrée :
---------------------
- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de paiement (dans le cas du prélèvement SEPA, c'est la date du prochain prélèvement par exemple le 5 du mois).

- ``payment_kind (payable, receivable)``
    Sens des paiements à créer (virement ou prélèvement par exemple). Si non renseigné, va générer les paiements entrants et sortants.

Filtres :
---------

Sélection des lignes de mouvements satisfaisant :

- date de paiement antérieure à la date de traitement
- aucun paiement non échoué associé
- aucun mouvement de réconciliation associé
- [Si module ``account_payment_sepa_cog`` installé : mandat SEPA valide de configuré pour les prélèvements utilisant le mode de traitement SEPA]

Parallélisation:
----------------
Supportée

Exemple :
---------
``coog batch exec account.payment.create 2 --treatment_date=YYYY-MM-05 --payment_kind=receivable``


Batch de traitement de paiements [``account.payment.process``]
==============================================================
Description :
-------------
Passe les paiements du statut *Approuvé* au statut *Traitement*, génère les groupes de paiement et les fichiers de prélèvements/virement SEPA éventuels à transmettre à la banque.

Dépendances :
-------------
A lancer après le batch de création des paiements [``account.payment.create``]

Fréquence :
-----------
A chaque génération de fichier de paiement.

Paramètres d'entrée :
---------------------

- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de paiement (dans le cas du prélèvement SEPA, c'est la date du prochain prélèvement par exemple le 5 du mois).
- ``payment_kind (payable, receivable)`` [obligatoire]
   Sens des paiements à traiter (entrant ou sortant par exemple).
- ``journal_methods (sepa,manual)``
   Méthodes de traitement des journaux pour les paiements à traiter, séparés par des virgules sans espace. Si non renseigné, traite tous les journaux.


Filtres :
---------
Sélection de tous les paiements dont :

- le type de paiement correspond au paramètre
- la date est <= à la date de traitement
- le statut est à l'état *Approuvé*
- associé à un journal de paiement dont le code de la méthode de traitement est dans la liste des paramètres

Parallélisation:
----------------
Non supportée

Exemple :
---------
``coog batch exec account.payment.process 1 --payment_kind=receivable --treatment_date=YYYY-MM-05 --journal_methods=sepa,manual``


Batch de validation des paiements [``account.payment.acknowledge``]
===================================================================
Description :
-------------
Passe le statut des paiements de *Traité* à *Validé* et les groupes de paiement à l'état *Fait*.

Si le module account_payment_clearing est installé, ce batch permet également de lettrer les quittances avec les paiements associés.

Ce batch automatise la tâche d'aller manuellement sur les groupes de paiement et de lancer l'action d'*Accuser réception*

Dépendances :
-------------
A lancer après le batch de traitement des paiements, soit dans la foulée, soit après constatation sur le compte bancaire de l'encaissement/décaissement du groupe de paiement.

Fréquence :
-----------
Postérieurement à chaque génération de bande de virement/prélèvement.

Paramètres d'entrée :
---------------------

- ``payment_kind (payable, receivable)`` [obligatoire]
   Sens des paiements à valider (entrant ou sortant par exemple).
- ``journal_methods (sepa,manual)``
   Méthode de traitement des journaux pour les paiements à traiter, séparés par des virgules sans espace. Si non renseigné, traite tous les journaux.

ou

- ``group_reference``
    Permet de spécifier l'identifiant précis d'un groupe de paiement (prioritaire sur les autres filtres).


Filtres :
---------

Sélection de tous les paiements :

- dont le type de paiement correspond au paramètre
- dont le statut est à l'état *Traitement*
- associé à un journal de paiement dont le code de la méthode de traitement est dans la liste des paramètres

ou

- rattachés au groupe de paiement dont l'identifiant est celui passé en paramètre.

Parallélisation:
----------------
Supportée

Exemple :
---------

``coog batch exec account.payment.acknowledge 2 --payment_kind=receivable --journal_methods=sepa,manual``
