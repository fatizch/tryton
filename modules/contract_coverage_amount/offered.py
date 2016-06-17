from trytond import backend
from trytond.pool import PoolMeta
from trytond.pyson import If, Bool, Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    'CoverageAmountRule',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    coverage_amount_rules = fields.One2Many('offered.coverage_amount.rule',
        'coverage', 'Coverage Amount Rules', delete_missing=True)

    def get_coverage_amount_rule_result(self, args):
        if not self.coverage_amount_rules:
            return
        return self.coverage_amount_rules[0].calculate_rule(args)


class CoverageAmountRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoopSQL, model.CoopView):
    'Coverage Amount Rule'

    __name__ = 'offered.coverage_amount.rule'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True, select=True)
    free_input = fields.Boolean('Free Input', help='If True, the rule '
        'must return a boolean to validate the entry, otherwise the rule must '
        'return a list of possible values')

    @classmethod
    def __setup__(cls):
        super(CoverageAmountRule, cls).__setup__()
        cls.rule.required = True
        cls.rule.domain.append(If(
                Bool(Eval('free_input', False)),
                [('type_', '=', 'coverage_amount_validation')],
                [('type_', '=', 'coverage_amount_selection')],
                ))
        cls.rule.depends.append('free_input')

    @classmethod
    def __register__(cls, module_name):
        super(CoverageAmountRule, cls).__register__(module_name)
        # Migration from 1.4: Rewrite whole coverage amount rule
        TableHandler = backend.get('TableHandler')
        rule = TableHandler(cls)
        for var_name in ['kind', 'amounts', 'amount_start', 'amount_end',
                'amount_step', 'other_coverage', 'template',
                'template_behaviour', 'start_date', 'end_date', 'offered',
                'config_kind']:
            if rule.column_exist(var_name):
                rule.drop_column(var_name)
