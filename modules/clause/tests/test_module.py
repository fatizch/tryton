import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    @classmethod
    def get_models(cls):
        return {
            'Clause': 'clause',
            'ClauseVersion': 'clause.version',
            }

    @classmethod
    def get_module_name(cls):
        return 'clause'

    def test0001_testClauseCreation(self):
        # Clause
        clause = self.Clause()
        clause.name = 'Test Clause'
        clause.code = clause.on_change_with_code()
        self.assertEqual(clause.code, 'test_clause')
        clause.kind = ''
        clause.title = 'Title of the test clause'
        clause.save()

        # Clause Version
        version = self.ClauseVersion()
        version.content = 'Clause content testing'
        version.start_date = datetime.date(2013, 2, 3)
        version.save()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
