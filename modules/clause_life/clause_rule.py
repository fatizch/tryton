from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'ClauseRule',
    ]


class ClauseRule:
    __name__ = 'clause.rule'

    has_beneficiary_clauses = fields.Function(
        fields.Boolean('With Beneficiary Clauses'),
        'on_change_with_has_beneficiary_clauses')
    has_default_beneficiary_clause = fields.Boolean(
        'With Default Beneficiary Clause',
        states={'invisible': ~Eval('has_beneficiary_clauses', False)},
        depends=['has_beneficiary_clauses'])
    default_beneficiary_clause = fields.Many2One('clause',
        'Default Beneficiary Clause', domain=[
            ('kind', '=', 'beneficiary'),
            ('id', 'in', Eval('clauses'))],
        states={
            'invisible': ~Eval('has_beneficiary_clauses', False),
            'readonly': ~Eval('has_default_beneficiary_clause', False),
            'required': Eval('has_default_beneficiary_clause', False)},
        depends=['has_default_beneficiary_clause', 'has_beneficiary_clauses'])

    def give_me_all_clauses(self, args):
        # Only add one benficiary clause by default
        beneficiary_clause_found = False
        result = []
        for clause in self.clauses:
            if clause.kind != 'beneficiary':
                result.append(clause)
            elif beneficiary_clause_found:
                continue
            else:
                result.append(clause)
                beneficiary_clause_found = True
        return result, []

    @fields.depends('has_default_beneficiary_clause',
        'has_beneficiary_clauses')
    def on_change_with_default_beneficiary_clause(self):
        return None

    @fields.depends('clauses')
    def on_change_with_has_beneficiary_clauses(self, name=None):
        for clause in self.clauses:
            if clause.kind == 'beneficiary':
                return True
        return False
