#-*- coding:utf-8 -*-
import sys
import os
from decimal import Decimal
import datetime
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.modules.insurance_product import PricingResultLine


MODULE_NAME = os.path.basename(
                  os.path.abspath(
                      os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(unittest.TestCase):
    '''
    Test Coop module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('life_product')
        self.Product = POOL.get('ins_product.product')
        self.coverage = POOL.get('ins_product.coverage')
        self.brm = POOL.get('ins_product.business_rule_manager')
        self.gbr = POOL.get('ins_product.generic_business_rule')
        self.pricing = POOL.get('ins_product.pricing_rule')
        self.currency = POOL.get('currency.currency')
        self.eligibility = POOL.get('ins_product.eligibility_rule')
        self.TreeElement = POOL.get('rule_engine.tree_element')
        self.Context = POOL.get('rule_engine.context')
        self.RuleEngine = POOL.get('rule_engine')
        self.TestCase = POOL.get('rule_engine.test_case')
        self.TestCaseValue = POOL.get('rule_engine.test_case.value')
        self.RunTests = POOL.get('rule_engine.run_tests', type='wizard')
        self.PricingData = POOL.get('ins_product.pricing_data')
        self.Calculator = POOL.get('ins_product.pricing_calculator')
        self.Tax = POOL.get('coop_account.tax_desc')
        self.TaxVersion = POOL.get('coop_account.tax_version')
        self.Fee = POOL.get('coop_account.fee_desc')
        self.FeeVersion = POOL.get('coop_account.fee_version')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view(MODULE_NAME)

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def createTestRule(self):
        te1 = self.TreeElement()
        te1.type = 'function'
        te1.name = 'get_subscriber_name'
        te1.description = 'Name'
        te1.namespace = 'ins_product.rule_sets.subscriber'

        te1.save()

        te2 = self.TreeElement()
        te2.type = 'function'
        te2.name = 'get_subscriber_birthdate'
        te2.description = 'Birthday'
        te2.namespace = 'ins_product.rule_sets.subscriber'

        te2.save()

        te = self.TreeElement()
        te.type = 'folder'
        te.description = 'Subscriber'
        te.children = [te1, te2]

        te.save()

        te3 = self.TreeElement()
        te3.type = 'function'
        te3.name = 'years_between'
        te3.description = 'Years between'
        te3.namespace = 'rule_engine.tools_functions'

        te3.save()

        te5 = self.TreeElement()
        te5.type = 'function'
        te5.name = 'today'
        te5.description = 'Today'
        te5.namespace = 'rule_engine.tools_functions'

        te5.save()

        te6 = self.TreeElement()
        te6.type = 'function'
        te6.name = 'message'
        te6.description = 'Add message'
        te6.namespace = 'rule_engine.tools_functions'

        te6.save()

        te4 = self.TreeElement()
        te4.type = 'folder'
        te4.description = 'Tools'
        te4.children = [te3, te5, te6]

        te4.save()

        ct = self.Context()
        ct.name = 'test_context'
        ct.allowed_elements = []
        ct.allowed_elements.append(te)
        ct.allowed_elements.append(te4)

        ct.save()

        rule = self.RuleEngine()
        rule.name = 'test_rule'
        rule.context = ct
        rule.code = '''
birthdate = get_subscriber_birthdate()
if years_between(birthdate, today()) > 40:
    message('Subscriber too old (max: 40)')
    return False
return True'''

        tcv = self.TestCaseValue()
        tcv.name = 'get_subscriber_birthdate'
        tcv.value = 'datetime.date(2000, 11, 02)'

        tc = self.TestCase()
        tc.description = 'Test'
        tc.values = [tcv]
        tc.expected_result = '(True, [], [])'

        tcv1 = self.TestCaseValue()
        tcv1.name = 'get_subscriber_birthdate'
        tcv1.value = 'datetime.date(1950, 11, 02)'

        tc1 = self.TestCase()
        tc1.description = 'Test1'
        tc1.values = [tcv1]
        tc1.expected_result = '(False, ["Subscriber too old (max: 40)"], [])'

        rule.test_cases = [tc, tc1]

        rule.save()

        return rule

    def create_tax(self, code, amount):
        tax_v1 = self.TaxVersion()
        tax_v1.kind = 'rate'
        tax_v1.value = Decimal(amount)
        tax_v1.start_date = datetime.date.today()

        tax = self.Tax()
        tax.name = 'Test Tax %s' % code
        tax.code = code
        tax.versions = [tax_v1]

        tax.save()

        return tax

    def create_fee(self, code, amount):
        fee_v1 = self.FeeVersion()
        fee_v1.kind = 'flat'
        fee_v1.value = Decimal(amount)
        fee_v1.start_date = datetime.date.today()

        fee = self.Fee()
        fee.name = 'Test Fee %s' % code
        fee.code = code
        fee.versions = [fee_v1]

        fee.save()

        return fee

    def test0010Coverage_creation(self):
        '''
            Tests process desc creation
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:

            rule = self.createTestRule()
            with transaction.set_context({'active_id': rule.id}):
                wizard_id, _, _ = self.RunTests.create()
                wizard = self.RunTests(wizard_id)
                wizard._execute('report')
                res = wizard.default_report(None)
                self.assertEqual(
                    res,
                    {'report': 'Test ... SUCCESS\n\nTest1 ... SUCCESS'})

            #We need to create the currency manually because it's needed
            #on the default currency for product and coverage
            euro = self.currency()
            euro.name = 'Euro'
            euro.symbol = u'€'
            euro.code = 'EUR'
            euro.save()

            # Coverage A

            tax = self.create_tax('TT', 13)
            fee = self.create_fee('FEE', 20)

            pr_data1 = self.PricingData()
            pr_data1.config_kind = 'simple'
            pr_data1.fixed_amount = 12
            pr_data1.kind = 'base'
            pr_data1.code = 'PP'

            pr_data11 = self.PricingData()
            pr_data11.kind = 'tax'
            pr_data11.the_tax = tax

            pr_data12 = self.PricingData()
            pr_data12.kind = 'fee'
            pr_data12.the_fee = fee

            pr_calc1 = self.Calculator()
            pr_calc1.data = [pr_data1, pr_data11, pr_data12]
            pr_calc1.key = 'price'

            pr_data2 = self.PricingData()
            pr_data2.config_kind = 'simple'
            pr_data2.fixed_amount = 1
            pr_data2.kind = 'base'
            pr_data2.code = 'PP'

            pr_calc2 = self.Calculator()
            pr_calc2.data = [pr_data2]
            pr_calc2.key = 'sub_price'

            prm_a = self.pricing()

            prm_a.calculators = [pr_calc1, pr_calc2]

            gbr_a = self.gbr()
            gbr_a.kind = 'ins_product.pricing_rule'
            gbr_a.start_date = datetime.date.today()
            gbr_a.end_date = datetime.date.today() + \
                                            datetime.timedelta(days=10)
            gbr_a.pricing_rule = [prm_a]

            pr_data3 = self.PricingData()
            pr_data3.config_kind = 'simple'
            pr_data3.fixed_amount = 15
            pr_data3.kind = 'base'
            pr_data3.code = 'PP'

            pr_calc3 = self.Calculator()
            pr_calc3.data = [pr_data3]
            pr_calc3.key = 'price'

            prm_b = self.pricing()
            prm_b.calculators = [pr_calc3]

            gbr_b = self.gbr()
            gbr_b.kind = 'ins_product.pricing_rule'
            gbr_b.start_date = datetime.date.today() + \
                                            datetime.timedelta(days=11)
            gbr_b.end_date = datetime.date.today() + \
                                            datetime.timedelta(days=20)
            gbr_b.pricing_rule = [prm_b]

            brm_a = self.brm()
            brm_a.business_rules = [gbr_a, gbr_b]

            coverage_a = self.coverage()
            coverage_a.family = coverage_a._fields['family'].selection[0][0]
            coverage_a.code = 'ALP'
            coverage_a.name = 'Alpha Coverage'
            coverage_a.start_date = datetime.date.today()

            coverage_a.pricing_mgr = [brm_a]

            coverage_a.save()

            # Coverage B

            tax_1 = self.create_tax('TTA', 27)

            pr_data4 = self.PricingData()
            pr_data4.config_kind = 'simple'
            pr_data4.fixed_amount = 30
            pr_data4.kind = 'base'
            pr_data4.code = 'PP'

            pr_data41 = self.PricingData()
            pr_data41.kind = 'tax'
            pr_data41.the_tax = tax_1

            pr_calc4 = self.Calculator()
            pr_calc4.data = [pr_data4, pr_data41]
            pr_calc4.key = 'price'

            prm_c = self.pricing()
            prm_c.config_kind = 'simple'
            prm_c.calculators = [pr_calc4]

            gbr_c = self.gbr()
            gbr_c.kind = 'ins_product.pricing_rule'
            gbr_c.start_date = datetime.date.today()
            gbr_c.end_date = datetime.date.today() + \
                                            datetime.timedelta(days=10)
            gbr_c.pricing_rule = [prm_c]

            brm_b = self.brm()
            brm_b.business_rules = [gbr_c]

            coverage_b = self.coverage()
            coverage_b.code = 'BET'
            coverage_b.name = 'Beta Coverage'
            coverage_b.family = coverage_a._fields['family'].selection[0][0]
            coverage_b.start_date = datetime.date.today() + \
                                            datetime.timedelta(days=5)

            coverage_b.pricing_mgr = [brm_b]

            coverage_b.save()

            # Coverage C

            erm_a = self.eligibility()
            erm_a.config_kind = 'rule'
            erm_a.is_eligible = False
            erm_a.rule = rule

            gbr_d = self.gbr()
            gbr_d.kind = 'ins_product.eligibility_rule'
            gbr_d.start_date = datetime.date.today()
            gbr_d.eligibility_rule = [erm_a]

            brm_c = self.brm()
            brm_c.business_rules = [gbr_d]

            coverage_c = self.coverage()
            coverage_c.code = 'GAM'
            coverage_c.name = 'Gamma Coverage'
            coverage_c.family = coverage_a._fields['family'].selection[0][0]
            coverage_c.start_date = datetime.date.today()

            coverage_c.eligibility_mgr = [brm_c]

            coverage_c.save()

            # Coverage D

            erm_d = self.eligibility()
            erm_d.config_kind = 'simple'
            erm_d.is_eligible = True
            erm_d.is_sub_elem_eligible = False

            gbr_g = self.gbr()
            gbr_g.kind = 'ins_product.eligibility_rule'
            gbr_g.start_date = datetime.date.today()
            gbr_g.eligibility_rule = [erm_d]

            brm_f = self.brm()
            brm_f.business_rules = [gbr_g]

            coverage_d = self.coverage()
            coverage_d.code = 'DEL'
            coverage_d.name = 'Delta Coverage'
            coverage_d.family = coverage_a._fields['family'].selection[0][0]
            coverage_d.start_date = datetime.date.today()

            coverage_d.eligibility_mgr = [brm_f]

            coverage_d.save()

            # Product Eligibility Manager

            erm_b = self.eligibility()
            erm_b.config_kind = 'simple'
            erm_b.is_eligible = True

            gbr_e = self.gbr()
            gbr_e.kind = 'ins_product.eligibility_rule'
            gbr_e.start_date = datetime.date.today()
            gbr_e.eligibility_rule = [erm_b]

            brm_d = self.brm()
            brm_d.business_rules = [gbr_e]

            # Product

            product_a = self.Product()
            product_a.code = 'AAA'
            product_a.name = 'Awesome Alternative Allowance'
            product_a.start_date = datetime.date.today()
            product_a.options = [
                coverage_a, coverage_b, coverage_c, coverage_d]
            product_a.eligibility_mgr = [brm_d]
            product_a.save()

            self.assert_(product_a.id)

            transaction.cursor.commit()

    def test0020Pricing_Line_Results(self):
        '''
            Tests pricing lines
        '''
        p1 = PricingResultLine(value=10, name='Alpha', desc=[])
        p2 = PricingResultLine(value=30, name='Beta', desc=[])

        p_add = p1 + p2

        self.assertEqual(p_add.value, 40)
        self.assertEqual(p_add.name, '')
        self.assertEqual(len(p_add.desc), 2)
        self.assertEqual(p_add.desc, [p1, p2])

        p1 += p2

        self.assertEqual(p1.value, 40)
        self.assertEqual(p1.name, 'Alpha')
        self.assertEqual(len(p1.desc), 1)

        sub_p = p1.desc[0]

        self.assertEqual(sub_p.value, p2.value)
        self.assertEqual(sub_p.name, p2.name)
        self.assertEqual(sub_p.desc, p2.desc)

        self.assertEqual(sub_p, p2)

        p1 += p2


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
