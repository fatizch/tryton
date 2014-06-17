import datetime
import unittest

from decimal import Decimal

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(unittest.TestCase):
    '''
    Test Billing module.
    '''
    pass


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
