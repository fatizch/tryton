Reprise Intégrale de Contrat
===================================

TODO
Ce module permet de déclencher une Reprise Intégrale de Contrat via le
processus d'avenant. Cet avenant particlier utilise l'état ``en cours`` des
avenants pour placer le contrat dans un état instable (``devis``), de sorte
qu'il puisse être librement modifié.

La modification est possible via l'utilisation d'un nouveau type de processus.
Lorsqu'il démarrera l'avenant, l'utilisateur déclenchera le lancement d'un
processus typé ``Reprise Intégrale de Contrat``. Durant ce processus, le bouton
``Annuler l'avenant en cours`` devra être disponible à tout instant (par
exemple en le mettant dans le champs ``xml_footer`` du processus). Ce bouton
permettra de remettre le contrat dans son état original, tel qu'il était avant
le démarrage de l'avenant.

Le processus doit également appeler la méthode
``apply_in_progress_endorsement`` en fin d'exécution afin de terminer
proprement l'avenant.

Comme pour tous les avenants utilisant l'état ``en cours``, aucun autre avenant
ne pourra être appliqué tant que celui-ci ne sera pas appliqué ou annulé.

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
