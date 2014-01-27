import unittest
import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'company_cog'

    @classmethod
    def depending_modules(cls):
        return ['currency_cog']

    @classmethod
    def get_models(cls):
        return {
            'User': 'res.user',
            'Party': 'party.party',
            'Company': 'company.company',
            }

    @test_framework.prepare_test('currency_cog.test0001_testCurrencyCreation')
    def test0001_testCompanyCreation(self):
        test_party = self.Party()
        test_party.name = 'World Company'
        test_party.save()

        company = self.Company()
        company.party = test_party
        company.currency = self.Currency.search([('code', '=', 'EUR')])[0]
        company.save()

        user = self.User(Transaction().user)
        user.main_company = company
        user.companies = [company]
        user.save()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
