# encoding: utf-8
import unittest
import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'currency_cog'

    @classmethod
    def get_models(cls):
        return {
            'Currency': 'currency.currency',
            }

    def test0001_testCurrencyCreation(self):
        euro = self.Currency()
        euro.name = 'Euro'
        euro.symbol = u'€'
        euro.code = 'EUR'
        euro.save()
        self.assert_(euro.id)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
