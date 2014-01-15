from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product:
    __name__ = 'offered.product'

    use_rates = fields.Function(
        fields.Boolean('Use Rates', states={'invisible': True}),
        'get_use_rates')

    def get_collective_rating_frequency(self):
        return 'quarterly'

    def get_use_rates(self, name):
        return self.is_group and any([x.rating_rules for x in self.coverages])


class OptionDescription:
    __name__ = 'offered.option.description'

    is_rating_by_fare_class = fields.Function(
        fields.Boolean('Rating by Fare Class', states={'invisible': True}),
        'get_rating_by_fare_class')
    use_rates = fields.Function(
        fields.Boolean('Use Rates', states={'invisible': True}),
        'get_use_rates')
    rating_rules = fields.One2Many('billing.premium.rate.rule', 'offered',
        'Rating Rules', states={'invisible': ~Eval('is_group')})

    def get_rating_by_fare_class(self, name):
        if utils.is_none(self, 'rating_rules'):
            return False
        for rating_rule in self.rating_rules:
            if rating_rule.rating_kind == 'fare_class':
                return True
        return False

    def get_use_rates(self, name):
        return self.is_group and len(self.rating_rules) > 0
