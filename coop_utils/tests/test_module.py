import sys
import os
import unittest
DIR = os.path.abspath(os.path.normpath(os.path.join(
    __file__, '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import trytond.tests.test_tryton

from trytond.modules.coop_utils import test_framework
from trytond.modules.coop_utils import utils

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

    def test0020get_module_path(self):
        self.assert_(utils.get_module_path(MODULE_NAME))
        self.assert_(utils.get_module_path('coop_party'))
        self.assert_(utils.get_module_path('dfsfsfsdf') is None)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
