Conditions d'éligibilité [offered_eligibility]
=====================================================

TODO
But
~~~

Le module offered_eligibility ajoute la possibilité d'employer le moteur de
règles pour ajouter des conditions d'éligibilité à une garantie.

Règle par défaut
~~~~~~~~~~~~~~~~

La configuration par défaut ajoute une clause (définie dans le fichier
rule_template.xml) nommée Option Elgibility Rule qui fournit un algorithme pour
définir l'égilibilité d'une garantie en fonction de l'âge du prospect.

La règle permet de mesurer si l'âge du prospect (soit son âge réel, soit son
âge millésime par rapport à une date donnée, soit son âge à la fin du mois) est
bien inférieur à un âge maximal.

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
