import datetime

# Needed for python test management
import unittest

# Needed for tryton test integration
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class LaboratoryTestCase(unittest.TestCase):
    def setUp(self):
        trytond.tests.test_tryton.install_module('insurance_product')
        self.product = POOL.get('ins_product.product')
        self.coverage = POOL.get('ins_product.coverage')
        self.brm = POOL.get('ins_product.business_rule_manager')
        self.gbr = POOL.get('ins_product.generic_business_rule')
        self.pricing = POOL.get('ins_product.pricing_rule')

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
            prm_a = self.pricing()
            prm_a.price = 12

            gbr_a = self.gbr()
            gbr_a.kind = 'ins_product.pricing_rule'
            gbr_a.start_date = datetime.date.today()
            gbr_a.end_date = datetime.date.today() + \
                                            datetime.timedelta(days=10)
            gbr_a.pricing_rule = [prm_a]

            prm_b = self.pricing()
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

            coverage_b = self.coverage()
            coverage_b.code = 'BET'
            coverage_b.name = 'Beta Coverage'
            coverage_b.start_date = datetime.date.today() + \
                                            datetime.timedelta(days=5)

            coverage_a.pricing_mgr = brm_a

            coverage_a.save()
            coverage_b.save()

            coverage_a, = self.coverage.search([('code', '=', 'ALP')])
            coverage_b, = self.coverage.search([('code', '=', 'BET')])

            product_a = self.product()
            product_a.code = 'AAA'
            product_a.name = 'Awesome Alternative Allowance'
            product_a.start_date = datetime.date.today()
            product_a.options = [coverage_a, coverage_b]
            product_a.save()

            transaction.cursor.commit()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        LaboratoryTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
