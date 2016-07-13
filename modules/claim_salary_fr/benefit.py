# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'BenefitRule',
    ]


class BenefitRule:
    __name__ = 'benefit.rule'

    def option_benefit_at_date(self, option, date):
        if not option:
            return ''
        version = option.get_version_at_date(date)
        option_benefit = version.get_benefit(self.benefit)
        return option_benefit
