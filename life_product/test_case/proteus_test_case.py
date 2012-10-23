#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import ConfigParser
import os

from decimal import Decimal
from proteus import Model

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


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
    cfg_dict['Fee'] = Model.get('coop_account.fee_desc')
    cfg_dict['FeeVersion'] = Model.get('coop_account.fee_version')
    cfg_dict['PricingData'] = Model.get('ins_product.pricing_data')
    cfg_dict['Calculator'] = Model.get('ins_product.pricing_calculator')
    cfg_dict['Sequence'] = Model.get('ir.sequence')
    cfg_dict['BRM'] = Model.get('ins_product.business_rule_manager')
    cfg_dict['GBR'] = Model.get('ins_product.generic_business_rule')
    cfg_dict['Lang'] = Model.get('ir.lang')
    cfg_dict['Benefit'] = Model.get('ins_product.benefit')
    return cfg_dict


def get_or_create_product(cfg_dict, code, name, options=None, date=None):
    product = get_object_from_db(cfg_dict, 'Product', 'code', code)
    if product:
        return product
    product = cfg_dict['Product']()
    product.code = code
    product.name = name
    product.start_date = date if date else cfg_dict['Date'].today({})
    if options:
        product.options[:] = options
    product.contract_generator = get_or_create_generator(
        cfg_dict, 'ins_product.product')
    return product


def get_or_create_generator(cfg_dict, code):
    seq = get_object_from_db(cfg_dict, 'Sequence', 'code', code)
    if seq:
        return seq
    seq = cfg_dict['Sequence']()
    seq.name = 'Contract Sequence'
    seq.code = code
    seq.prefix = 'Ctr'
    seq.suffix = 'Y${year}'
    seq.padding = 10
    seq.save()
    return seq


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


def get_or_create_benefit(cfg_dict, code, name, kind=None, date=None):
    benefit = get_object_from_db(cfg_dict, 'Benefit', 'code', code)
    if benefit:
        return benefit
    benefit = cfg_dict['Benefit']()
    benefit.code = code
    benefit.name = name
    benefit.start_date = date if date else cfg_dict['Date'].today({})
    if kind:
        benefit.kind = kind
    return benefit


def try_to_save_object(cfg_dict, cur_object):
    if not cfg_dict['re_create_if_already_exists']:
        cur_object.save()
    #if we try to save one object which already exists, we could have error
    #with constraints
    try:
        cur_object.save()
    except:
        print 'Exception raised when trying to save', cur_object


def get_or_create_coverage(cfg_dict, code, name, date=None,
        family='life_product.definition'):
    coverage = get_object_from_db(cfg_dict, 'Coverage', 'code', code)
    if coverage:
        return coverage
    coverage = cfg_dict['Coverage']()
    coverage.code = code
    coverage.name = name
    coverage.family = family
    if date:
        coverage.start_date = date
    else:
        coverage.start_date = cfg_dict['Date'].today({})
    coverage.insurer = get_object_from_db(cfg_dict, 'Insurer',
        force_search=True)
    return coverage


def get_or_create_tax(cfg_dict, code, name=None, vals=None):
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


