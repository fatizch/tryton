import datetime
import unittest

import trytond.tests.test_tryton

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
        self.assert_(party1.relations[0].type.reverse == party2.relations[0].type)
        self.assert_(party1.relations[0].type.name == rel_kind.name)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
