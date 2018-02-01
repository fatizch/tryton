# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond.pyson import Eval, Or, Bool
from trytond import backend
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    'UnderwritingDecision',
    'UnderwritingDecisionUnderwritingDecision',
    'UnderwritingRule',
    'UnderwritingRuleUnderwritingDecision',
    ]

UNDERWRITING_STATUSES = [
    ('accepted', 'Accepted'),
    ('accepted_with_conditions', 'Accepted With Conditions'),
    ('denied', 'Denied'),
    ('postponed', 'PostPoned'),
    ('pending', 'Pending'),
    ]


class UnderwritingDecision(model.CoogSQL, model.CoogView):
    'Underwriting Decision'

    __name__ = 'underwriting.decision'
    _func_key = 'code'

    code = fields.Char('Code', required=True, select=True)
    name = fields.Char('Name', required=True, translate=True)
    status = fields.Selection(UNDERWRITING_STATUSES, 'Status', required=True)
    status_string = status.translated('status')
    level = fields.Selection([
            ('coverage', 'Coverage'), ('contract', 'Contract')], 'Level')
    level_string = level.translated('level')
    with_extra_data = fields.Boolean('With Extra Data')
    decline_option = fields.Boolean('Decline Option',
        states={'invisible': Or(Eval('level') != 'coverage',
                ~Eval('status').in_(['denied', 'postponed']))},
        depends=['status', 'level'])
    contract_decisions = fields.Many2Many(
        'underwriting.decision-underwriting.decision',
        'coverage_decision', 'contract_decision', 'Contract Decisions',
        states={'invisible': Eval('level') != 'coverage'},
        domain=[('level', '=', 'contract')],
        depends=['level'])
    ordered_contract_decisions = fields.One2Many(
        'underwriting.decision-underwriting.decision',
        'coverage_decision', 'Ordered Contract Decisions',
        states={'invisible': Eval('level') != 'coverage'},
        domain=[('contract_decision.level', '=', 'contract')],
        depends=['level'], delete_missing=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)
        cursor = Transaction().connection.cursor()

        # Migration from 1.7 rename with_exclusion into with extra data
        table.column_rename('with_exclusion', 'with_extra_data')

        # Migration from 1.7 merge with_subscriber_validation and status
        col_validation_exist = table.column_exist('with_subscriber_validation')

        super(UnderwritingDecision, cls).__register__(module_name)
        if col_validation_exist:
            cursor.execute("UPDATE underwriting_decision "
                "SET status = 'accepted_with_conditions' "
                "WHERE with_subscriber_validation = 'TRUE' ")
            table.drop_column('with_subscriber_validation')

    @classmethod
    def __setup__(cls):
        super(UnderwritingDecision, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]

    def get_rec_name(self, name):
        return self.name

    @staticmethod
    def default_level():
        return 'contract'

    @fields.depends('name', 'code', 'level')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify('%s_%s' % (
                self.level_string if self.level else '',
                self.name))


class UnderwritingDecisionUnderwritingDecision(model.CoogSQL, model.CoogView):
    'Underwriting Decision to Underwriting Decision Relation'

    __name__ = 'underwriting.decision-underwriting.decision'

    order = fields.Integer('Order')
    coverage_decision = fields.Many2One('underwriting.decision',
        'Coverage Decision', ondelete='CASCADE', required=True, select=True)
    contract_decision = fields.Many2One('underwriting.decision',
        'Contract Decision', ondelete='RESTRICT', required=True, select=True)


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    @classmethod
    def kind_list_for_extra_data_domain(cls):
        kinds = super(Product, cls).kind_list_for_extra_data_domain()
        kinds.append('contract_underwriting')
        return kinds


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    underwriting_rules = fields.One2Many(
        'underwriting.rule', 'coverage',
        'Underwriting Rules', delete_missing=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        existing_with_underwriting = table.column_exist('with_underwriting')
        super(OptionDescription, cls).__register__(module_name)
        if existing_with_underwriting:
            # Migration from 1.7 Drop with_underwriting
            cursor.execute("SELECT id from rule_engine "
                "WHERE short_name='underwriting_basic_rule'")
            rule_id = cursor.fetchone()
            if not rule_id:
                # First pass xml not loaded yet
                return
            rule_id = rule_id[0]
            cursor.execute("SELECT id FROM offered_option_description "
                " WHERE with_underwriting = 'always_underwrite'")

            for row in cursor.fetchall():
                cursor.execute('INSERT INTO underwriting_rule '
                    '(create_uid, create_date, coverage, rule, '
                        'rule_extra_data)'
                    'VALUES (%s, now(), %s, %s, %s);',
                    (0, row[0], rule_id, '{"always_underwrite": true}'))
            table.drop_column('with_underwriting')

    @classmethod
    def kind_list_for_extra_data_domain(cls):
        kinds = super(OptionDescription, cls).kind_list_for_extra_data_domain()
        kinds.append('option_underwriting')
        return kinds

    def get_underwriting_rule(self):
        # TODO deal with multiple underwriting rules?
        return self.underwriting_rules[-1] if self.underwriting_rules else None


class UnderwritingRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Underwriting Rule'

    __name__ = 'underwriting.rule'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, ondelete='CASCADE', select=True)
    decisions = fields.Many2Many('underwriting.rule-underwriting.decision',
        'rule', 'decision', 'Decisions', domain=[('level', '=', 'coverage')])
    accepted_decision = fields.Many2One('underwriting.decision',
        'Default Accepted Decision', help='If set and the rule returns true, '
        'this would be the accepted decision for the coverage',
        domain=[('status', '=', 'accepted'), ('id', 'in', Eval('decisions'))],
        states={'required': Bool(Eval('decisions'))},
        depends=['decisions'], ondelete='RESTRICT',)

    @classmethod
    def __setup__(cls):
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'underwriting')]
        cls.rule.help = 'Returns True if accepted without condition, '
        'False if manual underwriting is necessary'
        super(UnderwritingRule, cls).__setup__()

    @classmethod
    def _export_light(cls):
        return super(UnderwritingRule, cls)._export_light(
            ) | {'rule'}

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
        return rule_result.result


class UnderwritingRuleUnderwritingDecision(model.CoogSQL):
    'Underwriting Rule to Underwriting Decision Relation'

    __name__ = 'underwriting.rule-underwriting.decision'

    rule = fields.Many2One('underwriting.rule', 'Rule', ondelete='CASCADE')
    decision = fields.Many2One('underwriting.decision', 'Rule',
        ondelete='RESTRICT')
