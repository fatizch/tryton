import sys
import logging
import datetime
import coog_async.broker as async_broker
from psycopg2.extensions import TransactionRollbackError
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
    from trytond.modules.coog_core.batch import BatchRoot
    import tryton_init

    # Get database from ENV variable
    database = tryton_init.database()
    logger = logging.getLogger(name)
    logger.info('batch arguments: %s', params)
    broker = async_broker.get_module()
    res = []
    with Transaction().start(database, 0, readonly=True):
        User = Pool().get('res.user')
        try:
            BatchModel = Pool().get(name)
        except KeyError:
            logger.critical('%s is not a valid model name' % name)
            sys.exit(1)

        if not issubclass(BatchModel, BatchRoot):
            logger.critical('%s is not a batch model' % name)
            sys.exit(1)

        admin = User.search([('login', '=', 'admin')])
        company = admin[0].company.id if admin and admin[0].company else None
        assert company is not None, 'No company configured on admin user'

        # Batch params computation
        batch_params = BatchModel._default_config_items.copy()

        conf = BatchModel.get_batch_configuration()
        to_disable = conf.get('disable')
        if to_disable:
            logger.info('This batch %s has been disabled' % name)
            return []

        conf.pop('disable', None)
        batch_params.update(conf)
        batch_params.update(params)
        batch_params = BatchModel.parse_params(batch_params)

        # Remove non business params (batch_params to be passed to select_ids)
        connection_date = batch_params.pop('connection_date',
           datetime.datetime.now().date())
        job_size = int(batch_params.pop('job_size'))
        transaction_size = int(batch_params.pop('transaction_size', 0))
        split = batch_params.pop('split', True)
        chain_name = batch_params.pop('chain_name', None)
        retry = int(batch_params.pop('retry', 0))

        if transaction_size > 0 and transaction_size < job_size:
            assert not split, "Jobs with a transaction_size cannot be " \
                "splitted. Please set split to False in this batch " \
                "configuration or add --no-split option to your command line"
            assert not retry, "Jobs with a transaction_size cannot be " \
                "retried. Please set split to False in this batch " \
                "configuration"

        # Prepare serialized params (to be saved on redis)
        job_params = batch_params.copy()
        job_params['connection_date'] = connection_date
        job_params['job_size'] = job_size
        job_params['transaction_size'] = transaction_size
        job_params['split'] = split
        job_params['retry'] = retry
        job_params['chain_name'] = chain_name or 'unknown'
        job_params = BatchModel.serializable_params(job_params)

        with Transaction().set_context(
                User.get_preferences(context_only=True),
                client_defined_date=connection_date, company=company):
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
                    if not len(res):
                        broker.insert_into_redis(
                            chain=job_params['chain_name'], queue=name,
                            nb_jobs=0, nb_records=0,
                            start_time=datetime.datetime.strftime(
                                datetime.datetime.now(),
                                '%Y-%m-%dT%H:%M:%S'),
                            duration=0, status='success')
            except Exception:
                logger.critical('Job generation crashed')
                broker.insert_into_redis(
                    chain=job_params['chain_name'], queue=name,
                    nb_jobs=-1, nb_records=0,
                    start_time=datetime.datetime.strftime(
                        datetime.datetime.now(),
                        '%Y-%m-%dT%H:%M:%S'),
                    duration=0, status='failed')
                raise
    logger.info('generated with params: %s', batch_params)
    return res


def split_job(l, n):
    assert n >= 0, 'Negative split size'
    if len(l) == 0:
        return
    elif n == 0 or n >= len(l):
        yield l
    else:
        for i in range(0, len(l), n):
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
        admin = User.search([('login', '=', 'admin')])
        company = admin[0].company.id if admin and admin[0].company else None
        assert company is not None, 'No company configured on admin user'

        BatchModel = Pool().get(name)

        batch_params = params.copy()
        batch_params = BatchModel.parse_params(batch_params)

        # Remove non business params (batch_params to be passed to select_ids)
        connection_date = batch_params.pop('connection_date')
        job_size = batch_params.pop('job_size')
        retry = batch_params.pop('retry', 0)
        transaction_size = batch_params.pop('transaction_size')
        batch_params.pop('split')
        batch_params.pop('chain_name', None)

    res = []
    if retry >= 0:
        loop = list(range(retry, -1, -1))
    else:
        def infinite():
            while True:
                yield -1
        loop = infinite()

    for count in loop:
        with Transaction().start(database, 0) as transaction:
            with transaction.set_context(
                    User.get_preferences(context_only=True),
                    client_defined_date=connection_date, company=company):
                try:
                    with ServerContext().set_context(from_batch=True,
                            user_to_notify=kwargs.get('user'),
                            job_size=job_size,
                            transaction_size=transaction_size,
                            auto_accept_warnings=True):
                        for l in split_job(ids, transaction_size):
                            to_treat = BatchModel.convert_to_instances(l,
                                **batch_params)
                            r = BatchModel.execute(to_treat, [x[0] for x in l],
                                **batch_params)
                            res.append(r or len(l))
                            transaction.commit()
                        break
                except TransactionRollbackError:
                    if count:
                        transaction.rollback()
                        logger.info(
                            'Retrying job: %d attempts left' % count)
                        continue
                    logger.critical('Job execution crashed after %d retry'
                        % retry)
                    raise
                except Exception:
                    logger.critical('Job execution crashed')
                    raise
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
