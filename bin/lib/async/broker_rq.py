import os
import json
import redis

from urlparse import urlparse
from rq import Queue

import async.config as config
from async.tasks import tasks

broker_url = os.environ.get('TRYTOND_ASYNC_RQ')
assert broker_url, 'TRYTOND_ASYNC_RQ should be set'
broker_url = urlparse(broker_url)
broker_host = broker_url.hostname
broker_port = broker_url.port
broker_db = broker_url.path.strip('/')
connection = redis.StrictRedis(host=broker_host, port=broker_port,
    db=broker_db)


def log_job(job, queue, fname, args):
    # stored by rq but pickled
    connection.hset(job.key, 'coog', json.dumps(
        {'queue': queue, 'func': fname, 'args': args}))


def log_result(job, result):
    connection.hset(job.key, 'coog-result', json.dumps(result))


def enqueue(queue, fname, args):
    if isinstance(fname, basestring):
        func = tasks[fname]
    else:
        func = fname
        fname = func.__name__
    assert func and callable(func), 'task %s does not exist' % fname
    q = Queue(queue, connection=connection)
    job = q.enqueue_call(func=func, args=args, timeout=config.JOB_TIMEOUT,
        ttl=config.JOB_TTL, result_ttl=config.JOB_RESULT_TTL)
    log_job(job, queue, fname, args)


def split(job_key):
    job = connection.hget('rq:job:%s' % job_key, 'coog')
    job = json.loads(job)
    args = job['args']
    ids = args[4]
    assert len(ids) > 1, 'can not split a singleton'
    args_list = [[args[0], args[1], args[2], args[3], [id]] for id in ids]
    for args in args_list:
        enqueue(job['queue'], job['func'], args)
