import datetime
from dateutil import rrule

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.model import MatchMixin

from trytond.modules.cog_utils import fields, model, coop_date
from trytond.modules.rule_engine import RuleMixin


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

__metaclass__ = PoolMeta
__all__ = [
    'ProductPremiumDate',
    'Product',
    'ProductFeeRelation',
    'OptionDescriptionPremiumRule',
    'OptionDescription',
    'OptionDescriptionFeeRelation',
    'OptionDescriptionTaxRelation',
    ]


class ProductPremiumDate(model.CoopSQL, model.CoopView):
    'Product Premium Dates'

    __name__ = 'offered.product.premium_date'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)
    type_ = fields.Selection([
            ('yearly_on_start_date', 'Yearly, from the contract start date'),
            ('yearly_custom_date', 'Yearly, at this date'),
            ], 'Date rule')
    custom_date = fields.Date('Custom Sync Date', states={
            'required': Eval('type_', '') == 'yearly_custom_date',
            'invisible': Eval('type_', '') != 'yearly_custom_date',
            }, depends=['type_'])

    @classmethod
    def __register__(cls, module_name):
        super(ProductPremiumDate, cls).__register__(module_name)

        # Migration from 1.3 : Remove constraint on triplet product / type_ /
        # custom_date
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        TableHandler(cursor, cls, module_name).drop_constraint(
            'offered_product_premium_date_rule_uniq')

    @classmethod
    def create(cls, values):
        for value in values:
            if value['type_'] != 'yearly_custom_date':
                value['custom_date'] = None
        return super(ProductPremiumDate, cls).create(values)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for instances, values in zip(actions, actions):
            if 'type_' in values and values['type_'] != 'yearly_custom_date':
                values['custom_date'] = None
        super(ProductPremiumDate, cls).write(*args)

    def get_rule_for_contract(self, contract):
        max_date = contract.end_date
        if not max_date:
            return
        if self.type_ == 'yearly_custom_date':
            return rrule.rrule(rrule.YEARLY, dtstart=contract.start_date,
                until=max_date, bymonthday=self.custom_date.day,
                bymonth=self.custom_date.month)
        elif self.type_ == 'yearly_on_start_date':
            return rrule.rrule(rrule.YEARLY, dtstart=contract.start_date,
                until=max_date)


class Product:
    __name__ = 'offered.product'

    fees = fields.Many2Many('offered.product-account.fee', 'product', 'fee',
        'Fees')
    premium_dates = fields.One2Many('offered.product.premium_date', 'product',
        'Premium Dates', delete_missing=True)

    def calculate_premiums(self, contract, dates):
        lines = {date: [] for date in dates}
        for coverage in self.coverages:
            coverage.calculate_premiums(contract, lines)
        for contract_fee in contract.fees:
            contract_fee.fee.calculate_premiums(contract_fee, lines)
        return lines

    def get_contract_dates(self, dates, contract):
        dates.add(contract.start_date)

    def get_option_dates(self, dates, option):
        if option.status == 'void':
            return
        dates.add(option.start_date)
        if option.end_date:
            dates.add(coop_date.add_day(option.end_date, 1))
        (dates.add(x.start) for x in option.versions if x.start is not None)

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


class ProductFeeRelation(model.CoopSQL):
    'Product Fee Relation'

    __name__ = 'offered.product-account.fee'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)
    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True, select=True)


class OptionDescriptionPremiumRule(RuleMixin, MatchMixin, model.CoopSQL,
        model.CoopView):
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
                self.taxes = []
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
            return ((rated_instance.start_date or datetime.date.min) <=
                date <= (rated_instance.end_date or datetime.date.max))
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
        for line in lines:
            line.taxes = list(self.coverage.taxes)

    def calculate(self, rated_instance, lines):
        rule_dict_template = self.get_base_premium_dict(rated_instance)
        dict_len = len(rule_dict_template)
        all_lines = []
        for date in lines.iterkeys():
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
        return [cls._premium_result_class(0, rule_dict)]


class OptionDescription:
    __name__ = 'offered.option.description'

    fees = fields.Many2Many('offered.option.description-account.fee',
        'coverage', 'fee', 'Fees')
    premium_rules = fields.One2Many('offered.option.description.premium_rule',
        'coverage', 'Premium Rules', delete_missing=True)
    taxes = fields.Many2Many('offered.option.description-account.tax',
        'coverage', 'tax', 'Taxes')

    @classmethod
    def _export_light(cls):
        return super(OptionDescription, cls)._export_light() | {'taxes'}

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

    def calculate_premiums(self, contract, lines):
        for rated_instance in self.get_rated_instances(contract):
            match_rule = self.get_match_rule(rated_instance)
            for premium_rule in self.premium_rules:
                if premium_rule.match(match_rule):
                    premium_rule.calculate(rated_instance, lines)


class OptionDescriptionFeeRelation(model.CoopSQL):
    'Option Description Fee Relation'

    __name__ = 'offered.option.description-account.fee'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True)
    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True)


class OptionDescriptionTaxRelation(model.CoopSQL):
    'Option Description Tax Relation'

    __name__ = 'offered.option.description-account.tax'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
        required=True)
