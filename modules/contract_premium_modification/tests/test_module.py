# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import copy
import doctest
from decimal import Decimal

from trytond.transaction import Transaction
from trytond.pool import Pool

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown
from trytond.modules.contract_premium_modification.exceptions import \
    WaiverDiscountValidationError


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'contract_premium_modification'

    @classmethod
    def fetch_models_for(cls):
        return ['bank_cog', 'contract', 'contract_insurance_invoice']

    @test_framework.prepare_test(
        'bank_cog.test0010bank',
        'contract_insurance_invoice.test0006_prepare_product_for_subscription',
        'contract.test0002_testCountryCreation',
        )
    def test0020_create_commercial_discounts(self):
        pool = Pool()
        Account = pool.get('account.account')
        CommercialDiscount = pool.get('commercial_discount')
        Coverage = pool.get('offered.option.description')
        RuleEngine = pool.get('rule_engine')
        RuleEngineContext = pool.get('rule_engine.context')

        account = Account.search([('code', '=', 'account_product')])[0]
        coverage_alpha = Coverage.search([('code', '=', 'ALP')])[0]
        coverage_alpha.subscription_behaviour = 'optional'
        coverage_alpha.save()
        coverage_beta = Coverage.search(['code', '=', 'BET'])[0]

        discount_alpha = CommercialDiscount(name="Discount Alpha")
        discount_alpha.code = 'ALP'
        discount_alpha.rules = [{}]
        discount_alpha.rules[-1].rate = Decimal('0.5')
        discount_alpha.rules[-1].account_for_modification = account.id
        discount_alpha.rules[-1].invoice_line_period_behaviour = \
            'one_day_overlap'
        discount_alpha.rules[-1].coverages = [Coverage(coverage_alpha.id)]
        discount_alpha.save()

        discount_beta = CommercialDiscount(name="Discount Beta")
        discount_beta.code = 'BET'
        discount_beta.rules = [{}]
        discount_beta.rules[-1].rate = Decimal('0.1')
        discount_beta.rules[-1].account_for_modification = account.id
        discount_beta.rules[-1].invoice_line_period_behaviour = \
            'one_day_overlap'
        discount_beta.rules[-1].coverages = [Coverage(coverage_beta.id)]
        discount_beta.save()

        discount_zeta = CommercialDiscount(name="Discount Zeta")
        discount_zeta.code = 'ZET'
        discount_zeta.rules = [{}]
        discount_zeta.rules[-1].rate = Decimal('0.5')
        discount_zeta.rules[-1].account_for_modification = account.id
        discount_zeta.rules[-1].invoice_line_period_behaviour = \
            'one_day_overlap'
        discount_zeta.save()

        rule_context = RuleEngineContext(1)

        duration_rule = RuleEngine(name="Discount Duration")
        duration_rule.algorithm = ('start_date=date_effet_initiale_contrat()\n'
            'end_date=ajouter_annees(date_effet_initiale_contrat(),1,False)\n'
            'end_date=ajouter_jours(end_date, -1)\n'
            'return(start_date,end_date)')
        duration_rule.context = rule_context
        duration_rule.rec_name = 'Discount_Duration'
        duration_rule.result_type = 'list'
        duration_rule.short_name = 'Discount_Duration'
        duration_rule.status = 'validated'
        duration_rule.type_ = 'discount_duration'
        duration_rule.save()

        discount_delta = CommercialDiscount(name="Discount Delta")
        discount_delta.code = 'DEL'
        discount_delta.rules = [{}]
        discount_delta.rules[-1].rate = Decimal('0.2')
        discount_delta.rules[-1].account_for_modification = account.id
        discount_delta.rules[-1].invoice_line_period_behaviour = \
            'one_day_overlap'
        discount_delta.rules[-1].coverages = [Coverage(coverage_alpha.id)]
        discount_delta.rules[-1].automatic = True
        discount_delta.rules[-1].duration_rule = duration_rule
        discount_delta.save()

    @test_framework.prepare_test(
        'contract_premium_modification.test0020_create_commercial_discounts',
        )
    def test0030_test_subscribe_contract_API(self):
        pool = Pool()
        Contract = pool.get('contract')
        ContractAPI = pool.get('api.contract')
        Coverage = pool.get('offered.option.description')
        coverages = Coverage.search([('code', 'in',
                ('BET', 'ALP'))])
        for coverage in coverages:
            coverage.allow_subscribe_coverage_multiple_times = True
            coverage.save()
        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Mother',
                    'birth_date': '1978-01-14',
                    'gender': 'female',
                    'bank_accounts': [{
                            'number': 'FR7619530001040006462803348',
                            'bank': {'bic': 'ABCDEFGHXXX'},
                            },
                        ],
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    },
                {
                    'ref': '2',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Father',
                    'birth_date': '1978-06-12',
                    'gender': 'male',
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {},
                    'billing': {
                        'payer': {'ref': '1'},
                        'billing_mode': {'code': 'quarterly'},
                        'direct_debit_day': 4,
                        },
                    'discounts': [
                        {'code': 'BET'}
                        ],
                    'covereds': [
                        {
                            'party': {'ref': '1'},
                            'item_descriptor': {'code': 'person'},
                            'coverages': [
                                {
                                    'coverage': {'code': 'BET'},
                                    'extra_data': {},
                                    },
                                ],
                            },
                        {
                            'party': {'ref': '2'},
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
                    },
                ],
            'options': {
                'activate': True,
                },
            }

        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(
            data_dict, {'_debug_server': True})
        contract = Contract(result['contracts'][0]['id'])
        self.assertEqual(contract.with_discount_of_premium, True)
        self.assertEqual(len(contract.discounts), 2)
        self.assertEqual(len(contract.discounts[0].options), 2)

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['discounts'].append({'code': 'ALP'})
        result = ContractAPI.subscribe_contracts(
            data_dict, {'_debug_server': True})
        contract = Contract(result['contracts'][0]['id'])
        self.assertEqual(contract.with_discount_of_premium, True)
        self.assertEqual(len(contract.discounts), 3)
        self.assertEqual(len(contract.discounts[0].options), 2)
        self.assertEqual(len(contract.discounts[1].options), 1)

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['discounts'][0]['code'] = 'ZET'
        self.assertEqual(ContractAPI.subscribe_contracts(data_dict, {}).data, [{
            'type': 'invalid_discount_for_coverages',
            'data': {
                'discount': 'ZET',
                },
            }])

    @test_framework.prepare_test(
        'contract_insurance_invoice.test0006_prepare_product_for_subscription',
        )
    def test0040_test_validate_commercial_discounts(self):
        pool = Pool()
        Account = pool.get('account.account')
        CommercialDiscount = pool.get('commercial_discount')
        Coverage = pool.get('offered.option.description')
        RuleEngine = pool.get('rule_engine')
        RuleEngineContext = pool.get('rule_engine.context')

        account = Account.search([('code', '=', 'account_product')])[0]
        coverage_alpha = Coverage.search([('code', '=', 'ALP')])[0]
        coverage_alpha.subscription_behavior = 'optional'
        coverage_alpha.save()

        rule_context = RuleEngineContext(1)

        duration_rule = RuleEngine(name="Discount Duration")
        duration_rule.algorithm = ('start_date=date_effet_initiale_contrat()\n'
            'end_date=ajouter_annees(date_effet_initiale_contrat(),1,False)\n'
            'end_date=ajouter_jours(end_date, -1)\n'
            'return(start_date,end_date)')
        duration_rule.context = rule_context
        duration_rule.rec_name = 'Discount_Duration'
        duration_rule.result_type = 'list'
        duration_rule.short_name = 'Discount_Duration'
        duration_rule.status = 'validated'
        duration_rule.type_ = 'discount_duration'
        duration_rule.save()

        discount_delta = CommercialDiscount(name="Discount Delta")
        discount_delta.code = 'DEL'
        discount_delta.rules = [{}, {}]
        discount_delta.rules[-1].rate = Decimal('0.2')
        discount_delta.rules[-1].account_for_modification = account.id
        discount_delta.rules[-1].invoice_line_period_behaviour = \
            'one_day_overlap'
        discount_delta.rules[-1].coverages = [Coverage(coverage_alpha.id)]
        discount_delta.rules[-1].automatic = True
        discount_delta.rules[-1].duration_rule = duration_rule
        discount_delta.rules[-2].rate = Decimal('0.1')
        discount_delta.rules[-2].account_for_modification = account.id
        discount_delta.rules[-2].invoice_line_period_behaviour = \
            'one_day_overlap'
        discount_delta.rules[-2].coverages = [Coverage(coverage_alpha.id)]
        discount_delta.rules[-2].automatic = False

        self.assertRaises(WaiverDiscountValidationError, discount_delta.save)

    @test_framework.prepare_test(
        'contract_premium_modification.test0020_create_commercial_discounts',
        )
    def test9910_test_simulate_API(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')
        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'birth_date': '1978-01-14',
                    },
                {
                    'ref': '2',
                    'is_person': True,
                    'birth_date': '1978-06-12',
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {},
                    'start': '2020-01-01',
                    'discounts': [
                        {'code': 'BET'}
                        ],
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
                                ],
                            },
                        {
                            'party': {'ref': '2'},
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
                    },
                ],
            }

        # We have to commit here because simulate is executed in a new
        # transaction, which cannot have access to the contents of the testing
        # transaction
        Transaction().commit()

        data_dict = copy.deepcopy(data_ref)
        schedule = ContractAPI.simulate(
            data_dict, {'_debug_server': True})

        self.maxDiff = None

        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0]['ref'], '1')

        # Monthly billing (default value for the product), default schedule is
        # 1 year
        self.assertEqual(len(schedule[0]['schedule']), 12)

        # Coverage A is 10 per month, 12 months + 2 covereds = 240
        # Coverage B is 100 per month, 12 months + 2 covereds = 2400
        self.assertEqual(schedule[0]['premium']['total'], '2400.00')

        self.assertEqual([(x['start'], x['end'], x['total'])
                    for x in schedule[0]['schedule']],
                [
                    ('2020-01-01', '2020-01-31', '200.00'),
                    ('2020-02-01', '2020-02-29', '200.00'),
                    ('2020-03-01', '2020-03-31', '200.00'),
                    ('2020-04-01', '2020-04-30', '200.00'),
                    ('2020-05-01', '2020-05-31', '200.00'),
                    ('2020-06-01', '2020-06-30', '200.00'),
                    ('2020-07-01', '2020-07-31', '200.00'),
                    ('2020-08-01', '2020-08-31', '200.00'),
                    ('2020-09-01', '2020-09-30', '200.00'),
                    ('2020-10-01', '2020-10-31', '200.00'),
                    ('2020-11-01', '2020-11-30', '200.00'),
                    ('2020-12-01', '2020-12-31', '200.00'),
                    ])

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['billing'] = {
            'billing_mode': {'code': 'quarterly'},
            }
        output = ContractAPI.simulate(
            data_dict, {'_debug_server': True})

        self.maxDiff = None

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]['ref'], '1')

        # Quarterly billing
        self.assertEqual(len(output[0]['schedule']), 4)
        self.assertEqual(output[0]['premium']['total'], '2400.00')
        self.assertEqual([(x['start'], x['end'], x['total'])
                    for x in output[0]['schedule']],
                [
                    # (ALP 30 * 2 covered) +  (BET 300 * 2 covered)
                    #  +  (BET discount -30 * 2 covered)
                    ('2020-01-01', '2020-03-31', '600.00'),
                    ('2020-04-01', '2020-06-30', '600.00'),
                    ('2020-07-01', '2020-09-30', '600.00'),
                    ('2020-10-01', '2020-12-31', '600.00'),
                    ])

        def check_amounts(p):
            sum_ = sum(Decimal(p[key]) for key in ('total_fee',
                    'total_premium', 'total_tax'))
            discounts = p.get('discounts', [])
            discount_sum = sum([Decimal(x["amount"]) for x in discounts])
            all_summed = sum_ + discount_sum
            self.assertEqual(Decimal(p['total']), all_summed)

        for c in output:
            check_amounts(c['premium'])
            covered_summary = c['covereds']
            self.assertTrue(bool(len(covered_summary)))
            for covered in covered_summary:
                check_amounts(covered['premium'])
                self.assertTrue(bool(len(covered['coverages'])))
                for coverage in covered['coverages']:
                    check_amounts(coverage['premium'])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_waiver_of_premium.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_waiver_of_premium_proportion.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_waiver_discount.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_automatic_discount_of_premium.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
