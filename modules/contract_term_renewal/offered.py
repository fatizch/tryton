from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields, model
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'ProductTermRenewalRule',
]


class Product:
    __name__ = 'offered.product'

    term_renewal_rule = fields.One2Many(
        'offered.product.term_renewal_rule', 'product',
        'Term Renewal Rule', delete_missing=True, size=1)

    def get_contract_end_date(self, exec_context):
        if self.term_renewal_rule:
            return self.term_renewal_rule[0].calculate_rule(exec_context)


class ProductTermRenewalRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoopSQL, model.CoopView):
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
