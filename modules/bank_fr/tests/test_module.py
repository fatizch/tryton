# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import copy

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
    def fetch_models_for(cls):
        return ['bank_cog', 'party_cog']

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
        bank1, = self.Bank.create([{'party': party1.id, 'bic': 'ABCDEFGH'}])
        bank2, = self.Bank.create([{'party': party1.id, 'bic': 'IJKLMNOP'}])
        self.assertTrue(bank1.id)

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

    @test_framework.prepare_test(
        'party_cog.test0002_testCountryCreation',
        'bank_fr.test0020_test_create_agencies',
        )
    def test0050_party_creation_API(self):
        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': False,
                    'name': 'My API Company',
                    'bank_accounts': [
                        {
                            'number': 'FR1420041010050500013M02606',
                            },
                        ],
                    },
                ]}

        party_data = copy.deepcopy(data_ref)
        self.APIParty.create_party(party_data, {'_debug_server': True})

        company, = self.Party.search([('name', '=', 'My API Company')])
        self.assertEqual(len(company.bank_accounts), 1)
        self.assertEqual(company.bank_accounts[0].number,
            'FR14 2004 1010 0505 0001 3M02 606')
        self.assertEqual(company.bank_accounts[0].bank.bic, 'ABCDEFGHXXX')

        party_data = copy.deepcopy(data_ref)
        party_data['parties'][0]['bank_accounts'][0]['number'] = \
            'FR7615970003860000690570007'
        self.assertEqual(
            self.APIParty.create_party(party_data, {}).data, [{
                    'type': 'cannot_detect_bank',
                    'data': {'number': 'FR7615970003860000690570007'}},
                ])

    @test_framework.prepare_test(
        'bank_fr.test0020_test_bank_from_iban'
        )
    def test0051_bank_from_number(self):
        data_ref = {
            'number': 'FR1420041010050500013M02606'
            }
        bank = self.APIParty.bank_from_number(data_ref, {})
        self.assertEqual(bank['bic'], 'ABCDEFGHXXX')

        data_ref['number'] = 'FR7615970003860000690570007'

        bank = self.APIParty.bank_from_number(data_ref, {})
        self.assertEqual(bank, {})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
