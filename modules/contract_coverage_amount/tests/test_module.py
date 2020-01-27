# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.pool import Pool
from trytond.server_context import ServerContext
from trytond.transaction import Transaction

from trytond.modules.coog_core import test_framework
from trytond.modules.rule_engine.tests.test_module import test_tree_element


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'contract_coverage_amount'

    @classmethod
    def fetch_models_for(cls):
        return ['contract_insurance', 'rule_engine']

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
        )
    def test0005_AddCoverageAmountRule(self):
        pool = Pool()
        Coverage = pool.get('offered.option.description')
        CoverageAmountRule = pool.get('offered.coverage_amount.rule')
        Language = pool.get('ir.lang')
        Product = pool.get('offered.product')
        RuleContext = pool.get('rule_engine.context')
        RuleEngine = pool.get('rule_engine')

        product_a, = Product.search([('code', '=', 'AAA')])
        coverage_a, = Coverage.search([('code', '=', 'ALP')])
        coverage_b, = Coverage.search([('code', '=', 'BET')])
        coverage_c, = Coverage.search([('code', '=', 'GAM')])
        rule_context, = RuleContext.search([('name', '=', 'test_context')])
        english, = Language.search([('code', '=', 'en')])

        # Create coverage amount tree element
        tree_element = self.RuleFunction()
        tree_element.type = 'function'
        tree_element.name = '_re_get_coverage_amount'
        tree_element.translated_technical_name = 'coverage_amount'
        tree_element.description = ''
        tree_element.namespace = 'rule_engine.runtime'
        tree_element.language = english
        tree_element.context = rule_context
        tree_element.save()

        rule_context.allowed_elements = list(rule_context.allowed_elements) + [
            tree_element]
        rule_context.save()

        rule_coverage_amount = RuleEngine()
        rule_coverage_amount.type_ = 'coverage_amount_selection'
        rule_coverage_amount.context = rule_context
        rule_coverage_amount.status = 'validated'
        rule_coverage_amount.name = 'Regle Coverage Amount'
        rule_coverage_amount.short_name = 'rule_coverage_amount'
        rule_coverage_amount.description = 'dolor sic amet'
        rule_coverage_amount.algorithm = '''
return [100 * x for x in [1, 2, 3, 4, 5]]
'''
        rule_coverage_amount.save()

        rule_coverage_validation = RuleEngine()
        rule_coverage_validation.type_ = 'coverage_amount_validation'
        rule_coverage_validation.context = rule_context
        rule_coverage_validation.status = 'validated'
        rule_coverage_validation.name = 'Regle Coverage Amount'
        rule_coverage_validation.short_name = 'rule_coverage_validation'
        rule_coverage_validation.description = 'dolor sic amet'
        rule_coverage_validation.algorithm = '''
return coverage_amount() < 1000
'''
        rule_coverage_validation.save()

        rule_coverage_calculation = RuleEngine()
        rule_coverage_calculation.type_ = 'coverage_amount_calculation'
        rule_coverage_calculation.context = rule_context
        rule_coverage_calculation.status = 'validated'
        rule_coverage_calculation.name = 'Regle Coverage Amount'
        rule_coverage_calculation.short_name = 'rule_coverage_calculation'
        rule_coverage_calculation.description = 'dulce periculum'
        rule_coverage_calculation.algorithm = '''
return Decimal('100.00')
'''
        rule_coverage_calculation.save()

        coverage_a.coverage_amount_rules = [
            CoverageAmountRule(amount_mode='free_input',
                rule=rule_coverage_validation)
            ]
        coverage_a.save()

        coverage_b.coverage_amount_rules = [
            CoverageAmountRule(amount_mode='selection',
                rule=rule_coverage_amount)
            ]
        coverage_b.save()

        coverage_c.coverage_amount_rules = [
            CoverageAmountRule(
                amount_mode='calculated_amount',
                rule=rule_coverage_calculation,
                label='Montant calculé',
                )
            ]
        coverage_c.save()

        product_a.coverages = [coverage_a, coverage_b, coverage_c]
        product_a.save()

    @test_framework.prepare_test(
        'contract_coverage_amount.test0005_AddCoverageAmountRule',
        'contract.test0005_PrepareProductForSubscription',
        )
    def test0050_productDescription(self):
        product, = self.Product.search([('code', '=', 'AAA')])
        alpha, = self.OptionDescription.search([('code', '=', 'ALP')])
        beta, = self.OptionDescription.search([('code', '=', 'BET')])
        gamma, = self.OptionDescription.search([('code', '=', 'GAM')])
        item_desc, = self.ItemDesc.search([('code', '=', 'person')])

        self.maxDiff = None
        self.assertEqual(
            self.APIProduct.describe_products({}, {'_debug_server': True}),
            [{
                    'code': 'AAA',
                    'coverages': [
                        ],
                    'description': '',
                    'extra_data': [],
                    'id': product.id,
                    'item_descriptors': [
                        {
                            'code': 'person',
                            'coverages': [
                                {
                                    'code': 'ALP',
                                    'description': '',
                                    'extra_data': [],
                                    'id': alpha.id,
                                    'mandatory': True,
                                    'name': 'Alpha Coverage',
                                    'coverage_amount': {
                                        'label': 'Coverage Amount',
                                        'name': 'coverage_amount',
                                        'required': True,
                                        'sequence': 0,
                                        'type': 'amount',
                                        'help': '',
                                        },
                                    },
                                {
                                    'code': 'BET',
                                    'description': '',
                                    'extra_data': [],
                                    'id': beta.id,
                                    'mandatory': True,
                                    'name': 'Beta Coverage',
                                    'coverage_amount': {
                                        'enum': ['100', '200', '300', '400',
                                            '500'],
                                        'name': 'coverage_amount',
                                        'required': True,
                                        'label': 'Coverage Amount',
                                        'sequence': 0,
                                        'help': '',
                                        'type': 'amount'
                                        },
                                    },
                                {
                                    'code': 'GAM',
                                    'description': '',
                                    'extra_data': [],
                                    'id': gamma.id,
                                    'mandatory': False,
                                    'name': 'GammaCoverage',
                                    },
                                ],
                            'extra_data': [],
                            'party': {
                                'model': 'party',
                                'domains': {
                                    'quotation': [
                                        {
                                            'fields': [
                                                {
                                                    'code': 'birth_date',
                                                    'required': True
                                                }
                                            ],
                                            'conditions': [
                                                {
                                                    'name': 'is_person',
                                                    'operator': '=',
                                                    'value': True
                                                },
                                            ]
                                        },
                                    ],
                                    'subscription': [
                                        {
                                            'conditions': [
                                                {
                                                    'name': 'is_person',
                                                    'operator': '=',
                                                    'value': True
                                                },
                                            ],
                                            'fields': [
                                                {'code': 'addresses',
                                                    'required': True},
                                                {'code': 'birth_date',
                                                    'required': True},
                                                {'code': 'email',
                                                    'required': False},
                                                {'code': 'first_name',
                                                    'required': True},
                                                {'code': 'is_person',
                                                    'required': False},
                                                {'code': 'name',
                                                    'required': True},
                                                {'code': 'phone',
                                                    'required': False},
                                            ],
                                        },
                                    ]
                                }},
                            'id': item_desc.id,
                            'name': 'Person'}],
                    'name': 'Awesome Alternative Allowance',
                    'packages': [],
                    'subscriber': {
                        'model': 'party',
                        'domains': {
                            'quotation': [
                                {
                                    'fields': [],
                                },
                            ],
                            'subscription': [
                                {
                                    'conditions': [
                                        {'name': 'is_person', 'operator': '=',
                                            'value': True},
                                        ],
                                    'fields': [
                                        {'code': 'addresses',
                                            'required': True},
                                        {'code': 'birth_date',
                                            'required': True},
                                        {'code': 'email',
                                            'required': False},
                                        {'code': 'first_name',
                                            'required': True},
                                        {'code': 'is_person',
                                            'required': False},
                                        {'code': 'name',
                                            'required': True},
                                        {'code': 'phone',
                                            'required': False},
                                    ],
                                },
                                {
                                    'conditions': [
                                        {'name': 'is_person', 'operator': '=',
                                            'value': False},
                                        ],
                                    'fields': [
                                        {'code': 'addresses',
                                            'required': True},
                                        {'code': 'email',
                                            'required': False},
                                        {'code': 'is_person',
                                            'required': False},
                                        {'code': 'name',
                                            'required': True},
                                        {'code': 'phone',
                                            'required': False},
                                    ],
                                },
                            ]
                        }
                    },
                    },
                ]
            )

    @test_framework.prepare_test(
        'contract_coverage_amount.test0005_AddCoverageAmountRule',
        'contract.test0005_PrepareProductForSubscription',
        'contract.test0002_testCountryCreation',
        )
    def test0060_subscribe_contract_API(self):
        pool = Pool()
        Contract = pool.get('contract')
        ContractAPI = pool.get('api.contract')

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Mother',
                    'birth_date': '1978-01-14',
                    'gender': 'female',
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
                    'extra_data': {},
                    'covereds': [
                        {
                            'party': {'ref': '1'},
                            'item_descriptor': {'code': 'person'},
                            'coverages': [
                                {
                                    'coverage': {'code': 'ALP'},
                                    'extra_data': {},
                                    'coverage_amount': '501.23',
                                    },
                                {
                                    'coverage': {'code': 'BET'},
                                    'extra_data': {},
                                    'coverage_amount': '100.00',
                                    },
                                {
                                    'coverage': {'code': 'GAM'},
                                    }
                                ],
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
        self.assertEqual(
            contract.covered_elements[0].options[0].current_coverage_amount,
            Decimal('501.23'))
        self.assertEqual(
            contract.covered_elements[0].options[1].current_coverage_amount,
            Decimal('100.00'))
        self.assertEqual(
            contract.covered_elements[0].options[2].current_coverage_amount,
            Decimal('100.00'))
        self.assertEqual(
            contract.covered_elements[0].options[2].coverage_amount_label,
            'Montant calculé')

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['covereds'][0]['coverages'][1][
            'coverage_amount'] = '10000.00'
        self.maxDiff = None
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data,
            {
                'code': 1,
                'description': '',
                'message': 'Coverage amount "10000.00" is invalid for coverage '
                '"Beta Coverage".',
                })

        data_dict = copy.deepcopy(data_ref)
        del data_dict['contracts'][0]['covereds'][0]['coverages'][1][
            'coverage_amount']
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'missing_coverage_amount',
                    'data': {
                        'coverage': 'BET',
                        },
                    }])

    def test0200_test_api_rule_tree_elements(self):
        APIRuleRuntime = Pool().get('api.rule_runtime')
        with ServerContext().set_context(_test_api_tree_elements=True):
            with ServerContext().set_context(
                    api_rule_context=APIRuleRuntime.get_runtime()):
                self.assertEqual(test_tree_element(
                        'rule_engine.runtime',
                        '_re_get_coverage_amount',
                        {'api.option':
                            {'coverage_amount': Decimal('123.45')}}
                        ).result,
                    Decimal('123.45'))

    @test_framework.prepare_test(
        'contract_coverage_amount.test0005_AddCoverageAmountRule',
        'contract.test0005_PrepareProductForSubscription',
        'contract.test0002_testCountryCreation',
        )
    def test9910_test_simulate_API(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Mother',
                    'birth_date': '1978-01-14',
                    'gender': 'female',
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
                    'extra_data': {},
                    'covereds': [
                        {
                            'party': {'ref': '1'},
                            'item_descriptor': {'code': 'person'},
                            'coverages': [
                                {
                                    'coverage': {'code': 'ALP'},
                                    'extra_data': {},
                                    'coverage_amount': '501.23',
                                    },
                                {
                                    'coverage': {'code': 'BET'},
                                    'extra_data': {},
                                    'coverage_amount': '100.00',
                                    },
                                {
                                    'coverage': {'code': 'GAM'},
                                    }
                                ],
                            },
                        ],
                    },
                ],
            'options': {},
            }

        # We have to commit here because simulate is executed in a new
        # transaction, which cannot have access to the contents of the testing
        # transaction
        Transaction().commit()

        data_dict = copy.deepcopy(data_ref)
        simulation = ContractAPI.simulate(data_dict, {'_debug_server': True})

        self.assertEqual(len(simulation), 1)
        self.assertEqual(simulation[0]['ref'], '1')
        self.assertEqual(simulation[0]['product']['code'], 'AAA')
        coverages = simulation[0]['covereds'][0]['coverages']
        self.assertEqual(len(coverages), 3)
        self.assertEqual(coverages[2]['coverage_amount'], {
                'amount': '100.00',
                'label': 'Montant calculé',
                })


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
