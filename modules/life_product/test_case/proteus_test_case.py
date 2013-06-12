#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from decimal import Decimal
from proteus import Model
import proteus_tools
from trytond.modules.insurance_product.test_case import get_or_create_context
from trytond.modules.insurance_product.test_case import create_or_update_folder


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Currency'] = Model.get('currency.currency')
    cfg_dict['Coverage'] = Model.get('offered.coverage')
    cfg_dict['Product'] = Model.get('offered.product')
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
    cfg_dict['PricingComponent'] = Model.get('ins_product.pricing_component')
    cfg_dict['Sequence'] = Model.get('ir.sequence')
    cfg_dict['Lang'] = Model.get('ir.lang')
    cfg_dict['Benefit'] = Model.get('ins_product.benefit')
    cfg_dict['RuleEngine'] = Model.get('rule_engine')
    cfg_dict['Context'] = Model.get('rule_engine.context')
    cfg_dict['TreeElement'] = Model.get('rule_engine.tree_element')
    cfg_dict['Tranche'] = Model.get('tranche.tranche')
    cfg_dict['LossDesc'] = Model.get('ins_product.loss_desc')
    cfg_dict['ComplementaryData'] = Model.get(
        'offered.complementary_data_def')
    cfg_dict['ItemDesc'] = Model.get('ins_product.item_desc')
    return cfg_dict


def get_or_create_product(cfg_dict, code, name, coverages=None, date=None):
    product = proteus_tools.get_objects_from_db(cfg_dict,
        'Product', 'code', code)
    if product:
        return product
    product = cfg_dict['Product']()
    product.code = code
    product.name = name
    product.start_date = date if date else cfg_dict['Date'].today({})
    if coverages:
        product.coverages[:] = coverages
    product.contract_generator = get_or_create_generator(
        cfg_dict, 'offered.product')
    return product


def get_or_create_generator(cfg_dict, code):
    seq = proteus_tools.get_objects_from_db(cfg_dict, 'Sequence', 'code', code)
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


def get_or_create_benefit(
        cfg_dict, code, name, kind, date=None, calc_unit=None):
    benefit = proteus_tools.get_objects_from_db(
        cfg_dict, 'Benefit', 'code', code)
    if benefit:
        return benefit
    benefit = cfg_dict['Benefit']()
    benefit.code = code
    benefit.name = name
    benefit.start_date = date if date else cfg_dict['Date'].today({})
    benefit.indemnification_kind = kind
    benefit.indemnification_calc_unit = calc_unit
    return benefit


def get_or_create_loss_desc(
        cfg_dict, code, name, item_kind, with_end_date=True):
    loss_desc = proteus_tools.get_objects_from_db(
        cfg_dict, 'LossDesc', 'code', code)
    if loss_desc:
        return loss_desc
    loss_desc = cfg_dict['LossDesc']()
    loss_desc.code = code
    loss_desc.name = name
    loss_desc.with_end_date = with_end_date
    loss_desc.item_kind = item_kind
    loss_desc.save()
    return loss_desc


def get_or_create_item_desc(cfg_dict, code, name, kind):
    item_desc = proteus_tools.get_objects_from_db(
        cfg_dict, 'ItemDesc', 'code', code)
    if item_desc:
        return item_desc
    item_desc = cfg_dict['ItemDesc']()
    item_desc.code = code
    item_desc.name = name
    item_desc.kind = kind
    item_desc.save()
    return item_desc


def get_or_create_coverage(
        cfg_dict, code, name, date=None, family='life_product.definition'):
    coverage = proteus_tools.get_objects_from_db(
        cfg_dict, 'Coverage', 'code', code)
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
    coverage.insurer = proteus_tools.get_objects_from_db(
        cfg_dict, 'Insurer', force_search=True)
    return coverage


def get_or_create_tax(cfg_dict, code, name=None, vals=None):
    tax = proteus_tools.get_objects_from_db(cfg_dict, 'Tax', 'code', code)
    if tax:
        return tax
    tax = cfg_dict['Tax']()
    tax.code = code
    tax.name = name
    if vals:
        for val in vals:
            tax_ver = cfg_dict['TaxVersion']()
            tax_ver.start_date = val.get('start_date',
                cfg_dict['Date'].today({}))
            tax_ver.end_date = val.get('end_date', None)
            tax_ver.kind = val.get('kind', 'rate')
            tax_ver.value = Decimal(val.get('value', 0))
            tax.versions.append(tax_ver)
    tax.save()
    return tax


