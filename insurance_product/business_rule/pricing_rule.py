#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool
from trytond.pyson import Eval, Or, Bool

from trytond.modules.coop_utils import utils, date, model, fields
from trytond.modules.insurance_product.product import DEF_CUR_DIG, CONFIG_KIND
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE, STATE_ADVANCED

__all__ = [
    'SimplePricingRule',
    'PricingRule',
    'PricingComponent',
]

PRICING_LINE_KINDS = [
    ('base', 'Base Price'),
    ('tax', 'Tax'),
    ('fee', 'Fee')
]

PRICING_FREQUENCY = [
    ('yearly', 'Yearly'),
    ('half-yearly', 'Half Yearly'),
    ('quarterly', 'Quarterly'),
    ('monthly', 'Monthly')
]

RATED_OBJECT_KIND = [
    ('global', 'Global'),
    ('sub_item', 'Covered Item'),
]


class SimplePricingRule(BusinessRuleRoot):
    'Simple Pricing Rule'

    __name__ = 'ins_product.simple_pricing_rule'

    @staticmethod
    def default_frequency():
        return 'yearly'


class PricingRule(SimplePricingRule, model.CoopSQL):
    'Pricing Rule'

    __name__ = 'ins_product.pricing_rule'

    components = fields.One2ManyDomain(
        'ins_product.pricing_component', 'pricing_rule', 'Components',
        domain=[('rated_object_kind', '=', 'global')],
        states={'invisible': STATE_ADVANCED})
    sub_item_components = fields.One2ManyDomain(
        'ins_product.pricing_component',
        'pricing_rule', 'Covered Item Components',
        domain=[('rated_object_kind', '=', 'sub_item')])
    frequency = fields.Selection(
        PRICING_FREQUENCY, 'Rate Frequency', required=True)
    specific_combination_rule = fields.Many2One(
        'rule_engine', 'Combination Rule',
        states={'invisible': STATE_ADVANCED})
    sub_item_specific_combination_rule = fields.Many2One(
        'rule_engine', 'Sub Item Combination Rule')
    basic_price = fields.Function(
        fields.Numeric(
            'Amount', states={'invisible': STATE_SIMPLE},
            digits=(
                16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG))),
        'get_basic_price',
        'set_basic_price')
    basic_tax = fields.Function(
        fields.Many2One(
            'coop_account.tax_desc', 'Tax',
            states={'invisible': STATE_SIMPLE}),
        'get_basic_tax',
        'set_basic_tax')

    @classmethod
    def set_basic_price(cls, pricing_rules, name, value):
        if not value:
            return
        Component = Pool().get('ins_product.pricing_component')
        for pricing in pricing_rules:
            Component.delete(
                [component for component in pricing.components
                    if component.kind == 'base']
                + list(pricing.sub_item_components))
            cls.write(
                [pricing],
                {'components': [(
                    'create', [{
                        'fixed_amount': value,
                        'kind': 'base',
                        'code': 'PP',
                        'rated_object_kind': 'global'}])]})

    @classmethod
    def set_basic_tax(cls, pricing_rules, name, value):
        if not value:
            return
        try:
            tax, = utils.get_those_objects(
                'coop_account.tax_desc',
                [('id', '=', value)])
        except ValueError:
            raise Exception(
                'Could not found a Tax Desc with code %s' % value)
        Component = Pool().get('ins_product.pricing_component')
        for pricing in pricing_rules:
            Component.delete(
                [component for component in pricing.components
                    if component.kind == 'tax']
                + list(pricing.sub_item_components))
            cls.write(
                [pricing],
                {'components': [(
                    'create', [{
                        'kind': 'tax',
                        'code': tax.code,
                        'rated_object_kind': 'global'}])]})

    def get_component_of_kind(self, kind='base', rated_object_kind='global'):
        components = self.get_components(rated_object_kind)
        return [comp for comp in components if comp.kind == kind]

    def get_single_component_of_kind(
            self, kind='base', rated_object_kind='global'):
        components = self.get_component_of_kind(kind, rated_object_kind)
        if components and len(components) == 1:
            return components[0]

    def get_basic_price(self, name, rated_object_kind='global'):
        component = self.get_single_component_of_kind(
            kind='base', rated_object_kind=rated_object_kind)
        if component:
            return component.fixed_amount
        return 0

    def get_basic_tax(self, name, rated_object_kind='global'):
        component = self.get_single_component_of_kind(
            kind='tax', rated_object_kind=rated_object_kind)
        if component:
            return component.tax.id

    def give_me_price(self, args):
        return self.calculate_price(args, rated_object_kind='global')

    def give_me_sub_elem_price(self, args):
        return self.calculate_price(args, rated_object_kind='sub_item')

    def give_me_frequency(self, args):
        if hasattr(self, 'frequency') and self.frequency:
            return self.frequency
        return None

    def give_me_frequency_days(self, args):
        if not 'date' in args:
            return (None, ['A base date must be provided !'])
        the_date = args['date']
        return date.number_of_days_between(
            the_date,
            utils.add_frequency(self.frequency, the_date))

    @staticmethod
    def default_frequency():
        return 'yearly'

    def get_components(self, rated_object_kind):
        if rated_object_kind == 'global':
            return self.components
        elif rated_object_kind == 'sub_item':
            return self.sub_item_components

    def get_combination_rule(self, rated_object_kind):
        if rated_object_kind == 'global':
            return self.specific_combination_rule
        elif rated_object_kind == 'sub_item':
            return self.sub_item_specific_combination_rule

    def calculate_price(self, args, rated_object_kind='global'):
        result = PricingResultLine(value=0)
        errors = []
        errs = []
        for component in self.get_components(rated_object_kind):
            res, errs = component.calculate_value(args)
            result += res
            errors += errs
        combination_rule = self.get_combination_rule(rated_object_kind)
        if not errors and combination_rule:
            new_args = copy.copy(args)
            new_args['price_details'] = result.details
            final_details = {}
            for key in result.details.iterkeys():
                final_details[key] = 0
            new_args['final_details'] = final_details
            res, mess, errs = utils.execute_rule(
                self, combination_rule, new_args)
            errors += mess + errs
            result = PricingResultLine(value=res)
            result.details = {}
            result.update_details(new_args['final_details'])
        elif not errs and not combination_rule:
            result.value = 0
            sorted = dict([(key, []) for key, _ in PRICING_LINE_KINDS])
            result.desc = []
            for key, value in result.details.iteritems():
                sorted[key[0]].append((key[1], value))
            for the_code, value in sorted['base']:
                result.value += value
            total_fee = 0
            for the_code, value in sorted['fee']:
                fee, = utils.get_those_objects(
                    'coop_account.fee_desc',
                    [('code', '=', the_code)], 1)
                fee_vers = fee.get_version_at_date(args['date'])
                amount = fee_vers.apply_fee(result.value)
                total_fee += amount
                result.details[('fee', the_code)] = amount
            result.value += total_fee
            total_tax = 0
            for the_code, value in sorted['tax']:
                tax, = utils.get_those_objects(
                    'coop_account.tax_desc',
                    [('code', '=', the_code)], 1)
                tax_vers = tax.get_version_at_date(args['date'])
                amount = tax_vers.apply_tax(result.value)
                total_tax += amount
                result.details[('tax', the_code)] = amount
            # result.value += total_tax
        result.create_descs_from_details()
        return result, errors


