#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.coop_utils import model
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot
from trytond.modules.insurance_product.product import DEF_CUR_DIG


__all__ = [
    'ReserveRule',
    ]


class ReserveRule(model.CoopSQL, BusinessRuleRoot):
    'Reserve Rule'

    __name__ = 'ins_product.reserve_rule'

    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        )