def get_or_create_fee(cfg_dict, code, name, vals=None):
    fee = get_object_from_db(cfg_dict, 'Fee', 'code', code)
    if fee:
        return fee
    fee = cfg_dict['Fee']()
    fee.code = code
    fee.name = name
    if vals:
        for val in vals:
            fee_ver = cfg_dict['FeeVersion']()
            fee_ver.start_date = val.get('start_date', None)
            fee_ver.end_date = val.get('end_date', None)
            fee_ver.kind = val.get('kind', 'None')
            fee_ver.value = Decimal(val.get('value', 0))
            fee.versions.append(fee_ver)
    fee.save()
    return fee


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
    brm = Model.get('ins_product.business_rule_manager')
    gbr = Model.get('ins_product.generic_business_rule')

    gbr_a = gbr()
    gbr_a.kind = 'ins_product.pricing_rule'
    gbr_a.start_date = cfg_dict['Date'].today({})
    gbr_a.end_date = cfg_dict['Date'].today({}) + \
                                    datetime.timedelta(days=10)

    pr_data1 = cfg_dict['PricingData']()
    pr_data1.config_kind = 'simple'
    pr_data1.fixed_amount = Decimal(12)
    pr_data1.kind = 'base'
    pr_data1.code = 'PP'

    tax = get_or_create_tax(cfg_dict,
        'CCSS',
        u'Contribution prévue par le Code de la Sécurité sociale',
        [
            {'start_date': cfg_dict['Date'].today({}),
            'kind': 'rate',
            'value': 15}])

    pr_data11 = cfg_dict['PricingData']()
    pr_data11.kind = 'tax'
    pr_data11.the_tax = tax

    fee = get_or_create_fee(cfg_dict,
        'FG',
        u'Frais de gestion',
        [
            {'start_date': cfg_dict['Date'].today({}),
            'kind': 'rate',
            'value': 4}])

    pr_data12 = cfg_dict['PricingData']()
    pr_data12.kind = 'fee'
    pr_data12.the_fee = fee

    pr_calc1 = cfg_dict['Calculator']()
    pr_calc1.data.append(pr_data1)
    pr_calc1.data.append(pr_data11)
    pr_calc1.data.append(pr_data12)
    pr_calc1.key = 'price'

    pr_data2 = cfg_dict['PricingData']()
    pr_data2.config_kind = 'simple'
    pr_data2.fixed_amount = Decimal(1)
    pr_data2.kind = 'base'
    pr_data2.code = 'PP'

    pr_calc2 = cfg_dict['Calculator']()
    pr_calc2.data.append(pr_data2)
    pr_calc2.key = 'sub_price'

    prm_a = gbr_a.pricing_rule[0]
    prm_a.config_kind = 'rule'
    prm_a.calculators.append(pr_calc1)
    prm_a.calculators.append(pr_calc2)

    gbr_b = gbr()
    gbr_b.kind = 'ins_product.pricing_rule'
    gbr_b.start_date = cfg_dict['Date'].today({}) + \
                                    datetime.timedelta(days=11)
    gbr_b.end_date = cfg_dict['Date'].today({}) + \
                                    datetime.timedelta(days=20)

    pr_data3 = cfg_dict['PricingData']()
    pr_data3.config_kind = 'simple'
    pr_data3.fixed_amount = Decimal(15)
    pr_data3.kind = 'base'
    pr_data3.code = 'PP'

    pr_data31 = cfg_dict['PricingData']()
    pr_data31.kind = 'tax'
    pr_data31.the_tax = tax

    pr_calc3 = cfg_dict['Calculator']()
    pr_calc3.data.append(pr_data3)
    pr_calc3.data.append(pr_data31)
    pr_calc3.key = 'price'

    prm_b = gbr_b.pricing_rule[0]
    prm_a.config_kind = 'rule'
    prm_b.calculators.append(pr_calc3)

    brm_a = brm()
    brm_a.business_rules.append(gbr_a)
    brm_a.business_rules.append(gbr_b)

    coverage_a = get_or_create_coverage(cfg_dict, 'ALP', 'Alpha Coverage')
    gbr_c = gbr()
    gbr_c.kind = 'ins_product.pricing_rule'
    gbr_c.start_date = cfg_dict['Date'].today({})
    gbr_c.end_date = cfg_dict['Date'].today({}) + \
                                    datetime.timedelta(days=10)

    pr_data4 = cfg_dict['PricingData']()
    pr_data4.config_kind = 'simple'
    pr_data4.fixed_amount = Decimal(30)
    pr_data4.kind = 'base'
    pr_data4.code = 'PP'

    pr_calc4 = cfg_dict['Calculator']()
    pr_calc4.data.append(pr_data4)
    pr_calc4.key = 'price'

    prm_c = gbr_c.pricing_rule[0]
    prm_a.config_kind = 'rule'
    prm_c.calculators.append(pr_calc4)

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

    product_a.contract_generator = get_or_create_generator(
        cfg_dict, 'ins_product.product')
    try_to_save_object(cfg_dict, product_a)


