# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from dateutil import rrule

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, In
from trytond.cache import Cache
from trytond.model import MatchMixin

from trytond.modules.coog_core import fields, model, coog_date, coog_string
from trytond.modules.rule_engine import get_rule_mixin


PREMIUM_FREQUENCY = [
    ('yearly', 'Yearly (Exact)'),
    ('yearly_360', 'Yearly (360 days)'),
    ('yearly_365', 'Yearly (365 days)'),
    ('half_yearly', 'Half-yearly'),
    ('quarterly', 'Quarterly'),
    ('monthly', 'Monthly'),
    ('once_per_contract', 'Once per Contract'),
    ('once_per_invoice', 'Once per Invoice'),
    ('once_per_year', 'Once per Year'),
    ('at_contract_signature', 'At contract signature'),
    ]

__all__ = [
    'ProductPremiumDate',
    'Product',
    'ProductFeeRelation',
    'OptionDescriptionPremiumRule',
    'OptionDescription',
    'OptionDescriptionFeeRelation',
    'OptionDescriptionTaxRelation',
    ]


class ProductPremiumDate(
    get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Product Premium Dates'

    __name__ = 'offered.product.premium_date'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)
    type_ = fields.Selection([
            ('yearly_on_start_date', 'Yearly, from the contract start date'),
            ('monthly_on_start_date', 'Monthly, from the contract start date'),
            ('yearly_custom_date', 'Yearly, at this date'),
            ('duration_initial_start_date', 'Duration from the contract '
                'initial start date'),
            ('duration_current_start_date', 'Duration from the contract '
                'current start date'),
            ('at_given_date', 'At this date')
            ], 'Date rule', sort=False)
    custom_date = fields.Date('Custom Sync Date', states={
            'required': Bool(In(Eval('type_', ''),
                    ['yearly_custom_date', 'at_given_date'])),
            }, depends=['type_'])
    duration = fields.Integer('Duration',
        states={
            'required': Eval('type_', '').in_(
                ['duration_initial_start_date', 'duration_current_start_date']),
            'invisible': ~Eval('type_', '').in_(
                ['duration_initial_start_date', 'duration_current_start_date']),
            }, depends=['type_'])
    duration_unit = fields.Selection(coog_date.DAILY_DURATION, 'Unit',
        states={
            'required': Eval('type_', '').in_(
                ['duration_initial_start_date', 'duration_current_start_date']),
            'invisible': ~Eval('type_', '').in_(
                ['duration_initial_start_date', 'duration_current_start_date']),
            }, depends=['type_'])

    @classmethod
    def __setup__(cls):
        super(ProductPremiumDate, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'premium_date_rule')]
        cls.rule.string = 'Premium Date Rule'

    @fields.depends('type_', 'custom_date')
    def on_change_type_(self):
        if self.type_ not in ('yearly_custom_date', 'at_given_date'):
            self.custom_date = None
        elif self.type_ not in ['duration_initial_start_date',
                'duration_current_start_date']:
            self.duration = None
            self.duration_unit = None

    def get_rule_for_contract(self, contract):
        if self._check_rule_availability(contract):
            return self._get_rule_results(contract)
        return []

    def _check_rule_availability(self, contract):
        if getattr(self, 'rule', None):
            # we assume that premium dates rules are filtered using rule
            # which use contract initial start date as context date
            # execution.
            args = {'date': contract.initial_start_date}
            args['context'] = self
            contract.init_dict_for_rule_engine(args)
            return self.calculate_rule(args)
        return True

    def _get_rule_results(self, contract):
        if self.type_ == 'duration_initial_start_date':
            date = coog_date.add_duration(contract.initial_start_date,
                self.duration_unit, self.duration, True)
            return [datetime.datetime.combine(date, datetime.time())]
        elif self.type_ == 'duration_current_start_date':
            date = coog_date.add_duration(contract.start_date,
                self.duration_unit, self.duration, True)
            return [datetime.datetime.combine(date, datetime.time())]
        elif self.type_ == 'at_given_date':
            return [datetime.datetime.combine(
                    self.custom_date, datetime.time.min)]

        # Manage rrules
        max_date = contract.final_end_date or contract.end_date
        if not max_date:
            return

        if self.type_ == 'yearly_custom_date':
            return rrule.rrule(rrule.YEARLY,
                dtstart=contract.initial_start_date, until=max_date,
                bymonthday=self.custom_date.day,
                bymonth=self.custom_date.month)
        elif self.type_ == 'yearly_on_start_date':
            return rrule.rrule(rrule.YEARLY,
                dtstart=contract.initial_start_date, until=max_date)
        elif self.type_ == 'monthly_on_start_date':
            monthly_dates = []
            cur_date = contract.initial_start_date
            while cur_date < max_date:
                monthly_dates.append(datetime.datetime.combine(
                        cur_date, datetime.time.min))
                cur_date = coog_date.add_month(cur_date, 1,
                    stick_to_end_of_month=True)
            return monthly_dates

    def get_rule_documentation_structure(self):
        return [
            coog_string.doc_for_field(self, 'type_'),
            coog_string.doc_for_field(self, 'custom_date'),
            coog_string.doc_for_field(self, 'duration'),
            coog_string.doc_for_field(self, 'duration_unit'),
            ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    fees = fields.Many2Many('offered.product-account.fee', 'product', 'fee',
        'Fees', help='Define which fee applies for this product')
    premium_dates = fields.One2Many('offered.product.premium_date', 'product',
        'Premium Dates', help='Rules that define dates when contract must be '
        'recalculed when a change occurs', delete_missing=True)

    def calculate_premiums(self, contract, dates):
        lines = {date: [] for date in dates}
        for coverage in self.coverages:
            coverage.calculate_premiums(contract, lines)
        for contract_fee in contract.fees:
            contract_fee.fee.calculate_premiums(contract_fee, lines)
        return lines

    def get_contract_dates(self, dates, contract):
        dates.add(contract.initial_start_date)
        dates.add(contract.start_date)

    def get_option_dates(self, dates, option):
        if option.status == 'void':
            return
        dates.add(option.start_date)
        if option.end_date:
            dates.add(coog_date.add_day(option.end_date, 1))
        for version in option.versions:
            if version.start is not None:
                dates.add(version.start)

    def get_dates(self, contract):
        dates = set()
        self.get_contract_dates(dates, contract)
        for option in contract.options:
            self.get_option_dates(dates, option)
        for extra_data in contract.extra_datas:
            if extra_data.date:
                dates.add(extra_data.date)
        rule_set = rrule.rruleset()
        for premium_date in self.premium_dates:
            premium_date_rule = premium_date.get_rule_for_contract(contract)
            if not premium_date_rule:
                continue
            rule_set.rrule(premium_date_rule)
        dates.update([x.date() for x in rule_set])
        return dates

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['rules'].append(
            coog_string.doc_for_field(self, 'fees'))
        doc['rules'].append(coog_string.doc_for_rules(self, 'premium_dates'))
        return doc


class ProductFeeRelation(model.CoogSQL):
    'Product Fee Relation'

    __name__ = 'offered.product-account.fee'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)
    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True, select=True)


class OptionDescriptionPremiumRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        MatchMixin, model.CoogSQL, model.CoogView):
    'Option Description Premium Rule'

    __name__ = 'offered.option.description.premium_rule'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True, select=True)
    frequency = fields.Selection(PREMIUM_FREQUENCY, 'Rate Frequency',
        required=True)
    premium_base = fields.Function(
        fields.Selection([('contract.option', 'Option')], 'Premium Base',
            states={'invisible': True}),
        'on_change_with_premium_base')

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionPremiumRule, cls).__setup__()
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'premium')]

    @classmethod
    def __post_setup__(cls):
        super(OptionDescriptionPremiumRule, cls).__post_setup__()
        cls._premium_result_class = cls.get_premium_result_class()

    @classmethod
    def default_premium_base(cls):
        return 'contract.option'

    def on_change_with_premium_base(self, name=None):
        return 'contract.option'

    @classmethod
    def get_premium_result_class(cls):
        class PremiumResult(object):
            def __init__(self, amount, data_dict):
                self.amount = amount
                self.data_dict = data_dict
                self.rated_instance = data_dict['_rated_instance']
                self.rated_entity = data_dict['_rated_entity']
                self.date = data_dict['date']
                self.frequency = None

            def __repr__(self):
                return '%.2f : %s (%s)' % (self.amount,
                    self.rated_instance.rec_name.encode('utf-8'), self.date)

            @property
            def contract(self):
                return self.data_dict.get('contract', None)

        return PremiumResult

    def must_be_rated(self, rated_instance, date):
        Option = Pool().get('contract.option')
        if date is None:
            return False
        if isinstance(rated_instance, Option):
            return (rated_instance.status not in ['void', 'declined']) and (
                (rated_instance.initial_start_date or datetime.date.min) <=
                date <= (rated_instance.final_end_date or datetime.date.max))
        return True

    def do_calculate(self, rule_dict):
        rule_result = self.rule.execute(rule_dict, self.rule_extra_data)
        return [self._premium_result_class(rule_result.result, rule_dict)]

    def get_base_premium_dict(self, rated_instance):
        return {
            '_rated_instance': rated_instance,
            '_premium_rule': self,
            '_rated_entity': self.coverage,
            }

    def set_line_frequencies(self, lines, rated_instance, date):
        for line in lines:
            # Do not override already set frequency
            if line.frequency:
                continue
            line.frequency = self.frequency

    def finalize_lines(self, lines):
        pass

    def calculate(self, rated_instance, lines):
        rule_dict_template = self.get_base_premium_dict(rated_instance)
        dict_len = len(rule_dict_template)
        all_lines = []
        for date in lines.keys():
            if len(rule_dict_template) == dict_len:
                rated_instance.init_dict_for_rule_engine(rule_dict_template)
            rule_dict = rule_dict_template.copy()
            rule_dict['date'] = date
            if self.must_be_rated(rated_instance, date):
                new_lines = self.do_calculate(rule_dict)
            else:
                new_lines = self.get_not_rated_line(rule_dict, date)
            if not new_lines:
                continue
            self.set_line_frequencies(new_lines, rated_instance, date)
            all_lines += new_lines
            lines[date] += new_lines
        self.finalize_lines(all_lines)

    @classmethod
    def get_not_rated_line(cls, rule_dict, date):
        # Default behaviour : Create a 0 amount line at date, for instance to
        # detect end of options.
        if not date:
            return []
        return [cls._premium_result_class(0, rule_dict)]

    def get_rule_documentation_structure(self):
        return [self.get_rule_rule_engine_documentation_structure()]


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    fees = fields.Many2Many('offered.option.description-account.fee',
        'coverage', 'fee', 'Fees', help='Fees that applies if this option is '
        'subscribed')
    premium_rules = fields.One2Many('offered.option.description.premium_rule',
        'coverage', 'Premium Rules', help='Rules that return the premium '
        'amount for the option', delete_missing=True)
    taxes = fields.Many2Many('offered.option.description-account.tax',
        'coverage', 'tax', 'Taxes', help='Taxes that apply to the coverage')

    _taxes_per_coverage_cache = Cache('taxes_per_coverage')

    @classmethod
    def _export_light(cls):
        return super(OptionDescription, cls)._export_light() | {'taxes'}

    def _get_taxes(self):
        taxes = self.__class__._taxes_per_coverage_cache.get(self.id, None)
        if taxes is not None:
            return taxes
        # Small table, load it fully
        for option_description in self.__class__.search([]):
            self.__class__._taxes_per_coverage_cache.set(option_description.id,
                [x.id for x in option_description.taxes])
        return self._get_taxes()

    def get_rated_instances(self, base_instance):
        pool = Pool()
        Contract = pool.get('contract')
        Option = pool.get('contract.option')
        result = []
        if isinstance(base_instance, Contract):
            for option in base_instance.options:
                result += self.get_rated_instances(option)
        elif isinstance(base_instance, Option):
            if base_instance.coverage == self and (
                    base_instance.status != 'void'):
                result.append(base_instance)
        return result

    @classmethod
    def get_match_rule(cls, rated_instance):
        return {'premium_base': rated_instance.__name__}

    def calculate_premiums(self, base_instance, lines):
        for rated_instance in self.get_rated_instances(base_instance):
            match_rule = self.get_match_rule(rated_instance)
            for premium_rule in self.premium_rules:
                if premium_rule.match(match_rule):
                    premium_rule.calculate(rated_instance, lines)

    def get_documentation_structure_for_premium_rule(self):
        premium_rule_desc = coog_string.doc_for_rules(self, 'premium_rules')
        premium_rule_desc['attributes'].extend([
                coog_string.doc_for_field(self, 'taxes'),
                coog_string.doc_for_field(self, 'fees'),
                ])
        return premium_rule_desc

    def get_documentation_structure(self):
        structure = super(OptionDescription, self).get_documentation_structure()
        structure['rules'].append(
            self.get_documentation_structure_for_premium_rule())
        return structure


class OptionDescriptionFeeRelation(model.CoogSQL):
    'Option Description Fee Relation'

    __name__ = 'offered.option.description-account.fee'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True)
    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True)


class OptionDescriptionTaxRelation(model.CoogSQL):
    'Option Description Tax Relation'

    __name__ = 'offered.option.description-account.tax'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
        required=True)

    @classmethod
    def create(cls, *args):
        OptionDescription = Pool().get('offered.option.description')
        OptionDescription._taxes_per_coverage_cache.clear()
        return super(OptionDescriptionTaxRelation, cls).create(*args)

    @classmethod
    def delete(cls, *args):
        OptionDescription = Pool().get('offered.option.description')
        OptionDescription._taxes_per_coverage_cache.clear()
        super(OptionDescriptionTaxRelation, cls).delete(*args)
