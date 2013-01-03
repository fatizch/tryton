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
        PackageCoverage,
        Product,
        ProductOptionsCoverage,
        GenericBusinessRule,
        BusinessRuleRoot,
        PricingRule,
        PricingComponent,
        EligibilityRule,
        EligibilityRelationKind,
        Benefit,
        BenefitRule,
        ReserveRule,
        CoverageAmountRule,
        DeductibleRule,
        ProductDefinition,
        DynamicDataManager,
        TermRenewalRule,
        CoopSchemaElement,
        SchemaElementRelation,
        # from rule_sets
        SubscriberContext,
        PersonContext,
        ContractContext,
        OptionContext,
        CoveredDataContext,
        RuleCombinationContext,
        ClauseRule,
        Clause,
        ClauseRelation,
        ClauseVersion,
        module='insurance_product', type_='model')
