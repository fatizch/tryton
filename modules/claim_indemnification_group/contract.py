# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Len

from trytond.modules.cog_utils import fields, model
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'Option',
    'OptionVersion',
    'OptionBenefit',
    ]


class Option:
    __name__ = 'contract.option'

    @classmethod
    def view_attributes(cls):
        return super(Option, cls).view_attributes() + [
            ("/form/notebook/page[@id='rules']", 'states', {
                    'invisible': ~Eval('is_group', False)})]

    @classmethod
    def new_option_from_coverage(cls, coverage, *args, **kwargs):
        new_option = super(Option, cls).new_option_from_coverage(coverage,
            *args, **kwargs)
        if not coverage.is_group:
            return new_option
        new_option.versions[0].init_from_coverage(coverage)
        return new_option


class OptionVersion:
    __name__ = 'contract.option.version'

    benefits = fields.One2Many('contract.option.benefit', 'version',
        'Benefits', delete_missing=True)

    @classmethod
    def view_attributes(cls):
        return super(OptionVersion, cls).view_attributes() + [
            ("/form/group[@id='invisible_benefit']", 'states', {
                    'invisible': Len(Eval('benefits', [])) == 1})]

    def init_from_coverage(self, coverage):
        OptionBenefit = Pool().get('contract.option.benefit')
        benefits = []
        for benefit in coverage.benefits:
            new_option_benefit = OptionBenefit(benefit=benefit)
            new_option_benefit.init_from_benefit()
            benefits.append(new_option_benefit)
        self.benefits = benefits

    def get_benefit(self, benefit):
        for option_benefit in self.benefits:
            if option_benefit.benefit == benefit:
                return option_benefit


class OptionBenefit(get_rule_mixin('deductible_rule', 'Deductible Rule'),
        get_rule_mixin('indemnification_rule', 'Indemnification Rule'),
        get_rule_mixin('revaluation_rule', 'Revaluation Rule'),
        model.CoopSQL, model.CoopView):
    'Option Benefit'

    __name__ = 'contract.option.benefit'

    version = fields.Many2One('contract.option.version', 'Version',
        required=True, ondelete='CASCADE', select=True)
    benefit = fields.Many2One('benefit', 'Benefit', required=True,
        ondelete='RESTRICT', readonly=True)
    available_deductible_rules = fields.Function(
        fields.Many2Many('rule_engine', None, None,
            'Available Deductible Rule'),
        'get_available_rule')
    available_indemnification_rules = fields.Function(
        fields.Many2Many('rule_engine', None, None,
            'Available Indemnification Rule'),
        'get_available_rule')
    available_revaluation_rules = fields.Function(
        fields.Many2Many('rule_engine', None, None,
            'Available Revaluation Rule'),
        'get_available_rule')

    @classmethod
    def __setup__(cls):
        super(OptionBenefit, cls).__setup__()
        cls.deductible_rule.domain = [
            ('id', 'in', Eval('available_deductible_rules'))]
        cls.deductible_rule.states['readonly'] = Len(
            'available_deductible_rules') <= 1
        cls.deductible_rule.depends = ['available_deductible_rules']
        cls.indemnification_rule.domain = [
            ('id', 'in', Eval('available_indemnification_rules'))]
        cls.indemnification_rule.states['readonly'] = Len(
            'available_indemnification_rules') <= 1
        cls.indemnification_rule.depends = ['available_indemnification_rules']
        cls.revaluation_rule.domain = [
            ('id', 'in', Eval('available_revaluation_rules'))]
        cls.revaluation_rule.states['readonly'] = Len(
            'available_revaluation_rules') <= 1
        cls.revaluation_rule.depends = ['available_revaluation_rules']

    @fields.depends('benefit', 'available_deductible_rules',
        'available_indemnification_rules', 'available_revaluation_rules')
    def on_change_benefit(self):
        self.available_deductible_rules = \
            self.get_available_rule('available_deductible_rules')
        self.available_indemnification_rules = \
            self.get_available_rule('available_indemnification_rules')
        self.available_revaluation_rules = \
            self.get_available_rule('available_revaluation_rules')

    def get_available_rule(self, name):
        if not self.benefit:
            return []
        benefit_rule = self.benefit.benefit_rules[0]
        force = getattr(benefit_rule, 'force_' + name[10:-1])
        if force:
            rule = getattr(benefit_rule, name[10:-1])
            return [rule.id] if rule else []
        return [x.id for x in getattr(benefit_rule, name[10:])]

    def init_from_benefit(self):
        for fname in ('deductible_rule', 'indemnification_rule',
                'revaluation_rule'):
            available = self.get_available_rule('available_' + fname + 's')
            if len(available) == 0:
                pass
            if len(available) == 1:
                setattr(self, fname, available[0])
                setattr(self, fname + '_extra_data', {})
                setattr(self, fname + '_extra_data',
                    getattr(self, 'on_change_with_' + fname + '_extra_data')())
