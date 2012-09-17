#-*- coding:utf-8 -*-
import datetime
from decimal import Decimal

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
        self.Person = POOL.get('party.person')
        self.Product = POOL.get('ins_product.product')
        self.coverage = POOL.get('ins_product.coverage')
        self.brm = POOL.get('ins_product.business_rule_manager')
        self.gbr = POOL.get('ins_product.generic_business_rule')
        self.pricing = POOL.get('ins_product.pricing_rule')
        self.eligibility = POOL.get('ins_product.eligibility_rule')
        self.currency = POOL.get('currency.currency')
        self.TreeElement = POOL.get('rule_engine.tree_element')
        self.Context = POOL.get('rule_engine.context')
        self.RuleEngine = POOL.get('rule_engine')
        self.TestCase = POOL.get('rule_engine.test_case')
        self.TestCaseValue = POOL.get('rule_engine.test_case.value')
        self.RunTests = POOL.get('rule_engine.run_tests', type='wizard')
        self.Tax = POOL.get('coop_account.tax_desc')
        self.TaxVersion = POOL.get('coop_account.tax_version')
        self.TaxManager = POOL.get('coop_account.tax_manager')
        self.AddressKind = POOL.get('party.address_kind')

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

    def create_tax(self, code, amount):
        tax_v1 = self.TaxVersion()
        tax_v1.kind = 'rate'
        tax_v1.rate_value = Decimal(amount)
        tax_v1.start_date = datetime.date.today()

        tax = self.Tax()
        tax.name = 'Test Tax %s' % code
        tax.code = 'code'
        tax.versions = [tax_v1]

        tax.save()

        return tax

    def create_person(self):
        address_kind = self.AddressKind()
        address_kind.key = 'main'
        address_kind.name = 'Main'
        address_kind.save()

        party = self.Person()
        party.name = 'Toto'
        party.first_name = 'titi'
        party.birth_date = datetime.date(1950, 12, 04)
        party.gender = 'M'
        party.save()

        party, = self.Party.search([('name', '=', 'Toto')])
        self.assert_(party.id)

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
        te.description = 'Person'
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

    def create_product(self):
        '''
            Tests process desc creation
        '''
        rule = self.createTestRule()

        #We need to create the currency manually because it's needed
        #on the default currency for product and coverage
        euro = self.currency()
        euro.name = 'Euro'
        euro.symbol = u'€'
        euro.code = 'EUR'
        euro.save()

        # Coverage A

        tax = self.create_tax('TT', 13)

        tm = self.TaxManager()
        tm.taxes = [tax]

        tm.save()

        prm_a = self.pricing()
        prm_a.config_kind = 'simple'
        prm_a.price = 12
        prm_a.tax_mgr = tm
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

        tax_1 = self.create_tax('TTA', 27)

        tm1 = self.TaxManager()
        tm1.taxes = [tax_1]

        tm1.save()

        prm_c = self.pricing()
        prm_c.config_kind = 'simple'
        prm_c.tax_mgr = tm1
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
        product_a.options = [
            coverage_a, coverage_b, coverage_c, coverage_d]
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
            self.create_person()
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
            self.assertEqual(tmp[1][0], 'GAM option not eligible :')
            self.assertEqual(tmp[1][1], '\tSubscriber too old (max: 40)')
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
            self.assertEqual(covered.person.party, on_party)
            self.assertEqual(len(covered.covered_data), 3)
            self.assertEqual(covered.covered_data[0].start_date,
                             wizard.project.start_date +
                             datetime.timedelta(days=1))
            tmp = wizard.extension_life.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], True)
            tmp = wizard.extension_life.post_step(
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
                if hasattr(line, 'value'):
                    res += ' => %.2f' % line.value
                if hasattr(line, 'taxes') and line.taxes:
                    res += ' (Tx : %.2f)' % line.taxes
                return res

            lines = []
            for elem in wizard.summary.lines:
                lines.append(print_line(elem))

            def date_from_today(nb):
                return add_days(datetime.date.today(), nb)

            good_lines = [
                date_from_today(5).isoformat(),
                '\tTotal Price => 43.00 (Tx : 9.66)',
                '\t\tProduct Base Price => 0.00',
                '\t\tOptions => 43.00 (Tx : 9.66)',
                '\t\t\tBeta Coverage => 30.00 (Tx : 8.10)',
                '\t\t\t\tBase Price => 30.00 (Tx : 8.10)',
                '\t\t\tAlpha Coverage => 13.00 (Tx : 1.56)',
                '\t\t\t\tBase Price => 12.00 (Tx : 1.56)',
                '\t\t\t\tToto => 1.00',
                '',
                date_from_today(2).isoformat(),
                '\tTotal Price => 0.00',
                '\t\tProduct Base Price => 0.00',
                '\t\tOptions => 0.00',
                '',
                date_from_today(3).isoformat(),
                '\tTotal Price => 13.00 (Tx : 1.56)',
                '\t\tProduct Base Price => 0.00',
                '\t\tOptions => 13.00 (Tx : 1.56)',
                '\t\t\tAlpha Coverage => 13.00 (Tx : 1.56)',
                '\t\t\t\tBase Price => 12.00 (Tx : 1.56)',
                '\t\t\t\tToto => 1.00',
                '',
                date_from_today(0).isoformat(),
                '\tTotal Price => 0.00',
                '\t\tProduct Base Price => 0.00',
                '\t\tOptions => 0.00',
                '',
                date_from_today(11).isoformat(),
                '\tTotal Price => 15.00',
                '\t\tProduct Base Price => 0.00',
                '\t\tOptions => 15.00',
                '\t\t\tBeta Coverage => 0.00',
                '\t\t\tAlpha Coverage => 15.00',
                '\t\t\t\tBase Price => 15.00',
                '']

            print '\n'.join(lines)
            print '###################'
            print '\n'.join(good_lines)

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
