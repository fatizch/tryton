import unittest
import doctest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_setup, doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'underwriting_claim_indemnification'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
        'scenario_underwriting_indemnification.rst',
        setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
