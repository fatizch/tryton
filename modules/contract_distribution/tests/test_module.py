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
    module = 'contract_distribution'

    @classmethod
    def fetch_models_for(cls):
        return ['contract', 'distribution', 'offered']

    @test_framework.prepare_test(
        'contract.test0002_testCountryCreation',
        'contract.test0005_PrepareProductForSubscription',
        'distribution.test0002_dist_network_creation',
        )
    def test0002_test_commercial_products(self):
        pool = Pool()
        DistNetwork = pool.get('distribution.network')
        Product = pool.get('offered.product')
        ComProduct = pool.get('distribution.commercial_product')

        product, = Product.search([('code', '=', 'AAA')])
        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])

        com_product_1 = ComProduct()
        com_product_1.code = 'com_product_1'
        com_product_1.name = 'Commercial Product 1'
        com_product_1.product = product
        com_product_1.save()

        com_product_2 = ComProduct()
        com_product_2.code = 'com_product_2'
        com_product_2.name = 'Commercial Product 2'
        com_product_2.product = product
        com_product_2.save()

        node_1.commercial_products = [com_product_1]
        node_1.save()
        node_1_1.commercial_products = [com_product_2]
        node_1_1.save()

        self.assertEqual({x.code for x in node_1.all_com_products},
            {'com_product_1'})
        self.assertEqual({x.code for x in node_1_1.all_com_products},
            {'com_product_1', 'com_product_2'})

    @test_framework.prepare_test(
        'contract_distribution.test0002_test_commercial_products',
        )
    def test0005_test_product_description_API(self):
        pool = Pool()
        APIProduct = pool.get('api.product')
        Product = pool.get('offered.product')
        DistNetwork = pool.get('distribution.network')
        ComProduct = pool.get('distribution.commercial_product')

        product_a, = Product.search([('code', '=', 'AAA')])
        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])
        com_product_1, = ComProduct.search([('code', '=', 'com_product_1')])
        com_product_2, = ComProduct.search([('code', '=', 'com_product_2')])

        self.maxDiff = None

        base_product_output = [
            {
                'id': product_a.id,
                'code': 'AAA',
                'name': 'Awesome Alternative Allowance',
                'description': '',
                'extra_data': [
                    {
                        'code': 'contract_1',
                        'name': 'Contract 1',
                        'type': 'numeric',
                        'sequence': 1,
                        'digits': 2,
                        },
                    {
                        'code': 'contract_2',
                        'name':
                        'Contract 2',
                        'type': 'boolean',
                        'sequence': 2,
                        },
                    {
                        'code': 'contract_3',
                        'name': 'Contract 3',
                        'type': 'selection',
                        'sequence': 3,
                        'selection': [
                            {'value': '1', 'name': '1',
                                'sequence': 0},
                            {'value': '2', 'name': '2',
                                'sequence': 1},
                            {'value': '3', 'name': '3',
                                'sequence': 2},
                            ],
                        },
                    ],
                'coverages': [
                    {
                        'id': product_a.coverages[0].id,
                        'name': 'Alpha Coverage',
                        'code': 'ALP',
                        'description': '',
                        'extra_data': [
                            {
                                'code': 'option_1',
                                'name': 'Option 1',
                                'type': 'numeric',
                                'sequence': 4,
                                'digits': 2,
                                },
                            {
                                'code': 'option_2',
                                'name':
                                'Option 2',
                                'type': 'boolean',
                                'sequence': 5,
                                },
                            {
                                'code': 'option_3',
                                'name': 'Option 3',
                                'type': 'selection',
                                'sequence': 6,
                                'selection': [
                                    {'value': '1', 'name': '1',
                                        'sequence': 0},
                                    {'value': '2', 'name': '2',
                                        'sequence': 1},
                                    {'value': '3', 'name': '3',
                                        'sequence': 2},
                                    ],
                                },
                            ],
                        },
                    {
                        'id': product_a.coverages[1].id,
                        'name': 'Beta Coverage',
                        'code': 'BET',
                        'description': '',
                        'extra_data': [],
                        },
                    ],
                'packages': [],
                'subscriber': {
                    'model': 'party',
                    'required': ['name', 'first_name', 'birth_date',
                        'email', 'addresses'],
                    'fields': ['name', 'first_name', 'birth_date',
                        'email', 'phone_number', 'is_person', 'addresses'],
                    },
                },
            ]

        self.assertEqual(APIProduct.describe_products(
                {}, {'_debug_server': True}), base_product_output)

        self.assertEqual(APIProduct.describe_products(
                {}, {'_debug_server': True, 'dist_network': node_1.id})[0][
                'commercial_products'], [{
                    'code': 'com_product_1',
                    'id': com_product_1.id,
                    'name': 'Commercial Product 1',
                    }])

        self.assertEqual(
            sorted(APIProduct.describe_products({}, {'_debug_server': True,
                        'dist_network': node_1_1.id})[0]['commercial_products'],
                key=lambda x: x['code']),
            [
                {'code': 'com_product_1', 'id': com_product_1.id,
                    'name': 'Commercial Product 1'},
                {'code': 'com_product_2', 'id': com_product_2.id,
                    'name': 'Commercial Product 2'},
                ])

    @test_framework.prepare_test(
        'contract_distribution.test0002_test_commercial_products',
        )
    def test0010_test_subscription_API(self):
        pool = Pool()
        DistNetwork = pool.get('distribution.network')
        Contract = pool.get('contract')
        ContractAPI = pool.get('api.contract')

        node_1, = DistNetwork.search([('code', '=', 'node_1')])

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
                    'relations': [
                        {
                            'ref': '3',
                            'type': 'child',
                            'to': {'ref': '3'},
                            },
                        ],
                    },
                {
                    'ref': '2',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Baby',
                    'birth_date': '2010-02-12',
                    'gender': 'female',
                    },
                {
                    'ref': '3',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Grand-Pa',
                    'birth_date': '1920-04-08',
                    'gender': 'male',
                    },
                ],
            'relations': [
                {
                    'ref': '1',
                    'type': 'child',
                    'from': {'ref': '2'},
                    'to': {'ref': '1'},
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {
                        'contract_1': '16.10',
                        'contract_2': False,
                        'contract_3': '2',
                        },
                    'commercial_product': {'code': 'com_product_1'},
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
            {'_debug_server': True, 'dist_network': node_1.id})

        contract = Contract(result['contracts'][0]['id'])
        self.assertEqual(contract.dist_network.id, node_1.id)
        self.assertEqual(contract.com_product.code, 'com_product_1')

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['commercial_product']['code'] = \
            'com_product_2'
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict,
                {'dist_network': node_1.id}).data,
            [{'type': 'unauthorized_commercial_product',
                    'data': {
                        'product': 'AAA',
                        'commercial_product': 'com_product_2',
                        'dist_network': node_1.id,
                        },
                    }])

        data_dict = copy.deepcopy(data_ref)
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{'type': 'missing_dist_network', 'data': {}}])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
