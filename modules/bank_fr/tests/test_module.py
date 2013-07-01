#-*- coding:utf-8 -*-
import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction


MODULE_NAME = os.path.basename(
    os.path.abspath(os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(unittest.TestCase):
    '''
    Test Bank Fr Module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module(MODULE_NAME)
        self.Party = POOL.get('party.party')
        self.Bank = POOL.get('party.bank')
        self.BankAccount = POOL.get('bank.account')
        self.BankAccountNumber = POOL.get('bank.account_number')
        self.Currency = POOL.get('currency.currency')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view(MODULE_NAME)

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010bank(self):
        '''
        Create Bank.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            party1, = self.Party.create([{
                    'name': 'Bank 1', 'addresses': []
            }])
            bank1, = self.Bank.create([{'party': party1.id}])
            self.assert_(bank1.id)
            transaction.cursor.commit()

    def test0020bankaccount(self):
        '''
        Create bank Account
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            party1, = self.Party.search([], limit=1)

            currency, = self.Currency.create([{
                    'name': 'Euro',
                    'code': 'EUR',
                    'symbol': u'€',
            }])

            bank_account = self.BankAccount()
            bank_account.party = party1.id
            bank_account.currency = currency
            rib = self.BankAccountNumber()
            rib.kind = 'RIB'
            rib.number = '15970003860000690570007'
            iban = self.BankAccountNumber()
            iban.kind = 'IBAN'
            iban.number = 'FR7615970003860000690570007'

            bank_account.account_numbers = [rib, iban]
            bank_account.save()
            self.assert_(bank_account.id)

    def test0050rib(self):
        '''
        Test RIB
        '''
        values = (
                ('11006005410000104703939', True),
                ('11600003910000247105389', True),
                ('11749006730007094332254', True),
                ('30047009950008375267822', True),
                ('11790003250008688281087', True),
                ('11790003250008688281088', False),
                ('1179003250008688281087', False),
                ('104230099100031044T8477', True),
                ('104230099100031044T8478', False),
        )
        for value, test in values:
            res = self.BankAccountNumber.check_rib(value)
            self.assert_(res == test, 'Error for %s, expected : %s, found : %s'
                % (value, test, res))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
