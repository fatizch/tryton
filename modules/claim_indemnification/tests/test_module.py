# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest

import trytond.tests.test_tryton
from trytond.modules.cog_utils import test_framework
from trytond.tests.test_tryton import doctest_setup, doctest_teardown


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'claim_indemnification'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
        'scenario_indemnification.rst',
        setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
