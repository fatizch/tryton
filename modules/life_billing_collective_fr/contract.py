from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields, utils
from trytond.modules.offered import NonExistingRuleKindException

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    'CoveredData',
    ]


class Contract():
    'Contract'

    __name__ = 'contract.contract'

    use_rates = fields.Function(
        fields.Boolean('Use Rates', states={'invisible': True}),
        'get_use_rates')
    rates = fields.One2Many('billing.rate_line', 'contract', 'Rates',
        states={'invisible': ~Eval('is_group')})

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_calculate_rates': {},
                })

    def get_use_rates(self, name):
        if not self.offered or not self.offered.is_group:
            return False
        for option in self.options:
            if option.offered.rating_rules:
                return True
        return False

    def calculate_rate_dict_at_date(self, date):
        cur_dict = {
            'date': date,
            'appliable_conditions_date': self.appliable_conditions_date}
        self.init_dict_for_rule_engine(cur_dict)
        rates = []
        errs = []
        for option in self.options:
            option_args = cur_dict.copy()
            option.init_dict_for_rule_engine(option_args)
            try:
                option_rates, option_errs = option.offered.get_result('rate',
                    option_args, 'rating')
            except NonExistingRuleKindException:
                continue
            rates.extend(option_rates)
            errs.extend(option_errs)
        return (rates, errs)

    def calculate_rates_dicts_between_dates(self, start=None, end=None):
        if not start:
            start = self.start_date
        rates = []
        errs = []
        dates = self.get_dates()
        dates = utils.limit_dates(dates, self.start_date)
        for cur_date in dates:
            rate, err = self.calculate_rate_dict_at_date(cur_date)
            if rate:
                rates.extend(rate)
            errs += err
        return rates, errs

    def calculate_rates(self):
        RateLine = Pool().get('billing.rate_line')
        rates, errs = self.calculate_rates_dicts_between_dates()
        if errs:
            return False, errs
        if self.rates:
            RateLine.delete(self.rates)
        self.rates = []
        pop_rates = {}
        for rate_dict in rates:
            population = rate_dict['covered_data'].covered_element
            if not population in pop_rates:
                rate_line = RateLine()
                rate_line.contract = self
                rate_line.covered_element = population
                tranche_dict = {}
                pop_rates[population] = rate_line, tranche_dict
            else:
                rate_line, tranche_dict = pop_rates[population]
            for rate in rate_dict['rates']:
                if rate['kind'] == 'tranche':
                    tranche = rate['key']
                    index = None
                    fare_class = None
                else:
                    tranche = None
                    index = rate['index']
                    fare_class = rate['key']
                if not rate['key'] in tranche_dict:
                    sub_rate_line = rate_line.add_main_rate_line(
                        tranche=tranche, fare_class=fare_class, index=index)
                    tranche_dict[rate['key']] = sub_rate_line
                else:
                    sub_rate_line = tranche_dict[rate['key']]
                sub_rate_line.add_option_rate_line(
                    rate_dict['covered_data'].option, rate['rate'])
        for population in self.covered_elements:
            if not population in pop_rates:
                continue
            self.rates.append(pop_rates[population][0])
        self.save()
        return True, ()

    @classmethod
    @model.CoopView.button
    def button_calculate_rates(cls, contracts):
        errs = []
        for contract in contracts:
            res, cur_errs = contract.calculate_rates()
            if cur_errs:
                errs.extend(cur_errs)
        if errs:
            cls.raise_user_error(errs)


class CoveredData():
    'Covered Data'

    __name__ = 'ins_contract.covered_data'

    is_rating_by_fare_class = fields.Function(
        fields.Boolean('Rating by Fare Class', states={'invisible': True}),
        'get_rating_by_fare_class')
    fare_class_group = fields.Many2One('collective.fare_class_group',
        'Fare Class Group', ondelete='RESTRICT',
        states={'invisible': ~Eval('is_rating_by_fare_class')})

    def get_rating_by_fare_class(self, name):
        return (self.option.offered.is_rating_by_fare_class
            if self.option else False)
