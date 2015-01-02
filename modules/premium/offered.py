from dateutil import rrule

from trytond.pool import PoolMeta, Pool
from trytond.model import MatchMixin

from trytond.modules.cog_utils import fields, model
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
    ('at_contract_signature', 'At contract signature'),
    ]

__metaclass__ = PoolMeta
__all__ = [
    'ProductPremiumDates',
    'Product',
    'ProductFeeRelation',
    'OptionDescriptionPremiumRule',
    'OptionDescription',
    'OptionDescriptionFeeRelation',
    'OptionDescriptionTaxRelation',
    ]


class ProductPremiumDates(model.CoopSQL, model.CoopView):
    'Product Premium Dates'

    __name__ = 'offered.product.premium_dates'

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


class Product:
    __name__ = 'offered.product'

    fees = fields.Many2Many('offered.product-account.fee', 'product', 'fee',
        'Fees')
    premium_dates = fields.One2Many('offered.product.premium_dates',
        'product', 'Premium Dates', size=1)

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
        dates.add(option.start_date)

    def get_dates(self, contract):
        dates = set()
        self.get_contract_dates(dates, contract)
        for option in contract.options:
            self.get_option_dates(dates, option)
        for extra_data in contract.extra_datas:
            if extra_data.date:
                dates.add(extra_data.date)
        return dates


class ProductFeeRelation(model.CoopSQL):
    'Product Fee Relation'

    __name__ = 'offered.product-account.fee'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True)
    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True)


class OptionDescriptionPremiumRule(RuleMixin, MatchMixin, model.CoopSQL,
        model.CoopView):
    'Option Description Premium Rule'

    __name__ = 'offered.option.description.premium_rule'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True)
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
            line.frequency = self.frequency

    def finalize_lines(self, lines):
        for line in lines:
            line.taxes = list(self.coverage.taxes)

    def calculate(self, rated_instance, lines):
        rule_dict_template = self.get_base_premium_dict(rated_instance)
        dict_len = len(rule_dict_template)
        all_lines = []
        for date in lines.iterkeys():
            if not self.must_be_rated(rated_instance, date):
                continue
            if len(rule_dict_template) == dict_len:
                rated_instance.init_dict_for_rule_engine(rule_dict_template)
            rule_dict = rule_dict_template.copy()
            rule_dict['date'] = date
            new_lines = self.do_calculate(rule_dict)
            self.set_line_frequencies(new_lines, rated_instance, date)
            all_lines += new_lines
            lines[date] += new_lines
        self.finalize_lines(all_lines)


class OptionDescription:
    __name__ = 'offered.option.description'

    fees = fields.Many2Many('offered.option.description-account.fee',
        'coverage', 'fee', 'Fees')
    premium_rules = fields.One2Many('offered.option.description.premium_rule',
        'coverage', 'Premium Rules')
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
            if base_instance.coverage == self:
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
