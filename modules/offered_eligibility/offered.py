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

    eligibility_rules = fields.One2Many(
        'offered.option.description.eligibility_rule', 'coverage',
        'Eligibility Rules', delete_missing=True)

    def check_eligibility(self, exec_context):
        if not self.eligibility_rules:
            return True
        return all([x.calculate(exec_context) for x in self.eligibility_rules])


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
        return self.coverage.code + '|' + self.rule.short_name

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                coverage_code, short_name = clause[2].split('|')
                return [('coverage.code', clause[1], coverage_code),
                    ('rule.short_name', clause[1], short_name)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('coverage.code',) + tuple(clause[1:])],
                [('rule.short_name',) + tuple(clause[1:])],
                ]

    def calculate(self, args):
        rule_result = self.rule.execute(args, self.rule_extra_data)
        result = rule_result.result
        for error_message in rule_result.errors:
            self.append_functional_error(error_message)
            result = False
        return result
