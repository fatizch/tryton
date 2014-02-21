import datetime
import unittest

from decimal import Decimal

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Billing module.
    '''

    @classmethod
    def get_module_name(cls):
        return 'billing_individual'

    @classmethod
    def depending_modules(cls):
        return ['company_cog']

    @classmethod
    def get_models(cls):
        return {
            'PaymentTerm': 'billing.payment.term',
            'PaymentTermLine': 'billing.payment.term.line',
            'Contract': 'contract',
            }

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test0010_payment_term_first_following_month(self):
        company = self.Company.search([])[0]
        payment_term = self.PaymentTerm()
        payment_term.name = 'Test First Following Month'
        payment_term.code = 'test_first_following_month'
        payment_term.base_frequency = 'monthly'
        payment_term.with_sync_date = True
        payment_term.split_method = 'equal'
        payment_term.sync_date = datetime.date(2012, 1, 1)
        payment_term.remaining_position = 'last_calc'
        payment_term.force_line_at_start = False
        payment_term.company = company
        payment_term.save()

        payment_term_line = self.PaymentTermLine()
        payment_term_line.add_calculated_period = True
        payment_term_line.amount = 0
        payment_term_line.number_of_periods = 1
        payment_term_line.type = 'prorata'
        payment_term_line.payment_term = payment_term
        payment_term_line.currency = company.currency
        payment_term_line.save()

        payment_term_line = self.PaymentTermLine()
        payment_term_line.add_calculated_period = False
        payment_term_line.day = 1
        payment_term_line.months = 1
        payment_term_line.type = 'fixed'
        payment_term_line.amount = 0
        payment_term_line.payment_term = payment_term
        payment_term_line.currency = company.currency
        payment_term_line.save()

    @test_framework.prepare_test(
        'billing_individual.test0010_payment_term_first_following_month')
    def test0011_computation_first_following_month(self):
        payment_term = self.PaymentTerm.search([
                ('code', '=', 'test_first_following_month')])[0]
        work_set = self.Contract.work_set_class()()
        work_set.period = (datetime.date(2013, 1, 1),
            datetime.date(2013, 12, 31))
        work_set.total_amount = Decimal(365)
        work_set.currency = payment_term.company.currency
        work_set.payment_date = 1
        lines = payment_term.compute(work_set)
        self.assertEqual(Decimal(365), sum(map(lambda x: x[1], lines)))

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test0012_payment_term_one_shot(self):
        company = self.Company.search([])[0]
        payment_term = self.PaymentTerm()
        payment_term.name = 'Test One Shot'
        payment_term.code = 'test_one_shot'
        payment_term.base_frequency = 'one_shot'
        payment_term.split_method = 'equal'
        payment_term.with_sync_date = False
        payment_term.remaining_position = 'first_calc'
        payment_term.force_line_at_start = False
        payment_term.company = company
        payment_term.save()

    @test_framework.prepare_test(
        'billing_individual.test0012_payment_term_one_shot')
    def test0013_computation_one_shot(self):
        payment_term = self.PaymentTerm.search([
                ('code', '=', 'test_one_shot')])[0]
        work_set = self.Contract.work_set_class()()
        work_set.period = (datetime.date(2013, 1, 1),
            datetime.date(2013, 12, 31))
        work_set.total_amount = Decimal(365)
        work_set.currency = payment_term.company.currency
        work_set.payment_date = 1
        lines = payment_term.compute(work_set)
        self.assertEqual(lines[0], (datetime.date(2013, 1, 1), Decimal(365)))
        work_set.period = (datetime.date(2014, 2, 15),
            datetime.date(2016, 11, 30))
        lines = payment_term.compute(work_set)
        self.assertEqual(lines[0], (datetime.date(2014, 2, 15), Decimal(365)))

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test0014_payment_term_monthly_exact(self):
        company = self.Company.search([])[0]
        payment_term = self.PaymentTerm()
        payment_term.name = 'Test Monthly Exact'
        payment_term.code = 'test_monthly_exact'
        payment_term.base_frequency = 'monthly'
        payment_term.with_sync_date = True
        payment_term.sync_date = datetime.date(2012, 1, 1)
        payment_term.remaining_position = 'last_calc'
        payment_term.force_line_at_start = True
        payment_term.split_method = 'proportional'
        payment_term.company = company
        payment_term.save()

    @test_framework.prepare_test(
        'billing_individual.test0014_payment_term_monthly_exact')
    def test0015_computation_monthly_exact(self):
        payment_term = self.PaymentTerm.search([
                ('code', '=', 'test_monthly_exact')])[0]
        work_set = self.Contract.work_set_class()()
        work_set.period = (datetime.date(2013, 1, 1),
            datetime.date(2013, 12, 31))
        work_set.total_amount = Decimal(365)
        work_set.currency = payment_term.company.currency
        work_set.payment_date = 1
        lines = payment_term.compute(work_set)
        self.assertEqual(lines, [
                (datetime.date(2013, 1, 1), Decimal('31.00')),
                (datetime.date(2013, 2, 1), Decimal('28.00')),
                (datetime.date(2013, 3, 1), Decimal('31.00')),
                (datetime.date(2013, 4, 1), Decimal('30.00')),
                (datetime.date(2013, 5, 1), Decimal('31.00')),
                (datetime.date(2013, 6, 1), Decimal('30.00')),
                (datetime.date(2013, 7, 1), Decimal('31.00')),
                (datetime.date(2013, 8, 1), Decimal('31.00')),
                (datetime.date(2013, 9, 1), Decimal('30.00')),
                (datetime.date(2013, 10, 1), Decimal('31.00')),
                (datetime.date(2013, 11, 1), Decimal('30.00')),
                (datetime.date(2013, 12, 1), Decimal('31.00'))])
        self.assertEqual(Decimal(365), sum(map(lambda x: x[1], lines)))
        work_set.period = (datetime.date(2013, 1, 12),
            datetime.date(2014, 1, 11))
        lines = payment_term.compute(work_set)
        self.assertEqual(lines, [
                (datetime.date(2013, 1, 12), Decimal('20.00')),
                (datetime.date(2013, 2, 1), Decimal('28.00')),
                (datetime.date(2013, 3, 1), Decimal('31.00')),
                (datetime.date(2013, 4, 1), Decimal('30.00')),
                (datetime.date(2013, 5, 1), Decimal('31.00')),
                (datetime.date(2013, 6, 1), Decimal('30.00')),
                (datetime.date(2013, 7, 1), Decimal('31.00')),
                (datetime.date(2013, 8, 1), Decimal('31.00')),
                (datetime.date(2013, 9, 1), Decimal('30.00')),
                (datetime.date(2013, 10, 1), Decimal('31.00')),
                (datetime.date(2013, 11, 1), Decimal('30.00')),
                (datetime.date(2013, 12, 1), Decimal('31.00')),
                (datetime.date(2014, 1, 1), Decimal('11.00'))])
        work_set.period = (datetime.date(2014, 1, 12),
            datetime.date(2015, 1, 11))
        work_set.total_amount = Decimal(366)
        lines = payment_term.compute(work_set)
        self.assertEqual(lines, [
                (datetime.date(2014, 1, 12), Decimal('20.05')),
                (datetime.date(2014, 2, 1), Decimal('28.08')),
                (datetime.date(2014, 3, 1), Decimal('31.08')),
                (datetime.date(2014, 4, 1), Decimal('30.08')),
                (datetime.date(2014, 5, 1), Decimal('31.08')),
                (datetime.date(2014, 6, 1), Decimal('30.08')),
                (datetime.date(2014, 7, 1), Decimal('31.08')),
                (datetime.date(2014, 8, 1), Decimal('31.08')),
                (datetime.date(2014, 9, 1), Decimal('30.08')),
                (datetime.date(2014, 10, 1), Decimal('31.08')),
                (datetime.date(2014, 11, 1), Decimal('30.08')),
                (datetime.date(2014, 12, 1), Decimal('31.08')),
                (datetime.date(2015, 1, 1), Decimal('11.07'))])
        self.assertEqual(Decimal(366), sum(map(lambda x: x[1], lines)))
        work_set.period = (datetime.date(2016, 1, 12),
            datetime.date(2017, 1, 11))
        lines = payment_term.compute(work_set)
        self.assertEqual(Decimal(366), sum(map(lambda x: x[1], lines)))
        self.assertEqual(lines, [
                (datetime.date(2016, 1, 12), Decimal('20.00')),
                (datetime.date(2016, 2, 1), Decimal('29.00')),
                (datetime.date(2016, 3, 1), Decimal('31.00')),
                (datetime.date(2016, 4, 1), Decimal('30.00')),
                (datetime.date(2016, 5, 1), Decimal('31.00')),
                (datetime.date(2016, 6, 1), Decimal('30.00')),
                (datetime.date(2016, 7, 1), Decimal('31.00')),
                (datetime.date(2016, 8, 1), Decimal('31.00')),
                (datetime.date(2016, 9, 1), Decimal('30.00')),
                (datetime.date(2016, 10, 1), Decimal('31.00')),
                (datetime.date(2016, 11, 1), Decimal('30.00')),
                (datetime.date(2016, 12, 1), Decimal('31.00')),
                (datetime.date(2017, 1, 1), Decimal('11.00'))])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
