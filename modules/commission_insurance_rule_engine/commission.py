# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Not, Or

from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.offered.extra_data import with_extra_data
from trytond.modules.offered.extra_data import with_extra_data_def

__all__ = [
    'Plan',
    'PlanLines',
    'Agent',
    ]


class Plan(with_extra_data_def('commission-plan-extra_data', 'plan', 'agent')):
    __metaclass__ = PoolMeta
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
        if pattern and 'agent' in pattern:
            context['names']['agent'] = pattern['agent']
            context['names']['extra_data'] = pattern['agent'].extra_data or {}
        return context


class PlanLines(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    __metaclass__ = PoolMeta
    __name__ = 'commission.plan.line'

    use_rule_engine = fields.Boolean('Use Rule Engine')

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
        if self.rule:
            return self.get_rule_extract()
        else:
            return super(PlanLines, self).get_formula_description(name)

    def get_amount(self, **context):
        if not self.use_rule_engine:
            return super(PlanLines, self).get_amount(**context)
        args = context['names']
        if 'option' in context['names']:
            context['names']['option'].init_dict_for_rule_engine(args)
        if 'invoice_line' in context['names']:
            # use the commission start date as date instead of invoice line
            # date to handle commission split
            if 'commission_start_date' in context['names']:
                args['date'] = context['names']['commission_start_date']
            else:
                args['date'] = context['names']['invoice_line'].coverage_start
        return Decimal(self.calculate_rule(args))

    def check_formula(self):
        return True

    def get_func_key(self, name):
        return self.options_extract


class Agent(with_extra_data(['agent'], schema='plan')):
    __metaclass__ = PoolMeta
    __name__ = 'commission.agent'

    @classmethod
    def format_hash(cls, hash_dict):
        return super(Agent, cls).format_hash(hash_dict) + '\n' + \
            coog_string.translate_label(cls, 'extra_data') + ' : ' + \
            str(hash_dict['extra_data'])

    def get_hash(self):
        return super(Agent, self).get_hash() + (
            ('extra_data', tuple([x for x in sorted(self.extra_data.items(),
                            key=lambda x: x[0])])),)
