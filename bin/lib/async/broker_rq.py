import os
import json
import redis

from urlparse import urlparse
from rq import Queue

import async.config as config

broker_url = os.environ.get('TRYTOND_ASYNC_RQ')
assert broker_url, 'TRYTOND_ASYNC_RQ should be set'
broker_url = urlparse(broker_url)
broker_host = broker_url.hostname
broker_port = broker_url.port
broker_db = broker_url.path.strip('/')
broker = redis.StrictRedis(host=broker_host, port=broker_port, db=broker_db)

from async.tasks import tasks


def log_job(job, queue, fname, args):
    # stored by rq but pickled
    broker.hset(job.key, 'coog', json.dumps(
        {'queue': queue, 'func': fname, 'args': args}))


def enqueue(queue, fname, args):
    func = tasks[fname]
    assert func, 'task %s does not exist' % fname
    q = Queue(queue, connection=broker)
    job = q.enqueue_call(func=func, args=args, timeout=config.JOB_TIMEOUT,
        ttl=config.JOB_TTL, result_ttl=config.JOB_RESULT_TTL)
    log_job(job, queue, fname, args)
