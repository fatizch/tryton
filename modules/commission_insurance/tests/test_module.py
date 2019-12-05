# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest
import doctest
import datetime
import mock

from decimal import Decimal

import trytond.tests.test_tryton

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'commission_insurance'

    @classmethod
    def fetch_models_for(cls):
        return ['contract_distribution', 'contract_insurance_invoice',
            'bank_cog', 'country_cog']

    @classmethod
    def get_models(cls):
        return {
            'Commission': 'commission',
            'Plan': 'commission.plan',
            'PlanDate': 'commission.plan.date',
            'Agent': 'commission.agent',
            'Invoice': 'account.invoice',
            'InvoiceLine': 'account.invoice.line',
            'InvoiceLineDetail': 'account.invoice.line.detail',
            'Currency': 'currency.currency',
            }

    def test0001_get_commission_periods(self):
        plan = self.Plan()
        invoice_line = mock.Mock()
        plan.get_commission_dates = mock.MagicMock(return_value=[
                datetime.date(2000, 1, 1), datetime.date(2000, 1, 16),
                datetime.date(2000, 1, 31)])
        self.assertEqual(self.Plan.get_commission_periods(plan, invoice_line),
            [(datetime.date(2000, 1, 1), datetime.date(2000, 1, 15)),
                (datetime.date(2000, 1, 16), datetime.date(2000, 1, 31))])

    @test_framework.prepare_test(
        'contract_insurance_invoice.test0006_prepare_product_for_subscription',
        )
    def test0002_create_accounting(self):
        pool = Pool()
        Account = pool.get('account.account')
        AccountKind = pool.get('account.account.type')
        CommissionDescriptionConfiguration = pool.get(
            'commission.description.configuration')
        Product = pool.get('offered.product')
        ProductCategory = pool.get('product.category')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        product, = Product.search([('code', '=', 'AAA')])
        company = product.company

        # Create accounting configuration
        with Transaction().set_context(company=company.id):
            com_account_kind_expense, = AccountKind.create([{
                        'name': 'Commission',
                        'company': company.id,
                        'expense': True,
                        'statement': 'income',
                        }])
            com_account_kind_revenue, = AccountKind.create([{
                        'name': 'Commission',
                        'company': company.id,
                        'revenue': True,
                        'statement': 'income',
                        }])
            com_expense_account, com_revenue_account = Account.create([
                    {
                        'name': 'Expense for Commissions',
                        'code': 'account_expense_commission',
                        'company': company.id,
                        'type': com_account_kind_expense.id,
                        },
                    {
                        'name': 'Revenue for Commissions',
                        'code': 'account_revenue_commission',
                        'company': company.id,
                        'type': com_account_kind_revenue.id,
                        },
                    ])

            unit, = Uom.search([('name', '=', 'Unit')])
            account_category_commission = ProductCategory()
            account_category_commission.name = 'Account Category Commission'
            account_category_commission.company = company
            account_category_commission.accounting = True
            account_category_commission.account_expense = com_expense_account
            account_category_commission.account_revenue = com_revenue_account
            account_category_commission.code = 'account_category_commission'
            account_category_commission.save()

            templateComission = Template()
            templateComission.name = 'Commission'
            templateComission.default_uom = unit
            templateComission.type = 'service'
            templateComission.list_price = Decimal(0)
            templateComission.cost_price = Decimal(0)
            templateComission.account_category = ProductCategory(
                account_category_commission.id)
            templateComission.products = [{}]
            templateComission.products[0].code = 'commission_product'
            templateComission.save()

            descriptionConfiguration = CommissionDescriptionConfiguration()
            descriptionConfiguration.linear_commission_title = \
                'Linear commission calculation details'
            descriptionConfiguration.save()

    @test_framework.prepare_test(
        'distribution.test0002_dist_network_creation',
        'commission_insurance.test0002_create_accounting',
        )
    def test0003_create_broker(self):
        pool = Pool()
        DistNetwork = pool.get('distribution.network')
        Party = pool.get('party.party')

        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])
        broker = Party()
        broker.is_person = False
        broker.name = 'My Broker'
        broker.save()

        node_1.party = broker
        node_1.is_distributor = True
        node_1.is_broker = True
        node_1.save()

        node_1_1.is_distributor = True
        node_1_1.save()

    @test_framework.prepare_test(
        'commission_insurance.test0003_create_broker',
        )
    def test0004_create_commission_agents(self):
        pool = Pool()
        AccountProduct = pool.get('product.product')
        Agent = pool.get('commission.agent')
        Party = pool.get('party.party')
        Plan = pool.get('commission.plan')
        Product = pool.get('offered.product')

        product, = Product.search([('code', '=', 'AAA')])
        broker, = Party.search([('name', '=', 'My Broker')])
        commission_product, = AccountProduct.search([
                ('code', '=', 'commission_product')])

        bad_plan = Plan()
        bad_plan.name = 'Bad Plan'
        bad_plan.code = 'bad_plan'
        bad_plan.commission_product = commission_product
        bad_plan.commission_method = 'payment_and_accounted'
        bad_plan.type_ = 'agent'
        bad_plan.lines = [{
                'options': [x.id for x in product.coverages],
                'formula': 'amount * 0.1',
                }]
        bad_plan.save()

        wonder_plan = Plan()
        wonder_plan.name = 'Wonder Plan'
        wonder_plan.code = 'wonder_plan'
        wonder_plan.commission_product = commission_product
        wonder_plan.commission_method = 'payment_and_accounted'
        wonder_plan.type_ = 'agent'
        wonder_plan.lines = [{
                'options': [x.id for x in product.coverages],
                'formula': 'amount * 0.5',
                }]
        wonder_plan.save()

        bad_agent_broker = Agent()
        bad_agent_broker.company = product.company
        bad_agent_broker.party = broker
        bad_agent_broker.code = 'bad'
        bad_agent_broker.type_ = 'agent'
        bad_agent_broker.plan = bad_plan
        bad_agent_broker.currency = product.company.currency
        bad_agent_broker.save()

        wonder_agent_broker = Agent()
        wonder_agent_broker.company = product.company
        wonder_agent_broker.party = broker
        wonder_agent_broker.code = 'wonder'
        wonder_agent_broker.type_ = 'agent'
        wonder_agent_broker.plan = wonder_plan
        wonder_agent_broker.currency = product.company.currency
        wonder_agent_broker.save()

    @test_framework.prepare_test(
        'commission_insurance.test0004_create_commission_agents',
        )
    def test0005_set_commercial_products(self):
        pool = Pool()
        AccountProduct = pool.get('product.product')
        ComProduct = pool.get('distribution.commercial_product')
        DistNetwork = pool.get('distribution.network')
        Party = pool.get('party.party')
        Product = pool.get('offered.product')

        product, = Product.search([('code', '=', 'AAA')])
        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])
        broker, = Party.search([('name', '=', 'My Broker')])

        commission_product, = AccountProduct.search([
                ('code', '=', 'commission_product')])

        # We must copy from
        # contract_distribution.test0002_test_commercial_products
        # because it does not set accounts on option descriptions
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

    @test_framework.prepare_test(
        'commission_insurance.test0005_set_commercial_products',
        )
    def test0010_describe_products(self):
        pool = Pool()
        APIProduct = pool.get('api.product')
        DistNetwork = pool.get('distribution.network')
        Product = pool.get('offered.product')
        Agent = pool.get('commission.agent')

        product, = Product.search([('code', '=', 'AAA')])
        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])

        description, = APIProduct.describe_products(
            {}, {'_debug_server': True})
        self.assertTrue('commission_agents' not in description)

        self.maxDiff = None
        description, = APIProduct.describe_products(
            {}, {'_debug_server': True, 'dist_network': node_1.id})
        self.assertEqual(description['commission_agents'], [
                {
                    'id': Agent.search([('code', '=', 'bad')])[0].id,
                    'code': 'bad',
                    'plan': 'bad_plan',
                    },
                {
                    'id': Agent.search([('code', '=', 'wonder')])[0].id,
                    'code': 'wonder',
                    'plan': 'wonder_plan',
                    },
                ])

        description, = APIProduct.describe_products(
            {}, {'_debug_server': True, 'dist_network': node_1_1.id})
        self.assertEqual(description['commission_agents'], [
                {
                    'id': Agent.search([('code', '=', 'bad')])[0].id,
                    'code': 'bad',
                    'plan': 'bad_plan',
                    },
                {
                    'id': Agent.search([('code', '=', 'wonder')])[0].id,
                    'code': 'wonder',
                    'plan': 'wonder_plan',
                    },
                ])

    @test_framework.prepare_test(
        'commission_insurance.test0005_set_commercial_products',
        'bank_cog.test0010bank',
        'contract.test0002_testCountryCreation',
        )
    def test0015_subscribe_contract(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')
        DistNetwork = pool.get('distribution.network')

        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])
        coverages = self.Coverage.search([('code', 'in', ('BET', 'ALP'))])
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
                    'bank_accounts': [
                        {
                            'number': 'FR7615970003860000690570007',
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
                    'agent': {'code': 'bad'},
                    'commercial_product': {'code': 'com_product_1'},
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
        ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True, 'dist_network': node_1.id})

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['commercial_product'] = {
            'code': 'com_product_2'}
        self.assertEqual(
            ContractAPI.subscribe_contracts(data_dict,
                {'dist_network': node_1.id}).data,
            [{
                    'type': 'unauthorized_commercial_product',
                    'data': {
                        'product': 'AAA',
                        'commercial_product': 'com_product_2',
                        'dist_network': node_1.id,
                        },
                    }])

        data_dict = copy.deepcopy(data_ref)
        ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True, 'dist_network': node_1_1.id})

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['agent'] = {'code': 'wonder'}
        ContractAPI.subscribe_contracts(data_dict,
            {'dist_network': node_1_1.id, '_debug_server': True})

    def test0020_date_calculations(self):
        invoice_line = mock.Mock()
        invoice_line.coverage_start = datetime.date(2000, 12, 31)
        invoice_line.coverage_end = datetime.date(2004, 1, 1)

        date_line = self.PlanDate()
        date_line.frequency = 'yearly'

        # Test empty
        date_line.get_reference_date = mock.MagicMock(return_value=None)
        self.assertEqual(date_line.get_dates(invoice_line), set())

        date_line.get_reference_date = mock.MagicMock(
            return_value=datetime.date(2000, 1, 1))

        # Test absolute
        date_line.type_ = 'absolute'
        date_line.month = '4'
        date_line.day = '10'

        date_line.first_match_only = True
        # Nothing matches, the first occurence is 2000-4-10 which is not in the
        # invoice line period
        self.assertEqual(date_line.get_dates(invoice_line), set())

        date_line.first_match_only = False
        self.assertEqual(date_line.get_dates(invoice_line), set([
                    datetime.date(2001, 4, 10), datetime.date(2002, 4, 10),
                    datetime.date(2003, 4, 10)]))

        # Test relative
        date_line.type_ = 'relative'
        date_line.year = '1'
        date_line.month = '2'
        date_line.day = '3'

        date_line.first_match_only = True
        self.assertEqual(date_line.get_dates(invoice_line),
            set([datetime.date(2001, 3, 4)]))

        date_line.first_match_only = False
        self.assertEqual(date_line.get_dates(invoice_line), set([
                    datetime.date(2001, 3, 4), datetime.date(2002, 5, 7),
                    datetime.date(2003, 7, 10)]))

    @test_framework.prepare_test(
        'distribution.test0002_dist_network_creation',
        )
    def test0030_close_network(self):
        self.APICore.close_distribution_network([
            {
                'code': 'node_1',
                'end_date': '2019-10-28',
                'block_payments': True
                },
            {
                'code': 'node_2',
                'block_payments': True
                }
            ], {})

    @test_framework.prepare_test(
        'commission_insurance.test0030_close_network',
        )
    def test0035_reopen_network(self):
        self.APICore.reopen_distribution_network([
            {
                'code': 'node_1'
                },
            {
                'code': 'node_2'
                }
            ], {})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_commission_insurance.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
