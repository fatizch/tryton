import argparse

import async.broker as async_broker

from async.tasks import batch_generate


def generate(name, connection_date, treatment_date, extra_args):
    batch_generate(name, connection_date, treatment_date, extra_args)


def generate_async(name, connection_date, treatment_date, extra_args):
    broker = async_broker.get_module()
    broker.enqueue(name, 'batch_generate', (name, connection_date,
        treatment_date, extra_args))


def parse_extra_args(extra_args):
    extra_args = [x.split('=', 1) for x in extra_args]
    extra_args = [x for sublist in extra_args for x in sublist]
    return dict(zip([x.lstrip('-') for x in extra_args[0::2]],
        extra_args[1::2]))


def main():
    parser = argparse.ArgumentParser(description='Coog batch command')

    # Tech
    parser.add_argument('--broker', '-b', choices=['rq', 'celery'],
        required=True, help='Queuing broker')
    parser.add_argument('--async', '-a', help='Generate in async mode')

    # Batch
    parser.add_argument('--name', '-n', type=str,
        required=True, help='Name of the batch to launch')
    parser.add_argument('--connexion-date', '-c', type=str,
        help='Date used to log in')
    parser.add_argument('--treatment-date', '-t', type=str,
        help='Batch treatment date')

    arguments, extra_args = parser.parse_known_args()
    extra_args = parse_extra_args(extra_args)

    # set broker (rq or celery) based on args
    async_broker.set_module(arguments.broker)

    fn = generate
    if arguments.async is not None:
        fn = generate_async
    fn(arguments.name, arguments.connexion_date, arguments.treatment_date,
        extra_args)


if __name__ == '__main__':
    main()
