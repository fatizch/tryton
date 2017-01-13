# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.exceptions import UserError


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'endorsement_set'

    @classmethod
    def fetch_models_for(cls):
        return ['endorsement', 'contract_set']

    @classmethod
    def get_models(cls):
        return {
            'EndorsementSet': 'endorsement.set',
            }

    @test_framework.prepare_test(
        'endorsement.test0030_create_endorsement',
        )
    def test_001_create_endorsement_set(self):
        contract, = self.Contract.search([
                ('product.code', '=', 'AAA'),
                ])

        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ])
        start_date = product.start_date + datetime.timedelta(weeks=4)
        contract2 = self.Contract(
            product=product.id,
            company=product.company.id,
            start_date=start_date,
            appliable_conditions_date=start_date,
            )
        contract2.save()
        contract2.activate_contract()
        contract2.save()
        self.assertEqual(contract2.status, 'active')

        endorsement, = self.Endorsement.search([
                ('contracts', '=', contract.id),
                ])
        definition, = self.EndorsementDefinition.search([
                ('code', '=', 'change_contract_number'),
                ])

        effective_date = contract.start_date + datetime.timedelta(weeks=24)
        endorsement2 = self.Endorsement(
            definition=definition,
            effective_date=effective_date,
            contract_endorsements=[{
                    'contract': contract2.id,
                    'values': {
                        'contract_number': '1234_2',
                        },
                    }])
        endorsement2.save()
        self.assertEqual(endorsement.state, 'draft')
        self.assertEqual(endorsement2.state, 'draft')

        endorsement_set = self.EndorsementSet(
            endorsements=[endorsement, endorsement2])
        endorsement_set.save()
        self.assertEqual(endorsement_set.state, 'draft')

    @test_framework.prepare_test(
        'endorsement_set.test_001_create_endorsement_set',
        )
    def test_002_must_apply_decline_all(self):
        'Test that one cannot apply an endorsement independently'
        sub_state = self.SubState(name='Illegible', code='illegible',
                state='declined')
        sub_state.save()
        contract = self.Contract.search([
                ('product.code', '=', 'AAA'),
                ])[0]
        endorsement = self.Endorsement.search([
                ('contracts', '=', contract.id),
                ])[0]
        self.assertEqual(endorsement.state, 'draft')
        self.assertRaises(UserError, endorsement.decline, [endorsement],
            reason=sub_state)
        self.assertEqual(endorsement.state, 'draft')
        self.assertRaises(UserError, endorsement.apply, [endorsement])
        self.assertEqual(endorsement.state, 'draft')

    @test_framework.prepare_test(
        'endorsement_set.test_001_create_endorsement_set',
        )
    def test_003_decline_set(self):
        sub_state = self.SubState(name='Illegible', code='illegible',
                state='declined')
        sub_state.save()
        endorsement_set, = self.EndorsementSet.search([])
        self.assertEqual(endorsement_set.state, 'draft')
        self.EndorsementSet.decline_set([endorsement_set], reason=sub_state)
        self.assertEqual(endorsement_set.state, 'declined')
        self.assertEqual(endorsement_set.endorsements[0].state, 'declined')
        self.assertEqual(endorsement_set.endorsements[1].state, 'declined')

    @test_framework.prepare_test(
        'endorsement_set.test_001_create_endorsement_set',
        )
    def test_004_apply_set(self):
        endorsement_set, = self.EndorsementSet.search([])
        self.assertEqual(endorsement_set.state, 'draft')
        self.EndorsementSet.apply_set([endorsement_set])
        self.assertEqual(endorsement_set.state, 'applied')
        self.assertEqual(endorsement_set.endorsements[0].state, 'applied')
        self.assertEqual(endorsement_set.endorsements[1].state, 'applied')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
