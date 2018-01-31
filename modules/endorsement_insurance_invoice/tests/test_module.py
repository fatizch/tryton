# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest
import mock

from trytond.transaction import Transaction

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'endorsement_insurance_invoice'

    @classmethod
    def fetch_models_for(cls):
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
            'Tax': 'account.tax',
            'Product': 'offered.product',
            'Coverage': 'offered.option.description',
            'PaymentTerm': 'account.invoice.payment_term',
            'BillingInformation': 'contract.billing_information',
            'BillingMode': 'offered.billing_mode',
            'Company': 'company.company',
            'MoveLine': 'account.move.line',
            'User': 'res.user',
            'Configuration': 'account.configuration',
            'OfferedConfiguration': 'offered.configuration',
            'ConfigurationTaxRounding': 'account.configuration.tax_rounding',
            'PaymentJournal': 'account.payment.journal',
            'Reconciliation': 'account.move.reconciliation',
            'ContractInvoice': 'contract.invoice',
            'Invoice': 'account.invoice',
            'InvoiceLine': 'account.invoice.line',
            'InvoiceLineDetail': 'account.invoice.line.detail',
            }

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test_contract_get_invoice_periods(self):
        'Test Contract get_invoice_periods'

        company, = self.Company.search([
                ('rec_name', '=', 'World Company'),
                ])
        currency, = self.Currency.search([], limit=1)
        self.User.write([self.User(Transaction().user)], {
                'main_company': company.id,
                'company': company.id,
                })
        payment_term, = self.PaymentTerm.create([{
                    'name': 'direct',
                    'lines': [('create', [{}])],
                    }])
        freq_year, freq_quart, freq_once = self.BillingMode.create([{
                'code': 'yearly',
                'name': 'yearly',
                'frequency': 'yearly',
                'sync_day': '1',
                'sync_month': '1',
                'allowed_payment_terms': [
                        ('add', [payment_term.id])]
                }, {
                'code': 'quarterly',
                'name': 'quarterly',
                'frequency': 'quarterly',
                'sync_day': '1',
                'sync_month': '1',
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
        with Transaction().set_context(company=company.id):
            product, = self.Product.create([{'company': company.id,
                        'name': 'Test Product',
                        'code': 'test_product',
                        'start_date': datetime.date(2014, 1, 1),
                        'billing_modes': [
                            ('add', [freq_year.id, freq_quart.id,
                                    freq_once.id])],
                        'contract_generator': sequence.id,
                        'quote_number_sequence': quote_sequence.id,
                        'currency': currency.id,
                        }])
        config = self.OfferedConfiguration(1)
        config.split_invoices_on_endorsement_dates = True
        config.save()
        contract = self.Contract(company=company,
            start_date=datetime.date(2017, 8, 1),
            product=product,
            billing_informations=[
                self.BillingInformation(date=None,
                    billing_mode=freq_year,
                    payment_term=payment_term),
                self.BillingInformation(date=datetime.date(2018, 1, 1),
                    billing_mode=freq_quart,
                    direct_debit_day=5,
                    payment_term=payment_term),
                ],
            )
        contract.save()
        self.maxDiff = None
        contract.rebill_endorsement_dates = mock.Mock(return_value=[
                datetime.datetime.combine(datetime.date(2017, 12, 15),
                    datetime.time()),
                datetime.datetime.combine(datetime.date(2018, 2, 28),
                    datetime.time())])
        self.assertEqual(contract.get_invoice_periods(
                datetime.date(2018, 4, 1), contract.start_date),
            [
                (datetime.date(2017, 8, 1), datetime.date(2017, 12, 14),
                    contract.billing_informations[0]),
                (datetime.date(2017, 12, 15), datetime.date(2017, 12, 31),
                    contract.billing_informations[0]),
                (datetime.date(2018, 1, 1), datetime.date(2018, 2, 27),
                    contract.billing_informations[1]),
                (datetime.date(2018, 2, 28), datetime.date(2018, 3, 31),
                    contract.billing_informations[1]),
                (datetime.date(2018, 4, 1), datetime.date(2018, 6, 30),
                    contract.billing_informations[1]),
                ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
