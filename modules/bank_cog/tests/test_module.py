# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import copy

from stdnum import iban

import trytond.tests.test_tryton
from trytond.exceptions import UserError
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework, utils


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'bank_cog'

    @classmethod
    def fetch_models_for(cls):
        return ['party_cog']

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
        bank1, = self.Bank.create([{'party': party1.id, 'bic': 'ABCDEFGH'}])
        self.assertTrue(bank1.id)

    @test_framework.prepare_test('bank_cog.test0010bank')
    def test0020bankaccount(self):
        '''
        Create bank Account
        '''
        party1, = self.Party.search([], limit=1)
        bank1, = self.Bank.search([], limit=1)

        currency = self.Currency.search([('code', '=', 'EUR')])
        if currency:
            currency, = currency
        else:
            currency, = self.Currency.create([{
                    'name': 'Euro',
                    'code': 'EUR',
                    'symbol': '€',
            }])

        bank_account = self.BankAccount()
        bank_account.bank = bank1
        bank_account.owners = [party1]
        bank_account.currency = currency
        cur_iban = self.BankAccountNumber()
        cur_iban.type = 'iban'
        cur_iban.number = 'FR7615970003860000690570007'

        bank_account.numbers = [cur_iban]
        bank_account.save()
        self.assertTrue(bank_account.id)

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
            self.assertTrue(iban.is_valid(value) == test)

    @test_framework.prepare_test('currency_cog.test0001_testCurrencyCreation',
        'bank_cog.test0010bank')
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
        self.assertTrue(bank_account.numbers[0].id)

        number = self.BankAccountNumber()
        number.type = 'iban'
        number.number = 'FR7610096002350004089177136'
        numbers = list(bank_account.numbers)
        numbers.append(number)
        bank_account.numbers = numbers
        try:
            bank_account.save()
        except UserError:
            pass
        self.assertTrue(bank_account.numbers[1].id is None)

    @test_framework.prepare_test(
        'party_cog.test0002_testCountryCreation', 'bank_cog.test0010bank',
        )
    def test0050_party_creation_API(self):
        # Run examples
        for example in self.APIParty._create_party_examples():
            self.APIParty.create_party(example['input'], {})

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': False,
                    'name': 'My API Company',
                    'bank_accounts': [
                        {
                            'number': 'FR7615970003860000690570007',
                            'bank': {'bic': 'ABCDEFGHXXX'},
                            },
                        ],
                    },
                ]}

        party_data = copy.deepcopy(data_ref)
        self.APIParty.create_party(party_data, {'_debug_server': True})

        company, = self.Party.search([('name', '=', 'My API Company')])
        self.assertEqual(len(company.bank_accounts), 1)
        self.assertEqual(company.bank_accounts[0].number,
            'FR76 1597 0003 8600 0069 0570 007')
        self.assertEqual(company.bank_accounts[0].bank.bic, 'ABCDEFGHXXX')

        party_data = copy.deepcopy(data_ref)
        party_data['parties'][0]['bank_accounts'][0]['number'] = '123456'
        self.assertEqual(
            self.APIParty.create_party(party_data, {}).data,
            [{'type': 'invalid_iban', 'data': {'number': '123456'}}])

        party_data = copy.deepcopy(data_ref)
        party_data['parties'][0]['bank_accounts'][0]['bank'] = {
            'bic': 'BAD_BIC'}
        self.assertEqual(
            self.APIParty.create_party(party_data, {}).data, [{
                    'type': 'unknown_bic',
                    'data': {'bic': 'BAD_BIC'},
                    }])

    def test_swift_import(self):
        fr = self.Country(name="France", code='FR')
        fr.save()
        ma = self.Country(name="Maroc", code='MA')
        ma.save()
        BankWizard = Pool().get('bank_cog.data.set.wizard', type='wizard')
        bank_wiz_id, _, _ = BankWizard.create()
        bank_wiz = BankWizard(bank_wiz_id)
        # Create banks
        bank_wiz._execute('configuration')
        bank_wiz.configuration.file_format = 'swift'
        bank_wiz.configuration.use_default = False
        test_file_path = utils.get_module_path(
            'bank_cog') + '/tests/test_files/%s'
        bank_wiz.configuration.resource = open(test_file_path % 'swift.txt',
            'rb').read()
        bank_wiz.configuration.countries_to_import = [fr.id, ma.id]
        bank_wiz._execute('set_')
        self.assertEqual(len(self.Bank.search([('bic', 'in',
            ('AAADFRP1XXX', 'AAAGFRP1XXX', 'AAAMFRP1XXX', 'ARABMAMC220',
             'ARABMAMC221', 'ARABMAMC230'))])), 6)
        # Update and create banks
        bank_wiz.configuration.resource = open(
            test_file_path % 'swift_update.txt', 'rb').read()
        bank_wiz._execute('set_')
        self.assertEqual(len(self.Bank.search([])), 8)
        self.assertEqual(self.Bank.search([('bic', '=', 'AAADFRP1XXX')])[
            0].party.name, '1818 GESTION')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
