# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton

from trytond.pool import Pool

from trytond.modules.api import date_for_api
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'endorsement_party'

    @test_framework.prepare_test(
        'party_cog.test0002_testCountryCreation',
        )
    def test0010_change_party_addresses(self):
        pool = Pool()
        Party = pool.get('party.party')
        PartyAPI = pool.get('api.party')
        EndorsementAPI = pool.get('api.endorsement')
        Endorsement = pool.get('endorsement')

        result = PartyAPI.create_party({
                'parties': [
                    {
                        'ref': '1',
                        'is_person': True,
                        'name': 'Doe',
                        'first_name': 'Father',
                        'birth_date': '1980-01-20',
                        'gender': 'male',
                        'addresses': [
                            {
                                'street': 'Somewhere along the street',
                                'zip': '75002',
                                'city': 'Paris',
                                'country': 'fr',
                                },
                            {
                                'street': 'Somewhere else along the street',
                                'zip': '75003',
                                'city': 'Paris',
                                'country': 'fr',
                                },
                            ],
                        },
                    {
                        'ref': '2',
                        'is_person': True,
                        'name': 'Doe',
                        'first_name': 'Mother',
                        'birth_date': '1981-10-10',
                        'gender': 'female',
                        'addresses': [
                            {
                                'street': 'Far away',
                                'zip': '75020',
                                'city': 'Paris',
                                'country': 'fr',
                                },
                            ],
                        },
                    ]}, {'_debug_server': True})
        party = Party(result['parties'][0]['id'])
        other_party = Party(result['parties'][1]['id'])

        today = datetime.date.today()
        result = EndorsementAPI.change_party_addresses({
                'party': {'code': party.code},
                'new_addresses': [
                    {
                        'street': 'Moved again',
                        'zip': '06000',
                        'city': 'Nice',
                        'country': 'fr',
                        },
                    ],
                }, {'_debug_server': True})
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result['endorsements']), 1)

        endorsement = Endorsement(result['endorsements'][0]['id'])
        self.assertEqual(endorsement.state, 'applied')
        self.assertEqual(endorsement.definition.code, 'change_party_address')
        self.assertEqual(endorsement.effective_date, today)
        self.assertEqual(party.addresses[-1].start_date, today)
        self.assertEqual(party.addresses[0].end_date, today -
            relativedelta(days=1))
        self.assertEqual(party.addresses[1].end_date, today -
            relativedelta(days=1))

        one_month_later = datetime.date.today() + relativedelta(months=1)
        result = EndorsementAPI.change_party_addresses({
                'party': {'code': party.code},
                'date': date_for_api(one_month_later),
                'new_addresses': [
                    {
                        'street': 'Moved another time',
                        'zip': '35000',
                        'city': 'Rennes',
                        'country': 'fr',
                        },
                    ],
                }, {'_debug_server': True})
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result['endorsements']), 1)

        endorsement = Endorsement(result['endorsements'][0]['id'])
        self.assertEqual(endorsement.state, 'applied')
        self.assertEqual(endorsement.definition.code, 'change_party_address')
        self.assertEqual(endorsement.effective_date, one_month_later)
        self.assertEqual(party.addresses[-1].start_date, one_month_later)
        self.assertEqual(party.addresses[0].end_date, today -
            relativedelta(days=1))
        self.assertEqual(party.addresses[1].end_date, today -
            relativedelta(days=1))
        self.assertEqual(party.addresses[2].end_date, one_month_later -
            relativedelta(days=1))

        self.assertEqual(
            EndorsementAPI.update_party_addresses({
                    'party': {'code': party.code},
                    'updated_addresses': [
                        {
                            'id': other_party.addresses[0].id,
                            'new_values': {
                                'street': 'Moved again',
                                'zip': '06000',
                                'city': 'Nice',
                                'country': 'fr',
                                },
                            },
                        ],
                    }, {}).data[0],
            {
                'type': 'invalid_party_address',
                'data': {
                    'party': party.code,
                    'address_id': other_party.addresses[0].id,
                    },
                })

        EndorsementAPI.update_party_addresses({
                'party': {'code': party.code},
                'updated_addresses': [
                    {
                        'id': party.addresses[0].id,
                        'new_values': {
                            'street': 'Address 0 Changed',
                            'zip': '75001',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        },
                    {
                        'id': party.addresses[3].id,
                        'new_values': {
                            'street': 'Address 3 Changed',
                            'zip': '75001',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        },
                    ],
                }, {'_debug_server': True})

        self.assertEqual(party.addresses[0].street, 'Address 0 Changed')
        self.assertEqual(party.addresses[3].street, 'Address 3 Changed')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_endorsement_party.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
