import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'contract'

    @classmethod
    def depending_modules(cls):
        return ['offered']

    @classmethod
    def get_models(cls):
        return {
            'Contract': 'contract',
            'Option': 'contract.option',
            'ActivationHistory': 'contract.activation_history',
            }

    @test_framework.prepare_test(
        'offered.test0030_testProductCoverageRelation',
        )
    def test0010_testContractCreation(self):
        product, = self.Product.search([
                ('code', '=', 'AAA'),
            ])
        start_date = datetime.date(2014, 2, 15)
        end_date = datetime.date(2015, 2, 14)
        contract = self.Contract(
            product=product.id,
            company=product.company.id,
            activation_history=[{
                    'start_date': start_date,
                    }],
            appliable_conditions_date=start_date,
            )
        contract.save()
        self.assertEqual(contract.status, 'quote')
        self.assertEqual(contract.start_date, start_date)
        contract.set_end_date(end_date)
        contract.save()
        self.assertEqual(contract.end_date, end_date)
        self.assertEqual(contract.start_date, start_date)
        self.assertEqual(len(contract.activation_history), 1)
        self.assertEqual(contract.activation_history[0].end_date, end_date)
        contract.finalize_contract()
        contract.activate_contract()
        contract.save()
        self.assertEqual(contract.status, 'active')
        self.assert_(contract.contract_number)
        self.assertEqual(contract.start_date, start_date)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
