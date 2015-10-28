Configuration
=============

Les fonctionnalités suivantes sont disponibles pour les processus.

Boutons
-------

- Prévisualisation des changements ::

  .. code:: xml

        <button name="button_preview_changes"/>

  Ce bouton, utilisé dans la vue d'une étape, permet de lancer
  l'assistant de prévisualisation des changements.

Champs
------

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
