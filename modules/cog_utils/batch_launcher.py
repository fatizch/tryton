import datetime
from celery import Celery, group

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond_celery import TrytonTask

from celery.utils.log import get_task_logger

##############################################################################
# Celery Usage
# Needed :
#   pip install celery flower
#
# Kill all celery processes :
#   ps ax | grep celery | awk '{print $1}' | xargs kill
#
# Start a worker :
#   celery worker -l info --config=celeryconfig
#                         --app=trytond.modules.cog_utils.batch_launcher
#                         --logfile=logs/coop_batch.log
#
# Start the workers as daemons (background) :
#   celery multi start CoopBatch -l info
#                         --app=trytond.modules.cog_utils.batch_launcher
#                         --logfile=logs/%n.log
# (conf file for daemon should be put in /etc/default/celery)
#
# Run a given batch :
#   celery call trytond.modules.cog_utils.batch_launcher.generate_all
#                         --args='[args]'
#   args are :
#      - batch class __name__ ("document.request.batch")
#      - business date "YYYY-MM-DD"
#
# Start Monitoring web server :
#   celery flower
#
##############################################################################


# Celery configuration file in cog_utils/celeryconfig.py
celery = Celery('Coopengo Batch')


def chunks_number(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i + n]


def chunks_size(l, n):
    newn = int(1.0 * len(l) / n + 0.5)
    for i in xrange(0, n - 1):
        yield l[i * newn:i * newn + newn]
    yield l[n * newn - newn:]


@celery.task(base=TrytonTask)
def generate_all(batch_name, connexion_date=None, treatment_date=None):
    if not connexion_date:
        connexion_date = datetime.date.today()
    else:
        connexion_date = datetime.datetime.strptime(connexion_date,
            '%Y-%m-%d').date()
    if not treatment_date:
        treatment_date = datetime.date.today()
    else:
        treatment_date = datetime.datetime.strptime(treatment_date,
            '%Y-%m-%d').date()
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    with Transaction().set_user(admin.id), Transaction().set_context(
            User.get_preferences(context_only=True),
            client_defined_date=connexion_date):
        ids = [x[0] for x in BatchModel.select_ids(treatment_date)]
        if BatchModel.get_conf_item('split_mode') == 'number':
            chunking = chunks_number
        else:
            chunking = chunks_size
        group(generate.s(BatchModel.__name__, tmp_list, connexion_date,
            treatment_date)
            for tmp_list in chunking(ids, int(BatchModel.get_conf_item(
                'split_size'))))()


@celery.task(base=TrytonTask)
def generate(batch_name, ids, connexion_date, treatment_date):
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    logger = get_task_logger(batch_name)
    with Transaction().set_user(admin.id), Transaction().set_context(
            User.get_preferences(context_only=True),
            client_defined_date=connexion_date):
        to_treat = BatchModel.convert_to_instances(ids)
        BatchModel.execute(to_treat, ids, logger, treatment_date)
    return
