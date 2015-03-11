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
from .exclusion import *
from .extra_premium import *


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
        # From business_rule.documents_rule
        CoverageAmountRule,
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
