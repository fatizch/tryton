import unittest
import doctest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'contract_invoicing_duration'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
        'scenario_contract_invoicing_duration.rst', tearDown=doctest_teardown,
        encoding='utf-8', optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
