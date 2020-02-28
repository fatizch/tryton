# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

from trytond.modules.coog_core import model, fields
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Product',
    'PremiumEndingRule',
    'OptionDescriptionPremiumRule',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    premium_ending_rule = fields.One2Many(
        'offered.product.premium_validity_rule', 'product',
        'Premiums Ending Rule', help='Rule that returns a date which defines '
        'when the premiums will end', delete_missing=True)


class PremiumEndingRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.ConfigurationMixin, model.CoogView):
    'Premium Ending Rule'

    __name__ = 'offered.product.premium_validity_rule'

    product = fields.Many2One('offered.product', 'Product', required=True,
        ondelete='CASCADE', select=True)

    @classmethod
    def __setup__(cls):
        super(PremiumEndingRule, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'ending')]


class OptionDescriptionPremiumRule(metaclass=PoolMeta):
    __name__ = 'offered.option.description.premium_rule'

    def must_be_rated(self, rated_instance, date):
        Option = Pool().get('contract.option')
        if isinstance(rated_instance, Option):
            validity_end = rated_instance.parent_contract.premium_validity_end
            if validity_end and date and date > validity_end:
                return False
        return super().must_be_rated(rated_instance, date)
