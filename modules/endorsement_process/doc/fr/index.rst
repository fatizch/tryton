Avenant - Souscription
======================

TODO
Ce module permet de définir des processus sur des avenants.
Il ajoute les principales fonctionnalités suivantes, utilisables
dans des processus.

Boutons:
--------

- Prévisualisation des changements

  .. code:: xml

        <button name="button_preview_changes"/>

  Ce bouton, utilisé dans la vue d'une étape, permet de lancer
  l'assitant de prévisualisation des changements.

Méthodes:
---------

- Génération des documents

  .. code:: python

      generate_and_attach_reports_in_endorsement

  Cette méthode permet de générer et d'attacher des documents sur les
  contrats de l'avenant. Les paramètres doivent être définis ainsi:


  .. code:: python

      [['modele1', 'modele2']]

  Où modele1 et modele2 sont des codes de modèles de lettre.

Champs:
-------

- Avenants Unitaires

  .. code:: xml

    <field name="endorsement_parts_union"/>

  Dans la vue d'une étape, ce champ affiche une liste d'avenants unitaires,
  avec un bouton qui permet d'afficher le masque de saisie correspondant.

- Pièces jointes

  .. code:: xml

     <field name="attachments"/>

  Ce champ permet d'afficher tous les documents qui sont attachés à l'avenant.

- Documents créés

  .. code:: xml

     <field name="created_attachments"/>

  Ce champ permet d'afficher tous les documents qui ont été générés par
  l'avenant.

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
