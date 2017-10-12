Installation des processus par défaut Coog
==========================================
Ce document a pour but de référencer et documenter les processus disponibles par défaut dans Coog.
En fonction des modules installés, ces derniers seront visibles dans l’arbre des points d’entrée de l’application 

*(Cf image ci-dessous)*

    .. image :: images/left_tree.png

Une liste de processus s'affiche en fonction des modules qui sont installés. 
Il suffit dès lors de cocher les processus voulus puis, cliquer sur "Import de processus" afin d'importer le paramétrage par défaut.

    .. image :: images/import_process.png

Vous pouvez accéder au(x) processus importé(s) via le point d'entrée "Moteur de Processus" > "Processus".

    .. image :: images/acces_aux_process.png

Voici un tableau des processus par défaut disponible avec les modules requis associés:
--------------------------------------------------------------------------------------
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Nom du processus                                              | Module(s) requis                                                                                                                     |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus standard de souscription de contract d'assurance    | contract_insurance_invoice, contract_insurance_process                                                                               |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus de souscripteur assurance emprunteur                | contract_loan_invoice, contract_insurance_process                                                                                    |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus d'analyse médicale                                  | underwriting_process                                                                                                                 |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus de souscription d'assurance collective              | contract_group_process, claim_process                                                                                                |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus de déclaration d'accident du travail                | claim_life_process, claim_salary_fr,claim_group_process, underwriting_claim, process_rule, claim_eligibility                         |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus de déclaration d'invalidité                         | claim_life_process, claim_salary_fr,claim_group_process, underwriting_claim, process_rule, claim_eligibility                         |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus de déclaration de décès                             | claim_life_process, claim_eckert, claim_salary_fr,claim_group_process, underwriting_claim, process_rule, claim_eligibility           |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus de déclaration de décès suite à un arrêt de travail | claim_life_process, claim_eckert, claim_salary_fr,claim_group_process, underwriting_claim, process_rule, claim_eligibility           |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Processus de déclaration d'une rechûte                        | claim_life_process, claim_salary_fr,claim_group_process, underwriting_claim, process_rule, claim_eligibility                         |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Suite - Nouvelle période                                      | claim_life_process, claim_salary_fr,claim_group_process, underwriting_claim, process_rule, claim_eligibility                         |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| Passage en invalidité                                         | claim_life_process, claim_salary_fr,claim_group_process, underwriting_claim, process_rule, claim_eligibility                         |
+---------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------+