class PricingComponent(model.CoopSQL, model.CoopView):
    'Pricing Component'

    __name__ = 'ins_product.pricing_component'

    pricing_rule = fields.Many2One(
        'ins_product.pricing_rule', 'Pricing Rule', ondelete='CASCADE')
    fixed_amount = fields.Numeric(
        'Amount', depends=['kind', 'config_kind'],
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': Or(
                Bool((Eval('kind') != 'base')),
                Bool((Eval('config_kind') != 'simple')))})
    config_kind = fields.Selection(
        CONFIG_KIND, 'Conf. kind', required=True,
        states={'invisible': Eval('kind') != 'base'})
    rated_object_kind = fields.Selection(
        RATED_OBJECT_KIND, 'Rated Object Level', required=True)
    rule = fields.Many2One(
        'rule_engine', 'Rule Engine',
        depends=['config_kind', 'kind'],
        states={
            'invisible': Or(
                Bool((Eval('kind') != 'base')),
                Bool((Eval('config_kind') != 'advanced')))})
    rule_complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Rule Complementary Data',
        on_change_with=['rule', 'rule_complementary_data'],
        states={
            'invisible': Or(
                Bool((Eval('kind') != 'base')),
                Bool((Eval('config_kind') != 'advanced')))})
    kind = fields.Selection(
        PRICING_LINE_KINDS, 'Line kind', required=True)
    code = fields.Char(
        'Code', required=True, on_change_with=['code', 'tax', 'fee'])
    tax = fields.Many2One(
        'coop_account.tax_desc', 'Tax',
        states={'invisible': Eval('kind') != 'tax'}, ondelete='RESTRICT')
    fee = fields.Many2One(
        'coop_account.fee_desc', 'Fee',
        states={'invisible': Eval('kind') != 'fee'}, ondelete='RESTRICT')
    summary = fields.Function(
        fields.Char(
            'Value', on_change_with=[
                'fixed_amount', 'config_kind', 'rule',
                'kind', 'tax', 'fee', 'code']),
        'get_summary')

    @classmethod
    def _export_keys(cls):
        return set([])

    @staticmethod
    def default_kind():
        return 'base'

    @staticmethod
    def default_config_kind():
        return 'simple'

    def calculate_tax(self, args):
        # No need to calculate here, it will be done at combination time
        return 0

    def calculate_fee(self, args):
        # No need to calculate here, it will be done at combination time
        return 0

    def get_amount(self, args):
        errors = []
        if self.kind == 'tax':
            amount = self.calculate_tax(args)
        elif self.kind == 'fee':
            amount = self.calculate_fee(args)
        elif self.config_kind == 'simple':
            amount = self.fixed_amount
        elif self.config_kind == 'advanced' and self.rule:
            res, mess, errs = utils.execute_rule(self, self.rule, args)
            amount, errors = res, mess + errs
        return amount, errors

    def on_change_with_rule_complementary_data(self):
        if not (hasattr(self, 'rule') and self.rule):
            return {}
        if not (hasattr(self.rule, 'complementary_parameters') and
                self.rule.complementary_parameters):
            return {}
        return dict([
            (elem.name, self.rule_complementary_data.get(
                elem.name, elem.get_default_value(None)))
            for elem in self.rule.complementary_parameters])

    def get_rule_complementary_data(self, schema_name):
        if not (hasattr(self, 'rule_complementary_data') and
                self.rule_complementary_data):
            return None
        return self.rule_complementary_data.get(schema_name, None)

    def calculate_value(self, args):
        kind = self.kind
        amount, errors = self.get_amount(args)
        code = self.code
        name = kind + ' - ' + code
        final_res = PricingResultLine(amount, name)
        final_res.update_details({(kind, code): amount})
        return final_res, errors

    @classmethod
    def get_summary(cls, pricings, name=None, with_label=False, at_date=None,
                    lang=None):
        res = {}
        for pricing in pricings:
            res[pricing.id] = ''
            if pricing.kind == 'tax' and pricing.tax:
                res[pricing.id] = pricing.tax.rec_name
            elif pricing.kind == 'fee' and pricing.fee:
                res[pricing.id] = pricing.fee.rec_name
            else:
                if pricing.config_kind == 'advanced' and pricing.rule:
                    res[pricing.id] = pricing.rule.rec_name
                elif pricing.config_kind == 'simple':
                    res[pricing.id] = str(pricing.fixed_amount)
        return res

    def get_rec_name(self, name=None):
        return self.get_summary([self])[self.id]

    def on_change_with_summary(self, name=None):
        return self.get_summary([self])[self.id]

    def on_change_with_code(self, name=None):
        if self.code:
            return self.code
        if self.tax:
            return self.tax.code
        if self.fee:
            return self.fee.code
