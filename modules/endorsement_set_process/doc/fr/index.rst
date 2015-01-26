Module endorsement_set_process
===============================

Ce module permet de définir des processus sur des ensembles d'avenants.
Il ajoute les principales fonctionnalités suivantes, utilisables
dans des processus.


Méthodes:
---------

- Génération des documents sur les contracts

  .. code:: python

      generate_and_attach_reports_on_contracts

  Cette méthode permet de générer et d'attacher des documents sur les
  contrats des avenants de l'ensemble. Les paramètres doivent être définis
  ainsi:

  .. code:: python

      [['modele1', 'modele2']]

  Où modele1 et modele2 sont des codes de modèles de lettre.


- Génération des documents sur l'ensemble de contrat

  .. code:: python

      generate_and_attach_reports_on_contract_set

  Cette méthode permet de générer et d'attacher des documents sur l'ensemble
  de contrats correspondant à l'ensemble d'avenants. Les paramètres doivent
  être définis ainsi:

  .. code:: python

      [['modele1', 'modele2']]

  Où modele1 et modele2 sont des codes de modèles de lettre.

Champs:
-------

- Avenants Unitaires

  .. code:: xml

    <field name="endorsements_parts_union" colspan="4" readonly="1"/>

  Dans la vue d'une étape, ce champ affiche une liste des avenants unitaires,
  composant les avenants de l'ensemble, avec un bouton qui permet d'afficher
  le masque de saisie correspondant.

- Pièces jointes

  .. code:: xml

     <field name="attachments"/>

  Ce champ permet d'afficher tous les documents qui sont attachés aux avenants
  de l'ensemble.

- Documents créés

  .. code:: xml

     <field name="created_attachments"/>

  Ce champ permet d'afficher tous les documents qui ont été générés par
  l'ensemble d'avenant (documents attachés à l'ensemble de contrat
  correspondant), et par les différents avenants (documents attachés aux
  contrats), au moment de l'application des avenants.
