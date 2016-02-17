import os
import json
import redis

from urlparse import urlparse
from celery import Celery

import async.config as config

from async.tasks import tasks

broker_url = os.environ.get('TRYTOND_ASYNC_CELERY')
assert broker_url, 'TRYTOND_ASYNC_CELERY should be set'
app = Celery('coog', broker=broker_url, backend=broker_url)

broker_url = urlparse(broker_url)
broker_host = broker_url.hostname
broker_port = broker_url.port
broker_db = broker_url.path.strip('/')
broker = redis.StrictRedis(host=broker_host, port=broker_port, db=broker_db)

for name, func in tasks.iteritems():
    app.task(func, name=name, serializer='json')


def log_job(job_id, queue, fname, args):
    broker.setex('coog:job:%s' % job_id, config.JOB_RESULT_TTL, json.dumps(
            {'queue': queue, 'func': fname, 'args': args}))


def enqueue(queue, fname, args):
    task = app.tasks[fname]
    res = task.apply_async(queue=queue, args=args, expires=config.JOB_TTL,
        retry=False)
    log_job(str(res), queue, fname, args)
