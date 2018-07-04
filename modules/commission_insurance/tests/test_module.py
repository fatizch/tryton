# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from decimal import Decimal
import mock

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'commission_insurance'

    @classmethod
    def get_models(cls):
        return {
            'Commission': 'commission',
            'Plan': 'commission.plan',
            'PlanDate': 'commission.plan.date',
            'Agent': 'commission.agent',
            'Invoice': 'account.invoice',
            'InvoiceLine': 'account.invoice.line',
            'InvoiceLineDetail': 'account.invoice.line.detail',
            'Currency': 'currency.currency',
            }

    def test0001_get_commission_periods(self):
        plan = self.Plan()
        invoice_line = mock.Mock()
        plan.get_commission_dates = mock.MagicMock(return_value=[
                datetime.date(2000, 1, 1), datetime.date(2000, 1, 16),
                datetime.date(2000, 1, 31)])
        self.assertEqual(self.Plan.get_commission_periods(plan, invoice_line),
            [(datetime.date(2000, 1, 1), datetime.date(2000, 1, 15)),
                (datetime.date(2000, 1, 16), datetime.date(2000, 1, 31))])

    def test0010_base_amount_computation(self):
        plan = mock.Mock()
        plan.get_commission_periods = mock.MagicMock(return_value=[
                (datetime.date(2000, 1, 1), datetime.date(2000, 1, 15)),
                (datetime.date(2000, 1, 16), datetime.date(2000, 1, 31))])
        plan.commission_product = None
        agent = self.Agent()
        agent.currency = None

        invoice = self.Invoice()
        invoice.currency = None
        invoice.currency_date = None
        invoice.type = 'in'

        invoice_line = self.InvoiceLine()
        invoice_line.invoice = invoice
        invoice_line.amount = Decimal(310)
        invoice_line.coverage_start = datetime.date(2000, 1, 1)
        invoice_line.coverage_end = datetime.date(2000, 1, 31)
        invoice_line.currency_digits = 2
        detail = self.InvoiceLineDetail()
        invoice_line.details = [detail]
        detail.get_option = mock.MagicMock(return_value=None)

        with mock.patch.object(self.Currency, 'compute',
                return_value=Decimal(310)):
            # Same rate => two lines
            invoice_line._get_commission_amount = mock.Mock(
                side_effect=[Decimal(15), Decimal(16)])
            commissions = invoice_line.get_commissions_for_agent(agent, plan)
            self.assertEqual([tuple(x) for x in
                invoice_line._get_commission_amount.call_args_list], [
                    ((150, plan), {
                            'pattern': {
                                'agent': agent,
                                'date_start': datetime.date(2000, 1, 1),
                                'date_end': datetime.date(2000, 1, 15)}}),
                    ((160, plan), {
                            'pattern': {
                                'agent': agent,
                                'date_start': datetime.date(2000, 1, 16),
                                'date_end': datetime.date(2000, 1, 31)}}),
                    ])
            self.assertEqual(len(commissions), 2)
            self.assertEqual(commissions[0].commission_rate, Decimal('.1'))
            self.assertEqual(commissions[0].start, datetime.date(2000, 1, 1))
            self.assertEqual(commissions[0].end, datetime.date(2000, 1, 15))
            self.assertEqual(commissions[0].amount, Decimal('15'))
            self.assertEqual(commissions[1].commission_rate, Decimal('.1'))
            self.assertEqual(commissions[1].start, datetime.date(2000, 1, 16))
            self.assertEqual(commissions[1].end, datetime.date(2000, 1, 31))
            self.assertEqual(commissions[1].amount, Decimal('16'))

            # Different rate => two lines
            invoice_line._get_commission_amount = mock.Mock(
                side_effect=[Decimal(75), Decimal(16)])
            commissions = invoice_line.get_commissions_for_agent(agent, plan)
            self.assertEqual(
                invoice_line._get_commission_amount.call_args_list, [
                    ((150, plan), {
                            'pattern': {
                                'agent': agent,
                                'date_start': datetime.date(2000, 1, 1),
                                'date_end': datetime.date(2000, 1, 15)}}),
                    ((160, plan), {
                            'pattern': {
                                'agent': agent,
                                'date_start': datetime.date(2000, 1, 16),
                                'date_end': datetime.date(2000, 1, 31)}}),
                    ])
            self.assertEqual(len(commissions), 2)
            self.assertEqual(commissions[0].commission_rate, Decimal('.5'))
            self.assertEqual(commissions[0].start, datetime.date(2000, 1, 1))
            self.assertEqual(commissions[0].end, datetime.date(2000, 1, 15))
            self.assertEqual(commissions[0].amount, Decimal('75'))
            self.assertEqual(commissions[1].commission_rate, Decimal('.1'))
            self.assertEqual(commissions[1].start, datetime.date(2000, 1, 16))
            self.assertEqual(commissions[1].end, datetime.date(2000, 1, 31))
            self.assertEqual(commissions[1].amount, Decimal('16'))

    def test0020_date_calculations(self):
        invoice_line = mock.Mock()
        invoice_line.coverage_start = datetime.date(2000, 12, 31)
        invoice_line.coverage_end = datetime.date(2004, 1, 1)

        date_line = self.PlanDate()
        date_line.frequency = 'yearly'

        # Test empty
        date_line.get_reference_date = mock.MagicMock(return_value=None)
        self.assertEqual(date_line.get_dates(invoice_line), set())

        date_line.get_reference_date = mock.MagicMock(
            return_value=datetime.date(2000, 1, 1))

        # Test absolute
        date_line.type_ = 'absolute'
        date_line.month = '4'
        date_line.day = '10'

        date_line.first_match_only = True
        # Nothing matches, the first occurence is 2000-4-10 which is not in the
        # invoice line period
        self.assertEqual(date_line.get_dates(invoice_line), set())

        date_line.first_match_only = False
        self.assertEqual(date_line.get_dates(invoice_line), set([
                    datetime.date(2001, 4, 10), datetime.date(2002, 4, 10),
                    datetime.date(2003, 4, 10)]))

        # Test relative
        date_line.type_ = 'relative'
        date_line.year = '1'
        date_line.month = '2'
        date_line.day = '3'

        date_line.first_match_only = True
        self.assertEqual(date_line.get_dates(invoice_line),
            set([datetime.date(2001, 3, 4)]))

        date_line.first_match_only = False
        self.assertEqual(date_line.get_dates(invoice_line), set([
                    datetime.date(2001, 3, 4), datetime.date(2002, 5, 7),
                    datetime.date(2003, 7, 10)]))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_commission_insurance.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
