import datetime

# Needed for python test management
import unittest

# Needed for tryton test integration
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction

# Needed for wizardry testing
from trytond.wizard import Wizard
from trytond.exceptions import UserError


class ContractTestCase(unittest.TestCase):

    def setUp(self):
        trytond.tests.test_tryton.install_module('insurance_contract')
        self.Contract = POOL.get('ins_contract.contract')
        self.SubsProcess = POOL.get('ins_contract.subs_process',
                                          type='wizard')
        self.ProcessDesc = POOL.get('ins_process.process_desc')
        self.Party = POOL.get('party.party')
        self.Product = POOL.get('ins_product.product')
        self.coverage = POOL.get('ins_product.coverage')
        self.brm = POOL.get('ins_product.business_rule_manager')
        self.gbr = POOL.get('ins_product.generic_business_rule')
        self.pricing = POOL.get('ins_product.pricing_rule')

        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:
            subs_process_desc, = self.ProcessDesc.search([
                        ('process_model', '=', 'ins_contract.subs_process')])
            self.assert_(subs_process_desc.id)

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('insurance_contract')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def create_party(self):
        party = self.Party()
        party.name = 'Toto'
        party.save()

        party, = self.Party.search([('name', '=', 'Toto')])
        self.assert_(party.id)

    def create_product(self):
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

        product_a = self.Product()
        product_a.code = 'AAA'
        product_a.name = 'Awesome Alternative Allowance'
        product_a.start_date = datetime.date.today()
        product_a.options = [coverage_a, coverage_b]
        product_a.save()

        self.assert_(product_a.id)

    def test0010Contract_creation(self):
        '''
            Tests subscription process
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:
            self.create_party()
            self.create_product()
            on_party, = self.Party.search([('name', '=', 'Toto')])
            on_product, = self.Product.search([('code', '=', 'AAA')])
            wizard_id, _, _ = self.SubsProcess.create()
            wizard = self.SubsProcess(wizard_id)
            wizard.transition_steps_start()
            tmp = wizard.project.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], False)
            self.assertEqual(wizard.project.start_date,
                            datetime.date.today())
            wizard.project.start_date += datetime.timedelta(days=2)
            wizard.project.subscriber = on_party
            tmp = wizard.project.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], False)
            wizard.project.product = on_product
            tmp = wizard.project.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], True)
            wizard.transition_steps_next()
            wizard.transition_master_step()
            tmp = set([elem.coverage.code for elem in
                        wizard.option_selection.options])
            self.assertEqual(len(tmp), len(on_product.options))
            self.assertEqual(tmp,
                             set([elem.code for elem in on_product.options]))
            self.assertEqual(wizard.option_selection.options[0].start_date,
                             wizard.project.start_date)
            self.assertEqual(wizard.option_selection.options[1].start_date,
                             wizard.project.start_date +
                             datetime.timedelta(days=3))
            wizard.option_selection.options[0].start_date += \
                datetime.timedelta(days=-4)
            tmp = wizard.option_selection.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], False)
            wizard.option_selection.options[0].start_date += \
                datetime.timedelta(days=5)
            wizard.option_selection.options[1].start_date += \
                datetime.timedelta(days=-1)
            tmp = wizard.option_selection.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], False)
            wizard.option_selection.options[1].start_date += \
                datetime.timedelta(days=1)
            wizard.option_selection.options[1].status = 'Refused'
            tmp = wizard.option_selection.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], True)
            wizard.transition_steps_next()
            wizard.transition_master_step()
            wizard.transition_steps_previous()
            wizard.transition_master_step()
            wizard.transition_steps_next()
            wizard.transition_master_step()
            tmp = hasattr(wizard, 'extension_life')
            self.assert_(tmp)
            self.assertEqual(len(wizard.extension_life.covered_elements), 1)
            covered = wizard.extension_life.covered_elements[0]
            self.assertEqual(covered.person, on_party)
            self.assertEqual(len(covered.covered_data), 1)
            self.assertEqual(covered.covered_data[0].start_date,
                             wizard.project.start_date +
                             datetime.timedelta(days=1))
            wizard.transition_steps_complete()
            wizard.transition_master_step()

            contract, = self.Contract.search([('id', '=', '1')])
            self.assert_(contract.id)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ContractTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
