# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'OptionDescription',
    'OptionDescriptionReductionRule',
    ]


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    reduction_rules = fields.One2Many(
        'offered.option.description.reduction_rule', 'coverage',
        'Reduction Rules', help='Rule that defines the contract reduction '
        'behavior', delete_missing=True, size=1)

    def get_documentation_structure(self):
        structure = super(OptionDescription, self).get_documentation_structure()
        structure['rules'].append(
            coog_string.doc_for_rules(self, 'reduction_rules'))
        return structure


class OptionDescriptionReductionRule(model.ConfigurationMixin, model.CoogView,
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

    def get_rule_documentation_structure(self):
        doc = []
        if self.rule:
            doc.append(self.get_rule_rule_engine_documentation_structure())
        if self.eligibility_rule:
            doc.append(self.
                get_eligibility_rule_rule_engine_documentation_structure())
        return doc
