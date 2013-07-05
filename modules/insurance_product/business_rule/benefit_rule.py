import datetime
from trytond.pyson import Eval, Or, Bool
from trytond.pool import Pool

from trytond.modules.coop_utils import model, coop_string, coop_date, utils
from trytond.modules.coop_utils import fields
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_ADVANCED, CONFIG_KIND, STATE_SIMPLE
from trytond.modules.offered.offered import DEF_CUR_DIG


__all__ = [
    'BenefitRule',
    'SubBenefitRule',
]
AMOUNT_KIND = [
    ('amount', 'Amount'),
    ('cov_amount', 'Coverage Amount'),
]
STATES_CAPITAL = Eval('_parent_offered', {}).get(
    'indemnification_kind') == 'capital'
STATES_PERIOD = Eval('_parent_offered', {}).get(
    'indemnification_kind') == 'period'
STATES_ANNUITY = Eval('_parent_offered', {}).get(
    'indemnification_kind') == 'annuity'
STATES_AMOUNT_EVOLVES = Bool(Eval('amount_evolves_over_time'))


class BenefitRule(BusinessRuleRoot, model.CoopSQL):
    'Benefit Rule'

    __name__ = 'ins_product.benefit_rule'

    amount_evolves_over_time = fields.Boolean('Evolves Over Time',
        states={'invisible': ~STATES_PERIOD})
    amount_kind = fields.Selection(AMOUNT_KIND, 'Amount Kind',
        states={'invisible': Or(STATE_ADVANCED, STATES_AMOUNT_EVOLVES)})
    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': Or(
                STATE_ADVANCED,
                Eval('amount_kind') != 'amount',
                STATES_AMOUNT_EVOLVES,
            )
        })
    #TODO: use new tryton digits factor
    coef_coverage_amount = fields.Numeric('Multiplier',
        states={
            'invisible': Or(
                STATE_ADVANCED,
                Eval('amount_kind') != 'cov_amount',
                STATES_AMOUNT_EVOLVES,
            )
        }, help='Add a multiplier to apply to the coverage amount', )
    indemnification_calc_unit = fields.Selection(coop_date.DAILY_DURATION,
        'Indemnification Calculation Unit',
        states={
            'invisible': Or(STATES_CAPITAL, STATES_AMOUNT_EVOLVES),
            'required': ~STATES_CAPITAL,
        }, sort=False)
    sub_benefit_rules = fields.One2Many('ins_product.sub_benefit_rule',
        'benefit_rule', 'Sub Benefit Rules',
        states={'invisible': ~STATES_AMOUNT_EVOLVES})
    use_monthly_period = fields.Boolean('Monthly Period',
        help='Split periods at the end of the month',
        states={'invisible':
                Or(STATES_CAPITAL, STATES_AMOUNT_EVOLVES,
                    Bool(Eval('max_duration_per_indemnification')))})
    max_duration_per_indemnification = fields.Integer(
        'Max duration per Indemnification',
        states={
            'invisible':
                Or(STATES_CAPITAL, STATES_AMOUNT_EVOLVES,
                    Bool(Eval('use_monthly_period'))),
            'required': Or(STATES_ANNUITY,
                Bool(Eval('max_duration_per_indemnification_unit')))
        })
    max_duration_per_indemnification_unit = fields.Selection(
        coop_date.DAILY_DURATION, 'Unit', sort=False,
        states={
            'invisible': Or(STATES_CAPITAL, STATES_AMOUNT_EVOLVES,
                Bool(Eval('use_monthly_period'))),
            'required': Or(STATES_ANNUITY,
                Bool(Eval('max_duration_per_indemnification')))
        })
    with_revaluation = fields.Boolean('With Revaluation',
        states={'invisible': Or(~STATES_ANNUITY, STATES_AMOUNT_EVOLVES)})
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
    index_initial_date = fields.Date('Index Initial Date', states={
            'invisible': Bool(~Eval('with_revaluation')),
            'required': Bool(Eval('with_revaluation'))})
    index_initial_value = fields.Function(
        fields.Char('Initial Value', states={
                'invisible': Bool(~Eval('with_revaluation')),
                'required': Bool(Eval('with_revaluation'))},
            domain=[('definition', '=', Eval('revaluation_index'))],
            depends=['revaluation_index'],
            on_change_with=['revaluation_index', 'index_initial_date']),
        'on_change_with_index_initial_value')
    validation_delay = fields.Integer('Validation Delay',
        states={'invisible': Bool(~Eval('with_revaluation'))})
    validation_delay_unit = fields.Selection(coop_date.DAILY_DURATION,
        'Delay', states={'invisible': Bool(~Eval('with_revaluation'))})

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        utils.update_states(cls, 'config_kind',
            {'invisible': Bool(Eval('amount_evolves_over_time'))})
        utils.update_states(cls, 'rule',
            {'invisible': Bool(Eval('amount_evolves_over_time'))})

    def get_currency(self):
        if self.offered:
            return self.offered.get_currency()

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
                #TODO : waiting tryton digits factor
                #res = '%s%% * %s' % (self.coef_coverage_amount * 100, res)
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
        return Cell.get_cell(self.revaluation_index, (at_date))

    def on_change_with_index_initial_value(self, name=None):
        cell = self.get_index_at_date(self.index_initial_date)
        if cell:
            return str(cell.get_value_with_type())
        return ''

    def get_revaluated_amount(self, amount, at_date):
        if not self.with_revaluation:
            return amount
        if not amount:
            return 0
        index = self.get_index_at_date(at_date)
        initial_value = 1
        if self.index_initial_date:
            initial_index = self.get_index_at_date(self.index_initial_date)
            if initial_index:
                initial_value = initial_index.get_value_with_type()
        if initial_value != 0:
            return index * amount / initial_value if index else 0
        return 0

    def get_coverage_amount(self, args):
        if 'option' in args:
            cov_amount = args['option'].get_coverage_amount()
            return cov_amount * self.coef_coverage_amount
        return 0

    def get_rule_result(self, args):
        rule_result = super(BenefitRule, self).get_rule_result(args)
        res = rule_result.result
        if not rule_result.has_errors:
            res = self.get_revaluated_amount(res, args['start_date'])
        return res, rule_result.print_errors()

    def get_simple_result(self, args):
        if self.amount_kind == 'amount':
            amount = self.amount
        elif self.amount_kind == 'cov_amount':
            amount = self.get_coverage_amount(args)
        return self.get_revaluated_amount(amount, args['start_date']), []

    def get_indemnification_for_non_capital(self, args):
        if not 'start_date' in args:
            return [{}], 'missing_start_date'
        if not self.amount_evolves_over_time:
            return self.get_indemnifications_for_periods(args)
        else:
            return self.get_evolving_indemnifications_for_period(args)

    def get_indemnification_end_date(self, from_date, to_date):
        if (self.max_duration_per_indemnification
                and self.max_duration_per_indemnification_unit):
            max_end_date = coop_date.get_end_of_period(from_date,
                self.max_duration_per_indemnification,
                self.max_duration_per_indemnification_unit)
        elif self.use_monthly_period:
            max_end_date = coop_date.get_end_of_month(from_date)
        else:
            return to_date
        return min(to_date, max_end_date) if to_date else max_end_date

    def get_period_end_date(self, from_date, to_date):
        if (self.offered.indemnification_kind == 'annuity'
                and self.with_revaluation):
            res = datetime.coop_date(from_date.year,
                self.revaluation_date.month, self.revaluation_date.day)
            res = coop_date.add_duration(res, -1, 'day')
            if res < from_date:
                    res = coop_date.add_duration(res, 1, 'year')
        else:
            return to_date

    def get_indemnifications_for_periods(self, args):
        errs = []
        res = []
        start_date = args['start_date']
        end_date = self.get_indemnification_end_date(start_date,
            args['end_date'] if 'end_date' in args else None)
        while True and not errs:
            period_end_date = self.get_period_end_date(start_date, end_date)
            period_args = args.copy()
            period_args['start_date'] = start_date
            period_args['end_date'] = min(period_end_date, end_date)
            indemns, err = self.get_indemnification_for_period(
                period_args)
            if not indemns:
                return res, errs
            indemn = indemns[0]
            res.append(indemn)
            errs += err
            if indemn['end_date'] == end_date:
                break
            start_date = coop_date.add_day(indemn['end_date'], 1)
        return res, errs

    def get_indemnification_for_period(self, args):
        errs = []
        res = {}
        res['start_date'] = args['start_date']
        end_date = None
        if self.offered.indemnification_kind == 'period':
            end_date = args['end_date'] if 'end_date' in args else None
        res['end_date'] = self.get_indemnification_end_date(res['start_date'],
            end_date)
        if not res['end_date']:
            errs += 'missing_end_date'
            return [res], errs
        nb = coop_date.duration_between(res['start_date'], res['end_date'],
            self.indemnification_calc_unit)
        res['nb_of_unit'] = nb
        res['unit'] = self.indemnification_calc_unit
        res['amount_per_unit'], re_errs = self.give_me_result(args)
        res['beneficiary_kind'] = self.offered.beneficiary_kind
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
            start_date = coop_date.add_day(indemn['end_date'], 1)
        return res, errs

    def get_indemnification_for_capital(self, args):
        res = {}
        res['nb_of_unit'] = 1
        res['amount_per_unit'], errs = self.give_me_result(args)
        res['beneficiary_kind'] = self.offered.beneficiary_kind
        return [res], errs

    def give_me_benefit(self, args):
        if self.offered.indemnification_kind != 'capital':
            return self.get_indemnification_for_non_capital(args)
        else:
            return self.get_indemnification_for_capital(args)


