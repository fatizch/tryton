Batch de nettoyage de la base de données [ir.model.cleandb]
===========================================================

Le but de ce batch est de détecter les structures de données dans la base
qui ne sont plus utilisées.

Le fonctionnement natif de tryton fait que:

- on garde les colonnes des variables enlevées du modèle (éventuellement les
  contraintes qui y sont associées)
- on garde les tables des modèles effacés

Un but a été détecté sur le passage à Tryton 3.6 qui fait qu'on puisse avoir des
contraintes dupliquées sur la base de données (quand le nom dépasse une
certaine taille)

Paramètres du batch (kwargs):

- module: le module qu'on souhaite nettoyer
- drop_const: si vrai permet de générer un script de purge des contraintes
- drop_index: si vrai permet de générer un script de purge des indexes

Ces éléments sont régénérés sur l'update des modules

Le résultat est stocké dans le répertoire ir.model.cleandb créé dans le
répertoire de sortie des batch (config: batch: log_dir)

*Note importante*: ce batch ne fait que générer des scripts SQL. Il n'exécute
rien sur la base de données.

Fréquence d'utilisation: à la demande et suite au livraisons

Extraction d'un exemple de sortie:

.. code:: sql

    DROP TABLE "party_check_vies_no_result";
    DROP TABLE "party_check_vies_no_result_id_seq";
    DROP TABLE "party_check_vies_no_result__history__";
    DROP TABLE "party_check_vies_no_result__history___id_seq";
    DROP TABLE "res_team_add_user_select";
    DROP TABLE "res_team_add_user_select_id_seq";
    DROP TABLE "res_team_add_user_select__history__";
    DROP TABLE "res_team_add_user_select__history___id_seq";
    DROP TABLE "task_select_available_tasks_task";
    DROP TABLE "task_select_available_tasks_task_id_seq";
