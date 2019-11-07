# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import copy
import doctest
from decimal import Decimal

from trytond.pool import Pool

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown


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
        self.assertEqual(len(contract.discounts), 1)
        self.assertEqual(len(contract.discounts[0].options), 2)

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['discounts'].append({'code': 'ALP'})
        result = ContractAPI.subscribe_contracts(
            data_dict, {'_debug_server': True})
        contract = Contract(result['contracts'][0]['id'])
        self.assertEqual(contract.with_discount_of_premium, True)
        self.assertEqual(len(contract.discounts), 2)
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
    return suite