class SubBenefitRule(model.CoopSQL, model.CoopView):
    'Sub Benefit Rule'

    __name__ = 'ins_product.sub_benefit_rule'

    benefit_rule = fields.Many2One('ins_product.benefit_rule', 'Benefit Rule',
        ondelete='CASCADE')
    config_kind = fields.Selection(CONFIG_KIND,
        'Conf. kind', required=True)
    rule = fields.Many2One(
        'rule_engine', 'Amount', states={'invisible': STATE_SIMPLE})
    rule_complementary_data = fields.Dict(
        'offered.complementary_data_def', 'Rule Complementary Data',
        on_change_with=['rule', 'rule_complementary_data'],
        states={'invisible': STATE_SIMPLE})
    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={'invisible': STATE_ADVANCED})
    indemnification_calc_unit = fields.Selection(coop_date.DAILY_DURATION,
        'Calculation Unit', sort=False)
    limited_duration = fields.Boolean('Limited Duration')
    duration = fields.Integer('Duration',
        states={'invisible': Bool(~Eval('limited_duration'))})
    duration_unit = fields.Selection(coop_date.DAILY_DURATION, 'Duration Unit',
        sort=False, states={'invisible': Bool(~Eval('limited_duration'))})

    def on_change_with_rule_complementary_data(self):
        if not (hasattr(self, 'rule') and self.rule):
            return {}
        return self.rule.get_complementary_data_for_on_change(
            self.rule_complementary_data)

    def get_rule_complementary_data(self, schema_name):
        if not (hasattr(self, 'rule_complementary_data') and
                self.rule_complementary_data):
            return None
        return self.rule_complementary_data.get(schema_name, None)

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
        max_end_date = coop_date.get_end_of_period(from_date, self.duration,
            self.duration_unit)
        return min(to_date, max_end_date) if to_date else max_end_date

    def get_rule_result(self, args):
        if self.rule:
            rule_result = utils.execute_rule(self, self.rule, args)
            return rule_result.result, rule_result.errors

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
        nb = coop_date.duration_between(from_date, end_date,
            self.indemnification_calc_unit)
        res['end_date'] = end_date
        res['nb_of_unit'] = nb
        res['unit'] = self.indemnification_calc_unit
        res['amount_per_unit'], re_errs = self.give_me_result(args)
        return res, errs + re_errs

    @staticmethod
    def default_indemnification_calc_unit():
        return 'day'
