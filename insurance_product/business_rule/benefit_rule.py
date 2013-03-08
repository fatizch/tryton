import copy

from trytond.model import fields
from trytond.pyson import Eval, Or, Bool

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


class BenefitRule(BusinessRuleRoot, model.CoopSQL):
    'Benefit Rule'

    __name__ = 'ins_product.benefit_rule'

    amount_evolves_over_time = fields.Boolean('Evolves Over Time',
        states={
            'invisible': Eval('_parent_offered', {}).get(
                'indemnification_kind') != 'period',
        })
    amount_kind = fields.Selection(AMOUNT_KIND, 'Amount Kind',
        states={
            'invisible': Or(
                STATE_SIMPLE,
                Bool(Eval('amount_evolves_over_time')),
            )
        })
    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible':
                Or(
                    STATE_SIMPLE,
                    Eval('amount_kind') != 'amount',
                    Bool(Eval('amount_evolves_over_time')),
                )
        })
    coef_coverage_amount = fields.Numeric('Multiplier',
        states={
            'invisible':
                Or(
                    STATE_SIMPLE,
                    Eval('amount_kind') != 'cov_amount',
                    Bool(Eval('amount_evolves_over_time')),
                )
        }, help='Add a multiplier to apply to the coverage amount', )
    indemnification_calc_unit = fields.Selection(date.DAILY_DURATION,
        'Indemnification Calculation Unit',
        states={
            'invisible':
                Or(
                    Eval('_parent_offered', {}).get(
                        'indemnification_kind') != 'period',
                    Bool(Eval('amount_evolves_over_time')),
                )
        }, sort=False)
    sub_benefit_rules = fields.One2Many('ins_product.sub_benefit_rule',
        'benefit_rule', 'Sub Benefit Rules',
        states={'invisible': ~Bool(Eval('amount_evolves_over_time'))})

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

    def get_coverage_amount(self, args):
        if 'option' in args:
            return args['option'].get_coverage_amount()

    def get_simple_result(self, args):
        if self.amount_kind == 'amount':
            return self.amount, []
        elif self.amount_kind == 'cov_amount':
            return self.get_coverage_amount(args), []

    def get_indemnification_for_period(self, args):
        if not self.amount_evolves_over_time:
            return self.get_fixed_indemnification_for_period(args)
        else:
            if not 'start_date' in args:
                return [{}], 'missing_date'
            return self.get_evolving_indemnifications_for_period(args)

    def get_fixed_indemnification_for_period(self, args):
        errs = []
        res = {}
        res['start_date'] = args['start_date']
        if not 'end_date' in args:
            nb = 1
        else:
            nb = date.duration_between(args['start_date'], args['end_date'],
            self.indemnification_calc_unit)
            res['end_date'] = args['end_date']
        res['nb_of_unit'] = nb
        res['unit'] = self.indemnification_calc_unit
        res['amount_per_unit'], re_errs = self.give_me_result(args)
        return [res], errs + re_errs

    def get_evolving_indemnifications_for_period(self, args):
        errs = []
        res = []
        start_date = args['start_date']
        for sub_rule in self.sub_benefit_rules:
            indemn, err = sub_rule.get_indemnification_for_period(args,
                start_date)
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
        '/', sort=False)
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
        return min(to_date, max_end_date)

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
        end_date = self.get_end_date(from_date, args['end_date'])
        nb = date.duration_between(from_date, end_date,
            self.indemnification_calc_unit)
        res['end_date'] = end_date
        res['nb_of_unit'] = nb
        res['unit'] = self.indemnification_calc_unit
        res['amount_per_unit'], re_errs = self.give_me_result(args)
        return res, errs + re_errs

    @staticmethod
    def default_duration():
        return 'day'

    @staticmethod
    def default_indemnification_calc_unit():
        return 'day'
