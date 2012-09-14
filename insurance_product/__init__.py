from trytond.pool import Pool
from rule_engine_results import *
from rule_sets import *
from .product import *


def register():
    Pool.register(
        # from product
        BusinessRuleManager,
        Offered,
        Coverage,
        Product,
        ProductOptionsCoverage,
        GenericBusinessRule,
        BusinessRuleRoot,
        PricingRule,
        EligibilityRule,
        EligibilityRelationKind,
        Benefit,
        BenefitRule,
        ReserveRule,
        CoverageAmountRule,
        # from rule_sets
        SubscriberContext,
        PersonContext,
        CoveredDataContext,
        module='insurance_product', type_='model')
