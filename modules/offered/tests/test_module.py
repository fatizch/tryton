#-*- coding:utf-8 -*-
import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton

from trytond.transaction import Transaction

from trytond.modules.coop_utils import test_framework

MODULE_NAME = os.path.basename(
    os.path.abspath(
        os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Offered Module
    '''

    @classmethod
    def get_module_name(cls):
        return MODULE_NAME

    @classmethod
    def get_models(cls):
        return {
            'User': 'res.user',
            'Currency': 'currency.currency',
            'Company': 'company.company',
            'Party': 'party.party',
        }

    def test0001_testCurrencyCreation(self):
        euro = self.Currency()
        euro.name = 'Euro'
        euro.symbol = u'€'
        euro.code = 'EUR'
        euro.save()
        self.assert_(euro.id)

    @test_framework.prepare_test('offered.test0001_testCurrencyCreation')
    def test0002_testCompanyCreation(self):
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
