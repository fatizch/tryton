# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_group'

    @classmethod
    def fetch_models_for(cls):
        return ['contract_insurance']

    @test_framework.prepare_test(
        'contract_insurance.test0050_testOveralppingCoveredElements'
        )
    def test0050_testOveralppingCoveredElements_group(self):
        pass


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