def get_or_create_fee(cfg_dict, code, name, vals=None):
    fee = proteus_tools.get_objects_from_db(cfg_dict, 'Fee', 'code', code)
    if fee:
        return fee
    fee = cfg_dict['Fee']()
    fee.code = code
    fee.name = name
    if vals:
        for val in vals:
            fee_ver = cfg_dict['FeeVersion']()
            fee_ver.start_date = val.get('start_date',
                cfg_dict['Date'].today({}))
            fee_ver.end_date = val.get('end_date', None)
            fee_ver.kind = val.get('kind', 'rate')
            fee_ver.value = Decimal(val.get('value', 0))
            fee.versions.append(fee_ver)
    fee.save()
    return fee


def get_or_create_complementary_data(cfg_dict, name, string=None, type_=None,
        kind=None, selection=None):
    name = cfg_dict['translate'].get(name, name)
    if string:
        string = cfg_dict['translate'].get(string, string)
    schema_el = proteus_tools.get_objects_from_db(cfg_dict,
        'ComplementaryData', 'name', name)
    if schema_el:
        return schema_el
    schema_el = cfg_dict['ComplementaryData']()
    schema_el.name = name
    schema_el.string = string
    schema_el.type_ = type_
    schema_el.kind = kind
    schema_el.selection = selection
    schema_el.save()
    return schema_el


def add_description(cfg_dict, product):
    if product.description:
        return product
    product.description = cfg_dict['translate']['product_life_description']


def create_AAA_Product(cfg_dict, code, name):
    product_a = get_or_create_product(cfg_dict, code, name)
    if product_a.id > 0:
        return product_a

    coverage_a = get_or_create_coverage(cfg_dict, 'ALP', 'Alpha Coverage')
    if coverage_a.id > 0:
        clean_rules(cfg_dict, coverage_a, 'pricing')
    tax = get_or_create_tax(
        cfg_dict, cfg_dict['translate']['IT'],
        cfg_dict['translate']['Insurance Tax'], [{'value': 15}])
    item_desc = get_or_create_item_desc(cfg_dict, 'person', 'Person', 'person')
    fee = get_or_create_fee(
        cfg_dict, 'FG', u'Frais de gestion', [{'value': 4}])

    pricing_rulea1 = create_pricing_rule(
        cfg_dict, coverage_a,
        config_kind='advanced', rated_object_kind='global', components=[
            {
                'kind': 'base',
                'code': 'PP',
                'config_kind': 'simple',
                'fixed_amount': Decimal(12),
            },
            {
                'kind': 'tax',
                'tax': tax,
                'config_kind': 'simple',
            },
            {
                'kind': 'fee',
                'fee': fee,
                'config_kind': 'simple',
            },
        ],
        end_date=cfg_dict['Date'].today({}) + datetime.timedelta(days=10))

    create_components(
        cfg_dict, pricing_rulea1, rated_object_kind='sub_item', components=[
            {
                'kind': 'base',
                'code': 'PP',
                'config_kind': 'simple',
                'fixed_amount': Decimal(1)
            }])

    create_pricing_rule(
        cfg_dict, coverage_a,
        config_kind='advanced', rated_object_kind='global', components=[
            {
                'kind': 'base',
                'code': 'PP',
                'config_kind': 'simple',
                'fixed_amount': Decimal(15),
            },
            {
                'kind': 'tax',
                'tax': tax,
                'config_kind': 'simple',
            },
        ],
        start_date=cfg_dict['Date'].today({}) + datetime.timedelta(days=11),
        end_date=cfg_dict['Date'].today({}) + datetime.timedelta(days=20))

    coverage_b = get_or_create_coverage(
        cfg_dict, 'BET', 'Beta Coverage',
        cfg_dict['Date'].today({}) + datetime.timedelta(days=5))
    if coverage_b.id > 0:
        clean_rules(cfg_dict, coverage_b, 'pricing')
    create_pricing_rule(
        cfg_dict, coverage_b,
        config_kind='advanced', rated_object_kind='global', components=[
            {
                'kind': 'base',
                'code': 'PP',
                'config_kind': 'simple',
                'fixed_amount': Decimal(30),
            },
        ],
        end_date=cfg_dict['Date'].today({}) + datetime.timedelta(days=10))

    coverage_a.item_desc = item_desc
    coverage_b.item_desc = item_desc
    proteus_tools.try_to_save_object(cfg_dict, coverage_a)
    proteus_tools.try_to_save_object(cfg_dict, coverage_b)

    product_a.coverages.append(coverage_a)
    product_a.coverages.append(coverage_b)
    product_a.item_descriptors.append(item_desc)

    product_a.contract_generator = get_or_create_generator(
        cfg_dict, 'offered.product')
    proteus_tools.try_to_save_object(cfg_dict, product_a)


