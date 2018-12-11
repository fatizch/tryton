# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool
from trytond.modules.coog_core import fields

__all__ = [
    'OptionBenefit',
    ]

_CONTRACT_STATUS_STATES = {
    'readonly': Bool(Eval('contract_status')) & (
        Eval('contract_status') != 'quote'),
    }
_CONTRACT_STATUS_DEPENDS = ['contract_status']

SALARY_MODES = [
    ('', ''),
    ('last_12_months', 'Last 12 months'),
    ('last_3_months', 'Last 3 months'),
    ('last_month', 'Last month'),
    ('last_12_months_last_year', 'Last 12 months on last year'),
    ('last_3_months_last_year', 'Last 3 months on last year'),
    ('last_month_last_year', 'Last month on last year'),
    ('last_year', 'Last Year'),
    ('last_4_quarters', 'Last 4 quarters'),
    ]


class OptionBenefit(metaclass=PoolMeta):
    __name__ = 'contract.option.benefit'

    salary_mode = fields.Selection(SALARY_MODES, 'Salary Mode',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    net_salary_mode = fields.Boolean('Calculate Net Salary',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    net_calculation_rule = fields.Many2One('claim.net_calculation_rule',
        'Net Calculation Rule', ondelete='RESTRICT', states={
            'readonly': Eval('contract_status') != 'quote',
            'required': Bool(Eval('net_salary_mode')),
            'invisible': ~Bool(Eval('net_salary_mode')),
            }, depends=['net_salary_mode', 'contract_status'])
    revaluation_on_basic_salary = fields.Boolean('Revaluation on basic salary',
        states={'invisible': Bool(Eval('revaluation_on_basic_salary_forced')),
            'readonly': Eval('contract_status') != 'quote'},
        depends=['revaluation_on_basic_salary_forced', 'contract_status'])
    revaluation_on_basic_salary_forced = fields.Function(
        fields.Boolean('Revaluation on basic salary forced'),
        'get_revaluation_forced')

    @staticmethod
    def default_net_salary_mode():
        return False

    @staticmethod
    def default_revaluation_on_basic_salary():
        return False

    def get_revaluation_forced(self, name):
        if not self.benefit:
            return False
        return self.benefit.benefit_rules[0].force_revaluation_on_basic_salary
