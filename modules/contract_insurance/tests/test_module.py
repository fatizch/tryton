#-*- coding:utf-8 -*-
import datetime
import unittest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'contract_insurance'

    @classmethod
    def depending_modules(cls):
        return ['contract_life', 'offered_insurance', 'billing']

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
        party.name = 'DOE'
        party.first_name = 'John'
        party.birth_date = datetime.date(1980, 5, 30)
        party.gender = 'male'
        party.save()

        party, = self.Party.search([('name', '=', 'DOE')])
        self.assert_(party.id)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
