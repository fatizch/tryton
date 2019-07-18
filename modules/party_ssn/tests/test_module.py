# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from datetime import date

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'party_ssn'

    @classmethod
    def fetch_models_for(cls):
        return ['party_cog']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            }

    def createPerson(
            self, birth_date, ssn, expected_return, gender='male', i=0):
        try:
            person, = self.Party.create([{
                'is_person': True,
                'name': 'Person %s' % i,
                'first_name': 'first name %s' % i,
                'ssn': ssn,
                'birth_date': birth_date,
                'gender': gender,
                'addresses': []
            }])
            res = person.id > 0
        except Exception:
            res = False
        self.assertEqual(res, expected_return)

    def test0010ssn(self):
        '''
        Test SSN
        '''
        values = (
                ('145062B12312341', True),
                ('145062B12312342', False),
                ('145062A12312314', True),
                ('145062A12312315', False),
                ('145067512312354', True),
                ('145067512312355', False),
                ('145065C12312307', False),
                ('14511661231233', False),
                ('279086507612053', True),
                ('176209939705448', True)
        )
        for i, (value, test) in enumerate(values):
            if int(value[3:5]) not in list(range(1, 13)):
                month = '1'
            else:
                month = value[3:5]
            birth_date = date(int('19' + value[1:3]), int(month), 1)
            gender = 'male'
            if value[0:1] == '2':
                gender = 'female'
            self.createPerson(birth_date, value, test, gender, i)

    @test_framework.prepare_test('party_cog.test0002_testCountryCreation')
    def test0060_party_API(self):
        pool = Pool()
        APIParty = pool.get('api.party')
        Party = pool.get('party.party')

        result = APIParty.create_party({
                'parties': [
                    {
                        'ref': '1',
                        'is_person': True,
                        'name': 'Doe',
                        'first_name': 'Father',
                        'birth_date': '1980-01-20',
                        'gender': 'male',
                        'ssn': '145067512312354',
                        },
                    ]}, {'_debug_server': True})
        party = Party(result['parties'][0]['id'])
        self.assertEqual(party.ssn, '145067512312354')

        self.assertEqual(
            APIParty.create_party({
                'parties': [
                    {
                        'ref': '1',
                        'is_person': True,
                        'name': 'Doe',
                        'first_name': 'Father',
                        'birth_date': '1980-01-20',
                        'gender': 'male',
                        'ssn': '145067512312353',
                        },
                        ]}, {}).data,
            [{
                    'type': 'invalid_ssn',
                    'data': {'ssn': '145067512312353'},
                    }])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
