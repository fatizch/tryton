Configuration celery et celeryd
===============================

`Celery`_ est le système utilisé par l'outil ``coop batch`` pour faire des traitements de batches distribués.

.. _Celery: http://celery.readthedocs.org/en/latest/

Installation
------------

Procéder comme suit ::

    pip install Celery
    apt-get install rabbitmq-server

Si pb d'host non joignable au démarrage du serveur cf ce post sur la `newslist
RabbitMQ`_.

.. _newslist RabbitMQ: http://permalink.gmane.org/gmane.comp.networking.rabbitmq.general/18295

Fichier de configuration celeryconfig.py
----------------------------------------

Voir description des directives sur <http://celery.readthedocs.org/en/latest/configuration.html>.

Ce fichier est créé dans le répertoire *conf* par la commande
``coop configure``.

Ci-dessous un exemple de fichier.
Les valeurs des champs ne sont pas forcément à reprendre telles quelles mais
la présence des champs dans le fichier est obligatoire au bon fonctionnement
des batches ::

    BROKER_URL = 'amqp://guest:guest@localhost:5672//'
    CELERY_ACCEPT_CONTENT = ['pickle', 'json']
    CELERYD_CONCURRENCY = 4
    CELERY_REDIRECT_STDOUT = True
    CELERY_REDIRECT_STDOUTS_LEVEL = 'INFO'
    CELERY_RESULT_BACKEND = 'amqp'
    CELERYD_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s][%(name)s] %(message)s'
    TRYTON_DATABASE = 'dbname'
    TRYTON_CONFIG = 'path/to/trytond.conf'

Lancement des workers celery
----------------------------

Avant de pouvoir exécuter un batch il faut que des workers celery tournent sur
la machine.
Il existe plusieurs moyens pour lancer des workers, seule l'utilisation de
``celeryd`` est supportée sur nos environnements de prod.

Dans le cadre de tests dans un environnement de dev, on pourra utiliser
l'utilitaire ``celery_multi`` qui ne nécessite pas la configuration d'un
démon.

Init script: celeryd
^^^^^^^^^^^^^^^^^^^^

Installer le script ``celeryd`` comme indiqué sur l'`aide officielle`_.

.. _aide officielle: http://celery.readthedocs.org/en/latest/tutorials/daemonizing.html#id7

exemple de ``/etc/default/celeryd`` ::

    # Names of nodes to start
    #   most will only start one node:
    CELERYD_NODES="coog_batch"

    # Absolute or relative path to the 'celery' command:
    CELERY_BIN="/Exploitation/virtualenvs/server_demo_cog/bin/celery"

    # App instance to use
    # comment out this line if you don't use an app
    CELERY_APP="trytond.modules.coog_core.batch_launcher"

    # Where to chdir at start.
    CELERYD_CHDIR="/Exploitation/virtualenvs/server_demo_cog/"

    # Extra command-line arguments to the worker
    CELERYD_OPTS="--config=celeryconfig"

    # %N will be replaced with the first part of the nodename.
    CELERYD_LOG_FILE="/var/log/celery/%N.log"
    CELERYD_PID_FILE="/var/run/celery/%N.pid"

    # Workers should run as an unprivileged user.
    #   You need to create this user manually (or you can choose
    #   a user/group combination that already exists, e.g. nobody).
    CELERYD_USER="root"
    CELERYD_GROUP="root"

    # If enabled pid and log directories will be created if missing,
    # and owned by the userid/group configured.
    CELERY_CREATE_DIRS=1

Si l'environnement virtuel est installé avec l'user *root*, il faudra alors au
niveau des permissions que le demon soit aussi lancé en root. Pour que cela
marche il faut que setter la variable d'environnemnt tel que `C_FORCE_ROOT=1`.

celery_multi
^^^^^^^^^^^^

**A utiliser seulement sur sa machine de dev, celeryd est la façon "propre"
de lancer des workers sur un env de prod**

Example de wrapping script autour de celery_multi pour lancer les workers
coog:

.. code:: bash

     #!/bin/bash

    USAGE="Usage: celery_multi_coog [start|stop|stopwait|restart|kill|get hostname|names]"

    if [ "$#" -eq "0" ]; then
        echo $USAGE
        exit 1
    fi

    if [ -z "$VIRTUAL_ENV" ]; then
        echo 'Error: no virtual env activated.'
        exit 1
    fi

    APP=trytond.modules.coog_core.batch_launcher
    ACTION=$1
    LOG_DIR=$VIRTUAL_ENV/tryton-workspace/logs
    WORKER_NAME='worker_coog'
    celery multi $ACTION $WORKER_NAME --config=celeryconfig -A $APP \
    --pidfile=$LOG_DIR/celery-%n.pid  \
    --loglevel=INFO --logfile=$LOG_DIR/$WORKER_NAME.log
