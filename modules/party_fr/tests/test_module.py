# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from datetime import date

import trytond.tests.test_tryton
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'party_fr'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Address': 'party.address',
            'Country': 'country.country',
            'ZipCode': 'country.zip',
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
        except:
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
            if int(value[3:5]) not in range(1, 13):
                month = '1'
            else:
                month = value[3:5]
            birth_date = date(int('19' + value[1:3]), int(month), 1)
            gender = 'male'
            if value[0:1] == '2':
                gender = 'female'
            self.createPerson(birth_date, value, test, gender, i)

    def test0020addresses_on_change(self):
        country = self.Country(name="Oz", code='OZ')
        country.save()

        zip_code1 = self.ZipCode(zip="1", city="Emerald", country=country,
            hexa_post_id='11')
        zip_code1.save()
        zip_code1_bis = self.ZipCode(zip="1", city="Emerald", country=country,
            line5='THE HILL', hexa_post_id='111')
        zip_code1_bis.save()
        zip_code2 = self.ZipCode(zip="2", city="Ruby", country=country,
            hexa_post_id='12')
        zip_code2.save()

        dorothy = self.Party(name="Dorothy")
        dorothy.save()
        address1 = self.Address(party=dorothy, zip="2", country=country,
            city="Ruby")
        address1.save()

        address1.zip_and_city = zip_code1
        address1.on_change_zip_and_city()
        address1.save()
        self.assertEqual(address1.zip_and_city, zip_code1)
        self.assertEqual(address1.zip, "1")
        self.assertEqual(address1.city, "Emerald")

        address1.streetbis = "THE HILL"
        address1.on_change_streetbis()
        address1.save()
        self.assertEqual(address1.zip_and_city, zip_code1_bis)
        self.assertEqual(address1.zip, "1")
        self.assertEqual(address1.city, "Emerald")
        self.assertEqual(address1.streetbis, "THE HILL")

        address1.streetbis = None
        address1.on_change_streetbis()
        address1.save()
        self.assertEqual(address1.zip_and_city, zip_code1)
        self.assertEqual(address1.zip, "1")
        self.assertEqual(address1.city, "Emerald")
        self.assertEqual(address1.streetbis, None)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
