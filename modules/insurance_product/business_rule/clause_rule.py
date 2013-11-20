#-*- coding:utf-8 -*-
from trytond.modules.coop_utils import model, fields
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot


__all__ = [
    'ClauseRule',
    'ClauseRelation'
]


class ClauseRule(BusinessRuleRoot, model.CoopSQL):
    'Clause Rule'

    __name__ = 'ins_product.clause_rule'

    shared_clauses = fields.Many2Many('ins_product.clause_relation',
        'rule', 'clause', 'Shared Clauses')

    def give_me_all_clauses(self, args):
        return self.shared_clauses, []


class ClauseRelation(model.CoopSQL):
    'Relation between clause and offered'

    __name__ = 'ins_product.clause_relation'

    rule = fields.Many2One('ins_product.clause_rule',
        'Rule', select=1, required=True, ondelete='CASCADE')
    clause = fields.Many2One('ins_product.clause',
        'Clause', select=1, required=True, ondelete='RESTRICT')
