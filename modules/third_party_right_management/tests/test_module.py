# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    module = 'third_party_right_management'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
        'scenario_right_management.rst',
        tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
        'scenario_right_management_renewal.rst',
        tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
        'scenario_right_management_endorsement.rst',
        tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
