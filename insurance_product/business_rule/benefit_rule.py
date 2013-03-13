import datetime
from trytond.model import fields
from trytond.pyson import Eval, Or, Bool
from trytond.pool import Pool

from trytond.modules.coop_utils import model, coop_string, date, utils
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE, CONFIG_KIND, STATE_ADVANCED
from trytond.modules.insurance_product.product import DEF_CUR_DIG


__all__ = [
    'BenefitRule',
    'SubBenefitRule',
]
AMOUNT_KIND = [
    ('amount', 'Amount'),
    ('cov_amount', 'Coverage Amount'),
]
STATES_PARENT_NOT_PERIODIC = Eval('_parent_offered', {}).get(
    'indemnification_kind') != 'period'
STATES_AMOUNT_EVOLVES = Bool(Eval('amount_evolves_over_time'))


class BenefitRule(BusinessRuleRoot, model.CoopSQL):
    'Benefit Rule'

    __name__ = 'ins_product.benefit_rule'

    amount_evolves_over_time = fields.Boolean('Evolves Over Time',
        states={'invisible': STATES_PARENT_NOT_PERIODIC})
    amount_kind = fields.Selection(AMOUNT_KIND, 'Amount Kind',
        states={'invisible': Or(STATE_SIMPLE, STATES_AMOUNT_EVOLVES)})
    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': Or(
                STATE_SIMPLE,
                Eval('amount_kind') != 'amount',
                STATES_AMOUNT_EVOLVES,
            )
        })
    #TODO: use new tryton digits factor
    coef_coverage_amount = fields.Numeric('Multiplier',
        states={
            'invisible': Or(
                STATE_SIMPLE,
                Eval('amount_kind') != 'cov_amount',
                STATES_AMOUNT_EVOLVES,
            )
        }, help='Add a multiplier to apply to the coverage amount', )
    indemnification_calc_unit = fields.Selection(date.DAILY_DURATION,
        'Indemnification Calculation Unit',
        states={
            'invisible': Or(STATES_PARENT_NOT_PERIODIC, STATES_AMOUNT_EVOLVES)
        }, sort=False)
    sub_benefit_rules = fields.One2Many('ins_product.sub_benefit_rule',
        'benefit_rule', 'Sub Benefit Rules',
        states={'invisible': ~STATES_AMOUNT_EVOLVES})
    max_duration_per_indemnification = fields.Integer(
        'Max duration per Indemnification', states={
            'invisible': Or(STATES_PARENT_NOT_PERIODIC, STATES_AMOUNT_EVOLVES)
        })
    max_duration_per_indemnification_unit = fields.Selection(
        date.DAILY_DURATION, 'Unit', sort=False, states={
            'invisible': Or(STATES_PARENT_NOT_PERIODIC, STATES_AMOUNT_EVOLVES)
        })
    with_revaluation = fields.Boolean('With Revaluation',
        states={
            'invisible': Or(STATES_PARENT_NOT_PERIODIC, STATES_AMOUNT_EVOLVES)
        })
    revaluation_date = fields.Date('Revaluation Date',
        states={
            'invisible': Bool(~Eval('with_revaluation')),
            'required': Bool(Eval('with_revaluation')),
        })
    revaluation_index = fields.Many2One('table.table_def', 'Revaluation Index',
        domain=[
            ('dimension_kind1', '=', 'range-date'),
            ('dimension_kind2', '=', None),
        ], states={
            'invisible': Bool(~Eval('with_revaluation')),
            'required': Bool(Eval('with_revaluation')),
        }, ondelete='RESTRICT')
    index_initial_value = fields.Many2One('table.table_cell',
        'Initial Value', states={
            'invisible': Bool(~Eval('with_revaluation')),
            'required': Bool(Eval('with_revaluation')),
        }, domain=[('definition', '=', Eval('revaluation_index'))])
    validation_delay = fields.Integer('Validation Delay',
        states={'invisible': Bool(~Eval('with_revaluation'))})
    validation_delay_unit = fields.Selection(date.DAILY_DURATION,
        'Delay', states={'invisible': Bool(~Eval('with_revaluation'))})

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        utils.update_states(cls, 'config_kind',
            {'invisible': Bool(Eval('amount_evolves_over_time'))})
        utils.update_states(cls, 'rule',
            {'invisible': Bool(Eval('amount_evolves_over_time'))})

    @staticmethod
    def default_coef_coverage_amount():
        return 1

    @staticmethod
    def default_amount_kind():
        return 'cov_amount'

    def get_simple_rec_name(self):
        if self.amount_kind == 'amount':
            return self.amount
        else:
            res = coop_string.translate_value(self, 'amount_kind')
            if self.coef_coverage_amount != 1:
                res = '%s * %s' % (self.coef_coverage_amount, res)
            return res

    def get_rec_name(self, name):
        if not self.amount_evolves_over_time:
            return super(BenefitRule, self).get_rec_name(name)
        res = ''
        for sub_rule in self.sub_benefit_rules:
            res += sub_rule.get_rec_name(name)
        return res

    @staticmethod
    def default_indemnification_calc_unit():
        return 'day'

    def get_index_at_date(self, at_date):
        if not self.revaluation_index:
            return
        Cell = Pool().get('table.table_cell')
        return Cell.get(self.revaluation_index, (at_date))

    def get_revaluated_amount(self, amount, at_date):
        if not self.with_revaluation:
            return amount
        if not amount:
            return 0
        index = self.get_index_at_date(at_date)
        if self.index_initial_value:
            initial_value = self.index_initial_value.get_value_with_type()
        else:
            initial_value = 1
        if initial_value != 0:
            return index * amount / initial_value if index else 0
        return 0

    def get_coverage_amount(self, args):
        if 'option' in args:
            return args['option'].get_coverage_amount()

    def get_rule_result(self, args,):
        res, errs = super(BenefitRule, self).get_rule_result(args)
        if not errs:
            res = self.get_revaluated_amount(res, args['start_date'])
        return res, errs

    def get_simple_result(self, args):
        if self.amount_kind == 'amount':
            amount = self.amount
        elif self.amount_kind == 'cov_amount':
            amount = self.get_coverage_amount(args)
        return self.get_revaluated_amount(amount, args['start_date']), []

    def get_indemnification_for_period(self, args):
        if not 'start_date' in args:
            return [{}], 'missing_start_date'
        if not self.amount_evolves_over_time:
            if not self.with_revaluation:
                return self.get_fixed_indemnification_for_period(args)
            else:
                return self.get_revaluated_indemnifications_for_period(args)
        else:
            return self.get_evolving_indemnifications_for_period(args)

    def get_revaluated_indemnifications_for_period(self, args):
        errs = []
        res = []
        start_date = args['start_date']
        end_date = self.get_end_date(start_date,
            args['end_date'] if 'end_date' in args else None)
        while True and not errs:
            period_end_date = datetime.date(start_date.year,
            self.revaluation_date.month, self.revaluation_date.day)
            period_end_date = date.add_duration(period_end_date, -1, 'day')
            if period_end_date < start_date:
                period_end_date = date.add_duration(period_end_date, 1,
                    'year')
            period_args = args.copy()
            period_args['start_date'] = start_date
            period_args['end_date'] = min(period_end_date, end_date)
            indemns, err = self.get_fixed_indemnification_for_period(
                period_args)
            if not indemns:
                return res, errs
            indemn = indemns[0]
            res.append(indemn)
            errs += err
            if indemn['end_date'] == end_date:
                break
            start_date = date.add_day(indemn['end_date'], 1)
        return res, errs

    def get_fixed_indemnification_for_period(self, args):
        errs = []
        res = {}
        res['start_date'] = args['start_date']
        end_date = args['end_date'] if 'end_date' in args else None
        res['end_date'] = self.get_end_date(res['start_date'], end_date)
        if not res['end_date']:
            errs += 'missing_end_date'
            return [res], errs
        nb = date.duration_between(res['start_date'], res['end_date'],
            self.indemnification_calc_unit)
        res['nb_of_unit'] = nb
        res['unit'] = self.indemnification_calc_unit
        res['amount_per_unit'], re_errs = self.give_me_result(args)
        return [res], errs + re_errs

    def get_evolving_indemnifications_for_period(self, args):
        errs = []
        res = []
        start_date = args['start_date']
        for sub_rule in self.sub_benefit_rules:
            sub_args = args.copy()
            sub_args['start_date'] = start_date
            indemn, err = sub_rule.get_indemnification_for_period(sub_args)
            res.append(indemn)
            errs += err
            if indemn['end_date'] == args['end_date']:
                break
            start_date = date.add_day(indemn['end_date'], 1)
        return res, errs

    def get_indemnification_for_capital(self, args):
        res = {}
        res['nb_of_unit'] = 1
        res['amount_per_unit'], errs = self.give_me_result(args)
        return [res], errs

    def give_me_benefit(self, args):
        if self.offered.indemnification_kind == 'period':
            return self.get_indemnification_for_period(args)
        else:
            return self.get_indemnification_for_capital(args)

    def get_end_date(self, from_date, to_date):
        if (not self.max_duration_per_indemnification
                or not self.max_duration_per_indemnification_unit):
            return to_date
        max_end_date = date.get_end_of_period(from_date,
            self.max_duration_per_indemnification,
            self.max_duration_per_indemnification_unit)
        return min(to_date, max_end_date) if to_date else max_end_date


