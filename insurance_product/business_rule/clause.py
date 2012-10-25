#-*- coding:utf-8 -*-
from trytond.model import fields

from trytond.modules.coop_utils import model
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot


__all__ = [
    'ClauseRule',
    ]


class ClauseRule(model.CoopSQL, BusinessRuleRoot):
    'Clause Rule'

    __name__ = 'ins_product.clause_rule'

    specific_clauses = fields.One2Many('ins_product.clause', 'rule',
        'Specific Clauses')
