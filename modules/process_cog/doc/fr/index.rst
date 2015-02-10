Module Processus Paramétrés Coog [process_cog]
==============================================

TODO
Ce module permet d'améliorer les processus paramétrés en ajoutant les
fonctionnalités suivantes :

 * Possibilité de définir un processus basique par simple ajout d'étapes (les
   étapes du processus seront placées les unes à la suite des autres dans le
   flux de travail du processus)
 * Possibilité d'afficher des boutons ``Précédent`` et ``Suivant`` pour
   faciliter la navigation
 * Possibilité de définir un domaine sur un état, qui empêche d'avancer dans le
   processus tant que les conditions définies dans ce domaine ne sont pas
   remplies. Cela permet de définir "simplement" des contraintes sur le
   workflow.

Résumé
------

.. include:: summary.rst

Fonctionnalités
---------------

.. include:: features.rst

.. toctree::
    :hidden:

    summary.rst
    features.rst
