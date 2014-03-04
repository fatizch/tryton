import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    @classmethod
    def depending_modules(cls):
        return ['clause']

    @classmethod
    def get_module_name(cls):
        return 'clause_life'

    def test0001_testBeneficiaryClauseCreation(self):
        # Clause Version
        version = self.ClauseVersion()
        version.content = 'Clause content testing'
        version.start_date = datetime.date(2013, 2, 3)

        # Clause
        clause = self.Clause()
        clause.name = 'Test beneficiary Clause'
        clause.code = clause.on_change_with_code()
        clause.with_beneficiary_list = True
        self.assertEqual(clause.code, 'test_beneficiary_clause')
        clause.kind = 'beneficiary'
        clause.versions = [version]
        clause.save()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
