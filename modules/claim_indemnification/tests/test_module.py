# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest
import datetime

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'claim_indemnification'

    @classmethod
    def get_models(cls):
        return {
            'Service': 'claim.service',
            'Runtime': 'rule_engine.runtime',
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

    def test0020_test_re_revaluation_pivot_dates(self):
        start_date = datetime.date(2000, 1, 31)
        end_date = datetime.date(2002, 2, 15)
        d = datetime.date
        for (start_date, end_date, freq, month_sync, day_sync), expected in [
                (
                    (d(2000, 1, 31), d(2002, 2, 15), 'YEARLY', 6, 30),
                    [d(2000, 6, 30), d(2001, 6, 30)]
                ),
                (
                    (d(2000, 1, 31), d(2000, 2, 15), 'MONTHLY', 1, 1),
                    [d(2000, 1, 1), d(2000, 2, 1)]
                ),
                    ]:
            self.assertEqual(
                self.Runtime._re_revaluation_pivot_dates(
                    None, start_date, end_date, freq, month_sync, day_sync),
                expected, str(expected))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
        'scenario_indemnification.rst',
        tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
