# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_setup, doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_insurance_invoice_dunning'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_contract_invoice_dunning.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
