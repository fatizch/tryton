#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from decimal import Decimal
from proteus import Model


def create_AAA_Product():
    Product = Model.get('ins_product.product')
    coverage = Model.get('ins_product.coverage')
    brm = Model.get('ins_product.business_rule_manager')
    gbr = Model.get('ins_product.generic_business_rule')

    gbr_a = gbr()
    gbr_a.kind = 'ins_product.pricing_rule'
    gbr_a.start_date = datetime.date.today()
    gbr_a.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=10)
    prm_a = gbr_a.pricing_rule[0]
    prm_a.price = Decimal(12.0)
    prm_a.per_sub_elem_price = Decimal(1.0)

    gbr_b = gbr()
    gbr_b.kind = 'ins_product.pricing_rule'
    gbr_b.start_date = datetime.date.today() + \
                                    datetime.timedelta(days=11)
    gbr_b.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=20)
    prm_b = gbr_b.pricing_rule[0]
    prm_b.price = Decimal(15.0)

    brm_a = brm()
    brm_a.business_rules.append(gbr_a)
    brm_a.business_rules.append(gbr_b)

    coverage_a = coverage()
    coverage_a.code = 'ALP'
    coverage_a.name = 'Alpha Coverage'
    coverage_a.start_date = datetime.date.today()

    gbr_c = gbr()
    gbr_c.kind = 'ins_product.pricing_rule'
    gbr_c.start_date = datetime.date.today()
    gbr_c.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=10)
    prm_c = gbr_c.pricing_rule[0]
    prm_c.price = Decimal(30.0)

    brm_b = brm()
    brm_b.business_rules.append(gbr_c)

    brm_b.save()
    brm_a.save()

    coverage_b = coverage()
    coverage_b.code = 'BET'
    coverage_b.name = 'Beta Coverage'
    coverage_b.start_date = datetime.date.today() + \
                                    datetime.timedelta(days=5)

#    coverage_b.pricing_mgr = []
    coverage_b.pricing_mgr.append(brm_b)

    coverage_a.pricing_mgr.append(brm_a)

    coverage_a.save()
    coverage_b.save()

    product_a = Product()
    product_a.code = 'AAA'
    product_a.name = 'Awesome Alternative Allowance'
    product_a.start_date = datetime.date.today()
    product_a.options.append(coverage_a)
    product_a.options.append(coverage_b)
    product_a.save()


def createRule():
    TreeElement = Model.get('rule_engine.tree_element')
    Context = Model.get('rule_engine.context')
    RuleEngine = Model.get('rule_engine')
    TestCase = Model.get('rule_engine.test_case')
    TestCaseValue = Model.get('rule_engine.test_case.value')

    te1 = TreeElement()
    te1.type = 'function'
    te1.name = 'get_person_name'
    te1.description = 'Name'
    te1.namespace = 'ins_product.rule_sets.person'

    te1.save()

    te2 = TreeElement()
    te2.type = 'function'
    te2.name = 'get_person_birthdate'
    te2.description = 'Birthday'
    te2.namespace = 'ins_product.rule_sets.person'

    te2.save()

    te = TreeElement()
    te.type = 'folder'
    te.description = 'Person'

    te.children.append(te1)
    te.children.append(te2)

    te.save()

    te3 = TreeElement()
    te3.type = 'function'
    te3.name = 'years_between'
    te3.description = 'Years between'
    te3.namespace = 'rule_engine.tools_functions'

    te3.save()

    te5 = TreeElement()
    te5.type = 'function'
    te5.name = 'today'
    te5.description = 'Today'
    te5.namespace = 'rule_engine.tools_functions'

    te5.save()

    te6 = TreeElement()
    te6.type = 'function'
    te6.name = 'message'
    te6.description = 'Add message'
    te6.namespace = 'rule_engine.tools_functions'

    te6.save()

    te4 = TreeElement()
    te4.type = 'folder'
    te4.description = 'Tools'
    te4.children.append(te3)
    te4.children.append(te5)
    te4.children.append(te6)

    te4.save()

    ct = Context()
    ct.name = 'test_context'
    ct.allowed_elements.append(te)
    ct.allowed_elements.append(te4)

    ct.save()

    rule = RuleEngine()
    rule.name = 'test_rule'
    rule.context = ct
    rule.code = '''
birthdate = get_person_birthdate()
if years_between(birthdate, today()) > 40:
    message('Subscriber too old (max: 40)')
    return False
return True'''

    tcv = TestCaseValue()
    tcv.name = 'get_person_birthdate'
    tcv.value = 'datetime.date(2000, 11, 02)'

    tc = TestCase()
    tc.description = 'Test'
    tc.values.append(tcv)
    tc.expected_result = '(True, [], [])'

    tcv1 = TestCaseValue()
    tcv1.name = 'get_person_birthdate'
    tcv1.value = 'datetime.date(1950, 11, 02)'

    tc1 = TestCase()
    tc1.description = 'Test1'
    tc1.values.append(tcv1)
    tc1.expected_result = '(False, ["Subscriber too old (max: 40)"], [])'

    rule.test_cases.append(tc)
    rule.test_cases.append(tc1)

    rule.save()

    return rule


