from trytond.pool import Pool
from product import *


def register():
    Pool.register(
        Coverage,
        Product,
        ProductOptionsCoverage,
        BusinessRuleManager,
        GenericBusinessRule,
        PricingRule,
        EligibilityRule,
        module='insurance_product', type_='model')
