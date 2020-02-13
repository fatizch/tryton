# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond import backend
from trytond.pool import PoolMeta
from trytond.pyson import If, Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'OptionDescription',
    'CoverageAmountRule',
    ]


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    coverage_amount_rules = fields.One2Many('offered.coverage_amount.rule',
        'coverage', 'Coverage Amount Rules',
        help='Define how a coverage amount will be required and filled for the'
        ' option', delete_missing=True)

    def get_coverage_amount_rule_result(self, args):
        if not self.coverage_amount_rules:
            return
        return self.coverage_amount_rules[0].calculate_rule(args)

    def get_documentation_structure(self):
        structure = super(OptionDescription, self).get_documentation_structure()
        structure['rules'].append(
            coog_string.doc_for_rules(self, 'coverage_amount_rules'))
        return structure


class CoverageAmountRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.ConfigurationMixin, model.CoogView):
    'Coverage Amount Rule'

    __name__ = 'offered.coverage_amount.rule'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True, select=True)
    amount_mode = fields.Selection([
            ('calculated_amount', 'Calculated Amount'),
            ('free_input', 'Free Input'),
            ('selection', 'Selection'),
            ], 'Amount Mode', help='If set to free input, the rule must return'
        'a boolean to validate the entry, otherwise the rule must return a '
        'list of possible values for selection or the amount if calculated')
    label = fields.Char('Label', help='This label will be used for the contract'
        ' option display if the amount is calculated')

    @classmethod
    def __setup__(cls):
        super(CoverageAmountRule, cls).__setup__()
        cls.rule.required = True
        cls.rule.domain.append(If(
                Eval('amount_mode', '') == 'free_input',
                [('type_', '=', 'coverage_amount_validation')],
                If(
                    Eval('amount_mode', '') == 'selection',
                    [('type_', '=', 'coverage_amount_selection')],
                    [('type_', '=', 'coverage_amount_calculation')]),
                ))
        cls.rule.depends.append('amount_mode')
        cls.rule.help = 'The rule must return the list of possible coverage '\
            'amounts'

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
        # Migration from 2.6
        if rule.column_exist('free_input'):
            cursor = Transaction().connection.cursor()
            rules = cls.__table__()
            cursor.execute(*rules.update(
                    where=rules.free_input == Literal(True),
                    columns=[rules.amount_mode],
                    values=['free_input']))
            rule.drop_column('free_input')

    @classmethod
    def default_amount_mode(cls):
        return 'selection'

    def get_rule_documentation_structure(self):
        return [
            coog_string.doc_for_field(self, 'amount_mode'),
            self.get_rule_rule_engine_documentation_structure()
            ]
