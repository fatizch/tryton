import sys
import os
import datetime

DIR = os.path.abspath(os.path.normpath(
    os.path.join(__file__, '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton

from trytond.modules.coop_utils import test_framework

MODULE_NAME = os.path.basename(os.path.abspath(os.path.join(
    os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return MODULE_NAME

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'RelationKind': 'party.party_relation_kind',
            'PartyRelation': 'party.party-relation',
        }

    def test0001_createParties(self):
        self.Party.create([
            {
                'name': 'Parent',
                'addresses': [],
            },
            {
                'name': 'Children',
                'addresses': [],
            }])

    @test_framework.prepare_test('coop_party.test0001_createParties')
    def test0010relations(self):
        '''
        Test Relations
        '''
        party1 = self.Party.search([('name', '=', 'Parent')])[0]
        party2 = self.Party.search([('name', '=', 'Children')])[0]
        relation = self.PartyRelation()
        relation.from_party = party1
        relation.to_party = party2
        relation.kind = 'parent'
        relation.start_date = datetime.date.today()
        relation.save()

        relation2 = self.PartyRelation()
        relation2.from_party = party2
        relation2.to_party = party1
        relation2.kind = 'child'
        relation2.start_date = datetime.date.today()
        relation2.save()

        self.assert_(relation.id > 0)
        self.assert_(party1.relations[0] == party2.in_relation_with[0])
        self.assert_(party2.relations[0] == party1.in_relation_with[0])
        self.assert_(relation.reverse_kind == relation2.kind)
        self.assert_(relation2.reverse_kind == relation.kind)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
