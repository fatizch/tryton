import datetime

# Needed for python test management
import unittest

# Needed for tryton test integration
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.modules.coop_utils import PricingResultLine
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

    def test0010Pricing_Line_Results(self):
        '''
            Tests pricing lines
        '''
        p1 = PricingResultLine(value=10, name='Alpha', desc=[])
        p2 = PricingResultLine(value=30, name='Beta', desc=[])

        p_add = p1 + p2

        self.assertEqual(p_add.value, 40)
        self.assertEqual(p_add.name, '')
        self.assertEqual(len(p_add.desc), 2)
        self.assertEqual(p_add.desc, [p1, p2])

        p1 += p2

        self.assertEqual(p1.value, 40)
        self.assertEqual(p1.name, 'Alpha')
        self.assertEqual(len(p1.desc), 1)

        sub_p = p1.desc[0]

        self.assertEqual(sub_p.value, p2.value)
        self.assertEqual(sub_p.name, p2.name)
        self.assertEqual(sub_p.desc, p2.desc)

        self.assertEqual(sub_p, p2)

        p1 += p2

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
