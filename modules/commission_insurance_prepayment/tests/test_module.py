import unittest
import doctest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework
from trytond.tests.test_tryton import doctest_setup, doctest_teardown


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'commission_insurance_prepayment'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_prepayment.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
