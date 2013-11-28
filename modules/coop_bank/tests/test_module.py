#-*- coding:utf-8 -*-
import os
import ibanlib
import unittest

import trytond.tests.test_tryton
from trytond.exceptions import UserError

from trytond.modules.coop_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'coop_bank'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Bank': 'bank',
            'BankAccount': 'bank.account',
            'BankAccountNumber': 'bank.account.number',
            'Currency': 'currency.currency',
        }

    def test0010bank(self):
        '''
        Create Bank.
        '''
        party1, = self.Party.create([{
                'name': 'Bank 1', 'addresses': []
        }])
        bank1, = self.Bank.create([{'party': party1.id}])
        self.assert_(bank1.id)

    def test0015ibanlibconfiguration(self):
        '''
        Check that the module ibanlib is well installed
        '''
        config_file = os.path.abspath(os.path.join(ibanlib.__file__, '..',
                'iban_countries.cfg'))
        self.assert_(os.path.isfile(config_file),
            'Impossible to found iban lib config file %s' % config_file)

    @test_framework.prepare_test('coop_bank.test0010bank')
    def test0020bankaccount(self):
        '''
        Create bank Account
        '''
        party1, = self.Party.search([], limit=1)
        bank1, = self.Bank.search([], limit=1)

        currency, = self.Currency.create([{
                'name': 'Euro',
                'code': 'EUR',
                'symbol': u'€',
        }])

        bank_account = self.BankAccount()
        bank_account.bank = bank1
        bank_account.owners = [party1]
        bank_account.currency = currency
        iban = self.BankAccountNumber()
        iban.type = 'iban'
        iban.number = 'FR7615970003860000690570007'

        bank_account.numbers = [iban]
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

    @test_framework.prepare_test('coop_bank.test0010bank')
    def test0040banknumberunicity(self):
        '''
        Check that a number account is unique in database
        '''
        party1, = self.Party.search([], limit=1)
        bank1, = self.Bank.search([], limit=1)
        currency, = self.Currency.search([], limit=1)
        bank_account = self.BankAccount()
        bank_account.bank = bank1
        bank_account.owners = [party1]
        bank_account.currency = currency
        number = self.BankAccountNumber()
        number.type = 'iban'
        number.number = 'FR7610096002350004089177136'
        bank_account.numbers = [number]
        bank_account.save()
        self.assert_(bank_account.numbers[0].id)

        number = self.BankAccountNumber()
        number.type = 'iban'
        number.number = 'FR7610096002350004089177136'
        bank_account.numbers = list(bank_account.numbers)
        bank_account.numbers.append(number)
        try:
            bank_account.save()
        except UserError:
            pass
        self.assert_(bank_account.numbers[1].id is None)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
