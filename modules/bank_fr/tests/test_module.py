# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework
from trytond.exceptions import UserWarning
from trytond.transaction import Transaction


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''

    module = 'bank_fr'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Bank': 'bank',
            'Agency': 'bank.agency',
            'BankAccount': 'bank.account',
            'BankAccountNumber': 'bank.account.number',
            'Currency': 'currency.currency',
        }

    def test0010_test_create_banks(self):
        party1, = self.Party.create([{
                'name': 'Bank 1', 'addresses': []}])
        bank1, = self.Bank.create([{'party': party1.id}])
        bank2, = self.Bank.create([{'party': party1.id}])
        self.assert_(bank1.id)

    @test_framework.prepare_test(
        'bank_fr.test0010_test_create_banks',
        )
    def test0020_test_create_agencies(self):
        bank1, bank2 = self.Bank.search([],
            order=[('id', 'ASC')])
        agency1 = self.Agency(bank=bank1, name='one', bank_code='20041',
            branch_code='01005')
        agency1.save()
        agency1_bis = self.Agency(bank=bank2, name='one', bank_code='20041',
            branch_code='00000')
        agency1_bis.save()
        agency2 = self.Agency(bank=bank2, name='one', bank_code='20001')
        agency2.save()

    @test_framework.prepare_test(
        'bank_fr.test0020_test_create_agencies',
        )
    def test0020_test_bank_from_iban(self):
        with Transaction().set_user(1):  # necessary to raise Warning
            bank1, bank2 = self.Bank.search([],
                order=[('id', 'ASC')])
            agency1, agency1_bis, agency2 = self.Agency.search([],
                order=[('id', 'ASC')])
            account1 = self.BankAccount()
            account1.number = 'FR14 2004 1010 0505 0001 3M02 606'
            # see the code for on_change_with_number
            account1.numbers = [self.BankAccountNumber(
                    **account1.on_change_with_numbers()['add'][0][1])]
            account1.on_change_number()
            account1.save()
            self.assertEqual(account1.bank, bank1)

            account1.bank = bank2
            self.assertRaises(UserWarning, account1.save)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
