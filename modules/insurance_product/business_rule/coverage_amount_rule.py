#-*- coding:utf-8 -*-
from trytond.pyson import Eval, Or, And

from trytond.modules.coop_utils import model, fields
from trytond.modules.offered.offered import DEF_CUR_DIG
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_ADVANCED

__all__ = [
    'CoverageAmountRule',
]


class CoverageAmountRule(BusinessRuleRoot, model.CoopSQL):
    'Coverage Amount Rule'

    __name__ = 'offered.coverage_amount.rule'

    kind = fields.Selection(
        [
            ('amount', 'Amount'),
            ('cal_list', 'Calculated List'),
            ('another_coverage', 'From another Coverage'),
        ],
        'Kind', states={'invisible': STATE_ADVANCED}, )
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
    other_coverage = fields.Many2One('offered.coverage', 'Source Coverage',
        domain=[('coverage_amount_rules', '!=', None)],
        states={
            'invisible': Or(
                (Eval('config_kind') != 'simple'),
                (Eval('kind') != 'another_coverage'),
            ),
            'required': And(
                (Eval('config_kind') != 'simple'),
                (Eval('kind') != 'another_coverage'),
            )},
        depends=['kind', 'config_kind'])

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
            elif self.kind == 'another_coverage':
                # Returning nothing will make the contract assume there is no
                # need to input a coverage amount on the covered data, which is
                # exactly what we need
                return self.other_coverage.get_result('allowed_amounts', args)
        elif self.config_kind == 'advanced' and self.rule:
            rule_result = self.get_rule_result(args)
            if rule_result.result_set:
                res = self.validate_those_amounts(rule_result.result)
            if not res and not rule_result.has_errors:
                res = []
                errs = ['Invalid amounts']
            return res, rule_result.print_errors() + errs

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

    def give_me_dependant_amount_coverage(self, args):
        if self.kind != 'another_coverage':
            return None, []
        return self.other_coverage, []

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
