# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    is_cash_value = fields.Function(
        fields.Boolean('Is Cash Value', states={'invisible': True}),
        'getter_is_cash_value')

    def getter_is_cash_value(self, name):
        for coverage in self.coverages:
            if coverage.is_cash_value:
                return True
        return False


class OptionDescription(get_rule_mixin('buyback_rule', 'Buyback Rule',
            extra_string='Buyback Rule Extra Data')):
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    is_cash_value = fields.Function(
        fields.Boolean('Is Cash Value', states={'invisible': True}),
        'getter_is_cash_value')

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('cash_value', 'Cash Value'))

    @fields.depends('family')
    def on_change_family(self):
        if self.family != 'cash_value':
            self.is_cash_value = False
        else:
            self.is_cash_value = True

    def getter_is_cash_value(self, name):
        return self.family == 'cash_value'
