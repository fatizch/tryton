#-*- coding:utf-8 -*-
from trytond.modules.insurance_product.business_rule import pricing_rule
from trytond.modules.insurance_collective import GroupRoot


class GroupPricingData(GroupRoot, pricing_rule.PricingData):
    'Pricing Data'

    __name__ = 'ins_collective.pricing_data'


class GroupPriceCalculator(GroupRoot, pricing_rule.PriceCalculator):
    'Price Calculator'

    __name__ = 'ins_collective.pricing_calculator'


class GroupPricingRule(GroupRoot, pricing_rule.PricingRule):
    'Pricing Rule'

    __name__ = 'ins_collective.pricing_rule'
