# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, model
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'Benefit',
    'BenefitEligibilityRule',
    ]


class Benefit:
    __name__ = 'benefit'

    eligibility_rules = fields.One2Many('benefit.eligibility.rule', 'benefit',
        'Benefit Eligibility Rules', delete_missing=True)

    def check_eligibility(self, exec_context):
        if self.eligibility_rules:
            return self.eligibility_rules[0].check_eligibility(exec_context)
        return True


class BenefitEligibilityRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoopSQL, model.CoopView):
    'Benefit Eligibility Rule'

    __name__ = 'benefit.eligibility.rule'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE',
        required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(BenefitEligibilityRule, cls).__setup__()
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'benefit')]

    def check_eligibility(self, exec_context):
        res = self.calculate_rule(exec_context, return_full=True)
        return res.result, '\n'.join(res.print_info())
