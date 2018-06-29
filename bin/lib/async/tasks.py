import logging
import datetime
import async.broker as async_broker
from psycopg2 import OperationalError as DatabaseOperationalError


def split_batch(l, n):
    assert n >= 0, 'Negative split size'
    group = []
    for ids in l:
        # using list to group jobs (not tuple or dict)
        if not isinstance(ids, list):
            ids = [ids]
        if n > 0 and len(group) + len(ids) > n:
            if len(ids) > len(group):
                yield ids[:]
            else:
                yield group
                group = ids[:]
        else:
            group.extend(ids)
    if len(group) > 0:
        yield group


def batch_generate(name, params):
    assert name, 'Batch name is required'

    from trytond.cache import Cache
    from trytond.pool import Pool
    from trytond.transaction import Transaction
    from trytond.server_context import ServerContext
    import tryton_init

    # Get database from ENV variable
    database = tryton_init.database()
    logger = logging.getLogger(name)
    logger.info('batch arguments: %s', params)
    broker = async_broker.get_module()
    res = []
    with Transaction().start(database, 0, readonly=True):
        User = Pool().get('res.user')
        # TODO: add batch user
        admin, = User.search([('login', '=', 'admin')])
        BatchModel = Pool().get(name)

        # Batch params computation
        batch_params = BatchModel._default_config_items.copy()
        batch_params.update(BatchModel.get_batch_configuration())
        batch_params.update(params)

        batch_params = BatchModel.parse_params(batch_params)

        # Remove non business params (batch_params to be passed to select_ids)
        connection_date = batch_params.pop('connection_date',
           datetime.datetime.now().date())
        job_size = int(batch_params.pop('job_size'))
        transaction_size = int(batch_params.pop('transaction_size', 0))
        split = batch_params.pop('split', True)
        chain_name = batch_params.pop('chain_name', None)

        # Prepare serialized params (to be saved on redis)
        job_params = batch_params.copy()
        job_params['connection_date'] = connection_date
        job_params['job_size'] = job_size
        job_params['transaction_size'] = transaction_size
        job_params['split'] = split
        job_params['chain_name'] = chain_name or 'unknown'
        job_params = BatchModel.serializable_params(job_params)

        with Transaction().set_context(
                User.get_preferences(context_only=True),
                client_defined_date=connection_date):
            Cache.clean(database)
            try:
                with ServerContext().set_context(
                        from_batch=True,
                        job_size=job_size,
                        transaction_size=transaction_size):
                    for l in split_batch(BatchModel.select_ids(**batch_params),
                            job_size):
                        broker.enqueue(name, 'batch_exec',
                            (name, l, job_params), database=database)
                        res.append(len(l))
            except Exception:
                logger.critical('Job generation crashed')
                raise
            finally:
                Cache.resets(database)
    logger.info('generated with params: %s', batch_params)
    return res


def split_job(l, n):
    assert n >= 0, 'Negative split size'
    if len(l) == 0:
        return
    elif n == 0 or n >= len(l):
        yield l
    else:
        for i in xrange(0, len(l), n):
            yield l[i:i + n]


def batch_exec(name, ids, params, **kwargs):
    assert name, 'Batch name is required'
    assert type(ids) is list, 'Ids list is required'
    assert type(params) is dict, 'Params dict is required'

    from trytond.cache import Cache
    from trytond.pool import Pool
    from trytond.transaction import Transaction
    from trytond.server_context import ServerContext
    import tryton_init

    logger = logging.getLogger(name)
    logger.info('exec %s items with params: %s', len(ids), params)

    database = tryton_init.database(kwargs.get('database'))
    logger.info('Executing batch on database %s' % database)
    with Transaction().start(database, 0, readonly=True):
        User = Pool().get('res.user')
        # TODO: add batch user
        admin, = User.search([('login', '=', 'admin')])
        BatchModel = Pool().get(name)

        batch_params = params.copy()
        batch_params = BatchModel.parse_params(batch_params)

        # Remove non business params (batch_params to be passed to select_ids)
        connection_date = batch_params.pop('connection_date')
        job_size = batch_params.pop('job_size')
        transaction_size = batch_params.pop('transaction_size')
        batch_params.pop('split')
        batch_params.pop('chain_name', None)

    res = []
    with Transaction().start(database, admin.id):
        with Transaction().set_context(User.get_preferences(context_only=True),
                client_defined_date=connection_date):
            Cache.clean(database)
            try:
                with ServerContext().set_context(from_batch=True,
                        job_size=job_size, transaction_size=transaction_size,
                        auto_accept_warnings=True):
                    for l in split_job(ids, transaction_size):
                        to_treat = BatchModel.convert_to_instances(l,
                            **batch_params)
                        r = BatchModel.execute(to_treat, [x[0] for x in l],
                            **batch_params)
                        res.append(r or len(l))
                        Transaction().commit()
            except Exception:
                logger.critical('Job execution crashed')
                Transaction().rollback()
                raise
            finally:
                Cache.resets(database)
    return res


def _execute(ids, *args, **kwargs):
    from trytond.pool import Pool
    from trytond.transaction import Transaction
    from trytond.config import config
    model_name = kwargs.pop('model_name')
    method_name = kwargs.pop('method_name')
    database = kwargs.pop('database')
    user = kwargs.pop('user', 0)
    res = None

    for count in range(config.getint('database', 'retry'), -1, -1):
        with Transaction().start(database, user) as transaction:
            Pool(database).init()
            User = Pool().get('res.user')
            with transaction.set_context(User.get_preferences(
                        context_only=True),
                    async_worker=True) as transaction:
                try:
                    model = Pool().get(model_name)
                    method = getattr(model, method_name)
                    records = model.browse(ids)
                    res = method(records, *args, **kwargs)
                    break
                except DatabaseOperationalError:
                    if count:
                        transaction.rollback()
                        continue
                    raise
    return res


tasks = {'batch_generate': batch_generate, 'batch_exec': batch_exec}
