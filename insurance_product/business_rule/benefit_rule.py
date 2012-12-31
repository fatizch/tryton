#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, coop_string
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot
from trytond.modules.insurance_product.product import DEF_CUR_DIG


__all__ = [
    'BenefitRule',
    ]


class BenefitRule(BusinessRuleRoot, model.CoopSQL):
    'Benefit Rule'

    __name__ = 'ins_product.benefit_rule'

    kind = fields.Selection(
        [
            ('amount', 'Amount'),
            ('cov_amount', 'Coverage Amount')
        ],
        'Kind')

    amount = fields.Numeric(
        'Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={'invisible': Eval('kind') != 'amount'},
        )

    coef_coverage_amount = fields.Numeric(
        'Multiplier',
        states={'invisible': Eval('kind') != 'cov_amount'},
        help='Add a multiplier to apply to the coverage amount',
        )

    @staticmethod
    def default_coef_coverage_amount():
        return 1

    @staticmethod
    def default_kind():
        return 'cov_amount'

    def get_simple_rec_name(self):
        if self.kind == 'amount':
            return self.amount
        else:
            res = coop_string.translate_value(self, 'kind')
            if self.coef_coverage_amount != 1:
                res = '%s * %s' % (self.coef_coverage_amount, res)
            return res
