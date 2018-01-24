# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond import backend

from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'Benefit',
    'BenefitEligibilityRule',
    'BenefitEligibilityDecision',
    'BenefitBenefitEligibility',
    ]


class Benefit:
    __name__ = 'benefit'

    eligibility_rules = fields.One2Many('benefit.eligibility.rule', 'benefit',
        'Benefit Eligibility Rules', delete_missing=True)
    refuse_from_rules = fields.Boolean('Refuse From Eligibility Rules',
        help='If True, a non-eligible service will be refused. Else it will '
        'still require a manual analysis')
    eligibility_decisions = fields.Many2Many(
        'benefit-benefit.eligibility_decision',
        'benefit', 'benefit_eligibility', 'Eligibility Decisions')
    decision_default = fields.Many2One('benefit.eligibility.decision',
        'Default Decision', ondelete='SET NULL', domain=[
            ('id', 'in', Eval('eligibility_decisions'))],
        depends=['eligibility_decisions'], help='The default decision to '
        'be set when delivering a new service')
    accept_decision_default = fields.Many2One('benefit.eligibility.decision',
            'Default Accept Decision', ondelete='SET NULL',
            domain=[
                ('id', 'in', Eval('eligibility_decisions')),
                ('state', '=', 'accepted')
                ],
            depends=['eligibility_decisions'], help='If the service is '
            'automatically accepted, then this decision will be used by '
            'default')
    refuse_decision_default = fields.Many2One('benefit.eligibility.decision',
            'Default Refuse Decision', ondelete='SET NULL',
            domain=[
                ('id', 'in', Eval('eligibility_decisions')),
                ('state', '=', 'refused')],
            states={
                'required': Bool(Eval('refuse_from_rules')),
                'invisible': ~Eval('refuse_from_rules'),
                },
            depends=['eligibility_decisions', 'refuse_from_rules'],
            help='If the service is automatically refused, then this '
            'decision will be used by default')

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

    @fields.depends('refuse_from_rules', 'refuse_decision_default')
    def on_change_refuse_from_rules(self):
        if self.refuse_decision_default and not self.refuse_from_rules:
            self.refuse_decision_default = None

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


class BenefitEligibilityDecision(model.CoogSQL, model.CoogView):
    'Benefit Eligibility Decision'

    __name__ = 'benefit.eligibility.decision'
    _func_key = 'code'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    description = fields.Text('Long Description')
    state = fields.Selection([
            ('study_in_progress', 'Study In Progress'),
            ('accepted', 'Accepted'),
            ('refused', 'Refused'),
            ], 'State')
    state_string = state.translated('state')

    @classmethod
    def __setup__(cls):
        super(BenefitEligibilityDecision, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!')]

    @fields.depends('code', 'name')
    def on_change_with_code(self, name=None):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


class BenefitBenefitEligibility(model.CoogSQL):
    'Benefit Benefit Eligibility Decision Relation'

    __name__ = 'benefit-benefit.eligibility_decision'

    benefit = fields.Many2One('benefit', 'Benefit',
        required=True, ondelete='CASCADE', select=True)
    benefit_eligibility = fields.Many2One('benefit.eligibility.decision',
        'Eligibility Decision', required=True, ondelete='CASCADE', select=True)
