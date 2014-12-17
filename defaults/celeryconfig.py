BROKER_URL = 'amqp://guest:guest@localhost:5672//'
CELERY_ACCEPT_CONTENT = ['pickle', 'json']
CELERY_REDIRECT_STDOUT = False
CELERY_REDIRECT_STDOUTS_LEVEL = 'INFO'
CELERY_RESULT_BACKEND = 'amqp'
CELERYD_CONCURRENCY = 4
CELERYD_TASK_LOG_FORMAT = \
    '[%(asctime)s: %(levelname)s/%(processName)s][%(name)s] %(message)s'
TRYTON_DATABASE = '$DATABASE'
TRYTON_CONFIG = '$WORKSPACE/conf/trytond.conf'
