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


Batch de validation des paiements [``account.payment.succeed``]
===============================================================
Description :
-------------
Passe le statut des paiements de *Traitement* à *Réussi*.

Si le module account_payment_clearing est installé, ce batch permet également de lettrer les quittances avec les paiements associés.

Ce batch automatise la validation des paiements (passer à l'état réussi) des groupes de paiement dont le filtre s'applique.

Dépendances :
-------------
A lancer après le batch de traitement des paiements ou de traitement des groupes de paiements, soit dans la foulée, soit après constatation sur le compte bancaire de l'encaissement/décaissement du groupe de paiement.

Fréquence :
-----------
Postérieurement à chaque génération de bande de virement/prélèvement.

Paramètres d'entrée :
---------------------

- ``payment_kind (payable, receivable)`` [obligatoire]
   Sens des paiements à valider (entrant ou sortant par exemple).
- ``journal_methods (sepa,manual)``
   Méthode de traitement des journaux pour les paiements à traiter, séparés par des virgules sans espace. Si non renseigné, traite tous les journaux.
- ``treatment_date``
   Date de traitement utilisée pour sélectionner tous les paiements d'un groupe de paiement dont la date minimale de paiement est inférieure ou égale
- ``auto_acknowledge``
   Si ce paramètre est à 1, alors la selection des groupe de paiement incluera également ceux dans l'état "En traitement" au lieu de ne séléctionner uniquement ceux dont l'accusé réception est planifié.

ou

- ``group_reference``
    Permet de spécifier l'identifiant précis d'un groupe de paiement (prioritaire sur les autres filtres).

Filtres :
---------

Sélection de tous les paiements :

- dont le type de paiement correspond au paramètre
- dont le statut est à l'état *Traitement* ou *Accusé réception planifié* en fonction de auto_acknowledge
- associé à un journal de paiement dont le code de la méthode de traitement est dans la liste des paramètres
- dont la date minimale de paiement sur le groupe de paiement est inférieure ou égale à la date de traitement.

ou

- rattachés au groupe de paiement dont l'identifiant est celui passé en paramètre.

Parallélisation:
----------------
Supportée

Exemple :
---------

``coog batch exec account.payment.succeed 2 --payment_kind=receivable --journal_methods=sepa,manual --treatment_date=$(date --iso) --auto_acknowledge=1``



Batch d'accusé récéption des paiements [``account.payment.acknowledge``]
========================================================================
Description :
-------------
Passe le statut des paiements de *Traitement* à *Reçu* et les groupes de paiement à l'état *Reçu*.

Si le module account_payment_clearing est installé, ce batch permet également de lettrer les quittances avec les paiements associés.

Ce batch automatise l'action manuelle d'*Accuser réception* les groupes de paiements.

Dépendances :
-------------
A lancer après le batch de traitement de validation des paiements

Fréquence :
-----------
Postérieurement à chaque génération de bande de virement/prélèvement.

Paramètres d'entrée :
---------------------

- ``payment_kind (payable, receivable)`` [obligatoire]
   Sens des paiements à valider (entrant ou sortant par exemple).
- ``journal_methods (sepa,manual)``
   Méthode de traitement des journaux pour les paiements à traiter, séparés par des virgules sans espace. Si non renseigné, traite tous les journaux.
- ``treatment_date``
   Date de traitement utilisée pour sélectionner tous les paiements d'un groupe de paiement dont la date minimale de paiement est inférieure ou égale
- ``auto_acknowledge``
   Si ce paramètre est à 1, alors la selection des groupes de paiements incluera également ceux dans l'état "En traitement" au lieu de ne séléctionner uniquement ceux dont l'accusé réception est planifié.

ou

- ``group_reference``
    Permet de spécifier l'identifiant précis d'un groupe de paiement (prioritaire sur les autres filtres).

Filtres :
---------

Sélection de tous les paiements :

- dont le type de paiement correspond au paramètre
- dont le statut est à l'état *Traitement* ou *Accusé réception planifié* en fonction de auto_acknowledge
- associé à un journal de paiement dont le code de la méthode de traitement est dans la liste des paramètres
- dont la date minimale de paiement sur le groupe de paiement est inférieure ou égale à la date de traitement.

ou

- rattachés au groupe de paiement dont l'identifiant est celui passé en paramètre.

Parallélisation:
----------------
Supportée

Exemple :
---------

``coog batch exec account.payment.acknowledge 2 --payment_kind=receivable --journal_methods=sepa,manual --treatment_date=$(date --iso) --auto_acknowledge=1``


Batch de création des groupes de paiements [``account.payment.group.create``]
=============================================================================

Description :
-------------

Création des groupes de paiements prêts à être traités

Dépendances :
-------------
A lancer après le batch de création des paiements [``account.payment.create``]

Fréquence :
-----------
Pour chaque génération de bande de virement/prélèvement.

Paramètres d'entrée :
---------------------
- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de paiement (dans le cas du prélèvement SEPA, c'est la date du prochain prélèvement par exemple le 5 du mois).

- ``payment_kind (payable, receivable)`` [obligatoire]
    Sens des de paiements à traiter (virement ou prélèvement par exemple).

- ``journal_methods (sepa,manual)``
   Méthodes de traitement des journaux pour les paiements à traiter, séparés par des virgules sans espace. Si non renseigné, traite tous les journaux.

- ``job_size`` (fichier de configuration)
    Nombre de paiements maximum dans un groupe
    [Si module ``account_payment_sepa_cog`` installé : nombre maximum de mandats différents dans un groupe]

Filtres :
---------

Sélection de tous les paiements dont :

- le sens correspond au paramètre
- la date est <= à la date de traitement
- le statut est à l'état *Approuvé*
- associé à un journal de paiement dont le code de la méthode de traitement est dans la liste des paramètres
- non associé à un groupe

Parallélisation:
----------------
Supportée

Exemple :
---------
``coog batch exec account.payment.group.create 2 --treatment_date=YYYY-MM-05 --payment_kind=receivable --journal_methods=sepa,manual``


Batch de mise à jour des paiements avant traitement [``account.payment.update``]
================================================================================

Description :
-------------

Mise à jour des paiements avant leur traitement

Dépendances :
-------------
A lancer après le batch de création des groupes de paiements [``account.payment.group.create``]

Fréquence :
-----------
Pour chaque génération de bande de virement/prélèvement.

Paramètres d'entrée :
---------------------
- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de paiement (dans le cas du prélèvement SEPA, c'est la date du prochain prélèvement par exemple le 5 du mois).

- ``payment_kind (payable, receivable)`` [obligatoire]
    Sens des paiements à traiter (virement ou prélèvement par exemple).

- ``update_method (sepa, manual)`` [obligatoire]
   Méthode de traitement des journaux pour les paiements à traiter. Attention, une seule méthode est supportée par exécution de batch.

Filtres :
---------

Sélection des groupes dont les paiements répondent aux critères suivants :

- le sens correspond au paramètre
- la date est <= à la date de traitement
- le statut est à l'état *Approuvé*
- associé à un journal de paiement dont le code de la méthode de traitement correspond au paramétre ``update_method``

Parallélisation:
----------------
Supportée

Exemple :
---------
``coog batch exec account.payment.update 5 --treatment_date=YYYY-MM-05 --payment_kind=receivable --update_method=sepa``


Batch de traitement des groupes de paiements [``account.payment.group.process``]
================================================================================

Description :
-------------

Traitement des groupes de paiements

Dépendances :
-------------
A lancer après le batch de mise à jour des paiements [``account.payment.update``]

Fréquence :
-----------
Pour chaque génération de bande de virement/prélèvement.

Paramètres d'entrée :
---------------------
- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de paiement (dans le cas du prélèvement SEPA, c'est la date du prochain prélèvement par exemple le 5 du mois).

- ``payment_kind (payable, receivable)`` [obligatoire]
    Sens des paiements à traiter (virement ou prélèvement par exemple).

- ``journal_methods (sepa,manual)``
   Méthodes de traitement des journaux pour les paiements à traiter, séparés par des virgules sans espace. Si non renseigné, traite tous les journaux.

Filtres :
---------

Sélection des groupes dont les paiements répondent aux critères suivants :

- le sens correspond au paramètre
- la date est <= à la date de traitement
- le statut est à l'état *Approuvé*
- associé à un journal de paiement dont le code de la méthode de traitement est dans la liste des paramètres

Parallélisation:
----------------
Supportée

Exemple :
---------
``coog batch exec account.payment.group.process 2 --treatment_date=YYYY-MM-05 --payment_kind=receivable --journal_methods=sepa,manual``
