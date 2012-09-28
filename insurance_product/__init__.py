from trytond.pool import Pool
from rule_engine_results import *
from rule_sets import *
from .business_family import *
from .product import *


def register():
    Pool.register(
        # from business_family
        BusinessFamily,
        # from product
        BusinessRuleManager,
        Offered,
        Coverage,
        Product,
        ProductOptionsCoverage,
        GenericBusinessRule,
        BusinessRuleRoot,
        PricingRule,
        PriceCalculator,
        PricingData,
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
        RuleCombinationContext,
        module='insurance_product', type_='model')
