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
        Contract = POOL.get('contract')
        ContractPaymentTerm = POOL.get('contract.payment_term')
        PaymentTerm = POOL.get('account.invoice.payment_term')
        ContractInvoiceFrequency = POOL.get('contract.invoice_frequency')
        InvoiceFrequency = POOL.get('offered.invoice.frequency')
        Company = POOL.get('company.company')
        User = POOL.get('res.user')

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
            contract = Contract(company=company,
                invoice_frequencies=[ContractInvoiceFrequency(
                        value=InvoiceFrequency(frequency='monthly'))])
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
        Contract = POOL.get('contract')
        ContractPaymentTerm = POOL.get('contract.payment_term')
        PaymentTerm = POOL.get('account.invoice.payment_term')
        ContractInvoiceFrequency = POOL.get('contract.invoice_frequency')
        InvoiceFrequency = POOL.get('offered.invoice.frequency')
        Company = POOL.get('company.company')
        User = POOL.get('res.user')

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

            contract = Contract(company=company,
                payment_terms=[ContractPaymentTerm(value=payment_term)],
                start_date=date(2014, 4, 15),
                invoice_frequencies=[
                    ContractInvoiceFrequency(date=None,
                        value=InvoiceFrequency(frequency='monthly')),
                    ContractInvoiceFrequency(date=date(2014, 7, 1),
                        value=InvoiceFrequency(frequency='quarterly')),
                    ])
            contract.save()
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
                start_date=date(2014, 4, 15),
                invoice_frequencies=[
                    ContractInvoiceFrequency(date=None,
                        value=InvoiceFrequency(frequency='once_per_contract')),
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
