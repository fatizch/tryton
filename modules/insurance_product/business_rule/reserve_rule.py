#-*- coding:utf-8 -*-
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_ADVANCED
from trytond.modules.insurance_product.product import DEF_CUR_DIG


__all__ = [
    'ReserveRule',
]


class ReserveRule(BusinessRuleRoot, model.CoopSQL):
    'Reserve Rule'

    __name__ = 'ins_product.reserve_rule'

    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={'invisible': STATE_ADVANCED}
        )
