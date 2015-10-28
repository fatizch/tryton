Configuration
=============

Les fonctionnalités suivantes sont disponibles pour les processus:

Champs
------

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
