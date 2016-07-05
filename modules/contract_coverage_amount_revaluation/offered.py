# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    'CoverageAmountRule',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    has_revaluated_coverage_amount = fields.Function(
        fields.Boolean('Has Revaluated Coverage Amount'),
        'get_has_revaluated_coverage_amount')

    def get_has_revaluated_coverage_amount(self, name):
        return (self.coverage_amount_rules and
            self.coverage_amount_rules[0].revaluation_rule)

    def calculate_revaluated_coverage_amount(self, args):
        if not self.coverage_amount_rules:
            return
        rule = self.coverage_amount_rules[0]
        return rule.calculate_revaluated_coverage_amount(args)


class CoverageAmountRule:
    __name__ = 'offered.coverage_amount.rule'

    revaluation_rule = fields.Many2One('rule_engine', 'Revaluation Rule',
        ondelete='RESTRICT',
        domain=[('type_', '=', 'coverage_amount_revaluation')],
        help="Must return the reevaluated amount that will be stored")
    revaluation_rule_extra_data = fields.Dict('rule_engine.rule_parameter',
        'Revaluation Rule Extra Data', states={
            'invisible': ~Eval('revaluation_rule_extra_data', False)})
    revaluation_rule_extra_data_string = \
        revaluation_rule_extra_data.translated('revaluation_rule_extra_data')

    def calculate_revaluated_coverage_amount(self, args):
        if not self.revaluation_rule:
            return
        return self.revaluation_rule.execute(args,
            self.revaluation_rule_extra_data).result
