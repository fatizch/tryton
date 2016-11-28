import logging

from datetime import datetime, date

import async.broker as async_broker

DATE_FORMAT = '%Y-%m-%d'           # 2000-12-31


def _batch_split(l, n):
    assert n >= 0, 'Negative split size'
    if len(l) == 0:
        return
    elif n == 0 or n >= len(l):
        yield l
    else:
        for i in xrange(0, len(l), n):
            yield l[i:i + n]


def batch_generate(name, connection_date, treatment_date, args):
    assert name, 'Batch name is required'

    from trytond.cache import Cache
    from trytond.pool import Pool
    from trytond.transaction import Transaction

    from tryton_init import database

    logger = logging.getLogger(name)

    broker = async_broker.get_module()

    if connection_date is None:
        connect_on = date.today()
        connection_date = connect_on.strftime(DATE_FORMAT)
    else:
        connect_on = datetime.strptime(connection_date, DATE_FORMAT).date()

    if treatment_date is None:
        treat_on = date.today()
        treatment_date = treat_on.strftime(DATE_FORMAT)
    else:
        treat_on = datetime.strptime(treatment_date, DATE_FORMAT).date()

    logger.info('generate with c_dt: %s, t_dt: %s, args: %s', connection_date,
        treatment_date, args)

    with Transaction().start(database, 0, readonly=True):
        User = Pool().get('res.user')
        # TODO: add batch user
        admin, = User.search([('login', '=', 'admin')])
        BatchModel = Pool().get(name)

    res = []
    with Transaction().start(database, admin.id, readonly=True):
        with Transaction().set_context(User.get_preferences(context_only=True),
                client_defined_date=connect_on):
            Cache.clean(database)
            try:
                job_size = args.get('job_size', None)
                if job_size is None:
                    job_size = BatchModel.get_conf_item('job_size')
                job_size = int(job_size)
                logger.info('job_size: %s', job_size)
                ids = [x[0] for x in BatchModel.select_ids(treat_on, args)]
                for l in _batch_split(ids, job_size):
                    broker.enqueue(name, 'batch_exec', (name, connection_date,
                            treatment_date, args, l))
                    res.append(len(l))
                    logger.info('created a job for %s ids', len(l))
            except Exception:
                logger.exception('generate crashed')
                raise
            finally:
                Cache.resets(database)
    return res


def batch_exec(name, connection_date, treatment_date, args, ids):
    assert name, 'Batch name is required'
    assert type(ids) is list, 'Ids list is required'
    assert connection_date, 'Connection date is required'
    assert treatment_date, 'Treatment date is required'

    from trytond.cache import Cache
    from trytond.pool import Pool
    from trytond.transaction import Transaction

    from tryton_init import database

    logger = logging.getLogger(name)

    logger.info('exec %s items with c_dt: %s, t_dat: %s, args: %s', len(ids),
        connection_date, treatment_date, args)

    connect_on = datetime.strptime(connection_date, DATE_FORMAT).date()
    treat_on = datetime.strptime(treatment_date, DATE_FORMAT).date()

    with Transaction().start(database, 0, readonly=True):
        User = Pool().get('res.user')
        # TODO: add batch user
        admin, = User.search([('login', '=', 'admin')])
        BatchModel = Pool().get(name)

    res = []
    with Transaction().start(database, admin.id):
        with Transaction().set_context(User.get_preferences(context_only=True),
                client_defined_date=connect_on):
            Cache.clean(database)
            transaction_size = args.get('transaction_size', None)
            if transaction_size is None:
                transaction_size = BatchModel.get_conf_item('transaction_size')
            transaction_size = int(transaction_size)
            logger.info('transaction_size: %s', transaction_size)
            try:
                for l in _batch_split(ids, transaction_size):
                    to_treat = BatchModel.convert_to_instances(l)
                    r = BatchModel.execute(to_treat, l, treat_on, args)
                    res.append(r or len(l))
                    Transaction().commit()
                    logger.info('committed %s items', len(l))
            except Exception:
                logger.exception('exec crashed')
                Transaction().rollback()
                raise
            finally:
                Cache.resets(database)
    return res


tasks = {'batch_generate': batch_generate, 'batch_exec': batch_exec}
