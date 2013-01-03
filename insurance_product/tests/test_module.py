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
        self.Coverage = POOL.get('ins_product.coverage')
        self.Pricing = POOL.get('ins_product.pricing_rule')
        self.Currency = POOL.get('currency.currency')
        self.Eligibility = POOL.get('ins_product.eligibility_rule')
        self.TreeElement = POOL.get('rule_engine.tree_element')
        self.Context = POOL.get('rule_engine.context')
        self.RuleEngine = POOL.get('rule_engine')
        self.TestCase = POOL.get('rule_engine.test_case')
        self.TestCaseValue = POOL.get('rule_engine.test_case.value')
        self.RunTests = POOL.get('rule_engine.run_tests', type='wizard')
        self.PricingComponent = POOL.get('ins_product.pricing_component')
        self.Tax = POOL.get('coop_account.tax_desc')
        self.TaxVersion = POOL.get('coop_account.tax_version')
        self.Fee = POOL.get('coop_account.fee_desc')
        self.FeeVersion = POOL.get('coop_account.fee_version')
        self.Sequence = POOL.get('ir.sequence')

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
        Lang = POOL.get('ir.lang')
        fr = Lang.search([('name', '=', 'French')], limit=1)[0]

        te2 = self.TreeElement()
        te2.language = fr
        te2.type = 'function'
        te2.name = '_re_get_subscriber_birthdate'
        te2.translated_technical_name = 'date_de_naissance_souscripteur'
        te2.description = 'Date de naissance du Souscripteur'
        te2.namespace = 'ins_product.rule_sets.subscriber'

        te2.save()

        te8 = self.TreeElement()
        te8.language = fr
        te8.type = 'folder'
        te8.translated_technical_name = 'Dossier Souscripteur'
        te8.description = 'Souscripteur'
        te8.children = [te2]

        te8.save()

        te3 = self.TreeElement()
        te3.language = fr
        te3.type = 'function'
        te3.name = '_re_years_between'
        te3.translated_technical_name = 'annees_entre'
        te3.description = 'Années entre...'
        te3.namespace = 'rule_engine.tools_functions'

        te3.save()

        te5 = self.TreeElement()
        te5.language = fr
        te5.type = 'function'
        te5.translated_technical_name = 'aujourd_hui'
        te5.name = '_re_today'
        te5.description = "Aujourd'hui"
        te5.namespace = 'rule_engine.tools_functions'

        te5.save()

        te6 = self.TreeElement()
        te6.language = fr
        te6.type = 'function'
        te6.name = '_re_message'
        te6.translated_technical_name = 'ajouter_message'
        te6.description = 'Ajouter message'
        te6.namespace = 'rule_engine.tools_functions'

        te6.save()

        te4 = self.TreeElement()
        te4.language = fr
        te4.type = 'folder'
        te4.translated_technical_name = 'Dossier Outils'
        te4.description = 'Outils'
        te4.children = [te3, te5, te6]

        te4.save()

        ct = self.Context()
        ct.name = 'test_context'
        ct.allowed_elements = []
        ct.allowed_elements.append(te8)
        ct.allowed_elements.append(te4)

        ct.save()

        rule = self.RuleEngine()
        rule.name = 'test_rule'
        rule.context = ct
        rule.code = '''
birthdate = date_de_naissance_souscripteur()
if annees_entre(birthdate, aujourd_hui()) > 40.0:
    ajouter_message('Subscriber too old (max: 40)')
    return False
return True'''

        tcv = self.TestCaseValue()
        tcv.name = 'date_de_naissance_souscripteur'
        tcv.value = 'datetime.date(2000, 11, 02)'

        tc = self.TestCase()
        tc.description = 'Test'
        tc.values = [tcv]
        tc.expected_result = '(True, [], [])'

        tcv1 = self.TestCaseValue()
        tcv1.name = 'date_de_naissance_souscripteur'
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

    def create_number_generator(self, code):
        ng = self.Sequence()
        ng.name = 'Contract Sequence'
        ng.code = code
        ng.prefix = 'Ctr'
        ng.suffix = 'Y${year}'
        ng.save()
        return ng

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

            ng = self.create_number_generator('ins_product.product')

            #We need to create the currency manually because it's needed
            #on the default currency for product and coverage
            euro = self.Currency()
            euro.name = 'Euro'
            euro.symbol = u'€'
            euro.code = 'EUR'
            euro.save()

            # Coverage A

            tax = self.create_tax('TT', 13)
            fee = self.create_fee('FEE', 20)

            pricing_comp1 = self.PricingComponent()
            pricing_comp1.config_kind = 'simple'
            pricing_comp1.fixed_amount = 12
            pricing_comp1.kind = 'base'
            pricing_comp1.code = 'PP'
            pricing_comp1.rated_object_kind = 'global'

            pricing_comp11 = self.PricingComponent()
            pricing_comp11.kind = 'tax'
            pricing_comp11.tax = tax
            pricing_comp11.code = tax.code
            pricing_comp11.rated_object_kind = 'global'

            pricing_comp12 = self.PricingComponent()
            pricing_comp12.kind = 'fee'
            pricing_comp12.fee = fee
            pricing_comp12.code = fee.code
            pricing_comp12.rated_object_kind = 'global'

            pricing_comp2 = self.PricingComponent()
            pricing_comp2.config_kind = 'simple'
            pricing_comp2.fixed_amount = 1
            pricing_comp2.kind = 'base'
            pricing_comp2.code = 'PP'
            pricing_comp2.rated_object_kind = 'sub_item'

            pricing_rulea = self.Pricing()

            pricing_rulea.components = [pricing_comp1, pricing_comp11,
                pricing_comp12]
            pricing_rulea.sub_item_components = [pricing_comp2]

            pricing_rulea.start_date = datetime.date.today()
            pricing_rulea.end_date = datetime.date.today() + \
                                            datetime.timedelta(days=10)

            pricing_comp3 = self.PricingComponent()
            pricing_comp3.config_kind = 'simple'
            pricing_comp3.fixed_amount = 15
            pricing_comp3.kind = 'base'
            pricing_comp3.code = 'PP'
            pricing_comp3.rated_object_kind = 'global'

            pricing_ruleb = self.Pricing()
            pricing_ruleb.components = [pricing_comp3]

            pricing_ruleb.start_date = datetime.date.today() + \
                                            datetime.timedelta(days=11)
            pricing_ruleb.end_date = datetime.date.today() + \
                                            datetime.timedelta(days=20)

            coverage_a = self.Coverage()
            coverage_a.family = coverage_a._fields['family'].selection[0][0]
            coverage_a.code = 'ALP'
            coverage_a.name = 'Alpha Coverage'
            coverage_a.start_date = datetime.date.today()

            coverage_a.pricing_rules = [pricing_rulea]

            coverage_a.save()

            # Coverage B

            tax_1 = self.create_tax('TTA', 27)

            pricing_comp4 = self.PricingComponent()
            pricing_comp4.config_kind = 'simple'
            pricing_comp4.fixed_amount = 30
            pricing_comp4.kind = 'base'
            pricing_comp4.code = 'PP'
            pricing_comp4.rated_object_kind = 'global'

            pricing_comp41 = self.PricingComponent()
            pricing_comp41.kind = 'tax'
            pricing_comp41.tax = tax_1
            pricing_comp41.code = tax_1.code
            pricing_comp41.rated_object_kind = 'global'

            pricing_rulec = self.Pricing()
            pricing_rulec.config_kind = 'simple'
            pricing_rulec.components = [pricing_comp4, pricing_comp41]

            pricing_rulec.start_date = datetime.date.today()
            pricing_rulec.end_date = datetime.date.today() + \
                                            datetime.timedelta(days=10)

            coverage_b = self.Coverage()
            coverage_b.code = 'BET'
            coverage_b.name = 'Beta Coverage'
            coverage_b.family = coverage_a._fields['family'].selection[0][0]
            coverage_b.start_date = datetime.date.today() + \
                                            datetime.timedelta(days=5)

            coverage_b.pricing_rules = [pricing_ruleb]

            coverage_b.save()

            # Coverage C

            eligibility_rule_a = self.Eligibility()
            eligibility_rule_a.config_kind = 'advanced'
            eligibility_rule_a.is_eligible = False
            eligibility_rule_a.rule = rule

            eligibility_rule_a.start_date = datetime.date.today()

            coverage_c = self.Coverage()
            coverage_c.code = 'GAM'
            coverage_c.name = 'Gamma Coverage'
            coverage_c.family = coverage_a._fields['family'].selection[0][0]
            coverage_c.start_date = datetime.date.today()

            coverage_c.eligibility_rules = [eligibility_rule_a]

            coverage_c.save()

            # Coverage D

            eligibility_rule_d = self.Eligibility()
            eligibility_rule_d.config_kind = 'simple'
            eligibility_rule_d.is_eligible = True
            eligibility_rule_d.is_sub_elem_eligible = False

            eligibility_rule_d.start_date = datetime.date.today()

            coverage_d = self.Coverage()
            coverage_d.code = 'DEL'
            coverage_d.name = 'Delta Coverage'
            coverage_d.family = coverage_a._fields['family'].selection[0][0]
            coverage_d.start_date = datetime.date.today()

            coverage_d.eligibility_rules = [eligibility_rule_d]

            coverage_d.save()

            # Product Eligibility Manager

            eligibility_rule_b = self.Eligibility()
            eligibility_rule_b.config_kind = 'simple'
            eligibility_rule_b.is_eligible = True

            eligibility_rule_b.start_date = datetime.date.today()

            # Product

            product_a = self.Product()
            product_a.code = 'AAA'
            product_a.name = 'Awesome Alternative Allowance'
            product_a.start_date = datetime.date.today()
            product_a.options = [
                coverage_a, coverage_b, coverage_c, coverage_d]
            product_a.eligibility_rules = [eligibility_rule_b]
            product_a.contract_generator = ng
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
