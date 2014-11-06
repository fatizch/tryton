# -*- coding:utf-8 -*-
import copy
from decimal import Decimal
from dateutil import rrule

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or, Bool

from trytond.modules.cog_utils import utils, model, fields
from trytond.modules.currency_cog.currency import DEF_CUR_DIG
from trytond.modules.offered.offered import CONFIG_KIND
from trytond.modules.offered import PricingResultLine
from trytond.modules.offered import PricingResultDetail
from trytond.modules.offered_insurance.business_rule.business_rule import \
    BusinessRuleRoot, STATE_ADVANCED, STATE_SIMPLE

__metaclass__ = PoolMeta
__all__ = [
    'PremiumDateConfiguration',
    'PremiumRule',
    'PremiumRuleComponent',
    'TaxVersion',
    'FeeVersion',
    ]

PRICING_LINE_KINDS = [
    ('base', 'Base Price'),
    ('tax', 'Tax'),
    ('fee', 'Fee'),
    ('extra', 'Extra'),
    ]

PRICING_FREQUENCY = [
    ('yearly', 'Yearly (Exact)'),
    ('yearly_360', 'Yearly (360 days)'),
    ('yearly_365', 'Yearly (365 days)'),
    ('half_yearly', 'Half-yearly'),
    ('quarterly', 'Quarterly'),
    ('monthly', 'Monthly'),
    ('once_per_contract', 'Once per Contract'),
    ('once_per_invoice', 'Once per Invoice'),
    ]


class PremiumDateConfiguration(model.CoopSQL, model.CoopView):
    '''Premium Date Configuration

    This model is used to store the dates at which the premiums should be
    calculated for a given contract. It has different toggles whose activation
    will add dome dates at which the premium should be calculated.

    Those toggles must be activated depending on the different premium rules
    that are activated on the product'''

    __name__ = 'billing.premium.date_configuration'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='CASCADE')
    yearly_custom_date = fields.Date('Yearly, this day')
    yearly_on_new_eve = fields.Boolean('Every first day of the year')
    yearly_on_start_date = fields.Boolean('Yearly from the contract start')

    @classmethod
    def default_yearly_on_new_eve(cls):
        return True

    @classmethod
    def default_yearly_on_start_date(cls):
        return True

    def get_dates_for_contract(self, contract):
        max_date = contract.end_date or contract.next_renewal_date
        if not max_date:
            return []
        ruleset = rrule.rruleset()
        if self.yearly_custom_date:
            ruleset.rrule(rrule.rrule(rrule.YEARLY,
                    dtstart=contract.start_date, until=max_date,
                    bymonthday=self.yearly_custom_date.day,
                    bymonth=self.yearly_custom_date.month))
        if self.yearly_on_new_eve:
            ruleset.rrule(rrule.rrule(rrule.YEARLY,
                    dtstart=contract.start_date, until=max_date,
                    bymonthday=1, bymonth=1))
        if self.yearly_on_start_date:
            ruleset.rrule(rrule.rrule(rrule.YEARLY,
                    dtstart=contract.start_date, until=max_date))
        return [x.date() for x in ruleset]


