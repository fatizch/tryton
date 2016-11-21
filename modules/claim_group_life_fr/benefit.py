# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'BenefitRule',
    ]


class BenefitRule:
    __metaclass__ = PoolMeta
    __name__ = 'benefit.rule'

    def calculate(self, args):
        res = super(BenefitRule, self).calculate(args)
        for benefit in res:
            if 'part_time_amount' in benefit and benefit['part_time_amount']:
                benefit['kind'] = 'part_time'
        return res
