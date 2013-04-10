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
#   celery multi start w1 --app=trytond.modules.coop_utils.batch_launcher
#                         --logfile=logfile_name.log -l info
#
# Start Monitoring web server :
#   celery flower
#
##############################################################################

celery = Celery('Coopengo Batch', broker='amqp://guest@localhost//')
celery.conf.TRYTON_DATABASE = 'new_feature'
celery.conf.TRYTON_CONFIG = '/home/giovanni/WorkDir/' + \
    'envs/new_feature/tryton-workspace/conf/trytond.conf'


def chunks_size(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def chunks_number(l, n):
    newn = int(1.0 * len(l) / n + 0.5)
    for i in xrange(0, n-1):
        yield l[i*newn:i*newn+newn]
    yield l[n*newn-newn:]


@celery.task(base=TrytonTask)
def generate_all(batch_name):
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    with Transaction().set_user(admin.id), \
        Transaction().set_context(
            User.get_preferences(context_only=True)):
        ids = map(lambda x: x[0], BatchModel.select_ids())
        if BatchModel.get_batch_stepping_mode() == 'number':
            chunking = chunks_number
        else:
            chunking = chunks_size
        group(
            generate.s(BatchModel.__name__, tmp_list)
            for tmp_list in chunking(ids, BatchModel.get_batch_step()))()


@celery.task(base=TrytonTask)
def generate(batch_name, ids):
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    logger = get_task_logger(BatchModel.__name__)
    with Transaction().set_user(admin.id), \
        Transaction().set_context(
            User.get_preferences(context_only=True)):
        to_treat = BatchModel.convert_to_instances(ids)
        BatchModel.execute(to_treat, ids, logger)
    return
