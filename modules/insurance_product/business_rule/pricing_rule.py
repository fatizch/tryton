#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or, Bool

from trytond.modules.coop_utils import utils, date, model, fields
from trytond.modules.offered.offered import DEF_CUR_DIG, CONFIG_KIND
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import PricingResultDetail
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_ADVANCED, STATE_SIMPLE

__all__ = [
    'SimplePricingRule',
    'PricingRule',
    'PricingComponent',
    'TaxVersion',
    'FeeVersion',
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
        states={'invisible': STATE_SIMPLE})
    sub_item_components = fields.One2ManyDomain(
        'ins_product.pricing_component',
        'pricing_rule', 'Covered Item Components',
        domain=[('rated_object_kind', '=', 'sub_item')])
    frequency = fields.Selection(
        PRICING_FREQUENCY, 'Rate Frequency', required=True)
    specific_combination_rule = fields.Many2One(
        'rule_engine', 'Combination Rule',
        states={'invisible': STATE_SIMPLE})
    sub_item_specific_combination_rule = fields.Many2One(
        'rule_engine', 'Sub Item Combination Rule')
    basic_price = fields.Function(
        fields.Numeric(
            'Amount', states={'invisible': STATE_ADVANCED},
            digits=(
                16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG))),
        'get_basic_price',
        'set_basic_price')
    basic_tax = fields.Function(
        fields.Many2One(
            'coop_account.tax_desc', 'Tax',
            states={'invisible': STATE_ADVANCED}),
        'get_basic_tax',
        'set_basic_tax')

    @classmethod
    def __setup__(cls):
        super(PricingRule, cls).__setup__()
        cls._error_messages.update({
            'bad_tax_version':
            '%s : Rule combination unavailable with tax (%s) version (%s)',
            'bad_fee_version':
            '%s : Rule combination unavailable with fee (%s) version (%s)',
        })

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

    @classmethod
    def validate(cls, rules):
        super(PricingRule, cls).validate(rules)
        for rule in rules:
            rule.check_rule_combination_compatibility()

    def check_rule_combination_compatibility(self):
        def check_component(component):
            for version in getattr(component, component.kind).versions:
                if (version.start_date >= self.start_date and
                        (not self.end_date or
                            self.end_date >= elem.end_date) or
                        version.start_date < self.start_date and
                        (not version.end_date or
                            version.end_date < self.start_date)):
                    if version.apply_at_pricing_time:
                        self.raise_user_error(
                            'bad_%s_version' % component.kind, (
                                self.start_date, elem.main_elem.code,
                                elem.start_date))

        if self.specific_combination_rule:
            for elem in self.components:
                if elem.kind in ('fee', 'tax'):
                    check_component(elem)
        if self.sub_item_specific_combination_rule:
            for elem in self.sub_item_components:
                if elem.kind in ('fee', 'tax'):
                    check_component(elem)

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
            date.add_frequency(self.frequency, the_date))

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

    def build_details(self, final_details):
        result = []
        for amount, detail_definition in final_details.itervalues():
            detail_definition.amount = amount
            result.append(detail_definition)
        return result

    def calculate_tax_detail(self, from_detail, args, base):
        tax = from_detail.on_object.tax
        tax_vers = tax.get_version_at_date(args['date'])
        amount = tax_vers.apply_tax(base)
        from_detail.to_recalculate = tax_vers.apply_at_pricing_time
        from_detail.amount = amount

    def calculate_fee_detail(self, from_detail, args, base):
        fee = from_detail.on_object.fee
        fee_vers = fee.get_version_at_date(args['date'])
        amount = fee_vers.apply_fee(base)
        from_detail.to_recalculate = fee_vers.apply_at_pricing_time
        from_detail.amount = amount

    def calculate_price(self, args, rated_object_kind='global'):
        result = PricingResultLine()
        errors = []
        errs = []
        for component in self.get_components(rated_object_kind):
            res, errs = component.calculate_value(args)
            result.add_detail(res)
            errors += errs
        combination_rule = self.get_combination_rule(rated_object_kind)
        if not errors and combination_rule:
            new_args = copy.copy(args)
            new_args['price_details'] = result.details
            new_args['final_details'] = {}
            rule_result = utils.execute_rule(
                self, combination_rule, new_args)
            res = rule_result.result
            errors.extend(rule_result.print_errors())
            errors.extend(rule_result.print_warnings())
            details = self.build_details(new_args['final_details'])
            result.amount = res
            result.details = details
        elif not errs and not combination_rule:
            result.amount = 0
            group_details = dict([(key, []) for key, _ in PRICING_LINE_KINDS])
            for detail in result.details:
                group_details[detail.on_object.kind].append(detail)
            result.details = []
            for detail in group_details['base']:
                result.add_detail(detail)
            # By default, taxes and fees are appliend on the total base amount
            fee_details = []
            for detail in group_details['fee']:
                self.calculate_fee_detail(detail, args, result.amount)
                fee_details.append(detail)
            tax_details = []
            for detail in group_details['tax']:
                self.calculate_tax_detail(detail, args, result.amount)
                tax_details.append(detail)
            for detail in fee_details:
                result.add_detail(detail)
            for detail in tax_details:
                result.add_detail(detail)
        result.frequency = self.frequency
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
        'offered.complementary_data_def', 'Rule Complementary Data',
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
            rule_result = utils.execute_rule(self, self.rule, args)
            amount, errors = rule_result.result, rule_result.print_errors()
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
        amount, errors = self.get_amount(args)
        detail_line = PricingResultDetail(amount, self)
        return detail_line, errors

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
        if self.tax:
            return self.tax.code
        if self.fee:
            return self.fee.code
        if self.code:
            return self.code


class TaxVersion():
    'Tax Version'

    __metaclass__ = PoolMeta
    __name__ = 'coop_account.tax_version'

    apply_at_pricing_time = fields.Boolean('Apply when Pricing')


class FeeVersion():
    'Fee Version'

    __metaclass__ = PoolMeta
    __name__ = 'coop_account.fee_version'

    apply_at_pricing_time = fields.Boolean('Apply when Pricing')
