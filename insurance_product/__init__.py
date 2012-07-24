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
        PricingContext_Contract,
        module='insurance_product', type_='model')
