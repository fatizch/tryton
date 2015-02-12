Ensemble de contrats
====================

TODO: deplacer texte dans summary.rst|features.rst|user/*.rst

Le module contract_set permet de définir un lien entre plusieurs contrats via
l'objet 'Ensemble de contrats'. L'objet 'Ensemble de contrat' contient un
identifiant unique.

Le module ajoute des données métiers au moteur de règles qui permettent
d'utiliser les informations des contrats liés :

- Numéro de la relation dans groupe de contrat (nom de la relation): cette
donnée regarde sur le contrat et les contrats liés la place de la personne
selon l'ordre de naissance du plus vieux au plus jeune et parmi les personnes
avec la même relation.
- Nombre de personnes couvertes avec la relation dans groupe de contrat
(nom de la relation): permet de connaître le nombre de personnes couvertes sur
l'ensemble des contrats liés avec la relation définie en paramètre.

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
