# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import mock
import datetime
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_setup, doctest_teardown

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_loan_invoice'

    @classmethod
    def get_models(cls):
        return {
            'Contract': 'contract',
            'Premium': 'contract.premium',
            'ExtraPremium': 'contract.option.extra_premium',
            'Coverage': 'offered.option.description',
            'Loan': 'loan',
            }

    def test001_store_prices(self):
        loan1 = self.Loan()
        loan2 = self.Loan()
        extra_premium = self.ExtraPremium(premiums=[])
        start1 = datetime.date(2000, 1, 1)
        end1 = datetime.date(2000, 11, 30)
        start2 = datetime.date(2000, 12, 1)
        end2 = datetime.date(2000, 12, 31)
        coverage = self.Coverage()
        premium1_1 = self.Premium(loan=loan1, amount=200, parent=extra_premium,
            start=start1, end=end1, rated_entity=coverage, frequency='monthly',
            account=None)
        premium1_2 = self.Premium(loan=loan1, amount=100, parent=extra_premium,
            start=start2, end=end2, rated_entity=coverage, frequency='monthly',
            account=None)
        premium2_1 = self.Premium(loan=loan2, amount=100, parent=extra_premium,
            start=start1, end=end1, rated_entity=coverage, frequency='monthly',
            account=None)
        premium2_2 = self.Premium(loan=loan2, amount=200, parent=extra_premium,
            start=start2, end=end2, rated_entity=coverage, frequency='monthly',
            account=None)
        with mock.patch.object(self.Contract, 'new_premium_from_price') as \
                new_premiums, mock.patch.object(self.Premium, 'save') as \
                patched_save:
            all_premiums = [premium1_1, premium1_2, premium2_1, premium2_2]
            new_premiums.return_value = all_premiums
            self.Contract.store_prices({None: [premium1_1]})
            patched_save.assert_called_with(all_premiums)
            self.assertEqual([(x.loan, x.start, x.end) for x in all_premiums],
                [(loan1, start1, end1), (loan1, start2, end2),
                    (loan2, start1, end1), (loan2, start2, end2)])

    def test002_store_prices_merge(self):
        loan1 = self.Loan()
        loan2 = self.Loan()
        extra_premium = self.ExtraPremium(premiums=[])
        start1 = datetime.date(2000, 1, 1)
        end1 = datetime.date(2000, 11, 30)
        start2 = datetime.date(2000, 12, 1)
        end2 = datetime.date(2000, 12, 31)
        coverage = self.Coverage()
        premium1_1 = self.Premium(loan=loan1, amount=100, parent=extra_premium,
            start=start1, end=end1, rated_entity=coverage, frequency='monthly',
            account=None)
        premium1_2 = self.Premium(loan=loan1, amount=100, parent=extra_premium,
            start=start2, end=end2, rated_entity=coverage, frequency='monthly',
            account=None)
        premium2_1 = self.Premium(loan=loan2, amount=100, parent=extra_premium,
            start=start1, end=end1, rated_entity=coverage, frequency='monthly',
            account=None)
        premium2_2 = self.Premium(loan=loan2, amount=200, parent=extra_premium,
            start=start2, end=end2, rated_entity=coverage, frequency='monthly',
            account=None)
        with mock.patch.object(self.Contract, 'new_premium_from_price') as \
                new_premiums, mock.patch.object(self.Premium, 'save') as \
                patched_save:
            all_premiums = [premium1_1, premium1_2, premium2_1, premium2_2]
            new_premiums.return_value = all_premiums
            self.Contract.store_prices({None: [premium1_1]})
            saved = [premium1_1, premium2_1, premium2_2]
            patched_save.assert_called_with(saved)
            self.assertEqual([(x.loan, x.start, x.end) for x in saved],
                [(loan1, start1, end2), (loan2, start1, end1),
                    (loan2, start2, end2)])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_loan_contract.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
