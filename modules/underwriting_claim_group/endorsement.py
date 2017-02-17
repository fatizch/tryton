# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'ManageOptionBenefits',
    'ManageOptionBenefitsDisplayer',
    ]


class ManageOptionBenefits:
    __metaclass__ = PoolMeta
    __name__ = 'contract.manage_option_benefits'

    @classmethod
    def get_displayer_fields(cls):
        res = super(ManageOptionBenefits, cls).get_displayer_fields()
        res['contract.option.benefit'].append('available_underwriting_rules')
        return res

    @classmethod
    def get_version_fields(cls):
        res = super(ManageOptionBenefits, cls).get_version_fields()
        res['contract.option.benefit'] += ('available_underwriting_rules',)
        return res


class ManageOptionBenefitsDisplayer:
    __metaclass__ = PoolMeta
    __name__ = 'contract.manage_option_benefits.option'

    @classmethod
    def get_option_benefit_fields(cls):
        return super(ManageOptionBenefitsDisplayer,
            cls).get_option_benefit_fields() + ('underwriting_rule',
            'underwriting_rule_extra_data')
