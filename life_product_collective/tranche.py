#-*- coding:utf-8 -*-

from trytond.model import fields
from trytond.pool import PoolMeta


PAYER_KIND = [
    ('employer', 'Employer'),
    ('employee', 'Employee')
]

__all__ = [
    'TrancheCalculator',
    'TrancheCalculatorLine',
]


class TrancheCalculator():
    'Tranche Calculator'

    __name__ = 'tranche.calculator'
    __metaclass__ = PoolMeta

    pricing_data = fields.Many2One('ins_collective.pricing_data',
        'Pricing Data', ondelete='CASCADE')


class TrancheCalculatorLine():
    'Tranche Calculator Line'

    __name__ = 'tranche.calc_line'
    __metaclass__ = PoolMeta

    payer_kind = fields.Selection(PAYER_KIND, 'At The Expense Of')

    @staticmethod
    def default_payer_kind():
        return 'employer'
