#-*- coding:utf-8 -*-
import datetime
import unittest
from decimal import Decimal

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
        return ['offered_insurance']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'ExtraPremium': 'contract.option.extra_premium',
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

    @test_framework.prepare_test(
         'offered_insurance.test0100_testExtraPremiumKindCreation',
    )
    def test0010_testExtraPremiumRateCalculate(self):
        extra_premium = self.ExtraPremium()
        extra_premium.calculation_kind = 'rate'
        extra_premium.rate = Decimal('-0.05')
        extra_premium_kind, = self.ExtraPremiumKind.search([
            ('code', '=', 'reduc_no_limit'), ])
        extra_premium.motive = extra_premium_kind

        result = extra_premium.calculate_premium_amount(None, base=100)
        self.assertEqual(result, Decimal('-5.0'))

    @test_framework.prepare_test(
         'offered_insurance.test0100_testExtraPremiumKindCreation',
    )
    def test0011_testExtraPremiumAmountCalculate(self):
        extra_premium = self.ExtraPremium()
        extra_premium.calculation_kind = 'flat'
        extra_premium.flat_amount = Decimal('100')
        extra_premium_kind, = self.ExtraPremiumKind.search([
            ('code', '=', 'reduc_no_limit'), ])
        extra_premium.motive = extra_premium_kind

        result = extra_premium.calculate_premium_amount(None, base=100)
        self.assertEqual(result, Decimal('100'))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
