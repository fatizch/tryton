#-*- coding:utf-8 -*-
from trytond.modules.cog_utils import model, fields
from trytond.modules.offered_insurance.business_rule.business_rule import \
    BusinessRuleRoot


__all__ = [
    'ClauseRule',
    'RuleClauseRelation'
    ]


class ClauseRule(BusinessRuleRoot, model.CoopSQL):
    'Clause Rule'

    __name__ = 'clause.rule'

    clauses = fields.Many2Many('clause.rule-clause', 'rule', 'clause',
        'Clauses')

    def give_me_all_clauses(self, args):
        return self.clauses, []


class RuleClauseRelation(model.CoopSQL):
    'Rule to Clause Relation'

    __name__ = 'clause.rule-clause'

    rule = fields.Many2One('clause.rule', 'Rule', select=1, required=True,
        ondelete='CASCADE')
    clause = fields.Many2One('clause', 'Clause', select=1, required=True,
        ondelete='RESTRICT')
