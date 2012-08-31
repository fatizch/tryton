# Needed for python test management
import unittest

# Needed for tryton test integration
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.modules.coop_utils import utils


class LaboratoryTestCase(unittest.TestCase):
    def setUp(self):
        trytond.tests.test_tryton.install_module('coop_utils')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('coop_utils')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0020get_module_path(self):
        self.assert_(utils.get_module_path('coop_utils'))
        self.assert_(utils.get_module_path('coop_party'))
        self.assert_(utils.get_module_path('dfsfsfsdf') is None)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        LaboratoryTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
