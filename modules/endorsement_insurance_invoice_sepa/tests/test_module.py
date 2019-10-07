# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.api import date_for_api
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'endorsement_insurance_invoice_sepa'

    @classmethod
    def fetch_models_for(cls):
        return ['company_cog', 'currency_cog', 'offered', 'offered_insurance',
            'bank_cog', 'rule_engine', 'contract_insurance_invoice']

    def test0010_prepare_product_for_subscription(self):
        pool = Pool()
        Product = pool.get('offered.product')
        Sequence = pool.get('ir.sequence')
        mandate_sequence = Sequence()
        mandate_sequence.name = 'Mandate Identification Sequence'
        mandate_sequence.code = 'account.payment.sepa.mandate'
        mandate_sequence.save()

        for product in Product.search([]):
            product.sepa_mandate_sequence = mandate_sequence
            product.save()

    @test_framework.prepare_test(
        'bank_cog.test0010bank',
        'contract.test0002_testCountryCreation',
        'contract_insurance_invoice.test0006_prepare_product_for_subscription',
        'endorsement_insurance_invoice_sepa.'
        'test0010_prepare_product_for_subscription',
        )
    def test0060_test_change_bank_account_API(self):
        pool = Pool()
        Contract = pool.get('contract')
        Party = pool.get('party.party')
        ContractAPI = pool.get('api.contract')
        EndorsementAPI = pool.get('api.endorsement')
        Endorsement = pool.get('endorsement')

        data_dict = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Mother',
                    'birth_date': '1978-01-14',
                    'gender': 'female',
                    'bank_accounts': [{
                            'number': 'FR7615970003860000690570007',
                            'bank': {'bic': 'ABCDEFGHXXX'},
                            }, {
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
                    'is_person': False,
                    'name': 'Other Party',
                    'bank_accounts': [{
                            'number': 'FR47104230099100031044T8477',
                            'bank': {'bic': 'ABCDEFGHXXX'},
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
                    'billing': {
                        'payer': {'ref': '1'},
                        'billing_mode': {'code': 'quarterly'},
                        'direct_debit_day': 4,
                        },
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
                        ],
                    },
                ],
            'options': {
                'activate': True,
                },
            }

        result = ContractAPI.subscribe_contracts(
            data_dict, {'_debug_server': True})

        contract = Contract(result['contracts'][0]['id'])
        party = Party(result['parties'][0]['id'])
        other_party = Party(result['parties'][1]['id'])
        billing_info, = contract.billing_informations
        mandate = billing_info.sepa_mandate
        self.assertIsNotNone(mandate)

        self.assertEqual(EndorsementAPI.change_bank_account(
                {
                    'party': {'code': other_party.code},
                    'new_accounts': [
                        {
                            'number': 'FR7610423009910003104438477',
                            'bank': {'bic': 'ABCDEFGHXXX'},
                            },
                        ],
                    'direct_debit_changes': [
                        {
                            'previous_account': {
                                'number': 'FR47104230099100031044T8477',
                                },
                            'new_account': {
                                'number': 'FR7610423009910003104438477',
                                },
                            'mandates': [
                                {
                                    'number': 'RUMXXXXXXXXXXX',
                                    },
                                ]
                            },
                        ],
                    }, {}).data[0],
            {
                'type': 'mandate_not_found',
                'data': {
                    'party': other_party.code,
                    'account_number': 'FR47104230099100031044T8477',
                    'mandate_identification': 'RUMXXXXXXXXXXX',
                    },
                })

        # Change again, in the future
        one_month_later = datetime.date.today() + relativedelta(months=1)
        result = EndorsementAPI.change_bank_account(
            {
                'party': {'code': party.code},
                'date': date_for_api(one_month_later),
                'new_accounts': [
                    {
                        'number': 'FR8412739000407261797876X36',
                        'bank': {'bic': 'ABCDEFGHXXX'},
                        },
                    ],
                'direct_debit_changes': [
                    {
                        'previous_account': {
                            'number': 'FR7619530001040006462803348',
                            },
                        'new_account': {
                            'number': 'FR8412739000407261797876X36',
                            },
                        'mandates': [
                            {
                                'number': mandate.identification,
                                },
                            ],
                        },
                    ],
                }, {'_debug_server': True})

        endorsement = Endorsement(result['endorsements'][0]['id'])
        self.assertEqual(endorsement.definition.code,
            'change_direct_debit_account')
        self.assertEqual(endorsement.state, 'applied')
        self.assertEqual(len(endorsement.contract_endorsements), 1)
        self.assertEqual(endorsement.contract_endorsements[0].contract,
            contract)

        self.assertEqual(len(contract.billing_informations), 2)
        prev_billing_info = contract.billing_informations[0]
        self.assertEqual(prev_billing_info.date, None)
        self.assertEqual(prev_billing_info.payer, party)
        self.assertEqual(
            prev_billing_info.direct_debit_account.numbers[0].number_compact,
            'FR7619530001040006462803348')
        self.assertEqual(prev_billing_info.sepa_mandate, mandate)
        self.assertEqual(mandate.start_date, None)
        self.assertEqual(mandate.amendment_of, None)

        new_billing_info = contract.billing_informations[1]
        self.assertEqual(new_billing_info.date, one_month_later)
        self.assertEqual(new_billing_info.payer, party)
        self.assertEqual(
            new_billing_info.direct_debit_account.numbers[0].number_compact,
            'FR8412739000407261797876X36')
        self.assertEqual(new_billing_info.sepa_mandate.amendment_of,
            mandate)
        self.assertEqual(new_billing_info.sepa_mandate.start_date,
            one_month_later)

        # Change again, at the same date => it should not be ok, because the
        # mandate on the original account is already amended
        self.assertEqual(EndorsementAPI.change_bank_account(
                {
                    'party': {'code': party.code},
                    'date': date_for_api(one_month_later),
                    'new_accounts': [
                        {
                            'number': 'FR8517569000706596319854R94',
                            'bank': {'bic': 'ABCDEFGHXXX'},
                            },
                        ],
                    'direct_debit_changes': [
                        {
                            'previous_account': {
                                'number': 'FR7619530001040006462803348',
                                },
                            'new_account': {
                                'number': 'FR8517569000706596319854R94',
                                },
                            'mandates': [
                                {
                                    'number': mandate.identification,
                                    },
                                ],
                            },
                        ],
                    }, {}).data[0],
                {
                    'type': 'already_amended_mandate',
                    'data': {
                        'party': '4',
                        'mandate': '1',
                        },
                    })


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
