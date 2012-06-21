from trytond.pool import Pool
from product import *


def register():
    Pool.register(
        BusinessRuleManager,
        Offered,
        Coverage,
        Product,
        ProductOptionsCoverage,
        GenericBusinessRule,
        BusinessRuleRoot,
        PricingRule,
        EligibilityRule,
        module='insurance_product', type_='model')
