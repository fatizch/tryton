# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
import copy

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'health'

    @classmethod
    def fetch_models_for(cls):
        return ['contract_insurance']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'PartyRelationType': 'party.relation.type',
            'PartyRelation': 'party.relation.all',
            'Contract': 'contract',
            'RuleEngineRuntime': 'rule_engine.runtime',
            'ItemDesc': 'offered.item.description',
            }

    @test_framework.prepare_test(
        'contract_insurance.test0005_PrepareProductForSubscription',
        )
    def test0005_PrepareProductForSubscription(self):
        pool = Pool()
        Coverage = pool.get('offered.option.description')

        coverages = Coverage.search([('item_desc', '!=', None)])
        for coverage in coverages:
            coverage.family = 'health'

        Coverage.save(coverages)

    def test0016_test_rule_engine_function(self):
        relation_spouse = self.PartyRelationType(name='Spouse', code='spouse')
        relation_spouse.save()
        relation_spouse.reverse = relation_spouse
        relation_spouse.reverse.save()
        relation_child, = self.PartyRelationType.search(
            [('code', '=', 'child')])
        party_father = self.Party(name='Father', first_name='F', gender='male',
            is_person=True, birth_date=datetime.date(1978, 2, 15))
        party_father.save()
        party_mother = self.Party(name='Mother', first_name='M',
            gender='female', is_person=True,
            birth_date=datetime.date(1975, 7, 10),
            relations=[{'to': party_father, 'type': relation_spouse}])
        party_mother.save()
        party_child1 = self.Party(name='Child1', first_name='C', gender='male',
            is_person=True, birth_date=datetime.date(2010, 3, 5),
            relations=[{'to': party_father, 'type': relation_child},
                {'to': party_mother, 'type': relation_child}])
        party_child1.save()
        party_child2 = self.Party(name='Child2', first_name='C',
            gender='female', is_person=True,
            birth_date=datetime.date(2009, 5, 15),
            relations=[{'to': party_father, 'type': relation_child},
                {'to': party_mother, 'type': relation_child}])
        party_child2.save()

        contract = self.Contract(subscriber=party_father, status='activate',
            activation_history=[{'start_date': datetime.date(2014, 1, 1),
                    'end_date': datetime.date(2016, 12, 31)}],
            covered_elements=[{
                    'party': party_father,
                    'options': [{
                            'initial_start_date': datetime.date(2014, 1, 1),
                            'start_date': datetime.date(2014, 1, 1),
                            'final_end_date': None,
                            'status': 'active'
                            }],
                    'sub_covered_elements': [],
                    }, {
                    'party': party_mother,
                    'options': [{
                            'initial_start_date': datetime.date(2014, 1, 1),
                            'start_date': datetime.date(2014, 1, 1),
                            'final_end_date': None,
                            'status': 'active'
                            }],
                    'sub_covered_elements': [],
                    }, {
                    'party': party_child1,
                    'options': [{
                            'initial_start_date': datetime.date(2014, 1, 1),
                            'start_date': datetime.date(2014, 1, 1),
                            'final_end_date': None,
                            'status': 'active'
                            }],
                    'sub_covered_elements': [],
                    }, {
                    'party': party_child2,
                    'options': [{
                            'initial_start_date': datetime.date(2014, 1, 1),
                            'start_date': datetime.date(2014, 1, 1),
                            'status': 'active',
                            'final_end_date': datetime.date(2014, 1, 31)}],
                    'sub_covered_elements': [],
                    }])
        # Force set function fields that will be used
        item_desc = self.ItemDesc(sub_item_descs=[])
        for covered_element in contract.covered_elements:
            covered_element.contract = contract
            covered_element.item_desc = item_desc
            covered_element.contract = contract
            covered_element.options[0].main_contract = contract
            for option in covered_element.options:
                option.parent_contract = contract
        args = {'contract': contract, 'person': party_child1,
            'date': datetime.date(2014, 1, 1)}
        # test _re_relation_number
        self.assertEqual(
            self.RuleEngineRuntime._re_relation_number_order_by_age(args,
                'child'), 2)
        args = {'contract': contract, 'person': party_child2,
            'date': datetime.date(2014, 1, 1)}
        self.assertEqual(
            self.RuleEngineRuntime._re_relation_number_order_by_age(args,
                'child'), 1)
        args = {'contract': contract, 'person': party_child2,
            'date': datetime.date(2014, 2, 1)}
        self.assertEqual(
            self.RuleEngineRuntime._re_relation_number_order_by_age(args,
                'child'), 1)
        args = {'contract': contract, 'person': party_child2,
            'date': datetime.date(2014, 1, 1)}
        self.assertEqual(
            self.RuleEngineRuntime._re_relation_number_order_by_age(args,
                'child'), 1)
        # test _re_number_of_covered_with_relation
        args = {'contract': contract, 'date': datetime.date(2014, 1, 1)}
        self.assertEqual(self.RuleEngineRuntime.
            _re_number_of_covered_with_relation(args, 'child'), 2)
        self.assertEqual(self.RuleEngineRuntime.
            _re_number_of_covered_with_relation(args, 'spouse'), 2)
        args = {'contract': contract, 'date': datetime.date(2014, 2, 1)}
        self.assertEqual(self.RuleEngineRuntime.
            _re_number_of_covered_with_relation(args, 'child'), 1)
        self.assertEqual(self.RuleEngineRuntime.
            _re_number_of_covered_with_relation(args, 'spouse'), 2)

    @test_framework.prepare_test(
        'health.test0005_PrepareProductForSubscription',
        'contract.test0002_testCountryCreation',
        )
    def test0060_subscribe_contract_API(self):
        ContractAPI = Pool().get('api.contract')
        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Mother',
                    'birth_date': '1978-01-14',
                    'gender': 'female',
                    'ssn': '145067512312354',
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
                                    },
                                {
                                    'coverage': {'code': 'BET'},
                                    'extra_data': {},
                                    },
                                {
                                    'coverage': {'code': 'GAM'},
                                    'extra_data': {},
                                    },
                                ],
                            },
                        ],
                    'coverages': [
                        {
                            'coverage': {'code': 'DEL'},
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
        self.ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})

        data_dict = copy.deepcopy(data_ref)
        data_dict['parties'][0]['first_name'] = 'Auntie'
        del data_dict['parties'][0]['ssn']
        self.assertEqual(
            ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'missing_ssn',
                    'data': {'field': 'covered.party'},
                    }])

        data_dict = copy.deepcopy(data_ref)
        data_dict['parties'][0]['first_name'] = 'Auntie'
        data_dict['parties'][0]['ssn'] = '145067512312353'
        self.assertEqual(
            ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'invalid_ssn',
                    'data': {'ssn': '145067512312353'},
                    }])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
