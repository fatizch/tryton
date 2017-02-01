Paramétrage des lancement automatique de batch
==============================================

Ce tutoriel explique les différentes étapes afin d'ajouter des taches
récurrentes lancées automatiquement depuis le "crontab".

Description
-----------

Le traitements de masse (Batchs) sont généralement des taches programmées pour
tourner la nuit de manière indépendante.
Ce tutoriel a pour but d'expliquer comment définir des taches récurrentes via
le crontab.

crontab
-------

Le crontab est un outil de plannification de taches qui permet d'éxecuter des actions
(commandes) de manière périodique ou ponctuelle.
Pour éditer les taches plannifiées, il suffit de lancer la commande suivante:

*crontab -e*

Ajout d'une tache
-----------------

Le crontab permet de plannifier des taches au lancement à la minute, l'heure, le jour du mois, au mois
ou au jour de la semaine.
Ainsi chaque ligne du crontab est de la forme suivante:
[0-59 minute] [0-23 heure] [jour du mois 1-31] [mois] [jour de la semaine 0-6] [commande]

Attention: le jour de la semaine 0 est un dimanche et le lundi comment à 1. Il est également possible de ne pas spécifier
une unité de temps en y mettant une "*".

Ainsi, si on souhaite éxécuter la chaîne de quittancement tous les dimanche à 01h00, il suffit d'ajouter la ligne suivante:

*0 1 * * 0 coog chain -- contract_insurance_invoice invoice --treatment_date=$(date --iso)*

En l'occurence si le traitement passe après minuit mais que l'on veuille lui passer la date de la veille il suffit d'écrire : $(date --iso -d "-1 days") soit 

*0 1 * * 0 coog chain -- contract_insurance_invoice invoice --treatment_date=$(date --iso -d "-1 days")*

Voici un autre exemple concernant la génération de la bande de prélèvement, tous les 15 du mois, 01h30:

*30 1 15 * * coog chain -- account_payment_sepa_cog payment --treatment_date=$(date --iso) --payment_kind=receivable --journal_methods=sepa --out=/chmemin/bande/prelevement*
