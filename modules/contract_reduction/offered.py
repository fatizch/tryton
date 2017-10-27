# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'OptionDescription',
    'OptionDescriptionReductionRule',
    ]


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    reduction_rules = fields.One2Many(
        'offered.option.description.reduction_rule', 'coverage',
        'Reduction Rules', delete_missing=True, size=1)


class OptionDescriptionReductionRule(model.CoogSQL, model.CoogView,
        get_rule_mixin('rule', 'Rule', extra_string='Rule Extra Data'),
        get_rule_mixin('eligibility_rule', 'Eligibility Rule',
            extra_string='Eligibility Rule Extra Data')):
    'Option Description Reduction Rule'
    __name__ = 'offered.option.description.reduction_rule'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, ondelete='CASCADE', select=True)

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionReductionRule, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'reduction')]
        cls.rule.help = 'If set, the rule result will be used to ' \
            'compute the reduction value of the contract'
        cls.eligibility_rule.domain = [('type_', '=',
                'reduction_eligibility')]
        cls.eligibility_rule.help = 'If set, the rule result must ' \
            'be True to allow reduction of the contract'
        cls.eligibility_rule.states = {
            'invisible': ~Eval('rule', False),
            }
        cls.eligibility_rule.depends = ['rule']

    @classmethod
    def _export_light(cls):
        return super(OptionDescriptionReductionRule, cls)._export_light() | {
            'eligibility_rule', 'rule'}
