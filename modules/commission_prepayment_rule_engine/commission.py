import datetime
from types import FloatType, IntType

from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, model, coop_string

from trytond.modules.rule_engine import RuleMixin

__all__ = [
    'Plan',
    'PrepaymentPaymentDateRule',
    ]
__metaclass__ = PoolMeta


class Plan:
    __name__ = 'commission.plan'

    prepayment_payment_rule = fields.Many2One(
        'commission.plan.prepayment.payment_rule',
        'Payment Date Rule for Prepayment', ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Plan, cls).__setup__()
        cls._error_messages.update({
                'invalid_rule_result': 'Prepayment payment rule result %s is '
                'not matching the expected format [(date, percentage)]',
                })

    def compute_prepayment_schedule(self, option):
        if self.prepayment_payment_rule and option:
            args = {}
            option.init_dict_for_rule_engine(args)
            schedule = self.prepayment_payment_rule.calculate(args)
            # check rule result
            if not schedule or not isinstance(schedule, list):
                self.raise_user_error('invalid_rule_result', schedule)
            try:
                for date, percentage in schedule:
                    if (not isinstance(date, datetime.date) or
                            not isinstance(percentage, FloatType) and
                            not isinstance(percentage, IntType)):
                        self.raise_user_error('invalid_rule_result', schedule)
            except:
                self.raise_user_error('invalid_rule_result', schedule)

            return schedule
        return super(Plan, self).compute_prepayment_schedule(option)


class PrepaymentPaymentDateRule(RuleMixin, model.CoopSQL, model.CoopView):
    'Prepayment Payment Date Rule'

    __name__ = 'commission.plan.prepayment.payment_rule'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)

    @classmethod
    def __setup__(cls):
        super(PrepaymentPaymentDateRule, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)
