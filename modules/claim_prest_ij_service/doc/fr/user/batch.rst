Batch de création des fiches IJ [``prest_ij.subscription.create``]
==================================================================

Description :
-------------

Crée les fiches Prest'IJ pour tous les tiers ayant un contrat collectif dont une 
garantie porte sur une prestation qui requiert la gestion du service "Prest'Ij" 

Dépendances :
-------------

Aucune

Fréquence :
-----------

Quotidienne pour étaler la charge de création des fiches pour les tiers et 
s'assurer d'une déclaration rapide auprès du service "Prest Ij"

Paramètres d'entrée :
---------------------

- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de traitement du batch
- ``kind (person, company)`` [obligatoire]
    Type de fiches à créer

Filtres :
---------

[Type company]

Sélection des tiers dont :

- Il est souscripteur d'un contrat collectif
- Le contrat collectif doit avoir une garantie portant sur une prestation 
  collective nécessitant la gestion du service "Prest Ij"
- Aucune fiche ne doit déja être présente sur ce tiers

[Type person]

Sélection des tiers dont :

- Il est assuré dans un dossier de prestation
- La prestation délivrée doit porter sur une prestation collective nécessitant 
  la gestion du service "Prest Ij"
- Aucune fiche ne doit déja être présente sur ce tiers

Parallélisation :
-----------------

Supportée

Exemple (Depuis coog-admin) :
-----------------------------
``./coog batch prest_ij.subscription.create --treatment_date=$(date --iso) 
--kind=[person/company]``


Batch de création de demande de déclaration ou de suppression [``prest_ij.subscription.submit_company``]
========================================================================================================

Description :
-------------

[opération cre] :
Crée les demandes de création IJ pour toutes les entitées légales possédant une 
fiche IJ à l'état "non déclaré".

[opération sup] : 
Crée les demandes de suppression IJ pour toutes les entitées légales possédant 
une fiche IJ à l'état "déclaration confirmée" avec un contrat résilié depuis 
plus de deux ans.   

Dépendances :
-------------

Aucune

Fréquence :
-----------

Quotidienne pour étaler la charge de création des demandes pour et s'assurer 
d'un traitement rapide des demandes auprès du service "Prest Ij"

Paramètres d'entrée :
---------------------

- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de traitement du batch
- ``operation (cre, sup)`` [obligatoire]
    Type d'opération des demandes à créer auprès du service "Prest Ij"

Filtres :
---------

Sélection de tous les paiements dont :

[opération cre] :

- Le tiers possédant une fiche à l'état "non déclaré" 
- Le tiers n'ayant aucune demande de déclaration en cours (à l'état 
  "non-traité")

[opération sup] :

- Le tiers possédant une fiche à l'état "déclaration confirmée"
- Le tiers n'ayant aucune demande de suppression en cours (à l'état 
  "non-traité")
- Le tiers souscripteur d'un contrat résilié depuis plus de deux ans

Parallélisation :
-----------------

Supportée

Exemple (Depuis coog-admin) :
-----------------------------

[opération cre] :

``./coog batch prest_ij.subscription.submit_company --treatment_date=YYYY-MM-DD 
--operation=cre``

[opération sup] :

``./coog batch prest_ij.subscription.submit_company --treatment_date=YYYY-MM-DD 
--operation=sup``


Batch de création de demande de déclaration ou de suppression [``prest_ij.subscription.submit_person``]
=======================================================================================================

Description :
-------------

[opération cre] :

Crée les demandes de création IJ pour tous les tiers physiques possédant une 
fiche IJ à l'état "non déclaré".   

[opération sup] :

Crée les demandes de suppression IJ pour tous les tiers physiques possédant une 
fiche IJ à l'état "déclaration confirmée" dont le dossier de prestation est 
fermé depuis plus de deux mois.   

Dépendances :
-------------

Aucune

Fréquence :
-----------

Quotidienne pour étaler la charge de création des demandes pour et s'assurer 
d'un traitement rapide des demandes auprès du service "Prest Ij"

Paramètres d'entrée :
---------------------

- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de traitement du batch
- ``operation (cre, sup)`` [obligatoire]
    Type d'opération des demandes à créer auprès du service "Prest Ij"

Filtres :
---------

Sélection de tous les paiements dont :

[opération cre] :

- Le tiers possédant une fiche à l'état "non déclaré" 
- Le tiers n'ayant aucune demande de déclaration en cours (à l'état 
  "non-traité")

[opération sup] : 

- Le tiers possédant une fiche à l'état "déclaration confirmée" 
- Le tiers n'ayant aucune demande de suppression en cours (à l'état 
  "non-traité")
- Le tiers est couvert sur un dossier de prestation qui est clôt depuis plus de 
  deux moins

Parallélisation :
-----------------

Supportée

Exemple (Depuis coog-admin) :
-----------------------------

[opération cre] :

``./coog batch prest_ij.subscription.submit_person --treatment_date=YYYY-MM-DD 
--operation=cre``

[opération sup] :

``./coog batch prest_ij.subscription.submit_person --treatment_date=YYYY-MM-DD 
--operation=sup``



Batch de traitement des demandes [``prest_ij.subscription.process``]
====================================================================

Description :
-------------

Traite les demandes de déclaration et de suppression, génère le flux qui sera 
transmit au service "Prest Ij".

Le fichier sera déposé dans le répertoire définit dans la configuration du 
batch, ou bien en paramètre passé à ce dernier.

Dépendances :
-------------

Aucune

Fréquence :
-----------

Quotidienne pour étaler la charge de traitement des demandes pour et s'assurer 
d'un traitement rapide des demandes auprès du service "Prest Ij"

Paramètres d'entrée :
---------------------

- ``treatment_date``
   Date de traitement du batch
- ``output_dir``
   Répetoire de sortie du flux

Filtres :
---------

Sélection de toutes les demandes :

- dont le statut est "non-traité"

Parallélisation :
-----------------

Supportée

Exemple (Depuis coog-admin) :
-----------------------------

``./coog batch prest_ij.subscription.process --treatment_date=$(date --iso) 
--output_dir=/chemin/absolu/vers/le/répetoire/de/sortie/``


Batch d'intégration des retours du service "Prest Ij" (gestip) [``gestip.flux.process``]
========================================================================================

Description :
-------------

Récupère toutes les archives présentes dans le répetoire donné au batch, puis 
intègre les données dans coog.

Dépendances :
-------------

Aucune

Fréquence :
-----------
Quotidienne pour étaler la charge de traitement des retours pour et s'assurer 
d'une intégration rapide dans coog des retours du service. 

Paramètres d'entrée :
---------------------

- ``treatment_date``
    Date de traitement  du batch
- ``directory``
    Chemin absolu vers le répertoire ou se trouvent les archives à intégrer
- ``kind``
    Type de fichier à traiter dans le répetoire (Retour "arl" ou "cr")

Filtres :
---------

Aucun

Parallélisation :
-----------------

Supportée

Exemple :
---------

[Type arl]:
``coog batch gestip.flux.process --treatment_date=$(date --iso) 
--directory=/chemin/absolu/vers/repertoire/intégration/ --kind='arl'``
[Type cr]:
``coog batch gestip.flux.process --treatment_date=$(date --iso) 
--directory=/chemin/absolu/vers/repertoire/intégration/ --kind='cr'``


Batch d'intégration des bordereaux de prestation "BPIJ" [``pres_ij.periods.batch``]
===================================================================================

Description :
-------------

Récupère toutes les archives présentes dans le répertoire de données du batch,
puis les intègre dans Coog.

Dépendances :
-------------

Aucune

Fréquence :
-----------

Quotidienne pour étaler la charge de traitement des retours pour et s'assurer
d'un traitement rapide des prestations.

Paramètres d'entrée :
---------------------

- ``directory``
    Chemin absolu vers le répertoire ou se trouvent les archives à intégrer

Filtres :
---------

Aucun

Parallélisation :
-----------------

Non supportée

Exemple :
---------

``coog batch prest_ij.periods.batch --directory=/chemin/absolu/vers/repertoire/intégration/``
