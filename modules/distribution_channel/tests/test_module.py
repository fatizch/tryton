# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest

import trytond.tests.test_tryton
from trytond.pool import Pool
from trytond.server_context import ServerContext

from trytond.modules.coog_core import test_framework
from trytond.modules.rule_engine.tests.test_module import test_tree_element


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'distribution_channel'

    @classmethod
    def fetch_models_for(cls):
        return ['commission_insurance', 'distribution', 'offered']

    def test0002_create_channels(self):
        Channel = Pool().get('distribution.channel')

        channel_1 = Channel(name='Channel 1', code='channel_1')
        channel_1.save()

        channel_2 = Channel(name='Channel 2', code='channel_2')
        channel_2.save()

        channel_3 = Channel(name='Channel 3', code='channel_3')
        channel_3.save()

    # All code is a copy from commission_insurance because channel is required
    # on dist networks, so we cannot reuse anything :'(
    @test_framework.prepare_test(
        'distribution_channel.test0002_create_channels',
        'distribution.test0002_dist_network_creation',
        'commission_insurance.test0002_create_accounting',
        )
    def test0003_create_broker(self):
        pool = Pool()
        DistNetwork = pool.get('distribution.network')
        Party = pool.get('party.party')
        Channel = pool.get('distribution.channel')

        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])
        broker = Party()
        broker.is_person = False
        broker.name = 'My Broker'
        broker.save()

        channel_1, = Channel.search([('code', '=', 'channel_1')])
        channel_2, = Channel.search([('code', '=', 'channel_2')])

        node_1.party = broker
        node_1.is_distributor = True
        node_1.is_broker = True
        node_1.authorized_distribution_channels = [channel_1]
        node_1.save()

        node_1_1.is_distributor = True
        node_1_1.authorized_distribution_channels = [channel_2]
        node_1_1.save()

        self.assertEqual({x.id for x in node_1.all_net_channels},
            {channel_1.id})
        self.assertEqual({x.id for x in node_1_1.all_net_channels},
            {channel_1.id, channel_2.id})

    @test_framework.prepare_test(
        'distribution_channel.test0003_create_broker',
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

        wonder_agent_broker = Agent()
        wonder_agent_broker.company = product.company
        wonder_agent_broker.party = broker
        wonder_agent_broker.code = 'wonder'
        wonder_agent_broker.type_ = 'agent'
        wonder_agent_broker.plan = wonder_plan
        wonder_agent_broker.currency = product.company.currency
        wonder_agent_broker.save()

    @test_framework.prepare_test(
        'distribution_channel.test0004_create_commission_agents',
        )
    def test0005_set_commercial_products(self):
        pool = Pool()
        AccountProduct = pool.get('product.product')
        ComProduct = pool.get('distribution.commercial_product')
        DistNetwork = pool.get('distribution.network')
        Party = pool.get('party.party')
        Product = pool.get('offered.product')
        Channel = pool.get('distribution.channel')

        product, = Product.search([('code', '=', 'AAA')])
        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])
        broker, = Party.search([('name', '=', 'My Broker')])
        channel_1, = Channel.search([('code', '=', 'channel_1')])
        channel_2, = Channel.search([('code', '=', 'channel_2')])
        channel_3, = Channel.search([('code', '=', 'channel_3')])

        commission_product, = AccountProduct.search([
                ('code', '=', 'commission_product')])

        com_product_1 = ComProduct()
        com_product_1.code = 'com_product_1'
        com_product_1.name = 'Commercial Product 1'
        com_product_1.product = product
        com_product_1.dist_authorized_channels = [channel_1, channel_3]
        com_product_1.save()

        com_product_2 = ComProduct()
        com_product_2.code = 'com_product_2'
        com_product_2.name = 'Commercial Product 2'
        com_product_2.product = product
        com_product_2.dist_authorized_channels = [channel_1, channel_2]
        com_product_2.save()

        node_1.commercial_products = [com_product_1]
        node_1.save()
        node_1_1.commercial_products = [com_product_2]
        node_1_1.save()

    @test_framework.prepare_test(
        'bank_cog.test0010bank',
        'contract.test0002_testCountryCreation',
        'distribution_channel.test0005_set_commercial_products',
        )
    def test0015_subscribe_contract(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')
        DistNetwork = pool.get('distribution.network')
        Channel = pool.get('distribution.channel')

        channel_1, = Channel.search([('code', '=', 'channel_1')])
        channel_2, = Channel.search([('code', '=', 'channel_2')])
        channel_3, = Channel.search([('code', '=', 'channel_3')])
        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        node_1_1, = DistNetwork.search([('code', '=', 'node_1_1')])

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
                    'agent': {'code': 'wonder'},
                    'commercial_product': {'code': 'com_product_1'},
                    'billing': {
                        'payer': {'ref': '1'},
                        'billing_mode': {'code': 'monthly'},
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

        # Channel is inferred from the dist_network (who only got one)
        data_dict = copy.deepcopy(data_ref)
        ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True, 'dist_network': node_1.id})
        self.assertEqual(Pool().get('contract').search([])[0].dist_channel.code,
            'channel_1')

        # Channel inferance cannot happen here, because node_1_1 has two
        # channels
        data_dict = copy.deepcopy(data_ref)
        self.assertEqual(
            ContractAPI.subscribe_contracts(data_dict,
                {'dist_network': node_1_1.id}).data, [
                {
                    'type': 'missing_distribution_channel',
                    'data': {},
                    },
                ])

        # We can force the value
        data_dict = copy.deepcopy(data_ref)
        ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True, 'dist_network': node_1_1.id,
                'distribution_channel': channel_1.id})

        data_dict = copy.deepcopy(data_ref)
        self.assertEqual(
            ContractAPI.subscribe_contracts(data_dict,
                {'dist_network': node_1_1.id,
                    'distribution_channel': channel_2.id}).data, [
                {
                    'type': 'unauthorized_channel_for_product',
                    'data': {
                        'channel': 'channel_2',
                        'product': 'com_product_1',
                        },
                    },
                ])

        data_dict = copy.deepcopy(data_ref)
        self.assertEqual(
            ContractAPI.subscribe_contracts(data_dict,
                {'dist_network': node_1_1.id,
                    'distribution_channel': channel_3.id}).data[0],
            {
                'type': 'unauthorized_channel',
                'data': {
                    'channel': 'channel_3',
                    'network': node_1_1.id,
                    },
                },
            )

    @test_framework.prepare_test(
        'distribution_channel.test0015_subscribe_contract',
        )
    def test0200_test_rule_tree_elements(self):
        pool = Pool()
        Contract = pool.get('contract')
        Channel = pool.get('distribution.channel')

        channel_1, = Channel.search([('code', '=', 'channel_1')])
        contract = Contract.search([])[0]

        args = {}
        contract.init_dict_for_rule_engine(args)
        self.assertEqual(test_tree_element(
                'rule_engine.runtime',
                '_re_get_channel_code',
                args).result,
            'channel_1')

        APIRuleRuntime = Pool().get('api.rule_runtime')
        with ServerContext().set_context(_test_api_tree_elements=True):
            with ServerContext().set_context(
                    api_rule_context=APIRuleRuntime.get_runtime()):
                self.assertEqual(test_tree_element(
                        'rule_engine.runtime',
                        '_re_get_channel_code',
                        {'dist_channel': channel_1}).result,
                    'channel_1')

    @test_framework.prepare_test(
        'distribution_channel.test0002_create_channels',
        'distribution.test0002_dist_network_creation',
        )
    def test0020_create_distribution_networks_api(self):
        pool = Pool()
        APICore = pool.get('api.core')
        Network = pool.get('distribution.network')

        data_ref = {
            'networks': [
                {
                    'ref': '1',
                    'name': 'My Test Network',
                    'parent': {'code': 'node_2_1'},
                    'distribution_channels': [
                        {'code': 'channel_2'},
                        {'code': 'channel_3'},
                        ],
                    },
                ],
            }

        data_dict = copy.deepcopy(data_ref)
        created = APICore.create_distribution_networks(data_dict,
            {'_debug_server': True})
        network_1 = Network(created['networks'][0]['id'])
        self.assertEqual(
            {x.code for x in network_1.authorized_distribution_channels},
            {'channel_2', 'channel_3'})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
