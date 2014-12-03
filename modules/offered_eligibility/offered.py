from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields, model
from trytond.modules.rule_engine import RuleMixin

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    'OptionDescriptionEligibilityRule',
]


class OptionDescription:
    __name__ = 'offered.option.description'

    eligibility_rule = fields.One2Many(
        'offered.option.description.eligibility_rule', 'coverage',
        'Eligibility Rule')

    def check_eligibility(self, exec_context):
        # TODO : Manage multiple eligibility rules
        if not self.eligibility_rule:
            return True
        return self.eligibility_rule[0].calculate(exec_context)


class OptionDescriptionEligibilityRule(RuleMixin, model.CoopSQL,
        model.CoopView):
    'Option Description Eligibility Rule'

    __name__ = 'offered.option.description.eligibility_rule'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, ondelete='CASCADE')
