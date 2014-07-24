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

    def test_contract_get_invoice_periods(self):
        'Test Contract get_invoice_periods'
        Sequence = POOL.get('ir.sequence')
        SequenceType = POOL.get('ir.sequence.type')
        Account = POOL.get('account.account')
        AccountKind = POOL.get('account.account.type')
        Product = POOL.get('offered.product')
        Contract = POOL.get('contract')
        PaymentTerm = POOL.get('account.invoice.payment_term')
        BillingInformation = POOL.get('contract.billing_information')
        BillingMode = POOL.get('offered.billing_mode')
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
            freq_month, freq_quart, freq_once = BillingMode.create([{
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
            sequence_code, = SequenceType.create([{
                        'name': 'Product sequence',
                        'code': 'contract',
                        }])
            sequence, quote_sequence = Sequence.create([{
                        'name': 'Contract sequence',
                        'code': sequence_code.code,
                        'company': company.id,
                        }, {
                        'name': 'Quote Sequence',
                        'code': 'quote',
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
                        'billing_modes': [
                            ('add', [freq_month.id, freq_quart.id,
                                    freq_once.id])],
                        'account_for_billing': account.id,
                        'contract_generator': sequence.id,
                        'quote_number_sequence': quote_sequence.id,
                        }])
            contract = Contract(company=company,
                activation_history=[ActivationHistory(
                        start_date=date(2014, 4, 15))],
                product=product,
                billing_informations=[
                    BillingInformation(date=None,
                        billing_mode=freq_month,
                        payment_term=payment_term),
                    BillingInformation(date=date(2014, 7, 1),
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

            contract = Contract(company=company,
                activation_history=[ActivationHistory(
                        start_date=date(2014, 4, 15))],
                product=product,
                billing_informations=[
                    BillingInformation(date=None,
                        billing_mode=freq_once),
                    ])
            contract.save()
            self.assertEqual(contract.get_invoice_periods(date(2014, 1, 1)),
                [])
            self.assertEqual(contract.get_invoice_periods(date(2014, 4, 16)),
                [(date(2014, 4, 15), date.max + relativedelta(days=-1),
                    contract.billing_informations[0])])


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ContractInsuranceInvoiceTestCase))
    return suite
