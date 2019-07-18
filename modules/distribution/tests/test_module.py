# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'distribution'

    @classmethod
    def fetch_models_for(cls):
        return ['party_cog', 'company_cog']

    @test_framework.prepare_test(
        'company_cog.test0001_testCompanyCreation',
        )
    def test0002_dist_network_creation(self):
        company, = self.Company.search([('party.name', '=', 'World Company')])
        DistNetwork = Pool().get('distribution.network')
        root = DistNetwork(name='Root', code='root')
        root.save()

        node_1 = DistNetwork(name='Node 1', code='node_1', parent=root,
            company=company)
        node_2 = DistNetwork(name='Node 2', code='node_2', parent=root,
            company=company)
        DistNetwork.save([node_1, node_2])

        node_1_1 = DistNetwork(name='Node 1 1', code='node_1_1',
            parent=node_1, company=company)
        node_1_2 = DistNetwork(name='Node 1 2', code='node_1_2',
            parent=node_1, company=company)
        node_2_1 = DistNetwork(name='Node 2 1', code='node_2_1',
            parent=node_2, company=company)
        node_2_2 = DistNetwork(name='Node 2 2', code='node_2_2',
            parent=node_2, company=company)
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
        'party_cog.test0001_createParties',
        'distribution.test0002_dist_network_creation',
        )
    def test9001_identity_context_api(self):
        pool = Pool()
        DistNetwork = pool.get('distribution.network')
        User = pool.get('res.user')
        APIIdentity = pool.get('ir.api.identity')
        APICore = pool.get('api.core')

        node_1, = DistNetwork.search([('code', '=', 'node_1')])
        admin = User(1)

        test_user = User(login='test', dist_network=node_1.id)
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