def get_or_create_tree_element(cfg_dict, cur_type, description,
        translated_technical, name=None, namespace=None):
    cur_domain = []
    if cur_type == 'function':
        cur_domain.append(('namespace', '=', namespace))
        cur_domain.append(('name', '=', name))
    if cur_type == 'folder':
        cur_domain.append(('name', '=', name))
    cur_domain.append(('language.code', '=', cfg_dict['language']))
    cur_domain.append(('translated_technical_name', '=', translated_technical))
    tree_element = get_object_from_db(cfg_dict, 'TreeElement',
        domain=cur_domain)
    if tree_element:
        return tree_element
    lang = cfg_dict['Lang'].find([('code', '=', cfg_dict['language'])])[0]
    te = cfg_dict['TreeElement']()
    te.type = cur_type
    te.name = name
    te.description = description
    te.translated_technical_name = translated_technical
    te.namespace = namespace
    te.language = lang
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
birthdate = date_de_naissance()
if annees_entre(birthdate, aujourd_hui({})) > 40:
    ajouter_message('Subscriber too old (max: 40)')
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


def create_folder_from_set(cfg_dict, set_name, descs):
    the_set = Model.get(set_name)
    if not the_set:
        return
    functions = the_set.get_rules({})
    tes = []
    for fun in functions:
        full_name = set_name + '.' + fun['name']
        cur_te = get_or_create_tree_element(
            cfg_dict, 'function', descs[full_name + '.desc'],
            descs[full_name + '.tech_name'], fun['name'], set_name)
        tes.append(cur_te)
    te_top = get_or_create_tree_element(
        cfg_dict, 'folder', descs[set_name + '.desc'],
        descs[set_name + '.tech_name'])
    append_inexisting_elements(te_top, 'children', tes)
    te_top.save()
    return te_top


def get_file_as_dict(filename):
    cfg_parser = ConfigParser.ConfigParser()
    with open(filename) as fp:
        cfg_parser.readfp(fp)
    cfg_dict = dict(cfg_parser.items('tree_name'))
    return cfg_dict


def create_rule_engine_data(cfg_dict):
    path = os.path.join(DIR, cfg_dict.get('language', 'fr')[0:2].lower())
    descs = get_file_as_dict(os.path.join(path, 'tree_names'))
    tools = create_folder_from_set(
        cfg_dict,
        'rule_engine.tools_functions',
        descs)

    person = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.person',
        descs)

    subscriber = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.subscriber',
        descs)

    contract = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.contract',
        descs)

    option = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.option',
        descs)

    data_coverage = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.covered_data',
        descs)

    rule_combination = create_folder_from_set(
        cfg_dict,
        'ins_product.rule_sets.rule_combination',
        descs)

    ct = get_or_create_context(cfg_dict, 'Default Context')
    append_inexisting_elements(ct, 'allowed_elements', [tools, person])

    ct.save()

    return get_or_create_rule(cfg_dict, ct, 'test_rule')


def create_BBB_product(cfg_dict, code, name):
    product_b = get_or_create_product(cfg_dict, code, name)
    if product_b.id > 0:
        return product_b
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
    erm_d.sub_min_age = 100

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

    brm_d = brm()
    brm_d.business_rules.append(gbr_e)

    # Product

    product_b.options.append(coverage_a)
    product_b.options.append(coverage_b)
    product_b.options.append(coverage_c)
    product_b.options.append(coverage_d)
    product_b.eligibility_mgr.append(brm_d)
    product_b.contract_generator = get_or_create_generator(
        cfg_dict, 'ins_product.product')
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


