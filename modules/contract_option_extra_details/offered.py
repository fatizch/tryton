# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Coverage',
    'CoverageExtraDetails',
    ]


class Coverage:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    extra_details_rule = fields.One2Many(
        'offered.option.description.extra_detail_rule', 'coverage',
        'Extra Details Rule', size=1, delete_missing=True)

    def calculate_extra_details(self, data):
        if not self.extra_details_rule:
            return {}
        return self.extra_details_rule[0].calculate_rule(data)


class CoverageExtraDetails(model.CoogSQL, model.CoogView,
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data')):
    'Coverage Extra Details'
    __name__ = 'offered.option.description.extra_detail_rule'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, select=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(CoverageExtraDetails, cls).__setup__()
        cls.rule.help = 'When contract recalculation is triggered, this ' \
            'rule will be called, and its result (a dict) will be set on ' \
            'the options extra details'
        cls.rule.domain = [('type_', '=', 'option_extra_detail')]
