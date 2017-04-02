# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool
from trytond.modules.coog_core import fields

__all__ = [
    'OptionBenefit',
    ]


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


class OptionBenefit:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.benefit'

    salary_mode = fields.Selection(SALARY_MODES, 'Salary Mode')
    net_salary_mode = fields.Boolean('Calculate Net Salary')
    net_calculation_rule = fields.Many2One('claim.net_calculation_rule',
        'Net Calculation Rule', ondelete='RESTRICT', states={
            'required': Bool(Eval('net_salary_mode')),
            'invisible': ~Bool(Eval('net_salary_mode')),
            }, depends=['net_salary_mode'])

    @staticmethod
    def default_net_salary_mode():
        return False