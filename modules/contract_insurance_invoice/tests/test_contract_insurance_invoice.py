import unittest
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class ContractInsuranceInvoiceTestCase(unittest.TestCase):
    'Test ContractInsuranceInvoice module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('contract_insurance_invoice')

    def test005views(self):
        'Test views'
        test_view('contract_insurance_invoice')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test_premium_get_amount(self):
        'Test Premium.get_amount'
        Premium = POOL.get('contract.premium')
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            premium_monthly = Premium(
                frequency='monthly',
                amount=Decimal(100),
                )

            for period, amount in (
                    ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                    ((date(2014, 1, 1), date(2014, 2, 28)), Decimal(200)),
                    ((date(2014, 1, 1), date(2014, 3, 31)), Decimal(300)),
                    ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(1200)),
                    ((date(2014, 1, 15), date(2014, 2, 23)),
                        Decimal(100) + Decimal(100) * Decimal(9 / 28.)),
                    ):
                self.assertEqual(premium_monthly.get_amount(*period), amount)

            premium_yearly = Premium(
                frequency='yearly',
                amount=Decimal(100),
                )
            for period, amount in (
                    ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(100)),
                    ((date(2014, 1, 1), date(2014, 1, 31)),
                        Decimal(100) * Decimal(31 / 365.)),
                    ((date(2014, 1, 1), date(2015, 12, 31)), Decimal(200)),
                    ):
                self.assertEqual(premium_yearly.get_amount(*period), amount)

            premium_one = Premium(
                frequency='once_per_contract',
                amount=Decimal(100),
                start=date(2014, 1, 1),
                )
            for period, amount in (
                    ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                    ((date(2014, 1, 1), date(2015, 12, 31)), Decimal(100)),
                    ((date(2014, 2, 1), date(2014, 2, 28)), Decimal(0)),
                    ):
                self.assertEqual(premium_one.get_amount(*period), amount)

    def test_contract_revision_value(self):
        'Test Contract revision_value'
        Sequence = POOL.get('ir.sequence')
        SequenceType = POOL.get('ir.sequence.type')
        Account = POOL.get('account.account')
        AccountKind = POOL.get('account.account.type')
        Product = POOL.get('offered.product')
        Contract = POOL.get('contract')
        ContractPaymentTerm = POOL.get('contract.payment_term')
        PaymentTerm = POOL.get('account.invoice.payment_term')
        ContractInvoiceFrequency = POOL.get('contract.invoice_frequency')
        InvoiceFrequency = POOL.get('offered.invoice.frequency')
        Company = POOL.get('company.company')
        User = POOL.get('res.user')
        ActivationHistory = POOL.get('contract.activation_history')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            company, = Company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            User.write([User(USER)], {
                    'main_company': company.id,
                    'company': company.id,
                    })
            payment_term1, payment_term2, payment_term3 = PaymentTerm.create([{
                        'name': '1',
                        'lines': [('create', [{}])],
                        }, {
                        'name': '2',
                        'lines': [('create', [{}])],
                        }, {
                        'name': '3',
                        'lines': [('create', [{}])],
                        }])
            freq_month, freq_quart = InvoiceFrequency.create([
                    {'frequency': 'monthly'},
                    {'frequency': 'quarterly'},
                    ])
            sequence_code, = SequenceType.create([{
                        'name': 'Product sequence',
                        'code': 'contract',
                        }])
            sequence, = Sequence.create([{
                        'name': 'Contract sequence',
                        'code': sequence_code.code,
                        'company': company.id,
                        }])
            account_kind, = AccountKind.create([{
                        'name': 'Product',
                        'company': company.id,
                        }])
            account, = Account.create([{
                        'name': 'Account for Product',
                        'code': 'Account for Product',
                        'kind': 'revenue',
                        'company': company.id,
                        'type': account_kind.id,
                        }])
            product, = Product.create([{'company': company.id,
                        'name': 'Test Product',
                        'code': 'test_product',
                        'start_date': date(2014, 4, 1),
                        'frequencies': [
                            ('add', [freq_month.id, freq_quart.id])],
                        'default_frequency': freq_month.id,
                        'payment_terms': [('add', [payment_term1.id,
                                    payment_term2.id, payment_term3.id])],
                        'default_payment_term': payment_term1.id,
                        'account_for_billing': account.id,
                        'contract_generator': sequence.id,
                        }])
            contract = Contract(company=company,
                product=product,
                activation_history=[ActivationHistory(
                        start_date=date(2014, 4, 1))],
                invoice_frequencies=[ContractInvoiceFrequency(
                        value=freq_month)])
            contract.payment_terms = [
                ContractPaymentTerm(date=None, value=payment_term1),
                ContractPaymentTerm(date=date(2014, 4, 1),
                    value=payment_term2),
                ContractPaymentTerm(date=date(2014, 6, 1),
                    value=payment_term3),
                ]
            contract.save()

            with Transaction().set_context(
                    contract_revision_date=date(2014, 1, 1)):
                contract = Contract(contract.id)
                self.assertEqual(contract.payment_term, payment_term1)

            with Transaction().set_context(
                    contract_revision_date=date(2014, 4, 1)):
                contract = Contract(contract.id)
                self.assertEqual(contract.payment_term, payment_term2)

            with Transaction().set_context(
                    contract_revision_date=date(2014, 5, 1)):
                contract = Contract(contract.id)
                self.assertEqual(contract.payment_term, payment_term2)

            with Transaction().set_context(
                    contract_revision_date=date(2014, 9, 1)):
                contract = Contract(contract.id)
                self.assertEqual(contract.payment_term, payment_term3)

    def test_contract_get_invoice_periods(self):
        'Test Contract get_invoice_periods'
        Sequence = POOL.get('ir.sequence')
        SequenceType = POOL.get('ir.sequence.type')
        Account = POOL.get('account.account')
        AccountKind = POOL.get('account.account.type')
        Product = POOL.get('offered.product')
        Contract = POOL.get('contract')
        ContractPaymentTerm = POOL.get('contract.payment_term')
        PaymentTerm = POOL.get('account.invoice.payment_term')
        ContractInvoiceFrequency = POOL.get('contract.invoice_frequency')
        InvoiceFrequency = POOL.get('offered.invoice.frequency')
        Company = POOL.get('company.company')
        User = POOL.get('res.user')
        ActivationHistory = POOL.get('contract.activation_history')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            company, = Company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            User.write([User(USER)], {
                    'main_company': company.id,
                    'company': company.id,
                    })
            payment_term, = PaymentTerm.create([{
                        'name': 'direct',
                        'lines': [('create', [{}])],
                        }])
            freq_month, freq_quart, freq_once = InvoiceFrequency.create([
                    {'frequency': 'monthly'},
                    {'frequency': 'quarterly'},
                    {'frequency': 'once_per_contract'},
                    ])
            sequence_code, = SequenceType.create([{
                        'name': 'Product sequence',
                        'code': 'contract',
                        }])
            sequence, = Sequence.create([{
                        'name': 'Contract sequence',
                        'code': sequence_code.code,
                        'company': company.id,
                        }])
            account_kind, = AccountKind.create([{
                        'name': 'Product',
                        'company': company.id,
                        }])
            account, = Account.create([{
                        'name': 'Account for Product',
                        'code': 'Account for Product',
                        'kind': 'revenue',
                        'company': company.id,
                        'type': account_kind.id,
                        }])
            product, = Product.create([{'company': company.id,
                        'name': 'Test Product',
                        'code': 'test_product',
                        'start_date': date(2014, 4, 1),
                        'frequencies': [
                            ('add', [freq_month.id, freq_quart.id,
                                    freq_once.id])],
                        'default_frequency': freq_month.id,
                        'payment_terms': [('add', [payment_term.id])],
                        'default_payment_term': payment_term.id,
                        'account_for_billing': account.id,
                        'contract_generator': sequence.id,
                        }])
            contract = Contract(company=company,
                payment_terms=[ContractPaymentTerm(value=payment_term)],
                activation_history=[ActivationHistory(
                        start_date=date(2014, 4, 15))],
                product=product,
                invoice_frequencies=[
                    ContractInvoiceFrequency(date=None, value=freq_month),
                    ContractInvoiceFrequency(date=date(2014, 7, 1),
                        value=freq_quart),
                    ],
                )
            contract.save()
            self.assertEqual(contract.start_date, date(2014, 4, 15))
            self.assertEqual(contract.get_invoice_periods(date(2014, 1, 1)),
                [])
            self.assertEqual(contract.get_invoice_periods(date(2014, 5, 1)),
                [(date(2014, 4, 15), date(2014, 5, 14))])
            self.assertEqual(contract.get_invoice_periods(date(2014, 8, 1)),
                [(date(2014, 4, 15), date(2014, 5, 14)),
                    (date(2014, 5, 15), date(2014, 6, 14)),
                    (date(2014, 6, 15), date(2014, 6, 30)),
                    (date(2014, 7, 1), date(2014, 9, 30))])

            contract = Contract(company=company,
                payment_terms=[ContractPaymentTerm(value=payment_term)],
                activation_history=[ActivationHistory(
                        start_date=date(2014, 4, 15))],
                product=product,
                invoice_frequencies=[
                    ContractInvoiceFrequency(date=None,
                        value=freq_once),
                    ])
            contract.save()
            self.assertEqual(contract.get_invoice_periods(date(2014, 1, 1)),
                [])
            self.assertEqual(contract.get_invoice_periods(date(2014, 4, 16)),
                [(date(2014, 4, 15), date.max + relativedelta(days=-1))])


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ContractInsuranceInvoiceTestCase))
    return suite
