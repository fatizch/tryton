from trytond.pool import Pool
from rule_sets import *
from .product import *
from .business_rule import *
from .coverage import *
from .benefit import *
from .clause import *
from .process import *
from .party import *
from .test_case import *


def register():
    Pool.register(
        # From party
        Party,
        Insurer,
        # From product
        Offered,
        ItemDescriptor,
        Coverage,
        OfferedCoverage,
        Product,
        OfferedProduct,
        ItemDescSubItemDescRelation,
        ItemDescriptorComplementaryDataRelation,
        ProductItemDescriptorRelation,
        ProductValidationBatch,
        # From business_rule
        RuleEngineParameter,
        RuleEngine,
        DimensionDisplayer,
        BusinessRuleRoot,
        # From business_rule.ir
        PrintableModel,
        NoTargetCheckAttachment,
        # From business_rule.documents_rule
        LetterModel,
        LetterVersion,
        DocumentDesc,
        DocumentRule,
        DocumentRuleRelation,
        DocumentRequest,
        Document,
        LetterModelDisplayer,
        LetterModelSelection,
        AttachmentCreation,
        RequestFinder,
        AttachmentSetter,
        DocumentRequestDisplayer,
        DocumentRequestBatch,
        # From business_rule.pricing_rule
        PricingRule,
        PricingComponent,
        TaxVersion,
        FeeVersion,
        # From business_rule.eligibility_rule
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
        # From rule_sets
        SubscriberContext,
        PersonContext,
        OptionContext,
        CoveredDataContext,
        RuleCombinationContext,
        ClauseRule,
        Clause,
        ClauseRelation,
        ClauseVersion,
        LossDescComplementaryDataRelation,
        # From process
        ProcessProductRelation,
        ProcessDesc,
        ExpenseKind,
        # From test_case
        TestCaseModel,
        module='insurance_product', type_='model')
    Pool.register(
        # From business_rule.documents_rule
        LetterReport,
        module='insurance_product', type_='report')
    Pool.register(
        # From business_rule.documents_rule
        LetterGeneration,
        ReceiveDocuments,
        module='insurance_product', type_='wizard')
