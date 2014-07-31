import unittest
import datetime

import trytond.tests.test_tryton
from trytond.transaction import Transaction

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'endorsement'

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
            }

    @classmethod
    def depending_modules(cls):
        return ['offered', 'contract']

    def test0001_check_possible_views(self):
        from trytond.pool import Pool
        from trytond.wizard import StateView
        from trytond.modules.cog_utils import model
        from trytond.modules.endorsement import EndorsementWizardStepMixin
        from trytond.modules.endorsement.wizard import StartEndorsement

        class SimpleContractModification(model.CoopView,
                EndorsementWizardStepMixin):
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
        self.assertEqual(possible_views, ['simple_contract_modification'])

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
                ('start_date', '=', datetime.date(2014, 2, 15)),
                ])
        effective_date = datetime.date(2014, 8, 10)
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
        self.assertEqual(contract_endorsement.apply_values, {
                'contract_number': '1234',
                })

    @test_framework.prepare_test(
        'endorsement.test0030_create_endorsement',
        )
    def test0031_apply_endorsement(self):
        # WARNING: No dependency, commit required for the history / write dates
        # to kick in properly
        Transaction().cursor.commit()

        contract, = self.Contract.search([
                ('product.code', '=', 'AAA'),
                ('start_date', '=', datetime.date(2014, 2, 15)),
                ])
        endorsement, = self.Endorsement.search([
                ('contracts', '=', contract.id),
                ])
        previous_contract_number = contract.contract_number

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

        endorsement.draft([endorsement])
        Transaction().cursor.commit()
        contract = endorsement.contracts[0]
        self.assertEqual(contract_endorsement.applied_on, None)
        self.assertEqual(contract_endorsement.state, 'draft')
        self.assertEqual(contract.contract_number, previous_contract_number)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
