import os
import time
import json
import redis
import traceback

from urllib.parse import urlparse
from celery import Celery
from celery import Task
from celery.utils.log import get_task_logger


import coog_async.config as config
from coog_async.tasks import tasks as batch_tasks
from coog_async.tasks import _execute


broker_url = os.environ.get('TRYTOND_ASYNC_CELERY')
assert broker_url, 'TRYTOND_ASYNC_CELERY should be set'
app = Celery('coog', broker=broker_url, backend=broker_url)
app.conf.CELERY_REDIRECT_STDOUTS = True                      # print are logged
app.conf.CELERY_REDIRECT_STDOUTS_LEVEL = 'INFO'              # assumed as info
app.conf.CELERY_ACCEPT_CONTENT = ['json']                    # only json
app.conf.CELERY_RESULT_SERIALIZER = 'json'                   # jsonify result
app.conf.CELERY_TASK_RESULT_EXPIRES = config.JOB_RESULT_TTL  # ttl for result

broker_url = urlparse(broker_url)
broker_host = broker_url.hostname
broker_port = broker_url.port
broker_db = broker_url.path.strip('/')
connection = redis.StrictRedis(host=broker_host, port=broker_port,
    db=broker_db)

logger = get_task_logger(__name__)


class CoogTask(Task):
    abstract = True


class CoogBatchTask(Task):

    def batch_trigger_event(self, method, task_id, batch_name, ids,
            *args, **kwargs):
        import tryton_init
        from trytond.transaction import Transaction
        from trytond.pool import Pool
        from trytond.modules.coog_core.batch import BatchRootNoSelect
        user_id = kwargs.get('user', None)
        database = tryton_init.database(kwargs.get('database'))
        with Transaction().start(database, 0, readonly=True):
            User = Pool().get('res.user')
            if not user_id:
                user, = User.search([('login', '=', 'admin')])
                user_id = user.id
        with Transaction().start(database, user_id):
            pool = Pool()
            with Transaction().set_context(
                    User.get_preferences(context_only=True)):
                batch = pool.get(batch_name)
                if issubclass(batch, BatchRootNoSelect):
                    return
                objects = batch.convert_to_instances(ids)
                getattr(batch, method)(task_id, objects, *args, **kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        try:
            connection.lpush('coog:fail', task_id)
            extra_args = {}
            extra_args.update(args[2])
            extra_args.update(kwargs)
            self.batch_trigger_event('on_job_fail', task_id, args[0],
               args[1], einfo, **extra_args)
        except Exception:
            logger.critical("!!!!Error happened during on failure!!!!")
            logger.critical("!!!!See stack below!!!!")
            tb = traceback.format_exc()
            logger.critical(''.join(tb))

    def on_success(self, retval, task_id, args, kwargs):
        extra_args = {}
        extra_args.update(args[2])
        extra_args.update(kwargs)
        self.batch_trigger_event('on_job_success', task_id, args[0], args[1],
            retval, **extra_args)


for name, func in batch_tasks.items():
    app.task(func, base=CoogBatchTask, name=name, serializer='json')


app.task(_execute, base=CoogTask, name='async_method_execution',
    serializer='json')


def api_offloading(api_model, api_name, database, user, context,
        *args, **kwargs):
    '''
        Execute an API call as an external call, and returns the result. Can be
        used to "parallelize" api calls by offloading them on celery processes
    '''
    from trytond.pool import Pool
    from trytond.transaction import Transaction

    with Transaction().start(database, user) as transaction:
        Pool(database).init()
        with transaction.set_context(**context) as transaction:
            pool = Pool()
            Model = pool.get(api_model)
            API = pool.get('api')

            # The apify wrapper will properly wrap errors, we just need to make
            # sure they are serialized the same way the dispatcher would
            return API.convert_result(
                Model, api_name, getattr(Model, api_name)(*args, **kwargs))


app.task(api_offloading, base=CoogTask, name='api_offloading',
    serializer='json', queue='api_offloading')


def log_job(job, queue, fname, args, kwargs):
    # not stored by celery
    connection.setex('coog:job:%s' % str(job), config.JOB_RESULT_TTL,
        json.dumps({
                'date': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'queue': queue,
                'func': fname,
                'args': args,
                'kwargs': kwargs,
                }))


def enqueue(queue, fname, args, **kwargs):
    task = app.tasks[fname]
    job = task.apply_async(queue=queue, args=args, kwargs=kwargs,
        expires=config.JOB_TTL, retry=False)
    log_job(job, queue, fname, args, kwargs)
    return job.task_id


def insert_into_redis(chain, queue, nb_jobs, nb_records, start_time,
        duration, status):
    info = {
        "chain_name": chain,
        "queue": queue,
        "nb_jobs": nb_jobs,
        "nb_records": nb_records,
        "first_launch_date": start_time,
        "duration_in_sec": duration,
        "status": status
    }
    info_s = json.dumps(info)
    connection.set("coog:extra:" + chain + queue + start_time, info_s)


def split(job_key):
    job = connection.get('coog:job:%s' % job_key)
    if not job:
        exit(code=1)
    job = json.loads(job)
    args = job['args']
    kwargs = job['kwargs']
    if not args[2].get('split', True):
        exit(code=1)
    ids = args[1]
    if len(ids) <= 1:
        exit(code=1)
    args_list = [[args[0], [id], args[2]] for id in ids]
    for args in args_list:
        enqueue(job['queue'], job['func'], args, **kwargs)


def replay(job_key):
    job = connection.get('coog:job:%s' % job_key)
    if not job:
        exit(code=1)
    job = json.loads(job)
    args = job['args']
    kwargs = job['kwargs']
    enqueue(job['queue'], job['func'], args, **kwargs)
