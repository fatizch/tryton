#-*- coding:utf-8 -*-
import datetime

# Needed for python test management
import unittest

# Needed for tryton test integration
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


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
        self.eligibility = POOL.get('ins_product.eligibility_rule')
        self.currency = POOL.get('currency.currency')

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
        party.address = []
        party.save()

        party, = self.Party.search([('name', '=', 'Toto')])
        self.assert_(party.id)

    def create_product(self):
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

        product_a = self.Product()
        product_a.code = 'AAA'
        product_a.name = 'Awesome Alternative Allowance'
        product_a.start_date = datetime.date.today()
        product_a.options = [coverage_a, coverage_b, coverage_c, coverage_d]
        product_a.eligibility_mgr = [brm_d]
        product_a.save()

        self.assert_(product_a.id)

        # Fake Eligibility Manager

        erm_c = self.eligibility()
        erm_c.config_kind = 'simple'
        erm_c.is_eligible = False

        gbr_f = self.gbr()
        gbr_f.kind = 'ins_product.eligibility_rule'
        gbr_f.start_date = datetime.date.today()
        gbr_f.eligibility_rule = [erm_c]

        brm_e = self.brm()
        brm_e.business_rules = [gbr_f]

        # Fake Product

        product_b = self.Product()
        product_b.code = 'BBB'
        product_b.name = 'Big Bad Bully'
        product_b.start_date = datetime.date.today()
        product_b.eligibility_mgr = [brm_e]
        product_b.save()

    def test0010Contract_creation(self):
        '''
            Tests subscription process
        '''
        from trytond.modules.coop_utils import add_days

        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:
            self.create_party()
            self.create_product()
            on_party, = self.Party.search([('name', '=', 'Toto')])
            on_product, = self.Product.search([('code', '=', 'BBB')])
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
            self.assertEqual(tmp[0], False)
            self.assertEqual(tmp[1][0], 'Not eligible')
            on_product, = self.Product.search([('code', '=', 'AAA')])
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
            tmp = wizard.option_selection.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], False)
            self.assertEqual(tmp[1][0], 'Not eligible')
            wizard.option_selection.options[3].status = 'Refused'
            wizard.option_selection.options[1].status = 'Refused'
            tmp = wizard.option_selection.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], True)
            wizard.option_selection.options[1].status = 'Active'
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
            self.assertEqual(len(covered.covered_data), 3)
            self.assertEqual(covered.covered_data[0].start_date,
                             wizard.project.start_date +
                             datetime.timedelta(days=1))
            tmp = wizard.extension_life.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], False)
            self.assertEqual(
                tmp[1][0],
                'Toto not eligible for Delta Coverage')
            wizard.transition_steps_previous()
            wizard.transition_master_step()
            wizard.option_selection.options[2].status = 'Refused'
            wizard.transition_steps_next()
            wizard.transition_master_step()
            tmp = wizard.extension_life.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], True)
            wizard.transition_steps_next()
            wizard.transition_master_step()

            def print_line(line):
                if not hasattr(line, 'name'):
                    return ''
                res = line.name
                if hasattr(line, 'value') and not line.value is None:
                    res += ' => %d' % line.value
                return res

            lines = []
            for elem in wizard.summary.lines:
                lines.append(print_line(elem))

            def date_from_today(nb):
                return add_days(datetime.date.today(), nb)

            good_lines = [
                date_from_today(5).isoformat(),
                '\tTotal Price => 43',
                '\t\tProduct Base Price => 0',
                '\t\tOptions => 43',
                '\t\t\tBeta Coverage => 30',
                '\t\t\t\tBase Price => 30',
                '\t\t\tAlpha Coverage => 13',
                '\t\t\t\tBase Price => 12',
                '\t\t\t\tToto => 1',
                '',
                date_from_today(2).isoformat(),
                '\tTotal Price => 0',
                '\t\tProduct Base Price => 0',
                '\t\tOptions => 0',
                '',
                date_from_today(3).isoformat(),
                '\tTotal Price => 13',
                '\t\tProduct Base Price => 0',
                '\t\tOptions => 13',
                '\t\t\tAlpha Coverage => 13',
                '\t\t\t\tBase Price => 12',
                '\t\t\t\tToto => 1',
                '',
                date_from_today(0).isoformat(),
                '\tTotal Price => 0',
                '\t\tProduct Base Price => 0',
                '\t\tOptions => 0',
                '',
                date_from_today(11).isoformat(),
                '\tTotal Price => 15',
                '\t\tProduct Base Price => 0',
                '\t\tOptions => 15',
                '\t\t\tBeta Coverage => 0',
                '\t\t\tAlpha Coverage => 15',
                '\t\t\t\tBase Price => 15',
                '']

            # print '\n'.join(lines)
            # print '###################'
            # print '\n'.join(good_lines)

            lines.sort()
            good_lines.sort()

            self.maxDiff = None

            self.assertListEqual(lines, good_lines)

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