def get_or_create_rule_for_birthdate_eligibility(cfg_dict, ct, name):
    rule = proteus_tools.get_objects_from_db(
        cfg_dict, 'RuleEngine', 'name', name)
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

    proteus_tools.try_to_save_object(cfg_dict, rule)

    return rule


def create_rule_engine_data(cfg_dict):
    create_or_update_folder(cfg_dict, 'ins_product.rule_sets.covered_data')


def create_BBB_product(cfg_dict, code, name):
    product_b = get_or_create_product(cfg_dict, code, name)
    if product_b.id > 0:
        return product_b
    coverage = Model.get('offered.coverage')

    rule = get_or_create_rule_for_birthdate_eligibility(
        cfg_dict, get_or_create_context(cfg_dict, 'Default Context'),
        'test_rule')

    coverage_a, = coverage.find([('code', '=', 'ALP')], limit=1)
    coverage_b, = coverage.find([('code', '=', 'BET')], limit=1)

    # Coverage C
    erm_a = Model.get('ins_product.eligibility_rule')()
    erm_a.start_date = cfg_dict['Date'].today({})
    erm_a.config_kind = 'advanced'
    erm_a.rule = rule

    coverage_c = get_or_create_coverage(cfg_dict, 'GAM', 'Gamma Coverage')
    if not coverage_c.id > 0:
        coverage_c.eligibility_rules.append(erm_a)
        proteus_tools.try_to_save_object(cfg_dict, coverage_c)

    # Coverage D
    erm_d = Model.get('ins_product.eligibility_rule')()
    erm_d.start_date = cfg_dict['Date'].today({})
    erm_d.config_kind = 'simple'
    erm_d.sub_min_age = 100

    coverage_d = get_or_create_coverage(cfg_dict, 'DEL', 'Delta Coverage')
    if not coverage_d.id > 0:
        coverage_d.eligibility_rules.append(erm_d)
        proteus_tools.try_to_save_object(cfg_dict, coverage_d)

    # Product Eligibility Manager
    erm_b = Model.get('ins_product.eligibility_rule')()
    erm_b.start_date = cfg_dict['Date'].today({})
    erm_b.config_kind = 'simple'

    # Product

    product_b.coverages.append(coverage_a)
    product_b.coverages.append(coverage_b)
    product_b.coverages.append(coverage_c)
    product_b.coverages.append(coverage_d)
    product_b.eligibility_rules.append(erm_b)
    product_b.contract_generator = get_or_create_generator(
        cfg_dict, 'offered.product')
    proteus_tools.try_to_save_object(cfg_dict, product_b)


def get_or_create_currency(cfg_dict):
    currency = proteus_tools.get_objects_from_db(
        cfg_dict, 'Currency', 'code', 'EUR', force_search=True)
    if currency:
        return currency
    currency = cfg_dict['Currency']()
    currency.name = 'Euro'
    currency.symbol = u'€'
    currency.code = 'EUR'
    proteus_tools.try_to_save_object(cfg_dict, currency)
    return currency


def get_module_name(instance):
    return instance.__class__.__name__.split('.')[0]


def add_rule(cfg_dict, offered, kind, at_date=None, end_date=None):
    if not at_date:
        at_date = cfg_dict['Date'].today({})
    res = Model.get('ins_product.%s_rule' % kind)()
    res.start_date = at_date
    res.end_date = end_date
    rules = getattr(offered, '%s_rules' % kind)
    rules.append(res)
    return res


def clean_rules(cfg_dict, offered, kind):
    RuleModel = Model.get('ins_product.%s_rule' % kind)
    for elem in getattr(offered, '%s_rules' % kind):
        RuleModel.delete(elem)


