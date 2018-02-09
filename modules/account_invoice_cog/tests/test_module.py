# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import mock
import datetime
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.modules.currency.tests import create_currency


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'account_invoice_cog'

    @classmethod
    def fetch_models_for(cls):
        return ['company_cog', 'currency_cog']

    @classmethod
    def get_models(cls):
        return {
            'Company': 'company.company',
            'Configuration': 'account.configuration',
            'Sequence': 'ir.sequence',
            'Invoice': 'account.invoice',
            'InvoiceLine': 'account.invoice.line',
            'LineTax': 'account.invoice.line-account.tax',
            'Journal': 'account.journal',
            'Account': 'account.account',
            'AccountKind': 'account.account.type',
            'Tax': 'account.tax',
            'PaymentTerm': 'account.invoice.payment_term',
            }

    def test0001_payment_term(self):
        'Test payment_term'
        cu1 = create_currency('cu1')
        term, = self.PaymentTerm.create([{
                    'name': 'End of quarter + 1 month',
                    'lines': [
                        ('create', [{
                                    'sequence': 1,
                                    'type': 'remainder',
                                    'relativedeltas': [('create', [{
                                                    'months': 1,
                                                    'quarter': True,
                                                    'day': 30,
                                                    },
                                                ]),
                                        ],
                                    }])]
                    }])
        amount = Decimal('1000')
        # End of quarter + 1 month
        for m in range(1, 10):
            terms = term.compute(amount, cu1, date=datetime.date(2011, m, 15))
            self.assertEqual(terms,
                [(datetime.date(2011, (m - 1) // 3 * 3 + 4, 30), amount), ])

        for m in range(10, 13):
            terms = term.compute(amount, cu1, date=datetime.date(2011, m, 15))
            self.assertEqual(terms, [(datetime.date(2012, 1, 30), amount), ])

        # End of quarter
        term.lines[0].relativedeltas[0].months = 0
        for m in range(1, 13):
            terms = term.compute(amount, cu1, date=datetime.date(2011, m, 15))
            self.assertEqual(terms,
                [(datetime.date(2011, (m - 1) // 3 * 3 + 3, 30), amount), ])

        # Beginning of quarter
        term.lines[0].relativedeltas[0].months = -2
        for m in range(1, 13):
            terms = term.compute(amount, cu1, date=datetime.date(2011, m, 15))
            self.assertEqual(terms,
                [(datetime.date(2011, (m - 1) // 3 * 3 + 1, 30), amount), ])

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test0010_invoice_line_taxes(self):
        self.maxDiff = None
        company, = self.Company.search([
                ('rec_name', '=', 'World Company'),
                ])
        company.party.addresses = [{}]
        company.party.save()
        tax_account_kind = self.AccountKind()
        tax_account_kind.name = 'Tax Account Kind'
        tax_account_kind.company = company
        tax_account_kind.save()
        tax_account = self.Account()
        tax_account.name = 'Main tax'
        tax_account.code = 'main_tax'
        tax_account.kind = 'revenue'
        tax_account.company = company
        tax_account.type = tax_account_kind
        tax_account.save()

        invoice_account_kind = self.AccountKind()
        invoice_account_kind.name = 'Invoice Account Kind'
        invoice_account_kind.company = company
        invoice_account_kind.save()

        invoice_account = self.Account()
        invoice_account.name = 'Invoice Account'
        invoice_account.code = 'main_account'
        invoice_account.kind = 'receivable'
        invoice_account.company = company
        invoice_account.type = invoice_account_kind
        invoice_account.save()

        configuration = self.Configuration(1)
        configuration.tax_rounding = 'line'
        configuration.save()
        tax_1 = self.Tax()
        tax_1.name = 'Tax1'
        tax_1.type = 'percentage'
        tax_1.description = 'Tax 1'
        tax_1.rate = Decimal('0.09')
        tax_1.company = company
        tax_1.invoice_account = tax_account
        tax_1.credit_note_account = tax_account
        tax_1.save()

        sequence = self.Sequence()
        sequence.name = 'Test Sequence'
        sequence.code = 'account.journal'
        sequence.suffix = 'Y${year}'
        sequence.save()

        Journal = self.Journal
        journal = Journal()
        journal.name = 'Test Journal'
        journal.code = 'test_journal'
        journal.type = 'revenue'
        journal.sequence = sequence
        journal.save()

        invoice = self.Invoice()
        invoice.description = 'Invoice 1'
        invoice.journal = journal
        invoice.currency = company.currency
        invoice.company = company
        invoice.account = invoice_account
        invoice.party = company.party
        invoice.state = 'draft'
        invoice.invoice_address = company.party.addresses[0]
        invoice.lines = [
            self.InvoiceLine(
                unit_price=Decimal('3.9450'),
                type='line',
                description='test',
                company=company,
                account=tax_account,
                quantity=1,
                taxes=[tax_1],
                ),
            ]

        with mock.patch.object(self.InvoiceLine, '_round_taxes') as rounding, \
                mock.patch.object(self.Invoice, 'reverse_tax_included') as \
                reverse_invoice, \
                mock.patch.object(self.LineTax, 'reverse_tax_included') as \
                reverse_line:
            rounding.return_value = True
            reverse_invoice.return_value = True
            reverse_line.return_value = True
            invoice.save()
            invoice.update_taxes([invoice])
            self.assertEqual(invoice.lines[0].tax_amount, Decimal('0.35'))
            self.assertEqual(invoice.taxes[0].amount, Decimal('0.35'))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
