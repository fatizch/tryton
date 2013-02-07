from trytond.pool import Pool
from rule_engine_results import *
from rule_sets import *
from .product import *
from .complementary_data import *
from .business_rule import *
from .coverage import *
from .benefit import *
from .clause import *


def register():
    Pool.register(
        # from product
        Offered,
        ItemDescriptor,
        Coverage,
        PackageCoverage,
        Product,
        ProductOptionsCoverage,
        ComplementaryDataDefinition,
        ItemDescriptorComplementaryDataRelation,
        ProductItemDescriptorRelation,
        # from business_rule
        BusinessRuleRoot,
        DocumentDesc,
        DocumentRule,
        DocumentRuleRelation,
        DocumentRequest,
        Document,
        PricingRule,
        PricingComponent,
        EligibilityRule,
        EligibilityRelationKind,
        EventDesc,
        LossDesc,
        LossDescDocumentsRelation,
        EventDescLossDescRelation,
        Benefit,
        CoverageBenefitRelation,
        BenefitLossDescRelation,
        BenefitRule,
        ReserveRule,
        CoverageAmountRule,
        DeductibleRule,
        ProductDefinition,
        TermRenewalRule,
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
        ProductComplementaryDataRelation,
        CoverageComplementaryDataRelation,
        LossDescComplementaryDataRelation,
        module='insurance_product', type_='model')