def create_BBB_product():

    Product = Model.get('ins_product.product')
    coverage = Model.get('ins_product.coverage')
    brm = Model.get('ins_product.business_rule_manager')
    gbr = Model.get('ins_product.generic_business_rule')

    rule = createRule()

    # Coverage A
    gbr_a = gbr()
    gbr_a.kind = 'ins_product.pricing_rule'
    gbr_a.start_date = datetime.date.today()
    gbr_a.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=10)
    prm_a = gbr_a.pricing_rule[0]
    prm_a.config_kind = 'simple'
    prm_a.price = Decimal(12.0)
    prm_a.per_sub_elem_price = Decimal(1.0)

    gbr_b = gbr()
    gbr_b.kind = 'ins_product.pricing_rule'
    gbr_b.start_date = datetime.date.today() + \
                                    datetime.timedelta(days=11)
    gbr_b.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=20)
    prm_b = gbr_b.pricing_rule[0]
    prm_b.config_kind = 'simple'
    prm_b.price = Decimal(15.0)

    brm_a = brm()
    brm_a.business_rules.append(gbr_a)
    brm_a.business_rules.append(gbr_b)

    coverage_a = coverage()
    coverage_a.code = 'ALP'
    coverage_a.name = 'Alpha Coverage'
    coverage_a.start_date = datetime.date.today()

    coverage_a.pricing_mgr.append(brm_a)

    coverage_a.save()

    # Coverage B
    gbr_c = gbr()
    gbr_c.kind = 'ins_product.pricing_rule'
    gbr_c.start_date = datetime.date.today()
    gbr_c.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=10)
    prm_c = gbr_c.pricing_rule[0]
    prm_c.config_kind = 'simple'
    prm_c.price = Decimal(30.0)

    brm_b = brm()
    brm_b.business_rules.append(gbr_c)

    coverage_b = coverage()
    coverage_b.code = 'BET'
    coverage_b.name = 'Beta Coverage'
    coverage_b.start_date = datetime.date.today() + \
                                    datetime.timedelta(days=5)

    coverage_b.pricing_mgr.append(brm_b)

    coverage_b.save()

    # Coverage C
    gbr_d = gbr()
    gbr_d.kind = 'ins_product.eligibility_rule'
    gbr_d.start_date = datetime.date.today()
    erm_a = gbr_d.eligibility_rule[0]
    erm_a.config_kind = 'rule'
    erm_a.is_eligible = False
    erm_a.rule = rule

    brm_c = brm()
    brm_c.business_rules.append(gbr_d)

    coverage_c = coverage()
    coverage_c.code = 'GAM'
    coverage_c.name = 'Gamma Coverage'
    coverage_c.start_date = datetime.date.today()

    coverage_c.eligibility_mgr.append(brm_c)

    coverage_c.save()

    # Coverage D
    gbr_g = gbr()
    gbr_g.kind = 'ins_product.eligibility_rule'
    gbr_g.start_date = datetime.date.today()
    erm_d = gbr_g.eligibility_rule[0]
    erm_d.config_kind = 'simple'
    erm_d.is_eligible = True
    erm_d.is_sub_elem_eligible = False

    brm_f = brm()
    brm_f.business_rules.append(gbr_g)

    coverage_d = coverage()
    coverage_d.code = 'DEL'
    coverage_d.name = 'Delta Coverage'
    coverage_d.start_date = datetime.date.today()

    coverage_d.eligibility_mgr.append(brm_f)

    coverage_d.save()

    # Product Eligibility Manager
    gbr_e = gbr()
    gbr_e.kind = 'ins_product.eligibility_rule'
    gbr_e.start_date = datetime.date.today()
    erm_b = gbr_e.eligibility_rule[0]
    erm_b.config_kind = 'simple'
    erm_b.is_eligible = True

    brm_d = brm()
    brm_d.business_rules.append(gbr_e)

    # Product

    product_a = Product()
    product_a.code = 'BBB'
    product_a.name = 'Big Bad Bully'
    product_a.start_date = datetime.date.today()
    product_a.options.append(coverage_a)
    product_a.options.append(coverage_b)
    product_a.options.append(coverage_c)
    product_a.options.append(coverage_d)
    product_a.eligibility_mgr.append(brm_d)
    product_a.save()


def launch_test_case(cfg_dict):
    currency = Model.get('currency.currency')
    #We need to create the currency manually because it's needed
    #on the default currency for product and coverage
    euro = currency()
    euro.name = 'Euro'
    euro.symbol = u'€'
    euro.code = 'EUR'
    euro.save()

    create_AAA_Product()
    create_BBB_product()
