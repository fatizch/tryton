from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields, utils, coop_date
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
        states={'invisible': ~Eval('use_rates')})
    next_assessment_date = fields.Date('Next Assessment Date',
        states={'invisible': ~Eval('use_rates')})

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_calculate_rates': {'invisible': ~Eval('use_rates')},
                })
        cls._error_messages.update({
                'existing_rate_note': ('''A rate note for contract %s (%s, %s)
already exists and can't be modified (%s)'''),
                })

    def get_use_rates(self, name):
        if not self.offered or not self.offered.is_group:
            return False
        for option in self.options:
            if option.offered.rating_rules:
                return True
        return False

    def calculate_rate_dict_at_date(self, date):
        cur_dict = {'date': date}
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
            option = rate_dict['covered_data'].option
            at_date = rate_dict['date']
            if not (population, at_date) in pop_rates:
                rate_line = RateLine()
                rate_line.contract = self
                rate_line.covered_element = population
                rate_line.start_date = at_date
                option_dict = {}
                pop_rates[(population, at_date)] = rate_line, option_dict
            else:
                rate_line, option_dict = pop_rates[(population, at_date)]
            for rate in rate_dict['rates']:
                if not rate['rate']:
                    continue
                if not option in option_dict:
                    sub_rate_line = rate_line.add_option_rate_line(
                        option)
                    option_dict[option] = sub_rate_line
                else:
                    sub_rate_line = option_dict[option]
                if rate['kind'] == 'tranche':
                    tranche = rate['key']
                    index = None
                    fare_class = None
                else:
                    tranche = None
                    index = rate['index']
                    fare_class = rate['key']
                sub_rate_line.add_sub_rate_line(rate['rate'], tranche=tranche,
                    fare_class=fare_class, index=index)
        for population in self.covered_elements:
            if not population in [x[0] for x in pop_rates.iterkeys()]:
                continue
            for rate in [value for (key, value) in pop_rates.iteritems()
                    if key[0] == population]:
                self.rates.append(rate[0])
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

    def calculate_rate_notes(self, until_date=None):
        RateNote = Pool().get('billing.rate_note')
        res = []
        if not until_date:
            until_date = utils.today()
        rating_freq = self.offered.get_collective_rating_frequency()
        while (not self.next_assessment_date
                or self.next_assessment_date <= until_date):
            if not self.next_assessment_date:
                cur_date = self.start_date
            else:
                cur_date = self.next_assessment_date
            start, end = self.subscriber.get_rate_note_dates(cur_date)
            rate_notes = RateNote.search([('contract', '=', self),
                    ('start_date', '=', start), ('end_date', '=', end)])
            if not rate_notes:
                rate_note = RateNote()
                rate_note.init_data(self, start, end)
            else:
                rate_note = rate_notes[0]
                if rate_note.status != 'draft':
                    self.raise_user_error('existing_rate_note',
                        (self.contract_number, start, end, rate_note.status))
            rate_note.calculate()
            rate_note.save()
            res.append(rate_note)
            next_date = coop_date.add_day(rate_note.end_date, 1)
            if self.offered.payment_delay == 'in_arrears':
                next_date = coop_date.get_end_of_period(next_date, 1,
                    rating_freq)
            self.next_assessment_date = next_date
        return res

    def get_rates(self, start_date, end_date):
        res = []
        for rate_line in self.rates:
            if start_date > rate_line.start_date:
                start = start_date
            else:
                start = rate_line.start_date
            if not rate_line.end_date:
                end = end_date
            elif end_date < rate_line.end_date:
                end = end_date
            else:
                end = rate_line.end_date
            if start <= end:
                res.append(((start, end), rate_line))
        return res


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
