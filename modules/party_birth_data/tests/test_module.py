import unittest

import trytond.tests.test_tryton
from trytond.pool import Pool
from trytond.modules.coog_core import test_framework
from trytond.transaction import Transaction
from trytond.exceptions import UserWarning
import datetime


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'party_birth_data'

    @classmethod
    def activate_module(cls):
        trytond.tests.test_tryton.activate_module(['api', 'country_hexaposte',
                'party_ssn', 'party_birth_data'],
            cache_name='party_birth_data')

    @classmethod
    def get_models(cls):
        return {
            'ZipCode': 'country.zip',
            'Party': 'party.party',
            'Country': 'country.country',
        }

    def test0000_testCountryCreation(self):
        country = self.Country(name="Carthage", code='Oz')
        country.save()
        zipcode = self.ZipCode(city="DJERBA", zip="43142",
            insee_code="12873", country=country)
        zipcode.save()
        second_zipcode = self.ZipCode(city="NICE", zip="88888",
            insee_code="43142", country=country)
        second_zipcode.save()

    @test_framework.prepare_test(
        'party_birth_data.test0000_testCountryCreation'
    )
    def test0001_testPersonCreation(self):
        party = self.Party(
            is_person=True,
            name='Hannibal',
            first_name='Barca',
            birth_date=datetime.date(1980, 5, 30),
            gender='male',
            ssn='176324314251121',
        )
        party.save()
        second_party = self.Party(
            is_person=True,
            name='Von',
            first_name='Neuman',
            birth_date=datetime.date(1980, 5, 30),
            gender='male',
            ssn='180127226401223'
        )
        second_party.save()

    @test_framework.prepare_test(
        'party_birth_data.test0001_testPersonCreation'
    )
    def test0002_test_birth_zip_initialization_from_ssn(self):
        party, = self.Party.search([('ssn', '=', '176324314251121')])
        self.assertEqual(party.birth_zip, None)
        birth_zip = party.on_change_with_birth_zip()
        self.assertEqual(birth_zip, '43142')
        # Test if there is no associated zip
        second_party, = self.Party.search([('ssn', '=', '180127226401223')])
        birth_zip = second_party.on_change_with_birth_zip()
        self.assertEqual(birth_zip, None)

    @test_framework.prepare_test(
        'party_birth_data.test0001_testPersonCreation'
    )
    def test0002_test_birth_city_initialization_from_ssn(self):
        party, = self.Party.search([('ssn', '=', '176324314251121')])
        self.assertEqual(party.birth_city, None)
        birth_city = party.on_change_with_birth_city()
        self.assertEqual(birth_city, 'NICE')
        # Test if there is no associated birth_city
        second_party, = self.Party.search([('ssn', '=', '180127226401223')])
        birth_city = second_party.on_change_with_birth_city()
        second_party.save()
        self.assertEqual(birth_city, None)

    def test_check_SSN_from_party_information(self):
        Configuration = Pool().get('party.configuration')
        config = Configuration(1)
        config.check_ssn_with_party_information = True
        config.save()
        country = self.Country(name="France", code='fr')
        country.save()
        zipcode = self.ZipCode(city="Nice", zip="72264",
                               insee_code="72264", country=country)
        zipcode.save()
        with Transaction().set_user(1):
            person, = self.Party.create([{
                'is_person': True,
                'name': 'Person test',
                'first_name': 'first name test',
                'ssn': '180127226401223',
                'birth_date': datetime.date(1980, 12, 5),
                'gender': 'male',
                'addresses': [],
                'birth_country': country,
                'birth_zip': '72264',
                'birth_city': 'Nice'
            }])
            # Test ok
            person.save()
            # Test ko
            zipcode.insee_code = "72265"
            zipcode.save()
            person.birth_zip = "72265"
            self.assertRaises(UserWarning, person.save)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
