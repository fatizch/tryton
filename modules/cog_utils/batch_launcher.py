import datetime

from celery import Celery, group
from celeryconfig import CELERY_RESULT_BACKEND
from celery.utils.log import get_task_logger
from celery_tryton import TrytonTask

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.cog_utils import batch, coop_string

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

logger = batch.BatchLogger(get_task_logger(__name__), {})
celery = Celery('Coopengo Batch', backend=CELERY_RESULT_BACKEND)


def chunks_number(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i + n]


def chunks_size(l, n):
    newn = int(1.0 * len(l) / n + 0.5)
    for i in xrange(0, n - 1):
        yield l[i * newn:i * newn + newn]
    yield l[n * newn - newn:]


@celery.task(base=TrytonTask)
def generate_all(batch_name, connexion_date=None, treatment_date=None,
        extra_args=None):
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
            client_defined_date=connexion_date, batch_extra_args=extra_args):
        ids = [x[0] for x in BatchModel.select_ids(treatment_date)]
        if BatchModel.get_conf_item('split_mode') == 'number':
            chunking = chunks_number
        else:
            chunking = chunks_size
        logger.info('Executing %s with %s' % (batch_name,
            coop_string.get_print_infos(ids)))
        job = group(generate.s(BatchModel.__name__, tmp_list, connexion_date,
            treatment_date, extra_args)
            for tmp_list in chunking(ids, int(BatchModel.get_conf_item(
                'split_size'))))()
    return job


@celery.task(base=TrytonTask)
def generate(batch_name, ids, connexion_date, treatment_date, extra_args):
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    with Transaction().set_user(admin.id), Transaction().set_context(
            User.get_preferences(context_only=True),
            client_defined_date=connexion_date):
        to_treat = BatchModel.convert_to_instances(ids)
        logger = batch.get_logger(batch_name)
        try:
            BatchModel.execute(to_treat, ids, treatment_date, extra_args)
            logger.success('Processed %s', coop_string.get_print_infos(ids))
        except Exception:
            logger.exception('Exception occured when processing %s',
                coop_string.get_print_infos(ids))
            Transaction().cursor.rollback()
            do_not_divide = BatchModel.get_conf_item('split_mode') == \
                'divide' and int(BatchModel.get_conf_item('split_size')) == 1
            if len(ids) < 2 or do_not_divide:
                logger.failure('Task cannot be divided, aborting.')
                return 1
            logger.info('Splitting task in subtasks and retrying.')
            half_idx = len(ids) / 2
            group(generate.s(batch_name, _ids, connexion_date, treatment_date,
                    extra_args)
                for _ids in (ids[:half_idx], ids[half_idx:]))()
    return 0
