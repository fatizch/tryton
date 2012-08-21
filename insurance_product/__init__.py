from trytond.pool import Pool
from rule_engine_results import *
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
        Benefit,
        BenefitRule,
        ReserveRule,
        CoverageAmountRule,
        module='insurance_product', type_='model')
