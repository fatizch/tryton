# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'BenefitRule',
    'ManageOptionBenefitsDisplayer',
    ]


class BenefitRule:
    __name__ = 'benefit.rule'

    def option_benefit_at_date(self, option, date):
        if not option:
            return ''
        version = option.get_version_at_date(date)
        option_benefit = version.get_benefit(self.benefit)
        return option_benefit


class ManageOptionBenefitsDisplayer:
    __metaclass__ = PoolMeta
    __name__ = 'contract.manage_option_benefits.option'

    @classmethod
    def get_option_benefit_fields(cls):
        return super(
            ManageOptionBenefitsDisplayer, cls).get_option_benefit_fields() + (
                'salary_mode', 'net_salary_mode', 'net_calculuation_rule')
