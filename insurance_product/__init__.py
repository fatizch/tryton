from trytond.pool import Pool
from rule_engine_results import *
from rule_sets import *
from .product import *
from .dynamic_data import *
from .business_rule import *
from .coverage import *
from .benefit import *
from .clause import *


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
        PriceCalculator,
        PricingData,
        EligibilityRule,
        EligibilityRelationKind,
        Benefit,
        BenefitRule,
        ReserveRule,
        CoverageAmountRule,
        ProductDefinition,
        DynamicDataManager,
        CoopSchemaElement,
        SchemaElementRelation,
        # from rule_sets
        SubscriberContext,
        PersonContext,
        ContractContext,
        OptionContext,
        CoveredDataContext,
        RuleCombinationContext,
        Clause,
        ClauseRelation,
        ClauseRule,
        ClauseVersion,
        module='insurance_product', type_='model')
