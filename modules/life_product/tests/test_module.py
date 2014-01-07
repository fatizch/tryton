import unittest

import trytond.tests.test_tryton

from trytond.modules.coop_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'life_product'

    @classmethod
    def depending_modules(cls):
        return ['insurance_product']

    @test_framework.prepare_test(
        'insurance_product.test0010Coverage_creation',
    )
    def test0010_LifeProductCreation(self):
        coverages = self.OptionDescription.search([
            ('code', 'in', ['ALP', 'BET', 'GAM', 'DEL'])])
        self.OptionDescription.write(coverages, {
                'family': 'life_product.definition'})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
