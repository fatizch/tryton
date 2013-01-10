#-*- coding:utf-8 -*-
from trytond.model import fields

from trytond.modules.coop_utils import model
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE


__all__ = [
    'DeductibleRule',
    ]


class DeductibleRule(BusinessRuleRoot, model.CoopSQL):
    'Deductible Rule'

    __name__ = 'ins_product.deductible_rule'

    value = fields.Char('Value', states={'invisible': STATE_SIMPLE})

    def get_simple_rec_name(self):
        return self.value
