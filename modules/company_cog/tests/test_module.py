# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'company_cog'

    @classmethod
    def fetch_models_for(cls):
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
        pool = Pool()
        Party = pool.get('party.party')
        User = pool.get('res.user')
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        Language = pool.get('ir.lang')

        test_party = Party()
        test_party.name = 'World Company'
        test_party.save()

        company = Company()
        company.party = test_party
        company.currency, = Currency.search([('code', '=', 'EUR')])
        company.save()

        user = User(Transaction().user)
        user.main_company = company
        user.companies = [company]
        user.save()

        test_party = Party(test_party.id)
        test_party.lang, = Language.search([('code', '=', 'fr')])
        test_party.save()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
