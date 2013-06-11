from trytond.pool import Pool
from rule_engine_results import *
from rule_sets import *
from .product import *
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
        Coverage,
        OfferedCoverage,
        Product,
        OfferedProduct,
        ItemDescriptorComplementaryDataRelation,
        ProductItemDescriptorRelation,
        # from business_rule
        RuleEngineComplementaryDataRelation,
        RuleEngine,
        BusinessRuleRoot,
        # from documents_rule
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
        DocumentRequestBatch,
        # from pricing_rule
        SimplePricingRule,
        PricingRule,
        PricingComponent,
        TaxVersion,
        FeeVersion,
        # from eligibility_rule
        EligibilityRule,
        EligibilityRelationKind,
        EventDesc,
        LossDesc,
        LossDescDocumentsRelation,
        EventDescLossDescRelation,
        Benefit,
        InsuranceBenefit,
        CoverageBenefitRelation,
        BenefitLossDescRelation,
        BenefitComplementaryDataRelation,
        BenefitRule,
        SubBenefitRule,
        ReserveRule,
        CoverageAmountRule,
        DeductibleRule,
        DeductibleDuration,
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
