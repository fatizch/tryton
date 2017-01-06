import logging
import async.broker as async_broker


def _batch_split(l, n):
    assert n >= 0, 'Negative split size'
    if len(l) == 0:
        return
    elif n == 0 or n >= len(l):
        yield l
    else:
        for i in xrange(0, len(l), n):
            yield l[i:i + n]


def batch_generate(name, params):
    assert name, 'Batch name is required'

    from trytond.cache import Cache
    from trytond.pool import Pool
    from trytond.transaction import Transaction
    from tryton_init import database

    logger = logging.getLogger(name)
    logger.info('generate with params: %s', params)
    broker = async_broker.get_module()
    batch_params = params.copy()
    job_size = batch_params.pop('job_size', None)
    batch_params.pop('transaction_size', None)
    res = []
    with Transaction().start(database, 0, readonly=True):
        User = Pool().get('res.user')
        # TODO: add batch user
        admin, = User.search([('login', '=', 'admin')])
        BatchModel = Pool().get(name)
        batch_params = BatchModel.check_params(batch_params)
        with Transaction().set_context(User.get_preferences(context_only=True),
                client_defined_date=batch_params['connection_date']):
            Cache.clean(database)
            batch_params.pop('connection_date', None)
            try:
                if job_size is None:
                    job_size = BatchModel.get_conf_item('job_size')
                job_size = int(job_size)
                ids = [x[0] for x in BatchModel.select_ids(**batch_params)]
                for l in _batch_split(ids, job_size):
                    broker.enqueue(name, 'batch_exec', (name, l, params))
                    res.append(len(l))
            except Exception:
                logger.exception('generate crashed')
                raise
            finally:
                Cache.resets(database)
    return res


def batch_exec(name, ids, params):
    assert name, 'Batch name is required'
    assert type(ids) is list, 'Ids list is required'
    assert type(params) is dict, 'Params dict is required'

    from trytond.cache import Cache
    from trytond.pool import Pool
    from trytond.transaction import Transaction
    from tryton_init import database

    logger = logging.getLogger(name)
    logger.info('exec %s items with params: %s', len(ids), params)

    with Transaction().start(database, 0, readonly=True):
        User = Pool().get('res.user')
        # TODO: add batch user
        admin, = User.search([('login', '=', 'admin')])
        BatchModel = Pool().get(name)

    batch_params = params.copy()
    batch_params.pop('job_size', None)
    transaction_size = batch_params.pop('transacion_size', None)

    res = []
    with Transaction().start(database, admin.id):
        batch_params = BatchModel.check_params(batch_params)
        with Transaction().set_context(User.get_preferences(context_only=True),
                client_defined_date=batch_params['connection_date']):
            batch_params.pop('connection_date', None)
            Cache.clean(database)
            if transaction_size is None:
                transaction_size = BatchModel.get_conf_item('transaction_size')
            transaction_size = int(transaction_size)
            try:
                for l in _batch_split(ids, transaction_size):
                    to_treat = BatchModel.convert_to_instances(l)
                    r = BatchModel.execute(to_treat, l, **batch_params)
                    res.append(r or len(l))
                    Transaction().commit()
            except Exception:
                logger.exception('exec crashed')
                Transaction().rollback()
                raise
            finally:
                Cache.resets(database)
    return res


tasks = {'batch_generate': batch_generate, 'batch_exec': batch_exec}