class SubBenefitRule(model.CoopSQL, model.CoopView):
    'Sub Benefit Rule'

    __name__ = 'ins_product.sub_benefit_rule'

    benefit_rule = fields.Many2One('ins_product.benefit_rule', 'Benefit Rule',
        ondelete='CASCADE')
    config_kind = fields.Selection(CONFIG_KIND,
        'Conf. kind', required=True)
    rule = fields.Many2One('rule_engine', 'Amount',
        states={'invisible': STATE_ADVANCED})
    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={'invisible': STATE_SIMPLE})
    indemnification_calc_unit = fields.Selection(date.DAILY_DURATION,
        'Calculation Unit', sort=False)
    limited_duration = fields.Boolean('Limited Duration')
    duration = fields.Integer('Duration',
        states={'invisible': Bool(~Eval('limited_duration'))})
    duration_unit = fields.Selection(date.DAILY_DURATION, 'Duration Unit',
        sort=False, states={'invisible': Bool(~Eval('limited_duration'))})

    def get_rec_name(self, name=None):
        if self.config_kind == 'advanced' and self.rule:
            return self.rule.get_rec_name()
        return self.get_simple_rec_name()

    def get_simple_rec_name(self):
        if not (hasattr(self, 'amount')
                and hasattr(self, 'indemnification_calc_unit')):
            return ''
        return '%s / %s' % (self.amount,
            coop_string.translate_value(self, 'indemnification_calc_unit'))

    def get_currency(self):
        if self.benefit_rule:
            return self.benefit_rule.get_currency()

    @staticmethod
    def default_config_kind():
        return 'simple'

    def get_end_date(self, from_date, to_date):
        if not self.limited_duration:
            return to_date
        max_end_date = date.get_end_of_period(from_date, self.duration,
            self.duration_unit)
        return min(to_date, max_end_date) if to_date else max_end_date

    def get_rule_result(self, args):
        if self.rule:
            res, mess, errs = self.rule.compute(args)
            return res, mess + errs

    def give_me_result(self, args):
        if self.config_kind == 'advanced':
            return self.get_rule_result(args)
        else:
            return self.get_simple_result(args)

    def get_simple_result(self, args):
        return self.amount, []

    def get_indemnification_for_period(self, args, from_date):
        errs = []
        res = {}
        res['start_date'] = from_date
        end_date = args['end_date'] if 'end_date' in args else None
        end_date = self.get_end_date(from_date, end_date)
        nb = date.duration_between(from_date, end_date,
            self.indemnification_calc_unit)
        res['end_date'] = end_date
        res['nb_of_unit'] = nb
        res['unit'] = self.indemnification_calc_unit
        res['amount_per_unit'], re_errs = self.give_me_result(args)
        return res, errs + re_errs

    @staticmethod
    def default_indemnification_calc_unit():
        return 'day'
