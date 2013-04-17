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
# Start the workers as daemons (background) :
#   celery multi start CoopBatch -l info
#                         --app=trytond.modules.coop_utils.batch_launcher
#                         --config=trytond.modules.coop_utils.celeryconfig
#                         --logfile=logs/%n.log
#
# Run a given batch :
#   celery call trytond.modules.coop_utils.batch_launcher.generate_all
#                         --args='[args]'
#   args are :
#      - batch class __name__ ("ins_product.document_request_batch")
#      - business date "YYYY-MM-DD"
#
# Start Monitoring web server :
#   celery flower
#
##############################################################################


# Celery configuration file in coop_utils/celeryconfig.py
celery = Celery('Coopengo Batch')


def chunks_number(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def chunks_size(l, n):
    newn = int(1.0 * len(l) / n + 0.5)
    for i in xrange(0, n-1):
        yield l[i*newn:i*newn+newn]
    yield l[n*newn-newn:]


@celery.task(base=TrytonTask)
def generate_all(batch_name, date=None):
    if not date:
        date = datetime.date.today()
    else:
        date = datetime.date(*map(int, date.split('-')))
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    with Transaction().set_user(admin.id), \
        Transaction().set_context(
            User.get_preferences(context_only=True),
            client_defined_date=date):
        ids = map(lambda x: x[0], BatchModel.select_ids())
        if BatchModel.get_batch_stepping_mode() == 'number':
            chunking = chunks_number
        else:
            chunking = chunks_size
        group(
            generate.s(BatchModel.__name__, tmp_list, date)
            for tmp_list in chunking(ids, BatchModel.get_batch_step()))()


@celery.task(base=TrytonTask)
def generate(batch_name, ids, date):
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    logger = get_task_logger(BatchModel.get_batch_name())
    with Transaction().set_user(admin.id), \
        Transaction().set_context(
            User.get_preferences(context_only=True),
            client_defined_date=date):
        to_treat = BatchModel.convert_to_instances(ids)
        BatchModel.execute(to_treat, ids, logger)
    return
