import unittest

import trytond.tests.test_tryton

from trytond.modules.coop_utils import test_framework
from trytond.modules.coop_utils import utils


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'coop_utils'

    def test0020get_module_path(self):
        self.assert_(utils.get_module_path('coop_utils'))
        self.assert_(utils.get_module_path('dfsfsfsdf') is None)

    def test9999_launch_test_cases(self):
        # We do not want to import the json test file
        pass


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
