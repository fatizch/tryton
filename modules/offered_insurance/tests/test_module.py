# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'offered_insurance'

    @classmethod
    def fetch_models_for(cls):
        return ['rule_engine', 'company_cog', 'offered']

    @classmethod
    def get_models(cls):
        return {
            'Product': 'offered.product',
            'OptionDescription': 'offered.option.description',
            'Package': 'offered.package',
            'Sequence': 'ir.sequence',
            'Lang': 'ir.lang',
            'ItemDesc': 'offered.item.description',
            'ExtraPremiumKind': 'extra_premium.kind',
            'Insurer': 'insurer',
            'Party': 'party.party',
            'PackageOptionRelation': 'offered.package-option.description',
            'ExtraData': 'extra_data',
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
        allowed_elements = []
        allowed_elements.append(te8)
        allowed_elements.append(te4)
        ct.allowed_elements = allowed_elements

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
        tcv.value = 'datetime.date(2000, 11, 2)'

        tc = self.TestCase()
        tc.description = 'Test'
        tc.test_values = [tcv]
        tc.expected_result = '[True, [], [], []]'

        tcv1 = self.TestCaseValue()
        tcv1.name = 'date_de_naissance_souscripteur'
        tcv1.value = 'datetime.date(1950, 11, 2)'

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

    def test0005_testItemDescCreation(self):
        item_desc = self.ItemDesc()
        item_desc.kind = 'person'
        item_desc.code = 'person'
        item_desc.name = 'Person'
        item_desc.save()
        self.assertTrue(item_desc.id)

    def test0005_testInsurerCreation(self):
        insurer = self.Insurer()
        insurer.party = self.Party()
        insurer.party.name = 'Insurer'
        insurer.party.save()
        insurer.save()
        self.assertTrue(insurer.id)

    @test_framework.prepare_test(
        'offered_insurance.test0001_testFunctionalRuleCreation',
        'offered.test0001_testNumberGeneratorCreation',
        'offered_insurance.test0005_testItemDescCreation',
        'company_cog.test0001_testCompanyCreation',
        'offered_insurance.test0005_testInsurerCreation',
        )
    def test0010Coverage_creation(self):
        '''
            Tests coverage creation
        '''
        company, = self.Company.search([('party.name', '=', 'World Company')])
        insurer, = self.Insurer.search([])
        ng = self.Sequence.search([
                ('code', '=', 'contract')])[0]

        # Coverage A
        item_desc = self.ItemDesc.search([('code', '=', 'person')])[0]

        coverage_a = self.OptionDescription()
        coverage_a.family = coverage_a._fields['family'].selection[0][0]
        coverage_a.code = 'ALP'
        coverage_a.name = 'Alpha Coverage'
        coverage_a.start_date = datetime.date.today()
        coverage_a.sequence = 1

        coverage_a.item_desc = item_desc
        coverage_a.insurer = insurer

        coverage_a.company = company
        coverage_a.currency = company.currency
        coverage_a.save()

        # Coverage B

        coverage_b = self.OptionDescription()
        coverage_b.code = 'BET'
        coverage_b.name = 'Beta Coverage'
        coverage_b.family = coverage_a._fields['family'].selection[0][0]
        coverage_b.start_date = datetime.date.today() + \
            datetime.timedelta(days=5)
        coverage_b.sequence = 2

        coverage_b.item_desc = item_desc
        coverage_b.insurer = insurer
        coverage_b.company = company
        coverage_b.currency = company.currency
        coverage_b.save()

        # Coverage C

        coverage_c = self.OptionDescription()
        coverage_c.code = 'GAM'
        coverage_c.name = 'GammaCoverage'
        coverage_c.family = coverage_a._fields['family'].selection[0][0]
        coverage_c.start_date = datetime.date.today()
        coverage_c.sequence = 3

        coverage_c.item_desc = item_desc
        coverage_c.insurer = insurer
        coverage_c.company = company
        coverage_c.subscription_behaviour = 'optional'
        coverage_c.currency = company.currency

        coverage_c.save()

        # Coverage D

        coverage_d = self.OptionDescription()
        coverage_d.code = 'DEL'
        coverage_d.name = 'Delta Coverage'
        coverage_d.family = coverage_a._fields['family'].selection[0][0]
        coverage_d.start_date = datetime.date.today()
        coverage_d.sequence = 4

        coverage_d.item_desc = None
        coverage_d.insurer = insurer
        coverage_d.company = company
        coverage_d.currency = company.currency

        coverage_d.save()

        # Product

        product_a = self.Product()
        product_a.code = 'AAA'
        product_a.name = 'Awesome Alternative Allowance'
        product_a.start_date = datetime.date.today()
        product_a.coverages = [
            coverage_a, coverage_b, coverage_c, coverage_d]
        product_a.contract_generator = ng
        product_a.item_descriptors = [item_desc]
        product_a.company = company
        product_a.currency = company.currency
        product_a.save()

        self.assertTrue(product_a.id)

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
        )
    def test0010Package_creation(self):
        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ], limit=1)
        item_desc = self.ItemDesc.search([('code', '=', 'person')])[0]
        # add coverage at contract level
        coverage = self.OptionDescription()
        coverage.family = coverage._fields['family'].selection[0][0]
        coverage.code = 'CONT'
        coverage.name = 'Contract Coverage'
        coverage.start_date = datetime.date.today()
        coverage.insurer = product.coverages[0].insurer
        coverage.company = product.company
        coverage.currency = product.company.currency
        coverage.save()
        product.coverages = product.coverages + (coverage,)
        product.save()
        self.assertTrue(len(product.coverages) == 5)

        c1, c2, c3, c4, c5 = product.coverages
        # create packages

        def create_package(name, code, options, contract_extra_data):
            # options is a tuple with option and extra_ data
            package = self.Package()
            package.name = name
            package.code = code
            package.extra_data = contract_extra_data
            relations = []
            for option in options:
                relation = self.PackageOptionRelation()
                relation.option = option[0]
                relation.extra_data = option[1]
                relations.append(relation)
            package.option_relations = relations
            package.save()
            return package

        # Add extra_data on contract
        contract_extra_data = self.ExtraData()
        contract_extra_data.name = 'extra_data_contract'
        contract_extra_data.string = 'Extra Data Contract'
        contract_extra_data.type_ = 'selection'
        contract_extra_data.selection = 'formula1: Formula 1\n'\
            'formula2: Formula 2,formula3: Formula 3'
        contract_extra_data.kind = 'contract'
        contract_extra_data.save()
        product.extra_data_def = [contract_extra_data]

        # Add extra_data on coverage 1
        option_extra_data = self.ExtraData()
        option_extra_data.name = 'extra_data_coverage_alpha'
        option_extra_data.string = 'Extra Data Coverage Alpha'
        option_extra_data.type_ = 'selection'
        option_extra_data.selection = 'option1: Option 1\n'\
            'option2: Option 2,option3: Option 3'
        option_extra_data.kind = 'option'
        option_extra_data.save()
        option_alpha = product.coverages[0]
        option_alpha.extra_data_def = [option_extra_data]
        option_alpha.save()

        # Add covered extra data on item desc
        covered_extra_data = self.ExtraData()
        covered_extra_data.name = 'extra_data_covered'
        covered_extra_data.string = 'Extra Data Covered'
        covered_extra_data.type_ = 'selection'
        covered_extra_data.selection = 'covered1: Covered 1\n'\
            'covered2: Covered 2,covered3: Covered 3'
        covered_extra_data.kind = 'covered_element'
        covered_extra_data.save()
        item_desc.extra_data_def = [covered_extra_data]
        item_desc.save()

        product.packages_defined_per_covered = False
        package1 = create_package('Package 1', 'P1',
            [(c1, {'extra_data_coverage_alpha': 'option2'}), (c2, {})], {})
        package2 = create_package('Package 2', 'P2',
            [(c1, {'extra_data_coverage_alpha': 'option3'}), (c3, {}),
                (c4, {}), (c5, {})],
            {'extra_data_contract': 'formula2'})
        package3 = create_package('Package 3', 'P3',
            [(c3, {}), (c4, {})], {'extra_data_contract': 'formula3'})
        create_package('Package 4', 'P4',
            [(c1, {'extra_data_coverage_alpha': 'option1'}), (c3, {}),
                (c4, {})], {'extra_data_covered': 'covered3'})
        product.packages = [package1, package2, package3]
        product.save()
        self.assertTrue(len(product.packages) == 3)

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
                ('code', '=', 'reduc_no_limit'),
                ])
        self.assertTrue(extra_premium_kind1.id)
        self.assertTrue(extra_premium_kind1.is_discount)

        extra_premium_kind2 = createExtraPremiumKind('reduc_max_10_prct', True,
            '-0.10')
        extra_premium_kind2.save()

        extra_premium_kind3 = createExtraPremiumKind('majo_max_10_prct',
            max_rate='0.10')
        extra_premium_kind3.save()
        self.assertFalse(extra_premium_kind3.is_discount)

    @test_framework.prepare_test('offered_insurance.test0010Coverage_creation')
    def test0200_productDescription(self):
        product, = self.Product.search([('code', '=', 'AAA')])
        alpha, = self.OptionDescription.search([('code', '=', 'ALP')])
        beta, = self.OptionDescription.search([('code', '=', 'BET')])
        gamma, = self.OptionDescription.search([('code', '=', 'GAM')])
        delta, = self.OptionDescription.search([('code', '=', 'DEL')])
        item_desc, = self.ItemDesc.search([('code', '=', 'person')])

        self.maxDiff = None
        self.assertEqual(
            self.APIProduct.describe_products({}, {'_debug_server': True}),
            [{
                    'code': 'AAA',
                    'coverages': [
                        {
                            'code': 'ALP',
                            'description': '',
                            'extra_data': [],
                            'id': alpha.id,
                            'item_desc': item_desc.id,
                            'name': 'Alpha Coverage',
                            },
                        {
                            'code': 'BET',
                            'description': '',
                            'extra_data': [],
                            'id': beta.id,
                            'item_desc': item_desc.id,
                            'name': 'Beta Coverage',
                            },
                        {
                            'code': 'GAM',
                            'description': '',
                            'extra_data': [],
                            'id': gamma.id,
                            'item_desc': item_desc.id,
                            'name': 'GammaCoverage',
                            },
                        {
                            'code': 'DEL',
                            'description': '',
                            'extra_data': [],
                            'id': delta.id,
                            'item_desc': None,
                            'name': 'Delta Coverage',
                            }],
                    'description': '',
                    'extra_data': [],
                    'id': product.id,
                    'item_descriptors': [
                        {
                            'code': 'person',
                            'extra_data': [],
                            'fields': {
                                'conditions': [
                                    {'name': 'is_person', 'operator': '=',
                                        'value': True},
                                    ],
                                'fields': ['name', 'first_name', 'birth_date',
                                    'email', 'phone_number', 'address'],
                                'model': 'party',
                                'required': ['name', 'first_name', 'birth_date',
                                    'email', 'address']},
                            'id': item_desc.id,
                            'name': 'Person'}],
                    'name': 'Awesome Alternative Allowance',
                    'packages': [],
                    'subscriber': {
                        'fields': ['name', 'first_name', 'birth_date', 'email',
                            'phone_number', 'is_person', 'address'],
                        'model': 'party',
                        'required': ['name', 'first_name', 'birth_date',
                            'email', 'address'],
                        },
                    },
                ]
            )
        item_desc.kind = ''
        item_desc.save()
        self.assertEqual(
            self.APIProduct.describe_products({}, {'_debug_server': True}
                )[0]['item_descriptors'][0], {
                'code': 'person',
                'extra_data': [],
                'fields': {},
                'id': item_desc.id,
                'name': 'Person',
                })


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
