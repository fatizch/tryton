# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    @classmethod
    def depending_modules(cls):
        return ['clause']

    module = 'offered_life_clause'

    def test0001_testBeneficiaryClauseCreation(self):
        # Clause
        clause = self.Clause()
        clause.name = 'Test beneficiary Clause'
        clause.code = clause.on_change_with_code()
        self.assertEqual(clause.code, 'test_beneficiary_clause')
        clause.kind = 'beneficiary'
        clause.content = 'Clause content testing'
        clause.save()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
