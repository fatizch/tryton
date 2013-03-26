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

    specific_clauses = fields.One2Many('ins_product.clause', 'rule',
        'Specific Clauses')
    shared_clauses = fields.Many2Many('ins_product.clause_relation',
        'rule', 'clause', 'Shared Clauses')


class ClauseRelation(model.CoopSQL):
    'Relation between clause and offered'

    __name__ = 'ins_product.clause_relation'

    rule = fields.Many2One('ins_product.clause_rule',
        'Rule', select=1, required=True, ondelete='CASCADE')
    clause = fields.Many2One('ins_product.clause',
        'Clause', select=1, required=True, ondelete='RESTRICT')
