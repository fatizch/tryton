# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

from trytond.modules.api import APIMixin, api_input_error_manager, APIInputError


def test_apis(klass):
    if not issubclass(klass, APIMixin):
        return
    access = {x.api[len(klass.__name__) + 1:]
        for x in Pool().get('ir.api.access').search([
                ('api', 'like', '%s%%' % klass.__name__)])}
    for name, data in klass._apis.items():
        if data['access_policy'] != 'public':
            assert name in access, 'Missing access right for api %s' % name

        # Run examples
        for example in data['examples']:
            data['compiled_input_schema'](example['input'])
            data['compiled_output_schema'](example['output'])


class ModuleTestCase(ModuleTestCase):
    'API Test Case'
    module = 'api'

    @with_transaction()
    def test_access_right(self):
        pool = Pool()
        Core = pool.get('api.core')
        test_apis(Core)

    @with_transaction()
    def test_api_input_errors(self):
        API = Pool().get('api')

        try:
            with api_input_error_manager():
                API.add_input_error({'test': 'hello'})
                API.add_input_error({'test1': 'hello1'})
            raise Exception('Not raised')
        except APIInputError as e:
            self.assertEqual(e.data, [
                    {'test': 'hello'},
                    {'test1': 'hello1'},
                    ])

        try:
            with api_input_error_manager():
                API.add_input_error({'test': 'hello'})
                API.add_input_error({'test1': 'hello1'})
                raise Exception('Should be shadowed')
        except APIInputError as e:
            self.assertEqual(e.data, [
                    {'test': 'hello'},
                    {'test1': 'hello1'},
                    ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