def get_module_name(instance):
    return instance.__class__.__name__.split('.')[0]


def add_rule(cfg_dict, offered, kind, at_date=None):
    if not at_date:
        at_date = cfg_dict['Date'].today({})
    mgr_list = getattr(offered, '%s_mgr' % kind)
    if len(mgr_list) == 0:
        mgr = cfg_dict['BRM']()
        mgr_list.append(mgr)
    mgr = mgr_list[-1]

    gbr = cfg_dict['GBR']()
    gbr.start_date = at_date
    mgr.business_rules.append(gbr)
    model_name = '%s.%s_rule' % (get_module_name(offered), kind)
    gbr.kind = model_name
    rule = getattr(gbr, '%s_rule' % kind)[0]
    return rule


def create_disability_coverage(cfg_dict):
    at_date = datetime.date(2011, 1, 1)
    cov = get_or_create_coverage(cfg_dict, 'INCAP', u'Incapacité',
        date=at_date)

    ca_rule = add_rule(cfg_dict, cov, 'coverage_amount', at_date)
    ca_rule.amounts = '40;90;140;190'

    at_date = datetime.date(2012, 1, 1)
    ca_rule = add_rule(cfg_dict, cov, 'coverage_amount', at_date)
    ca_rule.amounts = '50;100;150;200'

    at_date = datetime.date(2013, 1, 1)
    ca_rule = add_rule(cfg_dict, cov, 'coverage_amount', at_date)
    ca_rule.amounts = '60;110;160;210'

    elig_rule = add_rule(cfg_dict, cov, 'eligibility')
    elig_rule.min_age = 18
    elig_rule.max_age = 65

    pricing_rule = add_rule(cfg_dict, cov, 'pricing')
    pricing_rule.basic_price = Decimal(5)
    pricing_rule.basic_tax = get_or_create_tax(cfg_dict, 'TSCA')

    benefit = get_or_create_benefit(cfg_dict, 'IJ',
        'Indémnité Journalière', 'per_diem')
    benefit_rule = add_rule(cfg_dict, benefit, 'benefit')
    cov.benefits.append(benefit)

    cov.description = '''<b>En cas d’arrêt de travail temporaire ou prolongé, \
maintenez votre salaire à 100 %</b>
En cas d’arrêt de travail, seuls 50 % de vos revenus vous sont versés par \
la Sécurité Sociale. Pour maintenir votre revenu et continuer à vivre \
normalement, uneindemnité journalière complète intégralement celle de votre \
régime obligatoire jusqu’au 1095ème jour (3 ans, délai après lequel vous êtes \
considéré comme invalide).'''
    cov.save()
    return cov


def create_invalidity_coverage(cfg_dict):
    at_date = datetime.date(2011, 1, 1)
    cov = get_or_create_coverage(cfg_dict, 'INVAL', u'Invalidité',
        date=at_date)

    ca_rule = add_rule(cfg_dict, cov, 'coverage_amount', at_date)
    ca_rule.amounts = '0'

    elig_rule = add_rule(cfg_dict, cov, 'eligibility')
    elig_rule.min_age = 18
    elig_rule.max_age = 65

    pricing_rule = add_rule(cfg_dict, cov, 'pricing')
    pricing_rule.basic_price = Decimal(5)
    pricing_rule.basic_tax = get_or_create_tax(cfg_dict, 'TSCA')

    benefit = get_or_create_benefit(cfg_dict, 'RENT_INVAL',
        'Rente d\'invalidité', 'annuity')
    benefit_rule = add_rule(cfg_dict, benefit, 'benefit')
    cov.benefits.append(benefit)

    cov.description = '''<b>En cas d’invalidité, votre pouvoir d’achat est \
préservé</b>
Vous risquez de ne plus pouvoir exercer votre emploi. Nous complétons \
votre rente de la Sécurité Sociale par une rente d’invalidité, jusqu’à votre \
retraite (au plus tard jusqu’à votre 60ème anniversaire).'''
    cov.save()
    return cov


