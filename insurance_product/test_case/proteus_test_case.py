#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from decimal import Decimal
from proteus import Model


def get_models():
    res = {}
    res['Product'] = Model.get('ins_product.product')
    res['TreeElement'] = Model.get('rule_engine.tree_element')
    res['Context'] = Model.get('rule_engine.context')
    res['RuleEngine'] = Model.get('rule_engine')
    res['TestCase'] = Model.get('rule_engine.test_case')
    res['TestCaseValue'] = Model.get('rule_engine.test_case.value')
    return res


def create_product(models, code, name, options=None):
    if not is_in_db(models, 'Product', code):
        product = models['Product']()
        product.code = code
        product.name = name
        product.start_date = datetime.date.today()
        if options:
            product.options[:] = options
        return product


def is_in_db(models, model, code):
    return len(models[model].find([('code', '=', code)], limit=1)) > 0


def create_AAA_Product(models, code, name):
    product_a = create_product(models, code, name)
    if not product_a:
        return None
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

    product_a.options.append(coverage_a)
    product_a.options.append(coverage_b)
    product_a.save()


def get_or_create_tree_element(models, cur_type, description, name=None,
        namespace=None):
    cur_domain = []
    if cur_type == 'function':
        cur_domain.append(('namespace', '=', namespace))
        cur_domain.append(('name', '=', name))
    if cur_type == 'folder':
        cur_domain.append(('name', '=', name))
    tree_elements = models['TreeElement'].find(cur_domain)
    if len(tree_elements) > 0:
        return tree_elements[0]
    te = models['TreeElement']()
    te.type = cur_type
    te.name = name
    te.description = description
    te.namespace = namespace
    te.save()
    return te


def append_inexisting_elements(cur_object, list_name, cur_list):
    cur_list = getattr(cur_object, list_name, [])
    for child in cur_list:
        if not child in cur_list:
            cur_list.append(child)
    cur_object.save()
    return cur_object


def get_or_create_context(models, name):
    contexts = models['Context'].find([('name', '=', name)])
    if len(contexts) > 0:
        return contexts[0]
    ct = models['Context']()
    ct.name = name
    ct.save()
    return ct


def create_rule(models, ct, name):
    rules = models('RuleEngine').find([('name', '=', name)])
    if len(rules > 0):
        return rules[0]
    rule = models('RuleEngine')()
    rule.name = name
    rule.context = ct
    rule.code = '''
birthdate = get_person_birthdate()
if years_between(birthdate, today()) > 40:
    message('Subscriber too old (max: 40)')
    return False
return True'''

    tcv = models('TestCaseValue')()
    tcv.name = 'get_person_birthdate'
    tcv.value = 'datetime.date(2000, 11, 02)'

    tc = models('TestCase')()
    tc.description = 'Test'
    tc.values.append(tcv)
    tc.expected_result = '(True, [], [])'

    tcv1 = models('TestCaseValue')()
    tcv1.name = 'get_person_birthdate'
    tcv1.value = 'datetime.date(1950, 11, 02)'

    tc1 = models('TestCase')()
    tc1.description = 'Test1'
    tc1.values.append(tcv1)
    tc1.expected_result = '(False, ["Subscriber too old (max: 40)"], [])'

    rule.test_cases.append(tc)
    rule.test_cases.append(tc1)

    rule.save()

    return rule


def create_rule_engine_data(models):
    te1 = get_or_create_tree_element(models, 'function', 'Name',
        'get_person_name', 'ins_product.rule_sets.person')
    te2 = get_or_create_tree_element(models, 'function', 'Birthday',
        'get_person_birthdate', 'ins_product.rule_sets.person')
    te = get_or_create_tree_element(models, 'folder', 'Person')
    append_inexisting_elements(te, 'children', [te1, te2])

    te3 = get_or_create_tree_element(models, 'function', 'Years between',
        'years_between', 'rule_engine.tools_functions')
    te5 = get_or_create_tree_element(models, 'function', 'Today', 'today',
        'rule_engine.tools_functions')

    te6 = get_or_create_tree_element(models, 'function', 'Add message',
        'message', 'rule_engine.tools_functions')

    te4 = get_or_create_tree_element(models, 'folder', 'Tools')
    append_inexisting_elements(te4, 'children', [te3, te5, te6])

    ct = get_or_create_context(models, 'test_context')
    append_inexisting_elements(ct, 'allowed_elements', [te, te4])

    return create_rule(models, ct, 'test_rule')


def create_BBB_product(models, code, name):
    product_b = create_product(models, code, name)
    if not product_b:
        return None
    coverage = Model.get('ins_product.coverage')
    brm = Model.get('ins_product.business_rule_manager')
    gbr = Model.get('ins_product.generic_business_rule')

    rule = create_rule_engine_data(models)

    coverage_a, = coverage.find([('code', '=', 'ALP')], limit=1)
    coverage_b, = coverage.find([('code', '=', 'BET')], limit=1)

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

    product_b.options.append(coverage_a)
    product_b.options.append(coverage_b)
    product_b.options.append(coverage_c)
    product_b.options.append(coverage_d)
    product_b.eligibility_mgr.append(brm_d)
    product_b.save()


def launch_test_case(cfg_dict):
    currency = Model.get('currency.currency')
    #We need to create the currency manually because it's needed
    #on the default currency for product and coverage
    euro = currency()
    euro.name = 'Euro'
    euro.symbol = u'€'
    euro.code = 'EUR'
    euro.save()

    models = get_models()
    create_AAA_Product(models, 'AAA', 'Awesome Alternative Allowance')
    create_BBB_product(models, 'BBB', 'Big Bad Bully')
