# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool, Or

from trytond.modules.coog_core import fields


__all__ = [
    'OptionBenefitSalaryFr',
    'ManageOptionBenefitsDisplayer',
    ]


class OptionBenefitSalaryFr(metaclass=PoolMeta):
    __name__ = 'contract.option.benefit'

    revaluation_on_basic_salary_if_period = fields.Boolean(
        'Revaluation On Basic Salary If Deduction Period',
        states={
            'invisible': Or(Bool(Eval('revaluation_on_basic_salary')),
                Bool(Eval('revaluation_on_basic_salary_forced'))),
            'readonly': Bool(Eval('contract_status')) &
            (Eval('contract_status') != 'quote')
            }, depends=['revaluation_on_basic_salary_forced',
                'revaluation_on_basic_salary', 'contract_status'])
    revaluation_on_basic_salary_deduction_periods = fields.Many2One(
        'benefit.salary_revaluation.deduction_period.rule',
        'Revaluation On Basic Salary Deduction Period Rule',
        states={
            'invisible': ~Bool(Eval('revaluation_on_basic_salary_if_period')),
            'readonly': Bool(Eval('contract_status')) &
            (Eval('contract_status') != 'quote')
            },
        domain=[('id', 'in', Eval('possible_revaluation_deduction_periods'))],
        depends=['revaluation_on_basic_salary_if_period', 'contract_status',
            'possible_revaluation_deduction_periods'],
        help='If deduction rule defined, revaluation will be done on '
        'basic salary when computing indemnification periods with any of the '
        'following defined deduction period.', ondelete='RESTRICT',
        )
    possible_revaluation_deduction_periods = fields.Function(
        fields.Many2Many('benefit.salary_revaluation.deduction_period.rule',
            None, None, 'Possible Revaluation Deduction Periods'),
        getter='on_change_with_possible_revaluation_deduction_periods')

    @fields.depends('revaluation_on_basic_salary')
    def on_change_revaluation_on_basic_salary(self, name=None):
        if self.revaluation_on_basic_salary:
            self.revaluation_on_basic_salary_if_period = False
            self.revaluation_on_basic_salary_deduction_periods = None

    @fields.depends('benefit')
    def on_change_with_possible_revaluation_deduction_periods(self, name=None):
        if not self.benefit or not self.benefit.benefit_rules:
            None
        return [x.id for x in self.benefit.benefit_rules[0
            ].revaluation_on_basic_salary_period_rule]


class ManageOptionBenefitsDisplayer(metaclass=PoolMeta):
    __name__ = 'contract.manage_option_benefits.option'

    @classmethod
    def get_option_benefit_fields(cls):
        return super(
            ManageOptionBenefitsDisplayer, cls).get_option_benefit_fields() + (
                'revaluation_on_basic_salary_if_period',
                'revaluation_on_basic_salary_deduction_periods')
