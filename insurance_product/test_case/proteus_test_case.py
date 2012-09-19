#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from decimal import Decimal
from proteus import Model


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Currency'] = Model.get('currency.currency')
    cfg_dict['Coverage'] = Model.get('ins_product.coverage')
    cfg_dict['Product'] = Model.get('ins_product.product')
    cfg_dict['TreeElement'] = Model.get('rule_engine.tree_element')
    cfg_dict['Context'] = Model.get('rule_engine.context')
    cfg_dict['RuleEngine'] = Model.get('rule_engine')
    cfg_dict['TestCase'] = Model.get('rule_engine.test_case')
    cfg_dict['TestCaseValue'] = Model.get('rule_engine.test_case.value')
    cfg_dict['Insurer'] = Model.get('party.insurer')
    cfg_dict['Date'] = Model.get('ir.date')
    cfg_dict['Tax'] = Model.get('coop_account.tax_desc')
    cfg_dict['TaxVersion'] = Model.get('coop_account.tax_version')
    cfg_dict['TaxManager'] = Model.get('coop_account.tax_manager')
    return cfg_dict


def get_or_create_product(cfg_dict, code, name, options=None):
    product = get_object_from_db(cfg_dict, 'Product', 'code', code)
    if product:
        return product
    product = cfg_dict['Product']()
    product.code = code
    product.name = name
    product.start_date = cfg_dict['Date'].today({})
    if options:
        product.options[:] = options
    return product


def get_object_from_db(cfg_dict, model, key=None, value=None, domain=None,
        force_search=False):
    if not force_search and cfg_dict['re_create_if_already_exists']:
        return None
    if not domain:
        domain = []
    if key and value:
        domain.append((key, '=', value))
    instances = cfg_dict[model].find(domain, limit=1)
    if instances:
        return instances[0]


def try_to_save_object(cfg_dict, cur_object):
    if not cfg_dict['re_create_if_already_exists']:
        cur_object.save()
    #if we try to save one object which already exists, we could have error
    #with constraints
    try:
        cur_object.save()
    except:
        print 'Exception raised when trying to save', cur_object


def get_or_create_coverage(cfg_dict, code, name, date=None):
    coverage = get_object_from_db(cfg_dict, 'Coverage', 'code', code)
    if coverage:
        return coverage
    coverage = cfg_dict['Coverage']()
    coverage.code = code
    coverage.name = name
    if date:
        coverage.start_date = date
    else:
        coverage.start_date = cfg_dict['Date'].today({})
    coverage.insurer = get_object_from_db(cfg_dict, 'Insurer',
        force_search=True)
    return coverage


def get_or_create_tax(cfg_dict, code, name, vals=None):
    tax = get_object_from_db(cfg_dict, 'Tax', 'code', code)
    if tax:
        return tax
    tax = cfg_dict['Tax']()
    tax.code = code
    tax.name = name
    if vals:
        for val in vals:
            tax_ver = cfg_dict['TaxVersion']()
            tax_ver.start_date = val.get('start_date', None)
            tax_ver.end_date = val.get('end_date', None)
            tax_ver.kind = val.get('kind', 'None')
            tax_ver.value = Decimal(val.get('value', 0))
            tax.versions.append(tax_ver)
    tax.save()
    return tax


def add_description(product):
    if product.description:
        return product
    product.description = '''Une solution pour <b>compléter votre régime \
obligatoire</b>
<b>En cas d’arrêt de travail temporaire ou prolongé, maintenez votre \
salaire à 100 %</b>
    En cas d’arrêt de travail, seuls 50 % de vos revenus vous sont versés \
par la Sécurité Sociale. Pour maintenir votre revenu et continuer à vivre\
 normalement, une indemnité journalière complète intégralement celle de \
votre régime obligatoire jusqu’au 1095ème jour (3 ans, délai après lequel \
vous êtes considéré comme invalide).

<b>En cas d’invalidité, votre pouvoir d’achat est préservé</b>
    Vous risquez de ne plus pouvoir exercer votre emploi. Nous complétons \
votre rente de la Sécurité Sociale par une rente d’invalidité, jusqu’à \
votre retraite (au plus tard jusqu’à votre 60ème anniversaire).

<b>En cas de décès ou de Perte Totale et Irréversible d’Autonomie, \
l’avenir de vos proches est assuré</b>
    Des garanties financières pour votre foyer :
            • Capital décès
            Vous mettez vos proches à l’abri des soucis financiers.Vous \
choisissez librement le montant du capital qui peut aller jusqu’à \
600 000 € et n’est pas imposable dans la limite de 152 500 € \
(selon la réglementation en vigueur).
            • Rente de conjoint
            Une rente plafonnée à 20 000 € par an est versée jusqu’au 65ème \
anniversaire du conjoint ou concubin.Vous avez la certitude que \
votre conjoint bénéficiera d’un complément de revenu régulier \
jusqu’à sa retraite.
            • Rente éducation
            Vous donnez les moyens de garantir à vos enfants le financement \
de leurs études quoiqu’il arrive.Vos enfants perçoivent une rente \
pouvant atteindre 4 500 € par an et ce, jusqu’à la fin de \
leurs études (au plus tard jusqu’à leur 26ème anniversaire).'''


