from trytond.pool import Pool
from .rule_engine import *
from .offered import *
from .expense import *
from .business_rule import *
from .coverage import *
from .process import *
from .party import *
from .test_case import *
from .batch import *


def register():
    Pool.register(
        # From party
        Party,
        Insurer,
        # From offered
        Offered,
        ItemDescription,
        OptionDescription,
        OfferedOptionDescription,
        Product,
        OfferedProduct,
        ItemDescSubItemDescRelation,
        ItemDescriptionExtraDataRelation,
        # From Batch
        ProductValidationBatch,
        # From rule engine
        RuleEngineExtraData,
        RuleEngine,
        # From business_rule
        BusinessRuleRoot,
        # From business_rule.ir
        Model,
        Attachment,
        # From business_rule.documents_rule
        DocumentTemplate,
        DocumentProductRelation,
        DocumentTemplateVersion,
        DocumentDescription,
        DocumentRule,
        RuleDocumentDescriptionRelation,
        DocumentRequest,
        DocumentRequestLine,
        DocumentCreateSelectTemplate,
        DocumentCreateSelect,
        DocumentCreatePreview,
        DocumentCreateAttach,
        DocumentReceiveRequest,
        DocumentReceiveAttach,
        DocumentReceiveSetRequests,
        DocumentRequestBatch,
        # From business_rule.premium_rule
        PremiumDateConfiguration,
        PremiumRule,
        PremiumRuleComponent,
        TaxVersion,
        FeeVersion,
        # From business_rule.eligibility_rule
        EligibilityRule,
        CoverageAmountRule,
        DeductibleRule,
        DeductibleDuration,
        TermRule,
        # From business_rule.exclusion
        ExclusionKind,
        # From business_rule.extra_premium
        ExtraPremiumKind,
        # From rule_engine
        RuleEngineRuntime,
        # From process
        ProcessProductRelation,
        Process,
        # From Expense
        ExpenseKind,
        # From test_case
        TestCaseModel,
        module='offered_insurance', type_='model')
    Pool.register(
        # From business_rule.documents_rule
        DocumentGenerateReport,
        DocumentFromFilename,
        module='offered_insurance', type_='report')
    Pool.register(
        # From business_rule.documents_rule
        DocumentCreate,
        DocumentReceive,
        module='offered_insurance', type_='wizard')
