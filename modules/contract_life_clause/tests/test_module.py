# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_life_clause'

    @classmethod
    def fetch_models_for(cls):
        return ['offered_insurance', 'contract_insurance']

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
        )
    def test0010_addBeneficiaryClauses(self):
        pool = Pool()
        Coverage = pool.get('offered.option.description')
        Clause = pool.get('clause')

        coverage_a, = Coverage.search([('code', '=', 'ALP')])

        clause_benef_1 = Clause()
        clause_benef_1.code = 'clause_benef_1'
        clause_benef_1.name = 'Clause 1'
        clause_benef_1.content = 'Clause 1 contents'
        clause_benef_1.customizable = False
        clause_benef_1.kind = 'beneficiary'
        clause_benef_1.save()

        clause_benef_2 = Clause()
        clause_benef_2.code = 'clause_benef_2'
        clause_benef_2.name = 'Clause 2'
        clause_benef_2.content = 'Clause 2 contents (customizable <HERE>)'
        clause_benef_2.customizable = True
        clause_benef_2.kind = 'beneficiary'
        clause_benef_2.save()

        clause_benef_3 = Clause()
        clause_benef_3.code = 'clause_benef_3'
        clause_benef_3.name = 'Clause 3'
        clause_benef_3.content = 'Clause 3 contents'
        clause_benef_3.customizable = False
        clause_benef_3.kind = 'beneficiary'
        clause_benef_3.save()

        coverage_a.beneficiaries_clauses = [clause_benef_1, clause_benef_2]
        coverage_a.default_beneficiary_clause = clause_benef_2
        coverage_a.save()

    @test_framework.prepare_test(
        'contract_insurance.test0001_testPersonCreation',
        'contract_life_clause.test0010_addBeneficiaryClauses',
        'contract.test0005_PrepareProductForSubscription',
        'contract.test0002_testCountryCreation',
        )
    def test0060_subscribe_contract_API(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')
        Contract = pool.get('contract')
        Party = pool.get('party.party')

        baby, = Party.search([('name', '=', 'Antoine'),
                ('first_name', '=', 'Jeff')])

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
                                    'beneficiary_clause': {
                                        'clause': {'code': 'clause_benef_1'},
                                        'beneficiaries': [
                                            {
                                                'party': {'code': baby.code},
                                                'share': '0.5',
                                                },
                                            {
                                                'reference': 'My Dog',
                                                'share': '0.5',
                                                },
                                            ]
                                        },
                                    },
                                {
                                    'coverage': {'code': 'BET'},
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
        result = ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})
        contract = Contract(result['contracts'][0]['id'])
        option = contract.covered_elements[0].options[0]
        self.assertEqual(option.beneficiary_clause.code, 'clause_benef_1')
        self.assertEqual(
            option.customized_beneficiary_clause, 'Clause 1 contents')
        self.assertEqual(len(option.beneficiaries), 2)
        self.assertEqual(option.beneficiaries[0].party.id, baby.id)
        self.assertEqual(option.beneficiaries[0].share, Decimal('0.5'))

        data_dict = copy.deepcopy(data_ref)
        del data_dict['contracts'][0]['covereds'][0]['coverages'][0][
            'beneficiary_clause']
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'missing_beneficiary_clause',
                    'data': {
                        'coverage': 'ALP',
                        },
                    }])

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['covereds'][0]['coverages'][0][
            'beneficiary_clause']['clause']['code'] = 'clause_benef_3'
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'unauthorised_beneficiary_clause',
                    'data': {
                        'coverage': 'ALP',
                        'clause': 'clause_benef_3',
                        },
                    }])

        data_dict = copy.deepcopy(data_ref)
        del data_dict['contracts'][0]['covereds'][0]['coverages'][0][
            'beneficiary_clause']['beneficiaries'][0]['party']
        data_dict['contracts'][0]['covereds'][0]['coverages'][0][
            'beneficiary_clause']['beneficiaries'][0]['reference'] = ''
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'missing_beneficiary_identification',
                    'data': {
                        'coverage': 'ALP',
                        },
                    }])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
