# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Len, Bool

from trytond.modules.coog_core import fields, model
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.claim_indemnification.benefit import ANNUITY_FREQUENCIES


__all__ = [
    'Option',
    'OptionVersion',
    'OptionBenefit',
    ]


class Option:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    @classmethod
    def view_attributes(cls):
        return super(Option, cls).view_attributes() + [
            ("/form/notebook/page[@id='rules']", 'states', {
                    'invisible': ~Eval('is_group', False)}),
            ("/form/notebook/page/group[@id='claim_rules']", 'states', {
                    'invisible': ~Eval('is_group', False)})
            ]

    @classmethod
    def new_option_from_coverage(cls, coverage, *args, **kwargs):
        new_option = super(Option, cls).new_option_from_coverage(coverage,
            *args, **kwargs)
        if not coverage.is_group:
            return new_option
        new_option.versions[0].init_from_coverage(coverage)
        return new_option


class OptionVersion:
    __metaclass__ = PoolMeta
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
        model.CoogSQL, model.CoogView):
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
    annuity_frequency = fields.Selection(ANNUITY_FREQUENCIES,
        'Annuity Frequency', states={
            'readonly': Bool(Eval('annuity_frequency_forced')),
            'invisible': ~Eval('annuity_frequency_required'),
            'required': Bool(Eval('annuity_frequency_required'))},
        depends=['annuity_frequency_forced', 'annuity_frequency_required'])
    annuity_frequency_forced = fields.Function(
        fields.Boolean('Annuity frequency Forced'),
        'get_annuity_frequency_forced')
    annuity_frequency_required = fields.Function(
        fields.Boolean('Annuity Frequency Required'),
        'get_annuity_frequency_required')
    available_revaluation_rules = fields.Function(
        fields.Many2Many('rule_engine', None, None,
            'Available Revaluation Rule'),
        'get_available_rule')

    @classmethod
    def __setup__(cls):
        super(OptionBenefit, cls).__setup__()
        cls.deductible_rule.domain = [
            ('id', 'in', Eval('available_deductible_rules'))]
        cls.deductible_rule.states['readonly'] = Len(Eval(
                'available_deductible_rules')) == 1
        cls.deductible_rule.states['invisible'] = Len(Eval(
                'available_deductible_rules')) == 0
        cls.deductible_rule.depends = ['available_deductible_rules']
        cls.indemnification_rule.domain = [
            ('id', 'in', Eval('available_indemnification_rules'))]
        cls.indemnification_rule.states['readonly'] = Len(Eval(
                'available_indemnification_rules')) == 1
        cls.indemnification_rule.states['invisible'] = Len(Eval(
                'available_indemnification_rules')) == 0
        cls.indemnification_rule.depends = ['available_indemnification_rules']
        cls.revaluation_rule.domain = [
            ('id', 'in', Eval('available_revaluation_rules'))]
        cls.revaluation_rule.states['readonly'] = Len(Eval(
                'available_revaluation_rules')) == 1
        cls.revaluation_rule.states['invisible'] = Len(Eval(
                'available_revaluation_rules')) == 0
        cls.revaluation_rule.depends = ['available_revaluation_rules']

    @fields.depends('benefit', 'available_deductible_rules',
        'available_indemnification_rules', 'available_revaluation_rules',
        'annuity_frequency', 'annuity_frequency_forced')
    def on_change_benefit(self):
        self.available_deductible_rules = \
            self.get_available_rule('available_deductible_rules')
        self.available_indemnification_rules = \
            self.get_available_rule('available_indemnification_rules')
        self.available_revaluation_rules = \
            self.get_available_rule('available_revaluation_rules')
        if not self.benefit:
            self.annuity_frequency_forced = False
        else:
            self.annuity_frequency_forced = \
                self.benefit.benefit_rules[0].force_annuity_frequency
        if self.annuity_frequency_forced:
            self.annuity_frequency = \
                self.benefit.benefit_rules[0].annuity_frequency

    def get_annuity_frequency_forced(self, name):
        if not self.benefit:
            return False
        return self.benefit.benefit_rules[0].force_annuity_frequency

    def get_annuity_frequency_required(self, name):
        if not self.benefit:
            return False
        return self.benefit.indemnification_kind == 'annuity'

    def get_available_rule(self, name):
        if not self.benefit:
            return []
        benefit_rule = self.benefit.benefit_rules[0]
        force = getattr(benefit_rule, 'force_' + name[10:-1], -1)
        if force == -1:
            # In some cases, the configuration may be directly on the benefit
            benefit_rule = self.benefit
        if force:
            rule = getattr(benefit_rule, name[10:-1])
            return [rule.id] if rule else []
        return [x.id for x in getattr(benefit_rule, name[10:])]

    def init_from_benefit(self):
        for fname in self.__class__.rule_fields():
            available = self.get_available_rule('available_' + fname + 's')
            if len(available) == 0:
                continue
            if len(available) == 1:
                setattr(self, fname, available[0])
                setattr(self, fname + '_extra_data', {})
                setattr(self, fname + '_extra_data',
                    getattr(self, 'on_change_with_' + fname + '_extra_data')())
        benefit_rule = self.benefit.benefit_rules[0]
        if benefit_rule.force_annuity_frequency:
            self.annuity_frequency = benefit_rule.annuity_frequency

    @classmethod
    def rule_fields(cls):
        return ['deductible_rule', 'indemnification_rule', 'revaluation_rule']
