# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_setup, doctest_teardown

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'account_payment_clearing_cog'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_payment_clearing_cog.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
