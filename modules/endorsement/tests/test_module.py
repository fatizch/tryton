# encoding: utf-8
import unittest
import doctest
import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.transaction import Transaction
from trytond.exceptions import UserError

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'endorsement'

    @classmethod
    def get_models(cls):
        return {
            'EndorsementDefinition': 'endorsement.definition',
            'EndorsementPart': 'endorsement.part',
            'EndorsementDefinitionPartRelation':
            'endorsement.definition-endorsement.part',
            'Endorsement': 'endorsement',
            'EndorsementContract': 'endorsement.contract',
            'EndorsementContractField': 'endorsement.contract.field',
            'EndorsementOptionField': 'endorsement.contract.option.field',
            'Field': 'ir.model.field',
            'SubState': 'endorsement.sub_state',
            }

    @classmethod
    def depending_modules(cls):
        return ['offered', 'contract']

    def test0000_test_add_endorsement_step(self):
        'Tests the add_endorsement_step method'
        from trytond.pool import Pool
        from trytond.wizard import StateView, StateTransition
        from trytond.modules.endorsement.wizard import (add_endorsement_step,
            EndorsementWizardStepMixin, StartEndorsement)

        class FakeEndorsement(StartEndorsement):
            def __init__(self):
                pass

        class TestStep(EndorsementWizardStepMixin):
            'Test Step'
            __name__ = 'my_test_step'

            @classmethod
            def state_view_name(cls):
                return 'test.test_my_test_step_view_form'

            def step_default(self, *args):
                return ('default', args)

            def step_previous(self, *args):
                return ('previous', args)

            def step_next(self, *args):
                return ('next', args)

            def step_suspend(self, *args):
                return ('suspend', args)

        add_endorsement_step(FakeEndorsement, TestStep, 'test_endorsement')

        self.assert_(isinstance(FakeEndorsement.test_endorsement, StateView))
        self.assert_(isinstance(FakeEndorsement.test_endorsement_previous,
                StateTransition))
        self.assert_(isinstance(FakeEndorsement.test_endorsement_next,
                StateTransition))
        self.assert_(isinstance(FakeEndorsement.test_endorsement_suspend,
                StateTransition))

        TestStep.__setup__()
        TestStep.__post_setup__()
        TestStep.__register__('endorsement')

        Pool().add(TestStep)

        test_wizard = FakeEndorsement()
        self.assertEqual(test_wizard.default_test_endorsement('foo'),
            ('default', ('foo',)))
        self.assertEqual(test_wizard.transition_test_endorsement_previous(),
            ('previous', ()))
        self.assertEqual(test_wizard.transition_test_endorsement_next(),
            ('next', ()))
        self.assertEqual(test_wizard.transition_test_endorsement_suspend(),
            ('suspend', ()))

    def test0001_check_possible_views(self):
        from trytond.pool import Pool
        from trytond.wizard import StateView
        from trytond.modules.endorsement import EndorsementWizardStepMixin
        from trytond.modules.endorsement.wizard import StartEndorsement

        class SimpleContractModification(EndorsementWizardStepMixin):
            'Simple Contract Modification'
            __name__ = 'endorsement.simple_contract_modification'

        class TestStartEndorsement(StartEndorsement):
            __name__ = 'endorsement.start'
            simple_contract_modification = StateView(
                'endorsement.simple_contract_modification',
                '', [])

        SimpleContractModification.__setup__()
        SimpleContractModification.__post_setup__()
        SimpleContractModification.__register__('endorsement')

        TestStartEndorsement.__setup__()
        TestStartEndorsement.__post_setup__()
        TestStartEndorsement.__register__('endorsement')

        Pool().add(SimpleContractModification)
        Pool().add(TestStartEndorsement, type='wizard')

        possible_views = [
            x[0] for x in self.EndorsementPart.get_possible_views()]
        self.assertEqual(set(possible_views), {'simple_contract_modification',
                'dummy_step', 'change_start_date', 'void_contract',
                'change_contract_extra_data', 'terminate_contract',
                'change_contract_subscriber', 'manage_options'})

    @test_framework.prepare_test(
        'endorsement.test0001_check_possible_views',
        )
    def test0010_create_contract_endorsement_part(self):
        endorsement_part = self.EndorsementPart()
        endorsement_part.name = 'Change contract number'
        endorsement_part.code = endorsement_part.on_change_with_code()
        endorsement_part.view = 'simple_contract_modification'
        endorsement_part.kind = 'contract'
        endorsement_part.contract_fields = [{
                'field': self.Field.search([
                        ('model.model', '=', 'contract'),
                        ('name', '=', 'contract_number')])[0]
                }]

        self.assertEqual(endorsement_part.code, 'change_contract_number')
        endorsement_part.save()

    @test_framework.prepare_test(
        'endorsement.test0010_create_contract_endorsement_part',
        'offered.test0030_testProductCoverageRelation',
        )
    def test0020_create_endorsement_definition(self):
        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ])
        endorsement_part, = self.EndorsementPart.search([
                ('code', '=', 'change_contract_number'),
                ])
        definition = self.EndorsementDefinition()
        definition.name = 'Change Contract Number'
        definition.code = definition.on_change_with_code()
        definition.ordered_endorsement_parts = [{
                'endorsement_part': endorsement_part.id,
                'order': 1,
                }]
        definition.products = [product.id]
        self.assertEqual(definition.code, 'change_contract_number')
        definition.save()
        self.assertEqual(list(definition.endorsement_parts),
            [endorsement_part])

    @test_framework.prepare_test(
        'endorsement.test0020_create_endorsement_definition',
        'contract.test0010_testContractCreation',
        )
    def test0030_create_endorsement(self):
        definition, = self.EndorsementDefinition.search([
                ('code', '=', 'change_contract_number'),
                ])
        contract, = self.Contract.search([
                ('product.code', '=', 'AAA'),
                ])
        effective_date = contract.start_date + datetime.timedelta(weeks=24)
        previous_contract_number = contract.contract_number
        endorsement = self.Endorsement(
            definition=definition,
            effective_date=effective_date,
            contract_endorsements=[{
                    'contract': contract.id,
                    'values': {
                        'contract_number': '1234',
                        },
                    }])
        endorsement.save()
        contract_endorsement, = endorsement.contract_endorsements
        self.assertEqual(endorsement.state, 'draft')
        self.assertEqual(contract_endorsement.state, 'draft')
        self.assertEqual(contract_endorsement.definition, definition)
        self.assertEqual(list(endorsement.contracts), [contract])
        self.assertEqual(contract.contract_number, previous_contract_number)
        self.assertEqual(contract_endorsement.apply_values(), {
                'contract_number': '1234',
                })

    @test_framework.prepare_test(
        'endorsement.test0030_create_endorsement',
        )
    def test0031_endorsement_summary(self):
        contract, = self.Contract.search([
                ('product.code', '=', 'AAA'),
                ])
        endorsement, = self.Endorsement.search([
                ('contracts', '=', contract.id),
                ])
        self.assertEqual(endorsement.endorsement_summary,
            u'\n  <u>Change Contract Number</u>\n\n'
            u'        Contract Number : %s →<b> 1234</b>\n' %
            contract.contract_number)

    @test_framework.prepare_test(
        'endorsement.test0030_create_endorsement',
        )
    def test0032_endorsement_decline(self):
        sub_state = self.SubState(name='Illegible', code='illegible',
                state='declined')
        sub_state.save()

        contract, = self.Contract.search([
                ('product.code', '=', 'AAA'),
                ])
        endorsement, = self.Endorsement.search([
                ('contracts', '=', contract.id),
                ])
        self.assertEqual(endorsement.state, 'draft')
        endorsement.decline([endorsement], reason=sub_state)
        self.assertEqual(endorsement.state, 'declined')
        endorsement.draft([endorsement])
        self.assertEqual(endorsement.state, 'draft')

    @test_framework.prepare_test(
        'endorsement.test0030_create_endorsement',
        )
    def test0035_revert_endorsement(self):
        # WARNING: No dependency, commit required for the history / write dates
        # to kick in properly
        Transaction().cursor.commit()

        contract, = self.Contract.search([
                ('product.code', '=', 'AAA'),
                ])
        endorsement, = self.Endorsement.search([
                ('contracts', '=', contract.id),
                ])
        previous_contract_number = contract.contract_number

        # Test preview data. Requires save to function properly
        contract_id = contract.id

        def extract_method(instance):
            return {'contract_number': instance.contract_number}

        self.assertEqual(endorsement.extract_preview_values(extract_method),
            {
                'old': {
                    'contract,%i' % contract_id: {
                        'contract_number': previous_contract_number,
                        }},
                'new': {
                    'contract,%i' % contract_id: {
                        'contract_number': u'1234',
                        }}})

        endorsement.in_progress([endorsement])
        Transaction().cursor.commit()

        contract = endorsement.contracts[0]
        self.assertEqual(contract.contract_number, previous_contract_number)
        contract.contract_number = 'in_progress'
        contract.save()
        Transaction().cursor.commit()

        contract = endorsement.contracts[0]
        contract_endorsement, = endorsement.contract_endorsements
        self.assert_(endorsement.rollback_date)
        self.assertEqual(endorsement.application_date, None)
        self.assertEqual(contract.contract_number, 'in_progress')
        endorsement.apply([endorsement])
        Transaction().cursor.commit()

        contract = endorsement.contracts[0]
        contract_endorsement, = endorsement.contract_endorsements
        self.assert_(endorsement.application_date)
        self.assertEqual(endorsement.state, 'applied')
        self.assertEqual(contract_endorsement.state, 'applied')
        self.assertEqual(contract.contract_number, '1234')
        self.assertEqual(contract_endorsement.base_instance.contract_number,
            previous_contract_number)
        endorsement.cancel([endorsement])
        Transaction().cursor.commit()

        endorsement = self.Endorsement(endorsement.id)
        contract = endorsement.contracts[0]
        self.assertEqual(endorsement.state, 'canceled')
        self.assertEqual(contract.contract_number, previous_contract_number)

        # Canceled state is final (no outgoing transition), force it to 'draft'
        # to keep on testing
        endorsement.state = 'draft'
        endorsement.save()
        Transaction().cursor.commit()

        self.assertEqual(endorsement.rollback_date, None)
        endorsement.in_progress([endorsement])
        Transaction().cursor.commit()
        contract = endorsement.contracts[0]
        contract.apply_in_progress_endorsement([contract])
        Transaction().cursor.commit()

        self.assertEqual(endorsement.state, 'applied')
        self.assertRaises(UserError, contract.apply_in_progress_endorsement,
            [contract])
        endorsement.cancel([endorsement])
        Transaction().cursor.commit()

        endorsement.state = 'draft'
        endorsement.save()
        endorsement.in_progress([endorsement])
        Transaction().cursor.commit()

        contract.revert_current_endorsement([contract])

        # revert_current_endorsement deletes the current "in_progress"
        # endorsement
        self.assertEqual([], self.Endorsement.search([
                    ('contracts', '=', contract.id),
                    ]))

    def test0099_test_automatic_endorsement(self):
        from trytond.modules.endorsement import EndorsementWizardStepMixin

        _save_values = {
            'company': 1,
            'contract_number': '1234',
            'options': [
                ('add', (10, 11)),
                ('delete', (15, 12)),
                ('create', ({
                            'coverage': 1,
                            }, {
                            'coverage': 2,
                            })),
                ('write', [1, 2], {
                        'coverage': 100})]}

        test_endorsement = self.EndorsementContract()
        EndorsementWizardStepMixin._update_endorsement(test_endorsement,
            _save_values)
        self.assertEqual(test_endorsement.values, {'company': 1,
                'contract_number': '1234'})
        self.assertEqual(len(test_endorsement.options), 8)

        def test_value(endorsement, action, relation, values):
            self.assertEqual(endorsement.__name__,
                'endorsement.contract.option')
            self.assertEqual(endorsement.action, action)
            if relation:
                self.assertEqual(endorsement.relation, relation)
            else:
                self.assertIsNone(getattr(endorsement, 'relation', None))
            if values:
                self.assertEqual(endorsement.values, values)
            else:
                self.assertIsNone(getattr(endorsement, 'values', None))

        for idx, (action, relation, values) in enumerate([
                    ('add', 10, None),
                    ('add', 11, None),
                    ('remove', 15, None),
                    ('remove', 12, None),
                    ('add', None, {'coverage': 1}),
                    ('add', None, {'coverage': 2}),
                    ('update', 1, {'coverage': 100}),
                    ('update', 2, {'coverage': 100}),
                    ]):
            test_value(test_endorsement.options[idx], action, relation,
                values)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_endorsement_change_start_date.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_endorsement_change_extra_data.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
