from trytond.pool import Pool
from rule_engine_results import *
from rule_sets import *
from .product import *
from .complementary_data import *
from .business_rule import *
from .coverage import *
from .benefit import *
from .clause import *
from .process import *


def register():
    Pool.register(
        # from product
        Offered,
        ItemDescriptor,
        SimpleCoverage,
        Coverage,
        PackageCoverage,
        Product,
        ProductOptionsCoverage,
        # from complementary_data
        ComplementaryDataDefinition,
        ComplementaryDataRecursiveRelation,
        ItemDescriptorComplementaryDataRelation,
        ProductItemDescriptorRelation,
        # from business_rule
        RuleEngineComplementaryDataRelation,
        RuleEngine,
        BusinessRuleRoot,
        OverridenModel,
        LetterModel,
        LetterVersion,
        DocumentDesc,
        DocumentRule,
        DocumentRuleRelation,
        DocumentRequest,
        Document,
        LetterModelDisplayer,
        LetterModelSelection,
        NoTargetCheckAttachment,
        AttachmentCreation,
        RequestFinder,
        AttachmentSetter,
        DocumentRequestDisplayer,
        SimplePricingRule,
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
        BenefitComplementaryDataRelation,
        BenefitRule,
        SubBenefitRule,
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
        # from process
        ProcessProductRelation,
        ProcessDesc,
        ExpenseKind,
        module='insurance_product', type_='model')
    Pool.register(
        LetterReport,
        module='insurance_product', type_='report')
    Pool.register(
        LetterGeneration,
        ReceiveDocuments,
        module='insurance_product', type_='wizard')
