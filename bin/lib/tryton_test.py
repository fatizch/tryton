import os
import time
import unittest
from rq import get_current_job
import async.broker_rq as broker


def test(module, options=None):
    options = options or {}
    opts = {'doc': True, 'failfast': False, 'verbosity': 5}
    opts.update(options)
    from trytond import backend
    if backend.name() == 'sqlite':
        database_name = ':memory:'
    else:
        database_name = 'test_%s_%s' % (module, str(int(time.time())))
    os.environ.setdefault('DB_NAME', database_name)
    from trytond.tests.test_tryton import modules_suite
    suite = modules_suite([module], doc=opts['doc'])
    result = unittest.TextTestRunner(
        verbosity=opts['verbosity'], failfast=opts['failfast']).run(suite)
    job = get_current_job(connection=broker.connection)
    broker.log_result(job, {'total': result.testsRun,
            'errors': len(result.errors), 'fails': len(result.failures),
            'details': '\n\n'.join('%s\n%s' % (repr(x[0]), x[1])
                for x in result.failures)})

    assert result.wasSuccessful()
