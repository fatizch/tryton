import sys
import os
import datetime

DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class CoopPartyTestCase(unittest.TestCase):
    '''
    Test Coop Party module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('coop_party')
        self.Party = POOL.get('party.party')
        self.RelationKind = POOL.get('party.party_relation_kind')
        self.PartyRelation = POOL.get('party.party-relation')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('coop_party')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def createParty(self, name):
        party = self.Party.create({
            'name': name,
            'addresses': []
            })
        return party

    def test0010relations(self):
        '''
        Test Relations
        '''
        with Transaction().start(DB_NAME, USER,
           context=CONTEXT) as transaction:
            party1 = self.createParty('Parent')
            party2 = self.createParty('Children')
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
            transaction.cursor.commit()
            self.assert_(relation.id > 0)
            self.assert_(party1.relations[0] == party2.in_relation_with[0])
            self.assert_(party2.relations[0] == party1.in_relation_with[0])
            self.assert_(relation.reverse_kind == relation2.kind)
            self.assert_(relation2.reverse_kind == relation.kind)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CoopPartyTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
