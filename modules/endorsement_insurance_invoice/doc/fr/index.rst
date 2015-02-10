Module endorsment_insurance_invoice
===================================

TODO
Le module endorsement_insurance_invoice permet d'intégrer les avenants avec la
tarification et le quittancement des contrats d'assurance. Il permet de marquer
certains avenants unitaires comme étant tarifants. Cela signifie que les
modifications effectuées par l'avenant sont potentiellement tarifantes,
autrement dit qu'elles modifient le tarif du contrat.

Le comportement de ce genre d'avenants diffère de celui des avenants normaux
comme suit :

 * L'application de l'avenant déclenchera un recalcul des tarifs sur le
   contrats à partir de la date d'effet
 * Ce recalcul sera suivi d'une suppression / annulation des quittances
   antérieures à ou incluant la date d'effet de l'avenant, en fonction de leur
   statut (les quittances en brouillon ou simplement validée seront supprimées,
   celles émises ou payées seront annulées, et la comptabilité sera mise à jour
   en fonction).
 * Les quittances seront ensuite recréées / émises pour prendre en compte les
   nouveaux tarifs.
 * Tout ces comportement seront répliqués en cas d'annulation de l'avenant.

Il est important de noter que les avenants tarifants forcent la génration
d'une quittance débutant à leur date d'effet.

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
