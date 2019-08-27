#!/usr/bin/env python
import os
import argparse
from collections import OrderedDict

from trytond.pool import Pool
from trytond.modules.coog_core import batch, queue
from trytond.transaction import Transaction


def get_specific_concurrency_batches():
    """
    Batch environ syntax: [PREFIX]_[BATCH_NAME]
    - Prefix is "TRYTOND_CONCURRENCY"
    - BATCH_NAME is the batch __name__ with "_" instead of "."
    - If there "_" within the BATCH_NAME, we need to flag it with triple
      underscores.
       - Exemple: TRYTOND_CONCURRENCY_ACCOUNT_AGED___BALANCE_GENERATE=1
         => account.aged_balance.generate will be started with one worker
    """
    batches = OrderedDict()
    for key, value in os.environ.items():
        if not key.startswith('TRYTOND_CONCURRENCY_'):
            continue
        # Escape triple underscore
        key = key.replace('___', '\\')
        try:
            batch_name, value = key[
                len('TRYTOND_CONCURRENCY_'):].lower(), int(value)
        except ValueError:
            continue
        batch_name = '.'.join(batch_name.split('_')).replace('\\', '_')
        batches[batch_name] = value
    return batches


def run_specific_batch(specific_name, concurrency, last=False):
    loglevel = os.environ.get('LOG_LEVEL', 'ERROR')
    os.system("celery worker --app=coog_async.broker_celery --loglevel=%s "
        "--concurrency=%s --queues=%s > /dev/null 2>&1 %s"
        (loglevel, concurrency, specific_name, "&" if not last else ""))


def main(args):
    database = os.environ.get('DB_NAME', None)
    with Transaction().start(database, 0, readonly=True):
        # Why do we do need to this all of a sudden?
        pool = Pool()
        pool.init()
        specific_batches = get_specific_concurrency_batches()
        default_batches = []
        if not args.run_specific:
            for name, kls in pool.iterobject():
                if issubclass(kls, batch.BatchRoot) or issubclass(kls,
                        queue.QueueMixin):
                    if name not in specific_batches.keys():
                        default_batches.append(name)
            for name in default_batches:
                print(name)
        else:
            specific_batches = specific_batches.keys()
            assert specific_batches
            for specific_name, concurrency in specific_batches.items():
                run_specific_batch(specific_name, concurrency,
                    last=specific_name == specific_batches[-1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_specific', action='store_true',
        help='Run specific concurrency workers according to environment '
            'configuration')
    args = parser.parse_args()
    main(args)
