import datetime
import unittest

import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.modules.coop_utils import test_framework


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
            'RelationKind': 'party.relation.kind',
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
        self.RelationKind.create([{
                    'code': 'parent',
                    'name': 'Parent',
                    'reversed_name': 'Children'
                    }])

    @test_framework.prepare_test('party_cog.test0001_createParties')
    def test0010relations(self):
        '''
        Test Relations
        '''
        party1 = self.Party.search([('name', '=', 'Parent')])[0]
        party2 = self.Party.search([('name', '=', 'Children')])[0]
        rel_kind = self.RelationKind.search([])[0]
        relation = self.PartyRelation()
        relation.from_party = party1
        relation.to_party = party2
        relation.relation_kind = rel_kind
        relation.start_date = datetime.date.today()
        relation.save()

        self.assert_(relation.id > 0)
        self.assert_(party1.relations[0] == party2.in_relation_with[0])
        self.assert_(party1.relations[0].relation_name == rel_kind.name)
        with Transaction().set_context(direction='reverse'):
            self.assert_(party2.in_relation_with[0].relation_name
                == rel_kind.reversed_name)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
