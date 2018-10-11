# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
import mock

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'account_invoice_slip'

    @classmethod
    def get_models(cls):
        return {
            'Account': 'account.account',
            'Company': 'company.company',
            'Currency': 'currency.currency',
            'Invoice': 'account.invoice',
            'Journal': 'account.journal',
            'Party': 'party.party',
            'PaymentTerm': 'account.invoice.payment_term',
            'SlipConfiguration': 'account.invoice.slip.configuration',
            }

    def test0001_create_empty_slips(self):
        company = self.Company(1)
        company.currency = self.Currency(name='Currency')
        payment_term = self.PaymentTerm(name='Payment Term')
        parameters = [
            {
                'party': self.Party(name='Party 1',
                    supplier_payment_term=payment_term),
                'journal': self.Journal(name='Journal 1'),
                'date': datetime.date.today(),
                'slip_kind': 'default',
                'accounts': [
                    self.Account(name='account_1', rec_name='Account 1',
                        company=company),
                    self.Account(name='account_2', rec_name='Account 2'),
                    ],
                },
            ]
        account = self.Account(name='payable_account')

        with mock.patch.object(self.Invoice, 'search') as patched_search, \
                mock.patch.object(self.Party, 'account_payable_used',
                    new_callable=mock.PropertyMock) as patched_payable_used, \
                mock.patch.object(self.Invoice, 'save') as patched_save:

            patched_search.return_value = []
            patched_payable_used.return_value = account
            invoice, = self.SlipConfiguration.create_empty_slips(parameters)
            patched_search.assert_called()
            patched_save.assert_called()

            self.assertEqual(invoice.company.id, 1)
            self.assertEqual(invoice.party.name, 'Party 1')
            self.assertEqual(invoice.journal.name, 'Journal 1')
            self.assertEqual(invoice.invoice_date, datetime.date.today())
            self.assertEqual(invoice.type, 'in')
            self.assertEqual(invoice.business_kind, 'default')
            self.assertEqual(invoice.state, 'draft')
            self.assertEqual({x.description for x in invoice.lines}, {
                    'Account 1', 'Account 2',
                    })


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