class PremiumRule(BusinessRuleRoot, model.CoopSQL):
    'Premium Rule'

    __name__ = 'billing.premium.rule'

    components = fields.One2ManyDomain('billing.premium.rule.component',
        'premium_rule', 'Components',
        domain=[('rated_object_kind', '=', 'global')],
        states={'invisible': STATE_SIMPLE})
    sub_item_components = fields.One2ManyDomain(
        'billing.premium.rule.component',
        'premium_rule', 'Covered Item Components',
        domain=[('rated_object_kind', '=', 'sub_item')])
    match_contract_frequency = fields.Boolean('Match Contract Frequency',
        help='Should the premium be stored at the contract\'s frequency ?')
    frequency = fields.Selection(PRICING_FREQUENCY, 'Rate Frequency',
        required=True)
    specific_combination_rule = fields.Many2One('rule_engine',
        'Combination Rule', states={'invisible': STATE_SIMPLE},
        ondelete='RESTRICT')
    sub_item_specific_combination_rule = fields.Many2One('rule_engine',
        'Sub Item Combination Rule', ondelete='RESTRICT')
    basic_price = fields.Function(
        fields.Numeric('Amount', states={'invisible': STATE_ADVANCED}, digits=(
                16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG))),
        'get_basic_price', 'set_basic_price')
    basic_tax = fields.Function(
        fields.Many2One('account.tax.description', 'Tax',
            states={'invisible': STATE_ADVANCED}),
        'get_basic_tax', 'set_basic_tax')

    @classmethod
    def __setup__(cls):
        super(PremiumRule, cls).__setup__()
        cls._error_messages.update({
                'bad_tax_version':
                '%s : Rule combination unavailable with tax (%s) version (%s)',
                'bad_fee_version':
                '%s : Rule combination unavailable with fee (%s) version (%s)',
                })

    @classmethod
    def set_basic_price(cls, premium_rules, name, value):
        if not value:
            return
        Component = Pool().get('billing.premium.rule.component')
        for pricing in premium_rules:
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
                                'rated_object_kind': 'global',
                                }])]})

    @classmethod
    def set_basic_tax(cls, premium_rules, name, value):
        if not value:
            return
        try:
            tax, = utils.get_those_objects(
                'account.tax.description',
                [('id', '=', value)])
        except ValueError:
            raise Exception(
                'Could not found a Tax Desc with code %s' % value)
        Component = Pool().get('billing.premium.rule.component')
        for pricing in premium_rules:
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
                                'rated_object_kind': 'global',
                                'value': tax.id,
                                }])]})

    @classmethod
    def validate(cls, rules):
        super(PremiumRule, cls).validate(rules)
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

    def calculate_extra_detail(self, from_detail, args, base):
        extra = from_detail.on_object
        extra_amount = extra.calculate_premium_amount(args, base)
        if not extra_amount:
            return
        from_detail.amount = extra_amount
        from_detail.on_object = extra

    def calculate_components_contribution(self, args, result, errors,
            rated_object_kind):
        for component in self.get_components(rated_object_kind):
            res, errs = component.calculate_value(args)
            try:
                result.add_detail(res)
            except TypeError:
                errors.append('Calculated amount %s is not a valid result for '
                    '%s' % (res.amount, component))
            errors += errs
        if 'extra_premiums' not in args:
            return
        for extra in args['extra_premiums']:
            result.add_detail(PricingResultDetail(0, extra, kind='extra'))

    def calculate_price(self, args, rated_object_kind='global'):
        result = PricingResultLine()
        errors = []
        self.calculate_components_contribution(args, result, errors,
            rated_object_kind)
        if errors:
            return [], errors
        combination_rule = self.get_combination_rule(rated_object_kind)
        if not errors and combination_rule:
            new_args = copy.copy(args)
            new_args['price_details'] = result.details
            new_args['final_details'] = {}
            rule_result = combination_rule.execute(new_args)
            res = rule_result.result
            errors.extend(rule_result.print_errors())
            errors.extend(rule_result.print_warnings())
            details = self.build_details(new_args['final_details'])
            result.amount = res
            result.details = details
        elif not errors and not combination_rule:
            result.amount = 0
            group_details = dict([(key, []) for key, _ in PRICING_LINE_KINDS])
            for detail in result.details:
                group_details[detail.kind].append(detail)
            result.details = []
            for detail in group_details['base']:
                result.add_detail(detail)
            extra_details = []
            for detail in group_details['extra']:
                self.calculate_extra_detail(detail, args, result.amount)
                extra_details.append(detail)
            for detail in extra_details:
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
        lines = []
        fee_lines = []
        template = {
            'frequency': self.frequency,
            'target': self.get_lowest_level_instance(args),
            'product': args['product'],
            }
        taxes = []
        for detail in result.details:
            if detail.kind in ('base', 'extra'):
                new_line = dict(template)
                new_line['amount'] = detail.amount
                new_line['rated_entity'] = args.get('coverage',
                    args.get('product'))
                if detail.kind == 'extra':
                    new_line['target'] = detail.on_object
                if detail.amount:
                    lines.append(new_line)
            elif detail.kind == 'fee':
                new_line = dict(template)
                new_line['amount'] = detail.amount
                new_line['rated_entity'] = detail.on_object.fee
                if detail.amount:
                    fee_lines.append(new_line)
            elif detail.kind == 'tax':
                taxes.append(detail.on_object.tax.tax)
        for elem in (lines + fee_lines):
            elem['taxes'] = list(taxes)
        if self.match_contract_frequency:
            ContractBillingInformation = Pool().get(
                'contract.billing_information')
            contract_billing_mode = ContractBillingInformation.get_values(
                [args['contract']], date=args['date'],
                )['billing_mode'][args['contract'].id]
            frequency = Pool().get('offered.billing_mode')(
                contract_billing_mode).frequency
            for elem in (lines + fee_lines):
                self.convert_premium_frequency(elem, frequency)

        return lines + fee_lines, errors

    def get_lowest_level_instance(self, args):
        if 'covered_element' in args:
            if 'option' in args:
                return args['option']
            return args['covered_element']
        elif 'option' in args:
            return args['option']
        elif 'contract' in args:
            return args['contract']
        return None

    def convert_premium_frequency(self, line, frequency):
        if line['frequency'] in ('once_per_invoice', 'once_per_contract'):
            return
        if frequency in ('once_per_invoice', 'once_per_contract'):
            return
        conversion_table = {
            'yearly': Decimal(12),
            'yearly_360': Decimal(12),
            'yearly_365': Decimal(12),
            'half_yearly': Decimal(6),
            'quarterly': Decimal(3),
            'monthly': Decimal(1),
            }
        line['amount'] = line['amount'] / (conversion_table[line['frequency']]
            / conversion_table[frequency])
        line['frequency'] = frequency


