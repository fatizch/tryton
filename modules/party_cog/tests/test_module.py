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
    @classmethod
    def get_module_name(cls):
        return 'party_cog'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'RelationType': 'party.relation.type',
            'PartyRelation': 'party.relation',
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


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
