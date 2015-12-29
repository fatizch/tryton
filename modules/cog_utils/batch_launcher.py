import datetime
import logging

from celery import Celery, group
from celeryconfig import CELERY_RESULT_BACKEND, BROKER_URL
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

logger = logging.getLogger(__name__)
app = Celery('Coopengo Batch', backend=CELERY_RESULT_BACKEND,
    broker=BROKER_URL)


def chunks_number(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i + n]


def chunks_size(l, n):
    newn = int(1.0 * len(l) / n + 0.5)
    for i in xrange(0, n - 1):
        yield l[i * newn:i * newn + newn]
    yield l[n * newn - newn:]


@app.task(base=TrytonTask)
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
            client_defined_date=connexion_date):
        ids = [x[0] for x in BatchModel.select_ids(treatment_date, extra_args)]
        if BatchModel.get_conf_item('split_mode') == 'number':
            chunking = chunks_number
            chunk_param = int(BatchModel.get_conf_item('split_size'))
            generate_method = generate
        elif BatchModel.get_conf_item('split_mode') == 'divide':
            chunking = chunks_size
            chunk_param = int(BatchModel.get_conf_item('split_size'))
            generate_method = generate
        elif BatchModel.get_conf_item('split_mode') in ('mono_divide',
                'mono_number'):
            chunking = chunks_size
            chunk_param = 1
            generate_method = generate_mono
        logger.info('Executing %s with %s' % (batch_name,
            coop_string.get_print_infos(ids)))
        job = group(generate_method.s(BatchModel.__name__, tmp_list,
                connexion_date, treatment_date, extra_args)
            for tmp_list in chunking(ids, chunk_param))()
    return job


@app.task(base=TrytonTask)
def generate(batch_name, ids, connexion_date, treatment_date, extra_args):
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    to_treat = BatchModel.convert_to_instances(ids)
    batch_logger = batch.get_logger(batch_name)
    batch_logger.info('Executing batch on %s' %
        coop_string.get_print_infos(ids))
    try:
        run_task(to_treat, ids, treatment_date, extra_args, batch_name,
            connexion_date)
    except:
        Transaction().cursor.rollback()
        do_not_divide = BatchModel.get_conf_item('split_mode') == \
            'divide' and int(BatchModel.get_conf_item('split_size')) == 1
        if len(ids) < 2 or do_not_divide:
            batch_logger.failure('Task cannot be divided, aborting.')
            return 1
        batch_logger.info('Splitting task in subtasks and retrying.')
        half_idx = len(ids) / 2
        group(generate.s(batch_name, _ids, connexion_date, treatment_date,
                extra_args)
            for _ids in (ids[:half_idx], ids[half_idx:]))()
    return 0


@app.task(base=TrytonTask)
def generate_mono(batch_name, ids, connexion_date, treatment_date, extra_args):
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    batch_logger = batch.get_logger(batch_name)
    batch_logger.info('Executing batch on %s' %
        coop_string.get_print_infos(ids))
    if BatchModel.get_conf_item('split_mode').endswith('divide'):
        chunk_method = chunks_size
    else:
        chunk_method = chunks_number
    packets = list(chunk_method(ids, int(BatchModel.get_conf_item(
                    'split_size'))))
    error = 0
    while packets:
        batch_logger.info('%i packets remaining' % len(packets))
        packet_data = packets.pop()
        with Transaction().new_cursor() as transaction:
            try:
                to_treat = BatchModel.convert_to_instances(packet_data)
                run_task(to_treat, packet_data, treatment_date, extra_args,
                    batch_name, connexion_date)
                transaction.cursor.commit()
            except:
                transaction.cursor.rollback()
                if len(packet_data) < 2:
                    batch_logger.failure('Task cannot be divided, aborting.')
                    error = 1
                    continue
                batch_logger.info('Splitting task in subtasks and retrying.')
                half_idx = len(packet_data) / 2
                packets += [packet_data[:half_idx], packet_data[half_idx:]]
    return error


def run_task(to_treat, ids, treatment_date, extra_args, batch_name,
        connexion_date):
    User = Pool().get('res.user')
    admin, = User.search([('login', '=', 'admin')])
    BatchModel = Pool().get(batch_name)
    to_treat = BatchModel.convert_to_instances(ids)
    batch_logger = batch.get_logger(batch_name)
    with Transaction().set_user(admin.id), Transaction().set_context(
            User.get_preferences(context_only=True),
            client_defined_date=connexion_date):
        try:
            BatchModel.execute(to_treat, ids, treatment_date, extra_args)
            batch_logger.success('Processed %s',
                coop_string.get_print_infos(ids))
        except Exception:
            batch_logger.exception('Exception occured when processing %s',
                coop_string.get_print_infos(ids))
            Transaction().cursor.rollback()
