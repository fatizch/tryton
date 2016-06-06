import unittest
import doctest
import datetime
import mock

from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

from trytond.transaction import Transaction

import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_setup, doctest_teardown

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'contract_insurance_invoice'

    @classmethod
    def depending_modules(cls):
        return ['company_cog', 'currency_cog']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Contract': 'contract',
            'Premium': 'contract.premium',
            'Sequence': 'ir.sequence',
            'SequenceType': 'ir.sequence.type',
            'Account': 'account.account',
            'AccountKind': 'account.account.type',
            'Product': 'offered.product',
            'PaymentTerm': 'account.invoice.payment_term',
            'BillingInformation': 'contract.billing_information',
            'BillingMode': 'offered.billing_mode',
            'Company': 'company.company',
            'MoveLine': 'account.move.line',
            'User': 'res.user',
            'Configuration': 'account.configuration',
            'OfferedConfiguration': 'offered.configuration',
            'PaymentJournal': 'account.payment.journal',
            'Reconciliation': 'account.move.reconciliation',
            }

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test_premium_get_amount(self):
        'Test Premium.get_amount'
        company, = self.Company.search([
                ('rec_name', '=', 'World Company'),
                ])
        config = self.OfferedConfiguration(1)
        contract = self.Contract()
        contract.start_date = date(2011, 10, 21)
        contract.company = company
        premium_monthly = self.Premium(
            frequency='monthly',
            amount=Decimal(100),
            main_contract=contract,
            )

        for period, amount in (
                ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 16), date(2014, 1, 31)), Decimal(100) *
                    Decimal(16) / Decimal(31)),
                ((date(2014, 1, 1), date(2014, 2, 28)), Decimal(200)),
                ((date(2014, 1, 1), date(2014, 3, 31)), Decimal(300)),
                ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(1200)),
                ((date(2014, 1, 15), date(2014, 2, 23)), Decimal(100) +
                    Decimal(100) * Decimal(9) / Decimal(28)),
                ):
            self.assertEqual(premium_monthly.get_amount(*period), amount)

        config._prorate_cache.set('prorate', False)
        for period, expected in (
                ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 16), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2014, 2, 28)), Decimal(200)),
                ((date(2014, 1, 1), date(2014, 3, 31)), Decimal(300)),
                ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(1200)),
                ((date(2014, 1, 15), date(2014, 2, 23)), Decimal(200)),
                ):
            res = premium_monthly.get_amount(*period)
            self.assertEqual(res, expected, 'Expected %s , got %s '
                    'for period %s ' % (expected, res, period))

        config._prorate_cache.set('prorate', True)
        premium_yearly = self.Premium(
            frequency='yearly',
            amount=Decimal(100),
            main_contract=contract,
            )
        for period, amount in (
                ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2014, 1, 31)),
                    Decimal(100) * Decimal(31) / Decimal(365)),
                ((date(2014, 1, 1), date(2015, 12, 31)), Decimal(200)),
                ):
            self.assertEqual(premium_yearly.get_amount(*period), amount)

        config._prorate_cache.set('prorate', False)
        for period, expected in (
                ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2015, 1, 1)), Decimal(200)),
                ((date(2014, 1, 1), date(2015, 6, 1)), Decimal(200)),
                ):
            res = premium_yearly.get_amount(*period)
            self.assertEqual(res, expected, 'Expected %s , got %s '
                    'for period %s ' % (expected, res, period))
        config._prorate_cache.set('prorate', True)

        # Test leap years
        for period, amount in (
                ((date(2015, 2, 1), date(2016, 1, 31)), Decimal(100)),
                ((date(2015, 3, 1), date(2016, 2, 29)), Decimal(100)),
                ((date(2016, 1, 1), date(2016, 1, 31)),
                    Decimal(100) * Decimal(31) / Decimal(365)),
                ((date(2017, 1, 1), date(2017, 1, 31)),
                    Decimal(100) * Decimal(31) / Decimal(366)),
                ((date(2016, 1, 1), date(2017, 1, 31)),
                    Decimal(100) +
                    Decimal(100) * Decimal(31) / Decimal(366)),
                ):
            self.assertEqual(premium_yearly.get_amount(*period), amount)

        premium_one = self.Premium(
            frequency='once_per_contract',
            amount=Decimal(100),
            start=date(2014, 1, 1),
            main_contract=contract,
            )
        for period, amount in (
                ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2015, 12, 31)), Decimal(100)),
                ((date(2014, 2, 1), date(2014, 2, 28)), Decimal(0)),
                ):
            self.assertEqual(premium_one.get_amount(*period), amount)

        premium_signature = self.Premium(
            frequency='at_contract_signature',
            amount=Decimal(900),
            main_contract=contract,
            )
        for period, amount in (
                ((None, None), Decimal(900)),
                ((date(2014, 1, 1), date(2015, 12, 31)), Decimal(0)),
                ((date(2014, 2, 1), date(2014, 2, 28)), Decimal(0)),
                ):
            self.assertEqual(premium_signature.get_amount(*period), amount)

        premium_once_per_year = self.Premium(
            frequency='once_per_year',
            amount=Decimal(100),
            main_contract=contract,
            )
        for period, amount in (
                ((date(2015, 10, 1), date(2015, 10, 22)), Decimal(100)),
                ((date(2015, 10, 1), date(2015, 10, 21)), Decimal(100)),
                ((date(2015, 10, 1), date(2015, 10, 20)), Decimal(0)),
                ((date(2015, 10, 1), date(2017, 10, 21)), Decimal(300)),
                ):
            self.assertEqual(premium_once_per_year.get_amount(*period), amount)

        contract.start_date = date(2012, 2, 29)
        for period, amount in (
                ((date(2015, 2, 1), date(2015, 3, 1)), Decimal(100)),
                ((date(2015, 2, 1), date(2015, 2, 28)), Decimal(100)),
                ((date(2015, 2, 1), date(2015, 2, 27)), Decimal(0)),
                ((date(2016, 2, 1), date(2016, 3, 1)), Decimal(100)),
                ((date(2016, 2, 1), date(2016, 2, 29)), Decimal(100)),
                ((date(2016, 2, 1), date(2016, 2, 28)), Decimal(0)),
                ):
            self.assertEqual(premium_once_per_year.get_amount(*period), amount)

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test_contract_get_invoice_periods(self):
        'Test Contract get_invoice_periods'

        company, = self.Company.search([
                ('rec_name', '=', 'World Company'),
                ])
        self.User.write([self.User(Transaction().user)], {
                'main_company': company.id,
                'company': company.id,
                })
        payment_term, = self.PaymentTerm.create([{
                    'name': 'direct',
                    'lines': [('create', [{}])],
                    }])
        freq_month, freq_quart, freq_once = self.BillingMode.create([{
                'code': 'monthly',
                'name': 'monthly',
                'frequency': 'monthly',
                'allowed_payment_terms': [
                        ('add', [payment_term.id])]
                }, {
                'code': 'quarterly',
                'name': 'quarterly',
                'frequency': 'quarterly',
                'allowed_payment_terms': [
                        ('add', [payment_term.id])],
                'direct_debit': True,
                'allowed_direct_debit_days': '5, 10, 15'
                }, {
                'code': 'once_per_contract',
                'name': 'once_per_contract',
                'frequency': 'once_per_contract',
                'allowed_payment_terms': [
                        ('add', [payment_term.id])]
                }])
        sequence_code, = self.SequenceType.create([{
                    'name': 'Product sequence',
                    'code': 'contract',
                    }])
        sequence, quote_sequence = self.Sequence.create([{
                    'name': 'Contract sequence',
                    'code': sequence_code.code,
                    'company': company.id,
                    }, {
                    'name': 'Quote Sequence',
                    'code': 'quote',
                    'company': company.id,
                    }])
        account_kind, = self.AccountKind.create([{
                    'name': 'Product',
                    'company': company.id,
                    }])
        account, = self.Account.create([{
                    'name': 'Account for Product',
                    'code': 'Account for Product',
                    'kind': 'revenue',
                    'company': company.id,
                    'type': account_kind.id,
                    }])
        product, = self.Product.create([{'company': company.id,
                    'name': 'Test Product',
                    'code': 'test_product',
                    'start_date': date(2014, 1, 1),
                    'billing_modes': [
                        ('add', [freq_month.id, freq_quart.id,
                                freq_once.id])],
                    'contract_generator': sequence.id,
                    'quote_number_sequence': quote_sequence.id,
                    }])
        contract = self.Contract(company=company,
            start_date=date(2014, 4, 15),
            product=product,
            billing_informations=[
                self.BillingInformation(date=None,
                    billing_mode=freq_month,
                    payment_term=payment_term),
                self.BillingInformation(date=date(2014, 7, 1),
                    billing_mode=freq_quart,
                    direct_debit_day=5,
                    payment_term=payment_term),
                ],
            )
        contract.save()
        self.assertEqual(contract.start_date, date(2014, 4, 15))
        self.assertEqual(contract.get_invoice_periods(date(2014, 1, 1)),
            [])
        self.assertEqual(contract.get_invoice_periods(date(2014, 5, 1)),
            [(date(2014, 4, 15), date(2014, 5, 14),
                contract.billing_informations[0])])
        self.assertEqual(contract.get_invoice_periods(date(2014, 8, 1)),
            [(date(2014, 4, 15), date(2014, 5, 14),
                contract.billing_informations[0]),
                (date(2014, 5, 15), date(2014, 6, 14),
                    contract.billing_informations[0]),
                (date(2014, 6, 15), date(2014, 6, 30),
                    contract.billing_informations[0]),
                (date(2014, 7, 1), date(2014, 9, 30),
                    contract.billing_informations[1])])

        contract = self.Contract(company=company,
            start_date=date(2014, 4, 15),
            product=product,
            billing_informations=[
                self.BillingInformation(date=None,
                    billing_mode=freq_once),
                ])
        contract.save()
        self.assertEqual(contract.get_invoice_periods(date(2014, 1, 1)),
            [])
        self.assertEqual(contract.get_invoice_periods(date(2014, 4, 16)),
            [(date(2014, 4, 15), date.max + relativedelta(days=-1),
                contract.billing_informations[0])])

        contract = self.Contract(company=company,
            start_date=date(2014, 1, 1),
            product=product,
            billing_informations=[
                self.BillingInformation(date=None,
                    billing_mode=freq_quart,
                    direct_debit_day=5,
                    payment_term=payment_term),
                self.BillingInformation(date=date(2014, 1, 5),
                    billing_mode=freq_month,
                    payment_term=payment_term),
                ])
        contract.save()
        self.assertEqual(contract.get_invoice_periods(date(2014, 1, 1)), [(
                    date(2014, 1, 1), date(2014, 1, 4),
                    contract.billing_informations[0])])

        contract = self.Contract(company=company,
            start_date=date(2014, 1, 1),
            product=product,
            billing_informations=[
                self.BillingInformation(date=None,
                    billing_mode=freq_month,
                    payment_term=payment_term),
                self.BillingInformation(date=date(2014, 1, 5),
                    billing_mode=freq_month,
                    payment_term=payment_term),
                ])
        contract.save()
        self.assertEqual(contract.get_invoice_periods(date(2014, 1, 1)), [(
                    date(2014, 1, 1), date(2014, 1, 31),
                    contract.billing_informations[0])])

    def test_get_direct_debit_day(self):
        current_date = date(2014, 9, 1)
        with Transaction().set_context(client_defined_date=current_date):
            payment_journal = self.PaymentJournal()
            line = self.MoveLine(maturity_date=date(2014, 9, 1))
            self.assertEqual(
                payment_journal.get_next_possible_payment_date(line, 5),
                date(2014, 9, 5))
            line = self.MoveLine(maturity_date=date(2014, 9, 5))
            self.assertEqual(
                payment_journal.get_next_possible_payment_date(line, 5),
                date(2014, 9, 5))
            line = self.MoveLine(maturity_date=date(2014, 8, 5))
            self.assertEqual(
                payment_journal.get_next_possible_payment_date(line, 5),
                date(2014, 9, 5))
            line = self.MoveLine(maturity_date=date(2014, 9, 30))
            self.assertEqual(
                payment_journal.get_next_possible_payment_date(line, 5),
                date(2014, 10, 5))

    def test0050_propagate_contract_move_line(self):
        from trytond.modules.account.move import Line as SuperLine
        with mock.patch.object(SuperLine, 'write') as super_write:
            lines = [mock.Mock()]
            values = {'reconciliation': 16}
            self.MoveLine.write(lines, values)
            super_write.assert_called_with(lines, {
                    'reconciliation': 16})

        with mock.patch.object(SuperLine, 'write') as super_write:
            lines = [mock.Mock()]
            lines[0].contract = 10
            values = {'reconciliation': 16}
            self.MoveLine.write(lines, values)
            super_write.assert_called_with(lines, {
                    'reconciliation': 16})

        with mock.patch.object(SuperLine, 'write') as super_write:
            lines = [mock.Mock(), mock.Mock()]
            lines[0].contract = 10
            lines[1].contract = None
            values = {'reconciliation': 16}
            self.MoveLine.write(lines, values)
            super_write.assert_called_with(lines, {
                    'reconciliation': 16,
                    'contract': 10})

        with mock.patch.object(SuperLine, 'write') as super_write:
            lines = [mock.Mock(), mock.Mock(), mock.Mock()]
            lines[0].contract = 10
            lines[1].contract = 11
            lines[2].contract = None
            values = {'reconciliation': 16}
            self.MoveLine.write(lines, values)
            super_write.assert_called_with(lines, {
                    'reconciliation': 16})

        with mock.patch.object(SuperLine, 'write') as super_write:
            lines = [mock.Mock(), mock.Mock(), mock.Mock()]
            lines[0].contract = 10
            lines[1].contract = 10
            lines[2].contract = None
            values = {'reconciliation': 16}
            self.MoveLine.write(lines, values)
            super_write.assert_called_with(lines, {
                    'reconciliation': 16,
                    'contract': 10})

        with mock.patch.object(SuperLine, 'write') as super_write:
            lines_1 = [mock.Mock(), mock.Mock(), mock.Mock()]
            lines_1[0].contract = 10
            lines_1[1].contract = 10
            lines_1[2].contract = None
            values_1 = {'reconciliation': 16}
            lines_2 = [mock.Mock(), mock.Mock()]
            lines_2[0].contract = None
            lines_2[1].contract = 5
            values_2 = {'something': 10}
            lines_3 = [mock.Mock(), mock.Mock(), mock.Mock()]
            lines_3[0].contract = None
            lines_3[1].contract = 4
            lines_3[2].contract = None
            values_3 = {'reconciliation': 4, 'something': 31}
            self.MoveLine.write(lines_1, values_1, lines_2, values_2, lines_3,
                values_3)
            super_write.assert_called_with(lines_1, {
                    'reconciliation': 16,
                    'contract': 10}, lines_2, values_2, lines_3, {
                    'reconciliation': 4,
                    'something': 31,
                    'contract': 4})

    def test0060_test_reconciliation(self):
        contract = self.Contract(123)
        subscriber = self.Party(456)
        account = self.Account(789)
        contract.subscriber = subscriber
        contract.subscriber.account_receivable = account

        line_invoice_1 = mock.Mock()
        line_invoice_1.origin = mock.Mock()
        line_invoice_1.origin.__name__ = 'account.invoice'
        line_invoice_1.origin.start = datetime.date(2020, 1, 1)
        line_invoice_1.debit = 10
        line_invoice_1.credit = 0
        line_invoice_1.contract = contract

        line_invoice_2 = mock.Mock()
        line_invoice_2.origin = mock.Mock()
        line_invoice_2.origin.__name__ = 'account.invoice'
        line_invoice_2.origin.start = datetime.date(2020, 2, 1)
        line_invoice_2.date = datetime.date(2020, 1, 1)
        line_invoice_2.debit = 10
        line_invoice_2.credit = 0
        line_invoice_2.contract = contract

        line_to_pay = mock.Mock()
        line_to_pay.origin = mock.Mock()
        line_to_pay.origin.__name__ = 'random'
        line_to_pay.date = datetime.date(2020, 1, 15)
        line_to_pay.debit = 10
        line_to_pay.credit = 0
        line_to_pay.contract = contract

        line_pay_1 = mock.Mock()
        line_pay_1.origin = mock.Mock()
        line_pay_1.origin.__name__ = 'random'
        line_pay_1.date = datetime.date(2020, 1, 1)
        line_pay_1.debit = 0
        line_pay_1.credit = 10
        line_pay_1.contract = contract

        line_pay_2 = mock.Mock()
        line_pay_2.origin = mock.Mock()
        line_pay_2.origin.__name__ = 'random'
        line_pay_2.date = datetime.date(2020, 2, 1)
        line_pay_2.debit = 0
        line_pay_2.credit = 10
        line_pay_2.contract = contract

        line_pay_3 = mock.Mock()
        line_pay_3.origin = mock.Mock()
        line_pay_3.origin.__name__ = 'random'
        line_pay_3.date = datetime.date(2019, 12, 1)
        line_pay_3.debit = 0
        line_pay_3.credit = 5
        line_pay_3.contract = contract

        patched_search = mock.MagicMock(return_value=[
                line_invoice_1, line_invoice_2, line_to_pay, line_pay_1,
                line_pay_2, line_pay_3])
        patched_split = mock.MagicMock()

        with mock.patch.object(self.MoveLine, 'search', patched_search), \
                mock.patch.object(self.MoveLine, 'split_lines', patched_split):
            # Basic check : nothing to reconcile, check perfect reconciliation
            # is properly handled. ([1, 2], 0) is an arbitrary result, which is
            # expected to be returned "as is" by get_lines_to_reconcile
            contract.reconcile_perfect_lines = mock.MagicMock(
                return_value=([([1, 2], 0)], [line_invoice_1]))
            self.assertEqual([[1, 2]], self.Contract.get_lines_to_reconcile(
                    [contract]))
            contract.reconcile_perfect_lines.assert_called_with(
                [line_invoice_1, line_invoice_2, line_to_pay, line_pay_1,
                    line_pay_2, line_pay_3])
            patched_search.assert_called_with([
                    ('reconciliation', '=', None),
                    ('date', '<=', datetime.date.today()),
                    ('move_state', 'not in', ('draft', 'validated')),
                    ['OR', [
                            ('party', '=', 456),
                            ('account', '=', 789),
                            ('contract', 'in', [123])]]],
                order=[('contract', 'ASC')])

            def test_reco(lines, reconciliations):
                contract.reconcile_perfect_lines = mock.MagicMock(
                    return_value=([], lines))
                self.assertEqual(reconciliations,
                    self.Contract.get_lines_to_reconcile([contract]))

            # Test perfectly matched lines are reconciled
            test_reco([line_invoice_1, line_pay_1],
                [[line_invoice_1, line_pay_1]])

            # Check ordering on invoice effective dates
            test_reco([line_invoice_1, line_invoice_2, line_pay_1],
                [[line_invoice_1, line_pay_1]])
            test_reco([line_invoice_2, line_invoice_1, line_pay_1],
                [[line_invoice_1, line_pay_1]])

            # Check multiple line reconciliation
            test_reco([line_invoice_1, line_pay_1, line_pay_2],
                [[line_invoice_1, line_pay_1]])
            test_reco([line_invoice_1, line_invoice_2, line_pay_1, line_pay_2],
                [[line_invoice_1, line_invoice_2, line_pay_1, line_pay_2]])

            # Check that line_to_pay is reconciled before line_invoice_2
            test_reco([line_invoice_1, line_invoice_2, line_pay_1, line_pay_2,
                    line_to_pay],
                [[line_invoice_1, line_to_pay, line_pay_1, line_pay_2]])

            # Check payment splitting
            remaining = mock.Mock()
            compensation = mock.Mock()
            patched_split.return_value = {
                line_pay_1: (line_pay_1, remaining, compensation)}

            test_reco([line_invoice_1, line_pay_1, line_pay_3],
                [[line_invoice_1, line_pay_3, line_pay_1, remaining,
                        compensation]])

            # Check splits applies on right line
            test_reco([line_invoice_1, line_pay_1, line_pay_3, line_invoice_2],
                [[line_invoice_1, line_pay_3, line_pay_1, remaining,
                        compensation]])

            # Check no splits on debit lines
            test_reco([line_invoice_1, line_pay_3], [])

    def test0070_test_perfect_reconciliation(self):
        contract = self.Contract()

        invoice_1 = mock.Mock()
        invoice_1.__name__ = 'account.invoice'

        base_move = mock.Mock()
        base_move.__name__ = 'account.move'
        base_move.origin = invoice_1

        cancel_move = mock.Mock()
        cancel_move.__name__ = 'account.move'
        cancel_move.origin = base_move

        invoice_1.move = base_move
        invoice_1.cancel_move = cancel_move

        payment = mock.Mock()
        payment.__name__ = 'account.payment'
        payment.line = mock.Mock()
        payment.line.origin = invoice_1

        line_no_origin = mock.Mock()
        line_no_origin.origin = None

        line_random_origin = mock.Mock()
        line_random_origin.origin = mock.Mock()
        line_random_origin.origin.__name__ = 'random'

        line_base = mock.Mock()
        line_base.origin = invoice_1
        line_base.amount = 10
        line_base.move = base_move

        line_cancel_1 = mock.Mock()
        line_cancel_1.origin = base_move
        line_cancel_1.amount = -10
        line_cancel_1.move = cancel_move

        line_cancel_2 = mock.Mock()
        line_cancel_2.origin = base_move
        line_cancel_2.amount = -20
        line_cancel_2.move = cancel_move

        line_payment = mock.Mock()
        line_payment.origin = payment
        line_payment.amount = -10
        line_payment.origin.line = line_base

        def test_perfect(original_lines, expected):
            self.assertEqual(expected,
                contract.reconcile_perfect_lines(original_lines))

        # Test non affected lines are not used, base is reconciled with
        # cancellation
        test_perfect(
            [line_no_origin, line_random_origin, line_base, line_cancel_1],
            ([([line_base, line_cancel_1], 0)],
                [line_no_origin, line_random_origin]))

        # Test payment is not affected if line is reconciled with cancellation
        test_perfect([line_base, line_cancel_1, line_payment],
            ([([line_base, line_cancel_1], 0)], [line_payment]))

        # Test nothing happens if only payment and cancellation
        test_perfect([line_cancel_1, line_payment],
            ([], [line_cancel_1, line_payment]))

        # Test reconciliation for line and payment
        test_perfect([line_base, line_payment],
            ([([line_base, line_payment], 0)], []))

        # Test error if cancel amount does not match base amount
        self.assertRaises(AssertionError,
            lambda: contract.reconcile_perfect_lines([line_base, line_cancel_1,
                    line_cancel_2]))

        # Test that base lines which only look like base lines are properly
        # filtered
        invoice_1.move = None
        test_perfect([line_base, line_cancel_1],
            ([], [line_base, line_cancel_1]))
        invoice_1.move = base_move

        # Test that cancel lines which only look like cancel lines are properly
        # filtered
        invoice_1.cancel_move = None
        test_perfect([line_base, line_cancel_1],
            ([], [line_cancel_1, line_base]))
        invoice_1.cancel_move = cancel_move


def suite():
    suite = trytond.tests.test_tryton.suite()
    #  suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    #  suite.addTests(doctest.DocFileSuite('scenario_invoice_contract.rst',
    #          setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
    #          optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_invoice_contract_tax_included.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