def create_components(
        cfg_dict, pricing_rule, rated_object_kind='global',
        combi_rule=None, components=None):

    prefix = '%s_' % rated_object_kind if rated_object_kind != 'global' else ''
    setattr(pricing_rule, '%sspecific_combination_rule' % prefix, combi_rule)
    cur_list = getattr(pricing_rule, '%scomponents' % prefix)
    for comp_dict in components if components else []:
        component = cfg_dict['PricingComponent']()
        cur_list.append(component)
        component.rated_object_kind = rated_object_kind
        for key, value in comp_dict.iteritems():
            setattr(component, key, value)
    return pricing_rule


def create_pricing_rule(
        cfg_dict, cov, config_kind='simple',
        rated_object_kind='global', combi_rule=None, basic_price=None,
        basic_tax=None, components=None, start_date=None, end_date=None):

    res = add_rule(
        cfg_dict, cov, 'pricing', at_date=start_date, end_date=end_date)
    res.config_kind = config_kind
    res.basic_price = basic_price
    res.basic_tax = basic_tax
    create_components(
        cfg_dict, res, rated_object_kind, combi_rule, components)
    return res


def create_disability_coverage(cfg_dict):
    at_date = datetime.date(2011, 1, 1)
    cov = get_or_create_coverage(
        cfg_dict, 'INCAP', u'Incapacité', date=at_date)
    if cov.id > 0:
        clean_rules(cfg_dict, cov, 'coverage_amount')
        cov.reload()
    item_desc = get_or_create_item_desc(cfg_dict, 'person', 'Person', 'person')
    cov.item_desc = item_desc
    ca_rule = add_rule(
        cfg_dict, cov, 'coverage_amount', at_date,
        end_date=datetime.date(2011, 12, 31))
    ca_rule.amounts = '40;90;140;190'

    at_date = datetime.date(2012, 1, 1)
    ca_rule = add_rule(
        cfg_dict, cov, 'coverage_amount', at_date,
        end_date=datetime.date(2012, 12, 31))
    ca_rule.amounts = '50;100;150;200'

    at_date = datetime.date(2013, 1, 1)
    ca_rule = add_rule(cfg_dict, cov, 'coverage_amount', at_date)
    ca_rule.amounts = '60;110;160;210'

    elig_rule = add_rule(cfg_dict, cov, 'eligibility')
    elig_rule.min_age = 18
    elig_rule.max_age = 65

    fee = get_or_create_fee(
        cfg_dict, 'FG', u'Frais de gestion', [{'value': 4}])
    tax = get_or_create_tax(cfg_dict, 'TSCA')

    code = '''
PP = valeur_de_composante('PP')
ajouter_detail('PP', PP)

RA = valeur_de_composante('RA')
ajouter_detail('RA', RA)

Tax = appliquer_taxe('TSCA', PP + RA)
ajouter_detail('TSCA', Tax)

FG = appliquer_frais('FG', PP)
ajouter_detail('FG', FG)

return PP + FG + RA + Tax
'''
    combination_rule = get_or_create_rule(
        cfg_dict, u'Règle de combinaison', code, 'Rule Combination')
    create_pricing_rule(
        cfg_dict, cov, config_kind='advanced',
        rated_object_kind='global', combi_rule=combination_rule,
        components=[
            {
                'kind': 'base',
                'code': 'PP',
                'config_kind': 'simple',
                'fixed_amount': Decimal(5),
            },
            {
                'kind': 'base',
                'code': 'RA',
                'config_kind': 'simple',
                'fixed_amount': Decimal(2),
            },
            {
                'kind': 'tax',
                'tax': tax,
                'config_kind': 'simple',
            },
            {
                'kind': 'fee',
                'fee': fee,
                'config_kind': 'simple',
            },
        ])

    benefit = get_or_create_benefit(
        cfg_dict, 'IJ', 'Indémnité Journalière', kind='period',
        calc_unit='day')
    loss_desc = get_or_create_loss_desc(
        cfg_dict, 'WI', 'Arrêt de travail', 'person')
    benefit.loss_descs.append(loss_desc)
    add_rule(cfg_dict, benefit, 'benefit')
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
    cov = get_or_create_coverage(
        cfg_dict, 'INVAL', u'Invalidité', date=at_date)
    item_desc = get_or_create_item_desc(cfg_dict, 'person', 'Person', 'person')
    cov.item_desc = item_desc
    CSP = get_or_create_complementary_data(cfg_dict, name='CSP')
    salary = get_or_create_complementary_data(
        cfg_dict, name='salary', string='Annual Salary', type_='numeric',
        kind='sub_elem')
    cov.complementary_data_def.append(CSP)
    cov.complementary_data_def.append(salary)

    elig_rule = add_rule(cfg_dict, cov, 'eligibility')
    elig_rule.min_age = 18
    elig_rule.max_age = 65

    algo = '''salaire = donnee_compl_element_couvert('salaire')
if donnee_compl_element_couvert('CSP') == 'CSP1':
    return salaire * 0.0002
else:
    return salaire * 0.0001
'''
    rule_engine = get_or_create_rule(
        cfg_dict, u'Tarif CSP', algo, 'Default Context')
    create_pricing_rule(
        cfg_dict, cov, config_kind='advanced', rated_object_kind='sub_item',
        components=[
            {
                'kind': 'base',
                'code': 'PP',
                'config_kind': 'advanced',
                'rule': rule_engine,
            },
            {
                'kind': 'tax',
                'tax': get_or_create_tax(cfg_dict, 'TSCA'),
                'config_kind': 'simple',
            },
        ])

    benefit = get_or_create_benefit(
        cfg_dict, 'RENT_INVAL', 'Rente d\'invalidité', kind='annuity',
        calc_unit='quarter')
    loss_desc = get_or_create_loss_desc(
        cfg_dict, 'DY', 'Invalidité', 'person')
    benefit.loss_descs.append(loss_desc)
    add_rule(cfg_dict, benefit, 'benefit')
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
    item_desc = get_or_create_item_desc(cfg_dict, 'person', 'Person', 'person')
    cov.item_desc = item_desc

    cov.complementary_data_def.append(
        get_or_create_complementary_data(cfg_dict, name='is_vip'))

    ca_rule = add_rule(cfg_dict, cov, 'coverage_amount')
    ca_rule.kind = 'cal_list'
    ca_rule.amount_start = Decimal(25000)
    ca_rule.amount_end = Decimal(100000)
    ca_rule.amount_step = Decimal(25000)

    elig_rule = add_rule(cfg_dict, cov, 'eligibility')
    elig_rule.min_age = 18
    elig_rule.max_age = 65

    algo = '''esperance = table_MORTAL(annees_entre(\
date_de_naissance(),aujourd_hui()), 'Les deux sexes')

result = montant_de_couverture() * (100 - esperance) / 100 * 0.008
if donnee_compl_contrat('est_vip'):
    result = 0.9 * result
return result
'''
    rule_engine = get_or_create_rule(
        cfg_dict, u'2% du Montant de couverture et 10% de reduc pour VIP',
        algo, 'Default Context')
    create_pricing_rule(
        cfg_dict, cov, config_kind='advanced', rated_object_kind='sub_item',
        components=[
            {
                'kind': 'base',
                'code': 'PP',
                'config_kind': 'advanced',
                'rule': rule_engine,
            },
            {
                'kind': 'tax',
                'tax': get_or_create_tax(cfg_dict, 'TSCA'),
                'config_kind': 'simple',
            },
        ])

    capital_benefit = get_or_create_benefit(
        cfg_dict, 'CAP_DC', 'Capital Décès', kind='capital')
    benefit_rule = add_rule(cfg_dict, capital_benefit, 'benefit')
    loss_desc = get_or_create_loss_desc(
        cfg_dict, 'DH', 'Décès', 'person')
    capital_benefit.loss_descs.append(loss_desc)
    cov.benefits.append(capital_benefit)

    annuity_benefit = get_or_create_benefit(
        cfg_dict, 'RENT_CJ', 'Rente de conjoint', kind='annuity',
        calc_unit='quarter')
    benefit_rule = add_rule(cfg_dict, annuity_benefit, 'benefit')
    benefit_rule.coef_coverage_amount = Decimal(1 / (10 * 12))
    loss_desc = get_or_create_loss_desc(
        cfg_dict, 'DH', 'Décès', 'person')
    annuity_benefit.loss_descs.append(loss_desc)
    cov.benefits.append(annuity_benefit)

    annuity__edu_benefit = get_or_create_benefit(
        cfg_dict, 'RENT_EDU', 'Rente éducation', kind='annuity',
        calc_unit='quarter')
    benefit_rule = add_rule(cfg_dict, annuity__edu_benefit, 'benefit')
    benefit_rule.coef_coverage_amount = Decimal(1 / (10 * 12 * 4))
    loss_desc = get_or_create_loss_desc(
        cfg_dict, 'DH', 'Décès', 'person')
    annuity__edu_benefit.loss_descs.append(loss_desc)
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
    if proteus_tools.get_objects_from_db(cfg_dict, 'Product', 'code', 'PREV'):
        return
    at_date = datetime.date(2011, 1, 1)
    disability = create_disability_coverage(cfg_dict)
    death = create_death_coverage(cfg_dict)
    inval = create_invalidity_coverage(cfg_dict)
    prod = get_or_create_product(cfg_dict, 'PREV', u'Prévoyance Indviduelle',
        coverages=[death, inval, disability], date=at_date)
    add_description(cfg_dict, prod)
    item_desc = get_or_create_item_desc(cfg_dict, 'person', 'Person', 'person')
    prod.item_descriptors.append(item_desc)
    prod.save()
    return prod