class PremiumRuleComponent(model.CoopSQL, model.CoopView):
    'Premium Rule Component'

    __name__ = 'billing.premium.rule.component'
    _func_key = 'code'

    premium_rule = fields.Many2One('billing.premium.rule', 'Premium Rule',
        ondelete='CASCADE')
    fixed_amount = fields.Numeric('Amount', depends=['kind', 'config_kind'],
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': Or(
                Bool((Eval('kind') != 'base')),
                Bool((Eval('config_kind') != 'simple')))})
    config_kind = fields.Selection(CONFIG_KIND, 'Conf. kind', required=True,
        states={'invisible': Eval('kind') != 'base'})
    rated_object_kind = fields.Selection([
            ('global', 'Global'),
            ('sub_item', 'Covered Item'),
            ], 'Rated Object Level', required=True)
    rule = fields.Many2One('rule_engine', 'Rule Engine', ondelete='CASCADE',
        depends=['config_kind', 'kind'], states={
            'invisible': Or(
                Bool((Eval('kind') != 'base')),
                Bool((Eval('config_kind') != 'advanced')))})
    rule_extra_data = fields.Dict('rule_engine.rule_parameter',
        'Rule Extra Data', states={
            'invisible': Or(
                Bool((Eval('kind') != 'base')),
                Bool((Eval('config_kind') != 'advanced')))})
    kind = fields.Selection(PRICING_LINE_KINDS, 'Line kind', required=True)
    code = fields.Char('Code', required=True)
    tax = fields.Many2One('account.tax.description', 'Tax',
        states={'invisible': Eval('kind') != 'tax'}, ondelete='RESTRICT')
    fee = fields.Many2One('account.fee.description', 'Fee',
        states={'invisible': Eval('kind') != 'fee'}, ondelete='RESTRICT')
    summary = fields.Function(
        fields.Char('Value'),
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
            rule_result = self.rule.execute(args, self.rule_extra_data)
            amount, errors = rule_result.result, rule_result.print_errors()
        return amount, errors

    @fields.depends('rule', 'rule_extra_data')
    def on_change_with_rule_extra_data(self):
        if not (hasattr(self, 'rule') and self.rule):
            return {}
        return self.rule.get_extra_data_for_on_change(
            self.rule_extra_data)

    def get_rule_extra_data(self, schema_name):
        if not (hasattr(self, 'rule_extra_data') and
                self.rule_extra_data):
            return None
        return self.rule_extra_data.get(schema_name, None)

    def calculate_value(self, args):
        amount, errors = self.get_amount(args)
        detail_line = PricingResultDetail(amount, self, kind=self.kind)
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

    @fields.depends('fixed_amount', 'config_kind', 'rule', 'kind', 'tax',
        'fee', 'code')
    def on_change_with_summary(self, name=None):
        return self.get_summary([self])[self.id]

    @fields.depends('code', 'tax', 'fee')
    def on_change_with_code(self, name=None):
        if self.tax:
            return self.tax.code
        if self.fee:
            return self.fee.code
        if self.code:
            return self.code


class TaxVersion:
    __name__ = 'account.tax.description.version'

    apply_at_pricing_time = fields.Boolean('Apply when Pricing')

    @classmethod
    def default_apply_at_pricing_time(cls):
        return False


class FeeVersion:
    __name__ = 'account.fee.description.version'

    apply_at_pricing_time = fields.Boolean('Apply when Pricing')

    @classmethod
    def default_apply_at_pricing_time(cls):
        return False
