# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Product',
    'ProductExtraDetails',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    extra_details_rule = fields.One2Many('offered.product.extra_details_rule',
        'product', 'Extra Details Rule',
        help='Rule used to update extra details',
        size=1, delete_missing=True)

    def calculate_extra_details(self, data):
        if not self.extra_details_rule:
            return {}
        return self.extra_details_rule[0].calculate_rule(data)

    def get_documentation_structure(self):
        structure = super(Product, self).get_documentation_structure()
        structure['rules'].append(
            coog_string.doc_for_rules(self, 'extra_details_rule'))
        return structure


class ProductExtraDetails(model.ConfigurationMixin, model.CoogView,
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data')):
    'Product Extra Details'
    __name__ = 'offered.product.extra_details_rule'

    product = fields.Many2One('offered.product', 'Product', required=True,
            select=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(ProductExtraDetails, cls).__setup__()
        cls.rule.help = 'When contract recalculation is triggered, this ' \
            'rule will be called, and its result (a dict) will be set on ' \
            'the contract extra details'
        cls.rule.domain = [('type_', '=', 'contract_extra_detail')]

    def get_rule_documentation_structure(self):
        return [self.get_rule_rule_engine_documentation_structure()] if \
            self.rule else []