def create_AAA_Product(cfg_dict, code, name):
    product_a = get_or_create_product(cfg_dict, code, name)
    if product_a.id > 0:
        return product_a
    add_description(product_a)
    brm = Model.get('ins_product.business_rule_manager')
    gbr = Model.get('ins_product.generic_business_rule')

    gbr_a = gbr()
    gbr_a.kind = 'ins_product.pricing_rule'
    gbr_a.start_date = cfg_dict['Date'].today({})
    gbr_a.end_date = cfg_dict['Date'].today({}) + \
                                    datetime.timedelta(days=10)
    prm_a = gbr_a.pricing_rule[0]
    prm_a.price = Decimal(12.0)
    prm_a.per_sub_elem_price = Decimal(1.0)

    gbr_b = gbr()
    gbr_b.kind = 'ins_product.pricing_rule'
    gbr_b.start_date = cfg_dict['Date'].today({}) + \
                                    datetime.timedelta(days=11)
    gbr_b.end_date = cfg_dict['Date'].today({}) + \
                                    datetime.timedelta(days=20)

    tax = get_or_create_tax(cfg_dict,
        'CCSS',
        u'Contribution prévue par le Code de la Sécurité sociale',
        [
            {'start_date': cfg_dict['Date'].today({}),
            'kind': 'rate',
            'value': 0.15}])
    tax_manager = cfg_dict['TaxManager']()
    tax_manager.taxes.append(tax)

    tax_manager.save()

    prm_b = gbr_b.pricing_rule[0]
    prm_b.price = Decimal(15.0)
    prm_b.tax_mgr = tax_manager

    brm_a = brm()
    brm_a.business_rules.append(gbr_a)
    brm_a.business_rules.append(gbr_b)

    coverage_a = get_or_create_coverage(cfg_dict, 'ALP', 'Alpha Coverage')
    gbr_c = gbr()
    gbr_c.kind = 'ins_product.pricing_rule'
    gbr_c.start_date = cfg_dict['Date'].today({})
    gbr_c.end_date = cfg_dict['Date'].today({}) + \
                                    datetime.timedelta(days=10)
    prm_c = gbr_c.pricing_rule[0]
    prm_c.price = Decimal(30.0)

    brm_b = brm()
    brm_b.business_rules.append(gbr_c)

    try_to_save_object(cfg_dict, brm_b)
    try_to_save_object(cfg_dict, brm_a)

    coverage_b = get_or_create_coverage(cfg_dict, 'BET', 'Beta Coverage',
        cfg_dict['Date'].today({}) + datetime.timedelta(days=5))

#    coverage_b.pricing_mgr = []
    coverage_b.pricing_mgr.append(brm_b)

    coverage_a.pricing_mgr.append(brm_a)

    try_to_save_object(cfg_dict, coverage_a)
    try_to_save_object(cfg_dict, coverage_b)

    product_a.options.append(coverage_a)
    product_a.options.append(coverage_b)
    try_to_save_object(cfg_dict, product_a)


def get_or_create_tree_element(cfg_dict, cur_type, description, name=None,
        namespace=None):
    cur_domain = []
    if cur_type == 'function':
        cur_domain.append(('namespace', '=', namespace))
        cur_domain.append(('name', '=', name))
    if cur_type == 'folder':
        cur_domain.append(('name', '=', name))
    tree_element = get_object_from_db(cfg_dict, 'TreeElement',
        domain=cur_domain)
    if tree_element:
        return tree_element
    te = cfg_dict['TreeElement']()
    te.type = cur_type
    te.name = name
    te.description = description
    te.namespace = namespace
    try_to_save_object(cfg_dict, te)
    return te


def append_inexisting_elements(cur_object, list_name, the_list):
    to_set = False
    if hasattr(cur_object, list_name):
        cur_list = getattr(cur_object, list_name)
        if cur_list is None:
            cur_list = []
            to_set = True

    if not isinstance(the_list, (list, tuple)):
        the_list = [the_list]

    for child in the_list:
        if not child in cur_list:
            cur_list.append(child)

    if to_set:
        setattr(cur_object, list_name, cur_list)

    cur_object.save()
    return cur_object


def get_or_create_context(cfg_dict, name):
    ct = get_object_from_db(cfg_dict, 'Context', 'name', name)
    if ct:
        return ct
    ct = cfg_dict['Context']()
    ct.name = name
    try_to_save_object(cfg_dict, ct)
    return ct


