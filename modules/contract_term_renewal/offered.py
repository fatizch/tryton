# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Product',
    'ProductTermRenewalRule',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    term_renewal_rule = fields.One2Many(
        'offered.product.term_renewal_rule', 'product',
        'Term Renewal Rule', delete_missing=True, size=1)

    def get_contract_end_date(self, exec_context):
        if self.term_renewal_rule and not \
                exec_context['contract'].finally_renewed() and \
                exec_context['contract'].status != 'void':
            return self.term_renewal_rule[0].calculate_rule(exec_context)
        elif self.term_renewal_rule:
            return exec_context['contract'].final_end_date


class ProductTermRenewalRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Product Term Renewal Rule'

    __name__ = 'offered.product.term_renewal_rule'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    product = fields.Many2One('offered.product', 'Product', required=True,
        ondelete='CASCADE', select=True)
    allow_renewal = fields.Boolean('Allow Renewal')

    @classmethod
    def __setup__(cls):
        super(ProductTermRenewalRule, cls).__setup__()
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'renewal')]

    @classmethod
    def _export_light(cls):
        return super(ProductTermRenewalRule, cls)._export_light() | {
            'rule'}

    def get_func_key(self, name):
        return self.product.code

    @classmethod
    def search_func_key(cls, name, clause):
        return [('product.code',) + tuple(clause[1:])]
