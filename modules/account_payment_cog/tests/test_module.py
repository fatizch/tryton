# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from mock import Mock
import datetime
from decimal import Decimal

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework
from trytond.transaction import Transaction


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'account_payment_cog'

    @classmethod
    def get_models(cls):
        return {
            'Company': 'company.company',
            'User': 'res.user',
            'Currency': 'currency.currency',
            'MoveLine': 'account.move.line',
            'Journal': 'account.journal',
            'JournalType': 'account.journal.type',
            'PaymentJournal': 'account.payment.journal',
            'Payment': 'account.payment',
            'Party': 'party.party',
            'Account': 'account.account',
            'AccountType': 'account.account.type',
            'FiscalYear': 'account.fiscalyear',
            'Move': 'account.move',
            'MoveLine': 'account.move.line',
            'Sequence': 'ir.sequence',
            }

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test0010_test_init_payment(self):
        company = self.Company(1)
        with Transaction().set_context(company=company.id):
            today = datetime.date.today()
            sequence, sequence_journal = self.Sequence.create([{
                        'name': '%s' % today.year,
                        'code': 'account.move',
                        'company': company.id,
                        }, {
                        'name': '%s' % today.year,
                        'code': 'account.journal',
                        'company': company.id,
                        }])
            fiscalyear, = self.FiscalYear.create([{
                        'name': '%s' % today.year,
                        'start_date': today.replace(month=1, day=1),
                        'end_date': today.replace(month=12, day=31),
                        'company': company.id,
                        'post_move_sequence': sequence.id,
                        }])
            self.FiscalYear.create_period([fiscalyear])
            journal_type, = self.JournalType.create([{
                        'name': 'Revenue',
                        'code': 'REV',
                        }])
            journal_revenue, = self.Journal.create([{
                        'name': 'Revenue',
                        'type': 'REV',
                        'sequence': sequence_journal.id,
                        }])
            account_kind_receivable, = self.AccountType.create([{
                        'name': 'Receivable',
                        'company': company.id,
                        }])
            account_kind_payable, = self.AccountType.create([{
                        'name': 'Payable',
                        'company': company.id,
                        }])
            account_kind_revenue, = self.AccountType.create([{
                        'name': 'Revenue',
                        'company': company.id,
                        }])
            account_receivable, account_payable = self.Account.create([{
                        'name': 'Receivable',
                        'company': company.id,
                        'type': account_kind_receivable.id,
                        'kind': 'receivable',
                        'party_required': True,
                        }, {
                        'name': 'Payable',
                        'company': company.id,
                        'type': account_kind_payable.id,
                        'kind': 'payable',
                        'party_required': True,
                        }])
            account_revenue, = self.Account.create([{
                        'name': 'Revenu',
                        'company': company.id,
                        'type': account_kind_revenue.id,
                        'kind': 'revenue',
                        }])
            payment_journal, = self.PaymentJournal.create([{
                        'name': 'Manual',
                        'process_method': 'manual',
                        'company': company.id,
                        'currency': company.currency.id,
                        }])
            period = fiscalyear.periods[0]
            customer, = self.Party.create([{
                        'name': 'Customer',
                        'account_payable': account_payable,
                        'account_receivable': account_receivable,
                        }])
            # create first move
            move, = self.Move.create([{
                        'period': period.id,
                        'journal': journal_revenue.id,
                        'date': period.start_date,
                        'company': company.id,
                        }])
            move_line, move_line_receivable = self.MoveLine.create([{
                        'account': account_revenue.id,
                        'credit': Decimal(50),
                        'move': move.id
                        }, {
                        'account': account_receivable.id,
                        'debit': Decimal(50),
                        'move': move.id,
                        'party': customer.id,
                        'maturity_date': period.start_date,
                        'payment_date': period.start_date,
                        }])
            self.Move.post([move])
            lines_to_pay = [move_line_receivable]
            move_line_receivable.get_payment_journal = Mock(
                return_value=payment_journal)
            payments = self.MoveLine.create_payments(lines_to_pay)
            self.assertTrue(len(payments) == 1)
            self.assertTrue(payments[0].amount == Decimal(50))
            self.assertTrue(payments[0].kind == 'receivable')
            payments[0].state = 'draft'
            payments[0].save()
            self.Payment.delete(payments)

            # create credit receivable
            move, = self.Move.create([{
                        'period': period.id,
                        'journal': journal_revenue.id,
                        'date': period.start_date,
                        'company': company.id,
                        }])
            move_line, move_line_receivable = self.MoveLine.create([{
                        'account': account_revenue.id,
                        'debit': Decimal(20),
                        'move': move.id
                        }, {
                        'account': account_receivable.id,
                        'credit': Decimal(20),
                        'move': move.id,
                        'party': customer.id,
                        'maturity_date': period.start_date,
                        }])
            self.Move.post([move])
            move_line_receivable.get_payment_journal = Mock(
                return_value=payment_journal)
            payments = self.MoveLine.create_payments(lines_to_pay)
            self.assertTrue(len(payments) == 1)
            self.assertTrue(payments[0].amount == Decimal(30))
            self.assertTrue(payments[0].kind == 'receivable')
            payments[0].state = 'draft'
            payments[0].save()
            self.Payment.delete(payments)

            # mark credit receivable with payment_date
            move_line_receivable.payment_date = period.start_date
            move_line_receivable.save()
            lines_to_pay.append(move_line_receivable)
            payments = self.MoveLine.create_payments(lines_to_pay)
            self.assertTrue(len(payments) == 1)
            self.assertTrue(payments[0].amount == Decimal(30))
            self.assertTrue(payments[0].kind == 'receivable')
            payments[0].state = 'draft'
            self.Payment.delete(payments)

            # create payable move
            move, = self.Move.create([{
                        'period': period.id,
                        'journal': journal_revenue.id,
                        'date': period.start_date,
                        'company': company.id,
                        }])
            move_line, move_line_payable = self.MoveLine.create([{
                        'account': account_revenue.id,
                        'debit': Decimal(50),
                        'move': move.id
                        }, {
                        'account': account_payable.id,
                        'credit': Decimal(50),
                        'move': move.id,
                        'party': customer.id,
                        'maturity_date': period.start_date,
                        'payment_date': period.start_date,
                        }])
            move_line_payable.get_payment_journal = Mock(
                return_value=payment_journal)
            lines_to_pay.append(move_line_payable)
            move2, = self.Move.create([{
                        'period': period.id,
                        'journal': journal_revenue.id,
                        'date': period.start_date,
                        'company': company.id,
                        }])
            move_line, move_line_payable = self.MoveLine.create([{
                        'account': account_revenue.id,
                        'credit': Decimal(10),
                        'move': move2.id
                        }, {
                        'account': account_payable.id,
                        'debit': Decimal(10),
                        'move': move2.id,
                        'party': customer.id,
                        'maturity_date': period.start_date,
                        }])
            self.Move.post([move, move2])
            move_line_payable.get_payment_journal = Mock(
                return_value=payment_journal)
            payments = self.MoveLine.create_payments(lines_to_pay)
            self.assertTrue(len(payments) == 2)
            self.assertTrue(payments[0].amount == Decimal(40))
            self.assertTrue(payments[0].kind == 'payable')
            self.assertTrue(payments[1].amount == Decimal(30))
            self.assertTrue(payments[1].kind == 'receivable')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
