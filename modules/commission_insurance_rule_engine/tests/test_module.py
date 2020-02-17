# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'commission_insurance_rule_engine'

    @classmethod
    def fetch_models_for(cls):
        return ['contract_distribution', 'contract_insurance_invoice',
            'bank_cog', 'country_cog']

    @test_framework.prepare_test(
        'commission_insurance.test0004_create_commission_agents',
        )
    def test0005_use_rule_engine(self):
        pool = Pool()
        Plan = pool.get('commission.plan')
        Rule = pool.get('rule_engine')

        custom_rule, = Rule.search([('short_name', '=',
                    'commission_lineaire_avec_personnalisation')])
        wonder_plan, = Plan.search([('code', '=', 'wonder_plan')])

        wonder_plan.lines[0].use_rule_engine = True
        wonder_plan.lines[0].rule = custom_rule
        wonder_plan.lines[0].rule_extra_data = {
            'taux_par_defaut': Decimal('20'),
            }
        wonder_plan.lines[0].save()

    @test_framework.prepare_test(
        'commission_insurance.test0005_set_commercial_products',
        'commission_insurance_rule_engine.test0005_use_rule_engine',
        'commission_insurance.test0015_subscribe_contract',
        )
    def test0015_subscribe_contract(self):
        # What we want to check is that swapping to a rule for customized
        # commissions works the same way as the corresponding formula do
        pass


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModuleTestCase))
    return suite
