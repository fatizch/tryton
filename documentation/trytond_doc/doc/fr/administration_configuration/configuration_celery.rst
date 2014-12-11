Configuration Celery
====================

Celery <http://celery.readthedocs.org/en/latest/> est le système utilisé par l'outil ``coop batch`` pour faire des traitements de batches distribués.

celeryconfig.py
---------------

Voir description des directives sur <http://celery.readthedocs.org/en/latest/configuration.html>

Ci-dessous un exemple de fichier.
Les valeurs des champs ne sont pas forcément à reprendre telles quelles mais la présence des champs dans le fichier est obligatoire au bon fonctionnement des batches ::

    BROKER_URL = 'amqp://guest:guest@localhost:5672//'
    CELERY_ACCEPT_CONTENT = ['pickle', 'json']
    CELERYD_CONCURRENCY = 4
    CELERY_REDIRECT_STDOUT = True
    CELERY_REDIRECT_STDOUTS_LEVEL = 'INFO'
    CELERY_RESULT_BACKEND = 'amqp'
    CELERYD_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s][%(name)s] %(message)s'
    TRYTON_DATABASE = 'dbname'
    TRYTON_CONFIG = 'path/to/trytond.conf'


