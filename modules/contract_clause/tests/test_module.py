# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import copy

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_clause'

    @classmethod
    def fetch_models_for(cls):
        return ['contract', 'offered']

    @test_framework.prepare_test(
        'offered_clause.test0020_addClausesToProduct',
        )
    def test0005_PrepareProductForSubscription(self):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Product = pool.get('offered.product')

        qg = Sequence()
        qg.name = 'Quote Sequence'
        qg.code = 'quote'
        qg.prefix = 'Quo'
        qg.suffix = 'Y${year}'
        qg.save()

        product_a, = Product.search([('code', '=', 'AAA')])
        product_a.quote_number_sequence = qg
        product_a.save()

    @test_framework.prepare_test(
        'contract.test0002_testCountryCreation',
        'contract_clause.test0005_PrepareProductForSubscription',
        )
    def test0100_subscribe_contract_API(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')
        Contract = pool.get('contract')

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Father',
                    'birth_date': '1980-01-20',
                    'gender': 'male',
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'clauses': [
                        {'clause': {'code': 'clause_1'}},
                        {
                            'clause': {'code': 'clause_2'},
                            'customized_text': 'My Custom Text :)',
                            },
                        ],
                    'extra_data': {
                        'contract_1': '16.10',
                        'contract_2': False,
                        'contract_3': '2',
                        },
                    'coverages': [
                        {
                            'coverage': {'code': 'ALP'},
                            'extra_data': {
                                'option_1': '6.10',
                                'option_2': True,
                                'option_3': '2',
                                },
                            },
                        {
                            'coverage': {'code': 'BET'},
                            'extra_data': {},
                            },
                        ],
                    },
                ],
            'options': {
                'activate': True,
                },
            }

        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})
        contract = Contract(result['contracts'][0]['id'])
        self.assertEqual(len(contract.clauses), 2)
        self.assertEqual(contract.clauses[0].clause.code, 'clause_1')
        self.assertEqual(contract.clauses[0].text, 'Clause 1 contents')
        self.assertEqual(contract.clauses[1].clause.code, 'clause_2')
        self.assertEqual(contract.clauses[1].text, 'My Custom Text :)')

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['clauses'].append(
            {'clause': {'code': 'clause_3'}})
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'unauthorized_product_clause',
                    'data': {
                        'product': 'AAA',
                        'clause': 'clause_3',
                        },
                    }])

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['clauses'][0]['customized_text'] = 'Foo'
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'non_customizable_clause',
                    'data': {
                        'clause': 'clause_1',
                        },
                    }])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
