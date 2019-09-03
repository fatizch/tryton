# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import copy

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'commission_orias'

    @classmethod
    def fetch_models_for(cls):
        return ['party_cog', 'company_cog']

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
                    'orias': 'my_orias',
                    },
                ],
            }

        data_dict = copy.deepcopy(data_ref)
        created = Core.create_distribution_networks(data_dict,
            {'_debug_server': True})
        network_1 = Network(created['networks'][0]['id'])
        self.assertEqual(
            network_1.party.get_identifier_value('orias'), 'my_orias')

        # Error when trying to force a network you are not allowed to
        data_dict = copy.deepcopy(data_ref)
        del data_dict['networks'][0]['party']
        data_dict['networks'][0]['name'] = 'My Network'
        self.assertEqual(
            Core.create_distribution_networks(data_dict, {}).data,
            [{
                    'type': 'party_required_for_orias',
                    'data': {
                        'orias': 'my_orias',
                        },
                    }])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
