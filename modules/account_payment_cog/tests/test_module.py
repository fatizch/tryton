import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'account_payment_cog'

    @classmethod
    def get_models(cls):
        return {
            'Company': 'company.company',
            'MoveLine': 'account.move.line',
            'PaymentJournal': 'account.payment.journal',
            'Payment': 'account.payment',
            'Party': 'party.party',
            'Account': 'account.account'
            }

    def test0010_test_init_payment(self):
        journal = self.PaymentJournal(id=1)
        company = self.Company(id=2)
        account = self.Account(company=company)
        party = self.Party(id=3)
        move_line = self.MoveLine(
            id=4,
            account=account,
            party=party,
            payment_date=datetime.date(2014, 1, 1))

        move_line.debit = 45
        move_line.credit = 0
        payment = move_line.init_payment(journal)
        self.assertEqual(payment, {
            'company': 2,
            'kind': 'receivable',
            'journal': 1,
            'party': 3,
            'amount': 45,
            'line': 4,
            'date': move_line.payment_date,
            'state': 'approved'})

        move_line.debit = 0
        move_line.credit = 15
        payment = move_line.init_payment(journal)
        self.assertEqual(payment['amount'], 15)
        self.assertEqual(payment['kind'], 'payable')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