def get_or_create_rule(cfg_dict, ct, name):
    rule = get_object_from_db(cfg_dict, 'RuleEngine', 'name', name)
    if rule:
        return rule
    rule = cfg_dict['RuleEngine']()
    rule.name = name
    rule.context = ct
    rule.code = '''
birthdate = get_person_birthdate()
if years_between(birthdate, today({})) > 40:
    message('Subscriber too old (max: 40)')
    return False
return True'''

    tcv = cfg_dict['TestCaseValue']()
    tcv.name = 'get_person_birthdate'
    tcv.value = 'datetime.date(2000, 11, 02)'

    tc = cfg_dict['TestCase']()
    tc.description = 'Test'
    tc.values.append(tcv)
    tc.expected_result = '(True, [], [])'

    tcv1 = cfg_dict['TestCaseValue']()
    tcv1.name = 'get_person_birthdate'
    tcv1.value = 'datetime.date(1950, 11, 02)'

    tc1 = cfg_dict['TestCase']()
    tc1.description = 'Test1'
    tc1.values.append(tcv1)
    tc1.expected_result = '(False, ["Subscriber too old (max: 40)"], [])'

    rule.test_cases.append(tc)
    rule.test_cases.append(tc1)

    try_to_save_object(cfg_dict, rule)

    return rule


def create_folder_from_set(cfg_dict, set_name, folder_name):
    the_set = Model.get(set_name)
    if not the_set:
        return
    functions = the_set.get_rules({})
    tes = []
    for fun in functions:
        cur_te = get_or_create_tree_element(
            cfg_dict, 'function', fun['rule_name'], fun['name'], set_name)
        tes.append(cur_te)
    te_top = get_or_create_tree_element(cfg_dict, 'folder', folder_name)
    append_inexisting_elements(te_top, 'children', tes)
    te_top.save()
    return te_top


def create_rule_engine_data(cfg_dict):
    tools = create_folder_from_set(
        cfg_dict,
        'rule_engine.tools_functions',
        'Tools')

    person = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.person',
        'Person')

    subscriber = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.subscriber',
        'Subscriber')

    data_coverage = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.covered_data',
        'Coverage Data')

    ct = get_or_create_context(cfg_dict, 'test_context')
    append_inexisting_elements(ct, 'allowed_elements', [tools, person])

    ct.save()

    return get_or_create_rule(cfg_dict, ct, 'test_rule')


def create_BBB_product(cfg_dict, code, name):
    product_b = get_or_create_product(cfg_dict, code, name)
    if product_b.id > 0:
        return product_b
    add_description(product_b)
    coverage = Model.get('ins_product.coverage')
    brm = Model.get('ins_product.business_rule_manager')
    gbr = Model.get('ins_product.generic_business_rule')

    rule = create_rule_engine_data(cfg_dict)

    coverage_a, = coverage.find([('code', '=', 'ALP')], limit=1)
    coverage_b, = coverage.find([('code', '=', 'BET')], limit=1)

    # Coverage C
    gbr_d = gbr()
    gbr_d.kind = 'ins_product.eligibility_rule'
    gbr_d.start_date = cfg_dict['Date'].today({})
    erm_a = gbr_d.eligibility_rule[0]
    erm_a.config_kind = 'rule'
    erm_a.is_eligible = False
    erm_a.rule = rule

    brm_c = brm()
    brm_c.business_rules.append(gbr_d)

    coverage_c = get_or_create_coverage(cfg_dict, 'GAM', 'Gamma Coverage')
    if not coverage_c.id > 0:
        coverage_c.eligibility_mgr.append(brm_c)
        try_to_save_object(cfg_dict, coverage_c)

    # Coverage D
    gbr_g = gbr()
    gbr_g.kind = 'ins_product.eligibility_rule'
    gbr_g.start_date = cfg_dict['Date'].today({})
    erm_d = gbr_g.eligibility_rule[0]
    erm_d.config_kind = 'simple'
    erm_d.is_eligible = True
    erm_d.is_sub_elem_eligible = False

    brm_f = brm()
    brm_f.business_rules.append(gbr_g)

    coverage_d = get_or_create_coverage(cfg_dict, 'DEL', 'Delta Coverage')
    if not coverage_d.id > 0:
        coverage_d.eligibility_mgr.append(brm_f)
        try_to_save_object(cfg_dict, coverage_d)

    # Product Eligibility Manager
    gbr_e = gbr()
    gbr_e.kind = 'ins_product.eligibility_rule'
    gbr_e.start_date = cfg_dict['Date'].today({})
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
    try_to_save_object(cfg_dict, product_b)


def get_or_create_currency(cfg_dict):
    currency = get_object_from_db(cfg_dict, 'Currency', 'code', 'EUR',
        force_search=True)
    if currency:
        return currency
    currency = cfg_dict['Currency']()
    currency.name = 'Euro'
    currency.symbol = u'€'
    currency.code = 'EUR'
    try_to_save_object(cfg_dict, currency)
    return currency


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    get_or_create_currency(cfg_dict)
    create_AAA_Product(cfg_dict, 'AAA', 'Awesome Alternative Allowance')
    create_BBB_product(cfg_dict, 'BBB', 'Big Bad Bully')
