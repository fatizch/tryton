# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    'Test Account Statement Contract FR module'

    module = 'account_statement_contract_fr'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
