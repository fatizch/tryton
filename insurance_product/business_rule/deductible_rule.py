#-*- coding:utf-8 -*-
from trytond.model import fields

from trytond.modules.coop_utils import model
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot


__all__ = [
    'DeductibleRule',
    ]


class DeductibleRule(model.CoopSQL, BusinessRuleRoot):
    'Deductible Rule'

    __name__ = 'ins_product.deductible_rule'

    value = fields.Char('Value')
