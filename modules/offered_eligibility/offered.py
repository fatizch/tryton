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
        'Eligibility Rule', delete_missing=True)

    def check_eligibility(self, exec_context):
        # TODO : Manage multiple eligibility rules
        if not self.eligibility_rule:
            return True
        return self.eligibility_rule[0].calculate(exec_context)


class OptionDescriptionEligibilityRule(RuleMixin, model.CoopSQL,
        model.CoopView):
    'Option Description Eligibility Rule'

    __name__ = 'offered.option.description.eligibility_rule'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, ondelete='CASCADE', select=True)

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionEligibilityRule, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'eligibility')]

    @classmethod
    def _export_light(cls):
        return super(OptionDescriptionEligibilityRule, cls)._export_light() | {
            'rule'}

    def get_func_key(self, name):
        return self.coverage.code

    @classmethod
    def search_func_key(cls, name, clause):
        return [('coverage.code',) + tuple(clause[1:])]

    def calculate(self, args):
        rule_result = self.rule.execute(args, self.rule_extra_data)
        result = rule_result.result
        for error_message in rule_result.errors:
            self.append_functional_error(error_message)
            result = False
        return result
