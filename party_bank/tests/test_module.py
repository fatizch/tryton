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
        self.BankAccount = POOL.get('party.bank_account')
        self.BankAccountNumber = POOL.get('party.bank_account_number')
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
            rib = self.BankAccountNumber()
            rib.kind = 'RIB'
            rib.number = '15970003860000690570007'
            iban = self.BankAccountNumber()
            iban.kind = 'IBAN'
            iban.number = 'FR7615970003860000690570007'

            bank_account.account_numbers = [rib, iban]
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

    def test0040creditcard(self):
        '''
        Test Credit Card
        '''
        values = (
                ('378282246310005', True),
                ('378282546310005', False),
                ('371449635398431', True),
                ('371449635399431', False),
                ('378734493671000', True),
                ('30569309025904', True),
                ('38520000023237', True),
                ('6011111111111117', True),
                ('3530111333300000', True),
                ('5555555555554444', True),
                ('4111111111111111', True),
                ('4111111111111112', False),
                ('4012888888881881', True),
                ('4012868888881881', False),
                ('4222222222222', True),
        )
        for value, test in values:
            self.assert_(
                self.BankAccountNumber.check_credit_card(value) == test)

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
