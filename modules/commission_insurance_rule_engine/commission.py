from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Not, Or

from trytond.modules.cog_utils import fields, model
from trytond.modules.rule_engine import RuleMixin

__metaclass__ = PoolMeta
__all__ = [
    'Plan',
    'PlanLines',
    ]


class Plan:
    __name__ = 'commission.plan'

    rule_engine_key = fields.Char('Rule Engine Key',
        states={'invisible': Eval('type_') != 'agent'},
        help='key to retrieve the commission plan in rule engine algorithm',
        depends=['type_'])

    def get_context_formula(self, amount, product, pattern=None):
        context = super(Plan, self).get_context_formula(amount, product,
            pattern)
        if pattern and 'option' in pattern:
            context['names']['option'] = pattern['option']
        return context


class PlanLines(RuleMixin, model.CoopSQL, model.CoopView):
    __name__ = 'commission.plan.line'

    use_rule_engine = fields.Boolean('Use Rule Engine')
    formula_description = fields.Function(fields.Char('Formula'),
        'get_formula_description')

    def get_formula_description(self, name):
        if self.use_rule_engine:
            return self.rule.name
        else:
            return self.formula

    @classmethod
    def __setup__(cls):
        super(PlanLines, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'commission')]
        cls.rule.required = False
        cls.rule.states['invisible'] = Not(Eval('use_rule_engine', True))
        cls.rule.states['required'] = Eval('use_rule_engine', True)
        cls.rule.depends.append('use_rule_engine')

        cls.rule_extra_data.depends.append('use_rule_engine')
        cls.rule_extra_data.states['invisible'] = Or(
            cls.rule_extra_data.states['invisible'],
            Not(Eval('use_rule_engine', True)))
        cls.formula.states['invisible'] = Eval('use_rule_engine', True)
        cls.formula.depends.append('use_rule_engine')

    def get_amount(self, **context):
        if not self.use_rule_engine:
            return super(PlanLines, self).get_amount(**context)
        args = {}
        if 'option' in context['names']:
            context['names']['option'].init_dict_for_rule_engine(args)
        else:
            args = context['names']
        if 'invoice_line' in context['names']:
            args['invoice_line'] = context['names']['invoice_line']
            args['date'] = context['names']['invoice_line'].coverage_start
        args['amount'] = context['names']['amount']
        return Decimal(self.calculate(args))

    def check_formula(self):
        return True
