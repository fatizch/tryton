import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(
    __file__, '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton

from trytond.modules.coop_utils import test_framework

MODULE_NAME = os.path.basename(
    os.path.abspath(
        os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''

    @classmethod
    def get_module_name(cls):
        return MODULE_NAME

    @classmethod
    def depending_modules(cls):
        return ['insurance_product']

    @test_framework.prepare_test(
        'insurance_product.test0010Coverage_creation',
    )
    def test0010_LifeProductCreation(self):
        coverages = self.Coverage.search([
            ('code', 'in', ['ALP', 'BET', 'GAM', 'DEL'])])
        self.Coverage.write(coverages, {'family': 'life_product.definition'})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
