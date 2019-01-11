# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond.pyson import Eval, Bool, Not, And

from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Plan',
    'PrepaymentPaymentDateRule',
    'PlanLines',
    ]


class Plan(metaclass=PoolMeta):
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

    def getter_is_prepayment(self, name):
        if self.prepayment_payment_rule:
            return True
        return super(Plan, self).getter_is_prepayment(name)

    @classmethod
    def search_is_prepayment(cls, name, clause):
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[1] in reverse:
            if clause[2]:
                return [('prepayment_payment_rule', reverse[clause[1]], None)]
            else:
                return [('prepayment_payment_rule', clause[1], None)]
        else:
            return super(Plan, cls).search_is_prepayment(name, clause)

    def compute_prepayment_schedule(self, option, agent):
        if self.prepayment_payment_rule and option:
            args = {
                'date': option.initial_start_date,
                'extra_data': agent.extra_data
                }
            option.init_dict_for_rule_engine(args)
            schedule = self.prepayment_payment_rule.calculate_rule(args)
            # check rule result
            if not schedule or not isinstance(schedule, list):
                self.raise_user_error('invalid_rule_result', schedule)
            try:
                for date, percentage in schedule:
                    if (not isinstance(date, datetime.date) or
                            not isinstance(percentage, float) and
                            not isinstance(percentage, int) and
                            not isinstance(percentage, Decimal)):
                        self.raise_user_error('invalid_rule_result', schedule)
            except ValueError:
                self.raise_user_error('invalid_rule_result', schedule)

            return schedule
        return super(Plan, self).compute_prepayment_schedule(option, agent)

    @fields.depends('lines', 'is_prepayment', 'prepayment_payment_rule')
    def on_change_is_prepayment(self):
        for line in self.lines:
            line.is_prepayment = self.is_prepayment
            if not self.is_prepayment:
                line.prepayment_rule = None
        if not self.is_prepayment:
            self.prepayment_payment_rule = None
        if self.lines:
            self.lines = list(self.lines)


class PrepaymentPaymentDateRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
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
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'commission')]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


class PlanLines(get_rule_mixin('prepayment_rule', 'Prepayment Rule'),
        metaclass=PoolMeta):
    __name__ = 'commission.plan.line'

    is_prepayment = fields.Function(fields.Boolean('Is Prepayment'),
            getter='on_change_with_is_prepayment')

    @classmethod
    def __setup__(cls):
        super(PlanLines, cls).__setup__()
        cls.prepayment_rule.domain = [('type_', '=', 'commission')]
        cls.prepayment_rule.depends = ['use_rule_engine', 'is_prepayment']
        cls.prepayment_rule.states = {
                'invisible': Not(And(Bool(Eval('use_rule_engine')),
                    Bool(Eval('is_prepayment'))))
                }
        cls.prepayment_formula.states['invisible'] = Eval('use_rule_engine',
            True)
        cls.prepayment_formula.depends.append('use_rule_engine')
        cls.prepayment_rule.help = (
            'Returns a tuple with the prepayment commission amount and rate')
        cls._error_messages.update({
                'linear': 'Linear',
                'prepayment': 'Prepayment',
                })

    def get_formula_description(self, name):
        lines = [super(PlanLines, self).get_formula_description(name)]
        if self.prepayment_rule:
            if lines:
                lines[0] = '%s : %s' % (
                    self.raise_user_error('linear', raise_exception=False),
                    lines[0])
            lines.append('%s : %s' % (
                    self.raise_user_error('prepayment', raise_exception=False),
                    self.get_prepayment_rule_extract()))
        return ' \n'.join(lines)

    def get_prepayment_amount(self, **context):
        if not self.use_rule_engine:
            return super(PlanLines, self).get_prepayment_amount(**context)
        if not self.prepayment_rule:
            return
        args = context['names']
        if 'option' in context['names']:
            context['names']['option'].init_dict_for_rule_engine(args)
            args['date'] = context['names']['option'].initial_start_date
            args['first_year_premium'] = context['names']['first_year_premium']
        return self.calculate_prepayment_rule(args)

    @fields.depends('prepayment_rule', 'prepayment_rule_extra_data')
    def on_change_with_prepayment_rule_extra_data(self):
        if not self.prepayment_rule:
            return {}
        return self.prepayment_rule.get_extra_data_for_on_change(
            self.prepayment_rule_extra_data)

    @fields.depends('plan', 'use_rule_engine')
    def on_change_with_is_prepayment(self, name=None):
        return self.plan.is_prepayment if self.plan else None