def get_or_create_rule(cfg_dict, name, algo, context_name=None):
    rule = proteus_tools.get_objects_from_db(
        cfg_dict, 'RuleEngine', 'name', name)
    if rule:
        return rule
    rule = cfg_dict['RuleEngine']()
    rule.name = name
    rule.context = get_or_create_context(cfg_dict, context_name)
    rule.code = algo
    rule.save()
    return rule


def get_tree_element(cfg_dict, name=None, table_code=None):
    domain = []
    if name:
        domain.append(('name', '=', name))
    if table_code:
        domain.append(('the_table.code', '=', table_code))
    elements = cfg_dict['TreeElement'].find(domain, limit=1)
    if elements:
        return elements[0]


def write_ceiling_code(pss_multiplicator, pss_element):
    res = 'PMSS = %s(date_de_calcul())\n' % (
        pss_element.translated_technical_name)
    res += 'return %s * PMSS\n' % pss_multiplicator
    return res


def get_or_create_tranche(cfg_dict, code, floor=None, ceiling=None):
    res = proteus_tools.get_objects_from_db(cfg_dict, 'Tranche', 'code', code)
    if res:
        return res
    res = cfg_dict['Tranche']()
    res.code = code
    for tranche_version in res.versions:
        tranche_version.floor = floor
        tranche_version.ceiling = ceiling
    res.save()
    return res


