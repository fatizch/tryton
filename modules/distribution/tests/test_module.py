# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import copy

import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'distribution'
    extras = ['web_configuration']

    @classmethod
    def fetch_models_for(cls):
        return ['party_cog', 'company_cog']

    @test_framework.prepare_test(
        'company_cog.test0001_testCompanyCreation',
        )
    def test0002_dist_network_creation(self):
        company, = self.Company.search([('party.name', '=', 'World Company')])
        DistNetwork = Pool().get('distribution.network')
        Party = Pool().get('party.party')

        party_1 = Party(name='party_1', addresses=[])
        party_2 = Party(name='party_2', addresses=[])
        party_2_2 = Party(name='party_2_2', addresses=[])

        Party.save([party_1, party_2, party_2_2])

        root = DistNetwork(name='Root', code='root', company=company)
        root.save()

        node_1 = DistNetwork(name='Node 1', code='node_1', parent=root,
            company=company, party=party_1)
        node_2 = DistNetwork(name='Node 2', code='node_2', parent=root,
            company=company, party=party_2)
        DistNetwork.save([node_1, node_2])

        node_1_1 = DistNetwork(name='Node 1 1', code='node_1_1',
            parent=node_1, company=company)
        node_1_2 = DistNetwork(name='Node 1 2', code='node_1_2',
            parent=node_1, company=company)
        node_2_1 = DistNetwork(name='Node 2 1', code='node_2_1',
            parent=node_2, company=company)
        node_2_2 = DistNetwork(name='Node 2 2', code='node_2_2',
            parent=node_2, company=company, party=party_2_2)

        DistNetwork.save([node_1_1, node_1_2, node_2_1, node_2_2])

        self.assertEqual({x.id for x in node_2_2.parents},
            {node_2.id, root.id})
        self.assertEqual({x.id for x in node_2.parents}, {root.id})
        self.assertEqual({x.id for x in node_1.all_children},
            {node_1.id, node_1_1.id, node_1_2.id})
        self.assertEqual({x.id for x in root.all_children},
            {root.id, node_1.id, node_1_1.id, node_1_2.id, node_2.id,
                node_2_1.id, node_2_2.id})

    @test_framework.prepare_test(
        'distribution.test0002_dist_network_creation',
        )
    def test0020_create_distribution_networks_api(self):
        pool = Pool()
        Core = pool.get('api.core')
        Network = pool.get('distribution.network')
        node_2_2, = Network.search([('code', '=', 'node_2_2')])

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': False,
                    'name': 'My Network',
                    },
                ],
            'networks': [
                {
                    'ref': '1',
                    'party': {'ref': '1'},
                    'parent': {'code': 'node_2_1'},
                    },
                ],
            }

        data_dict = copy.deepcopy(data_ref)
        created = Core.create_distribution_networks(data_dict,
            {'_debug_server': True})
        network_1 = Network(created['networks'][0]['id'])
        self.assertEqual(network_1.code, created['networks'][0]['code'])
        self.assertEqual(network_1.code, 'node_2_1_1')
        self.assertEqual(network_1.party.id, created['parties'][0]['id'])
        self.assertEqual(network_1.party.name, 'My Network')
        self.assertEqual(network_1.parent.code, 'node_2_1')
        self.assertEqual(network_1.name, 'My Network')

        data_dict = copy.deepcopy(data_ref)
        del data_dict['parties']
        del data_dict['networks'][0]['party']
        data_dict['networks'][0]['name'] = 'Some Network'
        created = Core.create_distribution_networks(data_dict,
            {'_debug_server': True})
        network_2 = Network(created['networks'][0]['id'])
        self.assertEqual(network_2.code, 'node_2_1_2')
        self.assertEqual(network_2.party, None)
        self.assertEqual(network_2.name, 'Some Network')

        # Infer network from context
        data_dict = copy.deepcopy(data_ref)
        del data_dict['networks'][0]['parent']
        created = Core.create_distribution_networks(data_dict,
            {'_debug_server': True, 'dist_network': node_2_2.id})
        network_3 = Network(created['networks'][0]['id'])
        self.assertEqual(network_3.parent.code, 'node_2_2')

        # Error when trying to force a network you are not allowed to
        data_dict = copy.deepcopy(data_ref)
        self.assertEqual(
            Core.create_distribution_networks(data_dict,
                {'dist_network': node_2_2.id}).data,
            [{
                    'type': 'unauthorized_network',
                    'data': {
                        'user_network': 'node_2_2',
                        'network': 'node_2_1',
                        },
                    }])

        # Reuse existing party
        data_dict = copy.deepcopy(data_ref)
        del data_dict['parties']
        data_dict['networks'][0]['party'] = {'code': network_1.party.code}
        created = Core.create_distribution_networks(data_dict,
            {'_debug_server': True})
        network_3 = Network(created['networks'][0]['id'])
        self.assertEqual(network_3.party.id, network_1.party.id)

    @test_framework.prepare_test(
        'distribution.test0002_dist_network_creation'
        )
    def test0021_update_distribution_network_api(self):
        pool = Pool()
        Core = pool.get('api.core')
        Core.update_distribution_networks([
            {
                'code': 'node_1',
                'network': {'name': 'titi'},
                'party': {'name': 'tototo'}
                }
            ], {'_debug_server': True})

    @test_framework.prepare_test(
        'party_cog.test0001_createParties',
        'distribution.test0002_dist_network_creation',
        )
    def test9001_identity_context_api(self):
        pool = Pool()
        DistNetwork = pool.get('distribution.network')
        distNetwork = DistNetwork()
        User = pool.get('res.user')
        APIIdentity = pool.get('ir.api.identity')
        APICore = pool.get('api.core')
        WebUIResourceKey = pool.get('web.ui.resource.key')
        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        key_id = WebUIResourceKey.search([('code', '=', 'theme')])
        node_1.web_ui_resources = [
                {
                    'key': key_id[0],
                    'value': '"some value"',
                    'origin_resource': distNetwork,
                }]

        admin = User(1)

        api_user, = User.search([('login', '=', 'coog_api_user')])
        api_user.main_company = node_1.company
        api_user.save()

        test_user = User(login='test', dist_network=node_1.id,
            main_company=node_1.company.id)
        test_user.companies = [node_1.company]
        test_user.save()

        identity = APIIdentity()
        identity.identifier = '12345'
        identity.user = admin
        identity.save()

        network_identity = APIIdentity()
        network_identity.identifier = '09876'
        network_identity.user = test_user
        network_identity.save()

        with Transaction().set_user(User.search(
                    [('login', '=', 'coog_api_user')])[0].id):
            self.assertEqual(
                APICore.identity_context(
                    {'kind': 'generic', 'identifier': '12345'},
                    {'_debug_server': True}),
                {'user': {'id': 1, 'login': 'admin'}})

            self.assertEqual(
                APICore.identity_context(
                    {'kind': 'generic', 'identifier': '09876'},
                    {'_debug_server': True}),
                {'user': {'id': test_user.id, 'login': 'test'},
                    'dist_network': node_1.id})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
