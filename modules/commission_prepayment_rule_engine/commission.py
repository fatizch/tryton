import datetime
from decimal import Decimal
from types import FloatType, IntType

from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond.pyson import Eval, Bool, Not

from trytond.modules.cog_utils import fields, model, coop_string
from trytond.modules.rule_engine import RuleMixin

__all__ = [
    'Plan',
    'PrepaymentPaymentDateRule',
    'PlanLines',
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

    def compute_prepayment_schedule(self, option, agent):
        if self.prepayment_payment_rule and option:
            args = {
                'date': option.initial_start_date,
                'extra_data': agent.extra_data
                }
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
        return super(Plan, self).compute_prepayment_schedule(option, agent)


class PrepaymentPaymentDateRule(RuleMixin, model.CoopSQL, model.CoopView):
    'Prepayment Payment Date Rule'

    __name__ = 'commission.plan.prepayment.payment_rule'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)

    @classmethod
    def __setup__(cls):
        super(PrepaymentPaymentDateRule, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls.rule.domain = [('type_', '=', 'commission')]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class PlanLines:
    __name__ = 'commission.plan.line'

    prepayment_rule = fields.Many2One('rule_engine', 'Prepayment Rule',
        ondelete='RESTRICT', domain=[('type_', '=', 'commission')],
        depends=['use_rule_engine'],
        states={
            'invisible': Not(Eval('use_rule_engine', True))})
    prepayment_rule_extra_data = fields.Dict('rule_engine.rule_parameter',
        'Prepayment Rule Extra Data', states={
            'invisible': Not(Bool(Eval('prepayment_rule_extra_data', False)))})
    prepayment_formula_description = fields.Function(fields.Char('Prepayment'),
        'get_prepayment_formula_description')

    @classmethod
    def __setup__(cls):
        super(PlanLines, cls).__setup__()
        cls.prepayment_formula.states['invisible'] = Eval('use_rule_engine',
            True)
        cls.prepayment_formula.depends.append('use_rule_engine')

    def get_formula_description(self, name):
        if self.use_rule_engine:
            if self.prepayment_rule:
                return self.prepayment_rule.name
        else:
            return self.prepayment_formula

    def get_prepayment_amount(self, **context):
        if not self.use_rule_engine:
            return super(PlanLines, self).get_prepayment_amount(**context)
        if not self.prepayment_rule:
            return
        args = context['names']
        if 'option' in context['names']:
            context['names']['option'].init_dict_for_rule_engine(args)
            args['date'] = context['names']['option'].initial_start_date
        return Decimal(self.prepayment_rule.execute(
                args, self.prepayment_rule_extra_data).result)

    @fields.depends('prepayment_rule', 'prepayment_rule_extra_data')
    def on_change_with_prepayment_rule_extra_data(self):
        if not self.prepayment_rule:
            return {}
        return self.prepayment_rule.get_extra_data_for_on_change(
            self.prepayment_rule_extra_data)
