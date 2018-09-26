# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'party_fr'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Address': 'party.address',
            'Country': 'country.country',
            'CountryAddressLine': 'country.address.line',
            'ZipCode': 'country.zip',
            }

    def test0010addresses_on_change(self):
        country = self.Country(name='fr', code='FR')
        country.address_lines = [self.CountryAddressLine(
                name='5_ligne5', string='Line 5')]
        country.save()

        zip_code1 = self.ZipCode(zip="1", city="Emerald", country=country,
            hexa_post_id='11')
        zip_code1.save()
        zip_code1_bis = self.ZipCode(zip="1", city="Emerald", country=country,
            line5='THE HILL', hexa_post_id='111')
        zip_code1_bis.save()
        zip_code2 = self.ZipCode(zip="2", city='Ruby', country=country,
            hexa_post_id='12')
        zip_code2.save()
        zip_code3 = self.ZipCode(zip="3", city="Topaz", country=country,
            line5='THE MOUNTAIN', hexa_post_id='13')
        zip_code3.save()

        dorothy = self.Party(name='Dorothy')
        dorothy.save()
        address1 = self.Address(party=dorothy, zip='2', country=country,
            city='Ruby')
        address1.save()

        address1.zip_and_city = zip_code1
        address1.on_change_zip_and_city()
        address1.save()
        self.assertEqual(address1.zip_and_city, zip_code1)
        self.assertEqual(address1.zip, '1')
        self.assertEqual(address1.city, 'Emerald')

        address1.address_lines['5_ligne5'] = 'THE HILL'
        address1.on_change_address_lines()
        address1.save()
        self.assertEqual(address1.zip_and_city, zip_code1_bis)
        self.assertEqual(address1.zip, '1')
        self.assertEqual(address1.city, 'Emerald')
        self.assertEqual(address1.address_lines['5_ligne5'], 'THE HILL')

        address1.address_lines['5_ligne5'] = ''
        address1.on_change_address_lines()
        address1.save()
        self.assertEqual(address1.zip_and_city, zip_code1)
        self.assertEqual(address1.zip, '1')
        self.assertEqual(address1.city, 'Emerald')
        self.assertEqual(address1.address_lines['5_ligne5'], '')

        address2 = self.Address()
        address2.party = dorothy
        address2.country = country
        address2.on_change_with_address_lines()
        address2.address_lines['5_ligne5'] = 'THE OTHER HILL'
        address2.zip_and_city = zip_code1
        address2.on_change_zip_and_city()
        address2.save()
        self.assertEqual(address2.address_lines['5_ligne5'], 'THE OTHER HILL')
        self.assertEqual(address2.zip_and_city, zip_code1)
        self.assertEqual(address2.zip, '1')
        self.assertEqual(address2.city, 'Emerald')

        address2.zip_and_city = zip_code3
        address2.on_change_zip_and_city()
        address2.save()
        self.assertEqual(address2.address_lines['5_ligne5'], 'THE OTHER HILL')
        self.assertEqual(address2.zip_and_city, zip_code3)
        self.assertEqual(address2.zip, '3')
        self.assertEqual(address2.city, 'Topaz')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
