import os
import argparse
import logging
# import warnings

import async.broker as async_broker
from async.tasks import batch_generate


def generate(name, params):
    res = batch_generate(name, params)
    return '%d jobs with %s objs' % (len(res), sum(res))


def generate_async(name, params):
    broker = async_broker.get_module()
    broker.enqueue(name, 'batch_generate', (name, params))
    return 'enqueued'


def parse_extra_args(params):
    params = sum([x.split('=', 1) for x in params], [])
    params_dict = dict(zip([x.lstrip('-') for x in params[0::2]],
            params[1::2]))
    logging.basicConfig()
    logger = logging.getLogger()
    for deprecated, valid in (
            ('c', 'connection_date'),
            ('connection-date', 'connection_date'),
            ('t', 'treatment_date'),
            ('treatment-date', 'treatment_date')
            ):
        if deprecated in params_dict:
            logger.warning('-%s is deprecated, use -%s instead' % (deprecated,
                    valid))
            params_dict[valid] = params_dict[deprecated]
            del params_dict[deprecated]
    return params_dict


def main():
    log_level = os.environ.get('LOG_LEVEL', 'ERROR')
    logging.basicConfig(level=getattr(logging, log_level))
    parser = argparse.ArgumentParser(description='Coog batch command')
    # Technical parameters
    parser.add_argument('--broker', '-b', choices=['rq', 'celery'],
        required=True, help='Queuing broker')
    parser.add_argument('--async', '-a', help='Generate in async mode')
    # Batch parameters
    parser.add_argument('--name', '-n', type=str,
        required=True, help='Name of the batch to launch')
    # parse
    arguments, params = parser.parse_known_args()
    params = parse_extra_args(params)
    # set broker (rq or celery) based on args
    async_broker.set_module(arguments.broker)
    fn = generate
    if arguments.async is not None:
        fn = generate_async
    return fn(arguments.name, params)


if __name__ == '__main__':
    print(main())
