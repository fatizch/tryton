# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'claim'

    @classmethod
    def fetch_models_for(cls):
        return ['party_cog', 'bank_cog']

    @test_framework.prepare_test(
        'party_cog.test0002_testCountryCreation',
        'bank_cog.test0010bank',
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
                            'number': 'FR7615970003860000690570007',
                            'bank': {'bic': 'ABCDEFGHXXX'},
                            },
                        {
                            'number': 'FR0312739000504677943241D39',
                            'bank': {'bic': 'ABCDEFGHXXX'},
                            },
                        ],
                    },
                ]}

        party_data = copy.deepcopy(data_ref)
        self.APIParty.create_party(party_data, {'_debug_server': True})

        company, = self.Party.search([('name', '=', 'My API Company')])
        self.assertEqual(company.claim_bank_account.number_compact,
            'FR7615970003860000690570007')

        party_data = copy.deepcopy(data_ref)
        party_data['parties'][0]['name'] = 'My Awesome Company'
        party_data['parties'][0]['claim_bank_account'] = {
            'number': 'FR0312739000504677943241D39',
            }
        self.APIParty.create_party(party_data, {'_debug_server': True})

        company, = self.Party.search([('name', '=', 'My Awesome Company')])
        self.assertEqual(company.claim_bank_account.number_compact,
            'FR0312739000504677943241D39')

        party_data = copy.deepcopy(data_ref)
        party_data['parties'][0]['claim_bank_account'] = {
            'number': '1234567890',
            }
        self.assertEqual(
            self.APIParty.create_party(party_data, {}).data,
            [{
                    'type': 'unknown_bank_account_number',
                    'data': {'number': '1234567890'}},
                ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
