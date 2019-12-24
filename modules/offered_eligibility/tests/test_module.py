# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import copy

from collections import defaultdict

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.pool import Pool
from trytond.transaction import Transaction


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'offered_eligibility'

    @classmethod
    def fetch_models_for(cls):
        return ['offered_insurance', 'contract']

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
        'contract.test0005_PrepareProductForSubscription',
        )
    def test0100_PrepareProductForSubscription(self):
        pool = Pool()
        OptionDescription = pool.get('offered.option.description')
        OptionDescriptionEligibility = pool.get(
            'offered.option.description.eligibility_rule')
        Product = pool.get('offered.product')
        Rule = pool.get('rule_engine')
        product, = Product.search([
                ('code', '=', 'AAA'),
                ])
        age_rule, = Rule.search([('short_name', '=', 'option_age_eligibility')])
        coverage_a, = OptionDescription.search([('code', '=', 'ALP')])
        eligibility_rule = OptionDescriptionEligibility()
        eligibility_rule.rule = age_rule
        eligibility_rule.coverage = coverage_a
        eligibility_rule.rule_extra_data = {'max_age_for_option': 50,
            'age_kind': 'real'}
        eligibility_rule.save()

        all_coverages = OptionDescription.search([])
        OptionDescription.write(all_coverages,
            {'allow_subscribe_coverage_multiple_times': True})

    @test_framework.prepare_test(
        'offered_eligibility.test0100_PrepareProductForSubscription',
        'contract_insurance.test0001_testPersonCreation',
        'contract.test0002_testCountryCreation',
        )
    def test0200_subscribe_contract_eligibility_API(self):
        pool = Pool()
        Contract = pool.get('contract')
        baby, = self.Party.search([('name', '=', 'Antoine'),
                ('first_name', '=', 'Jeff')])
        base_input = {
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
                    'relations': [
                        {
                            'ref': '1',
                            'type': 'parent',
                            'to': {'id': baby.id},
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
                        {
                            'party': {'id': baby.id},
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
        input_ = copy.deepcopy(base_input)
        self.ContractAPI.subscribe_contracts(input_,
            {'_debug_server': True})
        first_contract, = Contract.search([])
        summary = {}
        for cov in first_contract.covered_elements:
            summary[cov.party.first_name] = [(x.coverage.code,
                    x.status) for x in cov.options]
        self.assertEqual(summary,
            {
                'Mother': [('ALP', 'active'), ('BET', 'active'),
                    ('GAM', 'active')],
                'Jeff': [('ALP', 'active'), ('BET', 'active')],
            }
        )

        #  Now make mother much older, activation should fail
        input_ = copy.deepcopy(base_input)
        input_['parties'][0]['birth_date'] = '1940-01-14'
        out = self.ContractAPI.subscribe_contracts(input_, {})
        self.assertEqual(out.data['message'],
            'Option Alpha Coverage is not eligible.')

    @test_framework.prepare_test(
        'offered_eligibility.test0100_PrepareProductForSubscription',
        'contract_insurance.test0001_testPersonCreation',
        'contract.test0002_testCountryCreation',
        'offered_eligibility.test0200_subscribe_contract_eligibility_API',
        )
    def test0300_simulate_contract_eligibility_API(self):
        baby, = self.Party.search([('name', '=', 'Antoine'),
                ('first_name', '=', 'Jeff')])
        base_input = {
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
                    'relations': [
                        {
                            'ref': '1',
                            'type': 'parent',
                            'to': {'id': baby.id},
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
                        {
                            'party': {'id': baby.id},
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
                'decline_non_eligible': True,
                },
            }

        def test_elig(input_, expected):

            output = self.ContractAPI.simulate(input_, {'_debug_server': True})
            summary = defaultdict(list)
            for covered in output[0]['covereds']:
                if 'ref' not in covered['party']:
                    key = 'party:id:' + str(covered['party']['id'])
                else:
                    key = 'ref:' + covered['party']['ref']
                for coverage in covered['coverages']:
                    desc = coverage['coverage']
                    summary[key].append((desc['code'], coverage['eligibility']))

            self.maxDiff = None
            self.assertEqual(dict(summary), expected)

        # We have to commit here because simulate is executed in a new
        # transaction, which cannot have access to the contents of the testing
        # transaction
        Transaction().commit()

        expected = {
            'ref:1': [
                ('ALP', {'eligible': True}),
                ('BET', {'eligible': True}),
                ('GAM', {'eligible': True})],
            'party:id:12': [
                ('ALP', {'eligible': True}),
                ('BET', {'eligible': True})],
        }

        input_ = copy.deepcopy(base_input)

        test_elig(input_, expected)

        #  Now make mother much older, non eligible options
        #  should be declined
        input_ = copy.deepcopy(base_input)
        input_['parties'][0]['birth_date'] = '1940-01-14'

        expected = {
            'ref:1': [
                ('ALP', {'eligible': False,
                        'message': 'Option Alpha Coverage is not eligible.'}),
                ('BET', {'eligible': True}),
                ('GAM', {'eligible': True})],
            'party:id:12': [
                ('ALP', {'eligible': True}),
                ('BET', {'eligible': True})],
        }
        test_elig(input_, expected)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
