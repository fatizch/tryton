# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond import backend

from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields, model
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
    refuse_from_rules = fields.Boolean('Refuse From Eligibility Rules',
        help='If True, a non-eligible service will be refused. Else it will '
        'still require a manual analysis')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.12: add refuse_from_rules field and set it to False
        # to keep the existing behaviour
        TableHandler = backend.get('TableHandler')
        table_handler = TableHandler(cls)
        cursor = Transaction().connection.cursor()
        do_migrate = not table_handler.column_exist('refuse_from_rules')
        super(Benefit, cls).__register__(module_name)
        if not do_migrate:
            return
        table = cls.__table__()
        cursor.execute(*table.update(columns=[table.refuse_from_rules],
                values=[Literal(False)]
                ))

    def check_eligibility(self, exec_context):
        if self.eligibility_rules:
            return self.eligibility_rules[0].check_eligibility(exec_context)
        return True, ''

    @classmethod
    def default_refuse_from_rules(cls):
        return True


class BenefitEligibilityRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
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
