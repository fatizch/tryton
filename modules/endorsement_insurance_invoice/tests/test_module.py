# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import datetime
import unittest
import mock

from dateutil.relativedelta import relativedelta

from trytond.transaction import Transaction
from trytond.pool import Pool

import trytond.tests.test_tryton

from trytond.modules.api import date_for_api
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'endorsement_insurance_invoice'

    @classmethod
    def fetch_models_for(cls):
        return ['company_cog', 'currency_cog', 'offered', 'offered_insurance',
            'bank_cog', 'rule_engine']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Contract': 'contract',
            'Premium': 'contract.premium',
            'Sequence': 'ir.sequence',
            'SequenceType': 'ir.sequence.type',
            'Account': 'account.account',
            'AccountKind': 'account.account.type',
            'Tax': 'account.tax',
            'BillingMode': 'offered.billing_mode',
            'Product': 'offered.product',
            'Coverage': 'offered.option.description',
            'PaymentTerm': 'account.invoice.payment_term',
            'BillingInformation': 'contract.billing_information',
            'Company': 'company.company',
            'MoveLine': 'account.move.line',
            'User': 'res.user',
            'Configuration': 'account.configuration',
            'OfferedConfiguration': 'offered.configuration',
            'ConfigurationTaxRounding': 'account.configuration.tax_rounding',
            'PaymentJournal': 'account.payment.journal',
            'Reconciliation': 'account.move.reconciliation',
            'ContractInvoice': 'contract.invoice',
            'Invoice': 'account.invoice',
            'InvoiceLine': 'account.invoice.line',
            'InvoiceLineDetail': 'account.invoice.line.detail',
            }

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test_contract_get_invoice_periods(self):
        'Test Contract get_invoice_periods'

        company, = self.Company.search([
                ('rec_name', '=', 'World Company'),
                ])
        currency, = self.Currency.search([], limit=1)
        self.User.write([self.User(Transaction().user)], {
                'main_company': company.id,
                'company': company.id,
                })
        payment_term, = self.PaymentTerm.create([{
                    'name': 'direct',
                    'lines': [('create', [{}])],
                    }])
        freq_year, freq_quart, freq_once = self.BillingMode.create([{
                'code': 'yearly',
                'name': 'yearly',
                'frequency': 'yearly',
                'sync_day': '1',
                'sync_month': '1',
                'allowed_payment_terms': [
                        ('add', [payment_term.id])]
                }, {
                'code': 'quarterly',
                'name': 'quarterly',
                'frequency': 'quarterly',
                'sync_day': '1',
                'sync_month': '1',
                'allowed_payment_terms': [
                        ('add', [payment_term.id])],
                'direct_debit': True,
                'allowed_direct_debit_days': '5, 10, 15'
                }, {
                'code': 'once_per_contract',
                'name': 'once_per_contract',
                'frequency': 'once_per_contract',
                'allowed_payment_terms': [
                        ('add', [payment_term.id])]
                }])
        sequence_code, = self.SequenceType.create([{
                    'name': 'Product sequence',
                    'code': 'contract',
                    }])
        sequence, quote_sequence = self.Sequence.create([{
                    'name': 'Contract sequence',
                    'code': sequence_code.code,
                    'company': company.id,
                    }, {
                    'name': 'Quote Sequence',
                    'code': 'quote',
                    'company': company.id,
                    }])
        account_kind, = self.AccountKind.create([{
                    'name': 'Product',
                    'company': company.id,
                    'statement': 'income',
                    'revenue': True,
                    }])
        account, = self.Account.create([{
                    'name': 'Account for Product',
                    'code': 'Account for Product',
                    'company': company.id,
                    'type': account_kind.id,
                    }])
        with Transaction().set_context(company=company.id):
            product, = self.Product.create([{'company': company.id,
                        'name': 'Test Product',
                        'code': 'test_product',
                        'start_date': datetime.date(2014, 1, 1),
                        'contract_generator': sequence.id,
                        'quote_number_sequence': quote_sequence.id,
                        'currency': currency.id,
                        'billing_rules': [
                            ('create', [{
                                        'billing_modes': [
                                            ('add', [freq_year.id,
                                                    freq_quart.id,
                                                    freq_once.id])],
                                        }])],
                        }])

            config = self.OfferedConfiguration(1)
            config.split_invoices_on_endorsement_dates = True
            config.save()
            contract = self.Contract(company=company,
                start_date=datetime.date(2017, 8, 1),
                product=product,
                billing_informations=[
                    self.BillingInformation(date=None,
                        billing_mode=freq_year,
                        payment_term=payment_term),
                    self.BillingInformation(date=datetime.date(2018, 1, 1),
                        billing_mode=freq_quart,
                        direct_debit_day=5,
                        payment_term=payment_term),
                    ],
                )
            contract.save()
            self.maxDiff = None
            contract.rebill_endorsement_dates = mock.Mock(return_value=[
                    datetime.datetime.combine(datetime.date(2017, 12, 15),
                        datetime.time()),
                    datetime.datetime.combine(datetime.date(2018, 2, 28),
                        datetime.time())])
            self.assertEqual(contract.get_invoice_periods(
                    datetime.date(2018, 4, 1), contract.start_date),
                [
                    (datetime.date(2017, 8, 1), datetime.date(2017, 12, 14),
                        contract.billing_informations[0]),
                    (datetime.date(2017, 12, 15), datetime.date(2017, 12, 31),
                        contract.billing_informations[0]),
                    (datetime.date(2018, 1, 1), datetime.date(2018, 2, 27),
                        contract.billing_informations[1]),
                    (datetime.date(2018, 2, 28), datetime.date(2018, 3, 31),
                        contract.billing_informations[1]),
                    (datetime.date(2018, 4, 1), datetime.date(2018, 6, 30),
                        contract.billing_informations[1]),
                    ])

    @test_framework.prepare_test(
        'bank_cog.test0010bank',
        'contract_insurance_invoice.test0006_prepare_product_for_subscription',
        'contract.test0002_testCountryCreation',
        )
    def test0060_test_change_bank_account_API(self):
        pool = Pool()
        Contract = pool.get('contract')
        Party = pool.get('party.party')
        ContractAPI = pool.get('api.contract')
        EndorsementAPI = pool.get('api.endorsement')
        Endorsement = pool.get('endorsement')

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
                            'number': 'FR7615970 0038600 00 69  0570007',
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

        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(
            data_dict, {'_debug_server': True})

        today = datetime.date.today()
        contract = Contract(result['contracts'][0]['id'])
        party = Party(result['parties'][0]['id'])
        other_party = Party(result['parties'][1]['id'])

        self.assertEqual(EndorsementAPI.change_bank_account(
                {
                    'party': {'code': party.code},
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
                            },
                        ],
                    }, {}).data[0],
            {
                'type': 'previous_bank_account_not_found',
                'data': {
                    'party': party.code,
                    },
                })

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
                                'number': 'XXXXXXXXXXXXXXXXXXXXXXXXXXX',
                                },
                            },
                        ],
                    }, {}).data[0],
            {
                'type': 'new_bank_account_not_found',
                'data': {
                    'party': other_party.code,
                    },
                })

        result = EndorsementAPI.change_bank_account(
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
                        },
                    ],
                }, {'_debug_server': True})

        self.assertEqual(len(other_party.bank_accounts), 2)
        self.assertEqual(
            other_party.bank_accounts[0].numbers[0].number_compact,
            'FR47104230099100031044T8477')
        self.assertEqual(other_party.bank_accounts[0].end_date,
            today - relativedelta(days=1))
        self.assertEqual(
            other_party.bank_accounts[1].numbers[0].number_compact,
            'FR7610423009910003104438477')
        self.assertEqual(other_party.bank_accounts[1].start_date, today)

        self.assertEqual(len(result['endorsements']), 1)
        endorsement = Endorsement(result['endorsements'][0]['id'])
        self.assertEqual(endorsement.definition.code,
            'change_direct_debit_account')
        self.assertEqual(endorsement.state, 'applied')

        result = EndorsementAPI.change_bank_account(
            {
                'party': {'code': party.code},
                'new_accounts': [
                    {
                        'number': 'FR3612739000702367973497Z31',
                        'bank': {'bic': 'ABCDEFGHXXX'},
                        },
                    ],
                'direct_debit_changes': [
                    {
                        'previous_account': {
                            'number': 'FR7619530001040006462803348',
                            },
                        'new_account': {
                            'number': 'FR3612739000702367973497Z31',
                            },
                        },
                    ],
                }, {'_debug_server': True})
        self.assertEqual(len(result['endorsements']), 1)
        endorsement = Endorsement(result['endorsements'][0]['id'])
        self.assertEqual(endorsement.definition.code,
            'change_direct_debit_account')
        self.assertEqual(endorsement.state, 'applied')

        self.assertEqual(len(party.bank_accounts), 3)
        self.assertEqual(
            party.bank_accounts[0].numbers[0].number_compact,
            'FR7615970003860000690570007')
        self.assertEqual(party.bank_accounts[0].end_date, None)
        self.assertEqual(
            party.bank_accounts[1].numbers[0].number_compact,
            'FR7619530001040006462803348')
        self.assertEqual(party.bank_accounts[1].end_date,
            today - relativedelta(days=1))
        self.assertEqual(
            party.bank_accounts[2].numbers[0].number_compact,
            'FR3612739000702367973497Z31')
        self.assertEqual(party.bank_accounts[2].start_date, today)

        # Still only one billing information, because the modification occurred
        # on the contract start date
        self.assertEqual(len(contract.billing_informations), 1)

        billing_info = contract.billing_information
        self.assertEqual(billing_info.date, None)
        self.assertEqual(billing_info.payer, party)
        self.assertEqual(
            billing_info.direct_debit_account.numbers[0].number_compact,
            'FR3612739000702367973497Z31')

        self.assertEqual(len(endorsement.contract_endorsements), 1)
        self.assertEqual(endorsement.contract_endorsements[0].contract,
            contract)

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
                            'number': 'FR3612739000702367973497Z31',
                            },
                        'new_account': {
                            'number': 'FR8412739000407261797876X36',
                            },
                        },
                    ],
                }, {'_debug_server': True})
        self.assertEqual(len(result['endorsements']), 1)
        endorsement = Endorsement(result['endorsements'][0]['id'])
        self.assertEqual(endorsement.definition.code,
            'change_direct_debit_account')
        self.assertEqual(endorsement.state, 'applied')

        self.assertEqual(len(party.bank_accounts), 4)
        self.assertEqual(
            party.bank_accounts[0].numbers[0].number_compact,
            'FR7615970003860000690570007')
        self.assertEqual(party.bank_accounts[0].end_date, None)
        self.assertEqual(
            party.bank_accounts[1].numbers[0].number_compact,
            'FR7619530001040006462803348')
        self.assertEqual(party.bank_accounts[1].end_date,
            today - relativedelta(days=1))
        self.assertEqual(
            party.bank_accounts[2].numbers[0].number_compact,
            'FR3612739000702367973497Z31')
        self.assertEqual(party.bank_accounts[2].start_date, today)
        self.assertEqual(party.bank_accounts[2].end_date,
            one_month_later - relativedelta(days=1))
        self.assertEqual(
            party.bank_accounts[3].numbers[0].number_compact,
            'FR8412739000407261797876X36')
        self.assertEqual(party.bank_accounts[3].start_date, one_month_later)
        self.assertEqual(party.bank_accounts[3].end_date, None)

        # Now there are two of them
        self.assertEqual(len(contract.billing_informations), 2)

        prev_billing_info = contract.billing_informations[0]
        self.assertEqual(prev_billing_info.date, None)
        self.assertEqual(prev_billing_info.payer, party)
        self.assertEqual(
            prev_billing_info.direct_debit_account.numbers[0].number_compact,
            'FR3612739000702367973497Z31')

        new_billing_info = contract.billing_informations[1]
        self.assertEqual(new_billing_info.date, one_month_later)
        self.assertEqual(new_billing_info.payer, party)
        self.assertEqual(
            new_billing_info.direct_debit_account.numbers[0].number_compact,
            'FR8412739000407261797876X36')

        self.assertEqual(len(endorsement.contract_endorsements), 1)
        self.assertEqual(endorsement.contract_endorsements[0].contract,
            contract)

        # Change again, later, on the original account of the contract
        two_months_later = datetime.date.today() + relativedelta(months=1)
        result = EndorsementAPI.change_bank_account(
            {
                'party': {'code': party.code},
                'date': date_for_api(two_months_later),
                'new_accounts': [
                    {
                        'number': 'FR2410096000509895795237P75',
                        'bank': {'bic': 'ABCDEFGHXXX'},
                        },
                    ],
                'direct_debit_changes': [
                    {
                        'previous_account': {
                            'number': 'FR3612739000702367973497Z31',
                            },
                        'new_account': {
                            'number': 'FR2410096000509895795237P75',
                            },
                        },
                    ],
                }, {'_debug_server': True})

        self.assertEqual(len(result['endorsements']), 1)
        endorsement = Endorsement(result['endorsements'][0]['id'])
        self.assertEqual(endorsement.definition.code,
            'change_direct_debit_account')
        self.assertEqual(endorsement.state, 'applied')

        # There were no billing informations on the contract for the previous
        # account at the given date
        self.assertEqual(len(endorsement.contract_endorsements), 0)

        # Only difference : There is a new account. The previous one was
        # already terminated
        self.assertEqual(len(party.bank_accounts), 5)
        self.assertEqual(
            party.bank_accounts[0].numbers[0].number_compact,
            'FR7615970003860000690570007')
        self.assertEqual(party.bank_accounts[0].end_date, None)
        self.assertEqual(
            party.bank_accounts[1].numbers[0].number_compact,
            'FR7619530001040006462803348')
        self.assertEqual(party.bank_accounts[1].end_date,
            today - relativedelta(days=1))
        self.assertEqual(
            party.bank_accounts[2].numbers[0].number_compact,
            'FR3612739000702367973497Z31')
        self.assertEqual(party.bank_accounts[2].start_date, today)
        self.assertEqual(party.bank_accounts[2].end_date,
            one_month_later - relativedelta(days=1))
        self.assertEqual(
            party.bank_accounts[3].numbers[0].number_compact,
            'FR8412739000407261797876X36')
        self.assertEqual(party.bank_accounts[3].start_date, one_month_later)
        self.assertEqual(party.bank_accounts[3].end_date, None)
        self.assertEqual(
            party.bank_accounts[4].numbers[0].number_compact,
            'FR2410096000509895795237P75')
        self.assertEqual(party.bank_accounts[4].start_date, two_months_later)
        self.assertEqual(party.bank_accounts[4].end_date, None)

        # Nothing should have changed
        self.assertEqual(len(contract.billing_informations), 2)

        prev_billing_info = contract.billing_informations[0]
        self.assertEqual(prev_billing_info.date, None)
        self.assertEqual(prev_billing_info.payer, party)
        self.assertEqual(
            prev_billing_info.direct_debit_account.numbers[0].number_compact,
            'FR3612739000702367973497Z31')

        new_billing_info = contract.billing_informations[1]
        self.assertEqual(new_billing_info.date, one_month_later)
        self.assertEqual(new_billing_info.payer, party)
        self.assertEqual(
            new_billing_info.direct_debit_account.numbers[0].number_compact,
            'FR8412739000407261797876X36')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
