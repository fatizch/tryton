import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends


class AccountStatementContractFR(unittest.TestCase):
    'Test Account Statement Contract FR module'

    def setUp(self):
        trytond.tests.test_tryton.install_module(
            'account_statement_contract_fr')

    def test0005views(self):
        'Test views'
        test_view('account_statement_contract_fr')

    def test0006depends(self):
        'Test depends'
        test_depends()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountStatementContractFR))
    return suite
