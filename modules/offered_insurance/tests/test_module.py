#-*- coding:utf-8 -*-
import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.modules.cog_utils import test_framework, utils


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'offered_insurance'

    @classmethod
    def depending_modules(cls):
        return ['rule_engine', 'company_cog']

    @classmethod
    def get_models(cls):
        return {
            'Product': 'offered.product',
            'OptionDescription': 'offered.option.description',
            'Pricing': 'billing.premium.rule',
            'Eligibility': 'offered.eligibility.rule',
            'PremiumRuleComponent': 'billing.premium.rule.component',
            'Tax': 'account.tax.description',
            'TaxVersion': 'account.tax.description.version',
            'Fee': 'account.fee.description',
            'FeeVersion': 'account.fee.description.version',
            'Sequence': 'ir.sequence',
            'Lang': 'ir.lang',
            'ItemDesc': 'offered.item.description',
            'ExtraPremiumKind': 'extra_premium.kind'
            }

    def test0001_testFunctionalRuleCreation(self):
        fr = self.Lang.search([('name', '=', 'French')], limit=1)[0]

        te2 = self.RuleFunction()
        te2.language = fr
        te2.type = 'function'
        te2.name = '_re_get_subscriber_birthdate'
        te2.translated_technical_name = 'date_de_naissance_souscripteur'
        te2.description = 'Date de naissance du Souscripteur'
        te2.namespace = 'rule_engine.runtime'

        te2.save()

        te8 = self.RuleFunction()
        te8.language = fr
        te8.type = 'folder'
        te8.translated_technical_name = 'Dossier Souscripteur'
        te8.description = 'Souscripteur'
        te8.children = [te2]

        te8.save()

        te3 = self.RuleFunction()
        te3.language = fr
        te3.type = 'function'
        te3.name = '_re_years_between'
        te3.translated_technical_name = 'annees_entre'
        te3.description = 'Années entre...'
        te3.namespace = 'rule_engine.runtime'

        te3.save()

        te5 = self.RuleFunction()
        te5.language = fr
        te5.type = 'function'
        te5.translated_technical_name = 'aujourd_hui'
        te5.name = '_re_today'
        te5.description = "Aujourd'hui"
        te5.namespace = 'rule_engine.runtime'

        te5.save()

        te6 = self.RuleFunction()
        te6.language = fr
        te6.type = 'function'
        te6.name = '_re_add_warning'
        te6.translated_technical_name = 'ajouter_warning'
        te6.description = 'Ajouter warning'
        te6.namespace = 'rule_engine.runtime'

        te6.save()

        te4 = self.RuleFunction()
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
        rule.algorithm = '''
birthdate = date_de_naissance_souscripteur()
if annees_entre(birthdate, aujourd_hui()) > 40.0:
    ajouter_warning('Subscriber too old (max: 40)')
    return False
return True'''

        tcv = self.TestCaseValue()
        tcv.name = 'date_de_naissance_souscripteur'
        tcv.value = 'datetime.date(2000, 11, 02)'

        tc = self.TestCase()
        tc.description = 'Test'
        tc.test_values = [tcv]
        tc.expected_result = '[True, [], [], []]'

        tcv1 = self.TestCaseValue()
        tcv1.name = 'date_de_naissance_souscripteur'
        tcv1.value = 'datetime.date(1950, 11, 02)'

        tc1 = self.TestCase()
        tc1.description = 'Test1'
        tc1.test_values = [tcv1]
        tc1.expected_result = \
            "[False, [], [Subscriber too old (max: 40)], []]"

        rule.test_cases = [tc, tc1]
        rule.short_name = 'Test Rule'
        rule.status = 'validated'

        rule.save()
        with Transaction().set_context({'active_id': rule.id}):
            wizard_id, _, _ = self.RunTests.create()
            wizard = self.RunTests(wizard_id)
            wizard._execute('report')
            res = wizard.default_report(None)
            self.assertEqual(
                res,
                {'report': 'Test ... SUCCESS\n\nTest1 ... SUCCESS'})

    def test0002_testTaxCreation(self):
        def create_tax(code, amount):
            tax_v = self.TaxVersion()
            tax_v.kind = 'rate'
            tax_v.value = Decimal(amount)
            tax_v.start_date = datetime.date.today()
            tax = self.Tax()
            tax.name = 'Test Tax %s' % code
            tax.code = code
            tax.versions = [tax_v]
            tax.save()
            return tax

        tax = create_tax('TT', 14)
        self.assert_(tax.id)
        tax = create_tax('TTA', 27)
        self.assert_(tax.id)

    def test0003_testFeeCreation(self):
        def create_fee(code, amount):
            fee_v = self.FeeVersion()
            fee_v.kind = 'flat'
            fee_v.value = Decimal(amount)
            fee_v.start_date = datetime.date.today()
            fee = self.Fee()
            fee.name = 'Test Fee %s' % code
            fee.code = code
            fee.versions = [fee_v]
            fee.save()
            return fee

        fee = create_fee('FEE', 20)
        self.assert_(fee.id)

    def test0004_testNumberGeneratorCreation(self):
        ng = self.Sequence()
        ng.name = 'Contract Sequence'
        ng.code = 'contract'
        ng.prefix = 'Ctr'
        ng.suffix = 'Y${year}'
        ng.save()
        self.assert_(ng.id)

    def test0005_testItemDescCreation(self):
        item_desc = self.ItemDesc()
        item_desc.kind = 'person'
        item_desc.code = 'person'
        item_desc.name = 'Person'
        item_desc.save()
        self.assert_(item_desc.id)

    @test_framework.prepare_test(
         'offered_insurance.test0001_testFunctionalRuleCreation',
         'offered_insurance.test0002_testTaxCreation',
         'offered_insurance.test0003_testFeeCreation',
         'offered_insurance.test0004_testNumberGeneratorCreation',
         'offered_insurance.test0005_testItemDescCreation',
         'company_cog.test0001_testCompanyCreation',
        )
    def test0010Coverage_creation(self):
        '''
            Tests coverage creation
        '''
        company, = self.Company.search([('party.name', '=', 'World Company')])
        rule = self.RuleEngine.search([('name', '=', 'test_rule')])[0]
        ng = self.Sequence.search([
                ('code', '=', 'contract')])[0]

        # Coverage A

        tax = self.Tax.search([('code', '=', 'TT')])[0]
        fee = self.Fee.search([('code', '=', 'FEE')])[0]
        item_desc = self.ItemDesc.search([('code', '=', 'person')])[0]

        pricing_comp1 = self.PremiumRuleComponent()
        pricing_comp1.config_kind = 'simple'
        pricing_comp1.fixed_amount = 12
        pricing_comp1.kind = 'base'
        pricing_comp1.code = 'PP'
        pricing_comp1.rated_object_kind = 'global'

        pricing_comp11 = self.PremiumRuleComponent()
        pricing_comp11.kind = 'tax'
        pricing_comp11.tax = tax
        pricing_comp11.code = tax.code
        pricing_comp11.rated_object_kind = 'global'

        pricing_comp12 = self.PremiumRuleComponent()
        pricing_comp12.kind = 'fee'
        pricing_comp12.fee = fee
        pricing_comp12.code = fee.code
        pricing_comp12.rated_object_kind = 'global'

        pricing_comp2 = self.PremiumRuleComponent()
        pricing_comp2.config_kind = 'simple'
        pricing_comp2.fixed_amount = 1
        pricing_comp2.kind = 'base'
        pricing_comp2.code = 'PP'
        pricing_comp2.rated_object_kind = 'sub_item'

        premium_rulea = self.Pricing()

        premium_rulea.components = [
            pricing_comp1, pricing_comp11, pricing_comp12]
        premium_rulea.sub_item_components = [pricing_comp2]

        premium_rulea.start_date = datetime.date.today()
        premium_rulea.end_date = datetime.date.today() + \
            datetime.timedelta(days=10)

        pricing_comp3 = self.PremiumRuleComponent()
        pricing_comp3.config_kind = 'simple'
        pricing_comp3.fixed_amount = 15
        pricing_comp3.kind = 'base'
        pricing_comp3.code = 'PP'
        pricing_comp3.rated_object_kind = 'global'

        premium_ruleb = self.Pricing()
        premium_ruleb.components = [pricing_comp3]

        premium_ruleb.start_date = datetime.date.today() + \
            datetime.timedelta(days=11)
        premium_ruleb.end_date = datetime.date.today() + \
            datetime.timedelta(days=20)

        coverage_a = self.OptionDescription()
        coverage_a.family = coverage_a._fields['family'].selection[0][0]
        coverage_a.code = 'ALP'
        coverage_a.name = 'Alpha Coverage'
        coverage_a.start_date = datetime.date.today()

        coverage_a.premium_rules = [premium_rulea]

        coverage_a.item_desc = item_desc

        coverage_a.company = company
        coverage_a.save()

        # Coverage B

        tax_1 = self.Tax.search([('code', '=', 'TTA')])[0]

        pricing_comp4 = self.PremiumRuleComponent()
        pricing_comp4.config_kind = 'simple'
        pricing_comp4.fixed_amount = 30
        pricing_comp4.kind = 'base'
        pricing_comp4.code = 'PP'
        pricing_comp4.rated_object_kind = 'global'

        pricing_comp41 = self.PremiumRuleComponent()
        pricing_comp41.kind = 'tax'
        pricing_comp41.tax = tax_1
        pricing_comp41.code = tax_1.code
        pricing_comp41.rated_object_kind = 'global'

        premium_rulec = self.Pricing()
        premium_rulec.config_kind = 'simple'
        premium_rulec.components = [pricing_comp4, pricing_comp41]

        premium_rulec.start_date = datetime.date.today()
        premium_rulec.end_date = datetime.date.today() + \
            datetime.timedelta(days=10)

        coverage_b = self.OptionDescription()
        coverage_b.code = 'BET'
        coverage_b.name = 'Beta Coverage'
        coverage_b.family = coverage_a._fields['family'].selection[0][0]
        coverage_b.start_date = datetime.date.today() + \
            datetime.timedelta(days=5)

        coverage_b.premium_rules = [premium_ruleb]

        coverage_b.item_desc = item_desc
        coverage_b.company = company
        coverage_b.save()

        # Coverage C

        eligibility_rule_a = self.Eligibility()
        eligibility_rule_a.config_kind = 'advanced'
        eligibility_rule_a.min_age = 100
        eligibility_rule_a.rule = rule

        eligibility_rule_a.start_date = datetime.date.today()

        coverage_c = self.OptionDescription()
        coverage_c.code = 'GAM'
        coverage_c.name = 'GammaCoverage'
        coverage_c.family = coverage_a._fields['family'].selection[0][0]
        coverage_c.start_date = datetime.date.today()

        coverage_c.eligibility_rules = [eligibility_rule_a]

        coverage_c.item_desc = item_desc
        coverage_c.company = company

        coverage_c.save()

        # Coverage D

        eligibility_rule_d = self.Eligibility()
        eligibility_rule_d.config_kind = 'simple'
        eligibility_rule_d.is_eligible = True
        eligibility_rule_d.is_sub_elem_eligible = False

        eligibility_rule_d.start_date = datetime.date.today()

        coverage_d = self.OptionDescription()
        coverage_d.code = 'DEL'
        coverage_d.name = 'Delta Coverage'
        coverage_d.family = coverage_a._fields['family'].selection[0][0]
        coverage_d.start_date = datetime.date.today()

        coverage_d.eligibility_rules = [eligibility_rule_d]

        coverage_d.item_desc = item_desc
        coverage_d.company = company

        coverage_d.save()

        # Product Eligibility Manager

        eligibility_rule_b = self.Eligibility()
        eligibility_rule_b.config_kind = 'simple'
        eligibility_rule_b.min_age = 40
        eligibility_rule_b.max_age = 45
        eligibility_rule_b.start_date = datetime.date.today()

        # Product

        product_a = self.Product()
        product_a.code = 'AAA'
        product_a.name = 'Awesome Alternative Allowance'
        product_a.start_date = datetime.date.today()
        product_a.coverages = [
            coverage_a, coverage_b, coverage_c, coverage_d]
        product_a.eligibility_rules = [eligibility_rule_b]
        product_a.contract_generator = ng
        product_a.item_descriptors = [item_desc]
        product_a.company = company
        product_a.save()

        self.assert_(product_a.id)

    def test0100_testExtraPremiumKindCreation(self):
        def createExtraPremiumKind(code, is_discount=False, max_rate=None,
                                   max_value=None):
            extra_premium_kind = self.ExtraPremiumKind()
            extra_premium_kind.code = code
            extra_premium_kind.name = code
            extra_premium_kind.is_discount = is_discount
            if max_rate:
                extra_premium_kind.max_rate = Decimal(max_rate)
            if max_value:
                extra_premium_kind.max_value = Decimal(max_value)
            return extra_premium_kind

        extra_premium_kind1 = createExtraPremiumKind('reduc_no_limit', True)

        extra_premium_kind1.save()
        extra_premium_kind1, = self.ExtraPremiumKind.search([
            ('code', '=', 'reduc_no_limit'), ])
        self.assert_(extra_premium_kind1.id)
        self.assert_(extra_premium_kind1.is_discount)

        extra_premium_kind2 = createExtraPremiumKind('reduc_max_10_prct',
                                                     True, '-0.10')
        print utils.format_data(extra_premium_kind2._save_values)
        extra_premium_kind2.save()

        extra_premium_kind3 = createExtraPremiumKind('majo_max_10_prct',
                                                     max_rate='0.10')
        extra_premium_kind3.save()
        self.assertFalse(extra_premium_kind3.is_discount)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
