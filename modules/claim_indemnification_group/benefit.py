# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta
from trytond.pyson import And, Eval, Or, Bool
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, model
from trytond.modules.claim_indemnification \
    import BenefitRule as OriginalBenefitRule

__all__ = [
    'Benefit',
    'BenefitCompanyProduct',
    'BenefitRule',
    'BenefitRuleIndemnification',
    'BenefitRuleDeductible',
    'BenefitRuleRevaluation',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    company_products = fields.Many2Many('benefit-company_product', 'benefit',
        'product', 'Company Products', help='Products available when '
        'paying a company')

    def _extra_data_structure(self):
        base = super(Benefit, self)._extra_data_structure()
        service = ServerContext().get('service', None)
        if not service or not service.benefit.is_group:
            return base
        version = service.option.get_version_at_date(service.loss.get_date())
        option_benefit = version.get_benefit(service.benefit)
        base.update(option_benefit._extra_data_structure())
        return base

    def get_benefit_accounts(self):
        accounts = super(Benefit, self).get_benefit_accounts()
        if not self.is_group:
            return accounts
        return accounts + [
            x.account_expense_used for x in self.company_products
            if x.account_expense and x.account_expense_used]


class BenefitCompanyProduct(model.CoogSQL):
    'Benefit Company Product relation'

    __name__ = 'benefit-company_product'

    benefit = fields.Many2One('benefit', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    product = fields.Many2One('product.product', 'Product', required=True,
        ondelete='RESTRICT')


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
    force_annuity_frequency = fields.Boolean(
        'Force Annuity Frenquency',
        help='Get annuity frequency from product if True',
        states={'invisible': ~Eval('is_group') | ~Eval('requires_frequency')},
        depends=['is_group', 'requires_frequency'])
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
        cls._error_messages.update({
                'multiple_indemnification_rules': 'Multiple indemnification '
                'rules allowed',
                })
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
        cls.revaluation_rule_extra_data.depends.append(
            'force_revaluation_rule')
        cls.annuity_frequency.states['invisible'] = Or(
                cls.annuity_frequency.states.get('invisible'),
                And(Bool(Eval('is_group')), ~Eval('force_annuity_frequency')))
        cls.annuity_frequency.depends.extend(['force_annuity_frequency',
            'is_group'])

    def get_rec_name(self, name):
        if not self.indemnification_rule and self.indemnification_rules:
            return self.raise_user_error('multiple_indemnification_rules',
                raise_exception=False)
        return super(BenefitRule, self).get_rec_name(name)

    @classmethod
    def default_force_annuity_frequency(cls):
        return True

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
        super(BenefitRule, self).on_change_benefit()
        self.is_group = self.benefit.is_group if self.benefit else False

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
        'indemnification_rule', 'indemnification_rule_extra_data')
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

    def _calculate_rule(self, rule_name, args, default_value, **kwargs):
        option = args.get('option', None)
        if not option or getattr(self, 'force_' + rule_name):
            return getattr(OriginalBenefitRule, 'calculate_' + rule_name)(
                self, args, **kwargs)
        # Use option defined rule
        version = option.get_version_at_date(args['date'])
        option_benefit = version.get_benefit(self.benefit)
        if not option_benefit or not getattr(option_benefit, rule_name):
            return default_value
        return getattr(option_benefit, 'calculate_' + rule_name)(args,
            **kwargs)

    def calculate_deductible_rule(self, args, **kwargs):
        return self._calculate_rule('deductible_rule', args, datetime.date.min,
            **kwargs)

    def calculate_indemnification_rule(self, args, **kwargs):
        return self._calculate_rule('indemnification_rule', args, [], **kwargs)

    def calculate_revaluation_rule(self, args, **kwargs):
        return self._calculate_rule('revaluation_rule', args, [], **kwargs)

    def must_revaluate(self):
        if self.force_indemnification_rule:
            return super(BenefitRule, self).must_revaluate()
        return bool(self.revaluation_rules)


class BenefitRuleIndemnification(model.CoogSQL):
    'Benefit Rule - Indemnification'

    __name__ = 'benefit_rule-indemnification_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')


class BenefitRuleDeductible(model.CoogSQL):
    'Benefit Rule - Deductible'

    __name__ = 'benefit_rule-deductible_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')


class BenefitRuleRevaluation(model.CoogSQL):
    'Benefit Rule - Revaluation'

    __name__ = 'benefit_rule-revaluation_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')
