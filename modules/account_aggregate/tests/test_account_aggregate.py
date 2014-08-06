import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends


class AccountAggregateTestCase(unittest.TestCase):
    'Test Account Aggregate module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('account_aggregate')

    def test0005views(self):
        'Test views'
        test_view('account')

    def test0006depends(self):
        'Test depends'
        test_depends()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountAggregateTestCase))
    return suite
