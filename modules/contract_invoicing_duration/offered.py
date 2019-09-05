# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'ProductBillingRule',
    ]


class ProductBillingRule(get_rule_mixin('invoicing_end_rule',
        'Invoicing end rule', extra_string='Rule Extra Data'),
            metaclass=PoolMeta):
    __name__ = 'offered.product.billing_rule'

    @classmethod
    def __setup__(cls):
        super(ProductBillingRule, cls).__setup__()
        cls.invoicing_end_rule.domain = [('type_', '=', 'invoicing_duration')]
