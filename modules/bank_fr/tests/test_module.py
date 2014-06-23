#-*- coding:utf-8 -*-
import unittest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''

    @classmethod
    def get_module_name(cls):
        return 'bank_fr'

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
        party1, = self.Party.create([{
                'name': 'Bank 1', 'addresses': []
        }])
        bank1, = self.Bank.create([{'party': party1.id}])
        self.assert_(bank1.id)

    @test_framework.prepare_test('bank_fr.test0010bank')
    def test0020bankaccount(self):
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
        rib = self.BankAccountNumber()
        rib.type = 'rib'
        rib.number = '15970003860000690570007'

        bank_account.numbers = [rib]
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
            res = self.BankAccountNumber.check_rib_number(value)
            self.assert_(res == test, 'Error for %s, expected : %s, found : %s'
                % (value, test, res))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
