#-*- coding:utf-8 -*-
import datetime

# Needed for python test management
import unittest

# Needed for tryton test integration
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.modules.insurance_product import PricingResultLine


class LaboratoryTestCase(unittest.TestCase):
    def setUp(self):
        trytond.tests.test_tryton.install_module('insurance_product')
        self.product = POOL.get('ins_product.product')
        self.coverage = POOL.get('ins_product.coverage')
        self.brm = POOL.get('ins_product.business_rule_manager')
        self.gbr = POOL.get('ins_product.generic_business_rule')
        self.pricing = POOL.get('ins_product.pricing_rule')
        self.currency = POOL.get('currency.currency')
        self.eligibility = POOL.get('ins_product.eligibility_rule')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('insurance_product')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010Coverage_creation(self):
        '''
            Tests process desc creation
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:

            #We need to create the currency manually because it's needed
            #on the default currency for product and coverage
            euro = self.currency()
            euro.name = 'Euro'
            euro.symbol = u'€'
            euro.code = 'EUR'
            euro.save()

            # Coverage A

            prm_a = self.pricing()
            prm_a.config_kind = 'simple'
            prm_a.price = 12
            prm_a.per_sub_elem_price = 1

            gbr_a = self.gbr()
            gbr_a.kind = 'ins_product.pricing_rule'
            gbr_a.start_date = datetime.date.today()
            gbr_a.end_date = datetime.date.today() + \
                                            datetime.timedelta(days=10)
            gbr_a.pricing_rule = [prm_a]

            prm_b = self.pricing()
            prm_b.config_kind = 'simple'
            prm_b.price = 15

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
            coverage_a.code = 'ALP'
            coverage_a.name = 'Alpha Coverage'
            coverage_a.start_date = datetime.date.today()

            coverage_a.pricing_mgr = [brm_a]

            coverage_a.save()

            # Coverage B

            prm_c = self.pricing()
            prm_c.config_kind = 'simple'
            prm_c.price = 30

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
            coverage_b.start_date = datetime.date.today() + \
                                            datetime.timedelta(days=5)

            coverage_b.pricing_mgr = [brm_b]

            coverage_b.save()

            # Coverage C

            erm_a = self.eligibility()
            erm_a.config_kind = 'simple'
            erm_a.is_eligible = False

            gbr_d = self.gbr()
            gbr_d.kind = 'ins_product.eligibility_rule'
            gbr_d.start_date = datetime.date.today()
            gbr_d.eligibility_rule = [erm_a]

            brm_c = self.brm()
            brm_c.business_rules = [gbr_d]

            coverage_c = self.coverage()
            coverage_c.code = 'GAM'
            coverage_c.name = 'Gamma Coverage'
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

            product_a = self.product()
            product_a.code = 'AAA'
            product_a.name = 'Awesome Alternative Allowance'
            product_a.start_date = datetime.date.today()
            product_a.options = [
                coverage_a, coverage_b, coverage_c, coverage_d]
            product_a.eligibility_mgr = [brm_d]
            product_a.save()

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
        LaboratoryTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
