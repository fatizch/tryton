#-*- coding:utf-8 -*-
import datetime
import unittest
from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton

from trytond.modules.coop_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'insurance_contract'

    @classmethod
    def depending_modules(cls):
        return ['life_contract', 'insurance_product', 'billing']

    @classmethod
    def get_models(cls):
        return {
            'Contract': 'contract',
            'Party': 'party.party',
            'Sequence': 'ir.sequence',
            # 'BillingProcess': 'contract.do_billing',
        }

    def test0001_testPersonCreation(self):
        party = self.Party()
        party.is_person = True
        party.name = 'Toto'
        party.first_name = 'titi'
        party.birth_date = datetime.date.today() + relativedelta(years=-39)
        party.gender = 'male'
        party.save()

        party, = self.Party.search([('name', '=', 'Toto')])
        self.assert_(party.id)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