def create_tranches(cfg_dict, pss_code):
    pss = get_tree_element(cfg_dict, table_code=pss_code)
    if not pss:
        print 'Impossible to find tree element and/or table %s' % pss_code
        return
    TA = get_or_create_rule(cfg_dict, 'Plafond TA', write_ceiling_code(1, pss))
    TB = get_or_create_rule(cfg_dict, 'Plafond TB', write_ceiling_code(4, pss))
    TC = get_or_create_rule(cfg_dict, 'Plafond TC', write_ceiling_code(8, pss))
    T2 = get_or_create_rule(cfg_dict, 'Plafond T2', write_ceiling_code(3, pss))

    get_or_create_tranche(cfg_dict, 'TA', ceiling=TA)
    get_or_create_tranche(cfg_dict, 'TB', floor=TA, ceiling=TB)
    get_or_create_tranche(cfg_dict, 'TC', floor=TB, ceiling=TC)
    get_or_create_tranche(cfg_dict, 'TD', floor=TC)
    get_or_create_tranche(cfg_dict, 'T1', ceiling=TA)
    get_or_create_tranche(cfg_dict, 'T2', floor=TA, ceiling=T2)


def create_shared_complementary_data(cfg_dict):
    get_or_create_complementary_data(
        cfg_dict, name='is_vip', string='Is VIP', type_='boolean',
        kind='contract')
    get_or_create_complementary_data(
        cfg_dict, name='salary', string='Annual Salary', type_='numeric',
        kind='sub_elem')
    get_or_create_complementary_data(
        cfg_dict, name='CSP', string='CSP', type_='selection',
        kind='sub_elem', selection='''CSP1: CSP1
CSP2: CSP2
CSP3: CSP3
CSP4: CSP4
''')


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    get_or_create_currency(cfg_dict)
    create_shared_complementary_data(cfg_dict)
    create_rule_engine_data(cfg_dict)
    create_AAA_Product(cfg_dict, 'AAA', 'Awesome Alternative Allowance')
    #create_BBB_product(cfg_dict, 'BBB', 'Big Bad Bully')
    create_prev_product(cfg_dict)
    create_tranches(cfg_dict, 'PMSS')
