#-*- coding:utf-8 -*-
from trytond.pyson import Eval, Or

from trytond.modules.coop_utils import model, fields, utils
from trytond.modules.insurance_product.product import DEF_CUR_DIG
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE

__all__ = [
    'CoverageAmountRule',
]


class CoverageAmountRule(BusinessRuleRoot, model.CoopSQL):
    'Coverage Amount Rule'

    __name__ = 'ins_product.coverage_amount_rule'

    kind = fields.Selection(
        [
            ('amount', 'Amount'),
            ('cal_list', 'Calculated List')
        ],
        'Kind', states={'invisible': STATE_SIMPLE}, )
    amounts = fields.Char(
        'Amounts', help='Specify amounts separated by ;',
        states={
            'invisible': Or(
                (Eval('kind') != 'amount'),
                (Eval('config_kind') != 'simple'),
            ),
        }, depends=['config_kind', 'kind'])
    amount_start = fields.Numeric(
        'From',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': Or(
                (Eval('kind') != 'cal_list'),
                (Eval('config_kind') != 'simple'),
            ),
        }, depends=['config_kind', 'kind'])
    amount_end = fields.Numeric(
        'To',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': Or(
                (Eval('kind') != 'cal_list'),
                (Eval('config_kind') != 'simple'),
            ),
        }, depends=['config_kind', 'kind'])
    amount_step = fields.Numeric(
        'Step',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': Or(
                (Eval('kind') != 'cal_list'),
                (Eval('config_kind') != 'simple'),
            ),
        })

    @classmethod
    def __setup__(cls):
        super(CoverageAmountRule, cls).__setup__()
        cls._error_messages.update({
            'amounts_float': 'Amounts need to be floats !',
        })

    def validate_those_amounts(self, amounts):
        try:
            return map(float, amounts.split(';'))
        except ValueError:
            return False

    def give_me_allowed_amounts(self, args):
        if self.config_kind == 'simple':
            if self.kind == 'amount' and self.amounts:
                res = map(float, self.amounts.split(';'))
                return res, []
            elif self.kind == 'cal_list' and self.amount_end:
                start = self.amount_start if self.amount_start else 0
                step = self.amount_step if self.amount_step else 1
                res = range(start, self.amount_end + 1, step)
                return res, []
        elif self.config_kind == 'advanced' and self.rule:
            mess = []
            try:
                res, mess, errs = utils.execute_rule(self, self.rule, args)
                if res:
                    res = self.validate_those_amounts(res)
            except Exception:
                res = []
                errs = ['Invalid rule !']
            if res is False:
                res = []
                errs = ['Invalid amounts']
            return res, mess + errs

    def give_me_coverage_amount_validity(self, args):
        if not('data' in args and hasattr(args['data'], 'coverage_amount')
                and not args['data'].coverage_amount is None):
            return (False, []), ['Coverage amount not found']
        amount = args['data'].coverage_amount
        if hasattr(self, 'amounts') and self.amounts:
            if not amount in self.give_me_allowed_amounts(args)[0]:
                errs = ['Amount %.2f not allowed on coverage %s' % (
                    amount,
                    args['data'].coverage.code)]
                return (False, errs), []
        return (True, []), []

    def pre_validate(self):
        if not hasattr(self, 'amounts'):
            return
        if self.config_kind == 'simple' and self.kind == 'amount':
            if self.validate_those_amounts(self.amounts) is False:
                self.raise_user_error('amounts_float')

    @staticmethod
    def default_kind():
        return 'amount'

    def get_simple_rec_name(self):
        return self.give_me_allowed_amounts({})[0]
