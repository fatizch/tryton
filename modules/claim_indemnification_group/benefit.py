# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta
from trytond.pyson import And, Eval, Or

from trytond.modules.cog_utils import fields, model

__all__ = [
    'Benefit',
    'BenefitRule',
    'BenefitRuleIndemnification',
    'BenefitRuleDeductible',
    'BenefitRuleRevaluation',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    def required_extra_data(self, service, date):
        if self.benefit_rules and service:
            return self.benefit_rules[0].required_extra_data(service, date)
        return []

    def get_extra_data_def(self, service):
        values = super(Benefit, self).get_extra_data_def(service)
        if not self.benefit_rules or not service:
            return values
        required = [e.name
            for e in self.required_extra_data(service,
                service.loss.get_date())]
        return {k: v for k, v in values.iteritems() if k in required}


class BenefitRule:
    __metaclass__ = PoolMeta
    __name__ = 'benefit.rule'

    indemnification_rules = fields.Many2Many(
        'benefit_rule-indemnification_rule', 'benefit', 'rule',
        'Indemnification Rules', states={
            'invisible': Eval('force_indemnification_rule', False)},
        depends=['force_indemnification_rule'])
    deductible_rules = fields.Many2Many('benefit_rule-deductible_rule',
        'benefit', 'rule', 'Deductible Rules', states={
            'invisible': Eval('force_deductible_rule', False)},
        depends=['force_deductible_rule'])
    revaluation_rules = fields.Many2Many('benefit_rule-revaluation_rule',
        'benefit', 'rule', 'Revaluation Rules', states={
            'invisible': Eval('force_revaluation_rule', False)},
        depends=['force_revaluation_rule'])
    force_indemnification_rule = fields.Function(
        fields.Boolean('Force Indemnification Rule',
            states={'invisible': ~Eval('is_group')},
            depends=['is_group']),
        'get_force_rule', setter='setter_void')
    force_deductible_rule = fields.Function(
        fields.Boolean('Force Deductible Rule',
            states={'invisible': ~Eval('is_group')},
            depends=['is_group']),
        'get_force_rule', setter='setter_void')
    force_revaluation_rule = fields.Function(
        fields.Boolean('Force Revaluation Rule',
            states={'invisible': ~Eval('is_group')},
            depends=['is_group']),
        'get_force_rule', setter='setter_void')

    is_group = fields.Function(
        fields.Boolean('Is Group'),
        'get_is_group')

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        cls.indemnification_rule.states['invisible'] = And(
            cls.indemnification_rule.states.get('invisible', True),
            ~Eval('force_indemnification_rule'))
        cls.indemnification_rule.depends.append('force_indemnification_rule')
        cls.indemnification_rule_extra_data.states['invisible'] = Or(
            cls.indemnification_rule_extra_data.states.get('invisible', True),
            ~Eval('force_indemnification_rule'))
        cls.indemnification_rule_extra_data.depends.append(
            'force_indemnification_rule')
        cls.deductible_rule.states['invisible'] = And(
            cls.deductible_rule.states.get('invisible',
                True), ~Eval('force_deductible_rule'))
        cls.deductible_rule.depends.append('force_deductible_rule')
        cls.deductible_rule_extra_data.states['invisible'] = Or(
            cls.deductible_rule_extra_data.states.get('invisible',
                True), ~Eval('force_deductible_rule'))
        cls.deductible_rule_extra_data.depends.append('force_deductible_rule')
        cls.revaluation_rule.states['invisible'] = And(
            cls.revaluation_rule.states.get('invisible',
                True), ~Eval('force_revaluation_rule'))
        cls.revaluation_rule.depends.append('force_revaluation_rule')
        cls.revaluation_rule_extra_data.states['invisible'] = Or(
            cls.revaluation_rule_extra_data.states.get('invisible',
                True), ~Eval('force_revaluation_rule'))
        cls.revaluation_rule_extra_data.depends.append('force_revaluation_rule')

    @classmethod
    def default_force_deductible_rule(cls):
        return True

    @classmethod
    def default_force_indemnification_rule(cls):
        return True

    @classmethod
    def default_force_revaluation_rule(cls):
        return True

    @fields.depends('benefit', 'is_group')
    def on_change_benefit(self):
        self.is_group = self.benefit.is_group

    def _on_change_rule(self, rule_name):
        if getattr(self, 'force_' + rule_name, None):
            setattr(self, rule_name, None)
            setattr(self, rule_name + '_extra_data', {})
            setattr(self, rule_name + 's', [])
        else:
            setattr(self, rule_name + 's', [getattr(self, rule_name)]
                if getattr(self, rule_name) else [])
            setattr(self, rule_name, None)
            setattr(self, rule_name + '_extra_data', {})

    @fields.depends('deductible_rule', 'deductible_rule_extra_data',
        'deductible_rules', 'force_deductible_rule')
    def on_change_force_deductible_rule(self):
        self._on_change_rule('deductible_rule')

    @fields.depends('force_indemnification_rule', 'indemnification_rules',
        'rule', 'rule_extra_data')
    def on_change_force_indemnification_rule(self):
        self._on_change_rule('indemnification_rule')

    @fields.depends('revaluation_rule', 'revaluation_rule_extra_data',
        'revaluation_rules', 'force_revaluation_rule')
    def on_change_force_revaluation_rule(self):
        self._on_change_rule('revaluation_rule')

    def get_force_rule(self, name):
        return bool(getattr(self, name[6:]))

    def get_is_group(self, name):
        return self.benefit.is_group

    def _calculate_rule(self, rule_name, args, default_value):
        option = args.get('option', None)
        if not option or getattr(self, 'force_' + rule_name):
            return getattr(super(BenefitRule, self),
                'calculate_' + rule_name)(args)
        # Use option defined rule
        version = option.get_version_at_date(args['date'])
        option_benefit = version.get_benefit(self.benefit)
        if not getattr(option_benefit, rule_name):
            return default_value
        return getattr(option_benefit, 'calculate_' + rule_name)(args)

    def calculate_deductible_rule(self, args):
        return self._calculate_rule('deductible_rule', args, datetime.date.min)

    def calculate_indemnification_rule(self, args):
        return self._calculate_rule('indemnification_rule', args, [])

    def calculate_revaluation_rule(self, args):
        return self._calculate_rule('revaluation_rule', args, [])

    def required_extra_data_for_rule(self, rule_name, date, option):
        if getattr(self, 'force_' + rule_name):
            return getattr(self, rule_name).extra_data_used
        # Use option defined rule
        version = option.get_version_at_date(date)
        option_benefit = version.get_benefit(self.benefit)
        rule = getattr(option_benefit, rule_name)
        if not rule:
            return []
        return rule.extra_data_used

    def required_extra_data(self, service, date):
        res = []
        for rule_name in ('deductible_rule', 'indemnification_rule',
                'revaluation_rule'):
            res.extend(self.required_extra_data_for_rule(rule_name, date,
                    service.option))
        return res

    def must_revaluate(self):
        if self.force_indemnification_rule:
            return super(BenefitRule, self).must_revaluate()
        return bool(self.revaluation_rules)


class BenefitRuleIndemnification(model.CoopSQL):
    'Benefit Rule - Indemnification'

    __name__ = 'benefit_rule-indemnification_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')


class BenefitRuleDeductible(model.CoopSQL):
    'Benefit Rule - Deductible'

    __name__ = 'benefit_rule-deductible_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')


class BenefitRuleRevaluation(model.CoopSQL):
    'Benefit Rule - Revaluation'

    __name__ = 'benefit_rule-revaluation_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')
