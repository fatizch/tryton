Utilisation des batches
=======================

Lister les batches disponibles
------------------------------

Utiliser un nom non existant pour forcer l'affichage du choix de noms, eg :

    .. code:: sh

        coop batch --name ???

Purger les workers en cours d'exécution
---------------------------------------

D'abord killer tous les processes celery puis utiliser la commande ``purge`` :

    .. code:: sh

        ps auxww | grep celery | awk '{print $2}' | xargs kill
        celery -A trytond.modules.coog_core.batch_launcher purge

.. _daemon:

Lancer celery en tant que un démon
----------------------------------

Différentes options :
http://celery.readthedocs.org/en/latest/tutorials/daemonizing.html#running-the-worker-as-a-daemon

La ligne de commande exacte pour ``celery multi`` étant :

    .. code:: sh

        celery multi start worker_coog --config=celeryconfig -A \
            trytond.modules.coog_core.batch_launcher --loglevel=INFO \
            --logfile=/my/path/worker_coog.log --pidfile=/my/path/celery-%n.pid

Consulter les logs batch
------------------------

Les logs sont accessibles dans le répertoire dont l'emplacement est déterminé
par l'attribut ``config_file`` (dans la section ``[batch]``) de *trytond.conf*.
Chaque batch logge ses données dans un fichier à son nom.
En parallèle, toutes les écritures des batches sont fusionnées dans le fichier
de log global donné en paramètre au lancement de celery (cf :ref:`daemon`).
