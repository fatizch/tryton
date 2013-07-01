#-*- coding:utf-8 -*-
import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import ibanlib
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction


MODULE_NAME = os.path.basename(
    os.path.abspath(os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(unittest.TestCase):
    '''
    Test Coop module.
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

    def test0015ibanlibconfiguration(self):
        '''
        Check that the module ibanlib is well installed
        '''
        config_file = os.path.abspath(os.path.join(ibanlib.__file__, '..',
                'iban_countries.cfg'))
        self.assert_(os.path.isfile(config_file),
            'Impossible to found iban lib config file %s' % config_file)

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
            iban = self.BankAccountNumber()
            iban.kind = 'IBAN'
            iban.number = 'FR7615970003860000690570007'

            bank_account.account_numbers = [iban]
            bank_account.save()
            self.assert_(bank_account.id)

    def test0030IBAN(self):
        '''
        Test IBAN
        '''
        values = (
                ('FR7615970003860000690570007', True),
                ('FR7619530001040006462803348', True),
                ('FR7610423009910003104438477', True),
                ('FR76104230099100031044T8477', False),
                ('FR47104230099100031044T8477', True),
                ('104230099100031044T8477', False),
                ('099100031044T8477', False),
        )
        for value, test in values:
            self.assert_(ibanlib.iban.valid(value) == test)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
