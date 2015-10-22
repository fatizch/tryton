import datetime
import unittest

import trytond.tests.test_tryton
from trytond.transaction import Transaction
from trytond.exceptions import UserWarning
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'party_cog'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'RelationType': 'party.relation.type',
            'PartyRelation': 'party.relation',
            'Address': 'party.address',
            'Country': 'country.country',
            'ZipCode': 'country.zipcode',
        }

    def test0001_createParties(self):
        self.Party.create([{
                    'name': 'Parent',
                    'addresses': [],
                }, {
                    'name': 'Children',
                    'addresses': [],
                }])
        relation_parent, = self.RelationType.create([{
                    'code': 'parent',
                    'name': 'Parent',
                    }])
        relation_children, = self.RelationType.create([{
                    'code': 'children',
                    'name': 'Children',
                    'reverse': relation_parent.id,
                    }])
        relation_parent.reverse = relation_children
        relation_parent.save()

    @test_framework.prepare_test('party_cog.test0001_createParties')
    def test0010relations(self):
        '''
        Test Relations
        '''
        party1 = self.Party.search([('name', '=', 'Parent')])[0]
        party2 = self.Party.search([('name', '=', 'Children')])[0]
        rel_kind = self.RelationType.search([])[0]
        relation = self.PartyRelation()
        relation.from_ = party1
        relation.to = party2
        relation.type = rel_kind
        relation.start_date = datetime.date.today()
        relation.save()

        self.assert_(relation.id > 0)
        self.assert_(party1.relations[0].from_ == party2.relations[0].to)
        self.assert_(party1.relations[0].to == party2.relations[0].from_)
        self.assert_(
            party1.relations[0].type.reverse == party2.relations[0].type)
        self.assert_(party1.relations[0].type.name == rel_kind.name)

    def test0020SearchDuplicate(self):
        with Transaction().set_user(1):
            party1 = self.Party(is_person=True, first_name='Mike',
                name='Wazowski', birth_date=datetime.date(2001, 10, 28),
                gender='male')
            party1.save()
            self.assert_(party1.id > 0)
            party2 = self.Party(is_person=True, first_name='Mike',
                name='Wazowski', birth_date=datetime.date(2001, 10, 28),
                gender='male')
            self.assertRaises(UserWarning, party2.save)
            party3 = self.Party(is_person=True, first_name='MIKE',
                name='wazowski', birth_date=datetime.date(2001, 10, 28),
                gender='male')
            self.assertRaises(UserWarning, party3.save)
            party4 = self.Party(is_person=True, first_name='Mikel',
                name='Wazowski', birth_date=datetime.date(2001, 10, 28),
                gender='male')
            party4.save()
            self.assert_(party4.id > 0)
            party5 = self.Party(is_company=True, name='Monsters Incorporated',
                short_name='Monsters, Inc.')
            party5.save()
            party6 = self.Party(is_company=True, name='MONSTERS Incorporated',
                short_name='Monsters, Inc.')
            self.assertRaises(UserWarning, party6.save)

    def test0030addresses_on_change(self):
        country = self.Country(name="Oz", code='OZ')
        country.save()
        zip_code1 = self.ZipCode(zip="1", city="Emerald", country=country)
        zip_code1.save()
        zip_code2 = self.ZipCode(zip="2", city="Ruby", country=country)
        zip_code2.save()
        zip_code3 = self.ZipCode(zip="3", city="Diamond", country=country)
        zip_code3.save()
        zip_code4 = self.ZipCode(zip="3", city="Amber", country=country)
        zip_code4.save()
        dorothy = self.Party(name="Dorothy")
        dorothy.save()
        address1 = self.Address(party=dorothy, zip="1", country=country,
            city="Emerald")
        address1.save()
        address2 = self.Address(party=dorothy, zip="2", country=country,
            city="Ruby")
        address2.save()
        address3 = self.Address(party=dorothy, zip="3", country=country,
            city="Diamond")
        address3.save()
        address4 = self.Address(party=dorothy, zip="3", country=country,
            city="Amber")
        address4.save()

        self.assertEqual(address1.zip_and_city, zip_code1)
        self.assertEqual(address2.zip_and_city, zip_code2)
        self.assertEqual(address3.zip_and_city, zip_code3)
        self.assertEqual(address4.zip_and_city, zip_code4)

        address1.zip = "2"
        address1.on_change_zip()
        address1.save()
        self.assertEqual(address1.zip_and_city, zip_code2)
        self.assertEqual(address1.zip, "2")
        self.assertEqual(address1.city, "Ruby")

        address2.zip_and_city = zip_code1
        address2.on_change_zip_and_city()
        address2.save()
        self.assertEqual(address2.zip_and_city, zip_code1)
        self.assertEqual(address2.zip, "1")
        self.assertEqual(address2.city, "Emerald")

        address3.on_change_zip()
        self.assertEqual(address3.zip, "3")
        self.assertEqual(address3.city, "Diamond")
        self.assertEqual(address3.zip_and_city, zip_code3)

        address3.on_change_city()
        self.assertEqual(address3.zip, "3")
        self.assertEqual(address3.city, "Diamond")
        self.assertEqual(address3.zip_and_city, zip_code3)

        address3.on_change_zip_and_city()
        self.assertEqual(address3.zip, "3")
        self.assertEqual(address3.city, "Diamond")
        self.assertEqual(address3.zip_and_city, zip_code3)

        address3.city = "Emerald"
        address3.on_change_city()
        address3.save()
        self.assertEqual(address3.zip_and_city, zip_code1)
        self.assertEqual(address3.zip, "1")
        self.assertEqual(address3.city, "Emerald")

        address3.zip = "3"
        address3.on_change_zip()
        address3.save()
        self.assertTrue(address3.city in ["Diamond", "Amber"])

        address2.city = "Amber"
        address2.on_change_city()
        address2.save()
        self.assertTrue(address2.zip == "3")

    def test0040set_contact(self):
        marty = self.Party(name="Marty")
        marty.save()

        marty.set_contact([marty], 'phone', '0164091187')
        self.assertEqual(marty.phone, '0164091187')
        self.assertEqual(marty.mobile, '')

        marty.set_contact([marty], 'phone', '')
        self.assertEqual(marty.phone, '')
        self.assertEqual(marty.mobile, '')

        marty.set_contact([marty], 'mobile', '0683162994')
        self.assertEqual(marty.mobile, '0683162994')
        self.assertEqual(marty.phone, '')

        marty.set_contact([marty], 'mobile', '0679511857')
        self.assertEqual(marty.mobile, '0679511857')
        self.assertEqual(marty.phone, '')

        marty.set_contact([marty], 'mobile', '0657511879')
        marty.set_contact([marty], 'phone', '0164091187')
        self.assertEqual(marty.mobile, '0657511879')
        self.assertEqual(marty.phone, '0164091187')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
