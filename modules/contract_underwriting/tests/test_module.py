# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest

from decimal import Decimal
from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton

from trytond.pool import Pool
from trytond.exceptions import UserError

from trytond.modules.api import date_for_api
from trytond.modules.coog_core import test_framework, utils


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_underwriting'

    @classmethod
    def fetch_models_for(cls):
        return ['offered_insurance', 'contract']

    def test0005_create_exclusions_extra_premiums_kinds(self):
        pool = Pool()
        ExtraPremium = pool.get('extra_premium.kind')
        Exclusion = pool.get('offered.exclusion')

        exclusion_1 = Exclusion()
        exclusion_1.code = 'exclusion_1'
        exclusion_1.name = 'Exclusion 1'
        exclusion_1.save()

        exclusion_2 = Exclusion()
        exclusion_2.code = 'exclusion_2'
        exclusion_2.name = 'Exclusion 2'
        exclusion_2.save()

        extra_premium_1 = ExtraPremium()
        extra_premium_1.code = 'extra_premium_1'
        extra_premium_1.name = 'Extra Premium 1'
        extra_premium_1.save()

        extra_premium_2 = ExtraPremium()
        extra_premium_2.code = 'extra_premium_2'
        extra_premium_2.name = 'Extra Premium 2'
        extra_premium_2.save()

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
        'contract_underwriting.test0005_create_exclusions_extra_premiums_kinds',
        )
    def test0010_AddUnderwritingConfiguration(self):
        pool = Pool()
        Coverage = pool.get('offered.option.description')
        UnderwritingRule = pool.get('underwriting.rule')
        Decision = pool.get('underwriting.decision')
        RuleEngine = pool.get('rule_engine')

        coverage_a, = Coverage.search([('code', '=', 'ALP')])
        coverage_b, = Coverage.search([('code', '=', 'BET')])
        coverage_c, = Coverage.search([('code', '=', 'GAM')])

        basic_rule, = RuleEngine.search([
                ('short_name', '=', 'underwriting_basic_rule')])

        contract_pending = Decision()
        contract_pending.status = 'pending'
        contract_pending.name = 'Pending'
        contract_pending.code = 'pending_contract'
        contract_pending.level = 'contract'
        contract_pending.save()

        contract_accept = Decision()
        contract_accept.status = 'accepted'
        contract_accept.name = 'Accepted'
        contract_accept.code = 'accepted_contract'
        contract_accept.level = 'contract'
        contract_accept.save()

        contract_denied = Decision()
        contract_denied.status = 'denied'
        contract_denied.name = 'Denieded'
        contract_denied.code = 'denied_contract'
        contract_denied.level = 'contract'
        contract_denied.save()

        contract_accept_conditions = Decision()
        contract_accept_conditions.status = 'accepted_with_conditions'
        contract_accept_conditions.name = 'Accept with Conditions'
        contract_accept_conditions.code = 'accept_with_conditions_contract'
        contract_accept_conditions.level = 'contract'
        contract_accept_conditions.save()

        option_pending = Decision()
        option_pending.status = 'pending'
        option_pending.name = 'Pending'
        option_pending.code = 'pending_option'
        option_pending.level = 'coverage'
        option_pending.contract_decisions = [contract_accept,
            contract_accept_conditions, contract_denied, contract_pending]
        option_pending.save()

        option_accept = Decision()
        option_accept.status = 'accepted'
        option_accept.name = 'Accepted'
        option_accept.code = 'accepted_option'
        option_accept.level = 'coverage'
        option_accept.contract_decisions = [contract_accept,
            contract_accept_conditions, contract_denied, contract_pending]
        option_accept.save()

        bad_option_accept = Decision()
        bad_option_accept.status = 'accepted'
        bad_option_accept.name = 'Accepted (BAD)'
        bad_option_accept.code = 'accepted_option_bad'
        bad_option_accept.level = 'coverage'
        bad_option_accept.contract_decisions = [contract_accept,
            contract_accept_conditions, contract_denied, contract_pending]
        bad_option_accept.save()

        option_accept_conditions = Decision()
        option_accept_conditions.status = 'accepted_with_conditions'
        option_accept_conditions.name = 'Accept with Conditions'
        option_accept_conditions.code = 'accept_with_conditions_option'
        option_accept_conditions.level = 'coverage'
        option_accept_conditions.contract_decisions = [
            contract_accept_conditions, contract_accept, contract_denied,
            contract_pending]
        option_accept_conditions.save()

        option_denied = Decision()
        option_denied.status = 'denied'
        option_denied.name = 'Denied'
        option_denied.code = 'denied_option'
        option_denied.level = 'coverage'
        option_denied.decline_option = True
        option_denied.contract_decisions = [contract_accept,
            contract_accept_conditions, contract_denied, contract_pending]
        option_denied.save()

        coverage_a_rule = UnderwritingRule()
        coverage_a_rule.coverage = coverage_a
        coverage_a_rule.rule = basic_rule
        coverage_a_rule.rule_extra_data = {'always_underwrite': True}
        coverage_a_rule.decisions = [option_accept, option_accept_conditions]
        coverage_a_rule.accepted_decision = option_accept
        coverage_a_rule.save()

        coverage_a.with_exclusions = True
        coverage_a.with_extra_premiums = True
        coverage_a.save()

        coverage_b_rule = UnderwritingRule()
        coverage_b_rule.coverage = coverage_b
        coverage_b_rule.rule = basic_rule
        coverage_b_rule.rule_extra_data = {'always_underwrite': True}
        coverage_b_rule.decisions = [option_accept, option_accept_conditions,
            option_denied]
        coverage_b_rule.accepted_decision = option_accept
        coverage_b_rule.save()

        coverage_c_rule = UnderwritingRule()
        coverage_c_rule.coverage = coverage_c
        coverage_c_rule.rule = basic_rule
        coverage_c_rule.rule_extra_data = {'always_underwrite': False}
        coverage_c_rule.decisions = [option_accept, option_accept_conditions]
        coverage_c_rule.accepted_decision = option_accept
        coverage_c_rule.save()

    @test_framework.prepare_test(
        'contract_underwriting.test0010_AddUnderwritingConfiguration',
        'contract_insurance.test0001_testPersonCreation',
        'contract.test0005_PrepareProductForSubscription',
        'contract.test0002_testCountryCreation',
        )
    def test0060_test_subscription_api(self):
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

        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(data_dict, {})

        # Logical, the underwriting is not yet done
        self.assertEqual(result.data['message'],
            'The underwriting process is still in progress.')

        # Ok so we just do not activate for now
        data_ref['options'] = {}

        data_dict = copy.deepcopy(data_ref)
        result = self.ContractAPI.subscribe_contracts(
            data_dict, {'_debug_server': True})
        contract = Contract(result['contracts'][0]['id'])

        self.assertEqual(len(contract.underwritings), 1)
        self.assertEqual(len(contract.underwritings[0].underwriting_options), 5)
        self.assertEqual(contract.underwritings[0].decision, None)

        mother = Party(result['parties'][0]['id'])
        self.assertEqual(
            {(x.option.covered_element.party.code, x.option.coverage.code,
                    x.decision.code if x.decision else None)
                for x in contract.underwritings[0].underwriting_options},
            {
                (mother.code, 'ALP', None),
                (mother.code, 'BET', None),
                (mother.code, 'GAM', 'accepted_option'),
                (baby.code, 'ALP', None),
                (baby.code, 'BET', None),
                }
            )

    @test_framework.prepare_test(
        'contract_underwriting.test0060_test_subscription_api',
        )
    def test0061_test_underwriting_acceptation(self):
        pool = Pool()
        Contract = pool.get('contract')
        Decision = pool.get('underwriting.decision')

        option_accepted, = Decision.search(
            [('code', '=', 'accepted_option')])
        option_denied, = Decision.search(
            [('code', '=', 'denied_option')])
        option_accept_conditions, = Decision.search(
            [('code', '=', 'accept_with_conditions_option')])
        contract_accepted, = Decision.search(
            [('code', '=', 'accepted_contract')])

        # test0060_test_subscription_api creates two contracts, since the first
        # calls fails in the activation process.
        contract = Contract.search([])[-1]

        # We still cannot activate the contract
        self.assertRaises(UserError,
            Contract.activate_contract, [contract])

        contract.underwritings[0].underwriting_options[0].decision = \
            option_accepted
        contract.underwritings[0].underwriting_options[1].decision = \
            option_accepted
        contract.underwritings[0].underwriting_options[3].decision = \
            option_denied
        contract.underwritings[0].underwriting_options[4].decision = \
            option_denied
        contract.underwritings[0].underwriting_options = list(
            contract.underwritings[0].underwriting_options)
        contract.underwritings[0].decision_date = utils.today()
        contract.underwritings[0].decision = contract_accepted
        contract.underwritings = list(contract.underwritings)

        # option_denied is not allowed for underwriting option 3
        self.assertRaises(UserError, contract.save)

        contract.underwritings[0].underwriting_options[3].decision = \
            option_accepted

        contract.save()
        Contract.activate_contract([contract])
        self.assertEqual(contract.status, 'active')

    @test_framework.prepare_test(
        'contract_underwriting.test0060_test_subscription_api',
        )
    def test0062_test_api_underwriting_acceptation(self):
        pool = Pool()
        Contract = pool.get('contract')
        ContractAPI = pool.get('api.contract')
        Party = pool.get('party.party')

        mother, = Party.search([('name', '=', 'Doe'),
                ('first_name', '=', 'Mother')])
        baby, = Party.search([('name', '=', 'Antoine'),
                ('first_name', '=', 'Jeff')])

        # test0060_test_subscription_api creates two contracts, since the first
        # calls fails in the activation process.
        contract = Contract.search([])[-1]

        # We still cannot activate the contract
        self.assertRaises(UserError,
            Contract.activate_contract, [contract])

        data_ref = {
            'contract': {
                'number': contract.quote_number,
                },
            'decision': {
                'code': 'accepted_contract',
                },
            'decision_date': date_for_api(utils.today()),
            'options': [
                {
                    'coverage': {
                        'code': 'ALP',
                        },
                    'party': {
                        'code': mother.code,
                        },
                    'decision': {
                        'code': 'accepted_option',
                        },
                    },
                ],
            }

        # There are options for which there is no decision taken
        data_dict = copy.deepcopy(data_ref)
        self.assertEqual(ContractAPI.update_underwriting(data_dict, {}).data[0],
            {
                'type': 'incomplete_underwriting',
                'data': {
                    'missing_options': ['Alpha Coverage', 'Beta Coverage',
                        'Beta Coverage'],
                    },
                }
            )

        data_ref['options'] += [
            {
                'coverage': {
                    'code': 'BET',
                    },
                'party': {
                    'code': mother.code,
                    },
                'decision': {
                    'code': 'accepted_option',
                    },
                },
            {
                'coverage': {
                    'code': 'ALP',
                    },
                'party': {
                    'code': baby.code,
                    },
                'decision': {
                    'code': 'accepted_option',
                    },
                },
            {
                'coverage': {
                    'code': 'BET',
                    },
                'party': {
                    'code': baby.code,
                    },
                'decision': {
                    'code': 'denied_option',
                    },
                },
            ]

        # The contract decision does not match the option decisions
        data_dict = copy.deepcopy(data_ref)
        data_dict['decision']['code'] = 'accept_with_conditions_contract'
        self.assertEqual(ContractAPI.update_underwriting(data_dict, {}).data[0],
            {
                'type': 'unauthorized_contract_underwriting_decision',
                'data': {
                    'contract': contract.rec_name,
                    'decision': 'accept_with_conditions_contract',
                    'allowed_decisions': ['accepted_contract'],
                    },
                }
            )

        # One option decision is not authorized
        data_dict = copy.deepcopy(data_ref)
        data_dict['options'][0]['decision']['code'] = 'accepted_option_bad'
        self.assertEqual(ContractAPI.update_underwriting(data_dict, {}).data[0],
            {
                'type': 'unauthorized_underwriting_decision',
                'data': {
                    'contract': contract.rec_name,
                    'option': 'Alpha Coverage',
                    'decision': 'accepted_option_bad',
                    'allowed_decisions': ['accept_with_conditions_option',
                        'accepted_option'],
                    },
                }
            )

        # Unknown option
        data_dict = copy.deepcopy(data_ref)
        data_dict['options'].append({
                'coverage': {
                    'code': 'GAM',
                    },
                'party': {
                    'code': baby.code,
                    },
                'decision': {
                    'code': 'accepted_option',
                    },
                })
        self.assertEqual(ContractAPI.update_underwriting(data_dict, {}).data[0],
            {
                'type': 'unknown_option_on_contract',
                'data': {
                    'option': 'GammaCoverage',
                    'parent': contract.covered_elements[1].rec_name,
                    },
                }
            )

        data_ref['decision']['code'] = 'accept_with_conditions_contract'
        data_ref['options'][0]['decision']['code'] = \
            'accept_with_conditions_option'
        data_ref['options'][0]['exclusions'] = [
            {
                'type': {'code': 'exclusion_1'},
                },
            {
                'type': {'code': 'exclusion_2'},
                'custom_content': 'Very Heavy Smoker',
                },
            ]
        data_ref['options'][0]['extra_premiums'] = [
            {
                'type': {'code': 'extra_premium_1'},
                'mode': 'rate',
                'rate': '0.50',
                'end': date_for_api(utils.today() + relativedelta(months=3)),
                },
            {
                'type': {'code': 'extra_premium_2'},
                'mode': 'flat',
                'flat_amount': '120.20',
                },
            ]

        # Already set underwriting decision
        data_dict = copy.deepcopy(data_ref)
        data_dict['options'].append({
                'coverage': {
                    'code': 'GAM',
                    },
                'party': {
                    'code': mother.code,
                    },
                'decision': {
                    'code': 'accept_with_conditions_option',
                    },
                })
        self.assertEqual(ContractAPI.update_underwriting(data_dict, {}).data[0],
            {
                'type': 'underwriting_decision_already_set',
                'data': {
                    'option': 'GammaCoverage',
                    'existing_decision': 'accepted_option',
                    'new_decision': 'accept_with_conditions_option',
                    },
                }
            )

        # Exclusion on un-authorized coverage
        data_dict = copy.deepcopy(data_ref)
        data_dict['options'][1]['exclusions'] = [
            {
                'type': {'code': 'exclusion_1'},
                },
            ]
        self.assertEqual(ContractAPI.update_underwriting(data_dict, {}).data[0],
            {
                'type': 'coverage_without_exclusions',
                'data': {
                    'coverage': 'BET',
                    },
                }
            )

        # Extra-premium on un-authorized coverage
        data_dict = copy.deepcopy(data_ref)
        data_dict['options'][1]['extra_premiums'] = [
            {
                'type': {'code': 'extra_premium_1'},
                'mode': 'rate',
                'rate': '0.50',
                },
            ]
        self.assertEqual(ContractAPI.update_underwriting(data_dict, {}).data[0],
            {
                'type': 'coverage_without_extra_premiums',
                'data': {
                    'coverage': 'BET',
                    },
                }
            )

        # There were no modifications yet, since all tries were errors
        self.assertEqual(
            {(x.option.covered_element.party.code, x.option.coverage.code,
                    x.decision.code if x.decision else None)
                for x in contract.underwritings[0].underwriting_options},
            {
                (mother.code, 'ALP', None),
                (mother.code, 'BET', None),
                (mother.code, 'GAM', 'accepted_option'),
                (baby.code, 'ALP', None),
                (baby.code, 'BET', None),
                }
            )

        # Let's do it
        data_dict = copy.deepcopy(data_ref)
        self.assertEqual(
            ContractAPI.update_underwriting(data_dict, {'_debug_server': True}),
            None)
        self.assertEqual(
            {(x.option.covered_element.party.code, x.option.coverage.code,
                    x.decision.code if x.decision else None)
                for x in contract.underwritings[0].underwriting_options},
            {
                (mother.code, 'ALP', 'accept_with_conditions_option'),
                (mother.code, 'BET', 'accepted_option'),
                (mother.code, 'GAM', 'accepted_option'),
                (baby.code, 'ALP', 'accepted_option'),
                (baby.code, 'BET', 'denied_option'),
                }
            )
        self.assertEqual(len(contract.underwritings), 1)
        self.assertEqual(contract.underwritings[0].decision.code,
            'accept_with_conditions_contract')
        self.assertEqual(contract.underwritings[0].decision_date, utils.today())

        # Option was declined, so it does not appear in the options field
        # anymore, but we can find it in "all_options'
        self.assertEqual(len(contract.covered_elements[1].options), 1)
        self.assertEqual(contract.covered_elements[1].all_options[1].status,
            'declined')

        option_with_conditions = contract.covered_elements[0].options[0]
        self.assertEqual(len(option_with_conditions.exclusions), 2)
        self.assertEqual(option_with_conditions.exclusions[0].exclusion.code,
            'exclusion_1')
        self.assertEqual(option_with_conditions.exclusions[0].comment,
            '')
        self.assertEqual(option_with_conditions.exclusions[1].exclusion.code,
            'exclusion_2')
        self.assertEqual(option_with_conditions.exclusions[1].comment,
            'Very Heavy Smoker')

        self.assertEqual(len(option_with_conditions.extra_premiums), 2)
        self.assertEqual(option_with_conditions.extra_premiums[0].motive.code,
            'extra_premium_1')
        self.assertEqual(
            option_with_conditions.extra_premiums[0].calculation_kind,
            'rate')
        self.assertEqual(
            option_with_conditions.extra_premiums[0].rate,
            Decimal('0.5'))
        self.assertEqual(
            option_with_conditions.extra_premiums[0].flat_amount,
            None)
        self.assertEqual(
            option_with_conditions.extra_premiums[0].end_date,
            utils.today() + relativedelta(months=3))
        self.assertEqual(option_with_conditions.extra_premiums[1].motive.code,
            'extra_premium_2')
        self.assertEqual(
            option_with_conditions.extra_premiums[1].calculation_kind,
            'flat')
        self.assertEqual(
            option_with_conditions.extra_premiums[1].rate,
            None)
        self.assertEqual(
            option_with_conditions.extra_premiums[1].flat_amount,
            Decimal('120.2'))
        self.assertEqual(
            option_with_conditions.extra_premiums[1].end_date,
            None)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
