from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields, utils
from trytond.modules.offered import NonExistingRuleKindException

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    'RateLine',
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
                if not rate['tranche'] in tranche_dict:
                    sub_rate_line = rate_line.add_tranche_rate_line(
                        rate['tranche'])
                    tranche_dict[rate['tranche']] = sub_rate_line
                else:
                    sub_rate_line = tranche_dict[rate['tranche']]
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


class RateLine(model.CoopSQL, model.CoopView):
    'Rate Line'

    __name__ = 'billing.rate_line'

    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE',
        states={'invisible': ~~Eval('parent')})
    covered_element = fields.Many2One('ins_contract.covered_element',
        'Covered Element', ondelete='RESTRICT')
    option = fields.Many2One('contract.subscribed_option', 'Option',
        ondelete='RESTRICT')
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
        ondelete='RESTRICT')
    parent = fields.Many2One('billing.rate_line', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('billing.rate_line', 'parent', 'Childs',
        states={'invisible': ~~Eval('tranche')})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    rate = fields.Numeric('Rate')
    sum_rate = fields.Function(
        fields.Numeric('Sum Rate', digits=(16, 4)),
        'get_sum_rate')

    def add_child(self):
        if utils.is_none(self, 'childs'):
            self.childs = []
        child_line = self.__class__()
        self.childs.append(child_line)
        return child_line

    def add_tranche_rate_line(self, tranche):
        child_line = self.add_child()
        child_line.tranche = tranche
        return child_line

    def add_option_rate_line(self, option, rate):
        child_line = self.add_child()
        child_line.option = option
        child_line.rate = rate
        return child_line

    def get_rec_name(self, name):
        if self.covered_element:
            return self.covered_element.rec_name
        elif self.option:
            return self.option.rec_name
        elif self.tranche:
            return self.tranche.rec_name

    def get_sum_rate(self, name):
        if self.contract:
            return None
        return (self.rate if self.rate else 0) + sum(
            map(lambda x: x.sum_rate, self.childs))
