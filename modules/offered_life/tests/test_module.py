# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'offered_life'

    @classmethod
    def depending_modules(cls):
        return ['offered_insurance']

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
    )
    def test0010_LifeProductCreation(self):
        coverages = self.OptionDescription.search([
            ('code', 'in', ['ALP', 'BET', 'GAM', 'DEL'])])
        self.OptionDescription.write(coverages, {
                'family': 'life'})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