def create_death_coverage(cfg_dict):
    at_date = datetime.date(2011, 1, 1)
    cov = get_or_create_coverage(cfg_dict, 'DC', u'Décès', date=at_date)
    ca_rule = add_rule(cfg_dict, cov, 'coverage_amount')
    ca_rule.kind = 'cal_list'
    ca_rule.amount_start = Decimal(25000)
    ca_rule.amount_end = Decimal(100000)
    ca_rule.amount_step = Decimal(25000)

    elig_rule = add_rule(cfg_dict, cov, 'eligibility')

    pricing_rule = add_rule(cfg_dict, cov, 'pricing')
    pricing_rule.basic_price = Decimal(5)
    pricing_rule.basic_tax = get_or_create_tax(cfg_dict, 'TSCA')

    capital_benefit = get_or_create_benefit(cfg_dict, 'CAP_DC',
        'Capital Décès', 'capital')
    benefit_rule = add_rule(cfg_dict, capital_benefit, 'benefit')
    cov.benefits.append(capital_benefit)

    annuity_benefit = get_or_create_benefit(cfg_dict, 'RENT_CJ',
        'Rente de conjoint', 'annuity')
    benefit_rule = add_rule(cfg_dict, annuity_benefit, 'benefit')
    benefit_rule.coef_coverage_amount = Decimal(1 / (10 * 12))
    cov.benefits.append(annuity_benefit)

    annuity__edu_benefit = get_or_create_benefit(cfg_dict, 'RENT_EDU',
        'Rente éducation', 'annuity')
    benefit_rule = add_rule(cfg_dict, annuity__edu_benefit, 'benefit')
    benefit_rule.coef_coverage_amount = Decimal(1 / (10 * 12 * 4))
    cov.benefits.append(annuity__edu_benefit)

    cov.description = '''<b>En cas de décès ou de Perte Totale et Irréversible\
 d’Autonomie</b>, l’avenir de vos proches est assuré Des garanties financières\
 pour votre foyer :
<b>• Capital décès</b>
Vous mettez vos proches à l’abri des soucis financiers.Vous choisissez \
librement le montant du capital qui peut aller jusqu’à 600 000 € \
et n’est pas imposable dans la limite de 152 500 € \
(selon la réglementation en vigueur).
<b>• Rente de conjoint</b>
Une rente plafonnée à 20 000 € par an est versée jusqu’au 65ème anniversaire \
du conjoint ou concubin.Vous avez la certitude que votre conjoint bénéficiera \
d’un complément de revenu régulier jusqu’à sa retraite.
<b>• Rente éducation</b>
Vous donnez les moyens de garantir à vos enfants le financement de leurs\
études quoiqu’il arrive.Vos enfants perçoivent une rente pouvant atteindre\
4 500 € par an et ce, jusqu’à la fin de leurs études (au plus tard jusqu’à leur
26ème anniversaire).'''
    cov.save()
    return cov


def create_prev_product(cfg_dict):
    if get_object_from_db(cfg_dict, 'Product', 'code', 'PREV'):
        return
    at_date = datetime.date(2011, 1, 1)
    disability = create_disability_coverage(cfg_dict)
    death = create_death_coverage(cfg_dict)
    inval = create_invalidity_coverage(cfg_dict)
    prod = get_or_create_product(cfg_dict, 'PREV', u'Prévoyance Indviduelle',
        options=[death, inval, disability], date=at_date)
    add_description(prod)
    prod.save()
    return prod


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    get_or_create_currency(cfg_dict)
    create_AAA_Product(cfg_dict, 'AAA', 'Awesome Alternative Allowance')
    create_BBB_product(cfg_dict, 'BBB', 'Big Bad Bully')
    create_prev_product(cfg_dict)
