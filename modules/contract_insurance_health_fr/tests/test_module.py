# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest
import datetime

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework
from trytond.exceptions import UserError


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_insurance_health_fr'

    @classmethod
    def fetch_models_for(cls):
        return ['contract_insurance']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'PartyRelationType': 'party.relation.type',
            'PartyRelation': 'party.relation.all',
            }

    def test0002_create_systems(self):
        pool = Pool()
        System = pool.get('health.care_system')
        Fund = pool.get('health.insurance_fund')

        system_1 = System()
        system_1.name = 'Regime General'
        system_1.code = '01'
        system_1.short_name = 'S1'
        system_1.save()

        fund_1 = Fund()
        fund_1.name = 'Some value'
        fund_1.code = '010110000'
        fund_1.department = '01'
        fund_1.hc_system = system_1
        fund_1.save()

    def test0010_social_security_relation(self):
        relation_dependent, = self.PartyRelationType.search([
                ('xml_id', '=', 'contract_insurance_health_fr.'
                    'social_security_dependent_relation_type'),
                ])
        relation_insured, = self.PartyRelationType.search([
                ('xml_id', '=', 'contract_insurance_health_fr.'
                    'social_security_insured_relation_type'),
                ])
        party_insured = self.Party(name='Insured', first_name='M',
            gender='male', is_person=True,
            birth_date=datetime.date(1978, 2, 15),
            ssn='178022460050197')
        party_insured.save()
        party_dependent = self.Party(name='Dependent', first_name='M',
            gender='male', is_person=True,
            birth_date=datetime.date(2005, 2, 15),
            ssn='178029435711662')
        party_dependent.save()
        party_dependent2 = self.Party(name='Dependent', first_name='MBis',
            gender='male', is_person=True,
            birth_date=datetime.date(1999, 2, 15),
            ssn='178025607673572')
        party_dependent2.save()
        relation = self.PartyRelation(from_=party_insured,
            type=relation_insured, to=party_dependent)
        relation.save()
        relation2 = self.PartyRelation(from_=party_insured,
            type=relation_dependent, to=party_dependent2)
        self.assertRaises(UserError, relation2.save)

    @test_framework.prepare_test(
        'health.test0005_PrepareProductForSubscription',
        'contract_insurance_health_fr.test0002_create_systems',
        'contract.test0002_testCountryCreation',
        )
    def test0060_subscribe_contract_API(self):
        ContractAPI = Pool().get('api.contract')
        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Mother',
                    'birth_date': '1978-01-14',
                    'gender': 'female',
                    'ssn': '145067512312354',
                    'hc_system': {'code': '01'},
                    'insurance_fund_number': '010110000',
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
                                {
                                    'coverage': {'code': 'GAM'},
                                    'extra_data': {},
                                    },
                                ],
                            },
                        ],
                    'coverages': [
                        {
                            'coverage': {'code': 'DEL'},
                            'extra_data': {},
                            },
                        ],
                    },
                ],
            'options': {
                'activate': True,
                },
            }

        data_dict = copy.deepcopy(data_ref)
        self.ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})

        data_dict = copy.deepcopy(data_ref)
        data_dict['parties'][0]['first_name'] = 'Auntie'
        del data_dict['parties'][0]['hc_system']
        self.assertEqual(
            ContractAPI.subscribe_contracts(data_dict, {}).data,
            [{
                    'type': 'missing_healthcare_system',
                    'data': {'insurance_fund_number': '010110000'},
                    }])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
