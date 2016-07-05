# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Not, Or

from trytond.modules.cog_utils import fields, model, coop_string
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'Plan',
    'PlanLines',
    'Agent',
    ]


class Plan:
    __name__ = 'commission.plan'

    rule_engine_key = fields.Char('Rule Engine Key',
        states={'invisible': Eval('type_') != 'agent'},
        help='key to retrieve the commission plan in rule engine algorithm',
        depends=['type_'])
    extra_data_def = fields.Many2Many('commission-plan-extra_data',
        'plan', 'extra_data_def', 'Extra Data',
        domain=[('kind', '=', 'agent')])

    def get_context_formula(self, amount, product, pattern=None):
        context = super(Plan, self).get_context_formula(amount, product,
            pattern)
        if pattern and 'option' in pattern:
            context['names']['option'] = pattern['option']
        if pattern and 'agent' in pattern:
            context['names']['agent'] = pattern['agent']
            context['names']['extra_data'] = pattern['agent'].extra_data or {}
        return context


class PlanLines(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoopSQL, model.CoopView):
    __name__ = 'commission.plan.line'

    use_rule_engine = fields.Boolean('Use Rule Engine')
    formula_description = fields.Function(fields.Char('Formula'),
        'get_formula_description')

    @classmethod
    def __setup__(cls):
        super(PlanLines, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'commission')]
        cls.rule.states['invisible'] = Not(Eval('use_rule_engine', True))
        cls.rule.states['required'] = Eval('use_rule_engine', True)
        cls.rule.depends.append('use_rule_engine')

        cls.rule_extra_data.depends.append('use_rule_engine')
        cls.rule_extra_data.states['invisible'] = Or(
            cls.rule_extra_data.states['invisible'],
            Not(Eval('use_rule_engine', True)))
        cls.formula.states['invisible'] = Eval('use_rule_engine', True)
        cls.formula.depends.append('use_rule_engine')

    def get_formula_description(self, name):
        if self.use_rule_engine:
            return self.rule.name
        else:
            return self.formula

    def get_amount(self, **context):
        if not self.use_rule_engine:
            return super(PlanLines, self).get_amount(**context)
        args = context['names']
        if 'option' in context['names']:
            context['names']['option'].init_dict_for_rule_engine(args)
        if 'invoice_line' in context['names']:
            args['date'] = context['names']['invoice_line'].coverage_start
        return Decimal(self.calculate_rule(args))

    def check_formula(self):
        return True

    def get_func_key(self, name):
        return self.options_extract


class Agent:
    __name__ = 'commission.agent'

    extra_data = fields.Dict('extra_data', 'Extra Data')
    extra_data_string = extra_data.translated('extra_data')
    extra_data_summary = fields.Function(
        fields.Text('Extra Data Summary'),
        'get_extra_data_summary')

    @fields.depends('plan')
    def on_change_with_extra_data(self):
        res = {}
        if not self.plan:
            return res
        self.extra_data = getattr(self, 'extra_data', {}) or {}
        for extra_data_def in self.plan.extra_data_def:
            if extra_data_def.name in self.extra_data:
                res[extra_data_def.name] = self.extra_data[extra_data_def.name]
            else:
                res[extra_data_def.name] = extra_data_def.get_default_value(
                    None)
        return res

    def get_all_extra_data(self, at_date):
        return self.extra_data if getattr(self, 'extra_data', None) else {}

    @classmethod
    def get_extra_data_summary(cls, agents, name):
        return Pool().get('extra_data').get_extra_data_summary(agents,
            'extra_data')

    @classmethod
    def format_hash(cls, hash_dict):
        return super(Agent, cls).format_hash(hash_dict) + '\n' + \
            coop_string.translate_label(cls, 'extra_data') + ' : ' + \
            str(hash_dict['extra_data'])

    def get_hash(self):
        return super(Agent, self).get_hash() + (
            ('extra_data', tuple([x for x in sorted(self.extra_data.items(),
                            key=lambda x: x[0])])),)
