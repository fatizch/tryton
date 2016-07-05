# -*- coding:utf-8 -*-
import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''

    module = 'offered_cash_value'


def suite():
    suite = trytond.tests.test_tryton.suite()
    # suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
