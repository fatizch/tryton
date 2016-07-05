# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'contract_set'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'PartyRelationType': 'party.relation.type',
            'PartyRelation': 'party.relation.all',
            'Contract': 'contract',
            'CoveredElement': 'contract.covered_element',
            'RuleEngineRuntime': 'rule_engine.runtime',
            'ContractSet': 'contract.set',
            }

    def test001_test_rule_engine_function(self):

        relation_spouse = self.PartyRelationType(name='Spouse', code='spouse')
        relation_spouse.save()
        relation_spouse.reverse = relation_spouse
        relation_spouse.reverse.save()
        relation_child = self.PartyRelationType(name='Child', code='child')
        relation_child.save()
        relation_parent = self.PartyRelationType(name='Parent', code='parent')
        relation_parent.reverse = relation_child
        relation_parent.save()

        party_father = self.Party(name='Father', first_name='F', gender='male',
            is_person=True, birth_date=datetime.date(1978, 2, 15))
        party_father.save()
        party_mother = self.Party(name='Mother', first_name='M',
            gender='female', is_person=True,
            birth_date=datetime.date(1975, 7, 10),
            relations=[{'to': party_father, 'type': relation_spouse}])
        party_mother.save()
        party_child1 = self.Party(name='Child1', first_name='C', gender='male',
            is_person=True, birth_date=datetime.date(2010, 3, 5),
            relations=[{'to': party_father, 'type': relation_child},
                {'to': party_mother, 'type': relation_child}])
        party_child1.save()
        party_child2 = self.Party(name='Child2', first_name='C',
            gender='female', is_person=True,
            birth_date=datetime.date(2009, 5, 15),
            relations=[{'to': party_father, 'type': relation_child},
                {'to': party_mother, 'type': relation_child}])
        party_child2.save()

        contract1 = self.Contract(start_date=datetime.date(2014, 01, 01),
            subscriber=party_father,
            covered_elements=[{
                    'party': party_father,
                    'options': [{
                            'start_date': datetime.date(2014, 1, 1),
                            'status': 'active'
                            }],
                    'sub_covered_elements': [],
                    }, {
                    'party': party_child1,
                    'options': [{
                            'start_date': datetime.date(2014, 1, 1),
                            'status': 'active',
                            }],
                    'sub_covered_elements': [],
                    }])
        contract2 = self.Contract(start_date=datetime.date(2014, 01, 01),
            subscriber=party_mother,
            covered_elements=[{
                    'party': party_mother,
                    'options': [{
                            'start_date': datetime.date(2014, 1, 1),
                            'status': 'active',
                            }],
                    'sub_covered_elements': [],
                    }, {
                    'party': party_child2,
                    'options': [{
                            'start_date': datetime.date(2014, 1, 1),
                            'final_end_date': datetime.date(2014, 1, 31),
                            'status': 'active',
                            }],
                    'sub_covered_elements': [],
                    }])
        contract_set = self.ContractSet()
        contract_set.contracts = [contract1, contract2]

        args = {'contract': contract1, 'contract_set': contract_set,
            'person': party_child1, 'date': datetime.date(2014, 1, 1)}
        # test _re_relation_number
        self.assertEqual(
            self.RuleEngineRuntime._re_relation_number_order_by_age_in_set(
                args, 'child'), 2)
        args = {'contract': contract1, 'person': party_child2,
            'contract_set': contract_set, 'date': datetime.date(2014, 1, 1)}
        self.assertEqual(
            self.RuleEngineRuntime._re_relation_number_order_by_age_in_set(
                args, 'child'), 1)
        args = {'contract': contract1, 'contract_set': contract_set,
            'person': party_child1, 'date': datetime.date(2014, 2, 1)}
        self.assertEqual(
            self.RuleEngineRuntime._re_relation_number_order_by_age_in_set(
                args, 'child'), 1)
        # test _re_number_of_covered_with_relation
        args = {'contract': contract2, 'date': datetime.date(2014, 1, 1),
            'contract_set': contract_set}
        self.assertEqual(self.RuleEngineRuntime.
            _re_number_of_covered_with_relation_in_set(args, 'child'), 2)
        self.assertEqual(self.RuleEngineRuntime.
            _re_number_of_covered_with_relation_in_set(args, 'spouse'), 2)
        args = {'contract': contract2, 'date': datetime.date(2014, 2, 1),
            'contract_set': contract_set}
        self.assertEqual(self.RuleEngineRuntime.
            _re_number_of_covered_with_relation_in_set(args, 'child'), 1)
        self.assertEqual(self.RuleEngineRuntime.
            _re_number_of_covered_with_relation_in_set(args, 'spouse'), 2)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
