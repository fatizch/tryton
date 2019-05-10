# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

from trytond.modules.api import APIMixin


def test_apis(klass):
    if not issubclass(klass, APIMixin):
        return
    access = {x.api[len(klass.__name__) + 1:]
        for x in Pool().get('ir.api.access').search([
                ('api', 'like', '%s%%' % klass.__name__)])}
    for name, api_data in klass._apis.items():
        if api_data['access_policy'] != 'public':
            assert name in access, 'Missing access right for api %s' % name


class ModuleTestCase(ModuleTestCase):
    'API Test Case'
    module = 'api'

    @with_transaction()
    def test_access_right(self):
        pool = Pool()
        Core = pool.get('api.core')
        test_apis(Core)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
