# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework
from trytond.exceptions import UserError


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'contract_insurance_health_fr'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'PartyRelationType': 'party.relation.type',
            'PartyRelation': 'party.relation.all',
            }

    def test0010_social_security_relation(self):
        relation_dependent, = self.PartyRelationType.search([
                ('xml_id', '=', 'contract_insurance_health_fr.'
                    'social_security_dependent_relation_type'),
                ])
        relation_insured, = self.PartyRelationType.search([
                ('xml_id', '=', 'contract_insurance_health_fr.'
                    'social_security_insured_relation_type'),
                ])
        party_insured = self.Party(name='Insured', first_name='M',
            gender='male', is_person=True,
            birth_date=datetime.date(1978, 2, 15),
            ssn='178022460050197')
        party_insured.save()
        party_dependent = self.Party(name='Dependent', first_name='M',
            gender='male', is_person=True,
            birth_date=datetime.date(2005, 2, 15),
            ssn='178029435711662')
        party_dependent.save()
        party_dependent2 = self.Party(name='Dependent', first_name='MBis',
            gender='male', is_person=True,
            birth_date=datetime.date(1999, 2, 15),
            ssn='178025607673572')
        party_dependent2.save()
        relation = self.PartyRelation(from_=party_insured,
            type=relation_insured, to=party_dependent)
        relation.save()
        relation2 = self.PartyRelation(from_=party_insured,
            type=relation_dependent, to=party_dependent2)
        self.assertRaises(UserError, relation2.save)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
