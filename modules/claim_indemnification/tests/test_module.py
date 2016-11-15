# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest
import datetime

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_setup, doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'claim_indemnification'

    @classmethod
    def get_models(cls):
        return {
            'Service': 'claim.service',
            }

    def test0010_test_annuity_period_computation(self):
        service = self.Service()
        service.annuity_frequency = 'monthly'
        self.assertEqual(service.calculate_annuity_periods(
                datetime.date(2016, 1, 1), datetime.date(2016, 1, 31)),
            [(datetime.date(2016, 1, 1), datetime.date(2016, 1, 31), True, 1,
                'month')])
        self.assertEqual(service.calculate_annuity_periods(
                datetime.date(2016, 1, 15), datetime.date(2016, 1, 31)),
            [(datetime.date(2016, 1, 15), datetime.date(2016, 1, 31), False,
                17, 'day')])
        service.annuity_frequency = 'quarterly'
        self.assertEqual(service.calculate_annuity_periods(
                datetime.date(2016, 1, 1), datetime.date(2016, 3, 31)),
            [(datetime.date(2016, 1, 1), datetime.date(2016, 3, 31), True, 3,
                'quarter')])
        self.assertEqual(service.calculate_annuity_periods(
                datetime.date(2016, 1, 15), datetime.date(2016, 6, 30)),
            [(datetime.date(2016, 1, 15), datetime.date(2016, 3, 31), False,
                77, 'day'), (datetime.date(2016, 4, 1),
                datetime.date(2016, 6, 30), True, 3, 'quarter')])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
        'scenario_indemnification.rst',
        setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
