import unittest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    @classmethod
    def depending_modules(cls):
        return ['clause']

    @classmethod
    def get_module_name(cls):
        return 'offered_life_clause'

    def test0001_testBeneficiaryClauseCreation(self):
        # Clause
        clause = self.Clause()
        clause.name = 'Test beneficiary Clause'
        clause.code = clause.on_change_with_code()
        self.assertEqual(clause.code, 'test_beneficiary_clause')
        clause.kind = 'beneficiary'
        clause.content = 'Clause content testing'
        clause.save()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
